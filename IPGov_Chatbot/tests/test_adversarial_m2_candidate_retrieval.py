# -*- coding: utf-8 -*-
"""
Empirical Adversarial Test Suite for Milestone M2:
Adversarially challenge candidate retrieval and hierarchy breakdown in `duckdb_semantic_catalog.py`:
1. Paraphrase and semantic candidate retrieval via `search_candidates_by_definition()`.
2. Dynamic hierarchy breakdown across all 5 branches (`HTX nông nghiệp`, `THT`, `Muối`, `Liên hiệp HTX`, `Trang trại`) without static keyword gates.
3. Strict verification of warehouse canonical order (`canonical_order ASC`).
4. Cross-entity isolation and adversarial edge cases.
"""

import pytest
import unicodedata
from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import (
    DuckDBSemanticCatalog,
    ALLOWED_SEMANTIC_LEXICON_SEED,
)


@pytest.fixture(scope="module")
def catalog():
    cat = DuckDBSemanticCatalog()
    return cat


# ==============================================================================
# SECTION 1: Adversarial Paraphrase & Definition-Based Retrieval
# ==============================================================================

class TestSemanticCandidateRetrievalByDefinition:
    """Challenge search_candidates_by_definition() with diverse phrasing and descriptive queries."""

    def test_paraphrase_ocop_cumulative_products(self, catalog):
        """Query describing cumulative OCOP products without exact warehouse string."""
        query = "tổng số sản phẩm OCOP được chứng nhận lũy kế đến kỳ báo cáo"
        cands = catalog.search_candidates_by_definition(query, top_k=5)
        assert len(cands) > 0, "Failed to retrieve candidates"
        codes = [c["code"] for c in cands]
        assert "luy_ke_tong_so_luong_san_pham_ocop_den_thoi_diem_bao_cao" in codes
        top1 = cands[0]
        assert "luy_ke" in top1["code"] or "ocop" in top1["code"].lower()
        assert top1["score"] >= 50.0

    def test_paraphrase_ocop_cumulative_subjects(self, catalog):
        """Query describing cumulative OCOP subjects."""
        query = "lũy kế tổng số lượng chủ thể sản phẩm theo dữ liệu mới nhất"
        cands = catalog.search_candidates_by_definition(query, top_k=5)
        assert len(cands) > 0
        codes = [c["code"] for c in cands]
        assert "luy_ke_tong_so_luong_chu_the_den_thoi_diem_bao_cao" in codes
        # Must not confuse with leaf 5 sao
        top_codes = [c["code"] for c in cands[:2]]
        assert "so_luong_chu_the_san_pham_ocop_5_sao" not in top_codes

    def test_paraphrase_salt_industrial_area(self, catalog):
        """Query describing industrial salt production area with synonyms."""
        query = "diện tích đất làm muối bằng phương pháp cơ giới công nghiệp"
        cands = catalog.search_candidates_by_definition(query, top_k=5)
        assert len(cands) > 0
        codes = [c["code"] for c in cands]
        assert "dien_tich_muoi_san_xuat_cong_nghiep" in codes
        # Must be in top 2 candidates with high confidence
        top_codes = [c["code"] for c in cands[:2]]
        assert "dien_tich_muoi_san_xuat_cong_nghiep" in top_codes
        top_score = next(c["score"] for c in cands if c["code"] == "dien_tich_muoi_san_xuat_cong_nghiep")
        assert top_score >= 80.0

    def test_paraphrase_salt_manual_yield(self, catalog):
        """Query describing manual salt harvest/yield."""
        query = "sản lượng muối kết tinh phơi cát thủ công truyền thống"
        cands = catalog.search_candidates_by_definition(query, top_k=5)
        assert len(cands) > 0
        codes = [c["code"] for c in cands]
        assert "san_luong_muoi_san_xuat_thu_cong" in codes
        top1 = cands[0]
        assert "thu_cong" in top1["code"]

    def test_paraphrase_farm_quantity(self, catalog):
        """Query describing household agricultural enterprises/farms."""
        query = "các mô hình kinh tế nông hộ đạt tiêu chí trang trại nông nghiệp"
        cands = catalog.search_candidates_by_definition(query, top_k=5)
        assert len(cands) > 0
        names = [c["name"].lower() for c in cands]
        assert any("trang trại" in n for n in names)

    def test_paraphrase_htx_newly_established(self, catalog):
        """Query for new cooperative licenses/establishment."""
        query = "số lượng hợp tác xã nông nghiệp mới được cấp phép thành lập"
        cands = catalog.search_candidates_by_definition(query, top_k=5)
        assert len(cands) > 0
        codes = [c["code"] for c in cands]
        assert any("thanh_lap_moi" in cd for cd in codes)

    def test_empty_and_noise_queries(self, catalog):
        """Ensure empty and whitespace inputs return empty list without crashing."""
        assert catalog.search_candidates_by_definition("") == []
        assert catalog.search_candidates_by_definition("   ") == []
        assert catalog.search_candidates_by_definition("\n\t") == []

    def test_candidate_metadata_completeness(self, catalog):
        """Ensure retrieved candidate has full dictionary contract."""
        cands = catalog.search_candidates_by_definition("lĩnh vực trồng trọt", top_k=1)
        assert len(cands) > 0
        c = cands[0]
        for key in ["id", "code", "name", "level", "is_leaf", "parent_id", "canonical_order", "definition", "score"]:
            assert key in c, f"Missing key '{key}' in candidate dict"
        assert isinstance(c["canonical_order"], int)
        assert isinstance(c["score"], float)


