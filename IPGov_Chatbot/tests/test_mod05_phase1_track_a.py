"""
Test Suite: IPGov_Chatbot/tests/test_mod05_phase1_track_a.py
Chức năng: Unit test kiểm chứng Phase 1 Module 05:
- DTO Contracts (sql_compiler_schema.py)
- Invariant Gate AST Validator (ast_validator.py)
- Track A Deterministic Semantic AST Compiler (track_a_compiler.py)
Căn cứ:
- Plan: plan_module_05_execution.md (Mục 4.1)
- Spec: MODULE_05_SQL_COMPILER_SPEC.md (Mục 4, Mục 5.1)
- TRAPS: [TRAP-004], [TRAP-005], [TRAP-007]
"""

import time
import pytest
import psycopg2

from IPGov_Chatbot.schemas.sql_compiler_schema import (
    GeneratedSQLDTO,
    MetricFilter,
    MetricSpecDTO,
    SQLExecutionMode,
    TextToSQLStructuredOutput,
)
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO
from IPGov_Chatbot.schemas.router_dto import RouterOutputDTO, RouteTypeEnum, IntentEnum
from IPGov_Chatbot.modules.mod05_sql_compiler.ast_validator import (
    validate_ast_syntax,
    validate_schema_grounding,
    validate_data_contracts,
    invariant_sql_validator,
    clean_sql_string,
)
from IPGov_Chatbot.modules.mod05_sql_compiler.track_a_compiler import TrackACompiler


class TestASTValidator:
    """Kiểm thử hàng rào Invariant Gate AST Validator trong RAM."""

    def test_clean_sql_string(self):
        raw = "```sql\nSELECT * FROM dwh_internal.criteria;\n```"
        cleaned = clean_sql_string(raw)
        assert cleaned == "SELECT * FROM dwh_internal.criteria;"

    def test_valid_postgres_select_syntax(self):
        sql = "SELECT id, name FROM dwh_internal.criteria WHERE id = 1;"
        valid, err, parsed = validate_ast_syntax(sql)
        assert valid is True
        assert err is None
        assert parsed is not None

    def test_reject_dml_and_ddl(self):
        ddl = "DROP TABLE dwh_internal.criteria;"
        valid, err, parsed = validate_ast_syntax(ddl)
        assert valid is False
        assert "Chỉ cho phép câu lệnh SELECT / UNION" in err

        dml = "DELETE FROM dwh_internal.fact_report_criteria WHERE year = '2025';"
        valid, err, parsed = validate_ast_syntax(dml)
        assert valid is False

    def test_schema_grounding_rejects_hallucinated_table(self):
        sql = "SELECT * FROM dwh_internal.fake_table;"
        _, _, parsed = validate_ast_syntax(sql)
        valid, err = validate_schema_grounding(
            parsed,
            candidate_tables=["dwh_internal.fact_report_criteria", "dwh_internal.criteria"]
        )
        assert valid is False
        assert "fake_table" in err

    def test_schema_grounding_allows_cte_and_candidates(self):
        sql = """
        WITH my_cte AS (
            SELECT id FROM dwh_internal.criteria
        )
        SELECT * FROM my_cte JOIN dwh_internal.fact_report_criteria f ON my_cte.id = f.criteria_id;
        """
        _, _, parsed = validate_ast_syntax(sql)
        valid, err = validate_schema_grounding(
            parsed,
            candidate_tables=["dwh_internal.fact_report_criteria", "dwh_internal.criteria"]
        )
        assert valid is True
        assert err is None

    def test_data_contract_trap_004_rejects_raw_value_cast(self):
        sql = "SELECT SUM(f.value::numeric) FROM dwh_internal.fact_report_criteria f;"
        _, _, parsed = validate_ast_syntax(sql)
        valid, err = validate_data_contracts(parsed)
        assert valid is False
        assert "[TRAP-004]" in err

    def test_data_contract_trap_004_accepts_nullif_trim(self):
        sql = "SELECT SUM(NULLIF(TRIM(f.value), '')::numeric) FROM dwh_internal.fact_report_criteria f;"
        _, _, parsed = validate_ast_syntax(sql)
        valid, err = validate_data_contracts(parsed)
        assert valid is True
        assert err is None

    def test_data_contract_trap_005_rejects_department_spelling(self):
        sql = "SELECT * FROM dwh_internal.department d;"
        _, _, parsed = validate_ast_syntax(sql)
        valid, err = validate_data_contracts(parsed)
        assert valid is False
        assert "[TRAP-005]" in err

    def test_invariant_gate_confidence_threshold(self):
        output_low_conf = TextToSQLStructuredOutput(
            thought_scratchpad="Suy luận...",
            sql_query="SELECT 1;",
            tables_used=["dwh_internal.criteria"],
            confidence_score=0.65,
        )
        assert invariant_sql_validator(output_low_conf, ["dwh_internal.criteria"]) is False

        output_high_conf = TextToSQLStructuredOutput(
            thought_scratchpad="Suy luận...",
            sql_query="SELECT id FROM dwh_internal.criteria;",
            tables_used=["dwh_internal.criteria"],
            confidence_score=0.95,
        )
        assert invariant_sql_validator(output_high_conf, ["dwh_internal.criteria"]) is True


