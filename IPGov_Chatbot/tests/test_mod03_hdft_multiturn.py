"""
Unit & Integration Tests for Module 03: H-DFT Dialogue Tracker & Multi-turn Threads
Căn cứ: evaluations/module_03_route_catalog_discovery.json,
        evaluations/MULTI_TURN_AND_DISCOVERY_TEST_CASES.md,
        Blueprints 02, 05, 08
"""

import json
from pathlib import Path
import pytest

from IPGov_Chatbot.schemas.router_dto import (
    IntentEnum,
    QuestActionEnum,
    QuestStatusEnum,
    RouteTypeEnum,
)
from IPGov_Chatbot.modules.mod03_router.intent_router import IntentRouter
from IPGov_Chatbot.modules.mod03_router.hdft_dialogue_tracker import HDFTDialogueTracker


DISC_PATH = Path(__file__).resolve().parent.parent / "evaluations" / "module_03_route_catalog_discovery.json"


@pytest.fixture(scope="module")
def discovery_cases():
    assert DISC_PATH.exists(), f"Không tìm thấy file: {DISC_PATH}"
    with open(DISC_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def router():
    r = IntentRouter()
    if r.session_manager and r.session_manager.enabled:
        for s in ["sess_thread_01", "sess_thread_02", "sess_thread_03", "sess_thread_04", "sess_thread_05"]:
            r.session_manager.clear_session(s)
        r.session_manager.clear_decision_cache()
    return r


@pytest.fixture
def tracker():
    return HDFTDialogueTracker()


# ===========================================================================
# 1. TEST 10 DISCOVERY & CAPABILITY CASES (DISC_01 -> DISC_10)
# ===========================================================================

def test_discovery_file_structure(discovery_cases):
    assert len(discovery_cases) == 10
    expected_ids = [f"DISC_{i:02d}" for i in range(1, 11)]
    actual_ids = [c["id"] for c in discovery_cases]
    assert actual_ids == expected_ids


@pytest.mark.parametrize("case_index", range(10))
def test_discovery_cases_routing(case_index, discovery_cases, router):
    """Kiểm tra 10 câu hỏi khám phá năng lực đều định tuyến sang CATALOG_DISCOVERY."""
    case = discovery_cases[case_index]
    prompt = case["input"]["prompt"]
    expected = case["expected"]

    result = router.route_query(prompt=prompt, session_id=f"disc_sess_{case['id']}")

    assert result.route == RouteTypeEnum.CATALOG_DISCOVERY
    assert result.intent == IntentEnum.META_CAPABILITY
    assert result.zero_sql is True
    assert result.latency_ms <= expected["sla_max_latency_ms"]
    assert len(result.action_chips) >= 1
    assert result.bypass_response is not None


# ===========================================================================
# 2. TEST 5 MULTI-TURN CONVERSATIONAL THREADS (16 TURNS H-DFT)
# ===========================================================================

def test_thread_01_anaphora_yoy_drilldown(router):
    """
    THREAD_01: Capability -> Metric -> Anaphora YoY ('Số lượng này') -> Drill-down ('Ở những đơn vị nào')
    """
    session_id = "sess_thread_01"

    # Turn 1: Khám phá chức năng
    t1 = router.route_query("Hệ thống này có chức năng gì ?", session_id=session_id)
    assert t1.route == RouteTypeEnum.CATALOG_DISCOVERY

    # Turn 2: Tra cứu số vụ tai nạn lao động gần đây
    t2 = router.route_query("Số vụ tai nạn lao động gần đây là bao nhiêu ?", session_id=session_id)
    assert t2.route in (RouteTypeEnum.TEMPLATE_FAST_TRACK, RouteTypeEnum.CLARIFICATION)
    assert t2.active_quest is not None
    assert t2.active_quest.temporal_val == "2025"  # "gần đây" giải quyết về 2025
    assert "tai nạn lao động" in (t2.active_quest.metric_code or "").lower()

    # Turn 3: Anaphora resolution: "Số lượng này đang tăng hay giảm ?"
    t3 = router.route_query("Số lượng này đang tăng hay giảm ?", session_id=session_id)
    assert t3.active_quest is not None
    assert "tai nạn lao động" in (t3.active_quest.metric_code or "").lower()
    assert t3.active_quest.comparison_year == "2024"  # YoY so sánh với 2024

    # Turn 4: Drill-down: "Ở những đơn vị nào xảy ra nhiều nhất ?"
    t4 = router.route_query("Ở những đơn vị nào xảy ra nhiều nhất ?", session_id=session_id)
    assert t4.active_quest is not None
    assert t4.active_quest.admin_level in (1, 2)  # Hạ độ mịn xuống cấp huyện/đơn vị


def test_thread_02_hierarchical_drilldown(router):
    """
    THREAD_02: Provincial total -> Hierarchical drill-down (Tỉnh -> Huyện -> Chi tiết huyện đó)
    """
    session_id = "sess_thread_02"

    # Turn 1: Toàn tỉnh năm 2025 trạm y tế đạt chuẩn
    t1 = router.route_query("Toàn tỉnh năm 2025 có bao nhiêu trạm y tế đạt chuẩn quốc gia ?", session_id=session_id)
    assert t1.active_quest is not None
    assert t1.active_quest.temporal_val == "2025"
    assert t1.active_quest.admin_level == 0  # Toàn tỉnh

    # Turn 2: Huyện nào thấp nhất
    t2 = router.route_query("Huyện nào có số lượng thấp nhất ?", session_id=session_id)
    assert t2.active_quest is not None
    assert t2.active_quest.admin_level == 1  # Cấp Huyện
    assert "trạm y tế" in (t2.active_quest.metric_code or "").lower()

    # Turn 3: "Cụ thể huyện đó có bao nhiêu trạm chưa đạt và tỷ lệ đạt chuẩn là bao nhiêu %?"
    t3 = router.route_query("Cụ thể huyện đó có bao nhiêu trạm chưa đạt và tỷ lệ đạt chuẩn là bao nhiêu %?", session_id=session_id)
    assert t3.active_quest is not None
    assert t3.active_quest.admin_level == 1  # Kế thừa cấp huyện từ lượt trước


def test_thread_03_ambiguity_clarification_slot_filling(router):
    """
    THREAD_03: Thiếu tham số -> Hỏi làm rõ (Clarification) -> Điền slot ngắn gọn -> Kế thừa so sánh
    """
    session_id = "sess_thread_03"

    # Turn 1: Câu hỏi thiếu cả năm và địa bàn
    t1 = router.route_query("Cho tôi xem số liệu giải ngân kinh phí khuyến công.", session_id=session_id)
    assert t1.route == RouteTypeEnum.CLARIFICATION
    assert t1.intent == IntentEnum.CLARIFICATION_NEEDED
    assert len(t1.missing_slots) > 0
    assert len(t1.clarification_options) > 0

    # Turn 2: Người dùng trả lời bổ sung: "Năm 2025 toàn tỉnh."
    t2 = router.route_query("Năm 2025 toàn tỉnh.", session_id=session_id)
    assert t2.active_quest is not None
    assert t2.active_quest.temporal_val == "2025"
    assert t2.active_quest.admin_level == 0
    assert "khuyến công" in (t2.active_quest.metric_code or "").lower()
    assert t2.route == RouteTypeEnum.TEMPLATE_FAST_TRACK

    # Turn 3: "So với năm 2024 thì sao ?"
    t3 = router.route_query("So với năm 2024 thì sao ?", session_id=session_id)
    assert t3.active_quest is not None
    assert t3.active_quest.temporal_val == "2025"
    assert t3.active_quest.comparison_year == "2024"
    assert "khuyến công" in (t3.active_quest.metric_code or "").lower()


def test_thread_04_form_discovery_and_workflow_status(router):
    """
    THREAD_04: Biểu mẫu thu thập -> Lọc theo phòng -> Kiểm tra trạng thái nộp duyệt
    """
    session_id = "sess_thread_04"

    # Turn 1: Năm 2026 có những biểu mẫu nào
    t1 = router.route_query("Năm 2026 có những biểu mẫu thu thập dữ liệu nào ?", session_id=session_id)
    assert t1.route in (RouteTypeEnum.CATALOG_DISCOVERY, RouteTypeEnum.TEMPLATE_FAST_TRACK, RouteTypeEnum.CLARIFICATION)

    # Turn 2: Biểu mẫu nào của Phòng Xây dựng sắp đến hạn nộp
    t2 = router.route_query("Biểu mẫu nào của Phòng Xây dựng sắp đến hạn nộp ?", session_id=session_id)
    assert t2.active_quest is not None
    assert "Phòng Xây dựng" in (t2.active_quest.admin_entity or "")

    # Turn 3: "Báo cáo này của phòng đã nộp và duyệt chưa ?"
    t3 = router.route_query("Báo cáo này của phòng đã nộp và duyệt chưa ?", session_id=session_id)
    assert t3.active_quest is not None
    assert "Phòng Xây dựng" in (t3.active_quest.admin_entity or "")


def test_thread_05_anomaly_accountability_and_topic_shift(router):
    """
    THREAD_05: Dị thường dữ liệu Y tế -> Cán bộ phụ trách -> Chuyển đổi chủ đề sang Giảm nghèo (Topic Shift)
    """
    session_id = "sess_thread_05"

    # Turn 1: Dị thường y tế 2025
    t1 = router.route_query("Có chỉ tiêu nào của lĩnh vực y tế năm 2025 bị để trống hoặc bằng 0 bất thường không ?", session_id=session_id)
    assert t1.active_quest is not None
    assert "y tế" in (t1.active_quest.extra_slots.get("domain", "") or "").lower()

    # Turn 2: Cán bộ nào phụ trách những chỉ tiêu đó
    t2 = router.route_query("Cán bộ nào phụ trách những chỉ tiêu đó ?", session_id=session_id)
    assert t2.active_quest is not None

    # Turn 3: Chuyển đổi chủ đề triệt để: "Thế còn bên mảng giảm nghèo năm 2025 toàn tỉnh đạt bao nhiêu % ?"
    t3 = router.route_query("Thế còn bên mảng giảm nghèo năm 2025 toàn tỉnh đạt bao nhiêu % ?", session_id=session_id)
    assert t3.active_quest is not None
    assert "y tế" not in (t3.active_quest.extra_slots.get("domain", "") or "").lower()
    assert "giảm nghèo" in (t3.active_quest.metric_code or "").lower()
    assert t3.active_quest.temporal_val == "2025"
    assert t3.active_quest.admin_level == 0
