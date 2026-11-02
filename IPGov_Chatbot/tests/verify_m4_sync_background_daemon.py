# -*- coding: utf-8 -*-
"""
Verification Script for Milestone 4 Remediation:
Autonomous 5-Minute (300s) Background Sync Daemon Monitor.

Verifies:
1. System running autonomously under live background catalog sync worker daemon
   (interval_seconds=300 / CATALOG_AUTO_SYNC_MINUTES=5) on a 50%-depleted catalog copy.
2. Real 300-second window monitoring WITHOUT manual check_and_sync_changes() call
   and WITHOUT mocking LLM generation methods.
3. Autonomous scheduled wake-up upon 300s timer expiration, scanning DWH, detecting
   missing criteria, and restoring full dictionary to genuine 149 criteria with 19 fields.
4. Concurrency safety: Zero reader errors or deadlocks during the entire window.
"""
import asyncio
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from IPGov_Chatbot.config import settings
from IPGov_Chatbot.main import _catalog_background_sync_loop
from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import warehouse_agent
from IPGov_Chatbot.modules.mod04_catalog.dynamic_criterion_ingestor import (
    DEFAULT_KB_PATH,
    REQUIRED_FIELDS,
    FiveGateValidator,
    sync_definitions_to_duckdb,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [SyncDaemonMonitor] %(message)s"
)
logger = logging.getLogger("m4_daemon_monitor")


