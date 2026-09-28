"""
IPGov Chatbot - Module 03: Hierarchical Dialogue Frame Tracker (H-DFT)
2-Tier Dialogue State Machine:
  - Tier 1: Active Quest Frame in RAM (Anaphora resolution, Hierarchical Drill-down, Slot Repair, Topic Shift)
  - Tier 2: Session Episodic Memory (temp_memory, default year, frequent entities, TTL)
Căn cứ: Blueprints 00_OVERVIEW, 02_ROUTER_SPEC, 05_MULTI_AGENT, 08_TEST_SUITE_DESIGN
"""

from __future__ import annotations
import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

from IPGov_Chatbot.schemas.router_dto import (
    ActiveQuestFrameDTO,
    QuestActionEnum,
    QuestStatusEnum,
    SessionEpisodicMemoryDTO,
    SlotTypeEnum,
)
from IPGov_Chatbot.modules.mod03_router.duckdb_fuzzy_strategy import DuckDBFuzzyStrategy


def normalize_entity_name(name: str) -> str:
    """Chuẩn hóa viết hoa danh từ riêng cơ quan/đơn vị hành chính công."""
    mapping = {
        "phòng xây dựng": "Phòng Xây dựng",
        "sở xây dựng": "Sở Xây dựng",
        "phòng y tế": "Phòng Y tế",
        "sở y tế": "Sở Y tế",
        "sở công thương": "Sở Công thương",
        "phòng lđtbxh": "Phòng LĐTBXH",
        "phòng tài chính": "Phòng Tài chính",
        "phòng kinh tế": "Phòng Kinh tế",
        "đam rông": "Huyện Đam Rông",
        "lâm hà": "Huyện Lâm Hà",
        "đà lạt": "TP. Đà Lạt",
        "bảo lộc": "TP. Bảo Lộc",
    }
    low = name.lower().strip()
    return mapping.get(low, name.title())


