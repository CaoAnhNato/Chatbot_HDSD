"""
Adversarial Stress Test Suite - Milestone 3 Challenger 2
Location: IPGov_Chatbot/tests/test_adversarial_m3_challenger2.py

Target:
Empirically stress test structural disambiguation refactor in `duckdb_semantic_catalog.py`:
1. Out-of-Scope Collisions:
   - Non-criteria queries ("3 mũ 2", "chào bạn", "thủ tục làm sổ đỏ", etc.) must NOT get boosted
     by aggregate bonuses or mistakenly map to random criteria.
2. Specificity vs Aggregate:
   - "chủ thể OCOP 3 sao", "chủ thể OCOP 4 sao", "chủ thể OCOP 5 sao" -> must route to specific leaf star rating.
   - "tổng số chủ thể OCOP" -> must route to aggregate.
   - Polarity check: chủ thể vs sản phẩm across star ratings and totals.
3. Branch Scoping:
   - "diện tích muối của tỉnh", "sản lượng muối của tỉnh" vs "chăn nuôi của liên hiệp htx",
     "chăn nuôi của hợp tác xã", "chăn nuôi của tổ hợp tác", "chăn nuôi của trang trại".
"""

import pytest
import uuid
from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog
from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import warehouse_agent


@pytest.fixture(scope="module")
def catalog():
    return DuckDBSemanticCatalog()


# ==============================================================================
# 1. OUT-OF-SCOPE COLLISIONS STRESS TESTS
# ==============================================================================
class TestOutOfScopeCollisions:
    """Stress test out-of-scope non-criteria queries against semantic catalog and agent."""

    @pytest.mark.parametrize("query", [
        "3 mũ 2",
        "chào bạn",
        "thủ tục làm sổ đỏ",
        "thời tiết thành phố Đà Lạt hôm nay",
        "cách làm hộ chiếu online",
        "hướng dẫn đăng ký kết hôn",
        "tính 15 nhân 20",
        "xin chào trợ lý ảo",
    ])
    def test_retrieve_candidate_metrics_empty_for_oos(self, catalog, query):
        """Out-of-scope queries must produce zero candidate metrics in pre-retrieval grounding."""
        cands = catalog.retrieve_candidate_metrics(query, top_k=3, score_threshold=0.40)
        assert len(cands) == 0, f"Query '{query}' produced spurious candidates: {cands}"

    @pytest.mark.parametrize("query", [
        "3 mũ 2",
        "chào bạn",
        "thủ tục làm sổ đỏ",
    ])
    def test_structural_compatibility_no_aggregate_boost_for_oos(self, catalog, query):
        """Out-of-scope queries must NOT trigger aggregate bonus (+10.0) in _compute_structural_compatibility."""
        # Check against an aggregate candidate like 'Tổng số lượng chủ thể sản phẩm OCOP trong năm'
        mock_cand_agg = {
            "name": "Tổng số lượng chủ thể sản phẩm OCOP trong năm",
            "is_leaf": False,
            "level": 1,
            "root_name": "Chương trình OCOP",
            "parent_name": "Chương trình OCOP",
        }
        score = catalog._compute_structural_compatibility(query, mock_cand_agg)
        # Should NOT have received +10.0 aggregate bonus
        # Query has no 'tổng', 'lũy kế', 'toàn bộ', 'chung', and conflicting/unmatched branch
        assert score <= 0.0, f"Query '{query}' unexpectedly received positive structural score: {score}"

    @pytest.mark.parametrize("query,forbidden_tokens", [
        ("3 mũ 2", ["9", "fact_report_criteria"]),
        ("chào bạn", ["fact_report_criteria", "Chỉ tiêu", "Giá trị"]),
        ("thủ tục làm sổ đỏ", ["fact_report_criteria", "Chỉ tiêu:", "Giá trị:"]),
    ])
    def test_e2e_oos_execution_guard(self, query, forbidden_tokens):
        """End-to-end execution must safely reject out-of-scope queries without hallucinating DWH cards."""
        session_id = f"test_oos_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(
            query=query,
            session_id=session_id,
            user_context={"role_level": 0, "tenant_code": "68"}
        )
        ans = res.get("final_answer", "")
        assert res.get("is_out_of_scope") is True or "ngoài phạm vi" in ans.lower() or "chào" in ans.lower(), (
            f"Query '{query}' failed out-of-scope guard! res: {res}"
        )
        for token in forbidden_tokens:
            assert token not in ans.split(), f"Query '{query}' produced forbidden token '{token}' in answer: {ans}"


