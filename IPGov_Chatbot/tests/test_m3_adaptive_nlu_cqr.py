# -*- coding: utf-8 -*-
"""
Specification Test Suite for Milestone M3: Adaptive RAG + NLU & Multi-Turn CQR/Discourse
File: IPGov_Chatbot/tests/test_m3_adaptive_nlu_cqr.py

Authoritative Specifications Grounded in:
- ORIGINAL_REQUEST.md (Section 2026-10-26T17:15:32Z: §R1, §R3; Section 2026-10-25T09:52:26Z: §R1, §R2; Section 2026-10-24T20:01:42Z: §R2, §R3, §R4)
- PROJECT.md (Milestone M3: Features 12, 13, 14, 15)
- TEST_INFRA.md (Tier 1-4 validation criteria)
- IPGov_Chatbot/docs/output.md (SRS-CHATBOT-QUERY-SPEC-V3: REQ-Q01 to REQ-Q05, SC-2.1, SC-2.1b, SC-2.4, SC-2.5, SC-2.6)
- Knowledge Base: IPGov_Chatbot/data/catalog/criterion_definitions_kb.json

Four Core Test Suites:
1. Suite A: Dạng 1 — SINGLE_CRITERION Resolution & Temporal Filtering
2. Suite B: Dạng 2 — PARENT_CHILDREN_BREAKDOWN Resolution & Canonical Ordering
3. Suite C: Dạng 3 — CROSS_BRANCH_COMPARISON Multi-Branch Resolution & Clean Output
4. Suite D: Multi-Turn Conversation, Self-Contained Query Preservation & CQR Guardrails
"""

import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog
from IPGov_Chatbot.modules.mod03_router.discourse_state_tracker import DiscourseStateTracker, DialogueStateFrame
from IPGov_Chatbot.modules.mod03_router.neural_cqr_engine import NeuralCQREngine, CQRReformulationResult
from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import warehouse_agent


@pytest.fixture(scope="module")
def catalog():
    return DuckDBSemanticCatalog()


@pytest.fixture(scope="module")
def discourse_tracker():
    return DiscourseStateTracker()


@pytest.fixture(scope="module")
def cqr_engine():
    return NeuralCQREngine()


# ==============================================================================
# SUITE A: DẠNG 1 — SINGLE_CRITERION RESOLUTION & TEMPORAL FILTERING
# ==============================================================================
class TestM3SingleCriterion:
    """
    Requirements:
    - R3 §1 (Dạng 1): Accurate resolution to single target metric or branch-scoped leaf.
    - SC-2.1b: Direct resolution for branch-scoped leaves (e.g. LHHTX chăn nuôi), bypassing 4-branch comparison.
    - SC-2.6 / R4: Disambiguation between cumulative, annual, and star-leaf criteria.
    - Temporal filtering: nearest milestone matching (e.g. 30/4 -> 31/03/2026 with delta note).
    """

    def test_single_criterion_leaf_latest(self, catalog):
        """Standard single leaf criterion with latest value."""
        query = "Cho tôi biết tổng hộ sản xuất muối năm 2026 là bao nhiêu?"
        cands, is_ambig, delta = catalog.find_top_k_candidates(query, top_k=5)
        assert len(cands) > 0
        top1 = cands[0]
        assert "tổng hộ sản xuất muối" in top1["name"].lower()
        assert top1["is_leaf"] is True

    @pytest.mark.parametrize("query,expected_keyword,forbidden_keywords", [
        (
            "bạn hãy cho tôi biết lũy kế tổng số lượng chủ thể sản phẩm theo dữ liệu mới nhất",
            "lũy kế",
            ["5 sao", "trong năm"]
        ),
        (
            "bạn hãy cho tôi biết lũy kế tổng số lượng chủ thể sản phẩm OCOP theo dữ liệu mới nhất",
            "lũy kế",
            ["5 sao", "trong năm"]
        ),
        (
            "tổng số lượng sản phẩm OCOP trong năm",
            "trong năm",
            ["lũy kế", "5 sao"]
        ),
        (
            "tổng số lượng chủ thể sản phẩm OCOP trong năm",
            "trong năm",
            ["lũy kế", "5 sao"]
        ),
    ])
    def test_single_criterion_cumulative_vs_annual_disambiguation(self, catalog, query, expected_keyword, forbidden_keywords):
        """SC-2.6 & R4: Verify cumulative vs annual disambiguation without token overlap traps."""
        cands, is_ambig, delta = catalog.find_top_k_candidates(query, top_k=5)
        assert len(cands) > 0, f"No candidates returned for '{query}'"
        top1 = cands[0]
        top1_name = top1["name"].lower()

        assert expected_keyword in top1_name, (
            f"Query '{query}' expected '{expected_keyword}' in top candidate '{top1['name']}'"
        )
        for fkw in forbidden_keywords:
            assert fkw not in top1_name, (
                f"Query '{query}' contained forbidden keyword '{fkw}' in top candidate '{top1['name']}'"
            )

    def test_branch_scoped_single_criterion_sc21b(self, catalog):
        """
        SC-2.1b & R2.5: 'cho tôi biết số liệu chăn nuôi của liên hiệp hợp tác xã ngày 30/4'
        Must resolve to LHHTX Chăn nuôi (code: chan_nuoi under LHHTX), NOT multi-branch comparison.
        """
        query = "cho tôi biết số liệu chăn nuôi của liên hiệp hợp tác xã ngày 30/4"
        cands, is_ambig, delta = catalog.find_top_k_candidates(query, top_k=5)
        assert len(cands) > 0

        # Must match Chăn nuôi under LHHTX
        top1 = cands[0]
        top1_name = top1["name"].lower()
        assert "chăn nuôi" in top1_name
        parent_name = (top1.get("parent_name") or "").lower()
        root_name = (top1.get("root_name") or "").lower()
        assert any(k in parent_name or k in root_name for k in ["lhhtx", "liên hiệp htx", "liên hiệp hợp tác xã"]), (
            f"Expected LHHTX parent, got parent='{top1.get('parent_name')}', root='{top1.get('root_name')}'"
        )

    def test_single_criterion_agent_e2e_response_format(self):
        """Verify warehouse agent output adheres to Senior-Friendly 5-Field Standard Card."""
        res = warehouse_agent.run(query="Cho tôi biết tổng hộ sản xuất muối năm 2026 là bao nhiêu?")
        ans = res.get("final_answer", "")

        # Must have 5 standard fields
        assert "Chỉ tiêu" in ans
        assert "Giá trị" in ans
        assert "Đơn vị thực hiện" in ans
        assert "Nhiệm vụ trọng tâm" in ans
        assert "Thời điểm báo cáo" in ans

        # Must contain approved value (0 at 31/07/2026 or 660 at 30/06/2026)
        assert ("0" in ans or "660" in ans)

        # Must NOT contain forbidden English or dev labels
        assert "Ticket thời gian:" not in ans
        assert "THINKING" not in ans


