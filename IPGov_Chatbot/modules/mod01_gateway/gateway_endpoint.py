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
    history: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    """
    Generator bất đồng bộ điều phối luồng SSE:
    1. Trích xuất User Context từ JWT (Module 1), hỗ trợ tenant_code và level truyền từ prompt hoặc payload.
    2. Phát Event 1 `connected` (< 50ms TTFE).
    3. Thực hiện tiền kiểm duyệt an toàn Guardrails (Module 2).
    4. Phản hồi cảnh báo nếu vi phạm hoặc chuẩn bị chuyển tiếp sang Router.
    """
    # 0. Trích xuất tenant_code và level nếu đã ở sẵn trong prompt (ví dụ: [tenant_code=68, level=0] ...)
    clean_prompt = prompt.strip()
    extracted_tenant = client_tenant
    extracted_level = client_level

    prefix_match = re.match(
        r"^\[\s*tenant_code\s*[=:]\s*(?P<tenant>[^,\]]+)\s*,\s*level\s*[=:]\s*(?P<level>\d+)\s*\]\s*(?P<rest>.*)$",
        clean_prompt,
        re.IGNORECASE | re.DOTALL
    )
    if prefix_match:
        if extracted_tenant is None:
            extracted_tenant = prefix_match.group("tenant").strip()
        if extracted_level is None:
            try:
                extracted_level = int(prefix_match.group("level").strip())
            except ValueError:
                pass
        rest_text = prefix_match.group("rest").strip()
        if rest_text:
            clean_prompt = rest_text

    # 1. Trích xuất User Context
    try:
        if auth_header:
            user_ctx = ContextExtractor.extract_from_auth_header(auth_header)
            # Cho phép ghi đè nếu client/prompt chỉ định rõ level hoặc tenant khác
            if (extracted_level is not None and user_ctx.role_level != extracted_level) or \
               (extracted_tenant is not None and user_ctx.tenant_code != extracted_tenant):
                user_ctx = UserSecurityContextDTO(
                    user_id=user_ctx.user_id,
                    username=user_ctx.username,
                    tenant_code=extracted_tenant or user_ctx.tenant_code,
                    department_code=client_dept or user_ctx.department_code,
                    office_id=user_ctx.office_id,
                    role_level=extracted_level if extracted_level is not None else user_ctx.role_level
                )
        else:
            # Fallback thông minh theo level hoặc role
            lvl = extracted_level if extracted_level is not None else 3
            t_code = extracted_tenant or "68"
            role_key = (client_role or "").lower()

            if "tphcm" in role_key or t_code == "79":
                if lvl == 0:
                    profile_key = "tphcm_province_leader"
                elif lvl == 1:
                    profile_key = "tphcm_so_noivu"
                else:
                    profile_key = "public_citizen"
            else:
                if lvl == 0 or role_key in ["phuong", "lanhdao", "leader", "tinh", "lamdong_leader"]:
                    profile_key = "lamdong_province_leader"
                elif lvl == 1 or role_key in ["so", "so_noivu", "lamdong_dept_noivu"]:
                    profile_key = "lamdong_province_leader"
                elif lvl == 2 or role_key in ["dn", "chuyenvien", "phong", "lamdong_phong_kinhte", "lamdong_phong_xaydung"]:
                    profile_key = "lamdong_phong_kinhte"
                else:
                    profile_key = "public_citizen"

            base_profile = SAMPLE_ROLE_PROFILES.get(profile_key, SAMPLE_ROLE_PROFILES["public_citizen"]).copy()
            if extracted_level is not None:
                base_profile["role_level"] = extracted_level
            if extracted_tenant is not None:
                base_profile["tenant_code"] = extracted_tenant
            if client_dept is not None:
                base_profile["department_code"] = client_dept

            token = JWTService.encode(base_profile)
            user_ctx = ContextExtractor.extract_from_auth_header(f"Bearer {token}")
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
        "role_level": extracted_level if extracted_level is not None else (user_ctx.role_level if user_ctx else 0),
        "tenant_code": extracted_tenant or (user_ctx.tenant_code if user_ctx else "68"),
        "department_code": client_dept or (user_ctx.department_code if user_ctx else None),
    }

    effective_session = session_id or session_ctx.session_id or "default_session"
    async for sse_chunk in warehouse_agent.run_stream(
        query=guardrail_result.sanitized_prompt,
        session_id=effective_session,
        user_context=agent_user_ctx,
        history=history,
    ):
        yield sse_chunk
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
    async for chunk in chat_sse_event_generator(
        prompt=raw_prompt,
        auth_header=authorization,
        session_id=req.session_id,
        client_ip=client_ip,
        client_role=req.role,
        client_level=req.level,
        client_tenant=req.tenant_code,
        client_dept=req.department_code,
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
                except Exception:
                    pass

    return {
        "success": True,
        "data": {
            "session_id": req.session_id or "default_session",
            "answer": full_answer,
            "tabular_data": tabular_data,
            "images": [],
            "youtube_links": [],
        }
    }

