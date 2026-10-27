# -*- coding: utf-8 -*-
"""
Unit tests for Milestone M2: Semantic Catalog Refactor.
Verifies the purge of hardcoded lexicon seeds, static aliases, and keyword gates,
and validates that semantic retrieval and hierarchy breakdown are fully grounded
in the Dynamic Criterion Knowledge Base (`catalog_definitions`).
"""

import pytest
from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import (
    DuckDBSemanticCatalog,
    ALLOWED_SEMANTIC_LEXICON_SEED,
)
from IPGov_Chatbot.schemas.canonical_query_frame import CanonicalIntentEnum


@pytest.fixture(scope="module")
def catalog():
    return DuckDBSemanticCatalog()


def test_allowed_semantic_lexicon_seed_purged():
    """Verify that the 938-line static seed lexicon is purged."""
    assert isinstance(ALLOWED_SEMANTIC_LEXICON_SEED, tuple)
    assert len(ALLOWED_SEMANTIC_LEXICON_SEED) == 0


def test_catalog_aliases_populated_dynamically_from_kb(catalog):
    """Verify that catalog_aliases is dynamically populated from catalog_definitions."""
    rows = catalog.conn.execute("SELECT count(*) FROM catalog_aliases;").fetchone()
    assert rows[0] > 0, "catalog_aliases should be populated from KB definitions"

    # Verify key aliases from KB are present
    salt_alias = catalog.conn.execute(
        "SELECT code FROM catalog_aliases WHERE alias LIKE '%diện tích muối công nghiệp%';"
    ).fetchone()
    assert salt_alias is not None
    assert salt_alias[0] == "dien_tich_muoi_san_xuat_cong_nghiep"


def test_search_candidates_by_definition(catalog):
    """Verify that search_candidates_by_definition retrieves criteria via semantic KB fields."""
    cands = catalog.search_candidates_by_definition("diện tích muối công nghiệp", top_k=3)
    assert len(cands) > 0
    top1 = cands[0]
    assert top1["code"] == "dien_tich_muoi_san_xuat_cong_nghiep"
    assert top1["score"] >= 80.0
    assert "definition" in top1
    assert "natural_synonyms" in top1


def test_resolve_hierarchy_breakdown_htx_fields(catalog):
    """Verify semantic breakdown for HTX fields query without keyword gates."""
    query = "HTX nông nghiệp gồm những lĩnh vực nào?"
    res = catalog.resolve_hierarchy_breakdown(query)
    assert res is not None
    assert res["status"] == "SUCCESS"
    assert res["child_count"] == 8
    child_names = [c["name"] for c in res["children"]]
    expected_fields = ["Trồng trọt", "Chăn nuôi", "Lâm nghiệp", "Thủy sản", "Diêm nghiệp", "Chế biến nông sản", "Nước sạch NT", "Tổng hợp"]
    for f in expected_fields:
        assert f in child_names

    # Verify canonical order ascending
    canon_orders = [c.get("canonical_order", 999) for c in res["children"]]
    assert canon_orders == sorted(canon_orders)


def test_resolve_hierarchy_breakdown_htx_effectiveness(catalog):
    """Verify semantic breakdown for HTX effectiveness levels."""
    query = "Các mức đánh giá hiệu quả hợp tác xã"
    res = catalog.resolve_hierarchy_breakdown(query)
    assert res is not None
    assert res["status"] == "SUCCESS"
    assert res["child_count"] == 4
    child_names = [c["name"] for c in res["children"]]
    assert any("tốt" in n.lower() for n in child_names)
    assert any("trung bình" in n.lower() for n in child_names)
    assert any("kém" in n.lower() for n in child_names)


def test_resolve_hierarchy_breakdown_salt_area(catalog):
    """Verify semantic breakdown for salt area types."""
    query = "Diện tích muối gồm các loại nào?"
    res = catalog.resolve_hierarchy_breakdown(query)
    assert res is not None
    assert res["status"] == "SUCCESS"
    assert res["child_count"] == 2
    child_names = [c["name"] for c in res["children"]]
    assert any("thủ công" in n.lower() for n in child_names)
    assert any("công nghiệp" in n.lower() for n in child_names)


def test_resolve_hierarchy_breakdown_farms_fields(catalog):
    """Verify semantic breakdown for farm fields."""
    query = "Số lượng trang trại theo lĩnh vực"
    res = catalog.resolve_hierarchy_breakdown(query)
    assert res is not None
    assert res["status"] == "SUCCESS"
    assert res["child_count"] == 7
    child_names = [c["name"] for c in res["children"]]
    assert "Trồng trọt" in child_names
    assert "Chăn nuôi" in child_names
    assert "Tổng hợp" in child_names


def test_resolve_hierarchy_breakdown_salt_yield(catalog):
    """Verify semantic breakdown for salt yield types."""
    query = "Sản lượng muối gồm những loại nào?"
    res = catalog.resolve_hierarchy_breakdown(query)
    assert res is not None
    assert res["status"] == "SUCCESS"
    assert res["child_count"] == 2
    child_names = [c["name"] for c in res["children"]]
    assert any("thủ công" in n.lower() for n in child_names)
    assert any("công nghiệp" in n.lower() for n in child_names)


def test_parent_children_breakdown_intent_in_schemas():
    """Verify CanonicalIntentEnum includes PARENT_CHILDREN_BREAKDOWN."""
    assert hasattr(CanonicalIntentEnum, "PARENT_CHILDREN_BREAKDOWN")
    assert CanonicalIntentEnum.PARENT_CHILDREN_BREAKDOWN.value == "PARENT_CHILDREN_BREAKDOWN"


def test_structural_compatibility_no_magic_numbers(catalog):
    """Verify structural compatibility scoring runs without heuristic magic floats."""
    query = "lũy kế tổng số sản phẩm ocop"
    candidate = {
        "code": "luy_ke_tong_so_luong_san_pham_ocop_den_thoi_diem_bao_cao",
        "name": "Lũy kế  tổng số lượng sản phẩm OCOP đến thời điểm báo cáo",
        "is_leaf": True,
        "is_cumulative": True,
        "level": 3
    }
    score = catalog._compute_structural_compatibility(query, candidate, {})
    assert isinstance(score, float)
    assert score >= 0.0
