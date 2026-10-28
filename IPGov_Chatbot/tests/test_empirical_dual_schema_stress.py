"""
Empirical Stress & Adversarial Test Suite for Dual-Schema Switching and Open Public Access
Author: Empirical Challenger
Target: IPGov_Chatbot
"""

import pytest
import sqlglot
from sqlglot import exp
from fastapi.testclient import TestClient

from IPGov_Chatbot.main import app
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO
from IPGov_Chatbot.modules.mod01_gateway.user_service import UserService
from IPGov_Chatbot.modules.mod03_router.canonical_normalizer import CanonicalSemanticNormalizer
from IPGov_Chatbot.modules.mod04_catalog import DuckDBSemanticCatalog
from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import (
    WarehouseLangGraphAgent,
    PUBLIC_WAREHOUSE_TABLES,
    ALLOWED_WAREHOUSE_TABLES,
)
from IPGov_Chatbot.modules.mod06_ast_enforcer.ast_enforcer_service import (
    ASTEnforcerService,
    ALLOWED_SCHEMAS,
    FORBIDDEN_SCHEMAS,
    SecurityEnforcementError,
)
from IPGov_Chatbot.schemas.sql_compiler_schema import GeneratedSQLDTO, SQLExecutionMode


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def user_service():
    return UserService.get_instance()


@pytest.fixture(scope="module")
def catalog():
    return DuckDBSemanticCatalog()


@pytest.fixture(scope="module")
def normalizer(catalog):
    return CanonicalSemanticNormalizer(catalog)


@pytest.fixture(scope="module")
def ast_enforcer():
    return ASTEnforcerService()


@pytest.fixture(scope="module")
def agent():
    return WarehouseLangGraphAgent()


def _enforce(ast_service: ASTEnforcerService, sql: str, ctx: UserSecurityContextDTO) -> str:
    dto = GeneratedSQLDTO(
        raw_sql=sql,
        execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
        generator_track="TRACK_A_COMPILER",
    )
    return ast_service.enforce_sql_sync(dto, ctx).sanitized_sql


# ==============================================================================
# SECTION 1: DYNAMIC SCHEMA TOGGLE & RAPID SWITCHING
# ==============================================================================

def test_dynamic_schema_toggle_rapid_alternating(client):
    """
    Stress-test: Rapidly alternate between dwh_internal and dwh_public
    within the same session across 10 consecutive requests.
    Verify no state leakage, session corruption, or authorization confusion.
    """
    session_id = "stress_toggle_session_rapid_10"
    
    # User: bacgianghia.ld (Level 3, assigned: Phát triển nông thôn, Diêm nghiệp, Trồng trọt)
    # Out of scope for internal: "ASXH" (Nhiệm vụ ASXH thuộc admin-lamdong)
    
    for i in range(10):
        if i % 2 == 0:
            # dwh_internal out-of-scope query -> MUST BE BLOCKED
            payload = {
                "prompt": "[user=bacgianghia.ld, schema=dwh_internal] Kinh phí thực hiện nhiệm vụ 1 ASXH năm 2025 là bao nhiêu?",
                "session_id": session_id,
            }
            resp = client.post("/api/v1/chat/stream", json=payload)
            assert resp.status_code == 200
            text = resp.text
            assert "event: guardrail_blocked" in text, f"Iteration {i}: Internal out-of-scope MUST be blocked!"
            assert "MISSION_SCOPE_VIOLATION" in text
        else:
            # dwh_public query -> MUST BE ALLOWED (public has equal open access)
            payload = {
                "prompt": "[user=bacgianghia.ld, schema=dwh_public] Kinh phí thực hiện nhiệm vụ 1 ASXH năm 2025 là bao nhiêu?",
                "session_id": session_id,
            }
            resp = client.post("/api/v1/chat/stream", json=payload)
            assert resp.status_code == 200
            text = resp.text
            assert "event: guardrail_blocked" not in text, f"Iteration {i}: Public query MUST NOT be blocked!"
            assert "event: connected" in text


