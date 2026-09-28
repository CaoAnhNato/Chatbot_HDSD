"""
Module: IPGov_Chatbot/tests/test_enterprise_modules_suites.py
Chức năng: Bộ kiểm thử tự động toàn diện chạy trực tiếp từ 2 tệp JSON:
  1. evaluations/module_01_gateway_test_cases.json (31 cases)
  2. evaluations/module_02_guardrails_test_cases.json (50 cases)
Tuân thủ /verification-before-completion và ipgov-coding-rules.md.
"""

import json
import re
import time
import uuid
from pathlib import Path
import pytest
from pydantic import ValidationError

from IPGov_Chatbot.modules.mod01_gateway.jwt_service import JWTService
from IPGov_Chatbot.modules.mod01_gateway.context_extractor import (
    ContextExtractor,
    SAMPLE_ROLE_PROFILES
)
from IPGov_Chatbot.modules.mod01_gateway.sse_dispatcher import SSEDispatcher
from IPGov_Chatbot.modules.mod01_gateway.gateway_endpoint import ChatStreamRequest
from IPGov_Chatbot.modules.mod02_guardrails.guardrails_pipeline import GuardrailsPipeline
from IPGov_Chatbot.schemas.guardrail_dto import ViolationTypeEnum


ROOT_DIR = Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT_DIR / "evaluations"
MOD01_JSON = EVAL_DIR / "module_01_gateway_test_cases.json"
MOD02_JSON = EVAL_DIR / "module_02_guardrails_test_cases.json"


def load_mod01_cases():
    with open(MOD01_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]


def load_mod02_cases():
    with open(MOD02_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]


MOD01_CASES = load_mod01_cases()
MOD02_CASES = load_mod02_cases()


# ============================================================================
# MODULE 1: API GATEWAY TESTS (31 CASES)
# ============================================================================

@pytest.mark.parametrize("case", [c for c in MOD01_CASES if c["category"] == "HBAC_PROFILE_EXTRACTION"], ids=lambda c: c["id"])
def test_mod01_hbac_profile_extraction(case):
    """Kiểm tra trích xuất 6 HBAC Profiles chuẩn hóa."""
    persona_key = case["persona"]
    token = ContextExtractor.generate_token_for_profile(persona_key)
    auth_header = f"Bearer {token}"
    
    user_ctx = ContextExtractor.extract_from_auth_header(auth_header)
    expected_ctx = case["expected"]["user_context"]
    
    assert user_ctx.user_id == expected_ctx["user_id"]
    assert user_ctx.tenant_code == expected_ctx["tenant_code"]
    assert user_ctx.role_level == expected_ctx["role_level"]
    assert user_ctx.department_code == expected_ctx["department_code"]
    assert user_ctx.office_id == expected_ctx["office_id"]
    assert user_ctx.is_province_level == expected_ctx["is_province_level"]
    assert user_ctx.is_department_level == expected_ctx["is_department_level"]
    assert user_ctx.is_office_level == expected_ctx["is_office_level"]
    assert user_ctx.is_public == expected_ctx["is_public"]


@pytest.mark.parametrize("case", [c for c in MOD01_CASES if c["category"] == "MULTI_TENANCY_ISOLATION"], ids=lambda c: c["id"])
def test_mod01_multi_tenancy_isolation(case):
    """Kiểm tra cô lập dữ liệu đa người thuê (Tenant 68 vs 79)."""
    persona_key = case["persona"]
    token = ContextExtractor.generate_token_for_profile(persona_key)
    user_ctx = ContextExtractor.extract_from_auth_header(f"Bearer {token}")
    
    session_ctx = SSEDispatcher.create_snapshot_stage_1(
        raw_prompt=case["input"]["body"]["prompt"],
        user_context=user_ctx,
        session_id=case["input"]["body"]["session_id"]
    )
    
    assert session_ctx.user_context.tenant_code == case["expected"]["snapshot_tenant_code"]
    if "forbidden_tenant_codes" in case["expected"]:
        for forbidden in case["expected"]["forbidden_tenant_codes"]:
            assert session_ctx.user_context.tenant_code != forbidden
    if "snapshot_department_code" in case["expected"]:
        assert session_ctx.user_context.department_code == case["expected"]["snapshot_department_code"]


