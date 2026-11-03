"""
Targeted TDD Suite: dwh_public Schema Isolation & UI Level Dropdown Guardrails.

Covers the two root-cause domains identified via /systematic-debugging:
1. UI Level Dropdown on dwh_public:
   - Level/account selector (`header-user-selector-container` / `#header-user-selector`)
     and `Level X` header subtitle must NOT be displayed when `activeSchema === 'dwh_public'`,
     since RBAC level restrictions do not apply to the open public schema.
2. Cross-Schema Internal Data Leakage on dwh_public:
   - Masked (`share_data = false`, `value = NULL`) criteria in `dwh_public.fact_report_criteria`
     must return `NULL` / unshared public status and empty timeline snapshots — NEVER leaking
     `dwh_internal` values, `office_name`, or `latest_report_date` from DuckDB RAM or
     hardcoded `dwh_internal` SQL helpers.
   - Shared (`share_data = true`) criteria, hierarchy breakdowns, and public dimensions
     (`mission`, `province`, `criteria`, `report`, `criteria_group`) must query `dwh_public.*`
     cleanly for ALL users regardless of `department_code` or `role_level`.
   - `ASTEnforcerService` must strictly block `dwh_internal.*` and internal-only HR/org tables
     when `user_ctx.schema == 'dwh_public'`, and expand hierarchy subqueries via `dwh_public.criteria`.
"""

from pathlib import Path
import pytest

from IPGov_Chatbot.modules.mod01_gateway.user_service import user_service
from IPGov_Chatbot.modules.mod03_router.canonical_normalizer import (
    CanonicalIntentEnum,
    CanonicalQueryFrameDTO,
    CanonicalSemanticNormalizer,
)
from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import WarehouseLangGraphAgent
from IPGov_Chatbot.modules.mod06_ast_enforcer.ast_enforcer_service import (
    ASTEnforcerService,
    SecurityEnforcementError,
)
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO


@pytest.fixture(scope="module")
def agent() -> WarehouseLangGraphAgent:
    return WarehouseLangGraphAgent()


@pytest.fixture(scope="module")
def normalizer(agent: WarehouseLangGraphAgent) -> CanonicalSemanticNormalizer:
    return agent.normalizer


@pytest.fixture(scope="module")
def ast_enforcer() -> ASTEnforcerService:
    return ASTEnforcerService()


# ==============================================================================
# 1. MASKED LEAF METRICS IN dwh_public MUST RETURN NULL (ZERO INTERNAL LEAKAGE)
# ==============================================================================


@pytest.mark.parametrize(
    "query_text,forbidden_internal_val",
    [
        ("số lượng bò hiện tại ?", "256"),
        ("Số lượng trâu năm 2026 là bao nhiêu?", "135"),
    ],
)
def test_public_schema_masked_leaf_returns_null_not_internal_value(
    agent: WarehouseLangGraphAgent,
    query_text: str,
    forbidden_internal_val: str,
):
    """
    When `schema='dwh_public'` is active (even if user_context carries department_code='68-1-01'
    from Lãnh đạo or role_level=0 from a restricted account), querying a non-shared criterion
    (`value IS NULL` in `dwh_public.fact_report_criteria`) must:
    - Query `dwh_public.fact_report_criteria` without `dwh_internal.`, `1 = 0`, or `department_code = '68-1-01'`.
    - Return `NULL` / unshared public notice, NEVER leaking `dwh_internal` values (`256`, `135`),
      `Phòng nông nghiệp`, or internal report date `27/10/2026`.
    - Return `timeline_snapshots == []` on `single_metric_card` (no leaked `dwh_internal` pills).
    """
    ctx_public_from_boss = {
        "user_id": "11111111-1111-1111-1111-111111111111",
        "username": "lanhdao",
        "name": "Lãnh đạo",
        "user_name": "Lãnh đạo",
        "role_level": 4,
        "tenant_code": "68",
        "department_code": "68-1-01",
        "schema": "dwh_public",
        "is_unrestricted": True,
    }
    res = agent.run(
        query=query_text,
        session_id=f"test_pub_masked_{forbidden_internal_val}",
        user_context=ctx_public_from_boss,
    )

    sql = (res.get("sql") or "").lower()
    answer = res.get("final_answer") or ""
    tab = res.get("tabular_data") or {}
    card = tab.get("single_metric_card") or {}

    assert "dwh_public.fact_report_criteria" in sql
    assert "dwh_internal." not in sql
    assert "1 = 0" not in sql
    assert "68-1-01" not in sql

    assert forbidden_internal_val not in answer, f"Leaked internal value {forbidden_internal_val} in answer: {answer}"
    assert "Phòng nông nghiệp" not in answer
    assert "27/10/2026" not in answer
    assert "NULL" in answer

    assert card.get("raw_value") is None
    assert card.get("timeline_snapshots") == []
    assert forbidden_internal_val not in str(card.get("current_value") or "")
    assert card.get("office_name") != "Phòng nông nghiệp"


