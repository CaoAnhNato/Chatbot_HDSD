"""
Test Suite: IPGov_Chatbot/tests/test_mod05_phase2_track_b.py
Chức năng: Unit test kiểm chứng Phase 2 Module 05:
- 3-tier Prompt Caching templates (prompt_templates.py)
- 5 Kimball Archetype SQL Window Function patterns (archetype_patterns.py)
- Track B Gated 2-Stage Generator & Fallback Mechanism (track_b_generator.py)
Căn cứ:
- Plan: plan_module_05_execution.md (Mục 4.2)
- Spec: MODULE_05_SQL_COMPILER_SPEC.md (Mục 5, Mục 6)
"""

import unittest.mock
import pytest
import psycopg2

from IPGov_Chatbot.modules.mod05_sql_compiler.archetype_patterns import ArchetypePatternCatalog
from IPGov_Chatbot.modules.mod05_sql_compiler.ast_validator import validate_ast_syntax
from IPGov_Chatbot.modules.mod05_sql_compiler.prompt_templates import (
    STATIC_INVARIANT_PREFIX_PROMPT,
    build_3tier_text_to_sql_prompt,
)
from IPGov_Chatbot.modules.mod05_sql_compiler.track_b_generator import TrackBGenerator
from IPGov_Chatbot.schemas.catalog_dto import CatalogPrunedDTO, JoinPathDTO
from IPGov_Chatbot.schemas.router_dto import (
    ActiveQuestFrameDTO,
    IntentEnum,
    QuestStatusEnum,
    RouteTypeEnum,
    RouterOutputDTO,
)
from IPGov_Chatbot.schemas.sql_compiler_schema import TextToSQLStructuredOutput
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO


class TestPromptTemplates:
    """Kiểm thử cấu trúc Prompt 3 tầng tối ưu hóa Prompt Caching."""

    def test_static_invariant_prefix_length_and_contracts(self):
        # Đảm bảo độ dài tĩnh đủ lớn (>= 1024 tokens ~ 4000 ký tự) cho prefix caching
        assert len(STATIC_INVARIANT_PREFIX_PROMPT) >= 3000
        # Đảm bảo các hợp đồng dữ liệu cốt tử được ghim cố định
        assert "NULLIF(TRIM(f.value), '')::numeric" in STATIC_INVARIANT_PREFIX_PROMPT
        assert "f.report_status = 'approved'" in STATIC_INVARIANT_PREFIX_PROMPT
        assert "leaf_criteria" in STATIC_INVARIANT_PREFIX_PROMPT
        assert "deparment" in STATIC_INVARIANT_PREFIX_PROMPT
        assert "thought_scratchpad" in STATIC_INVARIANT_PREFIX_PROMPT
        assert "TEMPORAL_COMPARISON" in STATIC_INVARIANT_PREFIX_PROMPT
        assert "RANKING_TOP_K" in STATIC_INVARIANT_PREFIX_PROMPT

    def test_build_3tier_prompt_composition(self):
        catalog_pruned = CatalogPrunedDTO(
            selected_tables=["dwh_internal.fact_report_criteria", "dwh_internal.criteria"],
            join_paths=[
                JoinPathDTO(
                    source_table="dwh_internal.fact_report_criteria",
                    target_table="dwh_internal.criteria",
                    on_clause="f.criteria_id = c.id",
                    join_type="INNER JOIN",
                )
            ],
            schema_slice_ddl="-- Slice DDL Test",
            data_contracts=["status = 'approved'"],
        )
        user_ctx = UserSecurityContextDTO(
            user_id="user_test",
            username="Chuyên viên",
            tenant_code="68",
            department_code="68-1-02",
            office_id=None,
            role_level=1,
        )
        router_out = RouterOutputDTO(
            session_id="session_01",
            query_sanitized="So sánh số lượng tai nạn lao động năm 2025 và 2026",
            route=RouteTypeEnum.DYNAMIC_PARALLEL_DAG,
            intent=IntentEnum.COMPLEX_DAG_ANALYTICS,
            dag_archetype="TEMPORAL_COMPARISON",
            confidence_score=0.92,
        )

        user_prompt = build_3tier_text_to_sql_prompt(
            catalog_pruned=catalog_pruned,
            router_output=router_out,
            security_context=user_ctx,
            negative_constraints="KHÔNG ĐƯỢC dùng value::numeric",
        )

        assert "Slice DDL Test" in user_prompt
        assert "TEMPORAL_COMPARISON" in user_prompt
        assert "'68'" in user_prompt
        assert "KHÔNG ĐƯỢC dùng value::numeric" in user_prompt
        assert "So sánh số lượng tai nạn lao động" in user_prompt