def test_dynamic_schema_toggle_payload_vs_prefix(client):
    """
    Test schema parameter precedence:
    When schema is set via JSON payload vs prompt prefix tag.
    Prefix tag should override or agree cleanly.
    """
    # Payload schema=dwh_public, prefix tag [schema=dwh_internal] -> prefix should take precedence
    payload = {
        "prompt": "[user=minhanh, schema=dwh_internal] Tình hình phát triển diêm nghiệp năm 2025?",
        "schema": "dwh_public",
        "session_id": "test_precedence_1",
    }
    resp = client.post("/api/v1/chat/stream", json=payload)
    assert resp.status_code == 200
    assert "MISSION_SCOPE_VIOLATION" in resp.text, "Prompt prefix schema=dwh_internal must enforce internal mission check!"


# ==============================================================================
# SECTION 2: DWH_PUBLIC SCHEMA INTEGRITY (ZERO OFFICE JOIN / COLUMN LEAKAGE)
# ==============================================================================

def test_dwh_public_schema_integrity_all_query_intents(normalizer):
    """
    Verify that NO SQL query generated for dwh_public contains:
    1. 'office' table join (dwh_internal.office, dwh_public.office, etc.)
    2. 'office_id' column reference or projection
    Across all supported canonical query intents.
    """
    test_queries = [
        "Kinh phí thực hiện khuyến công địa phương năm 2025 là bao nhiêu?",
        "Top 5 chỉ tiêu có kinh phí cao nhất năm 2025?",
        "Danh mục các chỉ tiêu thống kê năm 2025?",
        "Phân rã chỉ tiêu cha con ngành nông nghiệp năm 2025?",
        "So sánh chỉ tiêu giữa các ngành năm 2025?",
    ]
    
    for q in test_queries:
        frame = normalizer.normalize_query(query=q, session_tenant="68", session_year="2025")
        sql_pub = normalizer.compile_canonical_sql(frame, target_schema="dwh_public")
        if not sql_pub:
            continue
            
        parsed = sqlglot.parse_one(sql_pub, read="postgres")
        
        # Check all tables referenced in AST
        for tbl in parsed.find_all(exp.Table):
            tbl_name = (tbl.name or "").lower()
            assert "office" not in tbl_name, f"Query '{q}' leaked office table in dwh_public: {tbl_name}"
            
        # Check all column references in AST
        for col in parsed.find_all(exp.Column):
            col_name = (col.name or "").lower()
            assert col_name != "office_id", f"Query '{q}' leaked office_id column in dwh_public: {sql_pub}"


def test_dwh_public_agent_fallback_sql_integrity(agent):
    """
    Verify agent's fallback SQL generation when in dwh_public:
    Does NOT contain office table join or office_id column.
    """
    # Non-additive metric query in dwh_public
    state_non_add = {
        "user_query": "Số lượng hợp tác xã năm 2025?",
        "active_schema": "dwh_public",
        "target_tables": ["fact_report_criteria"],
        "user_context": {"schema": "dwh_public", "tenant_code": "68"},
        "candidate_metrics": [{"name": "Số lượng hợp tác xã", "aggregation_type": "NON_ADDITIVE"}],
    }
    res_non_add = agent.node_generate_and_validate_sql(state_non_add)
    sql_non_add = res_non_add.get("generated_sql") or ""
    assert "dwh_public.fact_report_criteria" in sql_non_add
    assert "office" not in sql_non_add.lower(), f"Fallback non-additive SQL leaked office: {sql_non_add}"
    assert "office_id" not in sql_non_add.lower(), f"Fallback non-additive SQL leaked office_id: {sql_non_add}"

    # Additive metric query in dwh_public
    state_add = {
        "user_query": "Tổng kinh phí khuyến công năm 2025?",
        "active_schema": "dwh_public",
        "target_tables": ["fact_report_criteria"],
        "user_context": {"schema": "dwh_public", "tenant_code": "68"},
        "candidate_metrics": [{"name": "Tổng kinh phí khuyến công", "aggregation_type": "SUM"}],
    }
    res_add = agent.node_generate_and_validate_sql(state_add)
    sql_add = res_add.get("generated_sql") or ""
    assert "dwh_public.fact_report_criteria" in sql_add
    assert "office" not in sql_add.lower(), f"Fallback additive SQL leaked office: {sql_add}"
    assert "office_id" not in sql_add.lower(), f"Fallback additive SQL leaked office_id: {sql_add}"


