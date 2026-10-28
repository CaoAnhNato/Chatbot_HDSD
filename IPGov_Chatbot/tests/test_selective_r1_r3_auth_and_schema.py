"""
Module: IPGov_Chatbot/tests/test_selective_r1_r3_auth_and_schema.py
Chức năng: Bộ kiểm thử chọn lọc Milestone 1 (Backend Core) xác thực toàn diện:
1. Phân loại người dùng & API Endpoint GET /api/v1/users (8 tài khoản, 5 tầng Level 0 - 4).
2. Hai tầng phòng thủ (Two-Tier Defense):
   - Tier 1: Pre-SQL Refusal Gate trong warehouse_langgraph_agent (chặn trước SQL khi out-of-mission).
   - Tier 2: AST Enforcer Invariant trong scope_visitor (cưỡng chế vị từ mission_id IN (...) hoặc 1 = 0).
3. Miễn trừ toàn quyền (Unrestricted Access) cho tài khoản Lãnh đạo.
4. Điều hướng kho dữ liệu động (Dual-Schema Switching: dwh_internal vs dwh_public):
   - dwh_public mở rộng cho toàn bộ người dùng tra cứu dữ liệu công khai.
   - dwh_public không chứa bảng office và không có trường office_id.
5. Chuyển đổi Schema nhanh chóng qua cú pháp prefix [schema=dwh_public] / [schema=dwh_internal].
"""

import pytest
from fastapi.testclient import TestClient

from IPGov_Chatbot.main import app
from IPGov_Chatbot.modules.mod01_gateway.user_service import UserService, PRE_SEEDED_USERS
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO
from IPGov_Chatbot.modules.mod06_ast_enforcer.ast_enforcer_service import ASTEnforcerService
from IPGov_Chatbot.schemas.sql_compiler_schema import GeneratedSQLDTO, SQLExecutionMode
from IPGov_Chatbot.modules.mod03_router.canonical_normalizer import CanonicalSemanticNormalizer
from IPGov_Chatbot.modules.mod04_catalog import DuckDBSemanticCatalog
from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import (
    WarehouseLangGraphAgent,
    PUBLIC_WAREHOUSE_TABLES,
    ALLOWED_WAREHOUSE_TABLES,
)


@pytest.fixture(scope="module")
def client():
    """Tạo FastAPI TestClient dùng chung cho module test."""
    return TestClient(app)


@pytest.fixture(scope="module")
def user_service():
    """Tạo UserService instance."""
    return UserService.get_instance()


@pytest.fixture(scope="module")
def ast_enforcer():
    """Tạo ASTEnforcerService instance."""
    return ASTEnforcerService()


@pytest.fixture(scope="module")
def catalog():
    """Tạo DuckDBSemanticCatalog instance."""
    return DuckDBSemanticCatalog()


@pytest.fixture(scope="module")
def normalizer(catalog):
    """Tạo CanonicalSemanticNormalizer instance."""
    return CanonicalSemanticNormalizer(catalog)


def _enforce(ast_service: ASTEnforcerService, sql: str, ctx: UserSecurityContextDTO) -> str:
    dto = GeneratedSQLDTO(
        raw_sql=sql,
        execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
        generator_track="TRACK_A_COMPILER",
    )
    return ast_service.enforce_sql_sync(dto, ctx).sanitized_sql


# ==============================================================================
# NHÓM 1: PHÂN LOẠI NGƯỜI DÙNG & API ENDPOINTS GET /api/v1/users
# ==============================================================================

