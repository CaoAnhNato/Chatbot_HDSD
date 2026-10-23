"""
Unit & Integration Contract Tests cho 5 Nâng Cấp Generative UI / Hybrid Chat-GUI (TC-CONTRACT-01 .. TC-CONTRACT-10).
Kiểm chứng trực tiếp trên dữ liệu thật của CSDL PostgreSQL (vna_wom_dev) và DuckDB Semantic Catalog.
"""

import pytest
from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import WarehouseLangGraphAgent


@pytest.fixture(scope="module")
def agent() -> WarehouseLangGraphAgent:
    return WarehouseLangGraphAgent()


def test_req_q01_level1_hierarchy_and_tree_modal_payload(agent: WarehouseLangGraphAgent):
    """TC-CONTRACT-01: Verify REQ-Q01 returns 9 Level 1 rows, raw_fact_count == 114, and tree_modal."""
    res = agent.run(
        "Danh sách các chỉ tiêu được phê duyệt năm 2026?",
        session_id="test_contract_01",
    )
    tab = res.get("tabular_data")
    assert tab is not None
    assert len(tab.get("level1_rows", [])) == 9
    assert tab.get("raw_fact_count") == 114
    tree_modal = tab.get("tree_modal") or {}
    assert len(tree_modal) == 9
    # Verify Chương trình OCOP has 4 Level 2 children and 12 Level 3 grandchildren (16 descendants)
    ocop_root = next(
        (node for node in tree_modal.values() if "chương trình ocop" in str(node.get("name", "")).lower()),
        None,
    )
    assert ocop_root is not None
    l2_children = ocop_root.get("children") or []
    assert len(l2_children) == 4
    l3_grandchildren = sum(len(ch.get("children") or []) for ch in l2_children)
    assert l3_grandchildren == 12


def test_sc_1_1_empty_month_no_latest_value_leak(agent: WarehouseLangGraphAgent):
    """TC-CONTRACT-02: Verify SC-1.1 empty month (tháng 1/2026) does not leak 30/09/2026 values and Quarter 2 masks unapproved nodes."""
    res_m1 = agent.run(
        "Các chỉ tiêu có số liệu được phê duyệt trong tháng 1/2026?",
        session_id="test_contract_02_m1",
    )
    ans_m1 = res_m1.get("final_answer") or ""
    assert "chưa ghi nhận" in ans_m1.lower() or "không tìm thấy" in ans_m1.lower()
    assert res_m1.get("tabular_data") is None

    res_q2 = agent.run(
        "Danh sách các chỉ tiêu được phê duyệt trong Quý 2/2026?",
        session_id="test_contract_02_q2",
    )
    tab_q2 = res_q2.get("tabular_data")
    assert tab_q2 is not None
    assert tab_q2.get("temporal_scope", {}).get("query_suffix") == "Quý 2/2026"
    assert "{period}" in (tab_q2.get("context_query_template") or "")
    tree_q2 = tab_q2.get("tree_modal") or {}
    assert len(tree_q2) > 0

    # Direct catalog check: build_criteria_tree_for_rows(rows=[], has_temporal_filter=True) must never leak latest_value
    empty_tree_map, empty_l1 = agent.catalog.build_criteria_tree_for_rows(
        rows=[], has_temporal_filter=True
    )
    for l1_row in empty_l1:
        assert l1_row.get("value") is None
        assert "Chưa có số liệu" in str(l1_row.get("gia_tri_moi_nhat") or "")
    for root_node in empty_tree_map.values():
        assert root_node.get("value") is None
        for ch2 in root_node.get("children") or []:
            assert ch2.get("value") is None
            for ch3 in ch2.get("children") or []:
                assert ch3.get("value") is None


def test_tree_modal_nodes_contain_complete_5_field_metadata(agent: WarehouseLangGraphAgent):
    """TC-CONTRACT-03: Verify every node in tree_modal contains id, code, name, level, value, office_name, mission_name, report_date."""
    res = agent.run(
        "Danh sách các chỉ tiêu được phê duyệt năm 2026?",
        session_id="test_contract_03",
    )
    tree_modal = (res.get("tabular_data") or {}).get("tree_modal") or {}
    assert len(tree_modal) > 0

    def _walk(node: dict):
        for required_key in ("id", "code", "name", "level", "office_name", "mission_name", "report_date"):
            assert required_key in node, f"Missing {required_key} in tree_modal node {node.get('name')}"
        if node.get("value") is not None and str(node.get("value")).strip() not in ("", "-"):
            assert node.get("report_date") and "/" in str(node.get("report_date"))
        for ch in node.get("children") or []:
            _walk(ch)

    for root_node in tree_modal.values():
        _walk(root_node)


