"""
Module: IPGov_Chatbot/schemas/sse_events.py
Chức năng: Đặc tả hợp đồng các sự kiện luồng Server-Sent Events (SSE 11 sự kiện).
Tuân thủ chuẩn Blueprint 07 (Advanced Reasoning Provenance & Streaming UX).
"""

import json
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class SSEEventType(str, Enum):
    """11 sự kiện tiến trình suy luận và phản hồi theo Blueprint 07."""
    CONNECTED = "connected"
    INTENT_CLASSIFIED = "intent_classified"
    CLARIFICATION_REQUESTED = "clarification_requested"
    SCHEMA_PRUNED = "schema_pruned"
    SQL_GENERATED = "sql_generated"
    AST_VALIDATED = "ast_validated"
    SQL_EXECUTED = "sql_executed"
    CALCULATING = "calculating"
    CHUNK = "chunk"
    LINEAGE_RESOLVED = "lineage_resolved"
    DONE = "done"
    GUARDRAIL_BLOCKED = "guardrail_blocked"  # Sự kiện chặn sớm từ Module 2


class SSEMessage(BaseModel):
    """Mô hình đóng gói thông điệp SSE chuẩn format text/event-stream."""
    event: SSEEventType
    data: Dict[str, Any]
    id: Optional[str] = None
    retry: Optional[int] = None

    def to_sse_format(self) -> str:
        """Chuyển đổi thành chuỗi format MIME text/event-stream."""
        lines = []
        if self.id:
            lines.append(f"id: {self.id}")
        lines.append(f"event: {self.event.value}")
        lines.append(f"data: {json.dumps(self.data, ensure_ascii=False)}")
        return "\n".join(lines) + "\n\n"
