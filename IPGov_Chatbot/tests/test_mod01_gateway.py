"""
Unit tests cho Module 1: API Gateway & Context Extraction.
Kiểm tra JWT encode/decode, 6 profiles phân quyền, và SSE dispatcher.
"""

import pytest
import time
from IPGov_Chatbot.modules.mod01_gateway.jwt_service import JWTService
from IPGov_Chatbot.modules.mod01_gateway.context_extractor import (
    ContextExtractor,
    SAMPLE_ROLE_PROFILES
)
from IPGov_Chatbot.modules.mod01_gateway.sse_dispatcher import SSEDispatcher


def test_jwt_encode_decode_success():
    """Kiểm tra mã hóa và giải mã JWT thành công."""
    payload = {"user_id": "test_001", "role_level": 0, "tenant_code": "68"}
    token = JWTService.encode(payload)
    decoded = JWTService.decode(token)
    assert decoded["user_id"] == "test_001"
    assert decoded["tenant_code"] == "68"
    assert decoded["role_level"] == 0
    assert "exp" in decoded


def test_jwt_tampered_signature_fails():
    """Kiểm tra phát hiện chữ ký bị sửa đổi trái phép."""
    payload = {"user_id": "test_002", "role_level": 1}
    token = JWTService.encode(payload)
    parts = token.split(".")
    # Sửa đổi payload nhưng giữ nguyên signature
    tampered_payload = parts[1] + "tamper"
    tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"
    with pytest.raises(ValueError, match="không hợp lệ"):
        JWTService.decode(tampered_token)


def test_jwt_expired_token_fails():
    """Kiểm tra từ chối token đã hết hạn."""
    payload = {"user_id": "test_003"}
    # Token hết hạn ngay lập tức (-10s)
    token = JWTService.encode(payload, expires_in_seconds=-10)
    with pytest.raises(ValueError, match="hết hạn"):
        JWTService.decode(token)


def test_context_extractor_all_sample_profiles():
    """Kiểm tra trích xuất đúng 6 Profiles mẫu chuẩn hóa."""
    for profile_key in SAMPLE_ROLE_PROFILES:
        token = ContextExtractor.generate_token_for_profile(profile_key)
        auth_header = f"Bearer {token}"
        user_ctx = ContextExtractor.extract_from_auth_header(auth_header)
        
        expected = SAMPLE_ROLE_PROFILES[profile_key]
        assert user_ctx.tenant_code == expected["tenant_code"]
        assert user_ctx.role_level == expected["role_level"]
        assert user_ctx.department_code == expected["department_code"]


def test_sse_dispatcher_connected_event_format():
    """Kiểm tra SSE Event 1: connected được định dạng chuẩn xác."""
    token = ContextExtractor.generate_token_for_profile("lamdong_province_leader")
    user_ctx = ContextExtractor.extract_from_auth_header(f"Bearer {token}")
    
    session_ctx = SSEDispatcher.create_snapshot_stage_1(
        raw_prompt="Tổng số vụ tai nạn lao động năm 2025 là bao nhiêu?",
        user_context=user_ctx
    )
    
    sse_output = SSEDispatcher.build_connected_event(session_ctx)
    assert sse_output.startswith("event: connected\ndata: {")
    assert '"tenant_code": "68"' in sse_output
    assert '"role_level": 0' in sse_output
    assert sse_output.endswith("\n\n")
