"""
Module: IPGov_Chatbot/modules/mod04_catalog/duckdb_semantic_catalog.py
Chức năng: Quản lý DuckDB In-Memory Metadata Catalog, ART Indexes, Native FTS (BM25)
và RapidFuzz C++ semantic similarity matching cho từ viết tắt công vụ.
Căn cứ: Blueprint 03_SEMANTIC_LAYER_MDL_VA_IN_MEMORY_CATALOG.md
"""

from __future__ import annotations
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import duckdb
from rapidfuzz import fuzz, process

from IPGov_Chatbot.schemas.catalog_dto import ColumnMetadataDTO, TableMetadataDTO

logger = logging.getLogger(__name__)


class DuckDBSemanticCatalog:
    """
    DuckDB In-Memory Catalog quản lý toàn bộ siêu dữ liệu DWH.
    Áp dụng cơ chế Hybrid Dual-Mode Hydration:
    - Thử kết nối Docker PostgreSQL vna_wom_dev lúc khởi động.
    - Fallback tự động nạp từ data/catalog_seed_metadata.json khi offline hoặc chạy CI.
    """

    def __init__(self, seed_path: Optional[str] = None) -> None:
        self.conn = duckdb.connect(":memory:")
        self.seed_path = Path(seed_path or Path(__file__).resolve().parent.parent.parent / "data" / "catalog_seed_metadata.json")
        self._table_metadata_cache: Dict[str, TableMetadataDTO] = {}
        self._alias_registry: List[Dict[str, Any]] = []
        self._init_schema()
        self._hydrate_catalog()
        self._build_indexes()

    def _init_schema(self) -> None:
        """Khởi tạo cấu trúc các bảng danh mục trong bộ nhớ RAM của DuckDB."""
        # 1. Bảng siêu dữ liệu bảng và cột
        self.conn.execute("""
            CREATE TABLE catalog_schema_metadata (
                table_name VARCHAR NOT NULL,
                simple_name VARCHAR NOT NULL,
                column_name VARCHAR NOT NULL,
                data_type VARCHAR NOT NULL,
                column_description VARCHAR,
                is_pk BOOLEAN NOT NULL DEFAULT FALSE,
                is_fk BOOLEAN NOT NULL DEFAULT FALSE,
                fk_target VARCHAR,
                table_description VARCHAR
            );
        """)

        # 2. Bảng Danh mục Chỉ tiêu Báo cáo (Criteria Catalog)
        self.conn.execute("""
            CREATE TABLE catalog_criteria (
                id VARCHAR PRIMARY KEY,
                code VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                unit VARCHAR,
                level INTEGER NOT NULL,
                is_leaf BOOLEAN NOT NULL DEFAULT TRUE,
                aliases VARCHAR
            );
        """)

        # 3. Bảng Danh mục Cơ quan (deparment - lưu ý không có chữ t thứ 2 theo TRAP-005)
        self.conn.execute("""
            CREATE TABLE catalog_departments (
                code VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                tenant_code VARCHAR NOT NULL,
                level INTEGER NOT NULL
            );
        """)

        # 4. Bảng Danh mục Phòng ban (Office Catalog)
        self.conn.execute("""
            CREATE TABLE catalog_offices (
                id UUID PRIMARY KEY,
                name VARCHAR NOT NULL,
                code VARCHAR,
                department_code VARCHAR NOT NULL,
                tenant_code VARCHAR NOT NULL,
                level INTEGER NOT NULL
            );
        """)

        # 5. Bảng Danh mục Nhiệm vụ (Mission Catalog)
        self.conn.execute("""
            CREATE TABLE catalog_missions (
                id BIGINT PRIMARY KEY,
                code VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                year VARCHAR NOT NULL,
                department_code VARCHAR NOT NULL,
                status VARCHAR NOT NULL
            );
        """)

        # 6. Bảng Danh mục Biểu mẫu Thu thập (Collection Form Catalog)
        self.conn.execute("""
            CREATE TABLE catalog_collection_forms (
                id BIGINT PRIMARY KEY,
                code VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                year VARCHAR NOT NULL,
                department_code VARCHAR NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                status VARCHAR NOT NULL
            );
        """)

        # 7. Bảng Nhật ký Đồng bộ (Sync Metadata)
        self.conn.execute("""
            CREATE TABLE catalog_sync_meta (
                last_synced_at TIMESTAMP NOT NULL,
                dwh_pipeline_run_at TIMESTAMP NOT NULL,
                total_criteria INTEGER NOT NULL,
                total_departments INTEGER NOT NULL,
                total_offices INTEGER NOT NULL,
                total_missions INTEGER NOT NULL,
                total_forms INTEGER NOT NULL,
                status VARCHAR NOT NULL
            );
        """)

    def _hydrate_catalog(self) -> None:
        """
        Cơ chế Hybrid Dual-Mode Hydration:
        Luôn nạp toàn bộ cấu trúc schema, aliases, acronyms và dữ liệu hạt giống từ seed file làm baseline.
        Sau đó, nếu kết nối Live PostgreSQL vna_wom_dev khả dụng thì đồng bộ và cập nhật thêm dữ liệu thực tế.
        Đảm bảo DuckDB RAM và Alias Registry KHÔNG BAO GIỜ bị rỗng!
        """
        # 1. Luôn nạp baseline từ seed file
        self._hydrate_from_seed_file()

        # 2. Thử kết nối Live PostgreSQL vna_wom_dev để đồng bộ thêm dữ liệu thực tế
        try:
            import psycopg2
            conn_pg = psycopg2.connect(
                host=os.getenv("DWH_HOST", "localhost"),
                port=int(os.getenv("DWH_PORT", "5432")),
                dbname=os.getenv("DWH_DB", "vna_wom_dev"),
                user=os.getenv("DWH_USER", "postgres"),
                password=os.getenv("DWH_PASS", "postgres"),
                connect_timeout=1
            )
            cur = conn_pg.cursor()
            # Cập nhật mốc pipeline thực tế từ pipeline_logs
            try:
                cur.execute("SELECT model_name, last_run_at, status FROM dwh_internal.pipeline_logs ORDER BY last_run_at DESC LIMIT 1;")
                log_row = cur.fetchone()
                if log_row:
                    self.conn.execute(
                        "UPDATE catalog_sync_meta SET dwh_pipeline_run_at = ?, status = ?;",
                        (str(log_row[1]), str(log_row[2]))
                    )
            except Exception:
                pass

            # Đồng bộ danh mục chỉ tiêu thực tế từ dwh_internal.criteria
            try:
                cur.execute("""
                    SELECT c.id, c.code, c.name, c.level,
                           NOT EXISTS (SELECT 1 FROM dwh_internal.criteria sub WHERE sub.parent_id = c.id) AS is_leaf
                    FROM dwh_internal.criteria c
                    WHERE c.deleted_date IS NULL;
                """)
                pg_crits = cur.fetchall()
                existing_codes = set(r[0] for r in self.conn.execute("SELECT code FROM catalog_criteria;").fetchall())
                new_crit_rows = []
                for cid, code, name, lvl, is_leaf in pg_crits:
                    if code and code not in existing_codes and name:
                        new_crit_rows.append((str(cid), code, name, "", lvl or 1, is_leaf, ""))
                        existing_codes.add(code)
                        self._alias_registry.append({
                            "alias": name.lower().strip(),
                            "code": code,
                            "name": name,
                            "type": "criteria",
                            "target_table": "dwh_internal.criteria"
                        })
                if new_crit_rows:
                    self.conn.executemany("INSERT INTO catalog_criteria VALUES (?, ?, ?, ?, ?, ?, ?)", new_crit_rows)
                    logger.info("Đã đồng bộ thêm %d chỉ tiêu thực tế từ Live PostgreSQL vào DuckDB Catalog.", len(new_crit_rows))
            except Exception as e:
                logger.warning(f"Không thể đồng bộ criteria từ PG: {e}")

            conn_pg.close()
            logger.info("Đã đồng bộ bổ sung thành công mốc pipeline và danh mục từ Live PostgreSQL vna_wom_dev.")
        except Exception as e:
            logger.info("Hoạt động ở chế độ Offline/Seed Hydration (Không kết nối Live PostgreSQL: %s).", e)

    def _hydrate_from_seed_file(self) -> None:
        """Nạp dữ liệu danh mục từ tệp seed JSON tĩnh."""
        if not self.seed_path.exists():
            raise FileNotFoundError(f"Không tìm thấy tệp seed metadata tại: {self.seed_path}")

        with open(self.seed_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 1. Nạp tables & columns
        schema_rows = []
        for tbl in data.get("tables", []):
            table_name = tbl["table_name"]
            simple_name = tbl.get("simple_name", table_name.split(".")[-1])
            desc = tbl.get("description", "")
            pk = tbl.get("primary_key")
            cols_dto = []
            for col in tbl.get("columns", []):
                cols_dto.append(
                    ColumnMetadataDTO(
                        column_name=col["name"],
                        data_type=col["type"],
                        description=col.get("description", ""),
                        is_pk=col.get("is_pk", False),
                        is_fk=col.get("is_fk", False),
                        fk_target_table=col.get("fk_target")
                    )
                )
                schema_rows.append((
                    table_name,
                    simple_name,
                    col["name"],
                    col["type"],
                    col.get("description", ""),
                    col.get("is_pk", False),
                    col.get("is_fk", False),
                    col.get("fk_target", None),
                    desc
                ))

            self._table_metadata_cache[table_name] = TableMetadataDTO(
                table_name=table_name,
                schema_name=table_name.split(".")[0] if "." in table_name else "dwh_internal",
                description=desc,
                columns=cols_dto,
                primary_key=pk
            )
            # Lưu cả alias simple_name
            self._table_metadata_cache[simple_name] = self._table_metadata_cache[table_name]

        self.conn.executemany(
            "INSERT INTO catalog_schema_metadata VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            schema_rows
        )

        # 2. Nạp criteria
        crit_rows = []
        for c in data.get("criteria", []):
            aliases_str = ", ".join(c.get("aliases", []))
            crit_rows.append((
                str(c["id"]), c["code"], c["name"], c.get("unit"), c["level"], c["is_leaf"], aliases_str
            ))
            # Đăng ký alias cho RapidFuzz
            for al in c.get("aliases", []):
                self._alias_registry.append({
                    "alias": al.lower().strip(),
                    "code": c["code"],
                    "name": c["name"],
                    "type": "criteria",
                    "target_table": "dwh_internal.criteria"
                })
        self.conn.executemany("INSERT INTO catalog_criteria VALUES (?, ?, ?, ?, ?, ?, ?)", crit_rows)

        # 3. Nạp departments
        dept_rows = []
        for d in data.get("departments", []):
            dept_rows.append((d["code"], d["name"], d["tenant_code"], d["level"]))
            # Đăng ký alias
            self._alias_registry.append({
                "alias": d["name"].lower().strip(),
                "code": d["code"],
                "name": d["name"],
                "type": "department",
                "target_table": "dwh_internal.deparment"
            })
        self.conn.executemany("INSERT INTO catalog_departments VALUES (?, ?, ?, ?)", dept_rows)

        # 4. Nạp offices
        office_rows = []
        for o in data.get("offices", []):
            office_rows.append((o["id"], o["name"], o.get("code"), o["department_code"], o["tenant_code"], o["level"]))
            self._alias_registry.append({
                "alias": o["name"].lower().strip(),
                "code": str(o["id"]),
                "name": o["name"],
                "type": "office",
                "target_table": "dwh_internal.office"
            })
        self.conn.executemany("INSERT INTO catalog_offices VALUES (?, ?, ?, ?, ?, ?)", office_rows)

        # 5. Nạp missions
        mission_rows = []
        for m in data.get("missions", []):
            mission_rows.append((m["id"], m["code"], m["name"], m["year"], m["department_code"], m["status"]))
            self._alias_registry.append({
                "alias": m["name"].lower().strip(),
                "code": m["code"],
                "name": m["name"],
                "type": "mission",
                "target_table": "dwh_internal.mission"
            })
        self.conn.executemany("INSERT INTO catalog_missions VALUES (?, ?, ?, ?, ?, ?)", mission_rows)

        # 6. Nạp collection_forms
        form_rows = []
        for f in data.get("collection_forms", []):
            form_rows.append((f["id"], f["code"], f["name"], f["year"], f["department_code"], f["is_active"], f["status"]))
            self._alias_registry.append({
                "alias": f["name"].lower().strip(),
                "code": f["code"],
                "name": f["name"],
                "type": "collection_form",
                "target_table": "dwh_internal.collection_form"
            })
        self.conn.executemany("INSERT INTO catalog_collection_forms VALUES (?, ?, ?, ?, ?, ?, ?)", form_rows)

        # 7. Nạp sync_meta
        sm = data.get("sync_meta", {})
        self.conn.execute(
            "INSERT INTO catalog_sync_meta VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                sm.get("last_synced_at", "2026-09-26T00:00:00"),
                sm.get("dwh_pipeline_run_at", "2026-09-26T00:00:00"),
                sm.get("total_criteria", 0),
                sm.get("total_departments", 0),
                sm.get("total_offices", 0),
                sm.get("total_missions", 0),
                sm.get("total_forms", 0),
                sm.get("status", "SUCCESS")
            )
        )

        # Đăng ký các từ viết tắt phổ biến công vụ vào Alias Registry
        common_acronyms = [
            ("tnlđ", "tai_nan_lao_dong_2", "Tai nạn lao động", "dwh_internal.criteria"),
            ("tnld", "tai_nan_lao_dong_2", "Tai nạn lao động", "dwh_internal.criteria"),
            ("tai nạn lđ", "tai_nan_lao_dong_2", "Tai nạn lao động", "dwh_internal.criteria"),
            ("dvc", "ho_so_dvc", "Dịch vụ công", "dwh_internal.criteria"),
            ("cchc", "cai_cach_hanh_chinh", "Cải cách hành chính", "dwh_internal.criteria"),
            ("khuyen cong", "kinh_phi_khuyen_cong", "Khuyến công", "dwh_internal.criteria"),
            ("bieu mau", "collection_form", "Biểu mẫu thu thập", "dwh_internal.collection_form"),
            ("collection form", "collection_form", "Biểu mẫu", "dwh_internal.collection_form"),
            ("nhiem vu", "mission", "Nhiệm vụ trọng tâm", "dwh_internal.mission"),
            ("ds phong ban ubnd tinh ld", "deparment", "Danh sách phòng ban đơn vị", "dwh_internal.deparment"),
            ("ubnd tinh ld", "deparment", "UBND Tỉnh Lâm Đồng", "dwh_internal.deparment"),
        ]
        for acr, code, name, tbl in common_acronyms:
            self._alias_registry.append({
                "alias": acr.lower().strip(),
                "code": code,
                "name": name,
                "type": "acronym",
                "target_table": tbl
            })

    def _build_indexes(self) -> None:
        """Tạo Index ART trên DuckDB để tối ưu tốc độ tra cứu < 1ms."""
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_crit_code ON catalog_criteria(code);")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_crit_name ON catalog_criteria(name);")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_dept_code ON catalog_departments(code);")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_office_name ON catalog_offices(name);")

    def search_tables_by_keywords(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Tìm kiếm các bảng liên quan dựa trên từ khóa truy vấn kết hợp BM25-like matching
        trên schema description và column description.
        """
        tokens = [t.strip().lower() for t in query.split() if len(t.strip()) > 1]
        if not tokens:
            return [{"table_name": "dwh_internal.fact_report_criteria", "score": 1.0}]

        # Quét và tính điểm xuất hiện token trên catalog_schema_metadata
        query_sql = """
            SELECT table_name, count(*) as match_count
            FROM catalog_schema_metadata
            WHERE 
        """
        conditions = []
        params = []
        for t in tokens:
            conditions.append("(LOWER(column_description) LIKE ? OR LOWER(table_description) LIKE ? OR LOWER(column_name) LIKE ?)")
            params.extend([f"%{t}%", f"%{t}%", f"%{t}%"])

        query_sql += " OR ".join(conditions) + " GROUP BY table_name ORDER BY match_count DESC LIMIT ?"
        params.append(limit)

        try:
            rows = self.conn.execute(query_sql, params).fetchall()
            results = []
            for r in rows:
                results.append({"table_name": r[0], "score": float(r[1])})
            if not results:
                # Fallback mặc định Fact
                results = [{"table_name": "dwh_internal.fact_report_criteria", "score": 0.5}]
            return results
        except Exception as e:
            logger.warning("Lỗi tra cứu bảng qua DuckDB: %s", e)
            return [{"table_name": "dwh_internal.fact_report_criteria", "score": 0.5}]

    def match_alias_or_abbreviation(self, term: str, threshold: float = 75.0) -> Optional[Dict[str, Any]]:
        """
        Sử dụng RapidFuzz C++ để đối chiếu mờ từ viết tắt hoặc danh xưng công vụ
        với danh mục alias đã đăng ký trong RAM.
        """
        term_clean = term.lower().strip()
        alias_names = [a["alias"] for a in self._alias_registry]
        match = process.extractOne(term_clean, alias_names, scorer=fuzz.ratio)
        if match and match[1] >= threshold:
            idx = match[2]
            res = self._alias_registry[idx].copy()
            res["match_score"] = match[1]
            return res
        return None

    def get_table_metadata(self, table_name: str) -> Optional[TableMetadataDTO]:
        """Truy xuất DTO siêu dữ liệu của một bảng."""
        return self._table_metadata_cache.get(table_name)

    def find_criteria_by_name(self, query: str, limit: int = 1) -> List[Dict[str, Any]]:
        """
        Tìm kiếm tiêu chí (criteria) phù hợp nhất với câu hỏi / từ khóa
        kết hợp alias registry và RapidFuzz matching trên tên chỉ tiêu / aliases.
        """
        if not query:
            return []

        q_clean = query.lower().strip()

        # 1. Thử match qua alias registry
        alias_match = self.match_alias_or_abbreviation(q_clean, threshold=60.0)
        if alias_match and alias_match.get("type") in ("criteria", "acronym"):
            return [{
                "code": alias_match["code"],
                "name": alias_match["name"],
                "score": alias_match.get("match_score", 100.0),
            }]

        ignore_codes = {
            "1_nam", "6_thang", "nam", "nu", "test", "abc", "numb", "number", "string",
            "num", "num2", "num23", "num23a", "num234", "ewwe", "ewe", "dl1", "123", "31321",
            "name", "name_2", "name_3", "name_4", "option", "nhap_sai", "nam_sinh", "doan_van",
            "do_tuoi", "level_1", "level_2", "muc_chon", "so_tien", "ho_ten", "noi_sinh", "tuoi_x",
            "dulieuma213", "phong_tam", "du_lieu_cap_2", "du_lieu_moi", "san_luong_cay_lau_nam",
            "binh_dang_gioi_o_mien_nam", "dao_tao_nghe_nong_thon", "quy_hoach_vung_tinh",
            "dia_chi_nha", "so_ld_2026", "so_vu_dinh_cong", "so_luong_thon", "thu_1_quy",
            "thu_6_thang", "ngay_thong_ke", "ngay_nhap"
        }
        # 2. Match qua catalog_criteria trực tiếp (exact substring cho tên có nghĩa)
        rows = self.conn.execute("SELECT code, name, aliases FROM catalog_criteria;").fetchall()
        for code, name, aliases in rows:
            if code in ignore_codes or len(name.strip()) < 3:
                continue
            c_low = code.lower()
            n_low = name.lower()
            if len(c_low) >= 6 and c_low in q_clean:
                return [{"code": code, "name": name, "score": 98.0}]
            if len(n_low) >= 6 and n_low in q_clean:
                return [{"code": code, "name": name, "score": 95.0}]
            alias_list = [a.strip().lower() for a in (aliases or "").split(",") if a.strip()]
            for al in alias_list:
                if len(al) >= 5 and al in q_clean:
                    return [{"code": code, "name": name, "score": 90.0}]

        # 3. Fuzzy matching bằng token_set_ratio
        best_code = None
        best_name = None
        best_score = 0.0
        for code, name, aliases in rows:
            if code in ignore_codes or len(name.strip()) <= 4:
                continue
            text = f"{name} {aliases or ''}".lower()
            score = fuzz.token_set_ratio(q_clean, text)
            if score > best_score:
                best_score = score
                best_code = code
                best_name = name

        if best_code and best_score >= 70.0:
            return [{"code": best_code, "name": best_name, "score": best_score}]

        return []

    def find_department_or_office(self, term: str) -> Optional[Dict[str, Any]]:
        """
        Đối chiếu tên phòng ban hoặc cơ quan sở ngành từ tên gọi / từ khóa.
        """
        if not term:
            return None

        t_clean = term.lower().strip()

        # 1. Thử qua match_alias
        alias_match = self.match_alias_or_abbreviation(t_clean, threshold=70.0)
        if alias_match and alias_match.get("type") in ("department", "office", "acronym"):
            return {
                "department_code": alias_match.get("code"),
                "code": alias_match.get("code"),
                "name": alias_match.get("name"),
                "type": alias_match.get("type"),
            }

        # 2. Tra cứu trực tiếp trên catalog_departments
        dept_rows = self.conn.execute("SELECT code, name FROM catalog_departments;").fetchall()
        for c, n in dept_rows:
            if n.lower() in t_clean or t_clean in n.lower():
                return {"department_code": c, "code": c, "name": n, "type": "department"}

        # 3. Tra cứu trên catalog_offices
        off_rows = self.conn.execute("SELECT id, name, department_code FROM catalog_offices;").fetchall()
        for oid, n, dcode in off_rows:
            if n.lower() in t_clean or t_clean in n.lower():
                return {"office_id": str(oid), "name": n, "department_code": dcode, "type": "office"}

        return None
