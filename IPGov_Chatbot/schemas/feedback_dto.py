"""
IPGov Chatbot - Schemas & Enums for Human-in-the-Loop Feedback & Quest Annotations
Căn cứ: Arc42 Sec 8, Ragas/LangSmith Annotation Queue Standards
Tuân thủ: .agents/rules/ipgov-coding-rules.md (Pydantic v2, Frozen/Immutable DTOs)
"""

from __future__ import annotations
import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ErrorCategoryEnum(str, Enum):
    ROUTING_MISMATCH = "ROUTING_MISMATCH"
    SLOT_EXTRACTION_ERROR = "SLOT_EXTRACTION_ERROR"
    ANAPHORA_RESOLUTION_FAIL = "ANAPHORA_FAIL"
    TOPIC_SHIFT_FAILED = "TOPIC_SHIFT_FAILED"
    GUARDRAIL_FALSE_POSITIVE = "GUARDRAIL_FALSE_POS"
    GUARDRAIL_FALSE_NEGATIVE = "GUARDRAIL_FALSE_NEG"
    SQL_LOGIC_ERROR = "SQL_LOGIC_ERROR"
    DATA_FRESHNESS_ISSUE = "DATA_FRESHNESS_ISSUE"
    RESPONSE_TONE_INCORRECT = "TONE_INCORRECT"
    OTHER = "OTHER"


class FeedbackSeverityEnum(str, Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class QuestAnnotationDTO(BaseModel):
    model_config = ConfigDict(frozen=False)

    annotation_id: str = Field(default_factory=lambda: f"note_{uuid.uuid4().hex[:8]}")
    trace_id: str = Field(..., description="Mã định danh duy nhất của lượt gọi SSE stream")
    session_id: str = Field(..., description="Mã phiên hội thoại")
    turn_index: int = Field(default=1, description="Thứ tự lượt hỏi trong phiên")
    prompt: str = Field(..., description="Câu hỏi gốc của người dùng")
    error_category: ErrorCategoryEnum = Field(..., description="Nhóm lỗi theo chuẩn phân loại")
    severity: FeedbackSeverityEnum = Field(default=FeedbackSeverityEnum.MAJOR, description="Mức độ nghiêm trọng")
    user_note: str = Field(..., description="Nhận xét, mô tả chi tiết lỗi của người dùng")
    expected_behavior: Optional[str] = Field(None, description="Hành vi hoặc kết quả mong muốn")
    expected_route: Optional[str] = Field(None, description="Đường dẫn định tuyến kỳ vọng (nếu biết)")
    actual_route: Optional[str] = Field(None, description="Tuyến bot đã thực tế điều hướng")
    actual_intent: Optional[str] = Field(None, description="Ý định bot đã nhận diện")
    active_quest_snapshot: Optional[Dict[str, Any]] = Field(None, description="Trạng thái ActiveQuestFrame tại thời điểm lỗi")
    status: Literal["OPEN", "ANALYZING", "RESOLVED", "CONVERTED_TO_TEST"] = Field(default="OPEN", description="Trạng thái xử lý")
    tags: List[str] = Field(default_factory=list, description="Thẻ gắn kèm tiện lọc tìm kiếm")
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    resolved_at: Optional[str] = Field(None, description="Thời điểm đánh dấu đã khắc phục")
    resolution_notes: Optional[str] = Field(None, description="Ghi chú giải pháp khắc phục của kỹ sư/Agent")
