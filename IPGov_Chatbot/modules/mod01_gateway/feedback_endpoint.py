"""
IPGov Chatbot - Module 01 Gateway: Feedback & Quest Annotation Endpoint
Cung cấp REST API tiếp nhận phản hồi lỗi từ Web UI và truy vấn danh sách ghi chú.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from IPGov_Chatbot.core.feedback_manager import FeedbackManager
from IPGov_Chatbot.schemas.feedback_dto import (
    ErrorCategoryEnum,
    FeedbackSeverityEnum,
    QuestAnnotationDTO,
)


router = APIRouter(prefix="/api/v1/chat", tags=["Quest Feedback & Annotations"])
feedback_mgr = FeedbackManager()


class FeedbackResponse(BaseModel):
    status: str
    annotation_id: str
    message: str


class ResolutionRequest(BaseModel):
    resolution_notes: str = Field(..., description="Mô tả cách thức đã khắc phục lỗi")


@router.post("/feedback", response_model=FeedbackResponse, summary="Gửi ghi chú phản hồi lỗi cho một quest")
async def submit_feedback(dto: QuestAnnotationDTO):
    """
    Tiếp nhận ghi chú phản hồi lỗi (Human-in-the-Loop) từ Web Test Bench hoặc Client:
    - Lưu trữ có cấu trúc vào logs/quest_annotations.jsonl
    - Đính kèm trace_id và session_id để tái hiện lỗi 100%
    """
    ok = feedback_mgr.save_annotation(dto)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể lưu trữ ghi chú phản hồi vào hệ thống log"
        )
    return FeedbackResponse(
        status="recorded",
        annotation_id=dto.annotation_id,
        message="Đã ghi nhận phản hồi lỗi thành công vào kho audit"
    )


@router.get("/feedback", summary="Truy vấn danh sách ghi chú phản hồi lỗi")
async def list_feedback(
    category: Optional[str] = Query(None, description="Lọc theo nhóm lỗi (ErrorCategory)"),
    severity: Optional[str] = Query(None, description="Lọc theo mức độ nghiêm trọng"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái (OPEN, RESOLVED...)"),
    keyword: Optional[str] = Query(None, description="Tìm kiếm từ khóa trong prompt hoặc note"),
    tag: Optional[str] = Query(None, description="Lọc theo tag"),
):
    """Truy vấn, lọc và tìm kiếm danh sách các ghi chú lỗi phục vụ debug."""
    items = feedback_mgr.search_annotations(keyword=keyword, tag=tag)

    if category:
        items = [i for i in items if i.error_category.value == category]
    if severity:
        items = [i for i in items if i.severity.value == severity]
    if status:
        items = [i for i in items if i.status == status]

    return {
        "total": len(items),
        "items": [i.model_dump() for i in items]
    }


@router.patch("/feedback/{annotation_id}/resolve", summary="Đánh dấu ghi chú lỗi đã được khắc phục")
async def resolve_feedback(annotation_id: str, req: ResolutionRequest):
    """Cập nhật trạng thái ghi chú sang RESOLVED kèm giải pháp khắc phục."""
    ok = feedback_mgr.mark_resolved(annotation_id, resolution_notes=req.resolution_notes)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy ghi chú với mã {annotation_id}"
        )
    return {"status": "resolved", "annotation_id": annotation_id}