# ==============================================================================
# SUITE B: DẠNG 2 — PARENT_CHILDREN_BREAKDOWN & CANONICAL ORDERING
# ==============================================================================
class TestM3ParentChildrenBreakdown:
    """
    Requirements:
    - R3 §1 (Dạng 2): Dynamic breakdown of child criteria under a parent concept.
    - R2.1 / SC-2.5: Strict canonical warehouse ordering (ORDER BY created_date ASC / canonical_order ASC).
    - Returns exact count in natural language lead sentence, bold names, and 6-column detail table.
    - Zero hardcoded regex or static trigger keywords.
    """

    def test_htx_fields_breakdown_count_and_canonical_order(self, catalog):
        """
        'bạn hãy cho tôi biết số lĩnh vực của HTX'
        Must return exactly 8 fields in canonical order:
        Trồng trọt -> Chăn nuôi -> Lâm nghiệp -> Thủy sản -> Diêm nghiệp -> Chế biến nông sản -> Nước sạch NT -> Tổng hợp
        """
        expected_fields = [
            "Trồng trọt",
            "Chăn nuôi",
            "Lâm nghiệp",
            "Thủy sản",
            "Diêm nghiệp",
            "Chế biến nông sản",
            "Nước sạch NT",
            "Tổng hợp",
        ]
        breakdown = catalog.resolve_hierarchy_breakdown("bạn hãy cho tôi biết số lĩnh vực của HTX")
        assert breakdown is not None, "Failed to resolve HTX fields hierarchy breakdown"

        children = breakdown.get("children", [])
        assert len(children) == 8, f"Expected 8 child fields, got {len(children)}"

        child_names = [c["name"] for c in children]
        assert child_names == expected_fields, (
            f"Canonical warehouse order violated!\nExpected: {expected_fields}\nGot: {child_names}"
        )

    def test_htx_evaluation_levels_breakdown_canonical_order(self, catalog):
        """
        'Bạn hãy cho tôi biết các mức đánh giá hiệu quả hoạt động của hợp tác xã'
        Must return exactly 4 levels in canonical order:
        Số HTX nông nghiệp hoạt động hiệu quả tốt -> Số HTX nông nghiệp hoạt động hiệu quả trung bình ->
        Số HTX nông nghiệp hoạt động kém hiệu quả -> Chưa đủ điều kiện đánh giá
        """
        expected_levels = [
            "Số HTX nông nghiệp hoạt động hiệu quả tốt",
            "Số HTX nông nghiệp hoạt động hiệu quả trung bình",
            "Số HTX nông nghiệp hoạt động kém hiệu quả",
            "Chưa đủ điều kiện đánh giá",
        ]
        breakdown = catalog.resolve_hierarchy_breakdown("Bạn hãy cho tôi biết các mức đánh giá hiệu quả hoạt động của hợp tác xã")
        assert breakdown is not None, "Failed to resolve HTX evaluation levels breakdown"

        children = breakdown.get("children", [])
        assert len(children) == 4, f"Expected 4 evaluation levels, got {len(children)}"

        child_names = [c["name"] for c in children]
        assert child_names == expected_levels, (
            f"Canonical evaluation levels order violated!\nExpected: {expected_levels}\nGot: {child_names}"
        )

    def test_salt_area_types_breakdown(self, catalog):
        """
        'Cho tôi biết đang có các loại diện tích sản xuất muối gì?'
        Must return 2 types: Diện tích muối sản xuất thủ công, Diện tích muối sản xuất công nghiệp.
        """
        expected_types = [
            "Diện tích muối sản xuất thủ công",
            "Diện tích muối sản xuất công nghiệp",
        ]
        breakdown = catalog.resolve_hierarchy_breakdown("Cho tôi biết đang có các loại diện tích sản xuất muối gì?")
        assert breakdown is not None, "Failed to resolve salt area types breakdown"

        children = breakdown.get("children", [])
        assert len(children) == 2, f"Expected 2 salt area types, got {len(children)}"
        child_names = [c["name"] for c in children]
        assert child_names == expected_types

    def test_breakdown_temporal_filter_support(self):
        """
        R2.3: 'số lượng lĩnh vực của HTX nông nghiệp trong quý 1'
        Must return 8-field breakdown filtered to Quý 1 (2026-03-31).
        """
        res = warehouse_agent.run(query="số lượng lĩnh vực của HTX nông nghiệp trong quý 1")
        ans = res.get("final_answer", "")
        tab = res.get("tabular_data")

        # Must mention 8 fields or render table with 8 rows
        assert "8" in ans or (tab and len(tab.get("rows", [])) == 8)
        assert "Trồng trọt" in ans or (tab and any("Trồng trọt" in str(r) for r in tab.get("rows", [])))


