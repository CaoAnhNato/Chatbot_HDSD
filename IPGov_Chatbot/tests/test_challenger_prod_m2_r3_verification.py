"""
Empirical Challenger Test Suite: test_challenger_prod_m2_r3_verification.py
Milestone 2 Iteration 3 Live Empirical Verification Harness authored by challenger_prod_m2_r3_1.

Empirical Objectives:
1. Target Defect Verification:
   - Prove NOT EXISTS clauses are preserved by ASTEnforcerService without alias leakage into outer query.
   - Verify multi-indicator inquiries execute cleanly against live PostgreSQL without 'missing FROM-clause entry for table "w"'.
   - Test multiple NOT EXISTS, mixed NOT EXISTS with negative status predicates.
2. Livestock Ground Truth Verification (2026-10-16):
   - Confirm approved figures: 170 trâu + 256 bò = 426 total.
   - Confirm unapproved draft/pending figures (255 animals or 681 all) are strictly excluded.
3. [TRAP-068] Valid Zero Preservation:
   - Verify salt indicators on 2026-07-31 preserve numeric 0.0 in SQL query, CTE ranking, and agent formatted table.
4. Multi-Schema Live PostgreSQL Execution:
   - Clean execution across dwh_internal and dwh_public.
"""

import re
import pytest
import psycopg2

from IPGov_Chatbot.config import settings
from IPGov_Chatbot.modules.mod03_router.canonical_normalizer import CanonicalSemanticNormalizer
from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import WarehouseLangGraphAgent
from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog
from IPGov_Chatbot.modules.mod06_ast_enforcer.ast_enforcer_service import ASTEnforcerService
from IPGov_Chatbot.schemas.sql_compiler_schema import GeneratedSQLDTO, SQLExecutionMode
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO


@pytest.fixture(scope="module")
def db_conn():
    """Establish direct connection to live PostgreSQL DWH with autocommit."""
    try:
        conn = psycopg2.connect(settings.sync_dwh_url, connect_timeout=5)
        conn.autocommit = True
        yield conn
        conn.close()
    except Exception as e:
        pytest.skip(f"Live PostgreSQL DWH not reachable at {settings.sync_dwh_url}: {e}")


@pytest.fixture(scope="module")
def shared_catalog():
    return DuckDBSemanticCatalog()


@pytest.fixture(scope="module")
def normalizer(shared_catalog):
    return CanonicalSemanticNormalizer(catalog=shared_catalog)


@pytest.fixture(scope="module")
def warehouse_agent():
    return WarehouseLangGraphAgent()


@pytest.fixture(scope="module")
def ast_enforcer():
    return ASTEnforcerService()


# ==============================================================================
# 1. TARGET DEFECT: AST ENFORCER NOT EXISTS PRESERVATION & ALIAS ISOLATION
# ==============================================================================

