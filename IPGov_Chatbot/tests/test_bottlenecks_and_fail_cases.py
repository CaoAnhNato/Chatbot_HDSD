"""
Test Suite: test_bottlenecks_and_fail_cases.py
Chức năng: Bộ kiểm thử TDD hồi quy kiểm chứng 8 điểm nghẽn và ca lỗi kiến trúc (FAIL-001 -> FAIL-008).
Tài liệu tham chiếu:
- IPGov_Chatbot/docs/FAILED_TEST_CASES_LOG.md
- IPGov_Chatbot/docs/TEST_CASES_GENEALOGY_AND_MAPPING_GUIDE.md
- TRAPS.md: [TRAP-007], [TRAP-010], [TRAP-011], [TRAP-012]
Tuân thủ: .agents/skills/bonsai-test/SKILL.md & .agents/skills/tdd/SKILL.md
"""

import pytest
import uuid
import inspect
import unittest.mock
from typing import Dict, Any

from IPGov_Chatbot.schemas.structured_router_schema import LLMRouterStructuredOutput
from IPGov_Chatbot.schemas.router_dto import (
    RouterOutputDTO,
    RouteTypeEnum,
    IntentEnum,
    ActiveQuestFrameDTO,
    QuestStatusEnum,
    QuestActionEnum,
)
from IPGov_Chatbot.modules.mod04_catalog.schema_pruner import SchemaPruner
from IPGov_Chatbot.modules.mod04_catalog.steiner_tree_builder import SteinerTreeBuilder
from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog
from IPGov_Chatbot.modules.mod03_router.intent_router import IntentRouter
from IPGov_Chatbot.modules.mod03_router.redis_session_manager import RedisSessionManager
from IPGov_Chatbot.modules.mod01_gateway.jwt_service import JWTService


class TestModule04InterfaceAndSwallowingFailures:
    """
    Kiểm thử TDD cho các lỗi khế ước giao tiếp và nuốt intent của Module 04.
    """

    def test_fail_008_schema_pruner_accepts_router_output_dto(self):
        """
        [FAIL-008] SchemaPruner.prune_schema() phải chấp nhận RouterOutputDTO
        thay vì chỉ nhận str, trích xuất query_sanitized và không ném AttributeError.
        """
        pruner = SchemaPruner()
        router_dto = RouterOutputDTO(
            session_id=str(uuid.uuid4()),
            query_sanitized="Báo cáo tiến độ giải ngân vốn đầu tư công năm 2025",
            route=RouteTypeEnum.TEMPLATE_FAST_TRACK,
            intent=IntentEnum.FAST_METRIC_COMPILER,
            confidence_score=0.95,
        )

        # Hành vi kỳ vọng: Không bị sập với AttributeError: 'RouterOutputDTO' object has no attribute 'strip'
        # và trả về CatalogPrunedDTO hợp lệ chứa Fact table.
        result = pruner.prune_schema(router_dto)
        assert result is not None
        assert "dwh_internal.fact_report_criteria" in result.selected_tables

    def test_fail_006_fact_query_with_chi_tieu_not_swallowed_as_dimension_only(self):
        """
        [FAIL-006] Câu hỏi thống kê số liệu Fact có chứa từ khóa 'chỉ tiêu'
        (ví dụ: 'Báo cáo thống kê số liệu chỉ tiêu khuyến công năm 2025')
        BẮT BUỘC phải giữ lại bảng Fact 'dwh_internal.fact_report_criteria' trong selected_tables,
        tuyệt đối không được chỉ trả về mỗi ['dwh_internal.criteria'].
        """
        pruner = SchemaPruner()
        prompt = "Báo cáo thống kê số liệu chỉ tiêu khuyến công năm 2025"

        result = pruner.prune_schema(prompt)
        assert "dwh_internal.fact_report_criteria" in result.selected_tables, (
            f"Bảng Fact bị nuốt mất! selected_tables={result.selected_tables}"
        )