# ==============================================================================
# SUITE C: DẠNG 3 — CROSS_BRANCH_COMPARISON & CLEAN OUTPUT
# ==============================================================================
class TestM3CrossBranchComparison:
    """
    Requirements:
    - R3 §1 (Dạng 3): Compare leaf criteria spanning multiple parent branches (SC-2.1).
    - R1.5: Clean output removing redundant post-table repeated text and trailing notes.
    """

    def test_cross_branch_crop_production(self, catalog):
        """
        'Chỉ tiêu trồng trọt hiện đạt bao nhiêu?'
        Trồng trọt exists across 4 branches: HTX, LHHTX, THT, Trang trại.
        """
        query = "Chỉ tiêu trồng trọt hiện đạt bao nhiêu?"
        cands, is_ambig, delta = catalog.find_top_k_candidates(query, top_k=10)
        crop_cands = [c for c in cands if c["name"] == "Trồng trọt"]
        assert len(crop_cands) >= 3, f"Expected >= 3 branches for Trồng trọt, found {len(crop_cands)}"

    def test_cross_branch_clean_output_no_redundant_text(self):
        """
        R1.5: In multi-branch single-metric comparison (SC-2.1), eliminate redundant text
        repeating each row after table and trailing 'Lưu ý mốc thời gian:' paragraph.
        """
        res = warehouse_agent.run(query="Chỉ tiêu trồng trọt hiện đạt bao nhiêu?")
        ans = res.get("final_answer", "")

        # Redundant post-table repeating patterns that must NOT be present
        assert "Lưu ý mốc thời gian:" not in ans
        # Should not have multiple trailing paragraphs repeating each row after the markdown table