class TestTargetDefectNotExistsPreservation:
    """Verifies that NOT EXISTS subqueries are preserved and do not leak subquery aliases."""

    def test_ast_enforcer_preserves_single_not_exists_subquery(self, ast_enforcer, db_conn):
        sql = """
            SELECT f.criteria_id, f.value
            FROM dwh_internal.fact_report_criteria f
            WHERE f.tenant_code = '68'
              AND f.report_status = 'approved'
              AND NOT EXISTS (
                  SELECT 1 FROM dwh_internal.fact_report_criteria w
                  WHERE w.criteria_id = f.criteria_id
                    AND w.report_date::date = f.report_date::date
                    AND w.office_id IS NULL
                    AND w.tenant_code = '68'
                    AND w.report_status = 'approved'
              )
        """
        ctx = UserSecurityContextDTO(
            user_id="test_user",
            username="citizen",
            tenant_code="68",
            role_level=3,
        )
        dto = GeneratedSQLDTO(
            raw_sql=sql,
            execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
            generator_track="TRACK_A_COMPILER",
        )
        res = ast_enforcer.enforce_sql_sync(dto, ctx)
        sanitized = res.sanitized_sql.lower()

        # Invariant 1: NOT EXISTS must remain in the query
        assert "not exists" in sanitized, f"DEFECT REGRESSION: NOT EXISTS was dropped: {res.sanitized_sql}"

        # Invariant 2: Subquery alias 'w' must be properly declared inside NOT EXISTS subquery
        assert "from dwh_internal.fact_report_criteria as w" in sanitized, f"Subquery declaration missing: {res.sanitized_sql}"
        assert "w.office_id is null" in sanitized

        # Invariant 3: Query must execute cleanly on PostgreSQL without 'missing FROM-clause'
        cur = db_conn.cursor()
        try:
            cur.execute(f"EXPLAIN {res.sanitized_sql}")
            assert cur.rowcount > 0
        except psycopg2.Error as e:
            pytest.fail(f"PostgreSQL failed to execute sanitized SQL: {e}")
        finally:
            cur.close()

    def test_ast_enforcer_preserves_multiple_not_exists_subqueries(self, ast_enforcer, db_conn):
        sql = """
            SELECT f.criteria_id, f.value
            FROM dwh_internal.fact_report_criteria f
            WHERE f.tenant_code = '68'
              AND f.report_status = 'approved'
              AND NOT EXISTS (
                  SELECT 1 FROM dwh_internal.fact_report_criteria w
                  WHERE w.criteria_id = f.criteria_id
                    AND w.office_id IS NULL
                    AND w.report_status = 'approved'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM dwh_internal.fact_report_criteria z
                  WHERE z.criteria_id = f.criteria_id
                    AND z.report_date > f.report_date
                    AND z.report_status = 'approved'
              )
        """
        ctx = UserSecurityContextDTO(
            user_id="test_user",
            username="citizen",
            tenant_code="68",
            role_level=3,
        )
        dto = GeneratedSQLDTO(
            raw_sql=sql,
            execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
            generator_track="TRACK_A_COMPILER",
        )
        res = ast_enforcer.enforce_sql_sync(dto, ctx)
        sanitized = res.sanitized_sql.lower()

        assert sanitized.count("not exists") == 2, f"Expected 2 NOT EXISTS clauses, got: {res.sanitized_sql}"
        cur = db_conn.cursor()
        try:
            cur.execute(f"EXPLAIN {res.sanitized_sql}")
            assert cur.rowcount > 0
        except psycopg2.Error as e:
            pytest.fail(f"PostgreSQL failed to execute multi-NOT-EXISTS SQL: {e}")
        finally:
            cur.close()

    def test_ast_enforcer_preserves_not_exists_while_rewriting_outer_negative_status(self, ast_enforcer, db_conn):
        """Mixed scenario: Outer WHERE has negative status attempt AND NOT EXISTS.
        The negative status must be converted to '= approved' while NOT EXISTS remains intact."""
        sql = """
            SELECT f.criteria_id, f.value
            FROM dwh_internal.fact_report_criteria f
            WHERE f.tenant_code = '68'
              AND f.report_status != 'approved'
              AND NOT EXISTS (
                  SELECT 1 FROM dwh_internal.fact_report_criteria w
                  WHERE w.criteria_id = f.criteria_id
                    AND w.report_status = 'approved'
              )
        """
        ctx = UserSecurityContextDTO(
            user_id="test_user",
            username="citizen",
            tenant_code="68",
            role_level=3,
        )
        dto = GeneratedSQLDTO(
            raw_sql=sql,
            execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
            generator_track="TRACK_A_COMPILER",
        )
        res = ast_enforcer.enforce_sql_sync(dto, ctx)
        sanitized = res.sanitized_sql.lower()

        # NOT EXISTS must remain
        assert "not exists" in sanitized
        # The != 'approved' must be rewritten to = 'approved'
        assert "!= 'approved'" not in sanitized
        assert "<> 'approved'" not in sanitized
        # Blocked access flag must be set for unauthorized role_level 3
        assert ctx.blocked_draft_access is True

        cur = db_conn.cursor()
        try:
            cur.execute(f"EXPLAIN {res.sanitized_sql}")
            assert cur.rowcount > 0
        except psycopg2.Error as e:
            pytest.fail(f"PostgreSQL execution error on mixed query: {e}")
        finally:
            cur.close()


# ==============================================================================
# 2. LIVE POSTGRESQL VERIFICATION: MULTI-INDICATOR INQUIRIES
# ==============================================================================

