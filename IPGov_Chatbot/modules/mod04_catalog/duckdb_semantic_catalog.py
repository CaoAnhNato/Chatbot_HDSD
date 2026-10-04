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
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import duckdb
import numpy as np
from openai import OpenAI
from rapidfuzz import fuzz, process

from IPGov_Chatbot.config import settings
from IPGov_Chatbot.core.model_registry import ModelRegistry
from IPGov_Chatbot.schemas.catalog_dto import ColumnMetadataDTO, TableMetadataDTO

logger = logging.getLogger(__name__)


class DuckDBSemanticCatalog:
    """
    DuckDB In-Memory Catalog quản lý toàn bộ siêu dữ liệu DWH.
    Áp dụng cơ chế Hybrid Dual-Mode Hydration:
    - Thử kết nối Docker PostgreSQL vna_wom_dev lúc khởi động.
    - Fallback tự động nạp từ data/catalog_seed_metadata.json khi offline hoặc chạy CI.
    - Tích hợp SOTA Hybrid Dense/Sparse RRF Retrieval & Micro-LLM Disambiguation.
    """

    def __init__(self, seed_path: Optional[str] = None) -> None:
        self.conn = duckdb.connect(":memory:")
        self.seed_path = Path(seed_path or Path(__file__).resolve().parent.parent.parent / "data" / "catalog_seed_metadata.json")
        self._table_metadata_cache: Dict[str, TableMetadataDTO] = {}
        self._alias_registry: List[Dict[str, Any]] = []
        self._embed_model: Optional[Any] = None
        self._criteria_embeddings: Optional[np.ndarray] = None
        self._criteria_cache_codes: List[str] = []
        self._criteria_cache_names: List[str] = []
        self._criteria_cache_aliases: List[str] = []
        self._criteria_cache_tenants: List[str] = []
        self._criteria_cache_levels: List[int] = []
        self._init_schema()
        self._hydrate_catalog()
        self._build_indexes()
        self._ensure_embeddings_indexed()


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
                aliases VARCHAR,
                tenant_code VARCHAR
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
                year_code VARCHAR NOT NULL,
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
                year_code VARCHAR NOT NULL,
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
                host=settings.DWH_HOST,
                port=settings.DWH_PORT,
                dbname=settings.DWH_DB,
                user=settings.DWH_USER,
                password=settings.DWH_PASSWORD,
                connect_timeout=3
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
                           NOT EXISTS (SELECT 1 FROM dwh_internal.criteria sub WHERE sub.parent_id = c.id) AS is_leaf,
                           c.tenant_code
                    FROM dwh_internal.criteria c
                    WHERE c.deleted_date IS NULL;
                """)
                pg_crits = cur.fetchall()
                existing_ids = set(r[0] for r in self.conn.execute("SELECT id FROM catalog_criteria;").fetchall())
                new_crit_rows = []
                for cid, code, name, lvl, is_leaf, tenant_code in pg_crits:
                    str_cid = str(cid)
                    tc = str(tenant_code or "")
                    if str_cid and str_cid not in existing_ids and code and name:
                        new_crit_rows.append((str_cid, code, name, "", lvl or 1, is_leaf, "", tc))
                        existing_ids.add(str_cid)
                        self._alias_registry.append({
                            "alias": name.lower().strip(),
                            "code": code,
                            "name": name,
                            "type": "criteria",
                            "target_table": "dwh_internal.criteria",
                            "tenant_code": tc
                        })
                if new_crit_rows:
                    self.conn.executemany("INSERT INTO catalog_criteria VALUES (?, ?, ?, ?, ?, ?, ?, ?)", new_crit_rows)
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
            tc = c.get("tenant_code", "68")
            crit_rows.append((
                str(c["id"]), c["code"], c["name"], c.get("unit"), c["level"], c["is_leaf"], aliases_str, tc
            ))
            # Đăng ký alias cho RapidFuzz
            for al in c.get("aliases", []):
                self._alias_registry.append({
                    "alias": al.lower().strip(),
                    "code": c["code"],
                    "name": c["name"],
                    "type": "criteria",
                    "target_table": "dwh_internal.criteria",
                    "tenant_code": tc
                })
        self.conn.executemany("INSERT INTO catalog_criteria VALUES (?, ?, ?, ?, ?, ?, ?, ?)", crit_rows)

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
            m_year = str(m.get("year_code", m.get("year", "2026")))
            mission_rows.append((m["id"], m["code"], m["name"], m_year, m["department_code"], m["status"]))
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
            f_year = str(f.get("year_code", f.get("year", "2026")))
            form_rows.append((f["id"], f["code"], f["name"], f_year, f["department_code"], f["is_active"], f["status"]))
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

    def match_alias_or_abbreviation(self, term: str, threshold: float = 75.0, tenant_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Sử dụng RapidFuzz C++ để đối chiếu mờ từ viết tắt hoặc danh xưng công vụ
        với danh mục alias đã đăng ký trong RAM (hỗ trợ phân vùng tenant_code).
        """
        term_clean = term.lower().strip()
        candidates = self._alias_registry
        if tenant_code:
            candidates = [
                a for a in self._alias_registry
                if not a.get("tenant_code") or a.get("tenant_code") == tenant_code or a.get("tenant_code") == "00"
            ]
        if not candidates:
            return None

        alias_names = [a["alias"] for a in candidates]
        match = process.extractOne(term_clean, alias_names, scorer=fuzz.ratio)
        if match and match[1] >= threshold:
            idx = match[2]
            res = candidates[idx].copy()
            res["match_score"] = match[1]
            return res
        return None

    def get_table_metadata(self, table_name: str) -> Optional[TableMetadataDTO]:
        """Truy xuất DTO siêu dữ liệu của một bảng."""
        return self._table_metadata_cache.get(table_name)

    def _ensure_embeddings_indexed(self) -> None:
        """Nạp hoặc tính toán ma trận Dense Embeddings cho catalog_criteria (có cơ chế Disk Cache v2 thuần name)."""
        if self._criteria_embeddings is not None and len(self._criteria_cache_codes) > 0:
            return

        rows = self.conn.execute("SELECT code, name, aliases, tenant_code, level FROM catalog_criteria;").fetchall()
        self._criteria_cache_codes = [r[0] for r in rows]
        self._criteria_cache_names = [r[1] for r in rows]
        self._criteria_cache_aliases = [r[2] or "" for r in rows]
        self._criteria_cache_tenants = [r[3] or "" for r in rows]
        self._criteria_cache_levels = [r[4] or 1 for r in rows]

        cache_dir = Path(__file__).resolve().parent.parent.parent / "data" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        emb_cache_path = cache_dir / "criteria_embeddings_v2_name_only.npy"
        meta_cache_path = cache_dir / "criteria_meta_v2_name_only.json"

        # 1. Thử nạp từ đĩa
        if emb_cache_path.exists() and meta_cache_path.exists():
            try:
                with open(meta_cache_path, "r", encoding="utf-8") as f:
                    cached_meta = json.load(f)
                if (
                    cached_meta.get("codes") == self._criteria_cache_codes
                    and cached_meta.get("tenants") == self._criteria_cache_tenants
                ):
                    self._criteria_embeddings = np.load(emb_cache_path)
                    logger.info("Đã nạp %d vector embeddings từ cache đĩa v2 thuần name.", len(self._criteria_cache_codes))
                    return
            except Exception as e:
                logger.warning("Không thể nạp cache embedding từ đĩa: %s. Tính toán lại...", e)

        # 2. Tính toán embeddings nếu chưa có cache (Chỉ embed trên name và aliases, loại bỏ 100% code)
        try:
            embed_model = ModelRegistry.get_embedding_model()

            texts = []
            for n, a in zip(self._criteria_cache_names, self._criteria_cache_aliases):
                a_clean = a.strip()
                if a_clean:
                    texts.append(f"{n} ({a_clean})")
                else:
                    texts.append(n)

            self._criteria_embeddings = embed_model.encode(texts, normalize_embeddings=True)
            np.save(emb_cache_path, self._criteria_embeddings)
            with open(meta_cache_path, "w", encoding="utf-8") as f:
                json.dump({
                    "codes": self._criteria_cache_codes,
                    "tenants": self._criteria_cache_tenants
                }, f)
            logger.info("Đã tính toán và lưu cache v2 %d vector embeddings thành công.", len(texts))
        except Exception as e:
            logger.warning("⚠️ [DuckDBSemanticCatalog] Không thể tính toán remote embedding (%s). Hệ thống tự động chuyển sang fallback text-matching.", e)
            self._criteria_embeddings = None

    def _llm_disambiguate(self, query: str, candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Gọi micro-prompt LLM (< 150 tokens) để giải quyết nhập nhằng hoặc chọn chỉ tiêu chính xác."""
        try:
            client = OpenAI(
                api_key=settings.effective_llm_api_key,
                base_url=settings.OPENROUTER_BASE_URL
            )
            cand_text = "\n".join([f"{i+1}. [{c['code']}] {c['name']}" for i, c in enumerate(candidates)])
            system_prompt = (
                "Bạn là trợ lý giải quyết nhập nhằng ngữ nghĩa chỉ tiêu (Criteria Disambiguator) cho kho dữ liệu chính phủ.\n"
                "Nhiệm vụ: Căn cứ vào câu hỏi người dùng và danh sách chỉ tiêu ứng viên:\n"
                "- Nếu câu hỏi chỉ rõ đại lượng cụ thể (như 'số vụ', 'số người', 'chi phí', 'diện tích'...), hãy chọn 1 chỉ tiêu chính xác nhất và trả về JSON:\n"
                "  {\"status\": \"MATCH\", \"code\": \"<selected_code>\", \"name\": \"<selected_name>\", \"reason\": \"<giải thích ngắn>\"}\n"
                "- Nếu câu hỏi quá bao trùm hoặc mơ hồ (chưa nói rõ đại lượng nào, ví dụ chỉ nói chung chung 'khuyến công', 'tai nạn lao động'), hãy trả về JSON:\n"
                "  {\"status\": \"AMBIGUOUS\", \"candidates\": [{\"code\": \"<code_1>\", \"name\": \"<name_1>\"}, ...], \"reason\": \"<lý do cần làm rõ>\"}\n"
                "CHỈ TRẢ VỀ JSON THUẦN TÚY, KHÔNG CÓ TEXT NGOÀI JSON."
            )
            user_prompt = f"Câu hỏi: {query}\nDanh sách ứng viên:\n{cand_text}"
            resp = client.chat.completions.create(
                model=settings.OPENROUTER_LIGHT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
                max_tokens=250
            )
            raw = resp.choices[0].message.content or ""
            raw_clean = raw.strip()
            if raw_clean.startswith("```json"):
                raw_clean = raw_clean[7:]
            if raw_clean.startswith("```"):
                raw_clean = raw_clean[3:]
            if raw_clean.endswith("```"):
                raw_clean = raw_clean[:-3]
            return json.loads(raw_clean.strip())
        except Exception as e:
            logger.warning("Lỗi LLM Disambiguation: %s", e)
            return None

    def find_criteria_by_name(
        self,
        query: str,
        limit: int = 1,
        top_k_candidates: int = 5,
        use_llm_disambiguation: bool = True,
        tenant_code: Optional[str] = "68",
        role_level: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Tìm kiếm tiêu chí (criteria) phù hợp nhất bằng SOTA Hybrid Search (Dense Embedding + Sparse BM25 via RRF)
        kết hợp Generative LLM Micro-Disambiguation (google/gemini-2.5-flash-lite).
        Cưỡng chế Pre-filtering theo tenant_code và role_level.
        So khớp thuần theo name và aliases, loại bỏ 100% mã kỹ thuật code.
        """
        if not query:
            return []

        q_clean = query.lower().strip()

        # 1. Thử đối chiếu nhanh qua Alias Registry có phân vùng tenant
        alias_match = self.match_alias_or_abbreviation(q_clean, threshold=85.0, tenant_code=tenant_code)
        if alias_match and alias_match.get("type") in ("criteria", "acronym"):
            return [{
                "code": alias_match["code"],
                "name": alias_match["name"],
                "score": alias_match.get("match_score", 100.0),
                "is_ambiguous": False,
                "candidates": [{
                    "code": alias_match["code"],
                    "name": alias_match["name"],
                    "rrf_score": 1.0
                }]
            }]

        self._ensure_embeddings_indexed()
        if len(self._criteria_cache_codes) == 0:
            return []

        # 2. Pre-filtering: Xác định tập chỉ số hợp lệ theo tenant_code và role_level
        valid_indices = []
        for i, (tc, lvl) in enumerate(zip(self._criteria_cache_tenants, self._criteria_cache_levels)):
            if tenant_code and tc and tc != tenant_code and tc != "00":
                continue
            if role_level == 3:
                # Role 3 (Công dân): Chỉ truy cập các chỉ tiêu công khai (level <= 2)
                if lvl > 2:
                    continue
            valid_indices.append(i)

        if not valid_indices:
            # Fallback nếu không có tiêu chí nào khớp tenant
            valid_indices = list(range(len(self._criteria_cache_codes)))

        # 3. Dense Semantic Search (chỉ duyệt/xếp hạng trên valid_indices nếu có embeddings)
        dense_ranked = []
        if self._criteria_embeddings is not None:
            try:
                embed_model = ModelRegistry.get_embedding_model()
                q_emb = embed_model.encode([query], normalize_embeddings=True)[0]
                dense_sims = np.dot(self._criteria_embeddings, q_emb)
                valid_dense_scores = [(i, float(dense_sims[i])) for i in valid_indices]
                valid_dense_scores.sort(key=lambda x: x[1], reverse=True)
                seen_dense_codes = set()
                for i, score in valid_dense_scores:
                    c = self._criteria_cache_codes[i]
                    if c not in seen_dense_codes:
                        seen_dense_codes.add(c)
                        dense_ranked.append((c, self._criteria_cache_names[i], score))
                        if len(dense_ranked) >= 20:
                            break
            except Exception as e:
                logger.warning("⚠️ [DuckDBSemanticCatalog] Lỗi trích xuất dense vector query (%s), tiếp tục với sparse.", e)

        # 4. Sparse Search via RapidFuzz token_set_ratio trên name và aliases (chỉ trên valid_indices)
        sparse_scores = []
        for i in valid_indices:
            name = self._criteria_cache_names[i]
            aliases = self._criteria_cache_aliases[i]
            target_text = f"{name} ({aliases})" if aliases else name
            s_score = fuzz.token_set_ratio(q_clean, target_text.lower())
            sparse_scores.append((i, s_score))
        sparse_scores.sort(key=lambda x: x[1], reverse=True)
        seen_sparse_codes = set()
        sparse_ranked = []
        for i, score in sparse_scores:
            c = self._criteria_cache_codes[i]
            if c not in seen_sparse_codes:
                seen_sparse_codes.add(c)
                sparse_ranked.append((c, self._criteria_cache_names[i], score))
                if len(sparse_ranked) >= 20:
                    break

        # 5. Reciprocal Rank Fusion (RRF)
        rrf_dict: Dict[str, float] = {}
        details: Dict[str, Dict[str, Any]] = {}
        for rank, (code, name, score) in enumerate(dense_ranked):
            rrf_dict[code] = rrf_dict.get(code, 0.0) + 1.0 / (60.0 + rank + 1)
            details[code] = {"name": name, "dense_score": float(score), "dense_rank": rank + 1}
        for rank, (code, name, score) in enumerate(sparse_ranked):
            rrf_dict[code] = rrf_dict.get(code, 0.0) + 1.0 / (60.0 + rank + 1)
            if code in details:
                details[code]["sparse_score"] = float(score)
                details[code]["sparse_rank"] = rank + 1
            else:
                details[code] = {"name": name, "sparse_score": float(score), "sparse_rank": rank + 1}

        sorted_candidates = sorted(rrf_dict.items(), key=lambda x: x[1], reverse=True)[:top_k_candidates]
        candidates = []
        for code, rrf_score in sorted_candidates:
            candidates.append({
                "code": code,
                "name": details[code]["name"],
                "rrf_score": rrf_score,
                "dense_score": details[code].get("dense_score", 0.0),
                "sparse_score": details[code].get("sparse_score", 0.0),
            })

        if not candidates:
            return []

        # 6. Generative LLM Micro-Disambiguation (< 150 tokens)
        if use_llm_disambiguation and settings.effective_llm_api_key:
            disambig_res = self._llm_disambiguate(query, candidates)
            if disambig_res:
                if disambig_res.get("status") == "MATCH" and disambig_res.get("code"):
                    matched_code = disambig_res["code"]
                    matched_name = disambig_res.get("name") or next((c["name"] for c in candidates if c["code"] == matched_code), matched_code)
                    return [{
                        "code": matched_code,
                        "name": matched_name,
                        "score": 98.0,
                        "is_ambiguous": False,
                        "reason": disambig_res.get("reason", "LLM exact disambiguation match"),
                        "candidates": candidates
                    }]
                elif disambig_res.get("status") == "AMBIGUOUS":
                    return [{
                        "code": candidates[0]["code"],
                        "name": candidates[0]["name"],
                        "score": 70.0,
                        "is_ambiguous": True,
                        "reason": disambig_res.get("reason", "Truy vấn mang tính bao trùm, cần người dùng làm rõ"),
                        "candidates": disambig_res.get("candidates") or candidates
                    }]

        # Fallback khi tắt LLM hoặc API lỗi: trả về Top-1 candidate từ RRF
        top1 = candidates[0]
        return [{
            "code": top1["code"],
            "name": top1["name"],
            "score": float(top1.get("dense_score", 0.8) * 100.0),
            "is_ambiguous": False,
            "candidates": candidates[:limit]
        }]

    def find_top_k_candidates(
        self,
        query: str,
        top_k: int = 5,
        score_cutoff: float = 60.0,
        tenant_code: Optional[str] = "68"
    ) -> Tuple[List[Dict[str, Any]], bool, float]:
        """
        Trích xuất Top-K ứng viên chỉ tiêu từ DuckDB In-Memory Catalog bằng Hybrid RRF (Dense + Sparse).
        Căn cứ: ADR-002, implementation_plan.md
        Trả về: (candidates, is_ambiguous, score_delta)
        - candidates: Danh sách ứng viên có score >= score_cutoff (tối đa top_k)
        - is_ambiguous: True nếu câu hỏi quá vắn tắt hoặc score delta giữa Top 1 & Top 2 < 0.10
        - score_delta: Điểm chênh lệch giữa Top 1 và Top 2
        """
        import unicodedata
        if not query:
            return ([], False, 0.0)

        q_clean = unicodedata.normalize('NFC', query.strip())
        q_lower = q_clean.lower()

        # 1. Tra cứu qua find_criteria_by_name với top_k_candidates mở rộng
        raw_res = self.find_criteria_by_name(
            query=q_clean,
            limit=top_k,
            top_k_candidates=max(top_k * 2, 10),
            use_llm_disambiguation=False,
            tenant_code=tenant_code
        )

        all_candidates = []
        if raw_res and raw_res[0].get("candidates"):
            all_candidates = raw_res[0]["candidates"]
        elif raw_res:
            all_candidates = raw_res

        # 2. Lọc và chuẩn hóa score kết hợp
        valid_candidates = []
        for c in all_candidates:
            raw_c_score = float(c.get("score", 0.0)) or (float(raw_res[0].get("score", 0.0)) if raw_res else 0.0)
            d_score = float(c.get("dense_score", 0.0)) * 100.0
            s_score = float(c.get("sparse_score", 0.0))
            if d_score > 0 or s_score > 0:
                comb_score = round(d_score * 0.6 + s_score * 0.4, 2) if s_score > 0 else round(d_score, 2)
            else:
                comb_score = round(raw_c_score, 2) if raw_c_score > 0 else 85.0
            c_name = unicodedata.normalize('NFC', c["name"].strip())

            # Thưởng điểm nếu khớp tuyệt đối
            if c_name.lower() == q_lower:
                comb_score = 100.0
            elif c_name.lower() in q_lower:
                comb_score = max(comb_score, 85.0)

            if comb_score >= score_cutoff:
                valid_candidates.append({
                    "code": c.get("code"),
                    "name": c_name,
                    "score": comb_score,
                    "dense_score": round(d_score, 2),
                    "sparse_score": round(s_score, 2),
                })

        valid_candidates.sort(key=lambda x: x["score"], reverse=True)

        # Ưu tiên chỉ tiêu tổng thể (Tổng ...) khi câu hỏi mang tính khái quát (không chỉ rõ phân loại con)
        tong_candidates = [c for c in valid_candidates if c["name"].lower().startswith("tổng ")]
        if tong_candidates and valid_candidates:
            best_tong = tong_candidates[0]
            top_1 = valid_candidates[0]
            if best_tong != top_1:
                # Nếu query không có các từ đặc thù của top_1 (ví dụ 'công nghiệp', 'thủ công')
                top1_extra_words = [w for w in top_1["name"].lower().split() if w not in best_tong["name"].lower() and len(w) > 2]
                has_specific_sub_in_query = any(w in q_lower for w in top1_extra_words)
                if not has_specific_sub_in_query and (top_1["score"] - best_tong["score"]) <= 5.0:
                    valid_candidates.remove(best_tong)
                    best_tong["score"] = top_1["score"] + 1.0
                    valid_candidates.insert(0, best_tong)

        top_candidates = valid_candidates[:top_k]

        # 3. Tính toán score_delta
        if len(top_candidates) >= 2:
            score_delta = round((top_candidates[0]["score"] - top_candidates[1]["score"]) / 100.0, 4)
        elif len(top_candidates) == 1:
            score_delta = 1.0
        else:
            score_delta = 0.0

        # 4. Xác định cờ mơ hồ (is_ambiguous)
        words = [
            w for w in q_lower.split()
            if len(w) > 1
            and not re.match(r"^202[0-9]$", w)
            and w not in ["là", "của", "tại", "năm", "bao", "nhiêu", "có", "tổng", "số", "lượng"]
        ]
        is_ambiguous = False
        if len(words) < 2 and len(top_candidates) >= 2:
            is_ambiguous = True
        elif len(top_candidates) >= 2 and score_delta < 0.10:
            # Nếu ứng viên top 1 có sparse_score >= 90.0 (khớp từ vựng chính xác cao) -> không xem là mơ hồ
            if top_candidates[0].get("sparse_score", 0.0) >= 90.0:
                is_ambiguous = False
            elif top_candidates[0]["name"].lower().startswith("tổng"):
                # Ưu tiên chỉ tiêu tổng thể (aggregate) khi có các phân loại con
                is_ambiguous = False
            elif top_candidates[0]["score"] < 100.0:
                is_ambiguous = True

        return (top_candidates, is_ambiguous, score_delta)

    def resolve_administrative_scope(self, term: str, admin_level_hint: Optional[int] = None) -> Dict[str, Any]:
        """
        Phân giải phạm vi hành chính đa cấp (Tenant / Department / Office).
        Triệt tiêu 100% heuristic substring 'in' gây nuốt phạm vi cấp Tỉnh.
        """
        if not term:
            return {"type": "unknown", "tenant_code": "68", "department_code": None, "office_id": None, "admin_level": None}

        t_clean = term.lower().strip()
        provincial_keywords = [
            "lâm đồng", "toàn tỉnh", "cả tỉnh", "toàn bộ tỉnh", "tỉnh lâm đồng", 
            "tất cả các sở", "toàn bộ các sở", "ubnd tỉnh lâm đồng"
        ]

        # 1. Cấp 0: Toàn tỉnh
        if admin_level_hint == 0 or any(pk == t_clean or pk in t_clean for pk in provincial_keywords):
            if not ("sở " in t_clean or "phòng " in t_clean):
                return {
                    "type": "tenant",
                    "tenant_code": "68",
                    "name": "Tỉnh Lâm Đồng",
                    "department_code": None,
                    "office_id": None,
                    "admin_level": 0
                }

        # 2. Cấp 1: Sở Ban Ngành (department)
        dept_rows = self.conn.execute("SELECT code, name, level, tenant_code FROM catalog_departments WHERE level = 1;").fetchall()
        best_dept = None
        best_dept_score = 0.0
        for code, name, lvl, t_code in dept_rows:
            score = fuzz.token_set_ratio(t_clean, name.lower())
            if score > best_dept_score:
                best_dept_score = score
                best_dept = (code, name, t_code)

        if best_dept and best_dept_score >= 80.0:
            return {
                "type": "department",
                "department_code": best_dept[0],
                "code": best_dept[0],
                "name": best_dept[1],
                "tenant_code": best_dept[2],
                "office_id": None,
                "admin_level": 1
            }

        # 3. Cấp 2: Phòng Ban (office)
        off_rows = self.conn.execute("SELECT id, name, department_code, tenant_code FROM catalog_offices;").fetchall()
        best_off = None
        best_off_score = 0.0
        for oid, name, dcode, t_code in off_rows:
            score = fuzz.token_set_ratio(t_clean, name.lower())
            if score > best_off_score:
                best_off_score = score
                best_off = (oid, name, dcode, t_code)

        if best_off and best_off_score >= 80.0:
            return {
                "type": "office",
                "office_id": str(best_off[0]),
                "code": str(best_off[0]),
                "name": best_off[1],
                "department_code": best_off[2],
                "tenant_code": best_off[3],
                "admin_level": 2
            }

        return {"type": "unknown", "tenant_code": "68", "department_code": None, "office_id": None, "admin_level": None}

    def find_department_or_office(self, term: str, admin_level_hint: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Đối chiếu tên phòng ban hoặc cơ quan sở ngành từ tên gọi / từ khóa.
        Sử dụng resolve_administrative_scope để bảo đảm Invariance Cấp Tỉnh.
        """
        res = self.resolve_administrative_scope(term, admin_level_hint=admin_level_hint)
        if res.get("type") in ("tenant", "department", "office"):
            return res
        return None

    def is_compatible(self, topic_entity: str, metric_attribute: str) -> bool:
        """
        Schema Compatibility Gate (Điểm chốt 1 - v1.4.0):
        Kiểm tra xem thuộc tính mới (metric_attribute, ví dụ: 'diện tích', 'hộ', 'sản lượng', 'chức vụ')
        có tương thích ngữ nghĩa và có tồn tại trong CSDL DWH đối với thực thể chủ đề (topic_entity, ví dụ: 'sản xuất muối') hay không.
        
        Trả về True nếu:
        - Tồn tại chỉ tiêu trong catalog_criteria kết hợp cả topic_entity và metric_attribute.
        - Hoặc topic_entity thuộc bảng nghiệp vụ phi-criteria (user/mission/report) và metric_attribute là cột hợp lệ.
        """
        if not topic_entity or not metric_attribute:
            return False

        t_low = topic_entity.lower().strip()
        m_low = metric_attribute.lower().strip()

        # 1. Kiểm tra miền cán bộ & nhân sự (user, user_mission)
        personnel_topics = ["cán bộ", "chuyên viên", "nhân sự", "người", "admin", "qtv", "lãnh đạo", "thành viên", "phân công"]
        personnel_attrs = ["chức vụ", "vị trí", "đơn vị", "phòng ban", "chi cục", "nhiệm vụ", "họ và tên", "tên", "username", "công tác", "phụ trách"]
        if any(pt in t_low for pt in personnel_topics):
            if any(pa in m_low for pa in personnel_attrs):
                return True

        # 2. Kiểm tra miền nhiệm vụ & đề án (mission, office_mission)
        mission_topics = ["nhiệm vụ", "đề án", "chương trình", "kế hoạch"]
        mission_attrs = ["trạng thái", "đơn vị chủ trì", "phòng ban", "phụ trách", "mã nhiệm vụ", "tên nhiệm vụ", "thực hiện"]
        if any(mt in t_low for mt in mission_topics):
            if any(ma in m_low for ma in mission_attrs):
                return True

        # 3. Kiểm tra miền báo cáo (report)
        report_topics = ["báo cáo", "đợt nộp", "kỳ báo cáo"]
        report_attrs = ["trạng thái", "tiến độ", "phê duyệt", "từ chối", "chờ duyệt", "ngày nộp", "đơn vị nộp", "số lượng"]
        if any(rt in t_low for rt in report_topics):
            if any(ra in m_low for ra in report_attrs):
                return True

        # 4. Kiểm tra miền biểu mẫu (collection_form)
        form_topics = ["biểu mẫu", "tờ khai", "mẫu phiếu"]
        form_attrs = ["mã", "tên", "trạng thái", "cơ quan", "ban hành", "danh sách"]
        if any(ft in t_low for ft in form_topics):
            if any(fa in m_low for fa in form_attrs):
                return True

        # 5. Kiểm tra đối soát với catalog_criteria trong RAM
        stop_words = {"tổng", "các", "những", "của", "và", "là", "trong", "cho", "ở", "tại", "năm"}
        t_tokens = [w for w in t_low.split() if w not in stop_words and len(w) > 1]
        m_tokens = [w for w in m_low.split() if w not in stop_words and len(w) > 1]

        if not t_tokens or not m_tokens:
            return False

        try:
            t_main = t_tokens[-1]
            m_main = m_tokens[0]

            check_sql = """
                SELECT COUNT(*) FROM catalog_criteria 
                WHERE LOWER(name) LIKE ? AND LOWER(name) LIKE ?;
            """
            row = self.conn.execute(check_sql, [f"%{t_main}%", f"%{m_main}%"]).fetchone()
            if row and row[0] > 0:
                return True

            if len(t_tokens) > 1:
                t_alt = t_tokens[0]
                row = self.conn.execute(check_sql, [f"%{t_alt}%", f"%{m_main}%"]).fetchone()
                if row and row[0] > 0:
                    return True

            for item in self._alias_registry:
                a_name = item.get("name", "").lower()
                if t_main in a_name and m_main in a_name:
                    return True
        except Exception as e:
            logger.debug("Lỗi kiểm tra tính tương thích criteria: %s", e)

        return False