@pytest.mark.asyncio
async def test_user_service_classification_8_accounts(user_service):
    """
    Kiểm tra UserService phân loại đúng 8 tài khoản vào 5 tầng cấp bậc (Level 0 - 4)
    với đầy đủ thông tin badge_label, mission_count, assigned_mission_names.
    """
    result = await user_service.get_users()
    users = result.get("users", [])
    assert len(users) == 8, f"Kỳ vọng 8 tài khoản mẫu, nhận được {len(users)}"

    by_username = {u["username"]: u for u in users}
    by_name = {u["name"]: u for u in users}

    # 1. Level 4: Lãnh đạo (Toàn quyền, unrestricted)
    boss = by_name.get("Lãnh đạo") or by_username.get("boss")
    assert boss is not None
    assert boss["role_level"] == 4
    assert boss["is_unrestricted"] is True
    assert "Toàn quyền" in boss["badge_label"]

    # 2. Level 3: Phường Bắc Gia Nghĩa (>= 3 missions) & Admin Tỉnh Lâm Đồng
    bac_gia_nghia = by_name.get("Phường Bắc Gia Nghĩa")
    assert bac_gia_nghia is not None
    assert bac_gia_nghia["role_level"] == 3
    assert bac_gia_nghia["mission_count"] >= 3
    assert "Đa nhiệm vụ" in bac_gia_nghia["badge_label"]

    admin_ld = by_name.get("Admin Tỉnh Lâm Đồng")
    assert admin_ld is not None
    assert admin_ld["role_level"] == 3
    assert admin_ld["mission_count"] >= 3

    # 3. Level 2: Hồng Ngọc (2 missions)
    hong_ngoc = by_name.get("Hồng Ngọc")
    assert hong_ngoc is not None
    assert hong_ngoc["role_level"] == 2
    assert hong_ngoc["mission_count"] == 2
    assert "Đa ngành" in hong_ngoc["badge_label"] or "Đa nhiệm vụ" in hong_ngoc["badge_label"]

    # 4. Level 1: Minh Anh (1 mission: Công nghiệp - Tiểu thủ công nghiệp và TTCN)
    minh_anh = by_name.get("Minh Anh")
    assert minh_anh is not None
    assert minh_anh["role_level"] == 1
    assert minh_anh["mission_count"] == 1
    assert any("công nghiệp" in m.lower() for m in minh_anh["assigned_mission_names"])

    # 5. Level 0: Nguyễn Thị Thúy Lành (0 missions)
    thuy_lanh = by_name.get("Nguyễn Thị Thúy Lành")
    assert thuy_lanh is not None
    assert thuy_lanh["role_level"] == 0
    assert thuy_lanh["mission_count"] == 0
    assert "Giới hạn" in thuy_lanh["badge_label"]


def test_api_get_users_endpoints(client):
    """
    Kiểm tra endpoint GET /api/v1/users và alias GET /api/v1/chat/users
    trả về đúng chuẩn HTTP 200 JSON với 8 tài khoản đã phân loại.
    """
    for endpoint in ["/api/v1/users", "/api/v1/chat/users"]:
        response = client.get(endpoint)
        assert response.status_code == 200, f"Endpoint {endpoint} thất bại với code {response.status_code}"
        data = response.json()
        assert "users" in data
        users = data.get("users", [])
        assert len(users) == 8

        # Kiểm tra cấu trúc phần tử người dùng theo hợp đồng API
        u0 = users[0]
        assert "id" in u0
        assert "name" in u0
        assert "username" in u0
        assert "role_level" in u0
        assert "badge_label" in u0
        assert "mission_count" in u0
        assert "assigned_mission_names" in u0
        assert "assigned_mission_ids" in u0


def test_user_service_build_context(user_service):
    """
    Kiểm tra hàm build_user_context() tạo ra đúng đối tượng UserSecurityContextDTO
    với đầy đủ thuộc tính schema, missions, và cờ is_unrestricted.
    """
    ctx_boss = user_service.build_user_context("lanhdao", schema="dwh_internal")
    assert ctx_boss.name == "Lãnh đạo"
    assert ctx_boss.role_level == 4
    assert ctx_boss.is_unrestricted is True
    assert ctx_boss.schema == "dwh_internal"

    ctx_minhanh = user_service.build_user_context("minhanh", schema="dwh_public")
    assert ctx_minhanh.name == "Minh Anh"
    assert ctx_minhanh.role_level == 1
    assert ctx_minhanh.is_unrestricted is False
    assert ctx_minhanh.schema == "dwh_public"
    assert len(ctx_minhanh.assigned_mission_ids) == 1


# ==============================================================================
# NHÓM 2: TWO-TIER DEFENSE TIER 1 - PRE-SQL REFUSAL GATE (LANGGRAPH AGENT)
# ==============================================================================