# ==============================================================================
# SECTION 3: EQUAL ACCESS IN DWH_PUBLIC (LEVEL 0 USER & CITIZEN ACCESS)
# ==============================================================================

def test_equal_access_level_0_user_thuy_lanh(agent, ast_enforcer):
    """
    Level 0 User 'Nguyễn Thị Thúy Lành' (username: tzyalnh, 0 missions assigned):
    1. In dwh_internal: MUST be refused deterministically (Tier 1) and AST enforcer injects 1 = 0 (Tier 2).
    2. In dwh_public: MUST HAVE FULL OPEN ACCESS without refusal and without 1 = 0.
    """
    ctx_internal = UserSecurityContextDTO(
        user_id="cc99047a-692d-49f8-aacc-f3f8031a445b",
        username="tzyalnh",
        name="Nguyễn Thị Thúy Lành",
        role_level=0,
        is_unrestricted=False,
        schema="dwh_internal",
        tenant_code="68",
        assigned_mission_ids=[],
    )
    
    ctx_public = UserSecurityContextDTO(
        user_id="cc99047a-692d-49f8-aacc-f3f8031a445b",
        username="tzyalnh",
        name="Nguyễn Thị Thúy Lành",
        role_level=0,
        is_unrestricted=False,
        schema="dwh_public",
        tenant_code="68",
        assigned_mission_ids=[],
    )

    # 1. Internal check Tier 1
    state_int = {
        "user_query": "Kinh phí hỗ trợ phát triển diêm nghiệp năm 2025 là bao nhiêu?",
        "user_context": ctx_internal.model_dump(),
        "active_schema": "dwh_internal",
    }
    res_int = agent.node_parse_context(state_int)
    assert res_int["is_permission_denied"] is True, "Level 0 user in dwh_internal must be denied out-of-mission queries!"

    # 2. Internal check Tier 2
    sql_int = "SELECT f.name, f.value FROM dwh_internal.fact_report_criteria f WHERE f.tenant_code = '68';"
    enforced_int = _enforce(ast_enforcer, sql_int, ctx_internal)
    assert "1 = 0" in enforced_int, "Level 0 user in dwh_internal must have '1 = 0' injected by AST enforcer!"

    # 3. Public check Tier 1: MUST NOT BE BLOCKED
    state_pub = {
        "user_query": "Kinh phí hỗ trợ phát triển diêm nghiệp năm 2025 là bao nhiêu?",
        "user_context": ctx_public.model_dump(),
        "active_schema": "dwh_public",
    }
    res_pub = agent.node_parse_context(state_pub)
    assert res_pub.get("is_permission_denied") is False, "Level 0 user in dwh_public MUST NOT be denied access!"

    # 4. Public check Tier 2: MUST NOT HAVE 1=0 OR MISSION_ID RESTRICTION
    sql_pub = "SELECT f.name, f.value FROM dwh_public.fact_report_criteria f WHERE f.tenant_code = '68' AND f.report_status = 'approved';"
    enforced_pub = _enforce(ast_enforcer, sql_pub, ctx_public)
    assert "1 = 0" not in enforced_pub, "dwh_public query must NOT inject 1 = 0!"
    assert "mission_id IN" not in enforced_pub, "dwh_public query must NOT restrict by mission_id!"


# ==============================================================================
# SECTION 4: INJECTION & BOUNDARY TESTING VIA SCHEMA PARAMETER
# ==============================================================================

