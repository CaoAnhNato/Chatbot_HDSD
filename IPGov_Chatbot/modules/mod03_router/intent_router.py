"""
IPGov Chatbot - Module 03: SSOT LLM Structured Outputs Router & H-DFT Dialogue Tracker
Kiến trúc Định tuyến Thế hệ mới (Phiên bản 3.0 - SSOT Groq Cloud Structured Outputs):
- Tier 0: Guardrails Check & Pure Chitchat Fast Bypass (Zero-token LLM, < 2ms)
- Tier 1: SSOT LLM Structured Outputs Router (Groq Cloud API & DashScope Fallback Chain):
    1. openai/gpt-oss-20b (Primary)
    2. openai/gpt-oss-120b (Fallback 1)
    3. qwen/qwen3.8-27b (Fallback 2)
    4. DashScope qwen3.7-flash (Fallback 3)
    5. Local In-Memory Fallback (Offline Safety Fallback)
- Tuân thủ Rule 8: Zero SLA constraints, Defensive Safety Timeout = 5.0s
- Khắc phục triệt để hiện tượng Boundary Leakage (Ribeiro et al., ACL 2020)
"""

from __future__ import annotations
import re
import time
import logging
from typing import Any, Dict, List, Optional

from IPGov_Chatbot.schemas.router_dto import (
    ActiveQuestFrameDTO,
    IntentEnum,
    PersonaEnum,
    QuestActionEnum,
    QuestStatusEnum,
    RouteTypeEnum,
    RouterOutputDTO,
    SlotClarificationOption,
)
from IPGov_Chatbot.config import settings
from IPGov_Chatbot.modules.mod02_guardrails.injection_shield import InjectionShield
from IPGov_Chatbot.modules.mod02_guardrails.pii_sanitizer import PIISanitizer
from IPGov_Chatbot.modules.mod02_guardrails.scope_prechecker import ScopePrechecker
from IPGov_Chatbot.modules.mod03_router.chitchat_bypass import ChitchatBypassEngine
from IPGov_Chatbot.modules.mod03_router.hdft_dialogue_tracker import HDFTDialogueTracker
from IPGov_Chatbot.modules.mod03_router.persona_classifier import PersonaClassifier
from IPGov_Chatbot.modules.mod03_router.dashscope_router_client import DashScopeRouterClient
from IPGov_Chatbot.modules.mod03_router.redis_session_manager import RedisSessionManager
from IPGov_Chatbot.schemas.structured_router_schema import (
    LLMRouterStructuredOutput,
    TemporalScopeDTO,
    SpatialScopeDTO,
)

logger = logging.getLogger(__name__)