def test_req_q02_single_metric_card_contains_timeline_snapshots(agent: WarehouseLangGraphAgent):
    """TC-CONTRACT-04: Verify REQ-Q02 attaches single_metric_card with timeline_snapshots sorted ascending and accurate delta_prev."""
    res = agent.run(
        "Cho tôi xem số liệu chỉ tiêu Diện tích muối công nghiệp năm 2026?",
        session_id="test_contract_04",
    )
    tab = res.get("tabular_data")
    assert tab is not None
    card = tab.get("single_metric_card")
    assert card is not None
    assert "diện tích muối sản xuất công nghiệp" in card.get("criteria_name", "").lower()
    snaps = card.get("timeline_snapshots") or []
    assert len(snaps) >= 2
    iso_dates = [s["iso_date"] for s in snaps]
    assert iso_dates == sorted(iso_dates)
    assert snaps[0]["date"] == "31/03/2026"
    assert snaps[0]["value"] == "520"
    assert snaps[-1]["date"] == "31/07/2026"
    assert snaps[-1]["value"] == "0"
    assert snaps[-1]["delta_prev"] == -520.0


def test_sc24_action_chips_contain_preview_values_and_child_counts(agent: WarehouseLangGraphAgent):
    """TC-CONTRACT-05: Verify quick_action_chips for SC-2.4 include preview_value, child_count, is_parent_group and respect temporal filters."""
    # Case 1: Chương trình OCOP (has 4 Level 2 children with preview_value and child_count)
    res_ocop = agent.run(
        "Số lượng chỉ tiêu chương trình OCOP năm 2026 là bao nhiêu?",
        session_id="test_contract_05_ocop",
    )
    chips_ocop = res_ocop.get("quick_action_chips") or []
    assert len(chips_ocop) == 4
    sp_chip = next((c for c in chips_ocop if "tổng số lượng sản phẩm ocop trong năm" in c["label"].lower()), None)
    ct_chip = next((c for c in chips_ocop if "tổng số lượng chủ thể sản phẩm ocop trong năm" in c["label"].lower()), None)
    assert sp_chip is not None
    assert sp_chip.get("preview_value") == "32"
    assert sp_chip.get("child_count") == 3
    assert sp_chip.get("is_parent_group") is True
    assert ct_chip is not None
    assert ct_chip.get("preview_value") == "17"
    assert ct_chip.get("child_count") == 3
    assert ct_chip.get("is_parent_group") is True

    # Case 2: Liên hiệp HTX nông nghiệp (SC-2.4b with 5 valued leaves + 1 intermediate Level 2 parent group)
    res_lhhtx = agent.run(
        "Cho tôi biết số liệu chỉ tiêu Liên hiệp HTX nông nghiệp năm 2026?",
        session_id="test_contract_05_lhhtx",
    )
    chips_lhhtx = res_lhhtx.get("quick_action_chips") or []
    assert len(chips_lhhtx) == 6
    c_dt = next((c for c in chips_lhhtx if "doanh thu bình quân" in c["label"].lower()), None)
    c_lk = next((c for c in chips_lhhtx if "lũy kế đến thời điểm báo cáo" in c["label"].lower()), None)
    c_lv = next((c for c in chips_lhhtx if "tổng số lhhtx phân theo lĩnh vực" in c["label"].lower()), None)
    assert c_dt is not None and c_dt.get("preview_value") == "16,500"
    assert c_lk is not None and c_lk.get("preview_value") == "4"
    assert c_lv is not None
    assert c_lv.get("is_parent_group") is True
    assert c_lv.get("child_count") == 8
    assert "8 chỉ tiêu con" in str(c_lv.get("unit_or_status") or "")

    # Case 2b: HTX nông nghiệp (SC-2.4b where intermediate Level 2 parent group has preview_value=None and child_count=8)
    res_htx = agent.run(
        "Cho tôi biết số liệu chỉ tiêu HTX nông nghiệp năm 2026?",
        session_id="test_contract_05_htx",
    )
    chips_htx = res_htx.get("quick_action_chips") or []
    c_htx_lv = next((c for c in chips_htx if "phân theo lĩnh vực" in c["label"].lower()), None)
    assert c_htx_lv is not None
    assert c_htx_lv.get("is_parent_group") is True
    assert c_htx_lv.get("child_count") == 8

    # Case 3: Parent criterion with temporal filter (Trang trại ngày 23/4 -> nearest snapshot 31/03/2026)
    res_tt = agent.run(
        "Số liệu chỉ tiêu trang trại ngày 23/4 là bao nhiêu?",
        session_id="test_contract_05_tt_2304",
    )
    ans_tt = res_tt.get("final_answer") or ""
    assert "31/03/2026" in ans_tt
    assert "lệch 23 ngày" in ans_tt
    chips_tt = res_tt.get("quick_action_chips") or []
    assert len(chips_tt) > 0
    for ch in chips_tt:
        assert "23/04/2026" in ch.get("query_text", "")