def test_tier1_in_mission_query_authorized():
    """
    Kiểm tra Tier 1 Pre-SQL Refusal Gate:
    Người dùng Minh Anh (chuyên trách Công nghiệp) tra cứu chỉ tiêu thuộc nhiệm vụ của mình
    trong dwh_internal -> Được phép đi tiếp (is_permission_denied is False).
    """
    agent = WarehouseLangGraphAgent()
    user_ctx = {
        "user_id": "11111111-1111-1111-1111-111111111113",
        "username": "minhanh",
        "name": "Minh Anh",
        "role_level": 1,
        "is_unrestricted": False,
        "schema": "dwh_internal",
        "tenant_code": "68",
        "assigned_mission_ids": ["88888888-8888-8888-8888-888888888882"],
        "assigned_mission_names": ["Công nghiệp - Tiểu thủ công nghiệp và TTCN"],
    }

    state = {
        "user_query": "Báo cáo kinh phí thực hiện khuyến công địa phương năm 2025?",
        "user_context": user_ctx,
        "active_schema": "dwh_internal",
    }

    result_state = agent.node_parse_context(state)
    assert result_state.get("is_permission_denied") is False, (
        f"Truy vấn hợp lệ trong phạm vi nhiệm vụ của Minh Anh không được bị từ chối! Lỗi: {result_state.get('permission_denied_reason')}"
    )


def test_tier1_out_of_mission_query_deterministic_refusal():
    """
    Kiểm tra Tier 1 Pre-SQL Refusal Gate (Chống rò rỉ dữ liệu - 0.0% Security Violation):
    Người dùng Minh Anh (chuyên trách Công nghiệp) tra cứu chỉ tiêu về Diêm nghiệp / Phát triển nông thôn
    trong dwh_internal -> Bị từ chối dứt khoát ngay tại Node parse_context (trước khi sinh SQL).
    """
    agent = WarehouseLangGraphAgent()
    user_ctx = {
        "user_id": "11111111-1111-1111-1111-111111111113",
        "username": "minhanh",
        "name": "Minh Anh",
        "role_level": 1,
        "is_unrestricted": False,
        "schema": "dwh_internal",
        "tenant_code": "68",
        "assigned_mission_ids": ["88888888-8888-8888-8888-888888888882"],
        "assigned_mission_names": ["Công nghiệp - Tiểu thủ công nghiệp và TTCN"],
    }

    state = {
        "user_query": "Kinh phí hỗ trợ phát triển diêm nghiệp và sản xuất muối năm 2025 là bao nhiêu?",
        "user_context": user_ctx,
        "active_schema": "dwh_internal",
    }

    result_state = agent.node_parse_context(state)
    assert result_state.get("is_permission_denied") is True, "Phải từ chối truy vấn ngoài phạm vi nhiệm vụ!"
    assert result_state.get("violation_type") == "MISSION_SCOPE_VIOLATION"
    assert "từ chối" in result_state.get("permission_denied_reason", "").lower()
    assert len(result_state.get("quick_action_chips", [])) > 0

    # Gọi trực tiếp qua flow run toàn diện
    agent_output = agent.run(
        query="Kinh phí hỗ trợ phát triển diêm nghiệp và sản xuất muối năm 2025 là bao nhiêu?",
        user_context=user_ctx,
        session_id="test_sess_denial_001"
    )
    assert agent_output.get("is_permission_denied") is True
    assert "từ chối" in (agent_output.get("final_answer") or agent_output.get("answer") or "").lower()
    assert agent_output.get("sql") is None, "CẤM tuyệt đối sinh hoặc thực thi SQL khi đã bị Tier 1 từ chối!"


def test_tier1_level_0_user_with_zero_missions_refusal():
    """
    Kiểm tra Tier 1 Pre-SQL Refusal Gate cho tài khoản Level 0 (Nguyễn Thị Thúy Lành - 0 nhiệm vụ):
    Khi tra cứu trong dwh_internal -> Bị chặn 100% với thông báo rõ ràng về việc chưa được giao nhiệm vụ.
    """
    agent = WarehouseLangGraphAgent()
    user_ctx = {
        "user_id": "11111111-1111-1111-1111-111111111114",
        "username": "thuylanh",
        "name": "Nguyễn Thị Thúy Lành",
        "role_level": 0,
        "is_unrestricted": False,
        "schema": "dwh_internal",
        "tenant_code": "68",
        "assigned_mission_ids": [],
        "assigned_mission_names": [],
    }

    state = {
        "user_query": "Báo cáo kinh phí thực hiện khuyến công năm 2025?",
        "user_context": user_ctx,
        "active_schema": "dwh_internal",
    }

    result_state = agent.node_parse_context(state)
    assert result_state.get("is_permission_denied") is True
    assert "chưa được phân công" in result_state.get("permission_denied_reason", "")


