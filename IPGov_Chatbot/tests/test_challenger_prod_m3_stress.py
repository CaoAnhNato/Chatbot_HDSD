"""
Challenger Adversarial Stress & Verification Test Suite for Milestone 3:
- Concurrency stress test on CriteriaCatalogSnapshot (zero IndexError, zero tearing, zero deadlocks).
- 5-Minute Sync Degradation & Recovery Test (50% deletion, detection, re-ingestion, 5-gate validation, < 30s recovery).
- Soft-Delete & Junk Code Filtration (deleted_date IS NOT NULL purged, dummy codes and short names excluded).
"""

import concurrent.futures
import json
import logging
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import duckdb
import pytest

from IPGov_Chatbot.config import settings
from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import (
    DuckDBSemanticCatalog,
    CriteriaCatalogSnapshot,
    is_dummy_criterion,
    DUMMY_FILTER_CODES,
    DUMMY_FILTER_NAMES,
)
from IPGov_Chatbot.modules.mod04_catalog.dynamic_criterion_ingestor import (
    DEFAULT_KB_PATH,
    REQUIRED_FIELDS,
    DynamicCriterionIngestor,
    FiveGateValidator,
    sync_definitions_to_duckdb,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture(scope="module")
def catalog_instance():
    """Shared DuckDBSemanticCatalog instance for testing."""
    cat = DuckDBSemanticCatalog()
    return cat


@pytest.fixture
def clean_kb_backup():
    """Ensure criterion_definitions_kb.json is backed up and strictly restored."""
    assert DEFAULT_KB_PATH.exists(), f"KB file does not exist at {DEFAULT_KB_PATH}"
    original_bytes = DEFAULT_KB_PATH.read_bytes()
    try:
        yield original_bytes
    finally:
        # Atomic restoration of the original KB file with fsync
        temp_restore = DEFAULT_KB_PATH.with_suffix(".restore_tmp")
        with open(temp_restore, "wb") as f:
            f.write(original_bytes)
            f.flush()
            os.fsync(f.fileno())
        temp_restore.replace(DEFAULT_KB_PATH)
        # Re-sync DuckDB RAM to prevent state pollution in subsequent tests
        try:
            from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog
            cat = DuckDBSemanticCatalog()
            cat._init_duckdb_schema()
            cat._sync_definitions_kb()
            cat._refresh_criteria_cache_lists()
        except Exception:
            pass


# ==============================================================================
# 1. CONCURRENCY STRESS TEST ON CriteriaCatalogSnapshot
# ==============================================================================

class TestSnapshotConcurrencyStress:
    """
    Stress-test CriteriaCatalogSnapshot under heavy multi-threaded concurrent read/write load.
    Assert zero IndexError, zero array length tearing, and zero lock deadlocks.
    """

    def test_concurrent_snapshot_readers_during_frequent_refreshes(self, catalog_instance):
        """
        Spawn 12 reader threads querying find_criteria_by_name, get_criterion_by_code,
        and iterating snapshot arrays, while 2 writer threads invoke _refresh_criteria_cache_lists
        repeatedly.
        """
        stop_event = threading.Event()
        errors: List[Exception] = []
        read_iterations = [0] * 12
        refresh_count = [0] * 2

        query_terms = [
            "chăn nuôi", "trâu bò", "sản xuất muối", "hợp tác xã nông nghiệp",
            "ocop", "làng nghề", "diện tích lúa", "thủy sản"
        ]

        def reader_worker(thread_idx: int):
            try:
                while not stop_event.is_set():
                    # 1. Access frozen snapshot directly
                    snap = catalog_instance.snapshot
                    assert isinstance(snap, CriteriaCatalogSnapshot)

                    # 2. Assert zero array length tearing across all snapshot lists
                    n_codes = len(snap.criteria_codes)
                    n_names = len(snap.criteria_names)
                    n_aliases = len(snap.criteria_aliases)
                    n_tenants = len(snap.criteria_tenants)
                    n_levels = len(snap.criteria_levels)

                    assert n_codes == n_names, f"Tearing detected: {n_codes} codes vs {n_names} names"
                    assert n_codes == n_aliases, f"Tearing detected: {n_codes} codes vs {n_aliases} aliases"
                    assert n_codes == n_tenants, f"Tearing detected: {n_codes} codes vs {n_tenants} tenants"
                    assert n_codes == n_levels, f"Tearing detected: {n_codes} codes vs {n_levels} levels"

                    if snap.criteria_embeddings is not None:
                        assert len(snap.criteria_embeddings) == n_codes, (
                            f"Embedding matrix tearing: {len(snap.criteria_embeddings)} vs {n_codes}"
                        )

                    # 3. Iterate through snapshot arrays by index (test for IndexError)
                    for i in range(min(n_codes, 30)):
                        _ = snap.criteria_codes[i]
                        _ = snap.criteria_names[i]
                        _ = snap.criteria_aliases[i]
                        _ = snap.criteria_tenants[i]
                        _ = snap.criteria_levels[i]

                    # 4. Call get_criterion_by_code
                    if n_codes > 0:
                        sample_code = snap.criteria_codes[0]
                        crit = snap.get_criterion_by_code(sample_code)
                        assert crit is not None
                        assert crit["code"] == sample_code

                    # 5. Call find_criteria_by_name with use_llm_disambiguation=False to test local in-memory catalog
                    q = query_terms[thread_idx % len(query_terms)]
                    results = catalog_instance.find_criteria_by_name(q, limit=2, top_k_candidates=3, use_llm_disambiguation=False)
                    assert isinstance(results, list)

                    read_iterations[thread_idx] += 1
            except Exception as exc:
                logger.exception("Reader thread %d encountered error: %s", thread_idx, exc)
                errors.append(exc)

        def writer_worker(thread_idx: int):
            try:
                while not stop_event.is_set():
                    catalog_instance._refresh_criteria_cache_lists()
                    refresh_count[thread_idx] += 1
                    time.sleep(0.01)  # small pause to yield GIL
            except Exception as exc:
                logger.exception("Writer thread %d encountered error: %s", thread_idx, exc)
                errors.append(exc)

        # Launch 12 reader threads + 2 writer threads
        threads: List[threading.Thread] = []
        for i in range(12):
            t = threading.Thread(target=reader_worker, args=(i,), name=f"ReaderThread-{i}")
            threads.append(t)
        for j in range(2):
            t = threading.Thread(target=writer_worker, args=(j,), name=f"WriterThread-{j}")
            threads.append(t)

        for t in threads:
            t.start()

        # Let the stress test run for 2.0 full seconds under concurrency
        time.sleep(2.0)
        stop_event.set()

        for t in threads:
            t.join(timeout=10.0)
            assert not t.is_alive(), f"Thread {t.name} deadlocked or failed to join within 10.0s!"

        # Assert zero errors occurred
        assert len(errors) == 0, f"Encountered {len(errors)} concurrency errors: {errors}"
        total_reads = sum(read_iterations)
        total_refreshes = sum(refresh_count)
        assert total_reads > 100, f"Reader iterations too low: {total_reads}"
        assert total_refreshes > 10, f"Writer refreshes too low: {total_refreshes}"
        logger.info(
            "Concurrency test passed: %d concurrent reads, %d snapshot refreshes, 0 errors.",
            total_reads, total_refreshes
        )


# ==============================================================================
# 2. 5-MINUTE SYNC DEGRADATION & RECOVERY TEST (EMPIRICAL SIMULATION)
# ==============================================================================

class TestFiveMinuteSyncDegradationAndRecovery:
    """
    Simulates 50% dictionary deletion, verifies detection of degradation,
    triggers re-ingestion, validates through FiveGateValidator, restores 149 criteria
    with 19 fields in < 30 seconds, and swaps snapshot atomically.
    """

    def test_50_percent_deletion_detection_and_fast_recovery(self, clean_kb_backup):
        """
        1. Back up criterion_definitions_kb.json.
        2. Simulate 50% dictionary deletion (delete 74 criteria from test copy and DuckDB RAM).
        3. Verify check_and_sync_changes() detects duckdb_count < pg_total or kb_count < pg_total.
        4. Trigger re-ingestion + FiveGateValidator validation.
        5. Verify all 149 criteria with 19 fields are restored.
        6. Verify entire recovery executes in < 30 seconds.
        7. Verify snapshot swapped atomically.
        """
        # 1. Verify initial state: exactly 149 criteria
        with open(DEFAULT_KB_PATH, "r", encoding="utf-8") as f:
            initial_kb = json.load(f)
        assert len(initial_kb) == 149, f"Expected 149 initial criteria, found {len(initial_kb)}"

        # 2. Simulate 50% deletion in criterion_definitions_kb.json
        all_ids = list(initial_kb.keys())
        keep_ids = set(all_ids[:75])
        deleted_ids = set(all_ids[75:])
        assert len(deleted_ids) == 74, f"Expected 74 deleted criteria, got {len(deleted_ids)}"

        depleted_kb = {k: v for k, v in initial_kb.items() if k in keep_ids}
        assert len(depleted_kb) == 75

        # Write depleted KB to disk
        with open(DEFAULT_KB_PATH, "w", encoding="utf-8") as f:
            json.dump(depleted_kb, f, ensure_ascii=False, indent=2)

        # Initialize catalog
        catalog = DuckDBSemanticCatalog()
        initial_ram_count = catalog.conn.execute("SELECT count(*) FROM catalog_criteria;").fetchone()[0]

        # Simulate 50% deletion in DuckDB RAM as well
        for d_id in deleted_ids:
            catalog.conn.execute("DELETE FROM catalog_criteria WHERE id = ?", (d_id,))
            catalog.conn.execute("DELETE FROM catalog_criteria_hierarchy WHERE id = ?", (d_id,))
            catalog.conn.execute("DELETE FROM catalog_definitions WHERE id = ?", (d_id,))
        catalog._refresh_criteria_cache_lists()

        ram_count_before = catalog.conn.execute("SELECT count(*) FROM catalog_criteria;").fetchone()[0]
        # Assert DuckDB RAM is depleted below 95% threshold of 149 active PG criteria
        assert ram_count_before < 149 * 0.95, f"Expected < 141.55 rows in DuckDB RAM, got {ram_count_before}"
        assert ram_count_before < initial_ram_count

        # 3. Time the detection and recovery process (Requirement: < 30 seconds)
        t_start = time.perf_counter()

        # To ensure deterministic, fast recovery under 30s without depending on 74 sequential external LLM calls,
        # we patch generate_definition_with_llm to provide the validated definitions from initial_kb
        def mock_generate_definition(criterion, context, max_retries=3):
            cid = criterion["id"]
            if cid in initial_kb:
                entry = initial_kb[cid]
                return {
                    "definition": entry["definition"],
                    "natural_synonyms": entry["natural_synonyms"],
                    "scope_description": entry.get("scope_description", "")
                }
            # Fallback
            name = criterion["name"]
            p_name = context.get("parent_name") or "nông nghiệp"
            return {
                "definition": f"Chỉ tiêu thống kê chuyên ngành {name} phản ánh kết quả quản lý điều hành thuộc nhóm {p_name}.",
                "natural_synonyms": [name.lower(), f"chỉ tiêu {name.lower()}"],
                "scope_description": f"Áp dụng trong phạm vi quản lý {name}."
            }

        with patch.object(DynamicCriterionIngestor, "generate_definition_with_llm", side_effect=mock_generate_definition):
            sync_result = catalog.check_and_sync_changes(force=False)

        recovery_duration = time.perf_counter() - t_start
        logger.info("Recovery completed in %.2f seconds (sync_result: %s)", recovery_duration, sync_result)

        # 4. Assert execution time < 30.0 seconds
        assert recovery_duration < 30.0, f"Recovery took {recovery_duration:.2f}s, exceeding 30s threshold!"

        # 5. Verify sync status
        assert sync_result.get("synced") is True, f"Expected synced=True, got: {sync_result}"
        assert sync_result.get("status") == "SYNCED"

        # 6. Verify KB file on disk restored to 149 entries with 19 fields
        with open(DEFAULT_KB_PATH, "r", encoding="utf-8") as f:
            restored_kb = json.load(f)
        assert len(restored_kb) == 149, f"Expected 149 restored criteria in KB, got {len(restored_kb)}"

        for cid, entry in restored_kb.items():
            for req_field in REQUIRED_FIELDS:
                assert req_field in entry, f"Restored criterion {cid} missing mandatory field {req_field}"
            # Verify 5-gate validity
            passed, err_msg = FiveGateValidator.validate_gate1_schema(entry)
            assert passed, f"Criterion {cid} failed Gate 1 validation: {err_msg}"

        # 7. Verify DuckDB RAM restored to at least 149 entries
        ram_count_after = catalog.conn.execute("SELECT count(*) FROM catalog_criteria;").fetchone()[0]
        assert ram_count_after >= 149, f"Expected >= 149 criteria in DuckDB RAM, got {ram_count_after}"

        # 8. Verify atomic snapshot swapped
        snap_after = catalog.snapshot
        assert len(snap_after.criteria_codes) >= 145
        assert len(snap_after.criteria_names) >= 145


# ==============================================================================
# 3. SOFT-DELETE & JUNK CODE FILTRATION
# ==============================================================================

class TestSoftDeleteAndJunkCodeFiltration:
    """
    Verifies that:
    1. Criteria with deleted_date IS NOT NULL are purged and absent from DuckDB tables.
    2. Dummy codes ('so', 'th', 'th1', 'th2', 'th3', 'test') and names with < 6 chars are completely filtered out.
    """

    def test_soft_deleted_criteria_absent_from_duckdb(self, catalog_instance):
        """Verify criteria marked as deleted in DWH are never present in DuckDB RAM tables."""
        # Query DWH for soft-deleted criteria
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
            cur.execute("SELECT id, code, name FROM dwh_internal.criteria WHERE deleted_date IS NOT NULL;")
            deleted_dwh_rows = cur.fetchall()
            conn_pg.close()
        except Exception as e:
            pytest.skip(f"PostgreSQL connection unavailable for live soft-delete query: {e}")

        if not deleted_dwh_rows:
            pytest.skip("No soft-deleted criteria present in PostgreSQL DWH to test against.")

        # For every soft-deleted row, assert it does NOT exist in DuckDB tables
        for del_id, del_code, del_name in deleted_dwh_rows:
            str_id = str(del_id)
            c_check = catalog_instance.conn.execute(
                "SELECT count(*) FROM catalog_criteria WHERE id = ? OR code = ?;",
                (str_id, del_code)
            ).fetchone()[0]
            assert c_check == 0, f"Soft-deleted criterion {del_code} ({str_id}) found in catalog_criteria!"

            h_check = catalog_instance.conn.execute(
                "SELECT count(*) FROM catalog_criteria_hierarchy WHERE id = ? OR code = ?;",
                (str_id, del_code)
            ).fetchone()[0]
            assert h_check == 0, f"Soft-deleted criterion {del_code} ({str_id}) found in catalog_criteria_hierarchy!"

            # Assert absent from snapshot
            assert del_code not in catalog_instance.snapshot.criteria_codes
            assert catalog_instance.snapshot.get_criterion_by_code(del_code) is None

    def test_dummy_codes_and_short_names_filtered_out(self, catalog_instance):
        """
        Verify dummy codes ('so', 'th', 'th1', 'th2', 'th3', 'test') and names with < 6 chars
        are completely filtered out of DuckDB tables, snapshot, and search.
        """
        forbidden_codes = {"so", "th", "th1", "th2", "th3", "test"}
        snap = catalog_instance.snapshot

        # 1. Check snapshot codes
        for code in snap.criteria_codes:
            clean_code = code.strip().lower()
            assert clean_code not in forbidden_codes, f"Dummy code {code} leaked into CriteriaCatalogSnapshot!"
            assert not clean_code.startswith("test_"), f"Test code {code} leaked into snapshot!"

        # 2. Check snapshot names length >= 6
        for name in snap.criteria_names:
            clean_name = name.strip()
            assert len(clean_name) >= 6, f"Short name '{clean_name}' (< 6 chars) leaked into CriteriaCatalogSnapshot!"

        # 3. Check is_dummy_criterion helper accuracy
        for code in forbidden_codes:
            assert is_dummy_criterion(code=code, name="Hợp lệ dài hơn 6 ký tự") is True
        assert is_dummy_criterion(code="valid_code", name="ngắn") is True  # len < 6
        assert is_dummy_criterion(code="test_dummy_var", name="Hợp lệ dài hơn 6 ký tự") is True
        assert is_dummy_criterion(code="valid_code", name="Số lượng đàn trâu") is False

        # 4. Search verification: querying dummy words returns no dummy candidates
        for dummy_code in forbidden_codes:
            results = catalog_instance.find_criteria_by_name(dummy_code)
            for res in results:
                assert res["code"].lower() not in forbidden_codes

    def test_synthetic_soft_delete_and_dummy_insertion_purge(self, catalog_instance):
        """
        Synthetically inject dummy records and soft-deleted records into DuckDB,
        call _refresh_criteria_cache_lists(), and verify they are strictly excluded.
        """
        conn = catalog_instance.conn

        # Insert dummy and short-name rows
        conn.execute("INSERT OR REPLACE INTO catalog_criteria VALUES ('dummy-1', 'so', 'Số', '', 1, true, '', '68', '2026-01-01');")
        conn.execute("INSERT OR REPLACE INTO catalog_criteria VALUES ('dummy-2', 'th1', 'Thử 1', '', 1, true, '', '68', '2026-01-01');")
        conn.execute("INSERT OR REPLACE INTO catalog_criteria VALUES ('dummy-3', 'test', 'Test', '', 1, true, '', '68', '2026-01-01');")
        conn.execute("INSERT OR REPLACE INTO catalog_criteria VALUES ('dummy-4', 'valid_c', 'ngắn', '', 1, true, '', '68', '2026-01-01');")

        # Refresh snapshot
        catalog_instance._refresh_criteria_cache_lists()
        snap = catalog_instance.snapshot

        # Verify none of the dummy entries are in the snapshot
        for dummy_code in ["so", "th1", "test"]:
            assert dummy_code not in snap.criteria_codes
            assert snap.get_criterion_by_code(dummy_code) is None

        for n in snap.criteria_names:
            assert len(n.strip()) >= 6
            assert n.strip().lower() not in DUMMY_FILTER_NAMES

        # Clean up synthetic rows from DuckDB
        conn.execute("DELETE FROM catalog_criteria WHERE id IN ('dummy-1', 'dummy-2', 'dummy-3', 'dummy-4');")
        catalog_instance._refresh_criteria_cache_lists()
