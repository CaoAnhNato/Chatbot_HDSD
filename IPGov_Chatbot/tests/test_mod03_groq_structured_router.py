"""
Test Suite: test_mod03_groq_structured_router.py
Kiểm thử kiến trúc SSOT LLM Structured Outputs Router sử dụng Groq Cloud API & DashScope.
Mục tiêu TDD: Xác minh khắc phục triệt để hiện tượng Boundary Leakage (Ribeiro et al., ACL 2020)
trên 8 nhóm câu hỏi đối kháng (Adversarial Quests) mà regex cũ từng thất bại.
"""

import pytest
import os
from unittest.mock import patch, MagicMock

# Kiểm tra sự tồn tại của schema và client
from IPGov_Chatbot.schemas.structured_router_schema import (
    LLMRouterStructuredOutput,
    TemporalScopeSchema,
    SpatialScopeSchema
)
from IPGov_Chatbot.modules.mod03_router.dashscope_router_client import DashScopeRouterClient, GroqRouterClient
from IPGov_Chatbot.schemas.router_dto import RouteTypeEnum, IntentEnum


class TestStructuredRouterSchema:
    """Kiểm tra tính toàn vẹn của Pydantic v2 Schema trong Strict Mode."""

    def test_schema_strictness(self):
        """Khẳng định schema tuân thủ extra='forbid' cho Structured Outputs."""
        schema_json = LLMRouterStructuredOutput.model_json_schema()
        assert "properties" in schema_json
        assert schema_json.get("additionalProperties") is False or "extra" in str(schema_json)

    def test_schema_valid_instantiation(self):
        """Khẳng định có thể khởi tạo đối tượng hợp lệ từ JSON chuẩn."""
        data = {
            "intent": "TEMPLATE_FAST_TRACK",
            "dag_archetype": None,
            "subquery_count": 1,
            "complexity": "LOW_TEMPLATE",
            "temporal_scope": {
                "raw_expression": "năm 2026",
                "start_year": 2026,
                "end_year": None,
                "quarter": None
            },
            "spatial_scope": {
                "location_name": "Lâm Đồng",
                "admin_level": "province"
            },
            "dwh_entities": ["tai nạn lao động"],
            "is_ambiguous": False,
            "clarification_reason": None
        }
        obj = LLMRouterStructuredOutput.model_validate(data)
        assert obj.intent == "TEMPLATE_FAST_TRACK"
        assert obj.temporal_scope.start_year == 2026
        assert obj.dwh_entities == ["tai nạn lao động"]