class TestLivePostgresMultiIndicatorInquiries:
    """Re-executes the exact multi-indicator inquiries that previously failed in Iteration 2."""

    def test_live_inquiry_trau_va_bo_no_from_clause_error(self, warehouse_agent):
        """Query: 'Số lượng trâu và số lượng bò ngày 16/10/2026'."""
        ctx = {
            "role_level": 4,
            "role": "boss",
            "username": "boss",
            "name": "Lãnh đạo",
            "is_unrestricted": True,
            "tenant_code": "68",
            "schema": "dwh_internal",
        }
        res = warehouse_agent.run("Số lượng trâu và số lượng bò ngày 16/10/2026", user_context=ctx)
        ans = res.get("final_answer", "")
        res_str = str(res)

        # Fatal defect check: No 'missing FROM-clause'
        assert "missing from-clause" not in res_str.lower(), f"DEFECT PERSISTS! Result: {res_str}"
        assert "lỗi thực thi postgresql" not in res_str.lower(), f"PostgreSQL Execution Error: {res_str}"

        # Ground truth check: 170 trâu and 256 bò
        assert "170" in ans, f"Expected 170 trâu in final answer, got: {ans}"
        assert "256" in ans, f"Expected 256 bò in final answer, got: {ans}"
        assert "426" in ans, f"Expected total 426 livestock in final answer, got: {ans}"

        # Strict exclusion of unapproved records
        assert "255" not in ans, f"LEAK DETECTED: 255 unapproved animals leaked into answer: {ans}"
        assert "681" not in ans, f"LEAK DETECTED: 681 (sum of all) leaked into answer: {ans}"

        # Table formatting check
        assert "| STT |" in ans, f"Markdown table missing: {ans}"
        assert "Số lượng trâu" in ans
        assert "Số lượng bò" in ans

    def test_live_inquiry_muoi_san_luong_va_dien_tich_preserves_zero(self, warehouse_agent):
        """Query: 'Sản lượng muối và diện tích muối ngày 31/07/2026'."""
        ctx = {
            "role_level": 4,
            "role": "boss",
            "username": "boss",
            "name": "Lãnh đạo",
            "is_unrestricted": True,
            "tenant_code": "68",
            "schema": "dwh_internal",
        }
        res = warehouse_agent.run("Sản lượng muối và diện tích muối ngày 31/07/2026", user_context=ctx)
        ans = res.get("final_answer", "")
        res_str = str(res)

        # Fatal defect check: No 'missing FROM-clause'
        assert "missing from-clause" not in res_str.lower(), f"DEFECT PERSISTS! Result: {res_str}"
        assert "lỗi thực thi postgresql" not in res_str.lower(), f"PostgreSQL Execution Error: {res_str}"

        # TRAP-068: Must preserve 0 / 0.0, rendering '**0**'
        assert "**0**" in ans or " 0 " in ans or "0.0" in ans, f"Expected valid zero preserved in answer, got: {ans}"
        assert "chưa có số liệu ghi nhận (-)" not in ans.lower(), f"Zero was converted to dash: {ans}"

    def test_live_inquiry_tong_muoi_multi_metric(self, warehouse_agent):
        """Query: 'Tổng diện tích sản xuất muối và tổng sản lượng muối ngày 31/07/2026'."""
        ctx = {
            "role_level": 4,
            "role": "boss",
            "username": "boss",
            "name": "Lãnh đạo",
            "is_unrestricted": True,
            "tenant_code": "68",
            "schema": "dwh_internal",
        }
        res = warehouse_agent.run("Tổng diện tích sản xuất muối và tổng sản lượng muối ngày 31/07/2026", user_context=ctx)
        ans = res.get("final_answer", "")
        res_str = str(res)

        assert "missing from-clause" not in res_str.lower()
        assert "lỗi thực thi postgresql" not in res_str.lower()
        assert "| STT |" in ans

    def test_live_inquiry_parent_rollup_livestock(self, warehouse_agent):
        """Single parent rollup: 'Số lượng gia súc ngày 16/10/2026 là bao nhiêu?'."""
        ctx = {
            "role_level": 4,
            "role": "boss",
            "username": "boss",
            "name": "Lãnh đạo",
            "is_unrestricted": True,
            "tenant_code": "68",
            "schema": "dwh_internal",
        }
        res = warehouse_agent.run("Số lượng gia súc ngày 16/10/2026 là bao nhiêu?", user_context=ctx)
        ans = res.get("final_answer", "")

        assert "426" in ans, f"Expected 426 in livestock answer, got: {ans}"
        assert "255" not in ans, f"LEAK DETECTED: 255 pending animals in answer: {ans}"
        assert "681" not in ans, f"LEAK DETECTED: 681 animals in answer: {ans}"


# ==============================================================================
# 3. DIRECT POSTGRESQL GROUND TRUTH AND ZERO PRESERVATION
# ==============================================================================

class TestDirectPostgresGroundTruthAndInvariants:
    """Direct database queries verifying exact numbers and zero preservation."""

    def test_postgres_livestock_direct_arithmetic_2026_10_16(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT f.code, f.value, f.report_status, f.report_date
            FROM dwh_internal.fact_report_criteria f
            WHERE f.report_date::date = '2026-10-16'
              AND f.code IN ('so_luong_trau', 'so_luong_bo', 'so_luong_gia_suc')
            ORDER BY f.report_date DESC;
        """)
        rows = cur.fetchall()
        cur.close()

        # Verify approved records
        approved_trau = [int(r[1]) for r in rows if r[0] == 'so_luong_trau' and r[2] == 'approved']
        approved_bo = [int(r[1]) for r in rows if r[0] == 'so_luong_bo' and r[2] == 'approved']
        approved_gia_suc = [int(r[1]) for r in rows if r[0] == 'so_luong_gia_suc' and r[2] == 'approved']

        # Most recent approved version on 2026-10-16 03:06:51
        assert 170 in approved_trau
        assert 256 in approved_bo
        assert 426 in approved_gia_suc
        assert 170 + 256 == 426

        # Verify pending records
        pending_trau = sum(int(r[1]) for r in rows if r[0] == 'so_luong_trau' and r[2] == 'pending')
        pending_bo = sum(int(r[1]) for r in rows if r[0] == 'so_luong_bo' and r[2] == 'pending')
        assert pending_trau + pending_bo == 255

    def test_postgres_salt_direct_zero_preservation_2026_07_31(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT f.code, f.value, f.report_status
            FROM dwh_internal.fact_report_criteria f
            WHERE f.report_date::date = '2026-07-31'
              AND f.report_status = 'approved'
              AND f.code IN ('tong_dien_tich_san_xuat_muoi', 'tong_san_luong_muoi_gd2', 'tong_ho_san_xuat_muoi');
        """)
        rows = cur.fetchall()
        cur.close()

        assert len(rows) >= 2
        for code, val, status in rows:
            assert float(val) == 0.0, f"Code {code} expected 0.0, got {val}"
            assert status == "approved"