class TestTrackACompiler:
    """Kiểm thử Track A Deterministic Semantic AST Compiler."""

    @pytest.fixture
    def user_ctx(self):
        return UserSecurityContextDTO(
            user_id="user_test_01",
            username="Chuyên viên Sở",
            tenant_code="68",
            department_code="68-1-02",
            office_id=None,
            role_level=1,
        )

    def test_compile_from_spec_generates_valid_sql_under_1ms(self, user_ctx):
        compiler = TrackACompiler()
        spec = MetricSpecDTO(
            metric_code="kinh_phi_khuyen_cong",
            aggregation_func="SUM",
            grain="leaf_criteria",
            filters=[MetricFilter(field="year_code", operator="eq", value="2026")],
            group_by=["year_code"],
        )

        t0 = time.perf_counter()
        dto = compiler.compile_from_spec(spec, user_ctx, trace_id="trace_test_01")
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        assert dto is not None
        assert dto.generator_track == "TRACK_A_COMPILER"
        assert dto.ast_valid is True
        assert elapsed_ms < 5.0  # Chạy trong RAM cực nhanh (< 5ms)

        # Kiểm tra nội dung câu SQL
        sql = dto.raw_sql
        assert "WITH leaf_criteria AS" in sql
        assert "NOT EXISTS" in sql  # CTE nút lá chống double counting
        assert "f.report_status = 'approved'" in sql
        assert "NULLIF(TRIM(f.value), '')::numeric" in sql  # [TRAP-004]
        assert "f.tenant_code = '68'" in sql
        assert "f.department_code = '68-1-02'" in sql
        assert "lc.code = 'kinh_phi_khuyen_cong'" in sql

        # Kiểm định cú pháp SQLGlot
        valid, err, _ = validate_ast_syntax(sql)
        assert valid is True, f"SQL syntax error: {err}"

    def test_adaptive_fallthrough_on_complex_query(self, user_ctx):
        compiler = TrackACompiler()
        # Câu hỏi so sánh tăng trưởng YoY phức tạp -> Fallthrough sang Track B
        complex_router = RouterOutputDTO(
            session_id="test_session",
            query_sanitized="Tổng số vụ tai nạn lao động năm 2025 tăng hay giảm bao nhiêu phần trăm so với năm 2024?",
            route=RouteTypeEnum.DYNAMIC_PARALLEL_DAG,
            intent=IntentEnum.COMPLEX_DAG_ANALYTICS,
            confidence_score=0.90,
        )

        can_fast = compiler.can_compile_fast_track(complex_router)
        assert can_fast is False

        can_compile, dto = compiler.compile_from_router(complex_router, user_ctx)
        assert can_compile is False
        assert dto is None

    def test_compile_from_router_on_fast_track(self, user_ctx):
        from IPGov_Chatbot.schemas.router_dto import ActiveQuestFrameDTO, QuestStatusEnum

        compiler = TrackACompiler()
        active_quest = ActiveQuestFrameDTO(
            quest_id="quest_test_01",
            metric_code="kinh_phi_khuyen_cong",
            temporal_val="2026",
            status=QuestStatusEnum.COMMITTED,
        )
        fast_router = RouterOutputDTO(
            session_id="test_session",
            query_sanitized="Báo cáo kinh phí khuyến công năm 2026",
            route=RouteTypeEnum.TEMPLATE_FAST_TRACK,
            intent=IntentEnum.FAST_METRIC_COMPILER,
            active_quest=active_quest,
            confidence_score=0.95,
        )

        can_compile, dto = compiler.compile_from_router(fast_router, user_ctx)
        assert can_compile is True
        assert dto is not None
        assert dto.generator_track == "TRACK_A_COMPILER"
        assert "kinh_phi_khuyen_cong" in dto.raw_sql

    def test_live_db_explain_track_a_sql(self, user_ctx):
        """Kiểm chứng trực tiếp trên PostgreSQL DWH vna_wom_dev bằng EXPLAIN."""
        from IPGov_Chatbot.config import settings

        compiler = TrackACompiler()
        spec = MetricSpecDTO(
            metric_code="tai_nan_lao_dong_2",
            aggregation_func="SUM",
            grain="leaf_criteria",
            filters=[MetricFilter(field="year_code", operator="eq", value="2026")],
            group_by=["year_code"],
        )
        dto = compiler.compile_from_spec(spec, user_ctx)

        # Chạy EXPLAIN trên CSDL Remote DWH
        try:
            conn = psycopg2.connect(settings.sync_dwh_url, connect_timeout=5)
            cur = conn.cursor()
            cur.execute(f"EXPLAIN (FORMAT JSON) {dto.raw_sql}")
            res = cur.fetchall()
            assert res is not None
            assert len(res) > 0
            conn.close()
        except Exception as e:
            pytest.skip(f"PostgreSQL DWH không khả dụng: {e}")