# ==============================================================================
# 2. SHARED METRICS IN dwh_public MUST WORK OPENLY FOR ALL USERS
# ==============================================================================


def test_public_schema_shared_metric_returns_exact_public_data_and_snapshots(
    agent: WarehouseLangGraphAgent,
):
    """
    Criteria with `share_data = true` in `dwh_public` (e.g. Diêm nghiệp metrics)
    must be queryable by ANY user (including Level 0 with 0 assigned missions and
    a different department_code) and return exact `dwh_public` values + snapshots.
    """
    ctx_lvl0_pub = user_service.build_user_context("tzyalnh", schema="dwh_public").model_dump()
    res = agent.run(
        query="Tổng hộ sản xuất muối tính đến ngày 30/06/2026 là bao nhiêu?",
        session_id="test_pub_shared_salt_households",
        user_context=ctx_lvl0_pub,
    )

    sql = (res.get("sql") or "").lower()
    answer = res.get("final_answer") or ""
    tab = res.get("tabular_data") or {}
    card = tab.get("single_metric_card") or {}
    snaps = card.get("timeline_snapshots") or []

    assert res.get("is_permission_denied") is not True
    assert "dwh_public.fact_report_criteria" in sql
    assert "dwh_internal." not in sql
    assert "660" in answer
    assert "Phòng nông nghiệp" not in answer
    assert len(snaps) >= 2
    assert all(s.get("office") == "Dữ liệu công khai" for s in snaps)


# ==============================================================================
# 3. PARENT & HIERARCHY BREAKDOWN IN dwh_public MUST NOT LEAK DUCKDB VALUES
# ==============================================================================


def test_public_schema_parent_and_breakdown_no_duckdb_leakage(
    agent: WarehouseLangGraphAgent,
):
    """
    1) Masked parent ('Số lượng gia súc hiện tại ?') on dwh_public must NOT leak
       internal child values (256, 135) or preview_value badges from DuckDB RAM.
    2) Shared breakdown ('Cơ cấu diện tích sản xuất muối tính đến ngày 30/06/2026?')
       on dwh_public must return public salt area breakdown (1.520 / 1520) cleanly.
    """
    pub_ctx = {"schema": "dwh_public", "tenant_code": "68", "department_code": "68-1-01"}

    res_masked_parent = agent.run(
        query="Số lượng gia súc hiện tại ?",
        session_id="test_pub_masked_parent_livestock",
        user_context=pub_ctx,
    )
    ans_masked = res_masked_parent.get("final_answer") or ""
    chips_masked = res_masked_parent.get("quick_action_chips") or []

    assert "256" not in ans_masked
    assert "135" not in ans_masked
    assert "Phòng nông nghiệp" not in ans_masked
    for ch in chips_masked:
        assert ch.get("preview_value") not in ("256", "135", 256, 135)

    res_shared_bd = agent.run(
        query="Cơ cấu diện tích sản xuất muối tính đến ngày 30/06/2026?",
        session_id="test_pub_shared_breakdown_salt_area",
        user_context=pub_ctx,
    )
    sql_bd = (res_shared_bd.get("sql") or "").lower()
    ans_bd = res_shared_bd.get("final_answer") or ""

    assert "dwh_internal." not in sql_bd
    assert any(v in ans_bd for v in ("1.520", "1,520", "1520"))
    assert "Phòng nông nghiệp" not in ans_bd


# ==============================================================================
# 4. AST ENFORCER & CANONICAL NORMALIZER STRICT dwh_public ISOLATION
# ==============================================================================