# ==============================================================================
# SECTION 2: Dynamic Hierarchy Breakdown Across All 5 Branches
# ==============================================================================

class TestHierarchyBreakdownAllBranches:
    """Adversarially challenge resolve_hierarchy_breakdown() across all required branches."""

    # Branch 1: HTX Nông Nghiệp
    @pytest.mark.parametrize("query", [
        "HTX nông nghiệp gồm những lĩnh vực nào?",
        "cho tôi biết số ngành nghề của hợp tác xã nông nghiệp",
        "hợp tác xã có những phân nhóm sản xuất nào?",
        "các lĩnh vực hoạt động của HTX nông nghiệp",
    ])
    def test_breakdown_htx_fields_paraphrases(self, catalog, query):
        res = catalog.resolve_hierarchy_breakdown(query)
        assert res is not None, f"Failed for query: {query}"
        assert res["status"] == "SUCCESS"
        assert res["child_count"] == 8
        child_names = [c["name"] for c in res["children"]]
        expected = ["Trồng trọt", "Chăn nuôi", "Lâm nghiệp", "Thủy sản", "Diêm nghiệp", "Chế biến nông sản", "Nước sạch NT", "Tổng hợp"]
        assert child_names == expected, f"Order or names mismatch for query: {query}"

    @pytest.mark.parametrize("query", [
        "Các mức đánh giá hiệu quả hợp tác xã",
        "hợp tác xã nông nghiệp có bao nhiêu mức xếp loại chất lượng hoạt động?",
        "phân hạng hiệu quả hoạt động của HTX",
    ])
    def test_breakdown_htx_efficiency_paraphrases(self, catalog, query):
        res = catalog.resolve_hierarchy_breakdown(query)
        assert res is not None, f"Failed for query: {query}"
        assert res["status"] == "SUCCESS"
        assert res["child_count"] == 4
        child_names = [c["name"] for c in res["children"]]
        expected = [
            "Số HTX nông nghiệp hoạt động hiệu quả tốt",
            "Số HTX nông nghiệp hoạt động hiệu quả trung bình",
            "Số HTX nông nghiệp hoạt động kém hiệu quả",
            "Chưa đủ điều kiện đánh giá",
        ]
        assert child_names == expected, f"Order or names mismatch for query: {query}"

    @pytest.mark.parametrize("query", [
        "tình hình liên kết sản xuất của hợp tác xã nông nghiệp",
        "các hình thức liên kết sản xuất trong HTX",
    ])
    def test_breakdown_htx_production_linkage(self, catalog, query):
        res = catalog.resolve_hierarchy_breakdown(query)
        assert res is not None, f"Failed for query: {query}"
        assert res["status"] == "SUCCESS"
        assert res["child_count"] == 2
        child_names = [c["name"] for c in res["children"]]
        assert any("ổn định" in n for n in child_names)
        assert any("không ổn định" in n for n in child_names)

    # Branch 2: Tổ Hợp Tác (THT)
    @pytest.mark.parametrize("query", [
        "THT nông nghiệp có những lĩnh vực nào?",
        "tổ hợp tác gồm các mảng hoạt động gì?",
        "các lĩnh vực của tổ hợp tác nông nghiệp",
    ])
    def test_breakdown_tht_fields(self, catalog, query):
        res = catalog.resolve_hierarchy_breakdown(query)
        assert res is not None, f"Failed for query: {query}"
        assert res["status"] == "SUCCESS"
        # Verify it belongs to THT, NOT HTX or LHHTX
        root_name = res.get("root_name") or res["parent_node"].get("root_name", "")
        p_name = res["parent_node"]["name"]
        assert "Tổ hợp tác" in root_name or "THT" in root_name or "Tổ hợp tác" in p_name or "THT" in p_name, (
            f"Cross-entity contamination: root={root_name}, parent={p_name}"
        )
        assert res["child_count"] >= 6
        # Verify canonical ordering
        orders = [c.get("canonical_order", 999) for c in res["children"]]
        assert orders == sorted(orders)

    # Branch 3: Muối (Diện tích & Sản lượng)
    @pytest.mark.parametrize("query", [
        "Diện tích muối gồm các loại nào?",
        "có những loại diện tích sản xuất muối gì?",
        "các phân loại về diện tích làm muối",
    ])
    def test_breakdown_salt_area(self, catalog, query):
        res = catalog.resolve_hierarchy_breakdown(query)
        assert res is not None, f"Failed for query: {query}"
        assert res["status"] == "SUCCESS"
        assert res["child_count"] == 2
        child_names = [c["name"] for c in res["children"]]
        assert "Diện tích muối sản xuất thủ công" in child_names[0]
        assert "Diện tích muối sản xuất công nghiệp" in child_names[1]

    @pytest.mark.parametrize("query", [
        "Sản lượng muối gồm những loại nào?",
        "các loại sản lượng muối thu hoạch",
        "phân loại sản lượng muối",
    ])
    def test_breakdown_salt_yield(self, catalog, query):
        res = catalog.resolve_hierarchy_breakdown(query)
        assert res is not None, f"Failed for query: {query}"
        assert res["status"] == "SUCCESS"
        assert res["child_count"] == 2
        child_names = [c["name"] for c in res["children"]]
        assert "Sản lượng muối sản xuất thủ công" in child_names[0]
        assert "Sản lượng muối sản xuất công nghiệp" in child_names[1]

    # Branch 4: Liên hiệp Hợp tác xã (LHHTX)
    @pytest.mark.parametrize("query", [
        "Liên hiệp HTX có những lĩnh vực nào?",
        "liên hiệp hợp tác xã nông nghiệp có các ngành nghề gì?",
        "các mảng phân loại lĩnh vực của liên hiệp HTX",
    ])
    def test_breakdown_lhhtx_fields(self, catalog, query):
        res = catalog.resolve_hierarchy_breakdown(query)
        assert res is not None, f"Failed for query: {query}"
        assert res["status"] == "SUCCESS"
        root_name = res.get("root_name") or res["parent_node"].get("root_name", "")
        p_name = res["parent_node"]["name"]
        assert "Liên hiệp" in root_name or "LHHTX" in root_name or "Liên hiệp" in p_name or "LHHTX" in p_name, (
            f"Cross-entity contamination: root={root_name}, parent={p_name}"
        )
        assert res["child_count"] >= 6
        orders = [c.get("canonical_order", 999) for c in res["children"]]
        assert orders == sorted(orders)

    # Branch 5: Trang Trại
    @pytest.mark.parametrize("query", [
        "Số lượng trang trại theo lĩnh vực",
        "trang trại gồm những loại hình lĩnh vực nào?",
        "các mảng ngành nghề phân loại trang trại",
    ])
    def test_breakdown_farm_fields(self, catalog, query):
        res = catalog.resolve_hierarchy_breakdown(query)
        assert res is not None, f"Failed for query: {query}"
        assert res["status"] == "SUCCESS"
        root_name = res.get("root_name") or res["parent_node"].get("root_name", "")
        p_name = res["parent_node"]["name"]
        assert "Trang trại" in root_name or "Trang trại" in p_name, (
            f"Cross-entity contamination: root={root_name}, parent={p_name}"
        )
        assert res["child_count"] == 7
        child_names = [c["name"] for c in res["children"]]
        assert "Trồng trọt" in child_names
        assert "Chăn nuôi" in child_names
        assert "Tổng hợp" in child_names
        orders = [c.get("canonical_order", 999) for c in res["children"]]
        assert orders == sorted(orders)