def test_schema_sql_injection_attempt_ast_enforcer(ast_enforcer):
    """
    Test SQL injection attempt via schema in AST Enforcer:
    e.g. raw_sql containing 'public; DROP TABLE user' or forbidden metadata schemas.
    """
    ctx = UserSecurityContextDTO(
        user_id="default_user",
        username="user",
        role_level=1,
        schema="dwh_internal",
    )
    
    # Injection 1: Multi-statement attack via semicolon
    sql_drop = "SELECT f.name FROM dwh_internal.fact_report_criteria f; DROP TABLE dwh_internal.\"user\";"
    with pytest.raises(SecurityEnforcementError) as exc_info:
        _enforce(ast_enforcer, sql_drop, ctx)
    assert exc_info.value.violation_type.name == "MULTIPLE_STATEMENTS"

    # Injection 2: Accessing system catalog pg_catalog
    sql_pg = "SELECT tablename FROM pg_catalog.pg_tables;"
    with pytest.raises(SecurityEnforcementError) as exc_info:
        _enforce(ast_enforcer, sql_pg, ctx)
    assert exc_info.value.violation_type.name == "FORBIDDEN_TABLE"

    # Injection 3: Accessing information_schema
    sql_info = "SELECT column_name FROM information_schema.columns;"
    with pytest.raises(SecurityEnforcementError) as exc_info:
        _enforce(ast_enforcer, sql_info, ctx)
    assert exc_info.value.violation_type.name == "FORBIDDEN_TABLE"


def test_schema_invalid_or_unknown_fallback(normalizer, agent):
    """
    Test boundary & injection behavior when user provides an unknown or malicious schema name:
    e.g. schema="unknown_schema", schema="dwh_internal; DROP TABLE user", schema="' OR '1'='1"
    
    Check:
    1. Does CanonicalSemanticNormalizer cleanly fall back to 'dwh_internal'?
    2. Does WarehouseLangGraphAgent cleanly reject or handle invalid schema?
    """
    malicious_schemas = [
        "unknown_schema",
        "dwh_internal; DROP TABLE user",
        "' OR '1'='1",
        "public; DROP TABLE criteria",
        "../../etc/passwd",
        "dwh_public_bypass",
    ]
    
    frame = normalizer.normalize_query(
        query="Kinh phí khuyến công năm 2025?",
        session_tenant="68",
        session_year="2025"
    )

    for bad_schema in malicious_schemas:
        sql = normalizer.compile_canonical_sql(frame, target_schema=bad_schema)
        # Normalizer must only output dwh_internal or dwh_public, never bad_schema directly
        assert bad_schema not in sql, f"Normalizer leaked unsanitized schema '{bad_schema}' into SQL: {sql}"
        assert ("dwh_internal.fact_report_criteria" in sql or "dwh_public.fact_report_criteria" in sql), \
            f"Expected fallback to dwh_internal for schema '{bad_schema}', got: {sql}"


def test_adversarial_bypass_attempt_via_unknown_schema(client, agent, ast_enforcer):
    """
    CRITICAL ADVERSARIAL CHALLENGE:
    Attacker is a restricted user (minhanh, Level 1, only assigned to 'Công nghiệp').
    Attacker tries to query an out-of-scope mission ('Diêm nghiệp') by setting
    schema='unknown_schema' or schema='xyz' to bypass Tier 1 (which checks active_schema == 'dwh_internal').
    
    Does the system prevent unauthorized access to internal data?
    """
    # Test via Gateway API stream
    payload = {
        "prompt": "[user=minhanh, schema=xyz_bypass] Kinh phí hỗ trợ phát triển diêm nghiệp và sản xuất muối năm 2025 là bao nhiêu?",
        "session_id": "test_adversarial_bypass_001"
    }
    resp = client.post("/api/v1/chat/stream", json=payload)
    assert resp.status_code == 200
    content = resp.text

    # Analyze behavior:
    # If the system treated schema='xyz_bypass' as non-internal, did it block or did it leak?
    print("\n[ADVERSARIAL PROBE RESULT for schema=xyz_bypass]:")
    print(f"Status Code: {resp.status_code}")
    print(f"Content preview: {content[:300]}")