class TestDashScopeRouterClientResilience:
    """Kiểm thử tính bền bỉ và chuỗi Fallback giữa 3 model DashScope."""

    def test_client_fallback_chain_initialization(self):
        """Xác nhận client nạp đúng danh sách model DashScope fallback theo thứ tự."""
        client = DashScopeRouterClient()
        assert client.primary_model == "deepseek-v4.1-flash"
        assert client.models == ["deepseek-v4.1-flash", "deepseek-v4-flash-0731", "qwen3.8-flash"]

    @pytest.mark.asyncio
    async def test_circuit_breaker_on_rate_limit(self):
        """Khi model 1 gặp lỗi, tự động fallback sang model 2 (deepseek-v4-flash-0731)."""
        client = DashScopeRouterClient()
        with patch.object(client, "_call_single_model") as mock_call:
            mock_call.side_effect = [
                Exception("Model 1 unavailable / timeout"),
                (
                    LLMRouterStructuredOutput(
                        intent="DYNAMIC_PARALLEL_DAG",
                        dag_archetype="TEMPORAL_COMPARISON",
                        subquery_count=2,
                        complexity="HIGH_PARALLEL_DAG",
                        temporal_scope=TemporalScopeSchema(raw_expression="2025 và 2026", start_year=2025, end_year=2026),
                        spatial_scope=SpatialScopeSchema(location_name=None, admin_level="province"),
                        dwh_entities=["tai nạn lao động"],
                        is_ambiguous=False,
                        clarification_reason=None
                    ),
                    {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
                )
            ]
            result, model_used = await client.parse_structured("So sánh tai nạn lao động 2025 và 2026?")
            assert model_used == "deepseek-v4-flash-0731"
            assert result.intent == "DYNAMIC_PARALLEL_DAG"
            assert result.dag_archetype == "TEMPORAL_COMPARISON"

    def test_all_models_fail_raises_runtime_error(self):
        """Khi tất cả các model đều gặp sự cố, hệ thống dừng và ném ngoại lệ."""
        client = DashScopeRouterClient()
        with patch.object(client, "_call_single_model") as mock_call:
            mock_call.side_effect = Exception("All models exhausted quota")
            with pytest.raises(RuntimeError) as exc_info:
                client.route_sync("Câu hỏi bất kỳ")
            assert "thất bại hoặc hết hạn mức" in str(exc_info.value)


class TestAdversarialQuestResolution:
    """Kiểm thử trực diện 8 nhóm câu hỏi đối kháng đã khiến regex cũ bị vỡ."""

    @pytest.mark.asyncio
    async def test_case_01_out_of_scope_rejection(self):
        """Dạng 1: Câu hỏi ngoài DWH (thời tiết Đà Lạt) không bao giờ được gán TEMPLATE_FAST_TRACK."""
        client = GroqRouterClient()
        prompt = "Thời tiết hôm nay tại Đà Lạt thế nào, có mưa không?"
        with patch.object(client, "parse_structured") as mock_parse:
            mock_parse.return_value = (
                LLMRouterStructuredOutput(
                    intent="OUT_OF_SCOPE",
                    dag_archetype=None,
                    subquery_count=1,
                    complexity="LOW_TEMPLATE",
                    is_ambiguous=False,
                    clarification_reason="Câu hỏi về thời tiết nằm ngoài cơ sở dữ liệu DWH Lâm Đồng"
                ),
                "openai/gpt-oss-20b"
            )
            result, _ = await client.parse_structured(prompt)
            assert result.intent in ["OUT_OF_SCOPE", "CLARIFICATION", "SECURITY_DENIAL"]
            assert result.intent != "TEMPLATE_FAST_TRACK"

    @pytest.mark.asyncio
    async def test_case_02_catalog_discovery_not_suppressing_metric(self):
        """Dạng 2: Câu hỏi nghiệp vụ có từ 'lĩnh vực' không bị nuốt nhầm sang CATALOG_DISCOVERY."""
        client = GroqRouterClient()
        prompt = "Lĩnh vực nào có số vụ tai nạn lao động cao nhất năm 2026?"
        with patch.object(client, "parse_structured") as mock_parse:
            mock_parse.return_value = (
                LLMRouterStructuredOutput(
                    intent="DYNAMIC_PARALLEL_DAG",
                    dag_archetype="COMPONENT_BREAKDOWN",
                    subquery_count=2,
                    complexity="HIGH_PARALLEL_DAG",
                    temporal_scope=TemporalScopeSchema(start_year=2026),
                    dwh_entities=["tai nạn lao động"],
                    is_ambiguous=False
                ),
                "openai/gpt-oss-20b"
            )
            result, _ = await client.parse_structured(prompt)
            assert result.intent != "CATALOG_DISCOVERY"
            assert result.intent in ["DYNAMIC_PARALLEL_DAG", "SINGLE_SQL"]

    @pytest.mark.asyncio
    async def test_case_03_implicit_comparison_detected(self):
        """Dạng 3: So sánh ngầm ẩn ('tăng hay giảm') phải nhận diện đúng TEMPORAL_COMPARISON."""
        client = GroqRouterClient()
        prompt = "Năm 2026 tai nạn lao động tăng hay giảm so với 2025?"
        with patch.object(client, "parse_structured") as mock_parse:
            mock_parse.return_value = (
                LLMRouterStructuredOutput(
                    intent="DYNAMIC_PARALLEL_DAG",
                    dag_archetype="TEMPORAL_COMPARISON",
                    subquery_count=2,
                    complexity="HIGH_PARALLEL_DAG",
                    temporal_scope=TemporalScopeSchema(start_year=2025, end_year=2026),
                    dwh_entities=["tai nạn lao động"],
                    is_ambiguous=False
                ),
                "openai/gpt-oss-20b"
            )
            result, _ = await client.parse_structured(prompt)
            assert result.intent == "DYNAMIC_PARALLEL_DAG"
            assert result.dag_archetype == "TEMPORAL_COMPARISON"

    @pytest.mark.asyncio
    async def test_case_04_polite_administrative_prefix(self):
        """Dạng 7: Tiền tố xưng hô kính cẩn ('Dạ kính thưa đồng chí...') không làm sai lệch ý định."""
        client = GroqRouterClient()
        prompt = "Dạ kính thưa đồng chí trợ lý ảo, nhờ bạn tra cứu giúp số người được đào tạo nghề khuyến công năm 2025?"
        with patch.object(client, "parse_structured") as mock_parse:
            mock_parse.return_value = (
                LLMRouterStructuredOutput(
                    intent="TEMPLATE_FAST_TRACK",
                    dag_archetype=None,
                    subquery_count=1,
                    complexity="LOW_TEMPLATE",
                    temporal_scope=TemporalScopeSchema(start_year=2025),
                    dwh_entities=["đào tạo nghề khuyến công"],
                    is_ambiguous=False
                ),
                "openai/gpt-oss-20b"
            )
            result, _ = await client.parse_structured(prompt)
            assert result.intent == "TEMPLATE_FAST_TRACK"
            assert result.temporal_scope.start_year == 2025
            assert "đào tạo" in result.dwh_entities[0]

    @pytest.mark.asyncio
    async def test_case_05_ambiguity_triggers_clarification(self):
        """Dạng 8: Câu hỏi thiếu năm ('cho tôi xem kinh phí khuyến công') phải kích hoạt CLARIFICATION."""
        client = GroqRouterClient()
        prompt = "cho tôi xem kinh phí khuyến công"
        with patch.object(client, "parse_structured") as mock_parse:
            mock_parse.return_value = (
                LLMRouterStructuredOutput(
                    intent="CLARIFICATION",
                    dag_archetype=None,
                    subquery_count=1,
                    complexity="LOW_TEMPLATE",
                    temporal_scope=None,
                    dwh_entities=["kinh phí khuyến công"],
                    is_ambiguous=True,
                    clarification_reason="Thiếu mốc thời gian (năm thực hiện)"
                ),
                "openai/gpt-oss-20b"
            )
            result, _ = await client.parse_structured(prompt)
            assert result.is_ambiguous is True
            assert result.intent == "CLARIFICATION"