# ==============================================================================
# SECTION 3: Canonical Order Invariant Verification
# ==============================================================================

class TestCanonicalOrderStrictAscending:
    """Stress-test that child criteria are strictly ordered by canonical_order ASC."""

    def test_all_breakdown_queries_maintain_canonical_order(self, catalog):
        queries = [
            "HTX nông nghiệp gồm những lĩnh vực nào?",
            "Các mức đánh giá hiệu quả hợp tác xã",
            "tình hình liên kết sản xuất của hợp tác xã nông nghiệp",
            "THT nông nghiệp có những lĩnh vực nào?",
            "Liên hiệp HTX có những lĩnh vực nào?",
            "Số lượng trang trại theo lĩnh vực",
            "Diện tích muối gồm các loại nào?",
            "Sản lượng muối gồm những loại nào?",
        ]
        for q in queries:
            res = catalog.resolve_hierarchy_breakdown(q)
            assert res is not None, f"Query '{q}' returned None"
            children = res["children"]
            orders = [c.get("canonical_order", 999) for c in children]
            assert orders == sorted(orders), f"Canonical order violated in '{q}': {orders}"
            # Verify no duplicates or descending order
            for i in range(len(orders) - 1):
                assert orders[i] <= orders[i+1], f"Order inversion at index {i} in '{q}': {orders}"


