# -*- coding: utf-8 -*-
"""
Empirical Adversarial Stress Test Suite for Milestone M3
File: IPGov_Chatbot/tests/test_challenger_m3_adversarial_stress.py

Adversarial Stress Verification Tasks:
1. Multi-turn conversations (Turn 1 -> Turn 2 -> Turn 3):
   Verify self-contained queries at Turn 3 do NOT get rewritten into scalar questions,
   preserve breakdown intent, do not leak previous turn entities, and maintain user_query immutability.
2. Cumulative vs Annual disambiguation on OCOP & other entities under diverse phrasing and noise.
3. Exclusive metric concept guarding (hộ vs sản lượng vs diện tích):
   Ensure single leaf queries are never hijacked by parent breakdown while legitimate breakdowns remain accessible.
"""

import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog
from IPGov_Chatbot.modules.mod03_router.discourse_state_tracker import (
    DiscourseStateTracker,
    DialogueStateFrame,
    is_self_contained_query,
)
from IPGov_Chatbot.modules.mod03_router.neural_cqr_engine import (
    NeuralCQREngine,
    CQRReformulationResult,
)
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
# SECTION 1: Adversarial Multi-Turn Stress (Turn 1 -> Turn 2 -> Turn 3)
# ==============================================================================
class TestAdversarialMultiTurnDiscourse:
    """
    Stress-test multi-turn conversation flow across 3 consecutive turns.
    Verify:
    1. Turn 1 (Breakdown or Single) sets dialogue frame.
    2. Turn 2 (Dependent or Pivot) correctly uses previous frame.
    3. Turn 3 (Self-contained) MUST NOT be distorted by CQR:
       - No scalar marker injection ("là bao nhiêu", "kết quả là", "chỉ tiêu đơn")
       - Preserves breakdown intent ("lĩnh vực", "mức đánh giá", "loại diện tích")
       - Isolates Turn 3 from Turn 1/2 entities (no topic leakage)
       - AgentState['user_query'] remains verbatim prompt.
    """

    def test_3turn_sequence_breakdown_to_dependent_to_breakdown(self, discourse_tracker, cqr_engine):
        """
        Sequence A:
        Turn 1: 'Bạn hãy cho tôi biết các mức đánh giá hiệu quả hoạt động của hợp tác xã' (Breakdown)
        Turn 2: 'thế còn về liên kết sản xuất thì sao?' (Dependent query)
        Turn 3: 'Cho tôi biết đang có các loại diện tích sản xuất muối gì?' (Self-contained breakdown on distinct entity)
        """
        session_id = "stress_3turn_seq_a"

        # Turn 1: Breakdown
        frame1, res1, hint1 = discourse_tracker.process_turn(
            session_id=session_id,
            turn_index=1,
            query="Bạn hãy cho tôi biết các mức đánh giá hiệu quả hoạt động của hợp tác xã",
        )
        assert res1 in ["NEW_TOPIC", "SELF_CONTAINED"]
        assert frame1.topic_entity is not None

        # Turn 2: Dependent query
        q2 = "thế còn về liên kết sản xuất thì sao?"
        assert not is_self_contained_query(q2, current_turn=2)
        frame2, res2, hint2 = discourse_tracker.process_turn(
            session_id=session_id,
            turn_index=2,
            query=q2,
        )
        cqr2 = cqr_engine.reformulate(query=q2, context_frame=frame1, standalone_hint=hint2)
        assert cqr2.is_dependent is True
        assert "hợp tác xã" in cqr2.standalone_query.lower() or "htx" in cqr2.standalone_query.lower()

        # Turn 3: Self-contained query on Salt Area breakdown
        q3 = "Cho tôi biết đang có các loại diện tích sản xuất muối gì?"
        assert is_self_contained_query(q3, current_turn=3) is True

        cqr3 = cqr_engine.reformulate(query=q3, context_frame=frame2, standalone_hint=None)
        assert cqr3.is_dependent is False, f"Turn 3 should be marked independent, got is_dependent={cqr3.is_dependent}"
        
        standalone3 = cqr3.standalone_query.lower()
        # Must NOT inject scalar markers
        for bad_kw in ["giá trị là bao nhiêu", "kết quả là", "chỉ tiêu đơn", "là bao nhiêu?"]:
            assert bad_kw not in standalone3, f"Scalar marker '{bad_kw}' leaked into Turn 3 standalone query: '{standalone3}'"

        # Must NOT leak Turn 1 or Turn 2 entities (htx, liên kết sản xuất) into salt query
        assert "hợp tác xã" not in standalone3 and "htx" not in standalone3, (
            f"Topic leakage: HTX entity leaked into Turn 3 query: '{cqr3.standalone_query}'"
        )
        assert "liên kết" not in standalone3, (
            f"Topic leakage: liên kết leaked into Turn 3 query: '{cqr3.standalone_query}'"
        )

        # Must preserve salt area breakdown aspect
        assert "muối" in standalone3
        assert "diện tích" in standalone3

    def test_3turn_sequence_single_leaf_to_pivot_to_breakdown(self, discourse_tracker, cqr_engine):
        """
        Sequence B:
        Turn 1: 'Cho tôi biết tổng hộ sản xuất muối năm 2026 là bao nhiêu?' (Single leaf)
        Turn 2: 'vậy còn diện tích sản xuất muối thì sao?' (Dependent pivot)
        Turn 3: 'cho tôi biết số lĩnh vực của HTX nông nghiệp' (Self-contained breakdown)
        """
        session_id = "stress_3turn_seq_b"

        # Turn 1
        frame1, res1, _ = discourse_tracker.process_turn(
            session_id=session_id,
            turn_index=1,
            query="Cho tôi biết tổng hộ sản xuất muối năm 2026 là bao nhiêu?",
        )

        # Turn 2: Dependent
        q2 = "vậy còn diện tích sản xuất muối thì sao?"
        assert not is_self_contained_query(q2, current_turn=2)
        frame2, res2, hint2 = discourse_tracker.process_turn(
            session_id=session_id,
            turn_index=2,
            query=q2,
        )
        cqr2 = cqr_engine.reformulate(query=q2, context_frame=frame1, standalone_hint=hint2)
        assert cqr2.is_dependent is True

        # Turn 3: Self-contained HTX fields breakdown
        q3 = "cho tôi biết số lĩnh vực của HTX nông nghiệp"
        assert is_self_contained_query(q3, current_turn=3) is True

        cqr3 = cqr_engine.reformulate(query=q3, context_frame=frame2, standalone_hint=None)
        assert cqr3.is_dependent is False
        standalone3 = cqr3.standalone_query.lower()

        # Must NOT contain scalar questions or salt leakage
        assert "muối" not in standalone3
        assert "là bao nhiêu" not in standalone3
        assert any(k in standalone3 for k in ["lĩnh vực", "ngành"])
        assert any(k in standalone3 for k in ["htx", "hợp tác xã"])

    def test_3turn_agent_e2e_execution(self):
        """
        End-to-End warehouse agent execution across 3 turns in a single session.
        Turn 1: HTX evaluation levels (Breakdown -> 4 levels)
        Turn 2: Branch-scoped leaf LHHTX Chăn nuôi (Single metric SC-2.1b)
        Turn 3: HTX fields breakdown (Breakdown -> 8 fields)
        """
        session_id = "stress_3turn_e2e_session"

        # Turn 1
        res1 = warehouse_agent.run(
            query="Bạn hãy cho tôi biết các mức đánh giá hiệu quả hoạt động của hợp tác xã",
            session_id=session_id,
        )
        ans1 = res1.get("final_answer", "")
        assert res1["user_query"] == "Bạn hãy cho tôi biết các mức đánh giá hiệu quả hoạt động của hợp tác xã"
        assert "4" in ans1 or (res1.get("tabular_data") and len(res1["tabular_data"].get("rows", [])) == 4)

        # Turn 2
        res2 = warehouse_agent.run(
            query="cho tôi biết số liệu chăn nuôi của liên hiệp hợp tác xã ngày 30/4",
            session_id=session_id,
        )
        ans2 = res2.get("final_answer", "")
        assert res2["user_query"] == "cho tôi biết số liệu chăn nuôi của liên hiệp hợp tác xã ngày 30/4"
        assert "Chỉ tiêu" in ans2
        assert "Giá trị" in ans2

        # Turn 3: Self-contained breakdown
        res3 = warehouse_agent.run(
            query="cho tôi biết số lĩnh vực của HTX nông nghiệp",
            session_id=session_id,
        )
        ans3 = res3.get("final_answer", "")
        assert res3["user_query"] == "cho tôi biết số lĩnh vực của HTX nông nghiệp"
        assert "8" in ans3 or (res3.get("tabular_data") and len(res3["tabular_data"].get("rows", [])) == 8)
        assert "Trồng trọt" in ans3 or (res3.get("tabular_data") and any("Trồng trọt" in str(r) for r in res3["tabular_data"].get("rows", [])))


