"""
Module: IPGov_Chatbot/tests/test_stream_pipeline_integration.py
Chức năng: Kiểm thử tích hợp luồng SSE hoàn chỉnh từ Module 01 đến Module 07.
Xác nhận các sự kiện: connected, thought_progress, router_routed, sql_generated, ast_sanitized, db_executed, done.
"""

import pytest
from IPGov_Chatbot.modules.mod01_gateway.gateway_endpoint import chat_sse_event_generator
from IPGov_Chatbot.modules.mod01_gateway.jwt_service import JWTService


@pytest.mark.asyncio
async def test_full_pipeline_stream_integration():
    """Kiểm thử luồng SSE xuyên suốt 7 modules với câu hỏi nghiệp vụ thực tế."""
    payload = {
        "user_id": "test_leader",
        "username": "lanhdao_so",
        "role_level": 0,
        "tenant_code": "68",
        "department_code": None,
    }
    token = JWTService.encode(payload)
    auth_header = f"Bearer {token}"

    prompt = "Xếp hạng 5 huyện, thành phố có kinh phí giải ngân khuyến công cao nhất toàn tỉnh năm 2025?"
    events = []

    async for chunk in chat_sse_event_generator(
        prompt=prompt,
        auth_header=auth_header,
        session_id="test_pipeline_e2e_01",
        client_ip="127.0.0.1",
    ):
        if chunk.startswith("event:"):
            lines = chunk.strip().split("\n")
            event_name = lines[0].replace("event:", "").strip()
            events.append(event_name)

    # Khẳng định sự hiện diện của chuỗi sự kiện tuần tự xuyên suốt 8 modules
    assert "connected" in events
    assert "router_routed" in events
    assert "sql_generated" in events
    assert "ast_sanitized" in events
    assert "db_executed" in events
    assert "content_chunk" in events
    assert "lineage_resolved" in events
    assert "done" in events
