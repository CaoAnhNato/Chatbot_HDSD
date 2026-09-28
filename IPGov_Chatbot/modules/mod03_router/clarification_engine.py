"""
IPGov Chatbot - Module 03: Clarification & Slot-Filling Engine
Phát hiện câu hỏi mơ hồ, khuyết thiếu tham số và sinh Interactive Action Chips.
Căn cứ: Blueprints 02_ROUTER_SPEC, 03_SEMANTIC_LAYER, 05_MULTI_AGENT
"""

from __future__ import annotations
import re
from typing import List, Optional, Tuple

from IPGov_Chatbot.schemas.router_dto import (
    ActiveQuestFrameDTO,
    SlotClarificationOption,
    SlotTypeEnum,
)


class ClarificationEngine:
    """
    Động cơ nhận diện 6 loại khe khuyết (H-DFT Missing Slots) và sinh Action Chips:
    1. TEMPORAL (thiếu năm/kỳ)
    2. ADMIN_ENTITY (thiếu đơn vị/địa bàn)
    3. METRIC_CODE (thiếu mã chỉ tiêu)
    4. COMPARISON_TARGET (thiếu kỳ so sánh)
    5. DISAMBIGUATION (thực thể trùng tên/đa nghĩa)
    6. OUT_OF_SCOPE (ngoài kho dữ liệu)
    """

    def __init__(self) -> None:
        # Nhận diện các câu hỏi mơ hồ điển hình thiếu tham số
        self._ambiguous_temporal_queries = [
            (
                re.compile(r"\b(gần đây|mới nhất)\b", re.IGNORECASE),
                ["temporal_period"],
                [
                    SlotClarificationOption(label="Năm 2025 (Chính thức)", slot_key="year", value="2025"),
                    SlotClarificationOption(label="Kế hoạch 2026", slot_key="year", value="2026"),
                    SlotClarificationOption(label="Năm 2024", slot_key="year", value="2024"),
                ]
            ),
            (
                re.compile(r"\b(cho tôi xem|cho xem|tra cứu|thống kê).*(kinh phí khuyến công|tai nạn lao động|trạm y tế|giảm nghèo)\b", re.IGNORECASE),
                ["temporal_year"],
                [
                    SlotClarificationOption(label="Năm 2025 toàn tỉnh", slot_key="temporal_scope", value="2025_toan_tinh"),
                    SlotClarificationOption(label="Năm 2024 toàn tỉnh", slot_key="temporal_scope", value="2024_toan_tinh"),
                    SlotClarificationOption(label="Năm 2026 toàn tỉnh", slot_key="temporal_scope", value="2026_toan_tinh"),
                ]
            ),
            (
                re.compile(r"\b(có những biểu mẫu thu thập dữ liệu nào)\b", re.IGNORECASE),
                ["target_scope"],
                [
                    SlotClarificationOption(label="Phòng Xây dựng", slot_key="scope", value="xay_dung"),
                    SlotClarificationOption(label="Phòng Kinh tế", slot_key="scope", value="kinh_te"),
                    SlotClarificationOption(label="Phòng LĐTBXH", slot_key="scope", value="ldtbxh"),
                ]
            ),
            (
                re.compile(r"\b(báo cáo này của phòng đã nộp và duyệt chưa|đã nộp và duyệt chưa)\b", re.IGNORECASE),
                ["entity_or_time_slot"],
                [
                    SlotClarificationOption(label="Báo cáo Quý 3/2026", slot_key="report_period", value="Q3_2026"),
                    SlotClarificationOption(label="Báo cáo 6 tháng 2026", slot_key="report_period", value="H1_2026"),
                    SlotClarificationOption(label="Báo cáo năm 2025", slot_key="report_period", value="2025"),
                ]
            ),
        ]

    def check_clarification_needed(
        self,
        prompt: str,
        active_quest: Optional[ActiveQuestFrameDTO] = None
    ) -> Tuple[bool, List[str], List[SlotClarificationOption], List[str]]:
        """
        Kiểm tra xem câu hỏi có cần hỏi làm rõ (Clarification) hay không.
        Trả về: (needs_clarification, missing_slots, clarification_options, action_chips_labels)
        """
        text = prompt.strip()

        # Kiểm tra các mẫu mơ hồ điển hình
        for pat, missing, options in self._ambiguous_temporal_queries:
            if pat.search(text):
                # Ngoại trừ khi người dùng đã chỉ định năm rõ ràng (ví dụ: "Năm 2025 gần đây" hay "Năm 2025 Phòng Xây dựng")
                if "202" in text and "biểu mẫu" not in text and "báo cáo này" not in text:
                    continue
                labels = [opt.label for opt in options]
                return True, missing, options, labels

        return False, [], [], []
