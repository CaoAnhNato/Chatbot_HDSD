"""
Module: IPGov_Chatbot/schemas/guardrail_dto.py
Chức năng: Hợp đồng dữ liệu cho Module 2 Pre-Router Security Guardrails.
Bao gồm định danh vi phạm (PII, Injection, Out-of-Scope) và snapshot đầu ra SanitizedQuestDTO.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO


class ViolationTypeEnum(str, Enum):
    """Phân loại vi phạm quy tắc an toàn bảo mật và phạm vi công vụ."""
    NONE = "none"
    PII = "pii"                       # Chứa CCCD, SĐT, STK theo Nghị định 13/2023
    INJECTION = "injection"           # Chứa câu lệnh DDL/DML hoặc jailbreak prompt
    OUT_OF_SCOPE = "out_of_scope"     # Nằm ngoài 8 lĩnh vực quản lý nhà nước số hóa


class GuardrailResultDTO(BaseModel):
    """Kết quả kiểm định của bộ ba Guardrails."""
    is_safe: bool = Field(..., description="True nếu câu hỏi an toàn để tiếp tục chuyển sang Router")
    violation_type: ViolationTypeEnum = Field(default=ViolationTypeEnum.NONE)
    violation_message: Optional[str] = Field(None, description="Thông điệp từ chối/cảnh báo thân thiện")
    violation_details: Optional[Dict[str, Any]] = Field(default_factory=dict)
    sanitized_prompt: str = Field(..., description="Prompt đã làm sạch / che giấu PII nếu áp dụng")
    latency_ms: float = Field(default=0.0, description="Độ trễ xử lý của Guardrails (< 30ms)")


class RequestSessionContextDTO(BaseModel):
    """
    Snapshot Stage 1: Ngữ cảnh phiên yêu cầu trích xuất từ Module 1 (API Gateway).
    Cung cấp làm dữ liệu đầu vào độc lập cho Module 2.
    """
    trace_id: str
    session_id: str
    raw_prompt: str
    user_context: UserSecurityContextDTO
    client_ip: Optional[str] = None
    created_at_epoch: float


class SanitizedQuestDTO(BaseModel):
    """
    Snapshot Stage 2: Yêu cầu đã được tiền kiểm duyệt an toàn từ Module 2.
    Cung cấp làm dữ liệu đầu vào cho Module 3 (Query Router & H-DFT).
    """
    trace_id: str
    session_id: str
    sanitized_prompt: str
    user_context: UserSecurityContextDTO
    is_safe: bool
    guardrail_result: GuardrailResultDTO
    created_at_epoch: float
