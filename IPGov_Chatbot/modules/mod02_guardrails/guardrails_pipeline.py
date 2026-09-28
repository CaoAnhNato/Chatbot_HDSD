"""
Module: IPGov_Chatbot/modules/mod02_guardrails/guardrails_pipeline.py
Chức năng: Đường ống kiểm duyệt an toàn tiền định tuyến (Pre-Router Guardrails Pipeline).
Kết hợp InjectionShield, PIISanitizer và ScopePrechecker theo chuỗi tuần tự tốc độ cao.
SLA đo lường: < 30ms.
"""

import time
from IPGov_Chatbot.schemas.guardrail_dto import (
    RequestSessionContextDTO,
    GuardrailResultDTO,
    SanitizedQuestDTO,
    ViolationTypeEnum
)
from IPGov_Chatbot.modules.mod02_guardrails.injection_shield import InjectionShield
from IPGov_Chatbot.modules.mod02_guardrails.pii_sanitizer import PIISanitizer
from IPGov_Chatbot.modules.mod02_guardrails.scope_prechecker import ScopePrechecker


class GuardrailsPipeline:
    """Đường ống tiền kiểm duyệt an toàn 3 tầng trước khi vào LLM Router."""

    @classmethod
    def evaluate(cls, session_ctx: RequestSessionContextDTO) -> GuardrailResultDTO:
        """
        Thực hiện đánh giá toàn diện câu hỏi của người dùng.
        
        Args:
            session_ctx: Snapshot Stage 1 chứa raw_prompt và user_context.
            
        Returns:
            GuardrailResultDTO: Kết quả kiểm tra, nhãn vi phạm, và thông điệp cảnh báo.
        """
        start_time = time.perf_counter()
        prompt = session_ctx.raw_prompt.strip()

        # 1. Tầng 1: Chặn DDL/DML & Prompt Injection (Ưu tiên P0 tối cao)
        is_inj, inj_msg, inj_details = InjectionShield.detect_injection(prompt)
        if is_inj:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return GuardrailResultDTO(
                is_safe=False,
                violation_type=ViolationTypeEnum.INJECTION,
                violation_message=inj_msg,
                violation_details=inj_details,
                sanitized_prompt=prompt,
                latency_ms=round(elapsed_ms, 2)
            )

        # 2. Tầng 2: Chặn và lọc dữ liệu cá nhân PII (Nghị định 13/2023)
        is_pii, pii_msg, pii_details = PIISanitizer.detect_pii(prompt)
        if is_pii:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return GuardrailResultDTO(
                is_safe=False,
                violation_type=ViolationTypeEnum.PII,
                violation_message=pii_msg,
                violation_details=pii_details,
                sanitized_prompt=prompt,
                latency_ms=round(elapsed_ms, 2)
            )

        # 3. Tầng 3: Tiền kiểm phạm vi dữ liệu DWH 8 lĩnh vực
        is_out, out_msg, out_details = ScopePrechecker.check_scope(prompt)
        if is_out:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return GuardrailResultDTO(
                is_safe=False,
                violation_type=ViolationTypeEnum.OUT_OF_SCOPE,
                violation_message=out_msg,
                violation_details=out_details,
                sanitized_prompt=prompt,
                latency_ms=round(elapsed_ms, 2)
            )

        # Vượt qua an toàn toàn bộ 3 tầng kiểm duyệt
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return GuardrailResultDTO(
            is_safe=True,
            violation_type=ViolationTypeEnum.NONE,
            violation_message=None,
            violation_details={},
            sanitized_prompt=prompt,
            latency_ms=round(elapsed_ms, 2)
        )

    @classmethod
    def create_snapshot_stage_2(
        cls,
        session_ctx: RequestSessionContextDTO,
        guardrail_result: GuardrailResultDTO
    ) -> SanitizedQuestDTO:
        """Đóng gói dữ liệu đầu ra của Stage 2 thành Snapshot DTO phục vụ Stage 3."""
        return SanitizedQuestDTO(
            trace_id=session_ctx.trace_id,
            session_id=session_ctx.session_id,
            sanitized_prompt=guardrail_result.sanitized_prompt,
            user_context=session_ctx.user_context,
            is_safe=guardrail_result.is_safe,
            guardrail_result=guardrail_result,
            created_at_epoch=time.time()
        )