def test_sc22_nearest_snapshot_dual_bound_and_timeline_snapshots(agent: WarehouseLangGraphAgent):
    """TC-CONTRACT-06: Verify SC-2.2 nearest snapshot lookup returns dual-bound notice and full timeline_snapshots."""
    res = agent.run(
        "Số lượng HTX trồng trọt ngày 15/05/2026 là bao nhiêu?",
        session_id="test_contract_06",
    )
    ans = res.get("final_answer") or ""
    assert "31/03/2026" in ans
    assert "30/06/2026" in ans
    tab = res.get("tabular_data")
    assert tab is not None
    card = tab.get("single_metric_card")
    assert card is not None
    assert card.get("temporal_shift_notice") is not None
    assert len(card.get("timeline_snapshots") or []) >= 2


def test_sc21_duplicate_leaf_multi_parent_rows_contract(agent: WarehouseLangGraphAgent):
    """TC-CONTRACT-07: Verify SC-2.1 duplicate leaf criterion returns multi_parent_rows with 4 branches, temporal_scope, and context_query_template."""
    res = agent.run(
        "Số lượng chỉ tiêu trồng trọt năm 2026 là bao nhiêu?",
        session_id="test_contract_07",
    )
    tab = res.get("tabular_data")
    assert tab is not None
    mp_rows = tab.get("multi_parent_rows") or []
    assert len(mp_rows) == 4
    assert tab.get("temporal_scope", {}).get("year") == "2026"
    assert "{period}" in (tab.get("context_query_template") or "")


def test_req_q05_audit_payload_supports_client_quick_filters(agent: WarehouseLangGraphAgent):
    """TC-CONTRACT-08: Verify REQ-Q05 / SC-5.1 returns status_summary, draft_criteria_rows, and draft_vs_approved_diff."""
    res = agent.run(
        "Kiểm tra tình hình nộp báo cáo và đối chiếu bản nháp với bản phê duyệt năm 2026?",
        session_id="test_contract_08",
        user_context={"role_level": 1, "tenant_code": "68"},
    )
    tab = res.get("tabular_data")
    assert tab is not None
    summary = tab.get("status_summary") or {}
    assert summary.get("approved") == 6
    assert summary.get("draft") == 3
    assert summary.get("total") == 9
    assert len(tab.get("draft_criteria_rows") or []) >= 10
    assert len(tab.get("draft_vs_approved_diff") or []) >= 7


def test_req_q03_and_req_q04_temporal_scope_metadata(agent: WarehouseLangGraphAgent):
    """TC-CONTRACT-09: Verify REQ-Q03 and REQ-Q04 include temporal_scope metadata, context_query_template, and preserve query_suffix in action_query."""
    res_q03 = agent.run(
        "Trong Quý 2/2026, lĩnh vực Nông nghiệp có các nhiệm vụ nào có số liệu báo cáo?",
        session_id="test_contract_09_q03",
    )
    tab_q03 = res_q03.get("tabular_data")
    assert tab_q03 is not None
    t_scope = tab_q03.get("temporal_scope") or {}
    assert t_scope.get("query_suffix") == "Quý 2/2026"
    assert "{period}" in (tab_q03.get("context_query_template") or "")
    rows_q03 = tab_q03.get("rows") or []
    assert len(rows_q03) >= 1
    assert "Quý 2/2026" in rows_q03[0].get("action_query", "")

    res_q04 = agent.run(
        "Hiển thị các chỉ tiêu Cấp 1 của nhiệm vụ Phát triển nông thôn Quý 2/2026?",
        session_id="test_contract_09_q04",
    )
    tab_q04 = res_q04.get("tabular_data")
    assert tab_q04 is not None
    assert (tab_q04.get("temporal_scope") or {}).get("query_suffix") == "Quý 2/2026"
    assert "{period}" in (tab_q04.get("context_query_template") or "")


def test_timeline_snapshots_single_period_and_empty_criterion_graceful_degradation(agent: WarehouseLangGraphAgent):
    """TC-CONTRACT-10: Verify graceful degradation when a criterion has 0 approved values (SC-2.3)."""
    res = agent.run(
        "Cho tôi biết số liệu chỉ tiêu Liên kết sản xuất năm 2026?",
        session_id="test_contract_10",
    )
    tab = res.get("tabular_data")
    assert tab is not None
    card = tab.get("single_metric_card")
    assert card is not None
    assert "chưa có số liệu" in card.get("current_value", "").lower()
    assert card.get("timeline_snapshots") == []