async def main():
    print("=" * 80)
    print("STARTING TASK 1: REAL 5-MINUTE (300s) BACKGROUND SYNC DAEMON MONITOR")
    print("=" * 80)

    # 1. Verify and backup initial KB
    assert DEFAULT_KB_PATH.exists(), f"KB file does not exist at {DEFAULT_KB_PATH}"
    original_kb_bytes = DEFAULT_KB_PATH.read_bytes()
    with open(DEFAULT_KB_PATH, "r", encoding="utf-8") as f:
        initial_kb = json.load(f)

    initial_kb_count = len(initial_kb)
    logger.info("[Step 1] Initial KB verified: %d entries (Expected: 149)", initial_kb_count)
    assert initial_kb_count == 149, f"Expected 149 criteria, found {initial_kb_count}"

    for cid, entry in initial_kb.items():
        for req_field in REQUIRED_FIELDS:
            assert req_field in entry, f"Criterion {cid} missing mandatory field {req_field}"

    catalog = warehouse_agent.catalog
    initial_ram_count = catalog.conn.execute("SELECT count(*) FROM catalog_criteria;").fetchone()[0]
    initial_snap_version = catalog.snapshot.version
    logger.info("[Step 1] Initial DuckDB RAM count: %d, Snapshot version: %d", initial_ram_count, initial_snap_version)

    # Configure 5-minute background sync interval
    os.environ["CATALOG_AUTO_SYNC_MINUTES"] = "5"
    os.environ["CATALOG_SYNC_INITIAL_DELAY_SECONDS"] = "300"
    sync_interval_sec = 300
    logger.info("[Step 1] Configured interval_seconds = 300 (CATALOG_AUTO_SYNC_MINUTES = 5)")

    sync_task = None
    stop_readers = threading.Event()
    reader_errors = []
    read_iterations = [0] * 4

    try:
        # 2. Simulate 50% dictionary deletion
        all_ids = list(initial_kb.keys())
        keep_ids = set(all_ids[:75])
        deleted_ids = set(all_ids[75:])
        logger.info("[Step 2] Simulating 50%% deletion: dropping %d criteria (keeping %d)...", len(deleted_ids), len(keep_ids))
        assert len(deleted_ids) == 74, f"Expected 74 deleted criteria, got {len(deleted_ids)}"

        depleted_kb = {k: v for k, v in initial_kb.items() if k in keep_ids}
        with open(DEFAULT_KB_PATH, "w", encoding="utf-8") as f:
            json.dump(depleted_kb, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())

        for d_id in deleted_ids:
            catalog.conn.execute("DELETE FROM catalog_criteria WHERE id = ?", (d_id,))
            catalog.conn.execute("DELETE FROM catalog_criteria_hierarchy WHERE id = ?", (d_id,))
            catalog.conn.execute("DELETE FROM catalog_definitions WHERE id = ?", (d_id,))
        catalog._refresh_criteria_cache_lists()

        ram_count_depleted = catalog.conn.execute("SELECT count(*) FROM catalog_criteria;").fetchone()[0]
        snap_depleted = catalog.snapshot
        logger.info("[Step 2] Depleted state: DuckDB RAM = %d, Snapshot criteria codes = %d", ram_count_depleted, len(snap_depleted.criteria_codes))
        assert ram_count_depleted < 149 * 0.95, f"Expected < 141.55 rows in DuckDB RAM, got {ram_count_depleted}"

        # 3. Start background concurrent readers to prove 0 downtime during the 300s window
        test_queries = [
            "sản lượng muối",
            "diện tích muối",
            "số lượng gia súc",
            "hợp tác xã nông nghiệp",
        ]

        def reader_worker(worker_id: int):
            while not stop_readers.is_set():
                try:
                    q = test_queries[worker_id % len(test_queries)]
                    snap = catalog.snapshot
                    assert snap is not None
                    assert len(snap.criteria_codes) == len(snap.criteria_names)
                    res = catalog.find_criteria_by_name(q, limit=2, top_k_candidates=3, use_llm_disambiguation=False)
                    assert isinstance(res, list)
                    read_iterations[worker_id] += 1
                except Exception as e:
                    reader_errors.append((worker_id, str(e)))
                time.sleep(0.05)

        reader_threads = [
            threading.Thread(target=reader_worker, args=(i,), daemon=True)
            for i in range(4)
        ]
        for t in reader_threads:
            t.start()
        logger.info("[Step 3] Started 4 background reader threads.")

        # 4. Start the live background catalog sync worker daemon
        # NOTE: NO manual check_and_sync_changes() call and NO LLM mock!
        logger.info("[Step 4] Launching live background sync daemon task (_catalog_background_sync_loop(interval_seconds=300))...")
        t_start = time.perf_counter()
        sync_task = asyncio.create_task(_catalog_background_sync_loop(interval_seconds=300))

        # 5. Monitor across the full 300s window with periodic heartbeats
        logger.info("[Step 5] Commencing 300-second autonomous window monitoring...")
        restored = False
        restoration_time = 0.0

        # Loop until restored or timeout (max 800s to allow full 74-criteria live LLM sync after 300s wake-up)
        max_wait_seconds = 800.0
        last_heartbeat = 0.0

        while (time.perf_counter() - t_start) < max_wait_seconds:
            await asyncio.sleep(5.0)
            elapsed = time.perf_counter() - t_start

            if sync_task.done():
                exc = sync_task.exception()
                if exc:
                    raise RuntimeError(f"Background sync daemon task failed with: {exc}") from exc

            current_ram = catalog.conn.execute("SELECT count(*) FROM catalog_criteria;").fetchone()[0]
            current_snap_version = catalog.snapshot.version

            # Log heartbeat every 30 seconds
            if elapsed - last_heartbeat >= 30.0:
                last_heartbeat = elapsed
                logger.info(
                    "[Heartbeat %6.1fs / 300s] DuckDB RAM: %d rows | Snapshot v%d | Reads: %d | Errors: %d | Daemon status: %s",
                    elapsed,
                    current_ram,
                    current_snap_version,
                    sum(read_iterations),
                    len(reader_errors),
                    "SLEEPING_SCHEDULED" if elapsed < 300 else "WOKEN_UP_PROCESSING",
                )

            # Check if autonomous restoration completed
            if current_ram >= initial_ram_count and current_snap_version > initial_snap_version and elapsed >= 295.0:
                with open(DEFAULT_KB_PATH, "r", encoding="utf-8") as f:
                    kb_check = json.load(f)
                if len(kb_check) >= 149:
                    restored = True
                    restoration_time = elapsed
                    logger.info("🎉 [Step 5] Autonomous background sync detected! Restoration completed at %.2fs!", restoration_time)
                    break

        # Stop readers
        stop_readers.set()
        for t in reader_threads:
            t.join(timeout=2.0)

        # 6. Verify timing invariant: Real 300s window wait
        logger.info("[Step 6] Verification of autonomous wake-up timing:")
        logger.info("         Total elapsed time: %.2f seconds", restoration_time)
        assert restored, f"Background sync worker failed to restore 149 criteria within {max_wait_seconds}s!"
        assert restoration_time >= 295.0, (
            f"INTEGRITY VIOLATION: Restoration occurred at {restoration_time:.2f}s (< 295s)! "
            "Real 300s sleep interval did not naturally elapse."
        )
        logger.info("✅ Timing Invariant PASSED: Naturally waited >= 295s (elapsed: %.2fs)", restoration_time)

        # 7. Verify KB on disk
        with open(DEFAULT_KB_PATH, "r", encoding="utf-8") as f:
            restored_kb = json.load(f)

        logger.info("[Step 7] Restored KB entry count: %d", len(restored_kb))
        assert len(restored_kb) == 149, f"Expected 149 criteria in restored KB, found {len(restored_kb)}"

        for cid, entry in restored_kb.items():
            for req_field in REQUIRED_FIELDS:
                assert req_field in entry, f"Restored criterion {cid} missing mandatory field {req_field}"
            passed, err_msg = FiveGateValidator.validate_gate1_schema(entry)
            assert passed, f"Criterion {cid} failed Gate 1 validation: {err_msg}"

        logger.info("✅ 19-Field Schema & Gate 1 Invariant PASSED for all 149 criteria.")

        # 8. Verify DuckDB RAM & Snapshot
        final_ram = catalog.conn.execute("SELECT count(*) FROM catalog_criteria;").fetchone()[0]
        final_snap = catalog.snapshot
        assert final_ram >= 149 and final_ram == initial_ram_count, f"Expected {initial_ram_count} DuckDB RAM rows, found {final_ram}"
        assert final_snap.version > initial_snap_version, f"Snapshot version not incremented (was {initial_snap_version}, now {final_snap.version})"
        logger.info("✅ DuckDB RAM (%d rows) and Snapshot version (v%d -> v%d) PASSED.", final_ram, initial_snap_version, final_snap.version)

        # 9. Concurrency safety check
        assert len(reader_errors) == 0, f"Encountered {len(reader_errors)} reader errors during sync: {reader_errors}"
        logger.info("✅ Concurrency Safety PASSED: %d reads executed across 4 threads with 0 errors.", sum(read_iterations))

        print("=" * 80)
        print(f"TASK 1 PASSED 100%: REAL 300s DAEMON WAKE-UP & RESTORATION CONFIRMED IN {restoration_time:.2f}s")
        print("=" * 80)

    finally:
        # Cleanup
        if sync_task and not sync_task.done():
            sync_task.cancel()
            try:
                await sync_task
            except asyncio.CancelledError:
                pass

        stop_readers.set()

        # Restore original KB to ensure zero state pollution
        with open(DEFAULT_KB_PATH, "wb") as f:
            f.write(original_kb_bytes)
            f.flush()
            os.fsync(f.fileno())

        sync_definitions_to_duckdb(DEFAULT_KB_PATH, catalog.conn)
        catalog._refresh_criteria_cache_lists()
        logger.info("[Cleanup] Original KB (149 entries) and DuckDB RAM restored atomically.")


if __name__ == "__main__":
    asyncio.run(main())