@pytest.mark.parametrize("case", [c for c in MOD01_CASES if c["category"] == "SSE_HANDSHAKE_SLA"], ids=lambda c: c["id"])
def test_mod01_sse_handshake_sla(case):
    """Kiểm tra cấu trúc Event 1 connected và SLA TTFE < 50ms."""
    persona_key = case["persona"]
    token = ContextExtractor.generate_token_for_profile(persona_key)
    user_ctx = ContextExtractor.extract_from_auth_header(f"Bearer {token}")
    
    start_t = time.perf_counter()
    session_ctx = SSEDispatcher.create_snapshot_stage_1(
        raw_prompt=case["input"]["body"]["prompt"],
        user_context=user_ctx,
        session_id=case["input"]["body"]["session_id"]
    )
    sse_event = SSEDispatcher.build_connected_event(session_ctx)
    elapsed_ms = (time.perf_counter() - start_t) * 1000
    
    # SLA TTFE < 50ms
    assert elapsed_ms < 50.0, f"TTFE {elapsed_ms}ms vượt chuẩn cam kết SLA 50ms"
    assert sse_event.startswith("event: connected\ndata: {")
    assert sse_event.endswith("\n\n")
    
    # Parse data payload
    data_line = [l for l in sse_event.split("\n") if l.startswith("data: ")][0]
    payload = json.loads(data_line[6:])
    assert "session_id" in payload
    assert "trace_id" in payload
    assert "tenant_code" in payload
    assert "role_level" in payload


@pytest.mark.parametrize("case", [c for c in MOD01_CASES if c["category"] == "STAGE1_SNAPSHOT_CONTRACT"], ids=lambda c: c["id"])
def test_mod01_snapshot_stage_1_contract(case):
    """Kiểm tra hợp đồng DTO Snapshot Stage 1."""
    persona_key = case["input"]["persona_key"]
    token = ContextExtractor.generate_token_for_profile(persona_key)
    user_ctx = ContextExtractor.extract_from_auth_header(f"Bearer {token}")
    
    client_ip = case["input"].get("client_ip")
    session_ctx = SSEDispatcher.create_snapshot_stage_1(
        raw_prompt=case["input"]["raw_prompt"],
        user_context=user_ctx,
        session_id=case["input"]["session_id"],
        client_ip=client_ip
    )
    
    assert uuid.UUID(session_ctx.trace_id)
    assert session_ctx.session_id == case["input"]["session_id"]
    assert session_ctx.raw_prompt == case["input"]["raw_prompt"]
    assert session_ctx.created_at_epoch > 1700000000.0
    if client_ip:
        assert session_ctx.client_ip == client_ip


@pytest.mark.parametrize("case", [c for c in MOD01_CASES if c["category"] == "SESSION_LIFECYCLE"], ids=lambda c: c["id"])
def test_mod01_session_lifecycle(case):
    """Kiểm tra vòng đời phiên (session_id tùy chọn vs tự sinh)."""
    token = ContextExtractor.generate_token_for_profile(case["persona"])
    user_ctx = ContextExtractor.extract_from_auth_header(f"Bearer {token}")
    
    custom_session_id = case["input"]["custom_session_id"]
    session_ctx = SSEDispatcher.create_snapshot_stage_1(
        raw_prompt=case["input"]["prompt"],
        user_context=user_ctx,
        session_id=custom_session_id
    )
    
    if custom_session_id:
        assert session_ctx.session_id == custom_session_id
    else:
        assert re.match(r"^sess_[0-9a-f]{12}$", session_ctx.session_id) is not None


@pytest.mark.parametrize("case", [c for c in MOD01_CASES if c["category"] == "AUTHORIZATION_HEADER_SECURITY"], ids=lambda c: c["id"])
def test_mod01_auth_header_security(case):
    """Kiểm tra bảo mật và từ chối các Authorization Header sai chuẩn."""
    auth_header = case["input"]["headers"].get("Authorization")
    with pytest.raises(ValueError) as excinfo:
        ContextExtractor.extract_from_auth_header(auth_header)
    assert any(sub in str(excinfo.value) for sub in ["Thiếu", "không hợp lệ", "Cấu trúc"])


@pytest.mark.parametrize("case", [c for c in MOD01_CASES if c["category"] == "TOKEN_TAMPERING_SECURITY"], ids=lambda c: c["id"])
def test_mod01_token_tampering_security(case):
    """Kiểm tra phát hiện và ngăn chặn token bị chỉnh sửa chữ ký hoặc payload."""
    auth_header = case["input"]["headers"]["Authorization"]
    with pytest.raises(ValueError) as excinfo:
        ContextExtractor.extract_from_auth_header(auth_header)
    assert any(sub in str(excinfo.value) for sub in ["không hợp lệ", "chỉnh sửa trái phép", "Cấu trúc"])