def test_tier1_boss_unrestricted_in_internal():
    """
    Kiểm tra Tier 1 Pre-SQL Refusal Gate cho tài khoản Lãnh đạo (Level 4):
    Toàn quyền tra cứu bất kỳ chỉ tiêu kinh tế nào trong dwh_internal mà không bị chặn.
    """
    agent = WarehouseLangGraphAgent()
    user_ctx = {
        "user_id": "11111111-1111-1111-1111-111111111111",
        "username": "lanhdao",
        "name": "Lãnh đạo",
        "role_level": 4,
        "is_unrestricted": True,
        "schema": "dwh_internal",
        "tenant_code": "68",
        "assigned_mission_ids": [],
        "assigned_mission_names": [],
    }

    for prompt in [
        "Báo cáo kinh phí khuyến công năm 2025?",
        "Kinh phí hỗ trợ phát triển diêm nghiệp năm 2025?",
        "Số lượng hợp tác xã thành lập mới năm 2024?",
    ]:
        state = {
            "user_query": prompt,
            "user_context": user_ctx,
            "active_schema": "dwh_internal",
        }
        result_state = agent.node_parse_context(state)
        assert result_state.get("is_permission_denied") is False, f"Lãnh đạo không bao giờ bị chặn trên câu hỏi: {prompt}"


# ==============================================================================
# NHÓM 3: TWO-TIER DEFENSE TIER 2 - AST ENFORCER INVARIANT (SCOPE VISITOR)
# ==============================================================================

def test_tier2_ast_enforcer_injects_mission_id_for_restricted_user(ast_enforcer):
    """
    Kiểm tra Tier 2 AST Enforcer Invariant:
    Khi schema == 'dwh_internal' và người dùng không phải Lãnh đạo:
    AST bắt buộc tiêm vị từ f.mission_id IN (...) vào mệnh đề WHERE của bảng fact_report_criteria.
    """
    ctx = UserSecurityContextDTO(
        user_id="11111111-1111-1111-1111-111111111113",
        username="minhanh",
        name="Minh Anh",
        role_level=1,
        is_unrestricted=False,
        schema="dwh_internal",
        tenant_code="68",
        assigned_mission_ids=["88888888-8888-8888-8888-888888888882"],
        assigned_mission_names=["Công nghiệp - Tiểu thủ công nghiệp và TTCN"],
    )

    sql = (
        "SELECT f.name, f.value, f.report_date "
        "FROM dwh_internal.fact_report_criteria f "
        "WHERE f.tenant_code = '68' AND f.report_status = 'approved';"
    )

    enforced_sql = _enforce(ast_enforcer, sql, ctx)
    assert "mission_id IN ('88888888-8888-8888-8888-888888888882')" in enforced_sql


def test_tier2_ast_enforcer_injects_1_equals_0_for_zero_mission_user(ast_enforcer):
    """
    Kiểm tra Tier 2 AST Enforcer Invariant cho tài khoản 0 nhiệm vụ:
    Nếu bằng cách nào đó câu lệnh lọt qua Tier 1 đến AST Enforcer,
    AST tiêm '1 = 0' để bảo đảm tuyệt đối không bao giờ trả về dữ liệu fact.
    """
    ctx = UserSecurityContextDTO(
        user_id="11111111-1111-1111-1111-111111111114",
        username="thuylanh",
        name="Nguyễn Thị Thúy Lành",
        role_level=0,
        is_unrestricted=False,
        schema="dwh_internal",
        tenant_code="68",
        assigned_mission_ids=[],
    )

    sql = (
        "SELECT f.name, f.value "
        "FROM dwh_internal.fact_report_criteria f "
        "WHERE f.tenant_code = '68';"
    )

    enforced_sql = _enforce(ast_enforcer, sql, ctx)
    assert "1 = 0" in enforced_sql