# ==============================================================================
# SECTION 2: Adversarial Cumulative vs. Annual Disambiguation on OCOP & Others
# ==============================================================================
class TestAdversarialCumulativeVsAnnual:
    """
    Stress-test candidate ranking between cumulative (lũy kế / đến thời điểm báo cáo)
    and annual (trong năm) across linguistic perturbations and star ratings.
    """

    @pytest.mark.parametrize("query,expected_substring,forbidden_substring", [
        (
            "bạn hãy cho tôi biết lũy kế tổng số lượng chủ thể sản phẩm theo dữ liệu mới nhất",
            "lũy kế",
            "trong năm",
        ),
        (
            "bạn hãy cho tôi biết lũy kế tổng số lượng chủ thể sản phẩm OCOP theo dữ liệu mới nhất",
            "lũy kế",
            "trong năm",
        ),
        (
            "cho tôi biết số lượng lũy kế đến thời điểm báo cáo của chủ thể sản phẩm OCOP",
            "lũy kế",
            "trong năm",
        ),
        (
            "tổng số lượng sản phẩm OCOP trong năm 2026",
            "trong năm",
            "lũy kế",
        ),
        (
            "tổng số lượng chủ thể sản phẩm OCOP trong năm",
            "trong năm",
            "lũy kế",
        ),
        (
            "số lượng sản phẩm OCOP phát sinh mới trong năm",
            "trong năm",
            "lũy kế",
        ),
    ])
    def test_cumulative_vs_annual_ranking(self, catalog, query, expected_substring, forbidden_substring):
        """Top candidate must match the temporal polarity of the query."""
        cands, _, _ = catalog.find_top_k_candidates(query, top_k=5)
        assert len(cands) > 0, f"No candidates found for: {query}"
        top1 = cands[0]
        top1_name = top1["name"].lower()

        assert expected_substring in top1_name, (
            f"Query '{query}' expected '{expected_substring}' in candidate '{top1['name']}'"
        )
        assert forbidden_substring not in top1_name, (
            f"Query '{query}' forbidden '{forbidden_substring}' found in candidate '{top1['name']}'"
        )

    def test_star_rating_not_hijacking_general_cumulative(self, catalog):
        """General cumulative query must NOT select a single star rating (3 sao, 4 sao, 5 sao)."""
        query = "bạn hãy cho tôi biết lũy kế tổng số lượng chủ thể sản phẩm OCOP theo dữ liệu mới nhất"
        cands, _, _ = catalog.find_top_k_candidates(query, top_k=5)
        top1 = cands[0]
        top1_name = top1["name"].lower()
        for star in ["3 sao", "4 sao", "5 sao"]:
            assert star not in top1_name, f"General query matched leaf star criterion: '{top1['name']}'"

    def test_star_rating_respected_when_explicitly_asked(self, catalog):
        """When user explicitly asks for 5-star OCOP, star penalty must not block it."""
        query = "số lượng chủ thể sản phẩm OCOP 5 sao"
        cands, _, _ = catalog.find_top_k_candidates(query, top_k=5)
        assert len(cands) > 0
        top1 = cands[0]
        assert "5 sao" in top1["name"].lower()