# ==============================================================================
# 2. SPECIFICITY VS AGGREGATE STRESS TESTS
# ==============================================================================
class TestSpecificityVsAggregate:
    """Stress test leaf star rating specificity vs aggregate totals."""

    def test_chu_the_ocop_3_sao_leaf_routing(self, catalog):
        """'chủ thể OCOP 3 sao' must resolve to 3-star leaf, NOT aggregate or other stars."""
        cands, is_ambig, delta = catalog.find_top_k_candidates("chủ thể OCOP 3 sao", top_k=5)
        assert len(cands) >= 1, "Must find candidates"
        top1 = cands[0]
        name = top1["name"].lower()
        assert "3 sao" in name, f"Must match 3 sao: {top1}"
        assert "chủ thể" in name, f"Must match chủ thể: {top1}"
        assert "4 sao" not in name and "5 sao" not in name, f"Must not match 4 or 5 sao: {top1}"
        assert not name.startswith("tổng "), f"Must not match aggregate 'tổng': {top1}"

    def test_chu_the_ocop_4_sao_leaf_routing(self, catalog):
        """'chủ thể OCOP 4 sao' must resolve to 4-star leaf, NOT aggregate or other stars."""
        cands, is_ambig, delta = catalog.find_top_k_candidates("chủ thể OCOP 4 sao", top_k=5)
        assert len(cands) >= 1, "Must find candidates"
        top1 = cands[0]
        name = top1["name"].lower()
        assert "4 sao" in name, f"Must match 4 sao: {top1}"
        assert "chủ thể" in name, f"Must match chủ thể: {top1}"
        assert "3 sao" not in name and "5 sao" not in name, f"Must not match 3 or 5 sao: {top1}"
        assert not name.startswith("tổng "), f"Must not match aggregate 'tổng': {top1}"

    def test_chu_the_ocop_5_sao_leaf_routing(self, catalog):
        """'chủ thể OCOP 5 sao' must resolve to 5-star leaf, NOT aggregate or other stars."""
        cands, is_ambig, delta = catalog.find_top_k_candidates("chủ thể OCOP 5 sao", top_k=5)
        assert len(cands) >= 1, "Must find candidates"
        top1 = cands[0]
        name = top1["name"].lower()
        assert "5 sao" in name, f"Must match 5 sao: {top1}"
        assert "chủ thể" in name, f"Must match chủ thể: {top1}"
        assert "3 sao" not in name and "4 sao" not in name, f"Must not match 3 or 4 sao: {top1}"
        assert not name.startswith("tổng "), f"Must not match aggregate 'tổng': {top1}"

    def test_tong_so_chu_the_ocop_aggregate_routing(self, catalog):
        """'tổng số chủ thể OCOP' must resolve to aggregate metric, NOT specific star rating."""
        cands, is_ambig, delta = catalog.find_top_k_candidates("tổng số chủ thể OCOP", top_k=5)
        assert len(cands) >= 1, "Must find candidates"
        top1 = cands[0]
        name = top1["name"].lower()
        assert "chủ thể" in name, f"Must match chủ thể: {top1}"
        assert ("tổng" in name or "lũy kế" in name), f"Must be aggregate metric: {top1}"
        assert "3 sao" not in name and "4 sao" not in name and "5 sao" not in name, (
            f"Must NOT route to narrow star rating: {top1}"
        )

    def test_san_pham_vs_chu_the_polarity_separation(self, catalog):
        """Verify polarity: 'sản phẩm OCOP 3 sao' matches 'sản phẩm', NOT 'chủ thể'."""
        cands_sp, _, _ = catalog.find_top_k_candidates("sản phẩm OCOP 3 sao", top_k=5)
        assert len(cands_sp) >= 1
        top_sp = cands_sp[0]["name"].lower()
        assert "sản phẩm" in top_sp, f"Must match sản phẩm: {cands_sp[0]}"
        assert "chủ thể" not in top_sp, f"Must NOT match chủ thể: {cands_sp[0]}"

        cands_ct, _, _ = catalog.find_top_k_candidates("chủ thể OCOP 3 sao", top_k=5)
        assert len(cands_ct) >= 1
        top_ct = cands_ct[0]["name"].lower()
        assert "chủ thể" in top_ct, f"Must match chủ thể: {cands_ct[0]}"

    def test_e2e_ocop_star_execution(self):
        """End-to-end verification for OCOP star rating query."""
        session_id = f"test_ocop_star_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(
            query="Hiện nay toàn tỉnh có bao nhiêu chủ thể sản phẩm OCOP đạt 4 sao ?",
            session_id=session_id,
            user_context={"role_level": 0, "tenant_code": "68"}
        )
        ans = res.get("final_answer", "")
        assert not res.get("is_clarification_needed"), f"Should not clarify: {ans}"
        assert "4 sao" in ans, f"Answer must reference 4 sao: {ans}"
        assert "chủ thể" in ans.lower(), f"Answer must reference chủ thể: {ans}"


