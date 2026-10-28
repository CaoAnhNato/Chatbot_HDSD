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
import re
from IPGov_Chatbot.modules.mod01_gateway.context_extractor import ContextExtractor, SAMPLE_ROLE_PROFILES
from IPGov_Chatbot.modules.mod01_gateway.jwt_service import JWTService
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO
from IPGov_Chatbot.modules.mod01_gateway.user_service import UserService, user_service
from IPGov_Chatbot.modules.mod01_gateway.sse_dispatcher import SSEDispatcher
from IPGov_Chatbot.modules.mod02_guardrails.guardrails_pipeline import GuardrailsPipeline
from IPGov_Chatbot.modules.mod03_router.intent_router import IntentRouter
from IPGov_Chatbot.modules.mod04_catalog.schema_pruner import SchemaPruner
from IPGov_Chatbot.modules.mod05_sql_compiler.compiler_facade import SQLCompilerFacade
from IPGov_Chatbot.modules.mod06_ast_enforcer.ast_enforcer_service import ASTEnforcerService
from IPGov_Chatbot.modules.mod07_dwh_exec.dwh_exec_service import DWHExecutionService
from IPGov_Chatbot.modules.mod08_response.response_synthesizer_service import ResponseSynthesizerService
from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import warehouse_agent
from IPGov_Chatbot.schemas.router_dto import RouteTypeEnum

logger = logging.getLogger(__name__)

_router_engine = IntentRouter()
_schema_pruner = SchemaPruner()
_compiler_facade = SQLCompilerFacade()
_ast_enforcer = ASTEnforcerService()
_dwh_exec = DWHExecutionService()
_synthesizer = ResponseSynthesizerService()


router = APIRouter(prefix="/api/v1/chat", tags=["IPGov Chat Gateway"])


class ChatStreamRequest(BaseModel):
    """Payload gửi lên từ Client (hỗ trợ cả bench lẫn Web Frontend)."""
    prompt: str | None = Field(None, description="Câu hỏi hoặc yêu cầu tra cứu của người dùng")
    query: str | None = Field(None, description="Tương thích ngược với Web Frontend Next.js")
    session_id: str | None = Field(None, description="Mã phiên hội thoại (nếu có)")
    user_id: str | None = Field(None, description="UUID tài khoản người dùng từ dwh_internal.user")
    user_name: str | None = Field(None, description="Tên người dùng hoặc chức danh")
    schema: str | None = Field(default="dwh_internal", description="Schema kho dữ liệu ('dwh_internal' hoặc 'dwh_public')")
    role: str | None = Field(None, description="Vai trò gửi từ frontend")
    level: int | None = Field(None, description="Cấp độ phân quyền HBAC (0: Tỉnh, 1: Sở, 2: Phòng, 3: Công dân)")
    tenant_code: str | None = Field(None, description="Mã tỉnh/thành phố (ví dụ: '68', '79')")
    department_code: str | None = Field(None, description="Mã phòng ban/sở ngành")
    history: list[dict] | None = Field(None, description="Lịch sử hội thoại")
    collection: str | None = Field(None, description="Collection name")


