"""
Module: IPGov_Chatbot/modules/mod01_gateway/gateway_endpoint.py
Chức năng: FastAPI Router cho endpoint /api/v1/chat/stream kết nối giao thức Server-Sent Events.
Tích hợp ContextExtractor (Module 1) và GuardrailsPipeline (Module 2).
"""

import asyncio
from typing import AsyncGenerator
from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import json
import logging
from IPGov_Chatbot.modules.mod01_gateway.context_extractor import ContextExtractor
from IPGov_Chatbot.modules.mod01_gateway.sse_dispatcher import SSEDispatcher
from IPGov_Chatbot.modules.mod02_guardrails.guardrails_pipeline import GuardrailsPipeline
from IPGov_Chatbot.modules.mod03_router.intent_router import IntentRouter
from IPGov_Chatbot.modules.mod04_catalog.schema_pruner import SchemaPruner
from IPGov_Chatbot.schemas.router_dto import RouteTypeEnum

logger = logging.getLogger(__name__)

_router_engine = IntentRouter()
_schema_pruner = SchemaPruner()


router = APIRouter(prefix="/api/v1/chat", tags=["IPGov Chat Gateway"])


class ChatStreamRequest(BaseModel):
    """Payload gửi lên từ Client."""
    prompt: str = Field(..., min_length=1, max_length=4000, description="Câu hỏi hoặc yêu cầu tra cứu của người dùng")
    session_id: str | None = Field(None, description="Mã phiên hội thoại (nếu có)")


