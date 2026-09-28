"""
Test Suite: IPGov_Chatbot/tests/test_mod05_phase3_error_cache.py
Chức năng: Unit test kiểm chứng Phase 3 Module 05:
- Deterministic Error-to-Constraint Mapper (error_cache_service.py)
- Redis SQL Error Cache & Circuit Breaker (error_cache_service.py)
- PostgreSQL Live DB Dry-Run via EXPLAIN (db_dry_run.py)
Căn cứ:
- Plan: plan_module_05_execution.md (Mục 4.3)
- Spec: MODULE_05_SQL_COMPILER_SPEC.md (Mục 7)
- TRAPS: [TRAP-004], [TRAP-005], [TRAP-015]
"""

import pytest
import psycopg2

from IPGov_Chatbot.modules.mod05_sql_compiler.db_dry_run import DatabaseDryRunner
from IPGov_Chatbot.modules.mod05_sql_compiler.error_cache_service import (
    RedisSQLErrorCache,
    map_postgres_error_to_constraint,
)


class TestDeterministicErrorMapper:
    """Kiểm thử khối Ánh xạ Tất định mã lỗi PostgreSQL sang Ràng buộc Phủ định."""

    def test_map_22P02_trap_004(self):
        constraint = map_postgres_error_to_constraint("22P02", 'invalid input syntax for type numeric: ""')
        assert "[TRAP-004]" in constraint
        assert "NULLIF(TRIM(f.value), '')::numeric" in constraint

    def test_map_42703_undefined_column(self):
        constraint = map_postgres_error_to_constraint("42703", 'column "fake_col" does not exist')
        assert "[42703]" in constraint
        assert "Schema Slice DDL" in constraint

    def test_map_42703_office_name(self):
        constraint = map_postgres_error_to_constraint("42703", 'column o.name does not exist')
        assert "office_name" in constraint

    def test_map_42P01_undefined_table(self):
        constraint = map_postgres_error_to_constraint("42P01", 'relation "dwh_internal.department" does not exist')
        assert "[TRAP-005]" in constraint
        assert "deparment" in constraint

    def test_map_42803_group_by(self):
        constraint = map_postgres_error_to_constraint("42803", 'column must appear in the group by clause')
        assert "[42803]" in constraint
        assert "GROUP BY" in constraint


class TestRedisSQLErrorCache:
    """Kiểm thử Redis SQL Error Cache và cơ chế phòng vệ Circuit Breaker [TRAP-015]."""

    @pytest.fixture
    def error_cache(self):
        cache = RedisSQLErrorCache()
        cache.clear()
        yield cache
        cache.clear()

    def test_record_and_get_error_trace(self, error_cache):
        prompt = "Thống kê kinh phí khuyến công năm 2025"
        failed_sql = "SELECT f.value::numeric FROM dwh_internal.fact_report_criteria f;"
        candidate_tables = ["dwh_internal.fact_report_criteria"]

        neg_constraint = error_cache.record_error(
            prompt=prompt,
            failed_sql=failed_sql,
            error_layer="POSTGRES_RUNTIME_ERROR",
            pg_code="22P02",
            error_message="invalid input syntax for type numeric",
            candidate_tables=candidate_tables,
        )

        assert "NULLIF(TRIM(f.value), '')::numeric" in neg_constraint

        # Tra cứu lại vết lỗi
        trace = error_cache.get_error_trace(prompt, candidate_tables)
        assert trace is not None
        assert trace["pg_code"] == "22P02"
        assert trace["failed_sql"] == failed_sql
        assert trace["negative_constraint"] == neg_constraint

    def test_circuit_breaker_offline_fallback(self):
        """Kiểm thử tự động chuyển sang bộ nhớ RAM nếu Redis cấu hình cổng sai hoặc offline."""
        offline_cache = RedisSQLErrorCache(redis_port=9999)
        # Thao tác không được văng Exception
        offline_cache.record_error(
            prompt="Test prompt",
            failed_sql="SELECT 1;",
            error_layer="AST",
            pg_code="TEST",
            error_message="Test message",
        )
        trace = offline_cache.get_error_trace("Test prompt")
        assert trace is not None
        assert trace["pg_code"] == "TEST"


class TestDatabaseDryRunner:
    """Kiểm thử dịch vụ PostgreSQL Live DB Dry-Run."""

    @pytest.fixture
    def dry_runner(self):
        return DatabaseDryRunner()

    def test_dry_run_valid_sql_sync(self, dry_runner):
        sql = "SELECT id, code, name FROM dwh_internal.criteria LIMIT 1;"
        is_valid, pg_code, err, plan = dry_runner.dry_run_explain_sync(sql)
        assert is_valid is True
        assert err is None
        assert plan is not None

    def test_dry_run_invalid_syntax_sync(self, dry_runner):
        bad_sql = "SELECT FROM WHERE dwh_internal.criteria;"
        is_valid, pg_code, err, plan = dry_runner.dry_run_explain_sync(bad_sql)
        assert is_valid is False
        assert err is not None

    def test_dry_run_undefined_column_captures_pg_code(self, dry_runner):
        bad_sql = "SELECT non_existent_column_xyz FROM dwh_internal.criteria;"
        is_valid, pg_code, err, plan = dry_runner.dry_run_explain_sync(bad_sql)
        assert is_valid is False
        assert pg_code == "42703"

    @pytest.mark.asyncio
    async def test_dry_run_valid_sql_async(self, dry_runner):
        sql = "SELECT count(*) FROM dwh_internal.criteria;"
        is_valid, pg_code, err, plan = await dry_runner.dry_run_explain_async(sql)
        assert is_valid is True
        assert err is None
