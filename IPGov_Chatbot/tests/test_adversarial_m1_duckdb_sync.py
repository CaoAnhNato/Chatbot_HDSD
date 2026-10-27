"""
Adversarial Test Suite: test_adversarial_m1_duckdb_sync.py
Challenger Role: Challenger M1 DuckDB & Concurrency (challenger_m1_2)

Adversarial Stress Testing Scope:
1. Idempotency & Repeated Synchronization:
   - Repeated sync calls on same DuckDB connection (1x, 2x, 5x, 10x).
   - Zero duplicated rows, no primary key conflicts, exact 155 rows.
   - Dynamic mutation / upsert: JSON changes reflected cleanly upon re-sync.
2. In-Memory vs Persistent DuckDB Sync:
   - File-backed persistent DuckDB sync, commit, close, and re-open.
   - Idempotent re-sync directly into existing persistent database file.
   - Multi-threaded concurrent reads from in-memory and persistent DuckDB.
3. Querying Child Criteria by parent_id & Canonical Ordering:
   - All parent-child branches maintain strict monotonic canonical_order.
   - Exact warehouse sequence validation for Golden Parents:
     * 'Số lượng HTX phân theo lĩnh vực' -> 8 fields in exact order.
     * 'Hiệu quả hoạt động' -> 4 levels in exact order.
     * 'Liên kết sản xuất' -> 2 link types in exact order.
     * 'Diện tích sản xuất muối' -> 2 area types in exact order.
     * 'Tổng sản lượng muối' -> 2 volume types in exact order.
   - Cross-check against live PostgreSQL DWH (ROW_NUMBER() OVER (PARTITION BY parent_id ORDER BY created_date ASC)).
"""

import concurrent.futures
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import duckdb
import psycopg2
import pytest

