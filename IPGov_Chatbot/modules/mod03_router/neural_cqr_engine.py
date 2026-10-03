"""
Module: IPGov_Chatbot/modules/mod03_router/neural_cqr_engine.py
Chức năng: Tầng tái cấu trúc câu hỏi nơ-ron không Regex (Zero-Regex End-to-End Conversational Query Reformulation - E2E CQR).
Căn cứ:
- SParC (Yu et al., ACL 2019), CoSQL (EMNLP 2019)
- Kế hoạch triển khai v1.4.0 (PLAN-REMEDIATION-v1.4.0)

Đặc tính:
1. Xóa bỏ 100% heuristic đếm từ (< 6 từ) và whitelist từ khóa ("vậy", "thế còn", "thì sao").
2. Kích hoạt mô hình nơ-ron (google/gemini-2.5-flash-lite) cho mọi lượt hỏi n > 1.
3. Trả về cấu trúc JSON Pydantic nghiêm ngặt: is_dependent, standalone_query, target_domain, missing_slots, fusion_rationale.
4. Cơ chế Graceful Fallback khi offline hoặc gặp sự cố mạng, bảo đảm không bao giờ làm gián đoạn hội thoại.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from IPGov_Chatbot.config import settings
from IPGov_Chatbot.modules.mod03_router.discourse_state_tracker import DialogueStateFrame

logger = logging.getLogger("ipgov.mod03.neural_cqr_engine")


class CQRReformulationResult(BaseModel):
    """
    Kết quả tái cấu trúc câu hỏi hội thoại nơ-ron (Pydantic Schema SSOT).
    """
    is_dependent: bool = Field(
        description="True nếu câu hỏi là câu tiếp nối, tỉnh lược, đại từ thay thế cần ngữ cảnh trước."
    )
    standalone_query: str = Field(
        description="Câu hỏi hoàn chỉnh độc lập sau khi đã hòa mạng đầy đủ thực thể và mốc thời gian."
    )
    target_domain: str = Field(
        default="fact_criteria",
        description="Miền dữ liệu: fact_criteria | report | mission_personnel | collection_form | out_of_scope"
    )
    missing_slots: List[str] = Field(
        default_factory=list,
        description="Các slot bị thiếu cần làm rõ (ví dụ: year, department)"
    )
    fusion_rationale: str = Field(
        default="",
        description="Lý do hòa mạng ngữ cảnh ngắn gọn."
    )
    confidence_score: float = Field(
        default=1.0,
        description="Độ tin cậy từ 0.0 đến 1.0."
    )


class NeuralCQREngine:
    """
    Động cơ tái cấu trúc câu hỏi đàm thoại bằng mô hình ngôn ngữ nơ-ron (Zero-Regex E2E CQR).
    """

    def __init__(self) -> None:
        self.primary_model = settings.AGENT_PRIMARY_MODEL
        self.fallback_model = settings.AGENT_FALLBACK_MODEL_1
        self.api_key = settings.AGENT_DECISION_LLM_API_KEY or settings.OPENROUTER_API_KEY or settings.GOOGLE_API_KEY
        self.base_url = settings.OPENROUTER_BASE_URL

    def reformulate(
        self,
        query: str,
        context_frame: Optional[DialogueStateFrame] = None,
        history: Optional[List[Dict[str, str]]] = None,
        standalone_hint: Optional[str] = None,
    ) -> CQRReformulationResult:
        """
        Thực hiện tái cấu trúc câu hỏi nơ-ron cho câu hỏi lượt n > 1.
        
        Args:
            query: Câu hỏi của người dùng tại lượt hiện tại.
            context_frame: State Frame hiện hành từ DiscourseStateTracker.
            history: Lịch sử hội thoại gần nhất (nếu có).
            standalone_hint: Gợi ý câu hỏi độc lập được kiến tạo bởi DiscourseStateTracker.
            
        Returns:
            CQRReformulationResult: Đối tượng Pydantic chứa câu hỏi độc lập đã hòa mạng.
        """
        q_clean = query.strip()
        if not context_frame or not context_frame.topic_entity:
            # Lượt 1 hoặc không có ngữ cảnh trước -> Trả về nguyên trạng độc lập
            return CQRReformulationResult(
                is_dependent=False,
                standalone_query=q_clean,
                target_domain=context_frame.domain if context_frame else "fact_criteria",
                missing_slots=[],
                fusion_rationale="Lượt hỏi đầu tiên hoặc câu hỏi độc lập không có ngữ cảnh phụ thuộc.",
                confidence_score=1.0,
            )

        # Xây dựng System Prompt chuyên biệt cho CQR
        sys_prompt = (
            "Bạn là chuyên gia Ngôn ngữ học Tái cấu trúc Câu hỏi Hội thoại (Conversational Query Reformulation - CQR) "
            "cho Trợ lý AI Tra cứu Kho Dữ Liệu Hành Chính Công tỉnh Lâm Đồng.\n"
            "NHIỆM VỤ:\n"
            "Phân tích câu hỏi lượt hiện tại của người dùng và ngữ cảnh hội thoại trước đó (Context Frame).\n"
            "Xác định xem câu hỏi hiện tại có phụ thuộc ngữ cảnh hay không (tỉnh lược đại từ, chuyển đổi thuộc tính đo lường, hỏi tiếp nối).\n"
            "Nếu có phụ thuộc: viết lại thành một câu hỏi ĐỘC LẬP, HOÀN CHỈNH, RÕ NGHĨA bằng tiếng Việt chuẩn công vụ, "
            "tích hợp đầy đủ Thực thể chủ đề (Topic Entity), Thuộc tính đo lường mới (Metric/Attribute) và Mốc thời gian (Year).\n"
            "ĐẶC BIỆT LƯU Ý:\n"
            "- Nếu người dùng hỏi 'vậy có bao nhiêu hộ' sau khi đã hỏi về 'muối': câu viết lại BẮT BUỘC là 'Tổng số hộ sản xuất muối năm <năm> là bao nhiêu?'.\n"
            "- Nếu người dùng hỏi 'diện tích là bao nhiêu' sau khi hỏi về 'muối': câu viết lại BẮT BUỘC là 'Diện tích sản xuất muối năm <năm> là bao nhiêu ha?'.\n"
            "- Tuyệt đối KHÔNG gộp sai chủ đề (ví dụ: không được ghép 'diện tích' vào 'tai nạn lao động' nếu chủ đề là tai nạn).\n"
            "- Trả về kết quả thuần túy dưới dạng JSON theo đúng schema sau (không thêm văn bản ngoài JSON):\n"
            "{\n"
            '  "is_dependent": true,\n'
            '  "standalone_query": "câu hỏi hoàn chỉnh độc lập",\n'
            '  "target_domain": "fact_criteria | report | mission_personnel | collection_form",\n'
            '  "missing_slots": [],\n'
            '  "fusion_rationale": "giải thích ngắn gọn",\n'
            '  "confidence_score": 0.95\n'
            "}"
        )

        user_content = (
            f"NGỮ CẢNH TRƯỚC ĐÓ (CONTEXT FRAME):\n"
            f"- Thực thể chủ đề (Topic Entity): {context_frame.topic_entity}\n"
            f"- Thuộc tính đo lường trước (Metric Attribute): {context_frame.metric_attribute or 'chưa có'}\n"
            f"- Mốc thời gian (Year): {context_frame.temporal_slot or '2026'}\n"
            f"- Miền dữ liệu (Domain): {context_frame.domain}\n"
            f"- Câu hỏi trước đó: \"{context_frame.raw_query}\"\n\n"
            f"GỢI Ý HÒA MẠNG TỪ TRACKER: \"{standalone_hint or 'None'}\"\n\n"
            f"CÂU HỎI LƯỢT HIỆN TẠI CẦN XỬ LÝ:\n"
            f"\"{q_clean}\""
        )

        # Gọi mô hình nơ-ron
        llm_output = self._call_llm(user_content, sys_prompt)
        if llm_output:
            try:
                # Làm sạch markdown fence nếu có
                clean_json = re.sub(r"^```json\s*", "", llm_output.strip())
                clean_json = re.sub(r"^```\s*", "", clean_json)
                clean_json = re.sub(r"\s*```$", "", clean_json).strip()
                data = json.loads(clean_json)
                res = CQRReformulationResult(**data)
                logger.info("[Neural CQR] Reformulated: '%s' -> '%s' (is_dependent=%s)",
                            q_clean, res.standalone_query, res.is_dependent)
                return res
            except Exception as e:
                logger.warning("[Neural CQR] Lỗi phân tích cú pháp JSON từ LLM (%s): %s", e, llm_output)

        # Fallback tất định khi LLM không trả lời được
        if standalone_hint:
            return CQRReformulationResult(
                is_dependent=True,
                standalone_query=standalone_hint,
                target_domain=context_frame.domain,
                missing_slots=[],
                fusion_rationale="Fallback hòa mạng tất định dựa trên Semantic Frame Tracker.",
                confidence_score=0.85,
            )

        return CQRReformulationResult(
            is_dependent=False,
            standalone_query=q_clean,
            target_domain=context_frame.domain,
            missing_slots=[],
            fusion_rationale="Fallback giữ nguyên câu hỏi thô khi mô hình nơ-ron không khả dụng.",
            confidence_score=0.70,
        )

    def _call_llm(self, prompt: str, system_prompt: str) -> Optional[str]:
        """Gọi LLM nơ-ron với cơ chế fallback."""
        from openai import OpenAI

        models = [self.primary_model, self.fallback_model]
        api_key = self.api_key or settings.OPENROUTER_API_KEY or settings.GOOGLE_API_KEY

        for model in models:
            try:
                client = OpenAI(
                    api_key=api_key,
                    base_url=self.base_url,
                    timeout=8.0,
                )
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    max_tokens=400,
                )
                if resp.choices and resp.choices[0].message and resp.choices[0].message.content:
                    return resp.choices[0].message.content.strip()
            except Exception as e:
                logger.warning("[Neural CQR] Mô hình %s thất bại (%s), chuyển fallback...", model, e)
                continue
        return None
