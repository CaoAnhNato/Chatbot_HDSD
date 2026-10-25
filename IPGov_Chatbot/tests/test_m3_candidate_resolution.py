# -*- coding: utf-8 -*-
"""
Empirical Candidate Resolution & Stress Testing for Milestone 3 (R3.1)
Targeted Verification:
1. "lũy kế tổng số lượng chủ thể sản phẩm OCOP" -> must resolve to cumulative subject criterion, not 5-star leaf.
2. "tổng số lượng sản phẩm OCOP trong năm" -> must resolve to annual product criterion.
3. Adversarial / Perturbation Variations on OCOP Metrics.
"""

import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog
from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import warehouse_agent


@pytest.fixture(scope="module")
def catalog():
    return DuckDBSemanticCatalog()


def test_inspect_all_ocop_nodes(catalog):
    """Inspect all OCOP and subject criteria in DuckDB catalog."""
    rows = catalog.conn.execute("""
        SELECT code, name, root_name, parent_name, level, is_leaf
        FROM catalog_criteria_hierarchy
        WHERE lower(name) LIKE '%ocop%' OR lower(name) LIKE '%chủ thể%'
           OR lower(parent_name) LIKE '%chủ thể%' OR lower(root_name) LIKE '%ocop%'
        ORDER BY level, code;
    """).fetchall()
    print(f"\n--- Total OCOP Nodes in Hierarchy: {len(rows)} ---")
    for r in rows:
        print(f"[{r[0]}] '{r[1]}' | root: '{r[2]}' | parent: '{r[3]}' | lvl: {r[4]} | leaf: {r[5]}")
    assert len(rows) > 0


def test_cumulative_subject_resolution(catalog):
    """
    Orchestrator Requirement:
    'lũy kế tổng số lượng chủ thể sản phẩm OCOP' -> must resolve to cumulative subject criterion, not 5-star leaf.
    """
    query = "lũy kế tổng số lượng chủ thể sản phẩm OCOP"
    cands, is_ambig, delta = catalog.find_top_k_candidates(query, top_k=5)
    assert len(cands) > 0, "No candidates returned"

    top1 = cands[0]
    top1_name = top1["name"].lower()
    print(f"\nQUERY: '{query}' -> Top 1: [{top1['code']}] '{top1['name']}' (score: {top1['score']}, delta: {delta})")

    # Must be cumulative
    assert any(k in top1_name for k in ["lũy kế", "đến thời điểm báo cáo"]), (
        f"Top 1 must be cumulative, got: '{top1['name']}'"
    )

    # Must NOT be a 5-star leaf
    for star in ["3 sao", "4 sao", "5 sao"]:
        assert star not in top1_name, f"Top 1 must not be a star leaf, got: '{top1['name']}'"

    # Must NOT be annual
    assert "trong năm" not in top1_name, f"Top 1 must not be annual, got: '{top1['name']}'"


def test_annual_product_resolution(catalog):
    """
    Orchestrator Requirement:
    'tổng số lượng sản phẩm OCOP trong năm' -> must resolve to annual product criterion.
    """
    query = "tổng số lượng sản phẩm OCOP trong năm"
    cands, is_ambig, delta = catalog.find_top_k_candidates(query, top_k=5)
    assert len(cands) > 0, "No candidates returned"

    top1 = cands[0]
    top1_name = top1["name"].lower()
    print(f"\nQUERY: '{query}' -> Top 1: [{top1['code']}] '{top1['name']}' (score: {top1['score']}, delta: {delta})")

    # Must be annual product criterion
    assert "trong năm" in top1_name, f"Top 1 must be annual, got: '{top1['name']}'"
    assert "sản phẩm" in top1_name, f"Top 1 must be product metric, got: '{top1['name']}'"
    assert "lũy kế" not in top1_name, f"Top 1 must not be cumulative, got: '{top1['name']}'"
    assert top1["code"] == "tong_so_luong_san_pham_ocop_trong_nam"


def test_adversarial_ocop_variations(catalog):
    """Adversarial stress testing across multiple linguistic variations."""
    cases = [
        {
            "query": "bạn hãy cho tôi biết lũy kế tổng số lượng chủ thể sản phẩm theo dữ liệu mới nhất",
            "must_have": ["lũy kế", "chủ thể"],
            "must_not_have": ["5 sao", "trong năm"],
        },
        {
            "query": "bạn hãy cho tôi biết lũy kế tổng số lượng chủ thể sản phẩm OCOP theo dữ liệu mới nhất",
            "must_have": ["lũy kế"],
            "must_not_have": ["5 sao", "trong năm"],
        },
        {
            "query": "số lượng chủ thể sản phẩm OCOP 5 sao",
            "must_have": ["chủ thể", "5 sao"],
            "must_not_have": ["3 sao", "4 sao"],
        },
        {
            "query": "tổng số lượng chủ thể sản phẩm OCOP trong năm",
            "must_have": ["chủ thể", "trong năm"],
            "must_not_have": ["lũy kế", "5 sao"],
        },
        {
            "query": "sản phẩm OCOP 3 sao trong năm",
            "must_have": ["3 sao", "sản phẩm"],
            "must_not_have": ["chủ thể", "5 sao"],
        },
    ]

    for tc in cases:
        q = tc["query"]
        cands, is_ambig, delta = catalog.find_top_k_candidates(q, top_k=5)
        assert len(cands) > 0, f"No candidates for query '{q}'"
        top1 = cands[0]
        top1_name = top1["name"].lower()
        print(f"\nAdversarial: '{q}' -> Top 1: [{top1['code']}] '{top1['name']}' (score: {top1['score']})")

        for kw in tc["must_have"]:
            assert kw in top1_name or (kw == "chủ thể" and "chủ thể" in top1_name), (
                f"Query '{q}' failed: expected '{kw}' in '{top1['name']}'"
            )
        for nkw in tc["must_not_have"]:
            assert nkw not in top1_name, (
                f"Query '{q}' failed: unexpected '{nkw}' in '{top1['name']}'"
            )


def test_agent_e2e_ocop_flow():
    """Verify warehouse agent end-to-end response for OCOP queries."""
    res1 = warehouse_agent.run(query="tổng số lượng sản phẩm OCOP trong năm")
    ans1 = res1.get("final_answer", "")
    assert "Tổng số lượng sản phẩm OCOP trong năm" in ans1, f"Expected metric missing in: {ans1}"

    res2 = warehouse_agent.run(query="bạn hãy cho tôi biết lũy kế tổng số lượng chủ thể sản phẩm theo dữ liệu mới nhất")
    ans2 = res2.get("final_answer", "")
    assert "Lũy kế" in ans2 or "lũy kế" in ans2, f"Cumulative missing in: {ans2}"
    assert "5 sao" not in ans2.split("\n")[0], f"5-star leaf wrongly resolved: {ans2}"