# ==============================================================================
# SUITE D: MULTI-TURN CONVERSATION, SELF-CONTAINED QUERY PRESERVATION & CQR
# ==============================================================================
class TestM3MultiTurnCQRAndDiscourse:
    """
    Requirements:
    - R3 §2: DiscourseStateTracker & NeuralCQREngine must NOT distort self-contained queries.
    - Prevention of intent overwrite: Do not convert PARENT_CHILDREN_BREAKDOWN into scalar inquiry.
    - user_query preservation: Original prompt text is never overwritten in AgentState.
    - Continuity across turns: Turn 1 -> Turn 2 breakdown consistency.
    """

    @pytest.mark.parametrize("query", [
        "cho tôi biết số lĩnh vực của HTX nông nghiệp",
        "cho tôi biết số lượng lĩnh vực của hợp tác xã nông nghiệp",
        "Bạn hãy cho tôi biết các mức đánh giá hiệu quả hoạt động của hợp tác xã",
        "Cho tôi biết đang có các loại diện tích sản xuất muối gì?",
        "Cho tôi biết tổng hộ sản xuất muối năm 2026 là bao nhiêu?",
    ])
    def test_self_contained_query_detection(self, discourse_tracker, query):
        """
        Verify that self-contained queries are correctly identified as autonomous,
        requiring NO context distortion.
        """
        # If method exists, verify directly; otherwise verify process_turn does not force level 1 pivot
        session_id = "test_self_contained_session"
        frame, resolution, hint = discourse_tracker.process_turn(
            session_id=session_id,
            turn_index=1,
            query=query,
        )
        assert resolution in ["NEW_TOPIC", "SELF_CONTAINED"], (
            f"Expected autonomous resolution for '{query}', got {resolution}"
        )

    def test_self_contained_query_preservation_across_turns(self, cqr_engine, discourse_tracker):
        """
        Critical Multi-Turn Test:
        Turn 1: 'cho tôi biết số lĩnh vực của HTX nông nghiệp'
        Turn 2: 'cho tôi biết số lượng lĩnh vực của hợp tác xã nông nghiệp'
        CQR must NOT rewrite Turn 2 into a scalar question or inject conflicting keywords.
        """
        session_id = "test_multi_turn_cqr_preservation"

        # Turn 1
        frame1, res1, hint1 = discourse_tracker.process_turn(
            session_id=session_id,
            turn_index=1,
            query="cho tôi biết số lĩnh vực của HTX nông nghiệp",
        )

        # Turn 2: Self-contained paraphrased breakdown query
        query_t2 = "cho tôi biết số lượng lĩnh vực của hợp tác xã nông nghiệp"
        cqr_result: CQRReformulationResult = cqr_engine.reformulate(
            query=query_t2,
            context_frame=frame1,
            standalone_hint=None,
        )

        # Invariance assertions
        # 1. Must NOT inject scalar keywords that destroy breakdown intent
        standalone = cqr_result.standalone_query.lower()
        for bad_kw in ["giá trị là bao nhiêu", "kết quả là", "chỉ tiêu đơn"]:
            assert bad_kw not in standalone, (
                f"CQR distorted breakdown query with scalar keyword '{bad_kw}': '{cqr_result.standalone_query}'"
            )

        # 2. Must preserve the core breakdown entity and aspect
        assert any(k in standalone for k in ["lĩnh vực", "ngành"])
        assert any(k in standalone for k in ["htx", "hợp tác xã"])

    def test_user_query_preserved_in_agent_state(self):
        """
        R3 §2: Invariance Rule: state['user_query'] must preserve the original verbatim user prompt,
        never overwritten by internal rewritten query strings.
        """
        original_prompt = "cho tôi biết số lượng lĩnh vực của hợp tác xã nông nghiệp"
        res = warehouse_agent.run(query=original_prompt, session_id="test_user_query_preservation")

        assert "user_query" in res, "AgentState response missing 'user_query'"
        assert res["user_query"] == original_prompt, (
            f"user_query was overwritten! Expected '{original_prompt}', got '{res['user_query']}'"
        )

    def test_multi_turn_e2e_breakdown_stability(self):
        """
        End-to-End Multi-Turn Session Stability:
        Turn 1: 'cho tôi biết số lĩnh vực của HTX nông nghiệp' -> 8 fields
        Turn 2: 'cho tôi biết số lượng lĩnh vực của hợp tác xã nông nghiệp' -> 8 fields
        Both turns must successfully return the 8 canonical fields.
        """
        session_id = "test_session_e2e_breakdown_stability"

        res1 = warehouse_agent.run(
            query="cho tôi biết số lĩnh vực của HTX nông nghiệp",
            session_id=session_id
        )
        ans1 = res1.get("final_answer", "")
        assert "8" in ans1 or (res1.get("tabular_data") and len(res1["tabular_data"].get("rows", [])) == 8)

        res2 = warehouse_agent.run(
            query="cho tôi biết số lượng lĩnh vực của hợp tác xã nông nghiệp",
            session_id=session_id
        )
        ans2 = res2.get("final_answer", "")
        assert "8" in ans2 or (res2.get("tabular_data") and len(res2["tabular_data"].get("rows", [])) == 8)