async def chat_sse_event_generator(
    prompt: str,
    auth_header: str | None,
    session_id: str | None,
    client_ip: str | None,
    client_role: str | None = None,
    client_level: int | None = None,
    client_tenant: str | None = None,
    client_dept: str | None = None,
    client_user_id: str | None = None,
    client_user_name: str | None = None,
    client_schema: str | None = None,
    history: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    """
    Generator bất đồng bộ điều phối luồng SSE:
    1. Trích xuất User Context từ UserService/JWT, hỗ trợ [user=..., level=..., tenant_code=..., schema=...] prefix hoặc payload.
    2. Phát Event 1 `connected` (< 50ms TTFE).
    3. Thực hiện tiền kiểm duyệt an toàn Guardrails (Module 2).
    4. Phản hồi cảnh báo nếu vi phạm hoặc chuẩn bị chuyển tiếp sang Router.
    """
    clean_prompt = prompt.strip()
    extracted_tenant = client_tenant
    extracted_level = client_level
    extracted_user = client_user_id or client_user_name or client_role
    extracted_schema = "dwh_public" if str(client_schema or "").strip().lower() == "dwh_public" else "dwh_internal"
    extracted_dept = client_dept

    # Trích xuất linh hoạt các tags [user=boss, level=4, tenant_code=68, schema=dwh_internal]
    prefix_match = re.match(
        r"^\[(?P<tags>[^\]]+)\]\s*(?P<rest>.*)$",
        clean_prompt,
        re.IGNORECASE | re.DOTALL
    )
    if prefix_match:
        tags_str = prefix_match.group("tags")
        for item in tags_str.split(","):
            if "=" in item or ":" in item:
                sep = "=" if "=" in item else ":"
                k, v = item.split(sep, 1)
                k_clean = k.strip().lower()
                v_clean = v.strip()
                if k_clean in ("user", "username", "user_id", "user_name", "name"):
                    extracted_user = v_clean
                elif k_clean in ("level", "role_level"):
                    try:
                        extracted_level = int(v_clean)
                    except ValueError:
                        pass
                elif k_clean in ("tenant_code", "tenant"):
                    extracted_tenant = v_clean
                elif k_clean in ("schema", "target_schema"):
                    extracted_schema = "dwh_public" if str(v_clean or "").strip().lower() == "dwh_public" else "dwh_internal"
                elif k_clean in ("dept", "department", "department_code"):
                    extracted_dept = v_clean
                elif k_clean == "role":
                    if not extracted_user:
                        extracted_user = v_clean
        rest_text = prefix_match.group("rest").strip()
        if rest_text:
            clean_prompt = rest_text

    # 1. Trích xuất User Context
    try:
        if auth_header and not extracted_user:
            user_ctx = ContextExtractor.extract_from_auth_header(auth_header)
            user_ctx.schema = extracted_schema
            if extracted_tenant is not None:
                user_ctx.tenant_code = extracted_tenant
            if extracted_dept is not None:
                user_ctx.department_code = extracted_dept
        else:
            user_ctx = user_service.build_user_context(
                user_identifier=extracted_user or client_role,
                role_level=extracted_level,
                schema=extracted_schema,
                tenant_code=extracted_tenant or "68",
                department_code=extracted_dept,
            )
    except Exception as e:
        err_event = f"event: error\ndata: {{\"error\": \"Xác thực thất bại: {str(e)}\", \"message\": \"Xác thực thất bại: {str(e)}\"}}\n\n"
        yield err_event
        return

    # 2. Khởi tạo Snapshot Stage 1 & phát Event 1 (connected)
    session_ctx = SSEDispatcher.create_snapshot_stage_1(
        raw_prompt=clean_prompt,
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
        block_msg = guardrail_result.violation_message or "Yêu cầu bị từ chối do vi phạm quy tắc an toàn."
        # Phát token cho web frontend
        token_payload = {"content": f"⚠️ {block_msg}", "trace_id": session_ctx.trace_id}
        yield f"event: token\ndata: {json.dumps(token_payload, ensure_ascii=False)}\n\n"
        # Chặn sớm và phát event guardrail_blocked
        yield SSEDispatcher.build_guardrail_blocked_event(
            violation_type=guardrail_result.violation_type.value,
            message=block_msg,
            trace_id=session_ctx.trace_id
        )
        done_payload = {
            "trace_id": session_ctx.trace_id,
            "status": "blocked_by_guardrail",
            "route": "SECURITY_DENIAL",
            "full_answer": f"⚠️ {block_msg}"
        }
        yield f"event: done\ndata: {json.dumps(done_payload, ensure_ascii=False)}\n\n"
        return

    # 4. Khi vượt qua Guardrails: Thông báo an toàn và điều phối toàn trình qua Autonomous Warehouse Agent
    progress_payload = {
        "step": "guardrails_passed",
        "message": "Yêu cầu an toàn. Đang chuyển tiếp sang bộ điều phối kho dữ liệu...",
        "trace_id": session_ctx.trace_id,
    }
    yield f"event: thought_progress\ndata: {json.dumps(progress_payload, ensure_ascii=False)}\n\n"

    agent_user_ctx = {
        "user_id": user_ctx.user_id,
        "username": user_ctx.username,
        "name": user_ctx.name or user_ctx.user_name,
        "user_name": user_ctx.user_name or user_ctx.name,
        "role_level": user_ctx.role_level,
        "tenant_code": user_ctx.tenant_code or extracted_tenant or "68",
        "department_code": user_ctx.department_code or extracted_dept,
        "schema": user_ctx.schema or extracted_schema or "dwh_internal",
        "assigned_mission_ids": user_ctx.assigned_mission_ids or [],
        "assigned_mission_names": user_ctx.assigned_mission_names or [],
        "is_unrestricted": user_ctx.is_unrestricted,
    }

    effective_session = session_id or session_ctx.session_id or "default_session"
    saved_full_answer = ""
    saved_tabular_data = None
    saved_chips = None
    async for sse_chunk in warehouse_agent.run_stream(
        query=guardrail_result.sanitized_prompt,
        session_id=effective_session,
        user_context=agent_user_ctx,
        history=history,
    ):
        for line in sse_chunk.split("\n"):
            if line.startswith("data: "):
                try:
                    payload = json.loads(line[6:])
                    if payload.get("full_answer"):
                        saved_full_answer = payload["full_answer"]
                    if payload.get("tabular_data"):
                        saved_tabular_data = payload["tabular_data"]
                    if payload.get("quick_action_chips"):
                        saved_chips = payload["quick_action_chips"]
                except Exception:
                    pass
        yield sse_chunk

    if session_id and saved_full_answer:
        try:
            from IPGov_Chatbot.core.chat_history_store import ChatHistoryStore
            ChatHistoryStore.get_instance().save_turn(
                session_id=session_id,
                user_prompt=prompt,
                assistant_answer=saved_full_answer,
                role=client_role or "phuong",
                level=agent_user_ctx["role_level"],
                tenant_code=agent_user_ctx["tenant_code"],
                tabular_data=saved_tabular_data,
                quick_action_chips=saved_chips,
            )
        except Exception as e:
            logger.warning("Could not persist turn to ChatHistoryStore: %s", e)
    return


@router.post("/stream", summary="Kết nối Server-Sent Events tra cứu dữ liệu DWH")
async def chat_stream_endpoint(
    req: ChatStreamRequest,
    request: Request,
    authorization: str | None = Header(None, alias="Authorization")
):
    """
    Endpoint tiếp nhận prompt tra cứu và mở luồng SSE stream.
    Yêu cầu Header `Authorization: Bearer <token>` hoặc tự động fallback theo vai trò (Role Mapping).
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    raw_prompt = (req.prompt or req.query or "").strip()
    if not raw_prompt:
        raise HTTPException(status_code=400, detail="Vui lòng cung cấp nội dung câu hỏi (prompt hoặc query).")
    
    return StreamingResponse(
        chat_sse_event_generator(
            prompt=raw_prompt,
            auth_header=authorization,
            session_id=req.session_id,
            client_ip=client_ip,
            client_role=req.role,
            client_level=req.level,
            client_tenant=req.tenant_code,
            client_dept=req.department_code,
            client_user_id=req.user_id,
            client_user_name=req.user_name,
            client_schema=req.schema,
            history=req.history,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("", summary="Tra cứu dữ liệu DWH đồng bộ")
@router.post("/", summary="Tra cứu dữ liệu DWH đồng bộ (trailing slash)")
async def chat_sync_endpoint(
    req: ChatStreamRequest,
    request: Request,
    authorization: str | None = Header(None, alias="Authorization")
):
    """Cung cấp endpoint đồng bộ dạng JSON cho các client không hỗ trợ SSE stream."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    raw_prompt = (req.prompt or req.query or "").strip()
    if not raw_prompt:
        raise HTTPException(status_code=400, detail="Vui lòng cung cấp nội dung câu hỏi (prompt hoặc query).")

    full_answer = ""
    tabular_data = None
    quick_action_chips = []
    async for chunk in chat_sse_event_generator(
        prompt=raw_prompt,
        auth_header=authorization,
        session_id=req.session_id,
        client_ip=client_ip,
        client_role=req.role,
        client_level=req.level,
        client_tenant=req.tenant_code,
        client_dept=req.department_code,
        client_user_id=req.user_id,
        client_user_name=req.user_name,
        client_schema=req.schema,
        history=req.history,
    ):
        for line in chunk.split("\n"):
            if line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                    if "full_answer" in data and data["full_answer"]:
                        full_answer = data["full_answer"]
                    if "tabular_data" in data and data["tabular_data"]:
                        tabular_data = data["tabular_data"]
                    if "quick_action_chips" in data and data["quick_action_chips"]:
                        quick_action_chips = data["quick_action_chips"]
                except Exception:
                    pass

    return {
        "success": True,
        "data": {
            "session_id": req.session_id or "default_session",
            "answer": full_answer,
            "tabular_data": tabular_data,
            "quick_action_chips": quick_action_chips,
            "images": [],
            "youtube_links": [],
        }
    }


# Router chuyên trách cấp phép danh mục người dùng theo chuẩn /api/v1/users
users_router = APIRouter(prefix="/api/v1", tags=["IPGov User Classification"])


@users_router.get("/users", summary="Danh sách tài khoản công vụ phân cấp từ kho DWH")
async def list_users():
    """Trả về danh sách 8 tài khoản công vụ phân cấp theo 5 bậc thẩm quyền."""
    return await UserService.get_instance().get_users()


@router.get("/users", summary="Danh sách tài khoản công vụ phân cấp từ kho DWH (prefix /chat/users)")
async def list_users_chat():
    return await UserService.get_instance().get_users()