class HDFTDialogueTracker:
    """
    Bộ theo dõi trạng thái đối thoại phân cấp H-DFT (Hierarchical Dialogue Frame Tracker).
    Giải quyết triệt để:
    1. Anaphora / Co-reference Resolution ("Số lượng này", "huyện đó", "báo cáo này")
    2. Hierarchical Drill-Down (Tỉnh Level 0 -> Huyện Level 1 -> Phòng/Xã Level 2)
    3. Topic Shift (Xóa sạch bộ lọc cũ, cô lập ngữ cảnh khi chuyển chủ đề)
    4. Slot Repair (Đính chính giá trị slot mà không phá vỡ toàn bộ quest)
    5. Session Episodic Memory (Ghi nhớ thực thể thường hỏi, năm ngầm định 2025)
    """

    def __init__(self, session_manager: Optional[Any] = None) -> None:
        self.session_manager = session_manager
        # In-Memory Session Storage dự phòng: session_id -> (ActiveQuestFrameDTO, SessionEpisodicMemoryDTO)
        self._sessions: Dict[str, Tuple[Optional[ActiveQuestFrameDTO], SessionEpisodicMemoryDTO]] = {}
        self.fuzzy_strategy = DuckDBFuzzyStrategy()
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        # Nhận diện mốc thời gian
        self._year_pat = re.compile(r"\b(202[4-6])\b")
        self._quarter_pat = re.compile(r"\b(quý\s*[1-4]|q[1-4]|q[1-4]/202[4-6])\b", re.IGNORECASE)
        self._recent_pat = re.compile(r"\b(gần đây|vừa qua|mới nhất|hôm nay)\b", re.IGNORECASE)

        # Nhận diện cấp hành chính và địa bàn
        self._provincial_pat = re.compile(r"\b(toàn tỉnh|toàn tp|cấp tỉnh|ubnd tỉnh)\b", re.IGNORECASE)
        self._district_kw_pat = re.compile(r"\b(huyện nào|thành phố nào|quận nào|huyện đó|quận đó)\b", re.IGNORECASE)
        self._district_names_pat = re.compile(
            r"\b(đam rông|lâm hà|bảo lộc|đà lạt|đức trọng|di linh|đơn dương|trảng bom|long thành|quận 1|bình thạnh)\b",
            re.IGNORECASE
        )
        self._dept_names_pat = re.compile(
            r"\b(phòng xây dựng|sở xây dựng|phòng y tế|sở y tế|phòng lđtbxh|sở công thương|phòng tài chính|phòng kinh tế|sở nông nghiệp|văn phòng ubnd)\b",
            re.IGNORECASE
        )

        # Nhận diện Anaphora (Đại từ thay thế)
        self._anaphora_metric_pat = re.compile(
            r"\b(số lượng này|chỉ tiêu này|con số này|chỉ số này|số này|những chỉ tiêu đó|chỉ tiêu đó)\b",
            re.IGNORECASE
        )
        self._anaphora_entity_pat = re.compile(r"\b(huyện đó|đơn vị đó|ở đó|nơi đó|tỉnh đó)\b", re.IGNORECASE)
        self._anaphora_report_pat = re.compile(r"\b(báo cáo này|biểu mẫu này|hồ sơ này)\b", re.IGNORECASE)

        # Nhận diện Topic Shift (Đổi chủ đề bất ngờ)
        self._topic_shift_pat = re.compile(
            r"\b(chuyển sang|nói về|qua mảng|đổi sang|chuyển qua)\s+([^?]+)",
            re.IGNORECASE
        )

        # Nhận diện Slot Repair (Đính chính)
        self._slot_repair_pat = re.compile(
            r"\b(không|không phải|nhầm rồi|ý tôi là|tôi muốn xem ở|tôi hỏi ở)\s+([^\.,\?!]+)",
            re.IGNORECASE
        )

        # Nhận diện Chỉ tiêu nghiệp vụ (Metric code keywords)
        self._metrics_map = [
            ("tai nạn lao động", re.compile(r"\b(tai nạn lao động|tnlđ|an toàn lao động)\b", re.IGNORECASE)),
            ("khuyến công", re.compile(r"\b(khuyến công|giải ngân kinh phí khuyến công|kinh phí khuyến công)\b", re.IGNORECASE)),
            ("trạm y tế đạt chuẩn", re.compile(r"\b(trạm y tế|đạt chuẩn quốc gia về y tế|y tế xã đạt chuẩn)\b", re.IGNORECASE)),
            ("giảm nghèo", re.compile(r"\b(giảm nghèo|hộ nghèo|tỷ lệ hộ nghèo)\b", re.IGNORECASE)),
            ("kiên cố hóa", re.compile(r"\b(kiên cố hóa|phòng học kiên cố)\b", re.IGNORECASE)),
            ("biểu mẫu thu thập dữ liệu", re.compile(r"\b(biểu mẫu|thu thập dữ liệu|biểu mẫu báo cáo)\b", re.IGNORECASE)),
            ("dị thường y tế", re.compile(r"\b(để trống hoặc bằng 0|bất thường|chỉ tiêu nào của lĩnh vực y tế.*bất thường)\b", re.IGNORECASE)),
        ]

    def get_or_create_session(self, session_id: str) -> Tuple[Optional[ActiveQuestFrameDTO], SessionEpisodicMemoryDTO]:
        """Lấy hoặc tạo mới cấu trúc 2 tầng cho phiên làm việc (ưu tiên Redis, fallback in-memory)."""
        if self.session_manager:
            try:
                active_quest = self.session_manager.get_active_quest(session_id)
                memory = self.session_manager.get_temp_memory(session_id)
                if memory is None:
                    memory = SessionEpisodicMemoryDTO(session_id=session_id, default_temporal_window="2025")
                    self.session_manager.save_temp_memory(session_id, memory)
                return active_quest, memory
            except Exception as e:
                logger.warning(f"Error accessing Redis in get_or_create_session: {e}")

        if session_id not in self._sessions:
            memory = SessionEpisodicMemoryDTO(session_id=session_id, default_temporal_window="2025")
            self._sessions[session_id] = (None, memory)
        return self._sessions[session_id]

    def set_active_quest(self, session_id: str, quest: Optional[ActiveQuestFrameDTO]) -> None:
        """Cập nhật hoặc xóa ActiveQuestFrame (đồng bộ cả Redis và RAM)."""
        if self.session_manager:
            try:
                if quest is None:
                    self.session_manager.reset_active_quest_and_archive(session_id)
                else:
                    self.session_manager.save_active_quest(session_id, quest)
            except Exception as e:
                logger.warning(f"Error saving to Redis in set_active_quest: {e}")

        # Đồng bộ in-memory
        curr, memory = self.get_or_create_session(session_id)
        if quest is None and curr is not None:
            memory.committed_quest_history.append(curr.quest_id)
            if self.session_manager:
                try:
                    self.session_manager.save_temp_memory(session_id, memory)
                except Exception:
                    pass
        self._sessions[session_id] = (quest, memory)

    def update_state(
        self,
        prompt: str,
        session_id: str = "default_session",
        override_topic_shift: Optional[bool] = None,
    ) -> Tuple[ActiveQuestFrameDTO, SessionEpisodicMemoryDTO, bool]:
        """
        Cập nhật trạng thái đàm thoại H-DFT dựa trên prompt mới và state hiện hành.
        Hỗ trợ override_topic_shift từ LLM Structured Output.
        Trả về: (active_quest, temp_memory, is_topic_shift)
        """
        text = prompt.strip()
        curr_quest, memory = self.get_or_create_session(session_id)
        is_topic_shift = False

        # 1. KIỂM TRA TOPIC SHIFT (Đổi đề tài)
        shift_match = self._topic_shift_pat.search(text)
        is_anaphora_or_drilldown = bool(
            self._anaphora_metric_pat.search(text)
            or self._anaphora_entity_pat.search(text)
            or self._anaphora_report_pat.search(text)
            or "huyện nào" in text.lower()
            or "đơn vị nào" in text.lower()
            or "tăng hay giảm" in text.lower()
            or "so với" in text.lower()
            or "thấp nhất" in text.lower()
            or "cao nhất" in text.lower()
        )
        if is_anaphora_or_drilldown:
            override_topic_shift = False

        if (shift_match or override_topic_shift) and not is_anaphora_or_drilldown:
            is_topic_shift = True
            if self.session_manager:
                try:
                    self.session_manager.reset_active_quest_and_archive(session_id)
                except Exception:
                    pass
            # Tạo frame hoàn toàn mới (Purge & Isolate Context)
            curr_quest = ActiveQuestFrameDTO(
                quest_id=f"quest_{uuid.uuid4().hex[:8]}",
                status=QuestStatusEnum.PENDING_SLOTS,
                turn_count=1,
            )

        # 2. KHỞI TẠO FRAME NẾU CHƯA CÓ
        if curr_quest is None:
            curr_quest = ActiveQuestFrameDTO(
                quest_id=f"quest_{uuid.uuid4().hex[:8]}",
                status=QuestStatusEnum.PENDING_SLOTS,
                turn_count=1,
            )
        else:
            curr_quest.turn_count += 1
            curr_quest.last_updated_turn = curr_quest.turn_count

        # 3. XỬ LÝ SLOT REPAIR (Đính chính giá trị)
        repair_match = self._slot_repair_pat.search(text)
        if repair_match:
            repair_target = repair_match.group(2)
            # Kiểm tra xem đính chính huyện/địa bàn nào
            dist_match = self._district_names_pat.search(repair_target)
            if dist_match:
                curr_quest.admin_entity = normalize_entity_name(dist_match.group(0))
                curr_quest.admin_level = 1

        # 4. TRÍCH XUẤT HOẶC KẾ THỪA MỐC THỜI GIAN (Temporal Slot)
        year_match = self._year_pat.search(text)
        if year_match:
            # Nếu là câu so sánh "So với năm 2024 thì sao?" và đã có temporal_val
            if "so với" in text.lower() or "tăng hay giảm" in text.lower():
                curr_quest.comparison_year = year_match.group(1)
            else:
                curr_quest.temporal_val = year_match.group(1)
        elif self._recent_pat.search(text):
            # "gần đây" giải quyết về năm đã chốt duyệt 2025
            curr_quest.temporal_val = "2025"
        elif curr_quest.temporal_val is None:
            # Fallback về năm mặc định trong Episodic Memory
            curr_quest.temporal_val = memory.default_temporal_window

        # Nếu có từ khóa so sánh YoY mà chưa có comparison_year
        if ("tăng hay giảm" in text.lower() or "so với năm trước" in text.lower() or "yoy" in text.lower()) and not curr_quest.comparison_year:
            if curr_quest.temporal_val == "2025":
                curr_quest.comparison_year = "2024"
            elif curr_quest.temporal_val == "2026":
                curr_quest.comparison_year = "2025"

        # 5. TRÍCH XUẤT HOẶC KẾ THỪA ĐỊA BÀN / ĐƠN VỊ (Admin Entity Slot)
        if self._provincial_pat.search(text):
            curr_quest.admin_entity = "Toàn tỉnh"
            curr_quest.admin_level = 0
        else:
            dist_match = self._district_names_pat.search(text)
            if dist_match:
                curr_quest.admin_entity = normalize_entity_name(dist_match.group(0))
                curr_quest.admin_level = 1
                if curr_quest.admin_entity not in memory.frequent_entities:
                    memory.frequent_entities.append(curr_quest.admin_entity)

            dept_match = self._dept_names_pat.search(text)
            if dept_match:
                curr_quest.admin_entity = normalize_entity_name(dept_match.group(0))
                curr_quest.admin_level = 2

        # Anaphora: "ở huyện đó" / "cụ thể huyện đó" -> kế thừa admin_entity
        if self._anaphora_entity_pat.search(text) and curr_quest.admin_entity:
            # Giữ nguyên admin_entity hiện thời
            pass

        # Drill-down: "Ở những đơn vị nào xảy ra nhiều nhất ?" / "Huyện nào..."
        if "ở những đơn vị nào" in text.lower() or "xảy ra nhiều nhất" in text.lower():
            curr_quest.admin_level = 2  # Hạ xuống đơn vị cơ sở
        elif self._district_kw_pat.search(text):
            curr_quest.admin_level = 1  # Cấp Huyện

        # 6. TRÍCH XUẤT HOẶC KẾ THỪA CHỈ TIÊU (Metric Code Slot)
        matched_metric = None
        # Ưu tiên tra cứu qua DuckDB In-Memory Catalog + RapidFuzz
        fuzzy_metric = self.fuzzy_strategy.match_metric(text)
        if fuzzy_metric:
            matched_metric = fuzzy_metric[0]
            if fuzzy_metric[1]:
                curr_quest.extra_slots["domain"] = fuzzy_metric[1]
        else:
            for name, pat in self._metrics_map:
                if pat.search(text):
                    matched_metric = name
                    break

        if matched_metric:
            curr_quest.metric_code = matched_metric
            if matched_metric == "dị thường y tế":
                curr_quest.extra_slots["domain"] = "Y tế"
                curr_quest.extra_slots["filter_null_zero"] = True
        elif is_anaphora_or_drilldown and curr_quest.metric_code:
            # Kế thừa/giữ nguyên metric_code từ lượt trước
            pass
        elif self._anaphora_metric_pat.search(text):
            # Kế thừa metric_code từ lượt trước
            pass

        # Bổ sung trích xuất địa bàn qua DuckDB Catalog nếu regex chưa bắt được
        if not curr_quest.admin_entity or curr_quest.admin_entity == "Toàn tỉnh":
            fuzzy_ent = self.fuzzy_strategy.match_entity(text)
            if fuzzy_ent and fuzzy_ent[0] != "Toàn tỉnh":
                curr_quest.admin_entity = fuzzy_ent[0]
                curr_quest.admin_level = fuzzy_ent[1]
                if curr_quest.admin_entity not in memory.frequent_entities:
                    memory.frequent_entities.append(curr_quest.admin_entity)

        # Lưu lại quest và episodic memory vào session
        self.set_active_quest(session_id, curr_quest)
        if self.session_manager:
            try:
                self.session_manager.save_temp_memory(session_id, memory)
            except Exception as e:
                logger.warning(f"Error saving temp_memory to Redis: {e}")
        return curr_quest, memory, is_topic_shift