@pytest.mark.parametrize("case", [c for c in MOD01_CASES if c["category"] == "TOKEN_EXPIRATION_SECURITY"], ids=lambda c: c["id"])
def test_mod01_token_expiration_security(case):
    """Kiểm tra từ chối token hết hạn."""
    # Sinh token hết hạn
    token = JWTService.encode({"user_id": "test_exp", "tenant_code": "68", "role_level": 0}, expires_in_seconds=-10)
    with pytest.raises(ValueError) as excinfo:
        ContextExtractor.extract_from_auth_header(f"Bearer {token}")
    assert "hết hạn" in str(excinfo.value)


@pytest.mark.parametrize("case", [c for c in MOD01_CASES if c["category"] == "INGRESS_PAYLOAD_BOUNDARY"], ids=lambda c: c["id"])
def test_mod01_ingress_payload_boundaries(case):
    """Kiểm tra giới hạn độ dài payload (min 1, max 4000)."""
    if "prompt_len" in case["input"].get("body", {}):
        prompt_len = case["input"]["body"]["prompt_len"]
        too_long_str = "A" * prompt_len
        with pytest.raises(ValidationError):
            ChatStreamRequest(prompt=too_long_str)
    elif "prompt" in case["input"].get("body", {}):
        empty_str = case["input"]["body"]["prompt"]
        with pytest.raises(ValidationError):
            ChatStreamRequest(prompt=empty_str)
    elif "valid_prompt_len" in case["input"]:
        valid_str = "A" * case["input"]["valid_prompt_len"]
        req = ChatStreamRequest(prompt=valid_str)
        assert len(req.prompt) == 4000
        
        invalid_str = "A" * case["input"]["invalid_prompt_len"]
        with pytest.raises(ValidationError):
            ChatStreamRequest(prompt=invalid_str)


@pytest.mark.parametrize("case", [c for c in MOD01_CASES if c["category"] == "PARSER_POISONING_SECURITY"], ids=lambda c: c["id"])
def test_mod01_parser_poisoning_security(case):
    """Kiểm tra xử lý chuỗi poison chứa null byte."""
    token = ContextExtractor.generate_token_for_profile("lamdong_province_leader")
    user_ctx = ContextExtractor.extract_from_auth_header(f"Bearer {token}")
    
    raw_prompt = case["input"]["body"]["prompt"]
    session_ctx = SSEDispatcher.create_snapshot_stage_1(
        raw_prompt=raw_prompt,
        user_context=user_ctx
    )
    result = GuardrailsPipeline.evaluate(session_ctx)
    assert result.is_safe is False
    assert result.violation_type == ViolationTypeEnum.INJECTION


# ============================================================================
# MODULE 2: PRE-ROUTER SECURITY GUARDRAILS TESTS (50 CASES)
# ============================================================================

@pytest.mark.parametrize("case", MOD02_CASES, ids=lambda c: c["id"])
def test_mod02_enterprise_guardrails_suite(case):
    """Kiểm tra toàn bộ 50 ca kiểm thử bảo mật, PII và phạm vi nghiệp vụ cho Module 2."""
    profile_key = case["input"].get("profile_key", "public_citizen")
    token = ContextExtractor.generate_token_for_profile(profile_key)
    user_ctx = ContextExtractor.extract_from_auth_header(f"Bearer {token}")
    
    session_ctx = SSEDispatcher.create_snapshot_stage_1(
        raw_prompt=case["input"]["raw_prompt"],
        user_context=user_ctx
    )
    
    result = GuardrailsPipeline.evaluate(session_ctx)
    expected = case["expected"]
    
    # 1. Kiểm tra trạng thái an toàn
    assert result.is_safe == expected["is_safe"], (
        f"Ca {case['id']}: Kỳ vọng is_safe={expected['is_safe']}, thực tế={result.is_safe}. "
        f"Prompt: '{case['input']['raw_prompt']}' - Message: {result.violation_message}"
    )
    
    # 2. Kiểm tra loại vi phạm
    assert result.violation_type.value == expected["violation_type"], (
        f"Ca {case['id']}: Kỳ vọng violation_type='{expected['violation_type']}', "
        f"thực tế='{result.violation_type.value}'"
    )
    
    # 3. Kiểm tra SLA độ trễ < 30ms
    assert result.latency_ms < expected.get("latency_sla_ms", 30.0), (
        f"Ca {case['id']}: Độ trễ {result.latency_ms}ms vượt quá SLA 30ms!"
    )
    
    # 4. Kiểm tra thông điệp giải thích đặc thù
    if "expected_explanation_contains" in expected:
        assert expected["expected_explanation_contains"] in (result.violation_message or "")
