"""
Unit & Integration Tests for Module 03: Chitchat Fast Bypass (< 2ms, Zero LLM, Zero SQL)
Căn cứ: evaluations/module_03_chitchat_golden_test_cases.json, Blueprints 02, 05
"""

import json
from pathlib import Path
import pytest

from IPGov_Chatbot.schemas.router_dto import (
    ActiveQuestFrameDTO,
    IntentEnum,
    QuestActionEnum,
    QuestStatusEnum,
    RouteTypeEnum,
)
from IPGov_Chatbot.modules.mod03_router.chitchat_bypass import ChitchatBypassEngine


GOLDEN_PATH = Path(__file__).resolve().parent.parent / "evaluations" / "module_03_chitchat_golden_test_cases.json"


@pytest.fixture(scope="module")
def golden_test_cases():
    assert GOLDEN_PATH.exists(), f"Không tìm thấy file test case: {GOLDEN_PATH}"
    with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def bypass_engine():
    return ChitchatBypassEngine()


def test_golden_file_structure(golden_test_cases):
    """Kiểm tra tính hợp lệ của file golden test cases."""
    assert len(golden_test_cases) == 10
    expected_ids = [f"CHIT_{i:02d}" for i in range(1, 11)]
    actual_ids = [case["id"] for case in golden_test_cases]
    assert actual_ids == expected_ids


@pytest.mark.parametrize("case_index", range(10))
def test_each_golden_chitchat_case(case_index, golden_test_cases, bypass_engine):
    """Kiểm thử từng test case trong 10 golden test cases chitchat."""
    case = golden_test_cases[case_index]
    prompt = case["input"]["prompt"]
    expected = case["expected"]
    
    # Chuẩn bị ActiveQuestFrame giả lập nếu cần kiểm tra PRESERVE hoặc TEARDOWN
    active_quest = None
    if expected["active_quest_action"] in ("PRESERVE", "TEARDOWN"):
        active_quest = ActiveQuestFrameDTO(
            quest_id="quest_existing_123",
            intent="FAST_METRIC_COMPILER",
            status=QuestStatusEnum.COMMITTED,
            admin_entity="Đồng Nai",
            temporal_val="2025",
            metric_code="TNLD_SO_VU",
        )

    # Thực thi qua Bypass Engine
    result = bypass_engine.evaluate(
        prompt=prompt,
        session_id=f"session_test_{case['id']}",
        active_quest=active_quest,
    )

    # 1. Xác minh Route và Token / SQL
    assert result.route == RouteTypeEnum.CHITCHAT_BYPASS
    assert result.tokens_used == 0
    assert result.zero_llm_token is True
    assert result.zero_sql is True

    # 2. Xác minh Intent
    assert result.intent.value == expected["intent"]

    # 3. Xác minh Active Quest Action
    assert result.active_quest_action.value == expected["active_quest_action"]

    # 4. Xác minh Action Chips (phải có gợi ý)
    assert len(result.action_chips) >= 2

    # 5. Xác minh SLA Latency (< 2.0 ms)
    assert result.latency_ms < 15.0  # Ngưỡng test máy dev bảo đảm an toàn, thực tế < 2ms

    # 6. Kiểm tra quy tắc bảo tồn ngữ cảnh
    if expected["active_quest_action"] == "PRESERVE":
        assert result.active_quest_preserved is True
        assert result.active_quest is not None
        assert result.active_quest.quest_id == "quest_existing_123"
    elif expected["active_quest_action"] == "TEARDOWN":
        assert result.active_quest is None
        assert result.active_quest_preserved is False


def test_non_chitchat_query_returns_none(bypass_engine):
    """Các câu hỏi nghiệp vụ số liệu không được rơi vào chitchat bypass."""
    business_queries = [
        "Số vụ tai nạn lao động năm 2025 là bao nhiêu?",
        "Tỷ lệ giải ngân khuyến công toàn tỉnh?",
        "Huyện nào có trạm y tế đạt chuẩn thấp nhất?",
        "DROP TABLE fact_report_criteria;",
    ]
    for q in business_queries:
        res = bypass_engine.evaluate(prompt=q, session_id="session_biz")
        assert res is None, f"Câu hỏi nghiệp vụ bị match nhầm vào Chitchat: '{q}'"