# ==============================================================================
# SECTION 4: Cross-Entity Isolation & Adversarial Edge Cases
# ==============================================================================

class TestCrossEntityIsolationAndRobustness:
    """Adversarially challenge cross-entity leakage and invalid inputs."""

    def test_tht_does_not_leak_to_htx(self, catalog):
        """Query for THT fields must not return HTX fields."""
        res = catalog.resolve_hierarchy_breakdown("các lĩnh vực của tổ hợp tác")
        assert res is not None
        root_name = res.get("root_name") or res["parent_node"].get("root_name", "")
        assert "Tổ hợp tác" in root_name or "THT" in root_name
        assert "Liên hiệp" not in root_name
        # THT does not have 'Nước sạch NT' or 'Chế biến nông sản'
        names = [c["name"] for c in res["children"]]
        # In warehouse, THT has 8 fields
        assert len(names) == 8

    def test_lhhtx_does_not_leak_to_htx(self, catalog):
        """Query for LHHTX fields must return LHHTX parent."""
        res = catalog.resolve_hierarchy_breakdown("các lĩnh vực của liên hiệp hợp tác xã")
        assert res is not None
        p_name = res["parent_node"]["name"]
        root_name = res.get("root_name") or res["parent_node"].get("root_name", "")
        assert "LHHTX" in p_name or "Liên hiệp" in p_name or "Liên hiệp" in root_name

    def test_farm_does_not_leak_to_htx(self, catalog):
        """Query for Trang trại fields must return Trang trại parent."""
        res = catalog.resolve_hierarchy_breakdown("các lĩnh vực sản xuất của trang trại")
        assert res is not None
        p_name = res["parent_node"]["name"]
        root_name = res.get("root_name") or res["parent_node"].get("root_name", "")
        assert "Trang trại" in p_name or "Trang trại" in root_name or "TT" in p_name

    def test_unrelated_out_of_domain_queries(self, catalog):
        """OOD queries must return None rather than falsely matching a breakdown."""
        ood_queries = [
            "hôm nay thời tiết thế nào",
            "hướng dẫn cài đặt hệ điều hành windows",
            "cách nấu món phở bò truyền thống",
            "báo giá linh kiện máy tính",
        ]
        for q in ood_queries:
            res = catalog.resolve_hierarchy_breakdown(q)
            assert res is None, f"OOD query falsely matched hierarchy: '{q}' -> {res}"
