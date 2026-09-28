"""
Unit Tests for RedisSessionManager
Kiểm tra toàn diện các chức năng quản lý phiên trên Redis 7.4.11:
1. Kết nối & Ping
2. Đọc/ghi ActiveQuestFrameDTO
3. Đọc/ghi SessionEpisodicMemoryDTO
4. Sliding Window Message Trim (tối đa 6 messages)
5. Semantic Decision Cache (Lượt 1)
6. Lưu trữ Lịch sử Quest và Reset Frame
Căn cứ: module_03_session_memory_redis_plan.md, Blueprints 00, 05
"""

import time
import pytest

from IPGov_Chatbot.modules.mod03_router.redis_session_manager import RedisSessionManager
from IPGov_Chatbot.schemas.router_dto import (
    ActiveQuestFrameDTO,
    QuestStatusEnum,
    SessionEpisodicMemoryDTO,
)


@pytest.fixture
def session_mgr():
    mgr = RedisSessionManager()
    if not mgr.ping():
        pytest.skip("Redis server không khả dụng trên localhost:6379")
    return mgr


def test_redis_connection_ping(session_mgr):
    """Xác minh kết nối Redis hoạt động thành công."""
    assert session_mgr.ping() is True


def test_active_quest_crud(session_mgr):
    """Xác minh các thao tác Lưu/Đọc/Xóa ActiveQuestFrameDTO trên Redis."""
    sess_id = f"test_quest_crud_{int(time.time() * 1000)}"
    try:
        # 1. Ban đầu chưa có
        assert session_mgr.get_active_quest(sess_id) is None

        # 2. Tạo và lưu frame mới
        quest = ActiveQuestFrameDTO(
            quest_id="q_101",
            intent="dwh_query",
            status=QuestStatusEnum.COMMITTED,
            metric_code="khuyến công",
            temporal_val="2025",
            admin_entity="Huyện Đam Rông",
            admin_level="district",
            turn_count=1,
        )
        session_mgr.save_active_quest(sess_id, quest)

        # 3. Đọc lại từ Redis và so sánh
        loaded = session_mgr.get_active_quest(sess_id)
        assert loaded is not None
        assert loaded.quest_id == "q_101"
        assert loaded.metric_code == "khuyến công"
        assert loaded.temporal_val == "2025"
        assert loaded.admin_entity == "Huyện Đam Rông"
        assert loaded.admin_level == 1

        # 4. Xóa frame
        session_mgr.save_active_quest(sess_id, None)
        assert session_mgr.get_active_quest(sess_id) is None
    finally:
        session_mgr.clear_session(sess_id)


def test_temp_memory_crud(session_mgr):
    """Xác minh đọc và lưu hồ sơ ngữ cảnh phiên SessionEpisodicMemoryDTO."""
    sess_id = f"test_mem_crud_{int(time.time() * 1000)}"
    try:
        mem = session_mgr.get_temp_memory(sess_id)
        assert mem.session_id == sess_id
        assert mem.default_temporal_window == "2025"

        mem.frequent_entities.append("Sở Xây dựng")
        mem.committed_quest_history.append("q_999")
        session_mgr.save_temp_memory(sess_id, mem)

        reloaded = session_mgr.get_temp_memory(sess_id)
        assert "Sở Xây dựng" in reloaded.frequent_entities
        assert "q_999" in reloaded.committed_quest_history
    finally:
        session_mgr.clear_session(sess_id)


def test_sliding_window_trim(session_mgr):
    """Xác minh cơ chế Sliding Window chỉ giữ lại đúng 6 tin nhắn (3 turns)."""
    sess_id = f"test_sliding_{int(time.time() * 1000)}"
    try:
        # Thêm 10 tin nhắn liên tiếp (5 turns)
        for i in range(1, 11):
            role = "user" if i % 2 != 0 else "assistant"
            session_mgr.append_message(sess_id, role, f"Message {i}")

        messages = session_mgr.get_recent_messages(sess_id)
        # Giới hạn max_turns = 3 -> 6 messages
        assert len(messages) == 6
        assert messages[0]["content"] == "Message 5"
        assert messages[-1]["content"] == "Message 10"
    finally:
        session_mgr.clear_session(sess_id)


def test_decision_cache(session_mgr):
    """Xác minh Semantic Decision Cache cho Lượt 1 trong Redis."""
    unique_suffix = int(time.time() * 1000)
    prompt = f"  Thống kê TAI NẠN LAO ĐỘNG   năm 2025 tại Lâm Đồng ({unique_suffix})?  "
    cached_payload = {
        "intent": "TEMPLATE_FAST_TRACK",
        "route": "TEMPLATE_FAST_TRACK",
        "metric_code": "tai nạn lao động",
        "start_year": 2025,
    }

    # Ban đầu chưa cache
    assert session_mgr.get_decision_cache(prompt) is None

    # Lưu cache
    session_mgr.set_decision_cache(prompt, cached_payload)

    # Đọc lại với các biến thể khoảng trắng/viết hoa
    variant_prompt = f"thống kê tai nạn lao động năm 2025 tại lâm đồng ({unique_suffix})?"
    loaded = session_mgr.get_decision_cache(variant_prompt)
    assert loaded is not None
    assert loaded["intent"] == "TEMPLATE_FAST_TRACK"
    assert loaded["start_year"] == 2025


def test_reset_and_archive_quest(session_mgr):
    """Xác minh việc lưu quest ID vào lịch sử và reset active quest khi chuyển chủ đề."""
    sess_id = f"test_archive_{int(time.time() * 1000)}"
    try:
        quest = ActiveQuestFrameDTO(
            quest_id="quest_completed_1",
            intent="dwh_query",
            status=QuestStatusEnum.RESOLVED,
            metric_code="khuyến công",
        )
        session_mgr.save_active_quest(sess_id, quest)

        # Lưu trữ và reset
        session_mgr.reset_active_quest_and_archive(sess_id)

        # Active quest phải bị xóa
        assert session_mgr.get_active_quest(sess_id) is None

        # Temp memory phải ghi nhận ID quest
        mem = session_mgr.get_temp_memory(sess_id)
        assert "quest_completed_1" in mem.committed_quest_history
    finally:
        session_mgr.clear_session(sess_id)