# ==============================================================================
# 3. BRANCH SCOPING STRESS TESTS
# ==============================================================================
class TestBranchScoping:
    """Stress test branch-scoped disambiguation: Muối vs Chăn nuôi across 4 branches."""

    def test_dien_tich_muoi_tinh(self, catalog):
        """'diện tích muối của tỉnh' must route to salt production area in Diêm nghiệp."""
        cands, _, _ = catalog.find_top_k_candidates("diện tích muối của tỉnh", top_k=5)
        assert len(cands) >= 1, "Must find candidates"
        top1 = cands[0]
        tree_text = f"{top1.get('root_name', '')} {top1.get('parent_name', '')} {top1['name']}".lower()
        assert "muối" in tree_text or "diêm nghiệp" in tree_text, f"Must route to salt branch: {top1}"
        assert "diện tích" in tree_text, f"Must contain diện tích: {top1}"

    def test_san_luong_muoi_tinh(self, catalog):
        """'sản lượng muối của tỉnh' must route to salt output in Diêm nghiệp."""
        cands, _, _ = catalog.find_top_k_candidates("sản lượng muối của tỉnh", top_k=5)
        assert len(cands) >= 1, "Must find candidates"
        top1 = cands[0]
        tree_text = f"{top1.get('root_name', '')} {top1.get('parent_name', '')} {top1['name']}".lower()
        assert "muối" in tree_text or "diêm nghiệp" in tree_text, f"Must route to salt branch: {top1}"
        assert "sản lượng" in tree_text, f"Must contain sản lượng: {top1}"

    def test_chan_nuoi_branch_isolation_4_branches(self, catalog):
        """Verify strict isolation of 'Chăn nuôi' across LHHTX, HTX, THT, and Trang trại."""
        queries_and_expected = [
            ("chăn nuôi của liên hiệp htx", "lhhtx", "Liên hiệp"),
            ("chăn nuôi của hợp tác xã", "htx", "Hợp tác xã"),
            ("chăn nuôi của tổ hợp tác", "tht", "Tổ hợp tác"),
            ("chăn nuôi của trang trại", "trang_trai", "Trang trại"),
        ]
        for q, expected_branch_tag, expected_branch_name in queries_and_expected:
            cands, _, _ = catalog.find_top_k_candidates(q, top_k=5)
            assert len(cands) >= 1, f"Failed for query '{q}'"
            top1 = cands[0]
            root_and_parent = f"{top1.get('root_name', '')} {top1.get('parent_name', '')}".lower()
            assert "chăn nuôi" in top1["name"].lower(), f"Must be Chăn nuôi for '{q}': {top1}"
            if expected_branch_tag == "lhhtx":
                assert "liên hiệp" in root_and_parent or "lhhtx" in root_and_parent, (
                    f"Expected LHHTX branch for '{q}', got: {top1}"
                )
            elif expected_branch_tag == "htx":
                assert ("hợp tác xã" in root_and_parent or "htx" in root_and_parent) and "liên hiệp" not in root_and_parent, (
                    f"Expected HTX branch for '{q}', got: {top1}"
                )
            elif expected_branch_tag == "tht":
                assert "tổ hợp tác" in root_and_parent or "tht" in root_and_parent, (
                    f"Expected THT branch for '{q}', got: {top1}"
                )
            elif expected_branch_tag == "trang_trai":
                assert "trang trại" in root_and_parent, (
                    f"Expected Trang trại branch for '{q}', got: {top1}"
                )

    def test_e2e_chan_nuoi_lhhtx_single_metric_value(self):
        """End-to-end execution of 'cho tôi biết số liệu chăn nuôi của liên hiệp hợp tác xã'."""
        session_id = f"test_lhhtx_cn_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(
            query="cho tôi biết số liệu chăn nuôi của liên hiệp hợp tác xã ngày 30/4",
            session_id=session_id,
            user_context={"role_level": 0, "tenant_code": "68"}
        )
        ans = res.get("final_answer", "")
        assert not res.get("is_clarification_needed"), f"Should not clarify: {ans}"
        assert "1" in ans, f"LHHTX chăn nuôi value 1 missing: {ans}"
        assert "31/03/2026" in ans, f"Milestone date missing: {ans}"
        assert "Tổng số LHHTX phân theo lĩnh vực" in ans or "Liên hiệp HTX" in ans, (
            f"Must reference LHHTX parent branch: {ans}"
        )
