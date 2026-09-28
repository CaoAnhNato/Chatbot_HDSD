"""
CI Automated Test for Module 03: H-DFT Multi-Turn State Durability & Slot Repair
Căn cứ: Blueprints 02, 05, 07, 08
"""

import pytest

from IPGov_Chatbot.schemas.router_dto import (
    IntentEnum,
    QuestStatusEnum,
    RouteTypeEnum,
)
from IPGov_Chatbot.modules.mod03_router.intent_router import IntentRouter
from IPGov_Chatbot.modules.mod03_router.hdft_dialogue_tracker import HDFTDialogueTracker


@pytest.fixture
def router():
    return IntentRouter()


@pytest.fixture
def tracker():
    return HDFTDialogueTracker()


def test_slot_repair_mechanism(router):
    """
    Kiểm thử cơ chế Slot Repair:
    Turn 1: Người dùng hỏi ở Huyện A
    Turn 2: Người dùng đính chính 'Không, tôi muốn hỏi ở Huyện B'
    -> Frame phải ghi đè Huyện B và xóa bỏ các dẫn xuất cũ của Huyện A.
    """
    session_id = "sess_slot_repair"

    # Turn 1
    t1 = router.route_query("Tỷ lệ trạm y tế đạt chuẩn năm 2025 ở Huyện Đam Rông?", session_id=session_id)
    assert t1.active_quest is not None
    assert "Đam Rông" in (t1.active_quest.admin_entity or "")

    # Turn 2: Slot Repair
    t2 = router.route_query("Không, tôi muốn xem ở Huyện Lâm Hà cơ", session_id=session_id)
    assert t2.active_quest is not None
    assert "Lâm Hà" in (t2.active_quest.admin_entity or "")
    assert "Đam Rông" not in (t2.active_quest.admin_entity or "")
    # Chỉ tiêu và năm vẫn được bảo tồn
    assert t2.active_quest.temporal_val == "2025"
    assert "trạm y tế" in (t2.active_quest.metric_code or "").lower()


def test_session_memory_decay_and_defaults(router):
    """
    Kiểm thử Tầng 2: Session Episodic Memory cung cấp năm mặc định '2025' khi người dùng không nói rõ.
    """
    session_id = "sess_defaults"

    res = router.route_query("Tỷ lệ giải ngân vốn đầu tư công toàn tỉnh?", session_id=session_id)
    assert res.active_quest is not None
    # Nếu không nhắc đến năm, hệ thống tự động fallback về năm 2025 từ Episodic Memory
    assert res.active_quest.temporal_val == "2025"
    assert res.active_quest.admin_level == 0


def test_interleaved_chitchat_and_quest_preservation(router):
    """
    Kiểm thử chitchat xen ngang không làm mất Quest đang thực hiện dở:
    Turn 1: Hỏi số liệu
    Turn 2: Cảm ơn nhé! -> PRESERVE Quest
    Turn 3: So sánh với năm trước -> Vẫn kế thừa đúng chỉ tiêu của Turn 1.
    """
    session_id = "sess_interleaved"

    # Turn 1: Tra cứu chỉ tiêu
    t1 = router.route_query("Số vụ tai nạn lao động năm 2025?", session_id=session_id)
    assert t1.active_quest is not None
    metric = t1.active_quest.metric_code

    # Turn 2: Cảm ơn xen ngang
    t2 = router.route_query("Cảm ơn trợ lý đã cung cấp số liệu kịp thời và chi tiết cho báo cáo của phòng.", session_id=session_id)
    assert t2.route == RouteTypeEnum.CHITCHAT_BYPASS
    assert t2.active_quest_preserved is True
    assert t2.active_quest is not None
    assert t2.active_quest.metric_code == metric

    # Turn 3: Tiếp tục hỏi
    t3 = router.route_query("So với năm 2024 thì sao ?", session_id=session_id)
    assert t3.active_quest is not None
    assert t3.active_quest.metric_code == metric
    assert t3.active_quest.comparison_year == "2024"