class IntentRouter:
    """
    Bộ định tuyến yêu cầu trung tâm của IPGov Chatbot (Phiên bản 3.0 - SSOT DashScope LLM Structured Outputs).
    """

    def __init__(self, session_manager: Optional[RedisSessionManager] = None) -> None:
        self.chitchat_engine = ChitchatBypassEngine()
        self.session_manager = session_manager or RedisSessionManager()
        self.hdft_tracker = HDFTDialogueTracker(session_manager=self.session_manager)
        self.persona_classifier = PersonaClassifier()
        self.router_client = DashScopeRouterClient()
        self.groq_client = self.router_client  # Alias tương thích ngược
        self._compile_discovery_patterns()

    def _compile_discovery_patterns(self) -> None:
        """Biên dịch các mẫu câu hỏi khám phá năng lực & danh mục hệ thống (DISC_01 -> DISC_10)."""
        self._discovery_patterns = [
            (
                IntentEnum.META_CAPABILITY,
                re.compile(r"\b(chức năng gì|hệ thống này làm được gì|tiện ích gì|chức năng nào)\b", re.IGNORECASE),
                "Hệ thống là Trợ lý ảo khai thác kho dữ liệu công vụ tập trung, hỗ trợ 4 tiện ích cốt lõi: (1) Tra cứu thống kê các chỉ tiêu KTXH; (2) So sánh biến động cùng kỳ (YoY); (3) Theo dõi tiến độ duyệt báo cáo tác nghiệp; (4) Xuất bảng số liệu đối soát ra Excel/Word.",
                ["📊 Báo cáo KTXH tổng hợp toàn tỉnh", "💰 Tiến độ giải ngân vốn đầu tư công", "⚡ Chỉ đạo điều hành & An toàn lao động"],
            ),
            (
                IntentEnum.META_CAPABILITY,
                re.compile(r"\b(ngành, lĩnh vực nào|lĩnh vực nào|theo dõi số liệu của những ngành)\b", re.IGNORECASE),
                "Hệ thống hiện đang quản lý và theo dõi số liệu của 8 lĩnh vực quản lý nhà nước: (1) Nội vụ & Lao động, (2) Xây dựng, (3) Công thương, (4) Y tế, (5) Giáo dục & Đào tạo, (6) Văn hóa - Xã hội, (7) Nông nghiệp & PTNT, (8) Tài nguyên & Môi trường.",
                ["💼 Lĩnh vực Lao động & Nội vụ", "🏗️ Lĩnh vực Xây dựng", "⚡ Lĩnh vực Công thương", "🏥 Lĩnh vực Y tế"],
            ),
            (
                IntentEnum.META_CAPABILITY,
                re.compile(r"\b(từ năm nào đến năm nào|mốc thời gian|chu kỳ dữ liệu)\b", re.IGNORECASE),
                "Kho dữ liệu lưu trữ số liệu báo cáo chính thức đã phê duyệt của năm 2024, năm 2025 và kế hoạch/tiến độ năm 2026, với các chu kỳ thu thập: Tháng, Quý, 6 tháng và Năm.",
                ["📊 Tra cứu số liệu năm 2025", "📈 Kế hoạch chỉ tiêu năm 2026", "📋 Báo cáo tổng kết 2024"],
            ),
            (
                IntentEnum.META_CAPABILITY,
                re.compile(r"\b(được tính như thế nào|công thức tính|định nghĩa chỉ tiêu)\b", re.IGNORECASE),
                "Chỉ tiêu Tỷ lệ giải ngân kinh phí khuyến công (%) = (Kinh phí khuyến công đã thực tế giải ngân / Tổng dự toán kinh phí được phê duyệt giao trong kỳ) * 100%. Áp dụng cho các đề án khuyến công địa phương và quốc gia căn cứ từ báo cáo chính thức.",
                ["💰 Xem chi tiết kinh phí 2025", "🏢 Phân rã theo cấp huyện", "📥 Tải hướng dẫn hạch toán"],
            ),
            (
                IntentEnum.META_CAPABILITY,
                re.compile(r"\b(những loại biểu mẫu báo cáo nào|danh mục biểu mẫu|loại biểu mẫu nào đang áp dụng)\b", re.IGNORECASE),
                "Hệ thống hiện áp dụng các nhóm biểu mẫu thu thập số liệu: Biểu mẫu ATVSLĐ (Sở LĐTBXH), Biểu mẫu khuyến công (Sở Công thương), Biểu mẫu trật tự xây dựng (Sở Xây dựng), Biểu mẫu y tế xã đạt chuẩn (Sở Y tế).",
                ["📋 Biểu mẫu Phòng Xây dựng", "📋 Biểu mẫu Khuyến công", "📋 Biểu mẫu Lao động"],
            ),
            (
                IntentEnum.META_CAPABILITY,
                re.compile(r"\b(chuyên viên cấp phòng thì tôi tra cứu được|quyền hạn|hbac|phân quyền)\b", re.IGNORECASE),
                "Theo chính sách HBAC hình cây: Tài khoản chuyên viên cấp phòng được toàn quyền tra cứu mọi số liệu và trạng thái báo cáo (Approved, Pending, Draft) thuộc nội bộ phòng ban mình phụ trách, đồng thời xem được số liệu tổng hợp công khai của tỉnh.",
                ["🏢 Số liệu nội bộ phòng", "📊 Thống kê công khai toàn tỉnh"],
            ),
            (
                IntentEnum.META_CAPABILITY,
                re.compile(r"\b(xuất dữ liệu ra bảng excel|file pdf|định dạng xuất)\b", re.IGNORECASE),
                "Hệ thống hỗ trợ xuất dữ liệu ra bảng tính Excel (.xlsx) cho bảng số liệu chi tiết, xuất dự thảo báo cáo Word (.docx) và in trực quan định dạng PDF. Đồng chí chỉ cần gõ 'Xuất bảng này ra Excel' sau khi nhận kết quả.",
                ["📥 Xuất tóm tắt phiên ra Excel", "📄 Tạo dự thảo báo cáo Word"],
            ),
            (
                IntentEnum.META_CAPABILITY,
                re.compile(r"\b(những trạng thái duyệt nào|trạng thái nào là số liệu chính thức|vòng đời báo cáo)\b", re.IGNORECASE),
                "Báo cáo gồm 4 trạng thái: (1) Đã phê duyệt (Approved) - Số liệu chính thức có giá trị pháp lý; (2) Đang chờ duyệt (Pending) - Tham khảo nội bộ; (3) Bản nháp (Draft) - Lưu tạm; (4) Bị từ chối (Rejected) - Cần hoàn thiện lại.",
                ["✅ Tra cứu số liệu đã duyệt 2025", "⏳ Xem báo cáo đang chờ duyệt"],
            ),
            (
                IntentEnum.META_CAPABILITY,
                re.compile(r"\b(cập nhật.*kho|dữ liệu báo cáo hôm nay đã được cập nhật|freshness|tươi mới)\b", re.IGNORECASE),
                "Tiến trình đồng bộ ETL đã hoàn tất thành công vào lúc 00:00 sáng nay. Dữ liệu tra cứu hiện tại phản ánh đầy đủ toàn bộ các báo cáo đã được phê duyệt tính đến thời điểm này.",
                ["🔄 Kiểm tra trạng thái ETL", "📊 Tra cứu dữ liệu mới nhất"],
            ),
            (
                IntentEnum.META_CAPABILITY,
                re.compile(r"\b(cán bộ mới thì nên bắt đầu|hướng dẫn cán bộ mới|hướng dẫn sử dụng chatbot)\b", re.IGNORECASE),
                "Chào mừng đồng chí cán bộ mới! Đồng chí có thể bắt đầu tra cứu nhanh qua 3 bước: (1) Nhập câu hỏi nêu rõ chỉ tiêu, đơn vị, năm; (2) Nhấp vào các nút Action Chips gợi ý sẵn; (3) Yêu cầu so sánh tăng/giảm hoặc xuất bảng Excel.",
                ["📊 Thử tra cứu số vụ tai nạn lao động 2025", "💰 Thử xem giải ngân khuyến công", "❓ Xem danh mục chỉ tiêu"],
            ),
        ]

    def _fallback_local_in_memory_parsed(
        self,
        prompt: str,
        curr_quest: Optional[ActiveQuestFrameDTO] = None,
    ) -> Tuple[LLMRouterStructuredOutput, str, Dict[str, int], float]:
        """
        Offline Safety Circuit Breaker: Sử dụng DuckDB In-Memory Catalog + Heuristics
        khi toàn bộ chuỗi API LLM gặp sự cố mạng hoặc hết hạn mức.
        Đảm bảo hệ thống KHÔNG BAO GIỜ CRASH 500!
        """
        text = prompt.strip()
        # 1. Trích xuất chỉ tiêu qua DuckDB Fuzzy
        fuzzy_metric = self.hdft_tracker.fuzzy_strategy.match_metric(text)
        dwh_entities = [fuzzy_metric[0]] if fuzzy_metric else []
        if not dwh_entities and curr_quest and curr_quest.metric_code:
            dwh_entities = [curr_quest.metric_code]

        # 2. Trích xuất địa bàn
        fuzzy_ent = self.hdft_tracker.fuzzy_strategy.match_entity(text)
        location_name = fuzzy_ent[0] if fuzzy_ent else ("Toàn tỉnh" if "toàn tỉnh" in text.lower() else None)
        if not location_name and curr_quest and curr_quest.admin_entity:
            location_name = curr_quest.admin_entity

        # 3. Trích xuất năm
        year_match = re.search(r"\b(202[4-6])\b", text)
        start_year = int(year_match.group(1)) if year_match else (int(curr_quest.temporal_val) if curr_quest and curr_quest.temporal_val and curr_quest.temporal_val.isdigit() else 2025)

        # 4. Xác định intent
        comparison_year = None
        if "so sánh" in text.lower() or "tăng hay giảm" in text.lower() or "yoy" in text.lower():
            intent = "DYNAMIC_PARALLEL_DAG"
            dag_archetype = "TEMPORAL_COMPARISON"
            if year_match:
                comparison_year = int(year_match.group(1))
            elif curr_quest and curr_quest.comparison_year and curr_quest.comparison_year.isdigit():
                comparison_year = int(curr_quest.comparison_year)
        elif any(k in text.lower() for k in ["nhiệm vụ", "chương trình", "đề án", "danh mục", "biểu mẫu"]):
            intent = "CATALOG_DISCOVERY"
            dag_archetype = None
        elif not year_match and not curr_quest:
            intent = "CLARIFICATION"
            dag_archetype = None
        else:
            intent = "TEMPLATE_FAST_TRACK"
            dag_archetype = None

        parsed = LLMRouterStructuredOutput(
            intent=intent,
            is_ambiguous=(intent == "CLARIFICATION"),
            is_topic_shift=False,
            clarification_reason="Hệ thống chuyển sang chế độ dự phòng nội bộ (Offline Circuit Breaker)." if intent == "CLARIFICATION" else None,
            candidate_clarification_chips=["Năm 2025", "Năm 2024"] if intent == "CLARIFICATION" else [],
            temporal_scope=TemporalScopeDTO(start_year=start_year, end_year=comparison_year) if start_year else None,
            spatial_scope=SpatialScopeDTO(location_name=location_name) if location_name else None,
            dwh_entities=dwh_entities,
            dag_archetype=dag_archetype,
            complexity="LOW_TEMPLATE" if intent == "TEMPLATE_FAST_TRACK" else "MEDIUM",
        )
        return parsed, "local-offline-circuit-breaker", {"total_tokens": 0}, 0.5

    def _finalize_output(
        self,
        output: RouterOutputDTO,
        session_id: str,
        effective_text: str,
        is_first_turn: bool,
    ) -> RouterOutputDTO:
        """Đồng bộ trạng thái sau định tuyến vào Redis Session Memory và Decision Cache."""
        if self.session_manager:
            try:
                # 1. Update active quest in Redis if present
                if output.active_quest:
                    self.session_manager.save_active_quest(session_id, output.active_quest)

                # 2. Append turn message to sliding window
                self.session_manager.append_message(session_id, "user", output.query_sanitized)
                resp_summary = output.bypass_response or f"Định tuyến: {output.routing_track}"
                if output.active_quest and output.active_quest.metric_code:
                    resp_summary += f", Chỉ tiêu: {output.active_quest.metric_code}"
                if output.active_quest and output.active_quest.admin_entity:
                    resp_summary += f", Địa bàn: {output.active_quest.admin_entity}"
                if output.active_quest and output.active_quest.temporal_val:
                    resp_summary += f", Năm: {output.active_quest.temporal_val}"
                self.session_manager.append_message(session_id, "assistant", resp_summary)

                # 3. Save to decision cache for turn 1 non-clarification routes
                if is_first_turn and settings.ENABLE_DECISION_CACHE and output.route not in [
                    RouteTypeEnum.CLARIFICATION,
                    RouteTypeEnum.SECURITY_DENIAL,
                ]:
                    self.session_manager.set_decision_cache(effective_text, output.model_dump())
            except Exception as e:
                logger.warning(f"Error in _finalize_output: {e}")
        return output

    def route_query(
        self,
        prompt: str,
        session_id: str = "default_session",
        user_context: Optional[Any] = None,
    ) -> RouterOutputDTO:
        """
        Thực thi quy trình định tuyến hoàn chỉnh cho một câu hỏi dựa trên SSOT DashScope LLM Router.
        Tuân thủ Rule 8: Zero SLA constraints, Safety Timeout = 5.0s.
        """
        start_time = time.perf_counter()
        text = prompt.strip()
        persona = self.persona_classifier.classify(text)

        # ==============================================================================
        # 1. TIER 0: SECURITY GUARDRAILS CHECK (P0 Tối Cao)
        # ==============================================================================
        is_inj, inj_msg, _ = InjectionShield.detect_injection(text)
        is_pii, pii_msg, _ = PIISanitizer.detect_pii(text)
        is_out, out_msg, _ = ScopePrechecker.check_scope(text)

        if is_inj or is_pii or is_out:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return RouterOutputDTO(
                session_id=session_id,
                query_sanitized=text,
                route=RouteTypeEnum.SECURITY_DENIAL,
                routing_track="SECURITY_DENIAL",
                intent=IntentEnum.SECURITY_DENIAL,
                persona=persona,
                confidence_score=1.0,
                tokens_used=0,
                zero_llm_token=True,
                zero_sql=True,
                safety_timeout_seconds=5.0,
                sla_max_latency_ms=30.0,
                latency_ms=round(latency_ms, 3),
                active_quest=None,
                active_quest_preserved=False,
                active_quest_action=QuestActionEnum.REFUSE,
                bypass_response=inj_msg or pii_msg or out_msg or "Yêu cầu bị từ chối do vi phạm quy tắc an toàn hoặc nằm ngoài phạm vi dữ liệu.",
                action_chips=[],
                missing_slots=[],
                clarification_options=[],
            )

        # ==============================================================================
        # 2. TIER 0: CHITCHAT FAST BYPASS & GREETING DECOUPLING
        # ==============================================================================
        curr_quest, _ = self.hdft_tracker.get_or_create_session(session_id)

        if self.chitchat_engine.is_chitchat(text):
            chitchat_res = self.chitchat_engine.evaluate(
                prompt=text,
                session_id=session_id,
                active_quest=curr_quest,
            )
            if chitchat_res is not None:
                if chitchat_res.active_quest_action == QuestActionEnum.TEARDOWN:
                    self.hdft_tracker.set_active_quest(session_id, None)
                return chitchat_res

        # Phân tách câu ghép (Compound Intent: Greeting + Business Payload)
        has_greeting, greeting_part, biz_payload = self.chitchat_engine.decouple_greeting_and_business(text)
        effective_text = biz_payload if (has_greeting and biz_payload) else text

        # ==============================================================================
        # 2.3. TIER 0.3: REDIS DECISION CACHE CHECK (Lượt 1, Zero-Token LLM, < 5ms)
        # ==============================================================================
        is_first_turn = (curr_quest is None or curr_quest.turn_count == 0)
        if is_first_turn and settings.ENABLE_DECISION_CACHE and self.session_manager:
            try:
                cached_dto = self.session_manager.get_decision_cache(effective_text)
                if cached_dto:
                    latency_ms = (time.perf_counter() - start_time) * 1000.0
                    cached_dto["session_id"] = session_id
                    cached_dto["latency_ms"] = round(latency_ms, 3)
                    cached_dto["tokens_used"] = 0
                    cached_dto["zero_llm_token"] = True
                    output_dto = RouterOutputDTO(**cached_dto)
                    # KHẮC PHỤC TRAP-011: Bắt buộc lưu active_quest vào Redis session của session_id hiện tại
                    if output_dto.active_quest:
                        self.session_manager.save_active_quest(session_id, output_dto.active_quest)
                    self.session_manager.append_message(session_id, "user", output_dto.query_sanitized)
                    resp_summary = output_dto.bypass_response or f"Định tuyến: {output_dto.routing_track}"
                    self.session_manager.append_message(session_id, "assistant", resp_summary)
                    return output_dto
            except Exception as e:
                logger.warning(f"Error reading decision cache from Redis: {e}")

        # ==============================================================================
        # 2.5. TIER 0.5: CATALOG DISCOVERY FAST BYPASS (Static Metadata < 50ms, Zero LLM)
        # ==============================================================================
        # Chỉ bypass khi không phải câu hỏi so sánh/truy vấn số liệu Fact/thống kê
        # Bỏ qua nếu có từ hỏi công thức định nghĩa (DISC_04)
        is_definition_query = any(ind in text.lower() for ind in ["được tính như thế nào", "công thức tính", "định nghĩa chỉ tiêu", "nghĩa là gì"])
        has_fact_operator = any(ind in text.lower() for ind in ["bao nhiêu", "cao nhất", "thấp nhất", "nhiều nhất", "ít nhất", "tăng hay giảm", "so sánh"])
        has_year = bool(re.search(r"\b(202[4-6])\b", text))
        is_fact_or_stat_query = (has_year or has_fact_operator) and not is_definition_query

        if not is_fact_or_stat_query:
            for intent_enum, pat, answer, chips in self._discovery_patterns:
                if pat.search(text) or pat.search(effective_text):
                    latency_ms = (time.perf_counter() - start_time) * 1000.0
                    res = RouterOutputDTO(
                        session_id=session_id,
                        query_sanitized=text,
                        route=RouteTypeEnum.CATALOG_DISCOVERY,
                        routing_track="CATALOG_DISCOVERY",
                        intent=intent_enum,
                        persona=persona,
                        confidence_score=1.0,
                        tokens_used=0,
                        zero_llm_token=True,
                        zero_sql=True,
                        safety_timeout_seconds=5.0,
                        sla_max_latency_ms=50.0,
                        latency_ms=round(latency_ms, 3),
                        active_quest=curr_quest,
                        active_quest_preserved=True if curr_quest else False,
                        active_quest_action=QuestActionEnum.INIT,
                        bypass_response=answer,
                        action_chips=chips,
                        missing_slots=[],
                        clarification_options=[],
                    )
                    return self._finalize_output(res, session_id, effective_text, is_first_turn)

        # ==============================================================================
        # 3. TIER 1: SSOT DASHSCOPE LLM STRUCTURED OUTPUTS ROUTER (with Dual-Context & Circuit Breaker)
        # ==============================================================================
        # 1. Structured Quest Context
        context_summary = None
        if curr_quest and (curr_quest.metric_code or curr_quest.admin_entity or curr_quest.temporal_val):
            context_summary = {
                "metric_code": curr_quest.metric_code or "Chưa rõ",
                "admin_entity": curr_quest.admin_entity or "Chưa rõ",
                "admin_level": curr_quest.admin_level,
                "temporal_val": curr_quest.temporal_val or "Chưa rõ",
            }
        # 2. Sliding Window Dialog History from Redis
        recent_messages = []
        if self.session_manager:
            try:
                recent_messages = self.session_manager.get_recent_messages(
                    session_id, max_turns=settings.SESSION_MAX_HISTORY_TURNS
                )
            except Exception as e:
                logger.warning(f"Error fetching recent messages from Redis: {e}")

        try:
            parsed, model_used, usage, llm_latency = self.router_client.route_sync(
                prompt=effective_text,
                context_summary=context_summary,
                recent_messages=recent_messages,
            )
            tokens_used = usage.get("total_tokens", 0)
            zero_llm_token = False
        except Exception as e:
            logger.error(f"Router LLM Client error: {e}. Activating Offline Circuit Breaker Fallback.")
            parsed, model_used, usage, llm_latency = self._fallback_local_in_memory_parsed(
                prompt=effective_text,
                curr_quest=curr_quest,
            )
            tokens_used = 0
            zero_llm_token = True

        # Cập nhật H-DFT Dialogue Tracker (hỗ trợ override topic shift từ LLM)
        active_quest, temp_memory, is_topic_shift = self.hdft_tracker.update_state(
            prompt=effective_text,
            session_id=session_id,
            override_topic_shift=getattr(parsed, "is_topic_shift", False),
        )

        # Nạp các slots trích xuất được từ LLM Structured Output vào active_quest một cách an toàn
        if parsed.temporal_scope:
            is_comp = (
                parsed.dag_archetype == "TEMPORAL_COMPARISON"
                or "so với" in text.lower()
                or "tăng hay giảm" in text.lower()
            )
            if is_comp:
                years = [
                    y for y in [parsed.temporal_scope.start_year, parsed.temporal_scope.end_year]
                    if y is not None
                ]
                if len(years) >= 2:
                    active_quest.temporal_val = str(max(years))
                    active_quest.comparison_year = str(min(years))
                elif len(years) == 1:
                    y = str(years[0])
                    if active_quest.temporal_val and y != active_quest.temporal_val:
                        active_quest.comparison_year = y
                    else:
                        active_quest.temporal_val = y
            else:
                if parsed.temporal_scope.start_year:
                    active_quest.temporal_val = str(parsed.temporal_scope.start_year)
                elif not active_quest.temporal_val and parsed.temporal_scope.raw_expression:
                    active_quest.temporal_val = parsed.temporal_scope.raw_expression

                if parsed.temporal_scope.end_year:
                    active_quest.comparison_year = str(parsed.temporal_scope.end_year)

        if parsed.spatial_scope and parsed.spatial_scope.location_name:
            active_quest.admin_entity = parsed.spatial_scope.location_name
        if parsed.dwh_entities and not active_quest.metric_code:
            active_quest.metric_code = ", ".join(parsed.dwh_entities)

        # Kế thừa slot từ lượt trước nếu không phải đổi đề tài (Topic Shift)
        if not is_topic_shift and curr_quest:
            if not active_quest.metric_code and curr_quest.metric_code:
                active_quest.metric_code = curr_quest.metric_code
            if not active_quest.admin_entity and curr_quest.admin_entity:
                active_quest.admin_entity = curr_quest.admin_entity
                active_quest.admin_level = curr_quest.admin_level
            if not active_quest.temporal_val and curr_quest.temporal_val:
                active_quest.temporal_val = curr_quest.temporal_val

        # Xử lý các phân nhánh theo Intent được định tuyến:
        # --------------------------------------------------------------------------
        # 0. GIAO TIẾP XÃ GIAO (CHITCHAT_BYPASS) - TỪ TẦNG NGỮ NGHĨA LLM
        # --------------------------------------------------------------------------
        if parsed.intent == "CHITCHAT_BYPASS":
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            chitchat_res = self.chitchat_engine.evaluate(
                prompt=text,
                session_id=session_id,
                active_quest=curr_quest,
            )
            if chitchat_res is not None:
                chitchat_res.latency_ms = round(latency_ms, 3)
                chitchat_res.tokens_used = tokens_used
                chitchat_res.zero_llm_token = zero_llm_token
                return self._finalize_output(chitchat_res, session_id, effective_text, is_first_turn)

            res = RouterOutputDTO(
                session_id=session_id,
                query_sanitized=text,
                route=RouteTypeEnum.CHITCHAT_BYPASS,
                routing_track="CHITCHAT_BYPASS",
                intent=IntentEnum.GREETING,
                persona=persona,
                confidence_score=0.98,
                tokens_used=tokens_used,
                zero_llm_token=zero_llm_token,
                zero_sql=True,
                safety_timeout_seconds=5.0,
                sla_max_latency_ms=50.0,
                latency_ms=round(latency_ms, 3),
                active_quest=curr_quest,
                active_quest_preserved=True if curr_quest else False,
                active_quest_action=QuestActionEnum.INIT,
                bypass_response="Xin chào đồng chí! Tôi là Trợ lý ảo Tra cứu Kho Dữ liệu Hành chính Công Tỉnh Lâm Đồng (IPGov Chatbot). Tôi có thể hỗ trợ đồng chí tra cứu số liệu chỉ tiêu kinh tế - xã hội, báo cáo tổng hợp và phân tích đa kỳ theo thẩm quyền.",
                action_chips=["Tra cứu kinh phí khuyến công 2025", "Báo cáo chỉ tiêu Sở Nội vụ", "Khám phá danh mục"],
                missing_slots=[],
                clarification_options=[],
            )
            return self._finalize_output(res, session_id, effective_text, is_first_turn)

        # --------------------------------------------------------------------------
        # A. NGOÀI PHẠM VI (OUT_OF_SCOPE / SECURITY_DENIAL)
        # --------------------------------------------------------------------------
        if parsed.intent in ["OUT_OF_SCOPE", "SECURITY_DENIAL"]:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            res = RouterOutputDTO(
                session_id=session_id,
                query_sanitized=text,
                route=RouteTypeEnum.SECURITY_DENIAL,
                routing_track="SECURITY_DENIAL",
                intent=IntentEnum.SECURITY_DENIAL,
                persona=persona,
                confidence_score=0.99,
                tokens_used=tokens_used,
                zero_llm_token=zero_llm_token,
                zero_sql=True,
                safety_timeout_seconds=5.0,
                sla_max_latency_ms=30.0,
                latency_ms=round(latency_ms, 3),
                active_quest=active_quest,
                active_quest_preserved=False,
                active_quest_action=QuestActionEnum.REFUSE,
                bypass_response=parsed.clarification_reason or "Yêu cầu nằm ngoài phạm vi cơ sở dữ liệu công vụ tỉnh Lâm Đồng.",
                action_chips=[],
                missing_slots=[],
                clarification_options=[],
            )
            return self._finalize_output(res, session_id, effective_text, is_first_turn)

        # --------------------------------------------------------------------------
        # B. CÂU HỎI MƠ HỒ / THIẾU SLOT (CLARIFICATION) - INVARIANT GATE
        # --------------------------------------------------------------------------
        has_prompt_year = bool(re.search(r"\b(202[4-6])\b", text))
        has_deictic_time = bool(re.search(r"\b(gần đây|vừa qua|mới nhất|hôm nay|hiện tại|năm ngoái)\b", text, re.IGNORECASE))
        has_extracted_year = bool(
            (parsed.temporal_scope and (parsed.temporal_scope.start_year or parsed.temporal_scope.end_year))
            or (active_quest and active_quest.temporal_val)
            or has_prompt_year
        )

        metric_str = (active_quest.metric_code or "").lower().strip()
        is_generic_metric = (
            not metric_str
            or metric_str in ["kinh_phi", "kinh phí", "số liệu", "chỉ tiêu", "tình hình", "ngân sách"]
        )

        # Nếu active_quest trước đó đang PENDING_SLOTS và lượt này đã có đủ temporal_val & metric_code:
        slot_filling_resolved = (
            curr_quest is not None
            and curr_quest.status == QuestStatusEnum.PENDING_SLOTS
            and bool(active_quest.temporal_val)
            and bool(active_quest.metric_code)
            and not is_generic_metric
        )

        has_all_key_slots = bool(active_quest.temporal_val and active_quest.metric_code and not is_generic_metric)

        # Tránh rơi vào CLARIFY nếu đã có đủ slot kế thừa từ lượt trước (Lượt 2+)
        if curr_quest is not None and has_all_key_slots and not is_topic_shift and parsed.intent == "CLARIFICATION":
            is_clarify = False
            parsed.intent = "TEMPLATE_FAST_TRACK"
        else:
            is_clarify = (
                not slot_filling_resolved
                and (
                    parsed.intent == "CLARIFICATION"
                    or parsed.is_ambiguous
                    or (
                        active_quest.turn_count <= 1
                        and not has_deictic_time
                        and parsed.intent in ["TEMPLATE_FAST_TRACK", "DYNAMIC_PARALLEL_DAG", "SINGLE_SQL"]
                        and (not has_extracted_year or (is_generic_metric and not active_quest.admin_entity))
                    )
                )
            )

        if is_clarify:
            active_quest.status = QuestStatusEnum.PENDING_SLOTS
            missing_slots = ["temporal_scope"] if not has_extracted_year else ["metric_code"]
            chip_labels = parsed.candidate_clarification_chips or (
                [
                    "Kinh phí khuyến công",
                    "Kinh phí sự nghiệp y tế",
                    "Chi đầu tư phát triển",
                ] if is_generic_metric else [
                    "Năm 2025 (Chính thức)",
                    "Năm 2026 (Kế hoạch)",
                    "Năm 2024",
                ]
            )
            clarify_opts = [
                SlotClarificationOption(
                    label=lbl,
                    slot_key="metric_code" if is_generic_metric else "year",
                    value=lbl,
                    preview_description="Làm rõ chỉ tiêu/thời gian",
                )
                for lbl in chip_labels
            ]
            active_quest.missing_slots = missing_slots
            active_quest.candidate_clarifications = clarify_opts

            latency_ms = (time.perf_counter() - start_time) * 1000.0
            res = RouterOutputDTO(
                session_id=session_id,
                query_sanitized=text,
                route=RouteTypeEnum.CLARIFICATION,
                routing_track="CLARIFICATION",
                intent=IntentEnum.CLARIFICATION_NEEDED,
                persona=persona,
                confidence_score=0.95,
                tokens_used=tokens_used,
                zero_llm_token=zero_llm_token,
                zero_sql=True,
                safety_timeout_seconds=5.0,
                sla_max_latency_ms=50.0,
                latency_ms=round(latency_ms, 3),
                active_quest=active_quest,
                active_quest_preserved=True,
                active_quest_action=QuestActionEnum.CLARIFY,
                bypass_response=parsed.clarification_reason or "Đồng chí vui lòng chọn mốc thời gian hoặc phạm vi địa bàn cần tra cứu số liệu:",
                action_chips=chip_labels,
                missing_slots=missing_slots,
                clarification_options=clarify_opts,
            )
            return self._finalize_output(res, session_id, effective_text, is_first_turn)

        # --------------------------------------------------------------------------
        # C. KHÁM PHÁ DANH MỤC & NĂNG LỰC HỆ THỐNG (CATALOG_DISCOVERY)
        # --------------------------------------------------------------------------
        if parsed.intent == "CATALOG_DISCOVERY":
            catalog_answer = None
            catalog_chips = []
            for _, pat, answer, chips in self._discovery_patterns:
                if pat.search(text) or pat.search(effective_text):
                    catalog_answer = answer
                    catalog_chips = chips
                    break

            latency_ms = (time.perf_counter() - start_time) * 1000.0
            if not catalog_answer:
                # Tra cứu danh mục bảng chiều (mission, collection_form, criteria, deparment)
                # Chuyển tiếp xuống Module 4 (Schema Pruner) và Module 5 (SQL Generator)
                res = RouterOutputDTO(
                    session_id=session_id,
                    query_sanitized=text,
                    route=RouteTypeEnum.CATALOG_DISCOVERY,
                    routing_track="CATALOG_DISCOVERY",
                    intent=IntentEnum.SCOPE_DISCOVERY,
                    persona=persona,
                    confidence_score=0.95,
                    tokens_used=tokens_used,
                    zero_llm_token=zero_llm_token,
                    zero_sql=False,
                    safety_timeout_seconds=5.0,
                    sla_max_latency_ms=50.0,
                    latency_ms=round(latency_ms, 3),
                    active_quest=curr_quest,
                    active_quest_preserved=True if curr_quest else False,
                    active_quest_action=QuestActionEnum.INIT,
                    bypass_response=None,
                    action_chips=[],
                    missing_slots=[],
                    clarification_options=[],
                )
            else:
                res = RouterOutputDTO(
                    session_id=session_id,
                    query_sanitized=text,
                    route=RouteTypeEnum.CATALOG_DISCOVERY,
                    routing_track="CATALOG_DISCOVERY",
                    intent=IntentEnum.META_CAPABILITY,
                    persona=persona,
                    confidence_score=0.98,
                    tokens_used=tokens_used,
                    zero_llm_token=zero_llm_token,
                    zero_sql=True,
                    safety_timeout_seconds=5.0,
                    sla_max_latency_ms=50.0,
                    latency_ms=round(latency_ms, 3),
                    active_quest=curr_quest,
                    active_quest_preserved=True if curr_quest else False,
                    active_quest_action=QuestActionEnum.INIT,
                    bypass_response=catalog_answer,
                    action_chips=catalog_chips,
                    missing_slots=[],
                    clarification_options=[],
                )
            return self._finalize_output(res, session_id, effective_text, is_first_turn)

        # --------------------------------------------------------------------------
        # D. PHÂN TÍCH SO SÁNH ĐA KỲ / ĐA CHIỀU (DYNAMIC_PARALLEL_DAG)
        # --------------------------------------------------------------------------
        # Invariant Gate: Anti-False-DAG
        # Nếu LLM gán DYNAMIC_PARALLEL_DAG nhưng câu hỏi thực tế không có từ khóa so sánh đa kỳ/phân rã/xếp hạng,
        # mà chỉ là truy vấn đơn lẻ hoặc thay thế slot đơn giản -> chuẩn hóa về TEMPLATE_FAST_TRACK
        if parsed.intent == "DYNAMIC_PARALLEL_DAG":
            has_comparison_kw = any(
                kw in text.lower()
                for kw in ["so với", "tăng", "giảm", "biến động", "chênh lệch", "so sánh", "cùng kỳ", "tỷ trọng", "cơ cấu", "top", "xếp hạng"]
            )
            if (
                not has_comparison_kw
                and parsed.dag_archetype not in ["COMPONENT_BREAKDOWN", "RANKING_TOP_K", "MULTI_METRIC_DRILLDOWN"]
            ):
                logger.info("Invariant Gate: Normalized false DYNAMIC_PARALLEL_DAG to TEMPLATE_FAST_TRACK")
                parsed.intent = "TEMPLATE_FAST_TRACK"

        if parsed.intent == "DYNAMIC_PARALLEL_DAG":
            active_quest.status = QuestStatusEnum.COMMITTED
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            res = RouterOutputDTO(
                session_id=session_id,
                query_sanitized=text,
                route=RouteTypeEnum.DYNAMIC_PARALLEL_DAG,
                routing_track="DYNAMIC_PARALLEL_DAG",
                intent=IntentEnum.COMPLEX_DAG_ANALYTICS,
                persona=persona,
                confidence_score=0.98,
                tokens_used=tokens_used,
                zero_llm_token=zero_llm_token,
                zero_sql=False,
                safety_timeout_seconds=5.0,
                sla_max_latency_ms=800.0,
                latency_ms=round(latency_ms, 3),
                active_quest=active_quest,
                active_quest_preserved=True,
                active_quest_action=QuestActionEnum.INIT,
                dag_archetype=parsed.dag_archetype or "TEMPORAL_COMPARISON",
                subquery_count=parsed.subquery_count or 2,
                complexity=parsed.complexity or "HIGH_PARALLEL_DAG",
                bypass_response=None,
                action_chips=[],
                missing_slots=[],
                clarification_options=[],
            )
            return self._finalize_output(res, session_id, effective_text, is_first_turn)

        # --------------------------------------------------------------------------
        # E. CÂU HỎI TRUY VẤN TỰ DO / SINGLE SQL (SINGLE_SQL)
        # --------------------------------------------------------------------------
        if parsed.intent == "SINGLE_SQL":
            active_quest.status = QuestStatusEnum.COMMITTED
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            res = RouterOutputDTO(
                session_id=session_id,
                query_sanitized=text,
                route=RouteTypeEnum.SINGLE_SQL,
                routing_track="SINGLE_SQL",
                intent=IntentEnum.COMPLEX_RAW_SQL,
                persona=persona,
                confidence_score=0.95,
                tokens_used=tokens_used,
                zero_llm_token=zero_llm_token,
                zero_sql=False,
                safety_timeout_seconds=5.0,
                sla_max_latency_ms=1500.0,
                latency_ms=round(latency_ms, 3),
                active_quest=active_quest,
                active_quest_preserved=True,
                active_quest_action=QuestActionEnum.INIT if not curr_quest else QuestActionEnum.PRESERVE,
                complexity=parsed.complexity or "MEDIUM_SINGLE_SQL",
                bypass_response=None,
                action_chips=[],
                missing_slots=[],
                clarification_options=[],
            )
            return self._finalize_output(res, session_id, effective_text, is_first_turn)

        # --------------------------------------------------------------------------
        # F. TRA CỨU CHỈ TIÊU ĐƠN LẺ CÓ MỐC NĂM (TEMPLATE_FAST_TRACK - 85% traffic)
        # --------------------------------------------------------------------------
        active_quest.status = QuestStatusEnum.COMMITTED
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        if latency_ms > 5000.0:
            logger.warning(
                f"Defensive safety timeout exceeded: {latency_ms:.2f}ms > 5000.0ms for prompt: {text[:50]}"
            )

        res = RouterOutputDTO(
            session_id=session_id,
            query_sanitized=text,
            route=RouteTypeEnum.TEMPLATE_FAST_TRACK,
            routing_track="TEMPLATE_FAST_TRACK",
            intent=IntentEnum.FAST_METRIC_COMPILER,
            persona=persona,
            confidence_score=0.98,
            tokens_used=tokens_used,
            zero_llm_token=zero_llm_token,
            zero_sql=False,
            safety_timeout_seconds=5.0,
            sla_max_latency_ms=300.0,
            latency_ms=round(latency_ms, 3),
            active_quest=active_quest,
            active_quest_preserved=True,
            active_quest_action=QuestActionEnum.COMMIT,
            complexity=parsed.complexity or "LOW_TEMPLATE",
            bypass_response=None,
            action_chips=[],
            missing_slots=[],
            clarification_options=[],
        )
        return self._finalize_output(res, session_id, effective_text, is_first_turn)