async def chat_sse_event_generator(
    prompt: str,
    auth_header: str | None,
    session_id: str | None,
    client_ip: str | None
) -> AsyncGenerator[str, None]:
    """
    Generator bất đồng bộ điều phối luồng SSE:
    1. Trích xuất User Context từ JWT (Module 1).
    2. Phát Event 1 `connected` (< 50ms TTFE).
    3. Thực hiện tiền kiểm duyệt an toàn Guardrails (Module 2).
    4. Phản hồi cảnh báo nếu vi phạm hoặc chuẩn bị chuyển tiếp sang Router.
    """
    # 1. Trích xuất User Context
    try:
        user_ctx = ContextExtractor.extract_from_auth_header(auth_header)
    except Exception as e:
        # Nếu lỗi JWT, phát event lỗi và ngắt kết nối
        err_event = f"event: error\ndata: {{\"error\": \"Xác thực thất bại: {str(e)}\"}}\n\n"
        yield err_event
        return

    # 2. Khởi tạo Snapshot Stage 1 & phát Event 1 (connected)
    session_ctx = SSEDispatcher.create_snapshot_stage_1(
        raw_prompt=prompt,
        user_context=user_ctx,
        session_id=session_id,
        client_ip=client_ip
    )
    yield SSEDispatcher.build_connected_event(session_ctx)

    # Đệm nhẹ 20ms mô phỏng I/O không phong tỏa
    await asyncio.sleep(0.02)

    # 3. Tiền kiểm duyệt an toàn qua Module 2 (Pre-Router Guardrails)
    guardrail_result = GuardrailsPipeline.evaluate(session_ctx)

    if not guardrail_result.is_safe:
        # Chặn sớm và phát event guardrail_blocked
        yield SSEDispatcher.build_guardrail_blocked_event(
            violation_type=guardrail_result.violation_type.value,
            message=guardrail_result.violation_message or "Yêu cầu bị từ chối do vi phạm quy tắc an toàn.",
            trace_id=session_ctx.trace_id
        )
        return

    # 4. Khi vượt qua Guardrails: Thông báo an toàn và thực thi định tuyến Module 3 (Router & H-DFT)
    yield f"event: thought_progress\ndata: {{\"step\": \"guardrails_passed\", \"message\": \"Yêu cầu an toàn. Đang chuyển tiếp sang bộ định tuyến...\", \"trace_id\": \"{session_ctx.trace_id}\"}}\n\n"

    # Định tuyến câu hỏi qua Module 3
    router_output = _router_engine.route_query(
        prompt=guardrail_result.sanitized_prompt,
        session_id=session_ctx.session_id or "default_session",
        user_context=user_ctx
    )

    # Phát Event router_routed
    routed_data = {
        "route": router_output.route.value,
        "intent": router_output.intent.value,
        "persona": router_output.persona.value,
        "active_quest_action": router_output.active_quest_action.value,
        "latency_ms": router_output.latency_ms,
        "trace_id": session_ctx.trace_id
    }
    yield f"event: router_routed\ndata: {json.dumps(routed_data, ensure_ascii=False)}\n\n"

    # Nếu là Chitchat Bypass hoặc Catalog Discovery: Trả lời trực tiếp và hoàn thành
    if router_output.bypass_response:
        content_payload = {"chunk": router_output.bypass_response, "trace_id": session_ctx.trace_id}
        yield f"event: content_chunk\ndata: {json.dumps(content_payload, ensure_ascii=False)}\n\n"
        if router_output.action_chips:
            chips_payload = {"chips": router_output.action_chips, "trace_id": session_ctx.trace_id}
            yield f"event: action_chips\ndata: {json.dumps(chips_payload, ensure_ascii=False)}\n\n"
        yield f"event: done\ndata: {{\"trace_id\": \"{session_ctx.trace_id}\", \"status\": \"completed\", \"route\": \"{router_output.route.value}\"}}\n\n"
        return

    # Nếu cần làm rõ (Clarification)
    if router_output.route == RouteTypeEnum.CLARIFICATION:
        clarify_payload = {
            "message": router_output.bypass_response or "Vui lòng chọn thông tin bổ sung:",
            "missing_slots": router_output.missing_slots,
            "options": [opt.model_dump() for opt in router_output.clarification_options],
            "trace_id": session_ctx.trace_id
        }
        yield f"event: clarification_requested\ndata: {json.dumps(clarify_payload, ensure_ascii=False)}\n\n"
        yield f"event: done\ndata: {{\"trace_id\": \"{session_ctx.trace_id}\", \"status\": \"clarification_needed\", \"route\": \"CLARIFICATION\"}}\n\n"
        return

    # Nếu là Fast Track / DAG / Single SQL / Catalog Dimension: Chuyển tiếp Module 4 Schema Pruner
    try:
        pruned_schema = _schema_pruner.prune_schema(router_output, user_ctx=user_ctx, trace_id=session_ctx.trace_id)
        pruned_payload = {
            "step": "schema_pruned",
            "selected_tables": pruned_schema.selected_tables,
            "bridge_tables": pruned_schema.bridge_tables,
            "join_paths": [jp.model_dump() for jp in pruned_schema.join_paths],
            "schema_slice_ddl": pruned_schema.schema_slice_ddl,
            "trace_id": session_ctx.trace_id,
            "latency_ms": pruned_schema.latency_ms,
        }
        yield f"event: thought_progress\ndata: {json.dumps(pruned_payload, ensure_ascii=False)}\n\n"
    except Exception as e:
        logger.error(f"Lỗi thực thi SchemaPruner trong Gateway stream: {e}")

    yield f"event: done\ndata: {{\"trace_id\": \"{session_ctx.trace_id}\", \"status\": \"ready_for_sql_generator\", \"route\": \"{router_output.route.value}\"}}\n\n"


@router.post("/stream", summary="Kết nối Server-Sent Events tra cứu dữ liệu DWH")
async def chat_stream_endpoint(
    req: ChatStreamRequest,
    request: Request,
    authorization: str | None = Header(None, alias="Authorization")
):
    """
    Endpoint tiếp nhận prompt tra cứu và mở luồng SSE stream.
    Yêu cầu Header `Authorization: Bearer <token>`.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    
    return StreamingResponse(
        chat_sse_event_generator(
            prompt=req.prompt,
            auth_header=authorization,
            session_id=req.session_id,
            client_ip=client_ip
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
