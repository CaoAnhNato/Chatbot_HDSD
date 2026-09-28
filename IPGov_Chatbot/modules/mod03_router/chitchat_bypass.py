"""
IPGov Chatbot - Module 03: Chitchat Fast Bypass Engine
Pre-router rule-based matching: Zero LLM Token, Zero SQL, SLA < 2ms
Căn cứ: Blueprints 02_ROUTER_SPEC, 05_CHITCHAT_FALLBACK, 08_TEST_SUITE_DESIGN
"""

from __future__ import annotations
import re
import time
from typing import Dict, List, Optional, Tuple

from IPGov_Chatbot.schemas.router_dto import (
    ActiveQuestFrameDTO,
    IntentEnum,
    PersonaEnum,
    QuestActionEnum,
    QuestStatusEnum,
    RouteTypeEnum,
    RouterOutputDTO,
)


class ChitchatBypassEngine:
    """
    Động cơ phân luồng xã giao công vụ siêu tốc (In-Memory Regex Matching).
    Nhận diện 5 nhóm chitchat:
    1. GREETING (Chào hỏi: trang trọng, doanh nghiệp, thông thường)
    2. GRATITUDE (Cảm ơn)
    3. FAREWELL (Tạm biệt, kết thúc phiên)
    4. PRAISE (Khen ngợi hiệu năng, độ chính xác)
    5. STATUS_INQUIRY (Thăm hỏi trạng thái hệ thống)
    """

    def __init__(self) -> None:
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        # 1. FAREWELL patterns (Ưu tiên kiểm tra trước vì có thể chứa từ "cảm ơn" kèm "nghỉ thôi")
        self._farewell_patterns = [
            re.compile(r"\b(tạm biệt|tam biet|hẹn gặp lại|hen gap lai|nghỉ thôi|nghi thoi|xong việc rồi|kết thúc phiên)\b", re.IGNORECASE),
            re.compile(r"\b(bye|goodbye|nghi ngoi)\b", re.IGNORECASE),
        ]

        # 2. STATUS_INQUIRY patterns
        self._status_patterns = [
            re.compile(r"\b(hệ thống|dwh|bot|chatbot).*(trực|sẵn sàng|sẵn sàng phục vụ|hoạt động không|online không)\b", re.IGNORECASE),
            re.compile(r"\b(sẵn sàng phục vụ công tác tra cứu không|có trực không)\b", re.IGNORECASE),
        ]

        # 3. PRAISE patterns
        self._praise_patterns = [
            re.compile(r"\b(nhanh và chuẩn|chuẩn đấy|rất chuẩn|rất tốt|chính xác đấy|khớp với thực tế|tuyệt vời|rất hay)\b", re.IGNORECASE),
            re.compile(r"\b(khen|good job|tốt lắm|xịn đấy)\b", re.IGNORECASE),
        ]

        # 4. GRATITUDE patterns
        self._gratitude_patterns = [
            re.compile(r"\b(cảm ơn|cam on|thanks|thank you|cám ơn)\b", re.IGNORECASE),
        ]

        # 5. GREETING patterns
        self._greeting_patterns = [
            re.compile(r"^(kính chào|kinh chao|chào đồng chí|chào bạn|xin chào|xin chao|chào trợ lý|hello|hi\b|alo)", re.IGNORECASE),
            re.compile(r"\b(chào chatbot|chào trợ lý ảo|kính chào)\b", re.IGNORECASE),
        ]

        # Business indicators (Nếu có các từ này thì KHÔNG PHẢI là chitchat đơn thuần, ngoại trừ status check)
        self._business_indicator = re.compile(
            r"\b(bao nhiêu|tăng hay giảm|tỷ lệ|thấp nhất|cao nhất|thế nào|ở đâu|số lượng|kinh phí|giải ngân|huyện nào|xã nào|phòng nào|biểu mẫu nào|select|drop|insert|delete)\b",
            re.IGNORECASE
        )

    def decouple_greeting_and_business(self, prompt: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Phân tách phần chào hỏi (Greeting/Politeness) và nội dung nghiệp vụ (Business Payload).
        Theo nguyên lý Joint Intent Detection & Slot Filling (MixSNIPS, Qin et al., 2020).
        Trả về: (has_greeting, greeting_part, business_payload)
        """
        text = prompt.strip()
        for pat in self._greeting_patterns:
            m = pat.search(text)
            if m:
                greeting_part = m.group(0).strip()
                rest = text[m.end():].lstrip(",.:;?! \t\n")
                if not rest:
                    return True, greeting_part, None

                # Các mẫu câu giới thiệu bản thân thuần xã giao (không có yêu cầu nghiệp vụ cụ thể)
                is_pure_intro = (
                    re.match(r"^(tôi đang chuẩn bị|tôi là đại diện doanh nghiệp|chúc |rất vui |rất hân hạnh|chúc một ngày)", rest, re.IGNORECASE)
                    and "?" not in rest
                    and not any(w in rest.lower() for w in [
                        "tai nạn", "tnld", "tnlđ", "lao động", "khuyến công", "y tế", "giảm nghèo",
                        "kiên cố", "chi ngân sách", "đầu tư công", "null", "rỗng", "zero",
                        "báo cáo này", "chức năng gì", "làm được gì", "biểu mẫu nào đang áp dụng",
                        "đã nộp và duyệt chưa"
                    ])
                )
                if is_pure_intro:
                    return True, greeting_part, None

                # Kiểm tra nếu rest có chứa yêu cầu, câu hỏi, hoặc chỉ tiêu/thực thể nghiệp vụ
                has_biz_content = (
                    "?" in rest
                    or self._business_indicator.search(rest)
                    or re.search(r"\b(cho tôi (xem|xin|hỏi)|cho em (xem|xin|hỏi)|tra giúp|xem giúp|liệt kê|danh sách|thống kê|tổng hợp|so sánh|đối chiếu|kiểm tra|tìm hiểu|giới thiệu|hướng dẫn)\b", rest, re.IGNORECASE)
                    or any(k in rest.lower() for k in [
                        "tai nạn", "lao động", "khuyến công", "y tế", "giảm nghèo",
                        "kiên cố", "chi ngân sách", "đầu tư công", "năm 202", "null", "rỗng", "zero",
                        "chức năng gì", "hệ thống này", "tiện ích gì", "biểu mẫu nào", "đã nộp và duyệt chưa"
                    ])
                )
                if has_biz_content:
                    return True, greeting_part, rest

                return True, greeting_part, None
        return False, None, text

    def is_chitchat(self, prompt: str) -> bool:
        """Kiểm tra nhanh prompt có thuộc luồng chitchat hay không (loại bỏ hoàn toàn bẫy greedy chitchat)."""
        text = prompt.strip()
        if not text:
            return False

        # Onboarding / Capability indicators (Nếu là câu hỏi của cán bộ mới thì chuyển sang Discovery)
        if re.search(r"\b(cán bộ mới|bắt đầu tra cứu|hướng dẫn tra cứu|hướng dẫn sử dụng)\b", text, re.IGNORECASE):
            return False

        # Kiểm tra status check trước
        for pat in self._status_patterns:
            if pat.search(text):
                return True

        for pat in self._farewell_patterns:
            if pat.search(text):
                return True

        for pat in self._praise_patterns:
            if pat.search(text):
                return True

        for pat in self._gratitude_patterns:
            if pat.search(text):
                if "?" in text or any(k in text.lower() for k in [
                    "cho em xin", "cho tôi xin", "cho xin", "tra giúp", "tra giup", "xem những",
                    "danh sách", "danh sach", "báo cáo nào", "đơn vị nào", "phòng ban nào", "xã nào", "huyện nào",
                    "thời hạn", "kết thúc trong tháng"
                ]):
                    continue
                return True

        for pat in self._greeting_patterns:
            if pat.search(text):
                has_g, g_part, biz_payload = self.decouple_greeting_and_business(text)
                if biz_payload:
                    # Compound Intent (Chào hỏi + Nội dung nghiệp vụ): Chuyển tiếp sang Tầng Ngữ nghĩa
                    return False
                return True

        return False

    def evaluate(
        self,
        prompt: str,
        session_id: str = "default_session",
        active_quest: Optional[ActiveQuestFrameDTO] = None,
    ) -> Optional[RouterOutputDTO]:
        """
        Đánh giá câu hỏi qua bộ lọc Chitchat Bypass.
        Trả về RouterOutputDTO nếu khớp, ngược lại trả về None để chuyển cho các router tiếp theo.
        """
        start_time = time.perf_counter()
        text = prompt.strip()

        # Kiểm tra nhanh
        if not self.is_chitchat(text):
            return None

        intent = IntentEnum.GREETING
        quest_action = QuestActionEnum.INIT
        response_text = ""
        action_chips: List[str] = []
        persona = PersonaEnum.CITIZEN
        active_quest_preserved = False
        out_quest = active_quest

        # 1. Kiểm tra FAREWELL
        if any(pat.search(text) for pat in self._farewell_patterns):
            intent = IntentEnum.FAREWELL
            quest_action = QuestActionEnum.TEARDOWN
            out_quest = None  # Giải phóng ActiveQuestFrame trong RAM
            active_quest_preserved = False
            if "nghỉ thôi" in text.lower() or "xong việc" in text.lower():
                response_text = "Rất vui được hỗ trợ đồng chí hoàn thành nhiệm vụ tổng hợp số liệu. Chúc đồng chí nghỉ ngơi vui vẻ!"
                action_chips = [
                    "🔄 Mở phiên tra cứu mới",
                    "📥 Xuất tệp tóm tắt toàn bộ phiên",
                ]
            else:
                response_text = "Tạm biệt đồng chí! Hệ thống trợ lý dữ liệu công vụ luôn sẵn sàng phục vụ khi đồng chí quay lại."
                action_chips = [
                    "🔄 Bắt đầu phiên tra cứu mới",
                    "📊 Xem lại tóm tắt phiên hôm nay",
                ]

        # 2. Kiểm tra STATUS_INQUIRY
        elif any(pat.search(text) for pat in self._status_patterns):
            intent = IntentEnum.STATUS_INQUIRY
            quest_action = QuestActionEnum.INIT
            response_text = "Kính chào đồng chí! Hệ thống kho dữ liệu công vụ tổng hợp đang vận hành ổn định 24/7 và sẵn sàng phục vụ công tác tra cứu, đối soát số liệu."
            action_chips = [
                "💼 Lĩnh vực Lao động & Nội vụ",
                "🏗️ Lĩnh vực Xây dựng",
                "⚡ Lĩnh vực Công thương",
                "🏥 Lĩnh vực Y tế",
            ]
            persona = PersonaEnum.SPECIALIST

        # 3. Kiểm tra GRATITUDE (Nếu có cảm ơn)
        elif any(pat.search(text) for pat in self._gratitude_patterns):
            intent = IntentEnum.GRATITUDE
            quest_action = QuestActionEnum.PRESERVE
            active_quest_preserved = True
            if "chuẩn xác" in text.lower() or "rõ ràng" in text.lower():
                response_text = "Dạ, không có gì ạ! Rất vui vì số liệu đã hỗ trợ đắc lực cho công tác kiểm tra, đối soát của đồng chí."
                action_chips = [
                    "🔍 Kiểm tra độ tươi mới dữ liệu (ETL Freshness)",
                    "🏢 Đối chiếu chéo giữa các đơn vị",
                    "📑 Xem số quyết định phê duyệt báo cáo",
                ]
                persona = PersonaEnum.AUDITOR
            elif "chi tiết cho báo cáo của phòng" in text.lower() or "kịp thời" in text.lower():
                response_text = "Rất hân hạnh được đồng hành và hỗ trợ đồng chí hoàn thiện báo cáo công tác của phòng ban đúng tiến độ."
                action_chips = [
                    "📈 So sánh với kỳ trước (YoY)",
                    "🏢 Xem chi tiết theo đơn vị con",
                    "📥 Xuất bảng số liệu ra Excel",
                ]
                persona = PersonaEnum.SPECIALIST
            else:
                response_text = "Không có chi ạ! Bạn có cần tra cứu thêm thông tin hay so sánh đối chiếu số liệu nào khác không?"
                action_chips = [
                    "📈 So sánh chuỗi thời gian",
                    "📊 Đối chiếu với bình quân tỉnh",
                    "📥 Tải kết quả vừa tra cứu",
                ]
                persona = PersonaEnum.COLLOQUIAL

        # 4. Kiểm tra PRAISE
        elif any(pat.search(text) for pat in self._praise_patterns):
            intent = IntentEnum.PRAISE
            quest_action = QuestActionEnum.PRESERVE
            active_quest_preserved = True
            response_text = "Cảm ơn sự ghi nhận của đồng chí! Hệ thống luôn nỗ lực đảm bảo số liệu chuẩn xác, nhất quán và phục vụ kịp thời công tác điều hành."
            action_chips = [
                "📊 Tra cứu chỉ tiêu kiểm tra tiếp theo",
                "📑 Xuất biên bản đối soát dữ liệu",
                "❓ Xem chi tiết nguồn dữ liệu (Lineage)",
            ]
            persona = PersonaEnum.AUDITOR

        # 5. Kiểm tra GREETING
        elif any(pat.search(text) for pat in self._greeting_patterns):
            intent = IntentEnum.GREETING
            quest_action = QuestActionEnum.INIT
            if "thường trực ubnd tỉnh" in text.lower() or "kính chào" in text.lower():
                response_text = "Kính chào đồng chí Lãnh đạo! Hệ thống trợ lý số liệu công vụ đã sẵn sàng cung cấp các bảng biểu, chỉ số tổng hợp phục vụ phiên họp."
                action_chips = [
                    "📊 Báo cáo KTXH tổng hợp toàn tỉnh 2025-2026",
                    "💰 Tiến độ giải ngân vốn đầu tư công",
                    "⚡ Chỉ đạo điều hành & An toàn vệ sinh lao động",
                ]
                persona = PersonaEnum.EXECUTIVE
            elif "doanh nghiệp" in text.lower():
                response_text = "Kính chào đại diện Doanh nghiệp! Hệ thống hỗ trợ tra cứu các biểu mẫu báo cáo định kỳ và chỉ số phát triển ngành trên địa bàn."
                action_chips = [
                    "📋 Danh mục biểu mẫu báo cáo đang áp dụng",
                    "🏭 Số liệu khuyến công & phát triển công nghiệp",
                    "🛡️ Quy định an toàn vệ sinh lao động",
                ]
                persona = PersonaEnum.CITIZEN
            else:
                response_text = "Xin chào! Tôi là trợ lý ảo khai thác kho dữ liệu công vụ. Tôi có thể giúp gì cho bạn hôm nay?"
                action_chips = [
                    "📊 Tra cứu số liệu năm 2026",
                    "📋 Danh mục 8 lĩnh vực DWH",
                    "❓ Hướng dẫn sử dụng chatbot",
                ]
                persona = PersonaEnum.COLLOQUIAL

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        return RouterOutputDTO(
            session_id=session_id,
            query_sanitized=prompt,
            route=RouteTypeEnum.CHITCHAT_BYPASS,
            routing_track="CHITCHAT_BYPASS",
            intent=intent,
            persona=persona,
            confidence_score=1.0,
            tokens_used=0,
            zero_llm_token=True,
            zero_sql=True,
            sla_max_latency_ms=2.0,
            latency_ms=round(latency_ms, 3),
            active_quest=out_quest,
            active_quest_preserved=active_quest_preserved,
            active_quest_action=quest_action,
            bypass_response=response_text,
            action_chips=action_chips,
            missing_slots=[],
            clarification_options=[],
        )
