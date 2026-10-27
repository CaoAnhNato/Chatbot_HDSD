# -*- coding: utf-8 -*-
"""
Adversarial Challenger Test Suite: Milestone M2 Iteration 2
Authored by: challenger_m2_1_iter2
Empirical verification of candidate retrieval and hierarchy breakdown:
1. Entity isolation across LHHTX vs HTX vs THT vs Trang trại (TT).
2. Exact canonical warehouse ordering verification (canonical_order ASC).
3. Protection against single-leaf hijacking across all entities.
4. Robustness against OOD queries.
"""

import pytest
from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog


@pytest.fixture(scope="module")
def catalog():
    return DuckDBSemanticCatalog()


class TestLHHTXvsHTXvsTHTvsTrangTrai:
    """Stress test entity isolation for fields ('lĩnh vực')."""

    @pytest.mark.parametrize("query,expected_root,expected_parent,expected_count", [
        ("các lĩnh vực của hợp tác xã", "HTX nông nghiệp", "Số lượng HTX phân theo lĩnh vực", 8),
        ("các ngành nghề của hợp tác xã nông nghiệp", "HTX nông nghiệp", "Số lượng HTX phân theo lĩnh vực", 8),
        ("các lĩnh vực của htx", "HTX nông nghiệp", "Số lượng HTX phân theo lĩnh vực", 8),
        ("các lĩnh vực của liên hiệp hợp tác xã", "Liên hiệp HTX nông nghiệp", "Tổng số LHHTX phân theo lĩnh vực", 8),
        ("các ngành nghề của liên hiệp hợp tác xã nông nghiệp", "Liên hiệp HTX nông nghiệp", "Tổng số LHHTX phân theo lĩnh vực", 8),
        ("các lĩnh vực của liên hiệp htx", "Liên hiệp HTX nông nghiệp", "Tổng số LHHTX phân theo lĩnh vực", 8),
        ("các lĩnh vực của lhhtx", "Liên hiệp HTX nông nghiệp", "Tổng số LHHTX phân theo lĩnh vực", 8),
        ("các lĩnh vực của tổ hợp tác", "Tổ hợp tác nông nghiệp", "Tổng số THT phân theo lĩnh vực", 8),
        ("các ngành nghề của tổ hợp tác nông nghiệp", "Tổ hợp tác nông nghiệp", "Tổng số THT phân theo lĩnh vực", 8),
        ("các lĩnh vực của tht", "Tổ hợp tác nông nghiệp", "Tổng số THT phân theo lĩnh vực", 8),
        ("các lĩnh vực của trang trại", "Trang trại", "Tổng số lượng TT phân theo lĩnh vực", 7),
        ("các ngành nghề phân loại trang trại", "Trang trại", "Tổng số lượng TT phân theo lĩnh vực", 7),
        ("các lĩnh vực của tt", "Trang trại", "Tổng số lượng TT phân theo lĩnh vực", 7),
    ])
    def test_fields_breakdown_entity_isolation(self, catalog, query, expected_root, expected_parent, expected_count):
        res = catalog.resolve_hierarchy_breakdown(query)
        assert res is not None, f"Query '{query}' returned None"
        assert res["status"] == "SUCCESS"
        act_root = res.get("root_name") or res["parent_node"].get("root_name")
        act_parent = res["parent_node"]["name"]
        act_count = res["child_count"]
        assert act_root == expected_root, f"Root mismatch for '{query}': expected '{expected_root}', got '{act_root}'"
        assert act_parent == expected_parent, f"Parent mismatch for '{query}': expected '{expected_parent}', got '{act_parent}'"
        assert act_count == expected_count, f"Child count mismatch for '{query}': expected {expected_count}, got {act_count}"

        # Canonical ordering check
        orders = [c.get("canonical_order", 999) for c in res["children"]]
        assert orders == sorted(orders), f"Canonical order violated in '{query}': {orders}"


class TestEfficiencyBreakdownAcrossEntities:
    """Stress test entity isolation for operational efficiency ('hiệu quả hoạt động')."""

    @pytest.mark.parametrize("query,expected_root,expected_count", [
        ("đánh giá hiệu quả hoạt động của hợp tác xã", "HTX nông nghiệp", 4),
        ("các mức hiệu quả hoạt động của HTX", "HTX nông nghiệp", 4),
        ("đánh giá hiệu quả hoạt động của tổ hợp tác", "Tổ hợp tác nông nghiệp", 3),
        ("các mức hiệu quả hoạt động của THT", "Tổ hợp tác nông nghiệp", 3),
        ("đánh giá hiệu quả hoạt động của trang trại", "Trang trại", 3),
        ("các mức hiệu quả hoạt động của kinh tế trang trại", "Trang trại", 3),
    ])
    def test_efficiency_breakdown_by_entity(self, catalog, query, expected_root, expected_count):
        res = catalog.resolve_hierarchy_breakdown(query)
        assert res is not None, f"Query '{query}' returned None"
        assert res["status"] == "SUCCESS"
        act_root = res.get("root_name") or res["parent_node"].get("root_name")
        act_parent = res["parent_node"]["name"]
        act_count = res["child_count"]
        assert act_root == expected_root, f"Root mismatch for '{query}': expected '{expected_root}', got '{act_root}'"
        assert "Hiệu quả hoạt động" in act_parent
        assert act_count == expected_count, f"Count mismatch for '{query}': expected {expected_count}, got {act_count}"

        orders = [c.get("canonical_order", 999) for c in res["children"]]
        assert orders == sorted(orders), f"Canonical order violated in '{query}': {orders}"