def test_tier2_ast_enforcer_bypasses_for_boss(ast_enforcer):
    """
    Kiểm tra Tier 2 AST Enforcer Invariant:
    Tài khoản Lãnh đạo (is_unrestricted == True) được miễn trừ hoàn toàn,
    không bị tiêm mission_id IN (...) hay 1 = 0.
    """
    ctx = UserSecurityContextDTO(
        user_id="11111111-1111-1111-1111-111111111111",
        username="lanhdao",
        name="Lãnh đạo",
        role_level=4,
        is_unrestricted=True,
        schema="dwh_internal",
        tenant_code="68",
    )

    sql = (
        "SELECT f.name, f.value "
        "FROM dwh_internal.fact_report_criteria f "
        "WHERE f.tenant_code = '68' AND f.report_status = 'approved';"
    )

    enforced_sql = _enforce(ast_enforcer, sql, ctx)
    assert "mission_id IN" not in enforced_sql
    assert "1 = 0" not in enforced_sql


def test_tier2_ast_enforcer_bypasses_for_dwh_public(ast_enforcer):
    """
    Kiểm tra Tier 2 AST Enforcer Invariant khi tra cứu dwh_public:
    Dữ liệu công khai không áp dụng giới hạn phòng ban (office_id), sở ngành (department_code)
    hoặc nhiệm vụ (mission_id).
    """
    ctx = UserSecurityContextDTO(
        user_id="11111111-1111-1111-1111-111111111113",
        username="minhanh",
        name="Minh Anh",
        role_level=1,
        is_unrestricted=False,
        schema="dwh_public",
        tenant_code="68",
        department_code="68-1-02",
        office_id="00000000-0000-0000-0000-000000000001",
        assigned_mission_ids=["88888888-8888-8888-8888-888888888882"],
    )

    sql = (
        "SELECT f.name, f.value "
        "FROM dwh_public.fact_report_criteria f "
        "WHERE f.tenant_code = '68' AND f.report_status = 'approved';"
    )

    enforced_sql = _enforce(ast_enforcer, sql, ctx)
    assert "mission_id IN" not in enforced_sql
    assert "department_code" not in enforced_sql
    assert "office_id" not in enforced_sql


# ==============================================================================
# NHÓM 4: DYNAMIC SCHEMA ROUTING & PUBLIC ACCESS
# ==============================================================================

def test_canonical_normalizer_routes_to_dwh_public_without_office_join(normalizer):
    """
    Kiểm tra Canonical Semantic Normalizer với target_schema='dwh_public':
    1. Câu SQL phải nhắm vào dwh_public.fact_report_criteria và dwh_public.dim_criteria.
    2. CẤM tuyệt đối JOIN bảng office hoặc dùng f.office_id (vì dwh_public không có bảng office).
    """
    frame = normalizer.normalize_query(
        query="Kinh phí thực hiện khuyến công địa phương năm 2025 là bao nhiêu?",
        session_tenant="68",
        session_year="2025"
    )

    # Trường hợp 1: dwh_public
    sql_public = normalizer.compile_canonical_sql(frame, target_schema="dwh_public")
    assert "dwh_public.fact_report_criteria" in sql_public
    assert "dwh_public.criteria" in sql_public or "dwh_public.fact_report_criteria" in sql_public
    assert "office" not in sql_public.lower(), "dwh_public không được phép chứa bảng office hoặc office_id!"

    # Trường hợp 2: dwh_internal
    sql_internal = normalizer.compile_canonical_sql(frame, target_schema="dwh_internal")
    assert "dwh_internal.fact_report_criteria" in sql_internal
    assert "dwh_internal.criteria" in sql_internal


def test_public_open_access_for_any_user_no_refusal():
    """
    Kiểm tra người dùng bất kỳ (kể cả Thúy Lành Level 0 hay Minh Anh)
    khi tra cứu trong schema dwh_public đều KHÔNG bị Tier 1 từ chối.
    """
    agent = WarehouseLangGraphAgent()
    user_ctx = {
        "user_id": "11111111-1111-1111-1111-111111111114",
        "username": "thuylanh",
        "name": "Nguyễn Thị Thúy Lành",
        "role_level": 0,
        "is_unrestricted": False,
        "schema": "dwh_public",
        "tenant_code": "68",
        "assigned_mission_ids": [],
    }

    state = {
        "user_query": "Kinh phí hỗ trợ phát triển diêm nghiệp năm 2025 là bao nhiêu?",
        "user_context": user_ctx,
        "active_schema": "dwh_public",
    }

    result_state = agent.node_parse_context(state)
    assert result_state.get("is_permission_denied") is False, (
        "Kho dữ liệu công khai dwh_public mở cho mọi công dân và cán bộ, không được áp dụng chặn nhiệm vụ!"
    )