class TestModule04SteinerTreeAndCatalogSyncFailures:
    """
    Kiểm thử TDD cho cấu trúc đồ thị Steiner Tree và đồng bộ CSDL Live PostgreSQL.
    """

    def test_fail_007_steiner_tree_fact_to_deparment_preserves_null_office_fact_rows(self):
        """
        [FAIL-007] Đồ thị DWH Steiner Tree phải có cạnh trực tiếp hoặc đường dẫn
        cho phép nối fact_report_criteria với deparment qua department_code,
        không ép buộc phải qua office để tránh loại bỏ 34 dòng Fact có office_id IS NULL.
        """
        builder = SteinerTreeBuilder()
        tree = builder.build_steiner_tree([
            "dwh_internal.fact_report_criteria",
            "dwh_internal.deparment",
        ])

        nodes = set(tree.nodes())
        assert "dwh_internal.fact_report_criteria" in nodes
        assert "dwh_internal.deparment" in nodes
        # Nếu chỉ có 2 terminal Fact và Department, đường đi tối ưu không được ép qua office
        # vì Fact có sẵn cột department_code
        assert "dwh_internal.office" not in nodes, (
            f"Steiner Tree vẫn ép bảng trung gian office: {nodes}"
        )

    def test_fail_005_pipeline_logs_query_does_not_request_nonexistent_row_count(self):
        """
        [FAIL-005] Câu truy vấn mốc ETL trong _hydrate_catalog không được chứa cột 'row_count'
        vốn không tồn tại trong bảng dwh_internal.pipeline_logs của CSDL vna_wom_dev.
        """
        source_code = inspect.getsource(DuckDBSemanticCatalog._hydrate_catalog)
        assert "row_count" not in source_code, (
            "Hàm _hydrate_catalog vẫn đang truy vấn cột ảo 'row_count' từ dwh_internal.pipeline_logs!"
        )


class TestModule03DecisionCacheAndRoutingFailures:
    """
    Kiểm thử TDD cho Decision Cache Amnesia và Dimension Routing trong Module 03.
    """

    def test_fail_004_decision_cache_hit_preserves_active_quest_in_redis_session(self):
        """
        [FAIL-004] Khi câu hỏi Turn 1 trúng Decision Cache trong Redis/Session,
        Router BẮT BUỘC vẫn phải lưu ActiveQuestFrameDTO vào session
        để Turn 2 (anaphora / follow-up) có thể kế thừa ngữ cảnh thay vì bị mất trí nhớ.
        """
        session_mgr = RedisSessionManager()
        router = IntentRouter(session_manager=session_mgr)
        test_session_id = f"test_cache_amnesia_{uuid.uuid4().hex[:8]}"

        # Pre-seed decision cache để đảm bảo chắc chắn trúng cache ở Turn 1
        prompt_t1 = "Tổng số người được đào tạo từ nguồn kinh phí khuyến công tại Phòng Kinh tế năm 2025?"
        fake_cached_quest = ActiveQuestFrameDTO(
            quest_id=str(uuid.uuid4()),
            metric_code="nguoi_duoc_dao_tao",
            temporal_val="2025",
            admin_entity="Phòng Kinh tế",
            admin_level="district",
            status=QuestStatusEnum.COMMITTED,
            turn_count=1,
        )
        fake_cached_dto = RouterOutputDTO(
            session_id=test_session_id,
            query_sanitized=prompt_t1,
            route=RouteTypeEnum.TEMPLATE_FAST_TRACK,
            routing_track="TEMPLATE_FAST_TRACK",
            intent=IntentEnum.FAST_METRIC_COMPILER,
            persona=router.persona_classifier.classify(prompt_t1),
            confidence_score=0.98,
            tokens_used=0,
            zero_llm_token=True,
            zero_sql=False,
            safety_timeout_seconds=5.0,
            sla_max_latency_ms=300.0,
            latency_ms=1.0,
            active_quest=fake_cached_quest,
            active_quest_preserved=True,
            active_quest_action=QuestActionEnum.COMMIT,
            complexity="LOW_TEMPLATE",
        )
        session_mgr.set_decision_cache(prompt_t1, fake_cached_dto.model_dump(mode="json"))

        # Turn 1: Bắt buộc trúng Decision Cache
        res_t1 = router.route_query(prompt_t1, session_id=test_session_id)
        assert res_t1 is not None
        assert res_t1.zero_llm_token is True

        # Kiểm tra: Session của test_session_id BẮT BUỘC phải có ActiveQuestFrame (Không bị amnesia!)
        saved_quest = session_mgr.get_active_quest(test_session_id)
        assert saved_quest is not None, (
            "Lỗi Mất Trí Nhớ Phiên: Trúng Decision Cache nhưng không lưu active_quest vào Session!"
        )
        assert saved_quest.admin_entity == "Phòng Kinh tế"
        assert saved_quest.temporal_val == "2025"

        # Turn 2: Câu hỏi tỉnh lược anaphora
        prompt_t2 = "Thế còn kinh phí thực hiện ở đó là bao nhiêu?"
        with unittest.mock.patch.object(
            router.router_client,
            "route_sync",
            return_value=(
                LLMRouterStructuredOutput(
                    intent="TEMPLATE_FAST_TRACK",
                    is_ambiguous=False,
                    is_topic_shift=False,
                    dwh_entities=["kinh_phi_thuc_hien"],
                ),
                "mock-model",
                {"total_tokens": 10},
                1.0,
            ),
        ):
            res_t2 = router.route_query(prompt_t2, session_id=test_session_id)

        # Turn 2 không được rơi vào CLARIFICATION đòi hỏi năm và phòng ban lại từ đầu
        assert res_t2.route != RouteTypeEnum.CLARIFICATION, (
            "Turn 2 bị rơi vào CLARIFICATION do Turn 1 trúng cache bị mất ngữ cảnh!"
        )

    def test_fail_003_router_dimension_query_golden_021_not_swallowed_as_chitchat(self):
        """
        [FAIL-003] Câu hỏi tra cứu danh mục bảng chiều GOLDEN_021
        không được gán bypass_response văn bản tĩnh giới thiệu chung và zero_sql=True,
        mà phải giữ nguyên để Module 4/5 xử lý sinh SQL danh mục.
        """
        router = IntentRouter()
        prompt_golden_021 = (
            "Cán bộ cho tôi hỏi, ở tỉnh Lâm Đồng trong năm nay có những nhiệm vụ "
            "hay chương trình nào về hỗ trợ việc làm và đào tạo nghề cho người lao động vậy?"
        )
        with unittest.mock.patch.object(
            router.router_client,
            "route_sync",
            return_value=(
                LLMRouterStructuredOutput(
                    intent="CATALOG_DISCOVERY",
                    is_ambiguous=False,
                    is_topic_shift=False,
                    dwh_entities=["mission"],
                ),
                "mock-model",
                {"total_tokens": 10},
                1.0,
            ),
        ):
            res = router.route_query(prompt_golden_021, session_id=f"test_dim_{uuid.uuid4().hex[:8]}")

        # Không được nuốt vào bypass_response tĩnh
        assert res.bypass_response is None, (
            f"GOLDEN_021 bị nuốt thành văn bản tĩnh chitchat bypass! bypass_response={res.bypass_response}"
        )
        assert res.zero_sql is False, "GOLDEN_021 phải có zero_sql=False để Module 4/5 sinh SQL!"
        assert res.route == RouteTypeEnum.CATALOG_DISCOVERY


