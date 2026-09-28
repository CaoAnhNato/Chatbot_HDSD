"""
Module: IPGov_Chatbot/modules/mod01_gateway/sse_dispatcher.py
Chức năng: Quản lý luồng Server-Sent Events (SSE Dispatcher), phát sự kiện Event 1 (connected)
và đóng gói Snapshot Stage 1 (RequestSessionContextDTO).
Tuân thủ chuẩn Blueprint 07 (TTFE < 50ms).
"""

import json
import time
import uuid
from typing import AsyncGenerator, Dict, Any, Optional
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO
from IPGov_Chatbot.schemas.sse_events import SSEEventType, SSEMessage
from IPGov_Chatbot.schemas.guardrail_dto import RequestSessionContextDTO


class SSEDispatcher:
    """Bộ điều phối phát các sự kiện luồng SSE cho Client."""

    @classmethod
    def create_snapshot_stage_1(
        cls,
        raw_prompt: str,
        user_context: UserSecurityContextDTO,
        trace_id: Optional[str] = None,
        session_id: Optional[str] = None,
        client_ip: Optional[str] = None
    ) -> RequestSessionContextDTO:
        """Đóng gói dữ liệu đầu ra của Stage 1 thành Snapshot DTO phục vụ kiểm thử dây chuyền."""
        return RequestSessionContextDTO(
            trace_id=trace_id or str(uuid.uuid4()),
            session_id=session_id or f"sess_{uuid.uuid4().hex[:12]}",
            raw_prompt=raw_prompt,
            user_context=user_context,
            client_ip=client_ip,
            created_at_epoch=time.time()
        )

    @classmethod
    def build_connected_event(cls, session_ctx: RequestSessionContextDTO) -> str:
        """
        Sinh chuỗi SSE sự kiện đầu tiên `connected` (Event 1).
        Đảm bảo Time to First Event (TTFE) < 50ms để xác nhận kết nối hai chiều thành công.
        """
        msg = SSEMessage(
            event=SSEEventType.CONNECTED,
            data={
                "session_id": session_ctx.session_id,
                "trace_id": session_ctx.trace_id,
                "user_id": session_ctx.user_context.user_id,
                "tenant_code": session_ctx.user_context.tenant_code,
                "role_level": session_ctx.user_context.role_level,
                "timestamp": int(session_ctx.created_at_epoch * 1000),
                "message": "Kết nối thành công đến Trợ lý ảo Tra cứu DWH Chính phủ điện tử."
            }
        )
        return msg.to_sse_format()

    @classmethod
    def build_guardrail_blocked_event(
        cls,
        violation_type: str,
        message: str,
        trace_id: str
    ) -> str:
        """Sinh chuỗi SSE khi bị chặn sớm bởi Module 2 Pre-Router Guardrails."""
        msg = SSEMessage(
            event=SSEEventType.GUARDRAIL_BLOCKED,
            data={
                "status": "blocked",
                "violation_type": violation_type,
                "message": message,
                "trace_id": trace_id
            }
        )
        done_msg = SSEMessage(
            event=SSEEventType.DONE,
            data={"trace_id": trace_id, "status": "terminated_by_guardrails"}
        )
        return msg.to_sse_format() + done_msg.to_sse_format()