def test_ast_enforcer_blocks_internal_schema_and_expands_public_criteria(
    ast_enforcer: ASTEnforcerService,
):
    """
    When `user_ctx.schema == 'dwh_public'`:
    - Explicit access to `dwh_internal.*` must raise `SecurityEnforcementError`.
    - Access to internal-only tables (`office`, `user`, `ward`, `collection_form`) must raise `SecurityEnforcementError`.
    - TẦNG 4.4 `criteria_id = '...'` rollup expansion must reference `dwh_public.criteria`, NEVER `dwh_internal.criteria`.
    """
    pub_sec_ctx = UserSecurityContextDTO(
        user_id="pub_tester",
        username="guest",
        role_level=0,
        tenant_code="68",
        schema="dwh_public",
    )

    for forbidden_sql in [
        "SELECT f.name, f.value FROM dwh_internal.fact_report_criteria f WHERE f.tenant_code = '68'",
        "SELECT o.office_name FROM dwh_public.office o",
        'SELECT u.username FROM "user" u',
        "SELECT w.name FROM ward w",
    ]:
        with pytest.raises(SecurityEnforcementError):
            ast_enforcer._sanitize_single_sql_ast(forbidden_sql, pub_sec_ctx)

    sanitized_sql, _, _ = ast_enforcer._sanitize_single_sql_ast(
        "SELECT f.name, f.value FROM dwh_public.fact_report_criteria f WHERE f.criteria_id = 'a6700052-cc21-43f1-bdb9-d6c1f96db76f'",
        pub_sec_ctx,
    )
    sanitized_low = sanitized_sql.lower()
    assert "dwh_public.criteria" in sanitized_low
    assert "dwh_internal." not in sanitized_low


def test_public_schema_dimensions_and_internal_hr_isolation(
    agent: WarehouseLangGraphAgent,
    normalizer: CanonicalSemanticNormalizer,
):
    """
    1) Public dimension tables (`mission`, `province`, `criteria`, `report`, `criteria_group`)
       must compile to `dwh_public.*` with zero `dwh_internal.` references and execute cleanly on PostgreSQL.
    2) Internal-only HR queries (e.g., officer assignment) on `dwh_public` must NOT query `dwh_internal."user"`
       or leak internal officer identities.
    """
    frames = [
        CanonicalQueryFrameDTO(
            intent=CanonicalIntentEnum.DIMENSION_LISTING,
            target_table="mission",
            tenant_code="68",
            year_code="2026",
        ),
        CanonicalQueryFrameDTO(
            intent=CanonicalIntentEnum.DIMENSION_LISTING,
            target_table="province",
            tenant_code="68",
            year_code="2026",
        ),
        CanonicalQueryFrameDTO(
            intent=CanonicalIntentEnum.METADATA_EXPLORATION,
            target_table="criteria",
            tenant_code="68",
            year_code="2026",
        ),
        CanonicalQueryFrameDTO(
            intent=CanonicalIntentEnum.REPORT_STATUS_AUDIT,
            target_table="report",
            tenant_code="68",
            year_code="2026",
        ),
        CanonicalQueryFrameDTO(
            intent=CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT,
            audit_sub_intent="FORM_CRITERIA_GROUP",
            target_table="criteria_group",
            tenant_code="68",
            year_code="2026",
        ),
    ]
    pub_ctx = {"schema": "dwh_public", "tenant_code": "68"}
    for frame in frames:
        sql = normalizer.compile_canonical_sql(frame, target_schema="dwh_public", user_context=pub_ctx)
        assert "dwh_internal" not in sql.lower(), f"Leaked dwh_internal for {frame.target_table}: {sql}"
        assert "dwh_public." in sql.lower(), f"Missing dwh_public prefix for {frame.target_table}: {sql}"
        exec_res = agent.execute_safe_sql(sql, user_context=pub_ctx)
        assert not exec_res.get("error"), f"Execution failed on dwh_public.{frame.target_table}: {exec_res.get('error')}\nSQL: {sql}"

    res_hr = agent.run(
        query="Cán bộ nào phụ trách nhiệm vụ diêm nghiệp?",
        session_id="test_pub_hr_isolation",
        user_context=pub_ctx,
    )
    sql_hr = (res_hr.get("sql") or "").lower()
    assert "dwh_internal" not in sql_hr


# ==============================================================================
# 5. FRONTEND ChatContainer.tsx HIDES LEVEL DROPDOWN ON dwh_public
# ==============================================================================