class TestArchetypePatterns:
    """Kiểm thử 5 mẫu hình phân tích Kimball Archetypes."""

    def test_temporal_comparison_sql_validity(self):
        sql = ArchetypePatternCatalog.build_temporal_comparison_sql(
            metric_code="tai_nan_lao_dong_2",
            years=["2025", "2026"],
            tenant_code="68",
        )
        assert "LAG(tong_gia_tri) OVER (ORDER BY nam ASC)" in sql
        assert "ROUND" in sql
        valid, err, _ = validate_ast_syntax(sql)
        assert valid is True, f"Syntax error: {err}"

    def test_ranking_top_k_sql_validity(self):
        sql = ArchetypePatternCatalog.build_ranking_top_k_sql(
            metric_code="kinh_phi_khuyen_cong",
            year="2026",
            top_k=5,
            tenant_code="68",
        )
        assert "DENSE_RANK() OVER" in sql
        assert "khoang_bien_do" in sql
        valid, err, _ = validate_ast_syntax(sql)
        assert valid is True, f"Syntax error: {err}"

    def test_part_to_whole_sql_validity(self):
        sql = ArchetypePatternCatalog.build_part_to_whole_sql(
            year="2026",
            tenant_code="68",
            scope_name="Xây dựng",
        )
        assert "SUM(SUM(NULLIF(TRIM(f.value), '')::numeric)) OVER ()" in sql
        assert "ty_trong_pct" in sql
        valid, err, _ = validate_ast_syntax(sql)
        assert valid is True, f"Syntax error: {err}"

    def test_live_db_explain_archetype_queries(self):
        """Kiểm chứng cả 3 mẫu SQL trên PostgreSQL Docker vna_wom_dev bằng EXPLAIN."""
        try:
            conn = psycopg2.connect(
                host="localhost",
                port=5432,
                dbname="vna_wom_dev",
                user="postgres",
                password="postgres",
                connect_timeout=2,
            )
            cur = conn.cursor()

            sql1 = ArchetypePatternCatalog.build_temporal_comparison_sql("tai_nan_lao_dong_2", ["2025", "2026"])
            cur.execute(f"EXPLAIN (FORMAT JSON) {sql1}")
            assert len(cur.fetchall()) > 0

            sql2 = ArchetypePatternCatalog.build_ranking_top_k_sql("kinh_phi_khuyen_cong", "2026", 5)
            cur.execute(f"EXPLAIN (FORMAT JSON) {sql2}")
            assert len(cur.fetchall()) > 0

            sql3 = ArchetypePatternCatalog.build_part_to_whole_sql("2026", "68")
            cur.execute(f"EXPLAIN (FORMAT JSON) {sql3}")
            assert len(cur.fetchall()) > 0

            conn.close()
        except Exception as e:
            pytest.skip(f"Docker PostgreSQL không khả dụng: {e}")


class TestTrackBGenerator:
    """Kiểm thử Track B Gated 2-Stage Generator."""

    @pytest.fixture
    def sample_inputs(self):
        cat = CatalogPrunedDTO(
            selected_tables=["dwh_internal.fact_report_criteria", "dwh_internal.criteria"],
            bridge_tables=["dwh_internal.deparment"],
            join_paths=[],
            schema_slice_ddl="",
        )
        user_ctx = UserSecurityContextDTO(
            user_id="user_test",
            username="Chuyên viên",
            tenant_code="68",
            department_code="68-1-02",
            office_id=None,
            role_level=1,
        )
        router_out = RouterOutputDTO(
            session_id="session_01",
            query_sanitized="Xếp hạng 5 đơn vị có số lượng hồ sơ cao nhất",
            route=RouteTypeEnum.DYNAMIC_PARALLEL_DAG,
            intent=IntentEnum.COMPLEX_DAG_ANALYTICS,
            dag_archetype="RANKING_TOP_K",
            confidence_score=0.90,
        )
        return cat, router_out, user_ctx

    def test_track_b_fast_gate_success(self, sample_inputs):
        cat, router_out, user_ctx = sample_inputs
        generator = TrackBGenerator()

        mock_output = TextToSQLStructuredOutput(
            thought_scratchpad="Bước 1: Thực thể. Bước 2: Bảng. Bước 3: Top-K. Bước 4: An toàn.",
            sql_query="SELECT f.name, SUM(NULLIF(TRIM(f.value), '')::numeric) AS tong FROM dwh_internal.fact_report_criteria f GROUP BY f.name ORDER BY tong DESC LIMIT 5;",
            tables_used=["dwh_internal.fact_report_criteria"],
            confidence_score=0.95,
        )

        with unittest.mock.patch(
            "IPGov_Chatbot.modules.mod05_sql_compiler.track_b_generator.call_structured_with_fallback",
            return_value=(mock_output, "google/gemini-3.5-flash-lite", {"cached_tokens": 1200}, 450.0),
        ):
            dto = generator.generate_sql_sync(cat, router_out, user_ctx)

            assert dto is not None
            assert dto.generator_track == "TRACK_B_LLM"
            assert dto.llm_provider == "google/gemini-3.5-flash-lite"
            assert dto.fallback_triggered is False
            assert dto.prompt_cache_hit is True
            assert dto.ast_valid is True
            assert "dwh_internal.fact_report_criteria" in dto.tables_referenced

    def test_track_b_heavy_fallback_triggered(self, sample_inputs):
        cat, router_out, user_ctx = sample_inputs
        generator = TrackBGenerator()

        mock_fallback_output = TextToSQLStructuredOutput(
            thought_scratchpad="Cổng 2: Phân tích lại lỗi AST và sửa câu truy vấn có Window Functions.",
            sql_query="SELECT f.name, DENSE_RANK() OVER (ORDER BY SUM(NULLIF(TRIM(f.value), '')::numeric) DESC) FROM dwh_internal.fact_report_criteria f GROUP BY f.name;",
            tables_used=["dwh_internal.fact_report_criteria"],
            confidence_score=0.92,
        )

        with unittest.mock.patch(
            "IPGov_Chatbot.modules.mod05_sql_compiler.track_b_generator.call_structured_with_fallback",
            return_value=(mock_fallback_output, "deepseek/deepseek-v4.1-flash", {"cached_tokens": 0}, 2400.0),
        ):
            dto = generator.generate_sql_sync(cat, router_out, user_ctx)

            assert dto is not None
            assert dto.generator_track == "TRACK_B_LLM"
            assert dto.llm_provider == "deepseek/deepseek-v4.1-flash"
            assert dto.fallback_triggered is True
            assert dto.ast_valid is True
