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
    """Bảng phân loại nhóm lỗi có cấu trúc (Standardized Error Taxonomy)."""
    ROUTING_MISMATCH = "ROUTING_MISMATCH"             # Nhầm lẫn luồng định tuyến (Chitchat, FastTrack, DAG...)
    SLOT_EXTRACTION_ERROR = "SLOT_EXTRACTION_ERROR"   # Bắt sai địa bàn (Huyện/Xã), sai năm hoặc sai chỉ tiêu
    ANAPHORA_RESOLUTION_FAIL = "ANAPHORA_FAIL"        # Không kế thừa được đại từ ("ở đó", "số lượng này")
    TOPIC_SHIFT_FAILED = "TOPIC_SHIFT_FAILED"         # Không xóa sạch context cũ khi đổi chủ đề
    GUARDRAIL_FALSE_POSITIVE = "GUARDRAIL_FALSE_POS"  # Câu hỏi nghiệp vụ hợp lệ nhưng bị chặn nhầm
    GUARDRAIL_FALSE_NEGATIVE = "GUARDRAIL_FALSE_NEG"  # Lọt câu hỏi tấn công/dò PII mà không bị chặn
    SQL_LOGIC_ERROR = "SQL_LOGIC_ERROR"               # Sinh mã SQL sai cú pháp hoặc sai logic nghiệp vụ
    DATA_FRESHNESS_ISSUE = "DATA_FRESHNESS_ISSUE"     # Số liệu cũ, không đồng bộ kịp với kho DWH
    RESPONSE_TONE_INCORRECT = "TONE_INCORRECT"        # Sai Persona (Lãnh đạo nhưng phản hồi thiếu chuẩn mực)
    OTHER = "OTHER"                                   # Các lỗi khác (yêu cầu ghi chú mô tả)


class FeedbackSeverityEnum(str, Enum):
    """Mức độ nghiêm trọng của lỗi được báo cáo."""
    CRITICAL = "CRITICAL"  # Sập pipeline, vi phạm an ninh, rò rỉ PII
    MAJOR = "MAJOR"        # Trả về kết quả sai lệch hoàn toàn, sai tuyến điều hướng
    MINOR = "MINOR"        # Văn phong chưa tối ưu, chậm nhẹ, gợi ý chip chưa sát


class QuestAnnotationDTO(BaseModel):
    """
    Hợp đồng dữ liệu một lượt ghi chú phản hồi lỗi (Quest Annotation).
    Liên kết chặt chẽ giữa câu hỏi, phản hồi, trạng thái máy đàm thoại và nhận xét của người dùng.
    """
    model_config = ConfigDict(frozen=False)

    annotation_id: str = Field(default_factory=lambda: f"note_{uuid.uuid4().hex[:8]}")
    trace_id: str = Field(..., description="Mã định danh duy nhất của lượt gọi SSE stream")
    session_id: str = Field(..., description="Mã phiên hội thoại")
    turn_index: int = Field(default=1, description="Thứ tự lượt hỏi trong phiên")
    prompt: str = Field(..., description="Câu hỏi gốc của người dùng")

    # Phân loại có cấu trúc
    error_category: ErrorCategoryEnum = Field(..., description="Nhóm lỗi theo chuẩn phân loại")
    severity: FeedbackSeverityEnum = Field(default=FeedbackSeverityEnum.MAJOR, description="Mức độ nghiêm trọng")

    # Nội dung ghi chú của con người (HITL Note)
    user_note: str = Field(..., description="Nhận xét, mô tả chi tiết lỗi của người dùng")
    expected_behavior: Optional[str] = Field(None, description="Hành vi hoặc kết quả mong muốn")
    expected_route: Optional[str] = Field(None, description="Đường dẫn định tuyến kỳ vọng (nếu biết)")

    # Execution Snapshot đính kèm để phục vụ tái hiện lỗi 100%
    actual_route: Optional[str] = Field(None, description="Tuyến bot đã thực tế điều hướng")
    actual_intent: Optional[str] = Field(None, description="Ý định bot đã nhận diện")
    active_quest_snapshot: Optional[Dict[str, Any]] = Field(None, description="Trạng thái ActiveQuestFrame tại thời điểm lỗi")

    # Trạng thái vòng đời giải quyết lỗi
    status: Literal["OPEN", "ANALYZING", "RESOLVED", "CONVERTED_TO_TEST"] = Field(default="OPEN", description="Trạng thái xử lý")
    tags: List[str] = Field(default_factory=list, description="Thẻ gắn kèm tiện lọc tìm kiếm")
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    resolved_at: Optional[str] = Field(None, description="Thời điểm đánh dấu đã khắc phục")
    resolution_notes: Optional[str] = Field(None, description="Ghi chú giải pháp khắc phục của kỹ sư/Agent")
