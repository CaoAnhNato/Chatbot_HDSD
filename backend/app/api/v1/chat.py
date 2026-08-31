from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
import os
from app.core.config import settings
from app.models.chat import ChatRequest, ChatResponse
from app.models.common import ApiResponse
from app.services.rag_service import rag_service
from app.services.chat_history_service import chat_history_service
from app.core.logger import logger

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ApiResponse[ChatResponse])
async def chat_endpoint(request: ChatRequest):
    try:
        response = await rag_service.process_chat(request)
        return ApiResponse(
            success=True,
            message="Generated response successfully",
            data=response
        )
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def chat_stream_endpoint(request: ChatRequest):
    """
    Server-Sent Events (SSE) streaming endpoint.
    Streams metadata and tokens in real-time.
    """
    try:
        return StreamingResponse(
            rag_service.process_chat_stream(request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    except Exception as e:
        logger.error(f"Chat stream endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/audit/export")
async def export_audit_log():
    """
    Direct download endpoint for the JSONL audit log file.
    """
    log_file = os.path.join(settings.LOG_DIR, settings.CHAT_AUDIT_LOG_FILE)
    if not os.path.exists(log_file):
        raise HTTPException(status_code=404, detail="Audit log file does not exist yet.")
    return FileResponse(
        path=log_file,
        filename="chat_audit.jsonl",
        media_type="application/x-jsonlines"
    )


@router.get("/history/{session_id}")
async def get_session_history(session_id: str):
    """
    Retrieves message history for a specific session directly from Supabase PostgreSQL.
    """
    try:
        messages = chat_history_service.get_session_messages(session_id)
        return ApiResponse(
            success=True,
            message=f"Retrieved {len(messages)} messages for session {session_id}",
            data=messages
        )
    except Exception as e:
        logger.error(f"Failed to fetch session history for {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

