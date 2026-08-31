from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models.chat import ChatRequest, ChatResponse
from app.models.common import ApiResponse
from app.services.rag_service import rag_service
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