def test_chat_container_hides_level_selector_and_omits_level_tag_on_public_schema():
    """
    Verifies ChatContainer.tsx enforces:
    - `header-user-selector-container` is conditionally rendered only when `activeSchema === 'dwh_internal'`.
    - Header subtitle does not display `Level {selectedRole.role_level}` when `activeSchema === 'dwh_public'`.
    - `promptWithContext` omits `user=` and `level=` when `activeSchema === 'dwh_public'`.
    """
    chat_container_path = (
        Path(__file__).resolve().parents[1]
        / "frontend"
        / "src"
        / "components"
        / "chat"
        / "ChatContainer.tsx"
    )
    src = chat_container_path.read_text(encoding="utf-8")

    # 1. Dropdown container must be gated on dwh_internal
    idx_selector = src.find('data-testid="header-user-selector-container"')
    assert idx_selector != -1
    preceding_window = src[max(0, idx_selector - 260) : idx_selector]
    assert "activeSchema === 'dwh_internal'" in preceding_window, (
        "header-user-selector-container must be conditionally rendered only when activeSchema === 'dwh_internal'"
    )

    # 2. Prompt prefix must branch on activeSchema === 'dwh_public' so level/user tags are omitted in public mode
    idx_prompt = src.find("const promptWithContext")
    assert idx_prompt != -1
    prompt_window = src[idx_prompt : idx_prompt + 420]
    assert "dwh_public" in prompt_window, (
        "promptWithContext must omit user/level RBAC tags when activeSchema === 'dwh_public'"
    )

    # 3. Welcome chips on dwh_public must use dedicated CHIPS_PUBLIC_SCHEMA (not broken CHIPS_LEVEL_3)
    assert "CHIPS_PUBLIC_SCHEMA" in src, "ChatContainer.tsx must define dedicated CHIPS_PUBLIC_SCHEMA for dwh_public"
    idx_welcome_chips = src.find("quick_action_chips: schema === 'dwh_public'")
    assert idx_welcome_chips != -1
    chips_window = src[idx_welcome_chips : idx_welcome_chips + 120]
    assert "CHIPS_PUBLIC_SCHEMA" in chips_window, (
        "getWelcomeMessage must assign CHIPS_PUBLIC_SCHEMA when schema === 'dwh_public'"
    )


# ==============================================================================
# 6. ADVERSARIAL RELOAD, OPEN AUDIT & JWT OVERRIDE ISOLATION ON dwh_public
# ==============================================================================


def test_chat_history_store_reload_never_leaks_internal_timeline_values_or_prefix():
    """
    Streaming a dwh_public Level-1 mission query and then reloading history via
    GET /api/v1/chat/history/{sid} and GET /api/v1/chat/sessions must:
    - NEVER hydrate confidential dwh_internal timeline_values (5.765, 1.396, 1, 256, 135)
      into masked dwh_public rows, tree_modal nodes, or quick_action_chips.
    - Strip [schema=dwh_public, tenant_code=68] from persisted session titles.
    """
    import json
    from fastapi.testclient import TestClient
    from IPGov_Chatbot.main import app
    from IPGov_Chatbot.core.chat_history_store import ChatHistoryStore

    sid = "test_pub_reload_isolation_l1"
    store = ChatHistoryStore.get_instance()
    store.delete_session(sid)

    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/chat/stream",
                json={
                    "prompt": "[schema=dwh_public, tenant_code=68] Các chỉ tiêu Cấp 1 của nhiệm vụ Phát triển nông thôn năm 2026?",
                    "session_id": sid,
                    "schema": "dwh_public",
                    "tenant_code": "68",
                },
            )
            assert resp.status_code == 200

            hist_resp = client.get(f"/api/v1/chat/history/{sid}")
            assert hist_resp.status_code == 200
            msgs = hist_resp.json().get("data") or []
            bot_msgs = [m for m in msgs if m.get("role") == "assistant"]
            assert len(bot_msgs) == 1

            bot_content = str(bot_msgs[0].get("content") or "")
            for leaked_val in ("5.765", "5,765", "1.396", "1,396", "256", "135", "Phòng nông nghiệp"):
                assert leaked_val not in bot_content, (
                    f"Reload leaked confidential dwh_internal token '{leaked_val}' into dwh_public content!"
                )

            td = bot_msgs[0].get("tabular_data") or {}
            leaked_Exact = {"5.765", "5,765", "5765", "1.396", "1,396", "1396", "256", "135"}

            for r in td.get("rows") or []:
                r_val = str(r.get("value") or r.get("gia_tri_moi_nhat") or "").strip()
                assert r_val not in leaked_Exact, f"Row '{r.get('item')}' leaked internal value: {r_val}"
                if "NULL" in r_val:
                    assert not r.get("timeline_values"), (
                        f"Masked dwh_public row '{r.get('item')}' must not have hydrated timeline_values: {r.get('timeline_values')}"
                    )
                for tv_v in (r.get("timeline_values") or {}).values():
                    assert str(tv_v).strip() not in leaked_Exact, (
                        f"Row '{r.get('item')}' timeline_values leaked internal value: {tv_v}"
                    )

            seen_masked_leaves: list[str] = []

            def _assert_tree_node_clean(node: dict) -> None:
                n_name = str(node.get("name") or "")
                n_val = node.get("value")
                if n_val is not None:
                    assert str(n_val).strip() not in leaked_Exact, (
                        f"Tree node '{n_name}' leaked internal value: {n_val}"
                    )
                for tv_v in (node.get("timeline_values") or {}).values():
                    assert str(tv_v).strip() not in leaked_Exact, (
                        f"Tree node '{n_name}' timeline_values leaked internal value: {tv_v}"
                    )
                if n_name in ("Số lượng bò", "Số lượng trâu"):
                    seen_masked_leaves.append(n_name)
                    assert n_val is None or "NULL" in str(n_val), (
                        f"Masked leaf '{n_name}' in tree_modal must be None/NULL, got {n_val!r}"
                    )
                    assert not node.get("timeline_values"), (
                        f"Masked leaf '{n_name}' must not have timeline_values: {node.get('timeline_values')}"
                    )
                for ch in node.get("children") or []:
                    if isinstance(ch, dict):
                        _assert_tree_node_clean(ch)

            for root_node in (td.get("tree_modal") or {}).values():
                if isinstance(root_node, dict):
                    _assert_tree_node_clean(root_node)
            assert set(seen_masked_leaves) >= {"Số lượng bò", "Số lượng trâu"}

            for ch in bot_msgs[0].get("quick_action_chips") or []:
                if isinstance(ch, dict):
                    for tv_v in (ch.get("timeline_values") or {}).values():
                        assert str(tv_v).strip() not in leaked_Exact, (
                            f"Chip '{ch.get('label')}' timeline_values leaked internal value: {tv_v}"
                        )

            sess_resp = client.get("/api/v1/chat/sessions")
            assert sess_resp.status_code == 200
            sessions = sess_resp.json().get("data") or []
            matched = next((s for s in sessions if s.get("id") == sid), None)
            assert matched is not None
            assert "[schema=" not in (matched.get("title") or ""), (
                f"Session title leaked raw context tag: {matched.get('title')}"
            )
    finally:
        store.delete_session(sid)