# ==============================================================================
# SECTION 3: Exclusive Metric Concept Guarding (Hộ vs Sản lượng vs Diện tích)
# ==============================================================================
class TestExclusiveMetricConceptGuarding:
    """
    Stress-test exclusive metric guard in resolve_hierarchy_breakdown():
    - Exclusive concept groups: {'hộ', 'hộ sản xuất'}, {'sản lượng', 'thu hoạch'}, {'diện tích', 'làm muối'}.
    - Single leaf queries must return None from resolve_hierarchy_breakdown (not hijacked by parent groups).
    - Legitimate breakdown queries must resolve to their correct parent group.
    """

    @pytest.mark.parametrize("leaf_query", [
        "Cho tôi biết tổng hộ sản xuất muối năm 2026 là bao nhiêu?",
        "tổng số hộ làm muối trên địa bàn tỉnh",
        "hộ sản xuất muối hiện nay có bao nhiêu hộ?",
        "diện tích làm muối của bà con là bao nhiêu?",
    ])
    def test_single_leaf_not_hijacked_by_yield_breakdown(self, catalog, leaf_query):
        """
        Queries asking about 'hộ' or 'diện tích' as a single scalar metric must NEVER
        be resolved as 'Tổng sản lượng muối edit 1' in hierarchy breakdown.
        """
        breakdown = catalog.resolve_hierarchy_breakdown(leaf_query)
        if breakdown is not None:
            parent_name = breakdown.get("parent_name", "").lower()
            root_name = breakdown.get("root_name", "").lower()
            # Must NOT resolve to salt yield breakdown
            assert "sản lượng" not in parent_name and "sản lượng" not in root_name, (
                f"Query '{leaf_query}' was hijacked by yield breakdown: parent='{parent_name}', root='{root_name}'"
            )

    @pytest.mark.parametrize("breakdown_query,expected_token,expected_count", [
        ("Cho tôi biết đang có các loại diện tích sản xuất muối gì?", "diện tích", 2),
        ("phân loại các loại diện tích sản xuất muối", "diện tích", 2),
        ("Sản lượng muối gồm những loại nào?", "sản lượng", 2),
        ("các loại sản lượng muối thu hoạch", "sản lượng", 2),
    ])
    def test_legitimate_breakdowns_not_blocked(self, catalog, breakdown_query, expected_token, expected_count):
        """
        Legitimate breakdown queries must still resolve successfully to their corresponding parent group.
        """
        breakdown = catalog.resolve_hierarchy_breakdown(breakdown_query)
        assert breakdown is not None, f"Breakdown unexpectedly returned None for '{breakdown_query}'"

        parent_name = breakdown.get("parent_name", "").lower()
        root_name = breakdown.get("root_name", "").lower()
        children = breakdown.get("children", [])

        assert expected_token in parent_name or expected_token in root_name
        assert len(children) == expected_count, (
            f"Expected {expected_count} children for '{breakdown_query}', got {len(children)}"
        )