class TestPipelineIntegrationFailures:
    """
    Kiểm thử TDD cho điểm nghẽn đứt gãy luồng Live SSE từ Gateway -> Module 3 -> Module 4.
    """

    @pytest.mark.asyncio
    async def test_fail_002_gateway_stream_forwards_to_schema_pruner(self):
        """
        [FAIL-002] Live SSE event generator tại gateway_endpoint.py
        sau khi có RouterOutputDTO (nhánh Fact) BẮT BUỘC phải gọi SchemaPruner
        và phát event schema_pruned (hoặc thought_progress mang lát cắt DDL)
        thay vì kết thúc ngay kết nối với event: done (status: ready_for_router).
        """
        from IPGov_Chatbot.modules.mod01_gateway import gateway_endpoint

        jwt_svc = JWTService()
        token = jwt_svc.encode({
            "user_id": "u_test",
            "username": "test_user",
            "role_level": 1,
            "tenant_code": "68",
            "department_code": "68-01",
        })
        auth_header = f"Bearer {token}"
        prompt = "Báo cáo số vụ tai nạn lao động năm 2026 toàn tỉnh Lâm Đồng"

        events = []
        with unittest.mock.patch.object(
            gateway_endpoint._router_engine.router_client,
            "route_sync",
            return_value=(
                LLMRouterStructuredOutput(
                    intent="TEMPLATE_FAST_TRACK",
                    is_ambiguous=False,
                    is_topic_shift=False,
                    dwh_entities=["tai_nan_lao_dong"],
                ),
                "mock-model",
                {"total_tokens": 10},
                1.0,
            ),
        ):
            async for chunk in gateway_endpoint.chat_sse_event_generator(
                prompt=prompt, auth_header=auth_header, client_ip="127.0.0.1", session_id=str(uuid.uuid4())
            ):
                events.append(chunk)

        full_stream = "".join(events)
        # Kiểm tra pipeline không dừng lại cụt ngủn ở ready_for_router mà có sự tham gia của Module 4
        assert "schema_pruned" in full_stream or "schema_slice" in full_stream or "fact_report_criteria" in full_stream, (
            "Đường ống Gateway SSE bị đứt gãy sau Router, không gọi qua Module 4 Schema Pruner!"
        )
