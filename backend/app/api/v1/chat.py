import asyncio
import json
import os
import uuid
from typing import AsyncGenerator, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.core.config import settings
from app.core.logger import logger
from app.models.chat import ChatRequest, ChatResponse, QuickActionChip
from app.models.common import ApiResponse
from app.services.chat_history_service import chat_history_service
from app.services.rag_service import rag_service

try:
    from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import warehouse_agent
except ImportError:
    warehouse_agent = None

router = APIRouter(prefix="/chat", tags=["Chat"])


def is_warehouse_query(request: ChatRequest) -> bool:
    """
    Xác định xem yêu cầu người dùng có thuộc phạm vi kho dữ liệu DWH hay không (Zero Heuristics).
    """
    col = (request.collection or "").lower().strip()
    if col in ("dwh", "warehouse"):
        return True

    role = (request.role or "").lower().strip()
    if role in ("lanhdao", "chuyenvien", "dwh"):
        return True

    text = getattr(request, "effective_query", None) or request.query
    if not text:
        return False

    # 1. Kiểm tra an toàn phạm vi qua ScopePrechecker (chặn ngoài phạm vi)
    try:
        from IPGov_Chatbot.modules.mod02_guardrails.scope_prechecker import ScopePrechecker
        is_out, _, _ = ScopePrechecker.check_scope(text)
        if is_out:
            return False
    except Exception:
        pass

    # 2. Kiểm tra dynamic qua DuckDB Catalog RAM của warehouse_agent
    if warehouse_agent and hasattr(warehouse_agent, "catalog") and warehouse_agent.catalog:
        cat = warehouse_agent.catalog
        # Kiểm tra từ vựng danh mục qua DuckDB semantic_lexicon
        for category in (
            "METRIC_LIST_TRIGGER",
            "METRIC_LIST_TARGET",
            "REPORT_SIGNAL",
            "MISSION_KEYWORD",
            "OFFICER_QUERY",
            "FORM_CRITERIA_GROUP",
            "REPORT_STATUS",
            "REPORT_DIFF",
        ):
            if hasattr(cat, "has_lexicon_term") and cat.has_lexicon_term(text, category):
                return True
        # Khớp alias hoặc tên chỉ tiêu trong catalog
        if hasattr(cat, "match_alias_or_abbreviation"):
            matched = cat.match_alias_or_abbreviation(text)
            if matched:
                return True
        if hasattr(cat, "find_criteria_by_name"):
            crits = cat.find_criteria_by_name(text, limit=1)
            if crits:
                return True

    return False


async def stream_warehouse_agent(request: ChatRequest, session_id: str) -> AsyncGenerator[str, None]:
    """
    Stream SSE các stage và tokens từ WarehouseLangGraphAgent,
    đồng thời lưu vết vào Supabase/SQLite chat history khi hoàn tất.
    """
    effective_q = getattr(request, "effective_query", None) or request.query
    user_context = {
        "role_level": getattr(request, "level", 0) if getattr(request, "level", None) is not None else 0,
        "tenant_code": getattr(request, "tenant_code", None) or "68",
        "department_code": getattr(request, "department_code", None),
    }
    history = [{"role": m.role, "content": m.content} for m in request.history] if request.history else []
    full_answer_parts = []

    async for chunk in warehouse_agent.run_stream(
        query=effective_q,
        session_id=session_id,
        user_context=user_context,
        history=history,
    ):
        yield chunk
        if "event: done" in chunk:
            try:
                for line in chunk.split("\n"):
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if "full_answer" in data:
                            full_answer_parts.append(data["full_answer"])
            except Exception:
                pass

    if full_answer_parts:
        try:
            bot_resp = ChatResponse(
                session_id=session_id,
                answer=full_answer_parts[0],
                intent="dwh_autonomous_query",
                source_chunks=[],
                images=[],
                youtube_links=[],
                quick_action_chips=[]
            )
            asyncio.create_task(
                chat_history_service.save_chat_interaction_async(
                    session_id=session_id,
                    user_query=effective_q,
                    bot_response=bot_resp,
                    role=request.role or "lanhdao"
                )
            )
        except Exception as e:
            logger.warning(f"Could not persist warehouse chat to history: {e}")


@router.post("", response_model=ApiResponse[ChatResponse])
async def chat_endpoint(request: ChatRequest):
    try:
        if warehouse_agent is not None and is_warehouse_query(request):
            effective_q = getattr(request, "effective_query", None) or request.query
            session_id = request.session_id or f"session_{uuid.uuid4().hex[:8]}"
            user_context = {
                "role_level": getattr(request, "level", 0) if getattr(request, "level", None) is not None else 0,
                "tenant_code": getattr(request, "tenant_code", None) or "68",
                "department_code": getattr(request, "department_code", None),
            }
            history = [{"role": m.role, "content": m.content} for m in request.history] if request.history else []
            result = warehouse_agent.run(
                query=effective_q,
                session_id=session_id,
                user_context=user_context,
                history=history,
            )
            raw_chips = result.get("quick_action_chips") or []
            chips = []
            for i, c in enumerate(raw_chips):
                if isinstance(c, dict):
                    chips.append(QuickActionChip(
                        id=c.get("id", f"chip_{i}"),
                        label=str(c.get("label", "")),
                        query_text=str(c.get("query_text", ""))
                    ))
                elif isinstance(c, QuickActionChip):
                    chips.append(c)
                else:
                    chips.append(QuickActionChip(id=f"chip_{i}", label=str(c), query_text=str(c)))
            answer = result.get("answer") or "Đã hoàn thành tra cứu số liệu."
            chat_response = ChatResponse(
                session_id=session_id,
                answer=answer,
                source_chunks=[],
                images=[],
                youtube_links=[],
                quick_action_chips=chips,
                intent="dwh_autonomous_query"
            )
            try:
                asyncio.create_task(
                    chat_history_service.save_chat_interaction_async(
                        session_id=session_id,
                        user_query=effective_q,
                        bot_response=chat_response,
                        role=request.role or "lanhdao"
                    )
                )
            except Exception as e:
                logger.warning(f"Could not persist warehouse chat to history: {e}")

            return ApiResponse(
                success=True,
                message="Generated response successfully",
                data=chat_response
            )

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
    Streams metadata, real-time stage updates, and tokens in real-time.
    """
    try:
        if warehouse_agent is not None and is_warehouse_query(request):
            session_id = request.session_id or f"session_{uuid.uuid4().hex[:8]}"
            return StreamingResponse(
                stream_warehouse_agent(request, session_id),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )

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
    os.makedirs(settings.LOG_DIR, exist_ok=True)
    log_file = os.path.join(settings.LOG_DIR, settings.CHAT_AUDIT_LOG_FILE)
    if not os.path.exists(log_file):
        with open(log_file, "w", encoding="utf-8") as f:
            pass  # Create empty file
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


@router.get("/sessions")
async def get_all_sessions(limit: int = 50):
    """
    Retrieves latest chat sessions summary directly from Supabase PostgreSQL.
    """
    try:
        sessions = chat_history_service.get_all_sessions(limit=limit)
        return ApiResponse(
            success=True,
            message=f"Retrieved {len(sessions)} sessions",
            data=sessions
        )
    except Exception as e:
        logger.error(f"Failed to fetch sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