class TestProductionLinkageBreakdownAcrossEntities:
    """Stress test entity isolation for production linkage ('liên kết sản xuất')."""

    @pytest.mark.parametrize("query,expected_root", [
        ("tình hình liên kết sản xuất của hợp tác xã", "HTX nông nghiệp"),
        ("tình hình liên kết sản xuất của tổ hợp tác", "Tổ hợp tác nông nghiệp"),
        ("tình hình liên kết sản xuất của trang trại", "Trang trại"),
    ])
    def test_linkage_breakdown_by_entity(self, catalog, query, expected_root):
        res = catalog.resolve_hierarchy_breakdown(query)
        assert res is not None, f"Query '{query}' returned None"
        assert res["status"] == "SUCCESS"
        act_root = res.get("root_name") or res["parent_node"].get("root_name")
        act_parent = res["parent_node"]["name"]
        assert act_root == expected_root, f"Root mismatch for '{query}': expected '{expected_root}', got '{act_root}'"
        assert "Liên kết" in act_parent
        assert res["child_count"] == 2

        orders = [c.get("canonical_order", 999) for c in res["children"]]
        assert orders == sorted(orders), f"Canonical order violated in '{query}': {orders}"


class TestWarehouseCanonicalOrderingPreservation:
    """Strictly verify canonical ordering matches warehouse data."""

    def test_htx_fields_exact_names_and_sequence(self, catalog):
        res = catalog.resolve_hierarchy_breakdown("các lĩnh vực của hợp tác xã nông nghiệp")
        assert res is not None
        names = [c["name"] for c in res["children"]]
        expected = [
            "Trồng trọt", "Chăn nuôi", "Lâm nghiệp", "Thủy sản",
            "Diêm nghiệp", "Chế biến nông sản", "Nước sạch NT", "Tổng hợp"
        ]
        assert names == expected, f"Sequence mismatch: {names}"

    def test_lhhtx_fields_exact_names_and_sequence(self, catalog):
        res = catalog.resolve_hierarchy_breakdown("các lĩnh vực của liên hiệp hợp tác xã")
        assert res is not None
        names = [c["name"] for c in res["children"]]
        expected = [
            "Trồng trọt", "Chăn nuôi", "Lâm nghiệp", "Thủy sản",
            "Diêm nghiệp", "Chế biến nông sản", "Nước sạch NT", "Tổng hợp"
        ]
        assert names == expected, f"Sequence mismatch: {names}"

    def test_tht_fields_exact_names_and_sequence(self, catalog):
        res = catalog.resolve_hierarchy_breakdown("các lĩnh vực của tổ hợp tác nông nghiệp")
        assert res is not None
        names = [c["name"] for c in res["children"]]
        expected = [
            "Trồng trọt", "Chăn nuôi", "Lâm nghiệp", "Thủy sản",
            "Diêm nghiệp", "Chế biến nông sản", "Nước sạch NT", "Tổng hợp"
        ]
        assert names == expected, f"Sequence mismatch: {names}"

    def test_trang_trai_fields_exact_names_and_sequence(self, catalog):
        res = catalog.resolve_hierarchy_breakdown("các lĩnh vực của trang trại")
        assert res is not None
        names = [c["name"] for c in res["children"]]
        expected = [
            "Trồng trọt", "Chăn nuôi", "Lâm nghiệp", "Nuôi trồng thủy sản",
            "Sản xuất muôi", "Chế biến nông sản", "Tổng hợp"
        ]
        assert names == expected, f"Sequence mismatch: {names}"

    def test_htx_efficiency_exact_names_and_sequence(self, catalog):
        res = catalog.resolve_hierarchy_breakdown("các mức đánh giá hiệu quả hợp tác xã")
        assert res is not None
        names = [c["name"] for c in res["children"]]
        expected = [
            "Số HTX nông nghiệp hoạt động hiệu quả tốt",
            "Số HTX nông nghiệp hoạt động hiệu quả trung bình",
            "Số HTX nông nghiệp hoạt động kém hiệu quả",
            "Chưa đủ điều kiện đánh giá",
        ]
        assert names == expected, f"Sequence mismatch: {names}"


class TestSingleLeafHijackingAdversarial:
    """Verify single-leaf queries across entities return None to let single-metric handler process them."""

    @pytest.mark.parametrize("query", [
        "số lượng hợp tác xã nông nghiệp hoạt động hiệu quả tốt trong quý 1",
        "số lượng hợp tác xã nông nghiệp hoạt động kém hiệu quả",
        "số THT nông nghiệp hoạt động hiệu quả tốt",
        "số TT nông nghiệp hoạt động hiệu quả tốt",
        "chăn nuôi của liên hiệp hợp tác xã",
        "chăn nuôi của hợp tác xã",
        "chăn nuôi của tổ hợp tác",
        "chăn nuôi của trang trại",
    ])
    def test_single_leaf_not_hijacked_by_breakdown(self, catalog, query):
        res = catalog.resolve_hierarchy_breakdown(query)
        assert res is None, f"Single leaf query '{query}' was hijacked by breakdown: {res['parent_node']['name']}"