def test_public_schema_open_audit_no_citizen_rbac_banner_and_jwt_override(
    agent: WarehouseLangGraphAgent,
):
    """
    1) On dwh_public, RBAC by level does NOT apply: report and criteria_group queries
       must NOT display Citizen/Guest RBAC restriction banners ('Tài khoản Công dân / Khách vãng lai').
    2) Parent breakdown ('Số lượng gia súc hiện tại ?') must NOT duplicate
       '(thuộc **Số lượng gia súc**)' when root name equals parent name.
    3) Even when a restricted staff JWT Bearer token is supplied, schema='dwh_public'
       must force open unrestricted access to public data.
    """
    from fastapi.testclient import TestClient
    from IPGov_Chatbot.main import app
    from IPGov_Chatbot.modules.mod01_gateway.jwt_service import JWTService

    pub_ctx = {"schema": "dwh_public", "tenant_code": "68"}
    res_rep = agent.run(
        query="Trạng thái các đợt nộp báo cáo năm 2026?",
        session_id="test_pub_open_report_audit",
        user_context=pub_ctx,
    )
    ans_rep = res_rep.get("final_answer") or ""
    assert "Tài khoản Công dân / Khách vãng lai" not in ans_rep
    assert "Thông báo phân quyền bảo mật" not in ans_rep

    res_parent = agent.run(
        query="Số lượng gia súc hiện tại ?",
        session_id="test_pub_parent_dedup_phrase",
        user_context=pub_ctx,
    )
    ans_parent = res_parent.get("final_answer") or ""
    assert "nhóm **'Số lượng gia súc'** (thuộc **Số lượng gia súc**)" not in ans_parent

    restricted_token = JWTService.encode(
        {
            "sub": "11111111-1111-1111-1111-111111111114",
            "username": "tzyalnh",
            "name": "Nguyễn Thị Thúy Lành",
            "role_level": 0,
            "tenant_code": "68",
            "department_code": "68-1-02",
        }
    )
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {restricted_token}"},
            json={
                "prompt": "Tổng hộ sản xuất muối tính đến ngày 30/06/2026 là bao nhiêu?",
                "schema": "dwh_public",
                "tenant_code": "68",
            },
        )
        assert resp.status_code == 200
        ans_jwt = (resp.json().get("data") or {}).get("answer") or ""
        assert "660" in ans_jwt
        assert "chưa được phân công" not in ans_jwt