def test_warehouse_agent_explore_tables_filtered_by_schema():
    """
    Kiểm tra Node explore_warehouse lọc danh sách bảng theo đúng schema hiện hành:
    - Khi dwh_public: chỉ khám phá PUBLIC_WAREHOUSE_TABLES (không có office, deparment, user, user_mission).
    - Khi dwh_internal: khám phá ALLOWED_WAREHOUSE_TABLES đầy đủ.
    """
    agent = WarehouseLangGraphAgent()

    # Schema dwh_public
    state_public = {
        "user_query": "Cho biết cơ cấu chỉ tiêu khuyến công?",
        "active_schema": "dwh_public",
        "target_tables": [],
    }
    res_pub = agent.node_explore_warehouse(state_public)
    assert "office" not in res_pub["target_tables"]
    assert "user" not in res_pub["target_tables"]
    assert "user_mission" not in res_pub["target_tables"]
    assert all(t in PUBLIC_WAREHOUSE_TABLES for t in res_pub["target_tables"])

    # Schema dwh_internal
    state_internal = {
        "user_query": "Cho biết cơ cấu chỉ tiêu khuyến công?",
        "active_schema": "dwh_internal",
        "target_tables": [],
    }
    res_int = agent.node_explore_warehouse(state_internal)
    assert any(t in ALLOWED_WAREHOUSE_TABLES for t in res_int["target_tables"])


# ==============================================================================
# NHÓM 5: FAST SCHEMA SWITCHING & GATEWAY INTEGRATION
# ==============================================================================

def test_fast_schema_switching_via_prefix(client):
    """
    Kiểm tra Gateway phân tích cú pháp prefix [schema=dwh_public] và [user=lanhdao]:
    1. Khi gọi SSE stream với prefix [user=minhanh, schema=dwh_public], hệ thống nhận diện đúng schema dwh_public.
    2. Khi gọi với [user=lanhdao, schema=dwh_internal], hệ thống nhận diện đúng schema dwh_internal và Lãnh đạo.
    """
    # 1. Tra cứu dwh_public qua stream
    payload_pub = {
        "prompt": "[user=minhanh, schema=dwh_public] Báo cáo tình hình diêm nghiệp năm 2025?",
        "session_id": "test_switch_pub_001"
    }
    resp_pub = client.post("/api/v1/chat/stream", json=payload_pub)
    assert resp_pub.status_code == 200
    assert "text/event-stream" in resp_pub.headers.get("content-type", "")
    content_pub = resp_pub.text
    assert "event: connected" in content_pub
    # Không bị chặn guardrail_blocked vì dwh_public mở
    assert "MISSION_SCOPE_VIOLATION" not in content_pub

    # 2. Tra cứu dwh_internal out-of-scope qua stream với user minhanh -> bị chặn Tier 1
    payload_denied = {
        "prompt": "[user=minhanh, schema=dwh_internal] Kinh phí hỗ trợ phát triển diêm nghiệp và sản xuất muối năm 2025?",
        "session_id": "test_switch_denied_002"
    }
    resp_denied = client.post("/api/v1/chat/stream", json=payload_denied)
    assert resp_denied.status_code == 200
    content_denied = resp_denied.text
    assert "event: guardrail_blocked" in content_denied
    assert "MISSION_SCOPE_VIOLATION" in content_denied
    assert "blocked_by_guardrail" in content_denied

    # 3. Chuyển sang Lãnh đạo [user=lanhdao] cùng câu hỏi trên -> Thành công, không bị chặn
    payload_boss = {
        "prompt": "[user=lanhdao, schema=dwh_internal] Kinh phí hỗ trợ phát triển diêm nghiệp và sản xuất muối năm 2025?",
        "session_id": "test_switch_boss_003"
    }
    resp_boss = client.post("/api/v1/chat/stream", json=payload_boss)
    assert resp_boss.status_code == 200
    content_boss = resp_boss.text
    assert "event: connected" in content_boss
    assert "event: guardrail_blocked" not in content_boss
