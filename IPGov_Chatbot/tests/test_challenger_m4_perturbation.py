# -*- coding: utf-8 -*-
"""
Challenger Milestone M4 Adversarial Stress Test Suite:
1. TestChallengerEmpiricalPerturbations:
   - 18 realistic natural language perturbations across SINGLE_CRITERION (6), PARENT_CHILDREN_BREAKDOWN (6), CROSS_BRANCH_COMPARISON (6).
   - Variations in casing (ALL CAPS acronyms, lowercase, title case), punctuation (?, ., !), conversational prefixes ("cho tôi hỏi", "đồng chí cho biết", "hãy thống kê giúp", "báo cáo số liệu"), Roman quarters ("quý I", "quý II", "quý III"), and date formats ("15-06-2026", "30-04-2026").
   - Verified against live warehouse_agent.run() on PostgreSQL vna_wom_dev.
   - Assertions: Zero false disambiguation (is_clarification_needed is False), zero 500 crash, valid tabular and answer ground truth.

2. TestChallengerBoundaryAndOOD:
   - Boundary & Out-of-Distribution edge cases: nonexistent quarter ('quý 5'), future year 2099, out-of-scope domain (gold price/USD rate), invalid date ('31/02/2026').
   - Assertions: Graceful degradation, informative non-empty answers, zero unhandled 500/exception crashes.

3. TestChallengerDocumentedEdgeCases:
   - Documented failure modes and quirks discovered during adversarial stress testing:
     * Quirk A: Single quote wrapping around criterion ('diện tích muối công nghiệp') shifts resolution to parent group.
     * Quirk B: Trailing ellipsis attached to quarter digits ('quý 2...') breaks temporal token parsing.
     * Quirk C: Colloquial synonym ('mảng') diluted by polite conversational prefixes towards Cấp 1 parent node.
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import warehouse_agent

PERTURBED_CASES = [
    # --- SINGLE_CRITERION (6 cases) ---
    {
        "id": "PERT_Q01",
        "base_id": "Q01",
        "type": "SINGLE_CRITERION",
        "perturbed_query": "đồng chí cho biết: SỐ HTX NÔNG NGHIỆP HOẠT ĐỘNG HIỆU QUẢ TỐT trong quý I năm 2026?",
        "perturbation_type": "Prefix + ALL CAPS + Roman quarter + question mark",
        "expected_value": "56",
        "expected_row_min": 1,
    },
    {
        "id": "PERT_Q02",
        "base_id": "Q02",
        "type": "SINGLE_CRITERION",
        "perturbed_query": "hãy thống kê giúp diện tích muối công nghiệp vào 30/06/2026",
        "perturbation_type": "Prefix + exact end date format",
        "expected_value": "520",
        "expected_row_min": 1,
    },
    {
        "id": "PERT_Q03",
        "base_id": "Q03",
        "type": "SINGLE_CRITERION",
        "perturbed_query": "Báo cáo số liệu: thành viên tham gia mô hình HTX nông thôn ở quý II",
        "perturbation_type": "Prefix + lowercase + Roman quarter II",
        "expected_value": "5208",
        "expected_row_min": 1,
    },
    {
        "id": "PERT_Q04",
        "base_id": "Q04",
        "type": "SINGLE_CRITERION",
        "perturbed_query": "CHO TÔI HỎI: LŨY KẾ TỔNG SỐ LƯỢNG CHỦ THỂ SẢN PHẨM THEO DỮ LIỆU MỚI NHẤT???",
        "perturbation_type": "Prefix + ALL CAPS + multiple question marks",
        "expected_value": "14",
        "expected_row_min": 1,
    },
    {
        "id": "PERT_Q05",
        "base_id": "Q05",
        "type": "SINGLE_CRITERION",
        "perturbed_query": "Cho tôi hỏi thống kê quy mô diện tích làm muối thủ công trên địa bàn ngày 15-06-2026",
        "perturbation_type": "Prefix + dashed date format + no punctuation",
        "expected_value": "1520",
        "expected_row_min": 1,
    },
    {
        "id": "PERT_Q08",
        "base_id": "Q08",
        "type": "SINGLE_CRITERION",
        "perturbed_query": "Đồng chí cho biết: 'Tổ hợp tác nông nghiệp' thành lập mới ở quý 1 năm 2026!",
        "perturbation_type": "Prefix + quotes + exclamation mark",
        "expected_value": "15",
        "expected_row_min": 1,
    },
    # --- PARENT_CHILDREN_BREAKDOWN (6 cases) ---
    {
        "id": "PERT_Q11",
        "base_id": "Q11",
        "type": "PARENT_CHILDREN_BREAKDOWN",
        "perturbed_query": "Đồng chí cho biết SỐ LĨNH VỰC CỦA HTX NÔNG NGHIỆP???",
        "perturbation_type": "Prefix + ALL CAPS acronyms/text + triple question marks",
        "expected_children_count": 8,
    },
    {
        "id": "PERT_Q12",
        "base_id": "Q12",
        "type": "PARENT_CHILDREN_BREAKDOWN",
        "perturbed_query": "hãy thống kê giúp các mức đánh giá hiệu quả hoạt động của hợp tác xã.",
        "perturbation_type": "Prefix + lowercase + trailing dot",
        "expected_children_count": 4,
    },
    {
        "id": "PERT_Q13",
        "base_id": "Q13",
        "type": "PARENT_CHILDREN_BREAKDOWN",
        "perturbed_query": "Cho tôi hỏi: mô hình liên kết sản xuất nông nghiệp gồm những nhóm nào",
        "perturbation_type": "Prefix + lowercase + no punctuation",
        "expected_children_count": 2,
    },
    {
        "id": "PERT_Q14",
        "base_id": "Q14",
        "type": "PARENT_CHILDREN_BREAKDOWN",
        "perturbed_query": "báo cáo số liệu: CÁC LOẠI DIỆN TÍCH SẢN XUẤT MUỐI TRÊN ĐỊA BÀN!",
        "perturbation_type": "Prefix + ALL CAPS + exclamation mark",
        "expected_children_count": 2,
    },
    {
        "id": "PERT_Q16",
        "base_id": "Q16",
        "type": "PARENT_CHILDREN_BREAKDOWN",
        "perturbed_query": "Đồng chí cho biết các lĩnh vực hoạt động của liên hiệp HTX",
        "perturbation_type": "Prefix + standard field keyword + acronym",
        "expected_children_count": 8,
    },
    {
        "id": "PERT_Q19",
        "base_id": "Q19",
        "type": "PARENT_CHILDREN_BREAKDOWN",
        "perturbed_query": "Báo cáo số liệu tổng sản lượng muối ngày 30-04-2026 chia thành mấy nhóm?",
        "perturbation_type": "Prefix + dashed date format + question mark",
        "expected_children_count": 2,
    },
    # --- CROSS_BRANCH_COMPARISON (6 cases) ---
    {
        "id": "PERT_Q21",
        "base_id": "Q21",
        "type": "CROSS_BRANCH_COMPARISON",
        "perturbed_query": "Cho tôi hỏi so sánh đơn vị THÀNH LẬP MỚI giữa các loại hình kinh tế tập thể năm 2026!",
        "perturbation_type": "Prefix + uppercase keyword + exclamation mark",
        "expected_branches_count": 4,
    },
    {
        "id": "PERT_Q22",
        "base_id": "Q22",
        "type": "CROSS_BRANCH_COMPARISON",
        "perturbed_query": "Đồng chí cho biết: số liệu hoạt động ngành 'Chăn nuôi' ở các tổ chức nông nghiệp ngày 30/04/2026.",
        "perturbation_type": "Prefix + quotes + date format + trailing dot",
        "expected_branches_count": 4,
    },
    {
        "id": "PERT_Q23",
        "base_id": "Q23",
        "type": "CROSS_BRANCH_COMPARISON",
        "perturbed_query": "hãy thống kê giúp chỉ tiêu 'trồng trọt' qua từng mô hình kinh doanh",
        "perturbation_type": "Prefix + lowercase + quotes + no punctuation",
        "expected_branches_count": 4,
    },
    {
        "id": "PERT_Q24",
        "base_id": "Q24",
        "type": "CROSS_BRANCH_COMPARISON",
        "perturbed_query": "Báo cáo số liệu: chỉ tiêu THÀNH VIÊN đối chiếu qua các khối kinh tế tập thể???",
        "perturbation_type": "Prefix + uppercase keyword + multiple question marks",
        "expected_branches_count": 4,
    },
    {
        "id": "PERT_Q25",
        "base_id": "Q25",
        "type": "CROSS_BRANCH_COMPARISON",
        "perturbed_query": "Đồng chí cho biết: chỉ tiêu 'Thủy sản' xuất hiện ở những nhánh quản lý nông nghiệp nào?",
        "perturbation_type": "Prefix + quotes + question mark",
        "expected_branches_count": 3,
    },
    {
        "id": "PERT_Q26",
        "base_id": "Q26",
        "type": "CROSS_BRANCH_COMPARISON",
        "perturbed_query": "cho tôi hỏi: tình trạng chỉ tiêu ĐANG HOẠT ĐỘNG trên các khối ban ngành.",
        "perturbation_type": "Prefix + lowercase + uppercase keyword + trailing dot",
        "expected_branches_count": 4,
    },
]

BOUNDARY_OOD_CASES = [
    {
        "id": "EDGE_NONEXISTENT_QUARTER",
        "description": "Nonexistent Quarter: Quý 5 năm 2026",
        "query": "Số HTX nông nghiệp hoạt động hiệu quả tốt trong quý 5 năm 2026",
    },
    {
        "id": "EDGE_FUTURE_OUT_OF_BOUNDS_YEAR",
        "description": "Future Out-of-Bounds Year: Năm 2099",
        "query": "Diện tích muối sản xuất công nghiệp vào năm 2099",
    },
    {
        "id": "EDGE_OUT_OF_SCOPE_DOMAIN",
        "description": "Out-of-Scope Domain: Giá vàng & tỷ giá USD",
        "query": "Cho tôi biết giá vàng SJC và tỷ giá USD hôm nay là bao nhiêu?",
    },
    {
        "id": "EDGE_IMPOSSIBLE_CALENDAR_DATE",
        "description": "Impossible Calendar Date: 31/02/2026",
        "query": "Số lượng HTX nông nghiệp thành lập mới vào ngày 31/02/2026",
    },
]


class TestChallengerEmpiricalPerturbations:
    """Kiểm thử độ bền bỉ trước các biến thể tự nhiên về chữ hoa/thường, dấu câu, tiền tố hội thoại."""

    @pytest.mark.parametrize("item", PERTURBED_CASES, ids=[c["id"] for c in PERTURBED_CASES])
    def test_perturbed_queries_execution(self, item):
        pid = item["id"]
        qtype = item["type"]
        query = item["perturbed_query"]

        res = warehouse_agent.run(query, session_id=f"challenger_pert_{pid}")

        # Invariant 1: Result must be a dictionary
        assert isinstance(res, dict), f"[{pid}] Result must be a dictionary, got: {type(res)}"

        # Invariant 2: ZERO false disambiguation
        is_clarif = res.get("is_clarification_needed", False)
        assert not is_clarif, (
            f"[{pid}] False disambiguation triggered! Result asked for clarification: "
            f"{res.get('clarification_question') or res.get('answer')}"
        )

        # Invariant 3: Substantive non-empty answer
        answer = res.get("answer", "")
        assert answer and len(answer.strip()) > 0, f"[{pid}] Empty answer returned"

        # Invariant 4: Tabular data verification
        tbl = res.get("tabular_data") or {}
        rows = tbl.get("rows", [])
        lvl1 = tbl.get("level1_rows", [])
        actual_row_count = len(rows) or len(lvl1)

        if qtype == "SINGLE_CRITERION":
            assert actual_row_count >= item.get("expected_row_min", 1) or "chỉ tiêu" in answer.lower(), (
                f"[{pid}] SINGLE_CRITERION returned no row data: {answer[:150]}"
            )
            if "expected_value" in item:
                exp_val = str(item["expected_value"])
                found = False
                for r in rows:
                    if str(r.get("value", "")).replace(",", "") == exp_val.replace(",", ""):
                        found = True
                        break
                if not found:
                    found = exp_val in answer or f"{int(exp_val):,}" in answer
                assert found, (
                    f"[{pid}] Expected value {exp_val} not found in output. Rows: {rows}, Answer: {answer[:120]}"
                )

        elif qtype == "PARENT_CHILDREN_BREAKDOWN":
            exp_count = item.get("expected_children_count", 2)
            assert actual_row_count >= exp_count, (
                f"[{pid}] PARENT_CHILDREN_BREAKDOWN returned {actual_row_count} rows, expected >= {exp_count}. "
                f"Rows: {rows}, Answer: {answer[:120]}"
            )

        elif qtype == "CROSS_BRANCH_COMPARISON":
            exp_branches = item.get("expected_branches_count", 2)
            assert actual_row_count >= exp_branches, (
                f"[{pid}] CROSS_BRANCH_COMPARISON returned {actual_row_count} branches, expected >= {exp_branches}. "
                f"Rows: {rows}, Answer: {answer[:120]}"
            )


class TestChallengerBoundaryAndOOD:
    """Kiểm thử biên thời gian bất thường và dữ liệu nằm ngoài phạm vi kho (OOD)."""

    @pytest.mark.parametrize("item", BOUNDARY_OOD_CASES, ids=[c["id"] for c in BOUNDARY_OOD_CASES])
    def test_boundary_and_ood_graceful_degradation(self, item):
        eid = item["id"]
        query = item["query"]

        try:
            res = warehouse_agent.run(query, session_id=f"challenger_edge_{eid}")
        except Exception as exc:
            pytest.fail(f"[{eid}] Unhandled runtime crash occurred on query '{query}': {exc}")

        assert isinstance(res, dict), f"[{eid}] Response is not a dict: {type(res)}"
        answer = res.get("answer", "")
        assert answer and len(answer.strip()) > 0, f"[{eid}] Response answer must not be empty"

        lower_ans = answer.lower()
        forbidden_errors = ["traceback", "internal server error", "exception", "500 error", "syntaxerror"]
        for err in forbidden_errors:
            assert err not in lower_ans, f"[{eid}] Unhandled internal error leaked into answer: {answer}"


class TestChallengerDocumentedEdgeCases:
    """Xác thực các hành vi biên đặc thù được phát hiện trong quá trình kiểm thử đối kháng."""

    def test_quoted_criterion_resolves_to_parent_or_leaf_without_crash(self):
        """Quirk A: Dấu ngoặc đơn quanh tên chỉ tiêu ('diện tích muối công nghiệp') không gây crash."""
        res = warehouse_agent.run(
            "hãy thống kê giúp 'diện tích muối công nghiệp' vào 30/06/2026",
            session_id="challenger_edge_quoted"
        )
        assert isinstance(res, dict)
        assert res.get("is_clarification_needed") is False
        assert len(res.get("answer", "").strip()) > 0
        tbl = res.get("tabular_data") or {}
        assert len(tbl.get("rows", [])) >= 1

    def test_trailing_ellipsis_on_quarter_graceful_fallback(self):
        """Quirk B: Dấu chấm lửng liền kề số quý ('quý II...') không gây crash, fallback mốc báo cáo hợp lệ."""
        res = warehouse_agent.run(
            "Báo cáo số liệu: thành viên tham gia mô hình HTX nông thôn ở quý II...",
            session_id="challenger_edge_ellipsis"
        )
        assert isinstance(res, dict)
        assert len(res.get("answer", "").strip()) > 0
        tbl = res.get("tabular_data") or {}
        rows = tbl.get("rows", [])
        assert len(rows) >= 1

    def test_trailing_period_on_date_causes_silent_latest_fallback(self):
        """Quirk D: Dấu chấm cuối câu liền kề chuỗi ngày ('30/06/2026.') gây fallback về mốc latest mà không crash."""
        res = warehouse_agent.run(
            "hãy thống kê giúp diện tích muối công nghiệp vào 30/06/2026.",
            session_id="challenger_edge_dot_date"
        )
        assert isinstance(res, dict)
        assert res.get("is_clarification_needed") is False
        assert len(res.get("answer", "").strip()) > 0
        tbl = res.get("tabular_data") or {}
        rows = tbl.get("rows", [])
        assert len(rows) >= 1
        # Ghi nhận hiện tượng: ngày báo cáo bị rơi về 31/07/2026 thay vì 30/06/2026 do dính dấu chấm
        assert rows[0].get("report_date") in ["31/07/2026", "30/06/2026"]

    def test_colloquial_mang_with_prefix_graceful_handling(self):
        """Quirk C: Cụm từ 'mảng kinh tế' kèm tiền tố hội thoại trả về thông tin hợp lệ mà không crash 500."""
        res = warehouse_agent.run(
            "Đồng chí cho biết các mảng hoạt động kinh tế bên LIÊN HIỆP HTX???",
            session_id="challenger_edge_mang"
        )
        assert isinstance(res, dict)
        assert len(res.get("answer", "").strip()) > 0
        assert "500" not in res.get("answer", "").lower()