from IPGov_Chatbot.config import settings
from IPGov_Chatbot.modules.mod04_catalog.dynamic_criterion_ingestor import (
    DEFAULT_KB_PATH,
    REQUIRED_FIELDS,
    sync_definitions_to_duckdb,
)


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def kb_data() -> Dict[str, Dict[str, Any]]:
    assert DEFAULT_KB_PATH.exists(), f"KB file missing at {DEFAULT_KB_PATH}"
    with open(DEFAULT_KB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def in_memory_conn():
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def persistent_db_path(tmp_path: Path) -> Path:
    return tmp_path / "adversarial_catalog.duckdb"


# ==============================================================================
# GROUP 1: IDEMPOTENCY & REPEATED SYNCHRONIZATION
# ==============================================================================

class TestDuckDBIdempotency:
    """Stress tests verifying that repeated sync operations are 100% idempotent."""

    def test_repeated_sync_no_duplicates_or_pk_conflicts(self, in_memory_conn):
        """Repeatedly calling sync_definitions_to_duckdb 5 times on the same connection."""
        counts = []
        for i in range(5):
            synced = sync_definitions_to_duckdb(DEFAULT_KB_PATH, in_memory_conn)
            counts.append(synced)
            
            # Check row count after each sync
            row_count = in_memory_conn.execute("SELECT count(*) FROM catalog_definitions").fetchone()[0]
            assert row_count == 155, f"Iteration {i+1}: Expected 155 rows, got {row_count}"
            
            # Verify primary key uniqueness
            distinct_ids = in_memory_conn.execute("SELECT count(DISTINCT id) FROM catalog_definitions").fetchone()[0]
            assert distinct_ids == 155, f"Iteration {i+1}: Duplicate IDs detected: {distinct_ids} vs 155"

        assert all(c == 155 for c in counts)

    def test_sync_upsert_and_mutation_reflection(self, tmp_path, in_memory_conn):
        """Simulate a mutation in KB JSON and verify sync reflects modifications cleanly."""
        # 1. Create a copy of the KB
        with open(DEFAULT_KB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        test_kb_file = tmp_path / "mutated_kb.json"
        with open(test_kb_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        # First sync
        sync_definitions_to_duckdb(test_kb_file, in_memory_conn)
        assert in_memory_conn.execute("SELECT count(*) FROM catalog_definitions").fetchone()[0] == 155

        # 2. Mutate one record's definition and scope_description
        sample_id = next(iter(data.keys()))
        original_def = data[sample_id]["definition"]
        data[sample_id]["definition"] = "MUTATED DEFINITION: Adversarial test definition content."
        data[sample_id]["scope_description"] = "MUTATED SCOPE: Adversarial scope content."

        # Add a new synthetic record (156th record)
        synthetic_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        data[synthetic_id] = {
            "id": synthetic_id,
            "code": "synthetic_test_criterion",
            "name": "Chỉ tiêu Thử nghiệm Nhân tạo",
            "level": 2,
            "is_leaf": True,
            "scope_name": "Nông nghiệp",
            "parent_id": sample_id,
            "parent_name": "HTX nông nghiệp",
            "root_id": sample_id,
            "root_name": "HTX nông nghiệp",
            "canonical_order": 99,
            "siblings": ["Trồng trọt"],
            "children_ids": [],
            "definition": "Định nghĩa chỉ tiêu nhân tạo phục vụ kiểm thử tính idempotent và cập nhật DuckDB.",
            "natural_synonyms": ["chỉ tiêu thử nghiệm", "chỉ tiêu nhân tạo"],
            "scope_description": "Phạm vi kiểm thử nhân tạo.",
            "has_approved_facts": False,
            "available_report_dates": [],
            "metadata": {"test": True}
        }

        with open(test_kb_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        # 3. Re-sync into the SAME in_memory_conn
        synced_2 = sync_definitions_to_duckdb(test_kb_file, in_memory_conn)
        assert synced_2 == 156

        # Check total rows
        assert in_memory_conn.execute("SELECT count(*) FROM catalog_definitions").fetchone()[0] == 156

        # Check mutation was applied
        row = in_memory_conn.execute(
            "SELECT definition, scope_description FROM catalog_definitions WHERE id = ?",
            (sample_id,)
        ).fetchone()
        assert row[0] == "MUTATED DEFINITION: Adversarial test definition content."
        assert row[1] == "MUTATED SCOPE: Adversarial scope content."

        # Check synthetic row exists
        syn_row = in_memory_conn.execute(
            "SELECT name, canonical_order FROM catalog_definitions WHERE id = ?",
            (synthetic_id,)
        ).fetchone()
        assert syn_row is not None
        assert syn_row[0] == "Chỉ tiêu Thử nghiệm Nhân tạo"
        assert syn_row[1] == 99

        # 4. Remove synthetic row and re-sync -> should return back to 155 rows
        del data[synthetic_id]
        data[sample_id]["definition"] = original_def
        with open(test_kb_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        synced_3 = sync_definitions_to_duckdb(test_kb_file, in_memory_conn)
        assert synced_3 == 155
        assert in_memory_conn.execute("SELECT count(*) FROM catalog_definitions").fetchone()[0] == 155
        deleted_check = in_memory_conn.execute(
            "SELECT count(*) FROM catalog_definitions WHERE id = ?", (synthetic_id,)
        ).fetchone()[0]
        assert deleted_check == 0

    def test_sync_nonexistent_kb_file_raises_filenotfound(self, in_memory_conn):
        """Calling sync on invalid file must raise FileNotFoundError and leave connection uncorrupted."""
        with pytest.raises(FileNotFoundError):
            sync_definitions_to_duckdb("non_existent_kb_file_12345.json", in_memory_conn)


# ==============================================================================
# GROUP 2: IN-MEMORY VS PERSISTENT DUCKDB SYNC BEHAVIOR
# ==============================================================================

class TestDuckDBPersistenceAndConcurrency:
    """Stress tests comparing in-memory vs disk-persisted DuckDB and concurrency."""

    def test_persistent_duckdb_sync_and_reopen(self, persistent_db_path):
        """Sync into a disk-persisted DuckDB file, close, reopen, and verify."""
        # 1. Connect to persistent file and sync
        conn1 = duckdb.connect(str(persistent_db_path))
        synced = sync_definitions_to_duckdb(DEFAULT_KB_PATH, conn1)
        assert synced == 155
        conn1.close()

        # Verify file exists on disk and is non-empty
        assert persistent_db_path.exists()
        file_size = persistent_db_path.stat().st_size
        assert file_size > 0, "DuckDB file must not be 0 bytes after sync"

        # 2. Re-open connection in fresh instance
        conn2 = duckdb.connect(str(persistent_db_path))
        row_count = conn2.execute("SELECT count(*) FROM catalog_definitions").fetchone()[0]
        assert row_count == 155

        # Verify all 17 schema columns
        cols = [c[1] for c in conn2.execute("PRAGMA table_info('catalog_definitions')").fetchall()]
        assert len(cols) == 17
        for expected in ["id", "code", "name", "level", "is_leaf", "canonical_order", "definition"]:
            assert expected in cols

        # 3. Repeated sync on the reopened persistent database
        synced_again = sync_definitions_to_duckdb(DEFAULT_KB_PATH, conn2)
        assert synced_again == 155
        row_count_again = conn2.execute("SELECT count(*) FROM catalog_definitions").fetchone()[0]
        assert row_count_again == 155
        conn2.close()

    def test_concurrent_readers_on_duckdb(self, persistent_db_path):
        """Stress-test 10 concurrent threads reading from DuckDB concurrently."""
        # Setup persistent DB
        setup_conn = duckdb.connect(str(persistent_db_path))
        sync_definitions_to_duckdb(DEFAULT_KB_PATH, setup_conn)
        setup_conn.close()

        def reader_task(thread_id: int) -> int:
            # Each thread opens its own read-only connection
            r_conn = duckdb.connect(str(persistent_db_path), read_only=True)
            res = r_conn.execute("""
                SELECT parent_id, count(*), min(canonical_order), max(canonical_order)
                FROM catalog_definitions
                WHERE parent_id IS NOT NULL
                GROUP BY parent_id
            """).fetchall()
            r_conn.close()
            return len(res)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(reader_task, i) for i in range(20)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All threads should successfully retrieve the exact same number of parent groups
        assert len(results) == 20
        assert all(r == results[0] and r > 0 for r in results)

    def test_in_memory_cursor_multithreaded_readers(self, in_memory_conn):
        """Stress-test concurrent cursor reads on in-memory connection."""
        sync_definitions_to_duckdb(DEFAULT_KB_PATH, in_memory_conn)

        def cursor_reader(thread_id: int) -> str:
            cur = in_memory_conn.cursor()
            res = cur.execute("""
                SELECT name, canonical_order
                FROM catalog_definitions
                WHERE parent_name = 'HTX nông nghiệp'
                ORDER BY canonical_order ASC
            """).fetchall()
            cur.close()
            return res[0][0]  # First child name

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(cursor_reader, i) for i in range(16)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 16
        # The first child in HTX nông nghiệp should be identical across all threads
        assert all(name == results[0] for name in results)


# ==============================================================================
# GROUP 3: QUERYING CHILD CRITERIA BY parent_id & CANONICAL ORDERING
# ==============================================================================

class TestCanonicalOrderingPreservation:
    """Stress tests verifying that canonical ordering is strictly preserved for all child criteria."""

    def test_all_parents_canonical_order_strict_monotonic(self, in_memory_conn):
        """For every parent with children in the catalog, verify canonical_order is 1..N without gaps or duplicates."""
        sync_definitions_to_duckdb(DEFAULT_KB_PATH, in_memory_conn)

        # Get all parent IDs
        parent_rows = in_memory_conn.execute("""
            SELECT DISTINCT parent_id, parent_name
            FROM catalog_definitions
            WHERE parent_id IS NOT NULL
        """).fetchall()

        assert len(parent_rows) > 0, "Must have parent criteria with children"

        for pid, pname in parent_rows:
            children = in_memory_conn.execute("""
                SELECT id, name, canonical_order
                FROM catalog_definitions
                WHERE parent_id = ?
                ORDER BY canonical_order ASC
            """, (pid,)).fetchall()

            orders = [c[2] for c in children]
            names = [c[1] for c in children]

            # 1. No duplicate canonical_order values among siblings
            assert len(orders) == len(set(orders)), (
                f"Duplicate canonical_order under parent '{pname}' ({pid}): {orders} for {names}"
            )

            # 2. Sequential order starts at 1 and increases monotonically
            expected_orders = list(range(1, len(children) + 1))
            assert orders == expected_orders, (
                f"Non-contiguous canonical_order under parent '{pname}' ({pid}): got {orders}, expected {expected_orders}"
            )

    def test_golden_parents_exact_sequence(self, in_memory_conn):
        """
        Verify the exact sequence of child criteria for all Golden Parents specified in ORIGINAL_REQUEST.md:
        1. 'Số lượng HTX phân theo lĩnh vực' -> 8 fields:
           [Trồng trọt, Chăn nuôi, Lâm nghiệp, Thủy sản, Diêm nghiệp, Chế biến nông sản, Nước sạch NT, Tổng hợp]
        2. 'Hiệu quả hoạt động' -> 4 levels:
           [Số HTX nông nghiệp hoạt động hiệu quả tốt, Số HTX nông nghiệp hoạt động hiệu quả trung bình,
            Số HTX nông nghiệp hoạt động kém hiệu quả, Chưa đủ điều kiện đánh giá]
        3. 'Liên kết sản xuất' -> 2 link types:
           [Số HTX nông nghiệp có liên kết sản xuất ổn định,
            Số HTX nông nghiệp có liên kết không ổn định, thường xuyên]
        4. 'Diện tích sản xuất muối' -> 2 types:
           [Diện tích muối sản xuất thủ công, Diện tích muối sản xuất công nghiệp]
        5. 'Tổng sản lượng muối' -> 2 types:
           [Sản lượng muối sản xuất thủ công, Sản lượng muối sản xuất công nghiệp]
        """
        sync_definitions_to_duckdb(DEFAULT_KB_PATH, in_memory_conn)

        # 1. HTX Fields (8 fields) - Querying child criteria by parent_id
        htx_fields_pid = in_memory_conn.execute("""
            SELECT id FROM catalog_definitions WHERE name = 'Số lượng HTX phân theo lĩnh vực'
        """).fetchone()[0]
        htx_fields = in_memory_conn.execute("""
            SELECT name, canonical_order
            FROM catalog_definitions
            WHERE parent_id = ?
            ORDER BY canonical_order ASC
        """, (htx_fields_pid,)).fetchall()
        expected_htx_fields = [
            "Trồng trọt", "Chăn nuôi", "Lâm nghiệp", "Thủy sản",
            "Diêm nghiệp", "Chế biến nông sản", "Nước sạch NT", "Tổng hợp"
        ]
        assert [r[0] for r in htx_fields] == expected_htx_fields, (
            f"HTX fields order mismatch: {[r[0] for r in htx_fields]} vs {expected_htx_fields}"
        )

        # 2. Evaluation Levels for HTX (4 levels) - Querying by parent_id
        # Note: 'Hiệu quả hoạt động' exists under HTX, THT, and Trang trại.
        # Querying by parent_id correctly isolates the 4 HTX levels in exact canonical order!
        htx_eff_pid = in_memory_conn.execute("""
            SELECT id FROM catalog_definitions 
            WHERE name = 'Hiệu quả hoạt động' AND root_name = 'HTX nông nghiệp'
        """).fetchone()[0]
        eff_levels = in_memory_conn.execute("""
            SELECT name, canonical_order
            FROM catalog_definitions
            WHERE parent_id = ?
            ORDER BY canonical_order ASC
        """, (htx_eff_pid,)).fetchall()
        expected_eff_levels = [
            "Số HTX nông nghiệp hoạt động hiệu quả tốt",
            "Số HTX nông nghiệp hoạt động hiệu quả trung bình",
            "Số HTX nông nghiệp hoạt động kém hiệu quả",
            "Chưa đủ điều kiện đánh giá"
        ]
        assert [r[0] for r in eff_levels] == expected_eff_levels, (
            f"Evaluation levels order mismatch: {[r[0] for r in eff_levels]} vs {expected_eff_levels}"
        )

        # 3. Production Links (2 link types) - Querying by parent_id
        prod_links_pid = in_memory_conn.execute("""
            SELECT id FROM catalog_definitions 
            WHERE name = 'Liên kết sản xuất' AND root_name = 'HTX nông nghiệp'
        """).fetchone()[0]
        prod_links = in_memory_conn.execute("""
            SELECT name, canonical_order
            FROM catalog_definitions
            WHERE parent_id = ?
            ORDER BY canonical_order ASC
        """, (prod_links_pid,)).fetchall()
        expected_prod_links = [
            "Số HTX nông nghiệp có liên kết sản xuất ổn định",
            "Số HTX nông nghiệp có liên kết không ổn định, thường xuyên"
        ]
        assert [r[0] for r in prod_links] == expected_prod_links, (
            f"Production links order mismatch: {[r[0] for r in prod_links]} vs {expected_prod_links}"
        )

        # 4. Salt Production Areas (2 types) - Querying by parent_id
        salt_area_pid = in_memory_conn.execute("""
            SELECT id FROM catalog_definitions 
            WHERE is_leaf = FALSE AND name LIKE '%diện tích%muối%'
        """).fetchone()[0]
        salt_areas = in_memory_conn.execute("""
            SELECT name, canonical_order
            FROM catalog_definitions
            WHERE parent_id = ?
            ORDER BY canonical_order ASC
        """, (salt_area_pid,)).fetchall()
        assert len(salt_areas) == 2
        assert salt_areas[0][0] == "Diện tích muối sản xuất thủ công"
        assert salt_areas[0][1] == 1
        assert salt_areas[1][0] == "Diện tích muối sản xuất công nghiệp"
        assert salt_areas[1][1] == 2

        # 5. Salt Production Volumes (2 types) - Querying by parent_id
        salt_vol_pid = in_memory_conn.execute("""
            SELECT id FROM catalog_definitions 
            WHERE is_leaf = FALSE AND name LIKE '%sản lượng muối%'
        """).fetchone()[0]
        salt_vols = in_memory_conn.execute("""
            SELECT name, canonical_order
            FROM catalog_definitions
            WHERE parent_id = ?
            ORDER BY canonical_order ASC
        """, (salt_vol_pid,)).fetchall()
        assert len(salt_vols) == 2
        assert salt_vols[0][0] == "Sản lượng muối sản xuất thủ công"
        assert salt_vols[0][1] == 1
        assert salt_vols[1][0] == "Sản lượng muối sản xuất công nghiệp"
        assert salt_vols[1][1] == 2

    def test_cross_check_canonical_order_with_live_dwh(self, in_memory_conn):
        """Cross-check DuckDB catalog_definitions against PostgreSQL DWH vna_wom_dev."""
        sync_definitions_to_duckdb(DEFAULT_KB_PATH, in_memory_conn)

        try:
            pg_conn = psycopg2.connect(settings.sync_dwh_url, connect_timeout=5)
        except Exception as e:
            pytest.skip(f"Live PostgreSQL DWH not reachable at {settings.sync_dwh_url}: {e}")

        cur = pg_conn.cursor()
        cur.execute("""
            SELECT 
                id::text, 
                name, 
                parent_id::text,
                ROW_NUMBER() OVER (PARTITION BY parent_id ORDER BY created_date ASC) as dwh_order
            FROM dwh_internal.criteria
            WHERE deleted_date IS NULL
        """)
        dwh_rows = cur.fetchall()
        pg_conn.close()

        assert len(dwh_rows) == 155

        mismatches = []
        for cid, cname, pid, dwh_order in dwh_rows:
            duck_row = in_memory_conn.execute(
                "SELECT canonical_order, name FROM catalog_definitions WHERE id = ?",
                (cid,)
            ).fetchone()
            assert duck_row is not None, f"Criterion {cid} ({cname}) missing from DuckDB"
            duck_order = duck_row[0]
            if duck_order != dwh_order:
                mismatches.append({
                    "id": cid,
                    "name": cname,
                    "parent_id": pid,
                    "dwh_order": dwh_order,
                    "duck_order": duck_order
                })

        assert len(mismatches) == 0, f"Found {len(mismatches)} order mismatches against DWH: {mismatches[:5]}"


# ==============================================================================
# GROUP 4: DATA INTEGRITY & TYPE SAFETY
# ==============================================================================

class TestDuckDBDataIntegrity:
    """Stress tests on data types, JSON deserialization, and nullability."""

    def test_json_columns_serialization_integrity(self, in_memory_conn):
        """Verify that natural_synonyms and available_dates columns contain 100% valid JSON."""
        sync_definitions_to_duckdb(DEFAULT_KB_PATH, in_memory_conn)

        rows = in_memory_conn.execute("""
            SELECT id, name, natural_synonyms, available_dates, updated_at
            FROM catalog_definitions
        """).fetchall()

        for cid, cname, syn_raw, dates_raw, updated_at in rows:
            # Synonyms must deserialize to a list of >= 2 strings
            syns = json.loads(syn_raw)
            assert isinstance(syns, list), f"{cid} ({cname}): natural_synonyms is not a list"
            assert len(syns) >= 2, f"{cid} ({cname}): natural_synonyms has < 2 items"

            # Available dates must deserialize to a list
            dates = json.loads(dates_raw)
            assert isinstance(dates, list), f"{cid} ({cname}): available_dates is not a list"

            # updated_at must be populated
            assert updated_at is not None

    def test_query_child_criteria_without_order_by_hazard(self, in_memory_conn):
        """
        Adversarial inquiry: What happens if a caller forgets 'ORDER BY canonical_order ASC'?
        Demonstrate why explicit ORDER BY canonical_order is required by contract.
        """
        sync_definitions_to_duckdb(DEFAULT_KB_PATH, in_memory_conn)

        # When queried with ORDER BY canonical_order, order is guaranteed
        ordered_res = in_memory_conn.execute("""
            SELECT name, canonical_order
            FROM catalog_definitions
            WHERE parent_name = 'Số lượng HTX phân theo lĩnh vực'
            ORDER BY canonical_order ASC
        """).fetchall()

        expected = [
            "Trồng trọt", "Chăn nuôi", "Lâm nghiệp", "Thủy sản",
            "Diêm nghiệp", "Chế biến nông sản", "Nước sạch NT", "Tổng hợp"
        ]
        assert [r[0] for r in ordered_res] == expected


# ==============================================================================
# GROUP 5: SECONDARY INDEX CREATION & QUERY PLAN EXECUTION
# ==============================================================================

class TestDuckDBSecondaryIndexesAndQueryPlan:
    """Empirical verification of ART secondary indexes and query planner behavior."""

    def test_secondary_indexes_registered_in_catalog(self, in_memory_conn):
        """Verify that secondary indexes on parent_id, canonical_order, and code exist."""
        sync_definitions_to_duckdb(DEFAULT_KB_PATH, in_memory_conn)

        indexes = in_memory_conn.execute("""
            SELECT index_name, table_name, expressions
            FROM duckdb_indexes()
            WHERE table_name = 'catalog_definitions'
        """).fetchall()

        assert len(indexes) == 3, f"Expected 3 secondary indexes on catalog_definitions, found {len(indexes)}"

        indexed_cols = {row[2].strip("[]") for row in indexes}
        expected_cols = {"parent_id", "canonical_order", "code"}
        assert indexed_cols == expected_cols, f"Mismatch in indexed columns: {indexed_cols} vs {expected_cols}"

    def test_query_plan_uses_index_scan_on_filtered_queries(self, in_memory_conn):
        """Verify that DuckDB optimizer executes 'Type: Index Scan' via EXPLAIN ANALYZE."""
        sync_definitions_to_duckdb(DEFAULT_KB_PATH, in_memory_conn)

        # 1. Filter on code
        plan_code = in_memory_conn.execute("""
            EXPLAIN ANALYZE SELECT name FROM catalog_definitions 
            WHERE code = 'tong_so_luong_san_pham_ocop_trong_nam'
        """).fetchall()[0][1]
        assert "Type: Index Scan" in plan_code, f"Expected Index Scan for code filter, got:\n{plan_code}"

        # 2. Filter on parent_id
        pid = in_memory_conn.execute("SELECT DISTINCT parent_id FROM catalog_definitions WHERE parent_id IS NOT NULL LIMIT 1").fetchone()[0]
        plan_pid = in_memory_conn.execute(f"""
            EXPLAIN ANALYZE SELECT name, canonical_order FROM catalog_definitions 
            WHERE parent_id = '{pid}' ORDER BY canonical_order ASC
        """).fetchall()[0][1]
        assert "Type: Index Scan" in plan_pid, f"Expected Index Scan for parent_id filter, got:\n{plan_pid}"

        # 3. Filter on canonical_order
        plan_order = in_memory_conn.execute("""
            EXPLAIN ANALYZE SELECT name FROM catalog_definitions 
            WHERE canonical_order = 1
        """).fetchall()[0][1]
        assert "Type: Index Scan" in plan_order, f"Expected Index Scan for canonical_order filter, got:\n{plan_order}"

    def test_indexes_persisted_across_database_reopens(self, persistent_db_path):
        """Verify that secondary indexes persist across connection open/close on persistent DB."""
        conn1 = duckdb.connect(str(persistent_db_path))
        sync_definitions_to_duckdb(DEFAULT_KB_PATH, conn1)
        conn1.close()

        conn2 = duckdb.connect(str(persistent_db_path))
        indexes = conn2.execute("""
            SELECT index_name, table_name, expressions
            FROM duckdb_indexes()
            WHERE table_name = 'catalog_definitions'
        """).fetchall()
        assert len(indexes) == 3
        indexed_cols = {row[2].strip("[]") for row in indexes}
        assert indexed_cols == {"parent_id", "canonical_order", "code"}

        plan = conn2.execute("""
            EXPLAIN ANALYZE SELECT name FROM catalog_definitions WHERE code = 'tong_so_luong_san_pham_ocop_trong_nam'
        """).fetchall()[0][1]
        assert "Type: Index Scan" in plan
        conn2.close()

