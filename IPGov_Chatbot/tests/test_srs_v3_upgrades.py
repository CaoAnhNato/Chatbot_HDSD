# -*- coding: utf-8 -*-
"""
Unit & Integration Tests for SRS V3 Architectural & UX Upgrades (PA 1.1, PA 2.1, PA 3.1, PA 4.1).
Covers:
  - PA 4.1: Neuro-Symbolic Calendar Contract (`TemporalSlotSpec.to_calendar_bounds`)
  - PA 1.1: Dual-Bound Snapshot (`resolve_nearest_report_date_with_bounds`, SQL window bounds, SC-2.2 shift notice)
  - PA 3.1: Context-Bound Action Chips (`label` vs `query_text`, recursive leaf harvesting for OCOP, `inherited_parent_criterion` Turn 1 -> Turn 2 disambiguation)
  - PA 2.1: Temporal-Safe Tree Hydration (`build_criteria_tree_for_rows(..., has_temporal_filter=True)`)
"""

import pytest
from IPGov_Chatbot.schemas.canonical_query_frame import TemporalSlotSpec
from IPGov_Chatbot.modules.mod03_router.canonical_normalizer import (
    resolve_nearest_report_date_with_bounds,
    CanonicalSemanticNormalizer,
)
from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog
from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import warehouse_agent


# ==============================================================================
# 1. PA 4.1: NEURO-SYMBOLIC CALENDAR CONTRACT (`TemporalSlotSpec`)
# ==============================================================================
class TestPA41NeuroSymbolicCalendarContract:
    def test_leap_year_vs_non_leap_year_february(self):
        # 2024 is a leap year -> Feb span has 29 days
        spec_2024 = TemporalSlotSpec(granularity="MONTH_SPAN", year=2024, start_month=2, end_month=2)
        b24 = spec_2024.to_calendar_bounds()
        assert b24["date_from"] == "2024-02-01"
        assert b24["date_to"] == "2024-02-29"
        assert b24["specific_date"] is None

        # 2026 is a non-leap year -> Feb span has 28 days
        spec_2026 = TemporalSlotSpec(granularity="MONTH_SPAN", year=2026, start_month=2, end_month=2)
        b26 = spec_2026.to_calendar_bounds()
        assert b26["date_from"] == "2026-02-01"
        assert b26["date_to"] == "2026-02-28"
        assert b26["specific_date"] is None

        # Exact date clamping on non-leap year Feb 29 -> 2026-02-28
        spec_exact = TemporalSlotSpec(granularity="EXACT_DATE", year=2026, month=2, day=29)
        assert spec_exact.to_calendar_bounds()["specific_date"] == "2026-02-28"

    def test_quarters_and_half_years_deterministic_bounds(self):
        # Q1 -> Jan 1 to Mar 31
        q1 = TemporalSlotSpec(granularity="QUARTER", year=2026, quarter=1).to_calendar_bounds()
        assert (q1["date_from"], q1["date_to"]) == ("2026-01-01", "2026-03-31")

        # Q2 -> Apr 1 to Jun 30
        q2 = TemporalSlotSpec(granularity="QUARTER", year=2026, quarter=2).to_calendar_bounds()
        assert (q2["date_from"], q2["date_to"]) == ("2026-04-01", "2026-06-30")

        # Q3 -> Jul 1 to Sep 30
        q3 = TemporalSlotSpec(granularity="QUARTER", year=2026, quarter=3).to_calendar_bounds()
        assert (q3["date_from"], q3["date_to"]) == ("2026-07-01", "2026-09-30")

        # Q4 -> Oct 1 to Dec 31
        q4 = TemporalSlotSpec(granularity="QUARTER", year=2026, quarter=4).to_calendar_bounds()
        assert (q4["date_from"], q4["date_to"]) == ("2026-10-01", "2026-12-31")

        # H1 & H2
        h1 = TemporalSlotSpec(granularity="HALF_YEAR", year=2026, half=1).to_calendar_bounds()
        assert (h1["date_from"], h1["date_to"]) == ("2026-01-01", "2026-06-30")
        h2 = TemporalSlotSpec(granularity="HALF_YEAR", year=2026, half=2).to_calendar_bounds()
        assert (h2["date_from"], h2["date_to"]) == ("2026-07-01", "2026-12-31")

    def test_ytd_and_month_range_bounds(self):
        # YTD 2026 -> Jan 1 to Dec 31
        ytd = TemporalSlotSpec(granularity="YTD", year=2026).to_calendar_bounds()
        assert (ytd["date_from"], ytd["date_to"]) == ("2026-01-01", "2026-12-31")

        # Tu thang 4 den thang 11 nam 2026 -> Apr 1 to Nov 30
        m_range = TemporalSlotSpec(granularity="MONTH_SPAN", year=2026, start_month=4, end_month=11).to_calendar_bounds()
        assert (m_range["date_from"], m_range["date_to"]) == ("2026-04-01", "2026-11-30")


# ==============================================================================
# 2. PA 1.1: DUAL-BOUND SNAPSHOT & TEMPORAL SHIFT NOTICE (`SC-2.2`)
# ==============================================================================
class TestPA11DualBoundSnapshot:
    def test_resolve_nearest_report_date_with_bounds_all_5_cases(self):
        dates = ["2026-03-31", "2026-06-30", "2026-09-30", "2026-12-31"]

        # Case 1: Exact match
        c1 = resolve_nearest_report_date_with_bounds(dates, "2026-06-30")
        assert c1["selected_date"] == "2026-06-30"
        assert c1["is_exact_match"] is True
        assert c1["delta_days"] == 0

        # Case 2: Closer to lower bound (2026-07-05 -> 5 days from 06-30 vs 87 days to 09-30)
        c2 = resolve_nearest_report_date_with_bounds(dates, "2026-07-05")
        assert c2["selected_date"] == "2026-06-30"
        assert c2["is_exact_match"] is False
        assert c2["bound_a_date"] == "2026-06-30"
        assert c2["bound_b_date"] == "2026-09-30"
        assert c2["delta_days"] == 5

        # Case 3: Closer to upper bound (2026-09-20 -> 10 days to 09-30 vs 82 days from 06-30)
        c3 = resolve_nearest_report_date_with_bounds(dates, "2026-09-20")
        assert c3["selected_date"] == "2026-09-30"
        assert c3["is_exact_match"] is False
        assert c3["bound_a_date"] == "2026-06-30"
        assert c3["bound_b_date"] == "2026-09-30"
        assert c3["delta_days"] == 10

        # Case 4: Equidistant tie-breaker favors upper bound B
        tie_dates = ["2026-06-10", "2026-06-20"]
        c4 = resolve_nearest_report_date_with_bounds(tie_dates, "2026-06-15")
        assert c4["selected_date"] == "2026-06-20"
        assert c4["bound_a_date"] == "2026-06-10"
        assert c4["bound_b_date"] == "2026-06-20"
        assert c4["delta_days"] == 5

        # Case 5: Out of outer bounds (before earliest or after latest)
        c5_before = resolve_nearest_report_date_with_bounds(dates, "2026-01-15")
        assert c5_before["selected_date"] == "2026-03-31"
        assert c5_before["bound_a_date"] is None
        assert c5_before["bound_b_date"] == "2026-03-31"

        c5_after = resolve_nearest_report_date_with_bounds(dates, "2026-12-31")
        assert c5_after["selected_date"] == "2026-12-31"
        assert c5_after["is_exact_match"] is True

    def test_sql_compiler_includes_dual_bound_window_columns(self):
        norm = CanonicalSemanticNormalizer()
        q = "Số liệu chỉ tiêu doanh thu hợp tác xã ngày 20/03/2026 là bao nhiêu?"
        frame = norm.normalize_query(q)
        assert frame.specific_date == "2026-03-20"
        sql = norm.compile_canonical_sql(frame)
        assert "do_lech_ngay" in sql
        assert "can_duoi_ngay" in sql
        assert "can_tren_ngay" in sql

    def test_e2e_sc22_shift_notice_in_answer_text(self):
        q = "Số liệu chỉ tiêu doanh thu hợp tác xã ngày 20/3 là bao nhiêu?"
        res = warehouse_agent.run(q)
        ans = res.get("answer", "")
        assert "31/03/2026" in ans and "20/03/2026" in ans
        assert "Lưu ý mốc thời gian:" in ans


# ==============================================================================
# 3. PA 3.1: CONTEXT-BOUND ACTION CHIPS & PARENT-SLOT PERSISTENCE (`SC-2.4` <-> `SC-2.1`)
# ==============================================================================
class TestPA31ParentSlotPersistenceAndHarvesting:
    def test_sc24_recursive_leaf_harvesting_for_ocop(self):
        # "Chương trình OCOP" has Level-2 group header children with empty latest_value,
        # so PA 3.1 must harvest its Level-3 leaf descendants with values into chips
        q = "Cho tôi xem số liệu chỉ tiêu Chương trình OCOP năm 2026?"
        res = warehouse_agent.run(q)
        chips = res.get("chips") or []
        assert len(chips) >= 2
        for chip in chips:
            assert "label" in chip
            assert "query_text" in chip
            assert chip["label"].startswith("🔘 ")
            assert "thuộc Chương trình OCOP" in chip["query_text"]

    def test_multi_turn_sc24_to_sc21_disambiguation_via_inherited_parent(self):
        # Turn 1: User asks about parent criterion "HTX nông nghiệp" -> triggers SC-2.4
        q1 = "Cho tôi xem số liệu chỉ tiêu HTX nông nghiệp năm 2026?"
        res1 = warehouse_agent.run(q1)
        ans1 = res1.get("answer", "")
        assert "chỉ tiêu cha (nhóm chỉ tiêu)" in ans1.replace("**", "").lower()

        # Turn 2: User types natural follow-up for duplicate leaf "Đang hoạt động"
        # Without parent context, "Đang hoạt động" matches 4 parent groups (DUPLICATE_LEAF).
        # With Turn 1 assistant message in history, PA 3.1 must disambiguate to "HTX nông nghiệp" (code='dang_hoat_dong', value=130)!
        history = [
            {"role": "user", "content": q1},
            {"role": "assistant", "content": ans1},
        ]
        q2 = "Thế còn chỉ tiêu Đang hoạt động thì sao?"
        res2 = warehouse_agent.run(q2, history=history)
        ans2 = res2.get("answer", "")
        tbl2 = res2.get("tabular_data") or {}
        # Should resolve to SINGLE_LEAF under "HTX nông nghiệp" (value 130), NOT the 4-row multi_parent_rows table!
        assert "- **Chỉ tiêu:** Đang hoạt động" in ans2
        assert "- **Giá trị:** 130" in ans2
        assert len(tbl2.get("multi_parent_rows", [])) == 0

        # Turn 3: Normal query in the same session with non-SC-2.4 history -> must NOT crash and must reset parent context
        history_turn3 = history + [
            {"role": "user", "content": q2},
            {"role": "assistant", "content": ans2},
        ]
        q3 = "Số liệu của chỉ tiêu Tổng số hiện có là bao nhiêu?"
        res3 = warehouse_agent.run(q3, history=history_turn3)
        tbl3 = res3.get("tabular_data") or {}
        assert len(tbl3.get("multi_parent_rows", [])) == 4

    def test_multi_turn_independent_duplicate_leaf_after_parent_query_does_not_leak_context(self):
        """
        Anti-pattern regression test (Case 1):
        Turn 1: User asks about parent criterion 'Trang trại' (SC-2.4) -> triggers parent answer.
        Turn 2 (SAME session): User asks independent query 'Chỉ tiêu trồng trọt hiện đạt bao nhiêu?' (SC-2.1).
        MUST return all 4 branches in multi_parent_rows (HTX, LHHTX, THT, Trang trại),
        and MUST NOT leak 'inherited_parent_ctx = Trang trại' to restrict results to only 1 branch (value 26).
        """
        # Turn 1: Parent query
        q1 = "Cho tôi xem số liệu chỉ tiêu Trang trại năm 2026?"
        res1 = warehouse_agent.run(q1)
        ans1 = res1.get("answer", "")
        assert "chỉ tiêu cha (nhóm chỉ tiêu)" in ans1.replace("**", "").lower()

        # Turn 2: Independent duplicate leaf query in same session
        history = [
            {"role": "user", "content": q1},
            {"role": "assistant", "content": ans1},
        ]
        q2 = "Chỉ tiêu trồng trọt hiện đạt bao nhiêu?"
        res2 = warehouse_agent.run(q2, history=history)
        ans2 = res2.get("answer", "")
        tbl2 = res2.get("tabular_data") or {}

        # Must return full 4-branch comparison table, NOT 1 branch!
        multi_rows = tbl2.get("multi_parent_rows", [])
        assert len(multi_rows) == 4, (
            f"Expected 4 branches for DUPLICATE_LEAF 'Trồng trọt', but got {len(multi_rows)} rows. "
            f"Parent context 'Trang trại' was leaked into independent query! Answer: {ans2}"
        )
        assert "HTX nông nghiệp" in ans2
        assert "Liên hiệp HTX nông nghiệp" in ans2
        assert "Tổ hợp tác nông nghiệp" in ans2
        assert "Trang trại" in ans2

        # Turn 2b: Even shorter query without question words 'Chỉ tiêu trồng trọt'
        q2b = "Chỉ tiêu trồng trọt"
        res2b = warehouse_agent.run(q2b, history=history)
        tbl2b = res2b.get("tabular_data") or {}
        multi_rows_b = tbl2b.get("multi_parent_rows", [])
        assert len(multi_rows_b) == 4, (
            f"Expected 4 branches for short query 'Chỉ tiêu trồng trọt', but got {len(multi_rows_b)} rows. "
            f"Parent context leaked!"
        )

    def test_multi_turn_independent_duplicate_leaf_with_preposition_trong_does_not_leak_context(self):
        """
        Regression test: Preposition 'trong' must NOT trigger DISCOURSE_CONNECTIVE context leakage.
        Turn 1: Parent query 'Trang trại' (SC-2.4).
        Turn 2: 'Chỉ tiêu trồng trọt trong năm 2026 là bao nhiêu?'
        Must return 4 branches in multi_parent_rows, 0 leakage to 1 branch.
        """
        q1 = "Cho tôi xem số liệu chỉ tiêu Trang trại năm 2026?"
        res1 = warehouse_agent.run(q1)
        ans1 = res1.get("answer", "")
        history = [
            {"role": "user", "content": q1},
            {"role": "assistant", "content": ans1},
        ]
        q2 = "Chỉ tiêu trồng trọt trong năm 2026 là bao nhiêu?"
        res2 = warehouse_agent.run(q2, history=history)
        ans2 = res2.get("answer", "")
        tbl2 = res2.get("tabular_data") or {}
        multi_rows = tbl2.get("multi_parent_rows", [])
        assert len(multi_rows) == 4, (
            f"Expected 4 branches for 'Chỉ tiêu trồng trọt trong năm 2026 là bao nhiêu?', but got {len(multi_rows)} rows. "
            f"Preposition 'trong' leaked parent context 'Trang trại'! Answer: {ans2}"
        )
        assert "HTX nông nghiệp" in ans2
        assert "Liên hiệp HTX nông nghiệp" in ans2
        assert "Tổ hợp tác nông nghiệp" in ans2
        assert "Trang trại" in ans2

    def test_multi_turn_independent_mission_with_preposition_thuoc_does_not_leak_context(self):
        """
        Regression test: Preposition 'thuộc' and explicit mission must NOT inherit previous parent context.
        Turn 1: Parent query 'Trang trại' (SC-2.4).
        Turn 2: 'Các chỉ tiêu thuộc nhiệm vụ Diêm nghiệp?'
        Must return 3 Level-1 criteria of mission Diêm nghiệp, 0 leakage from 'Trang trại'.
        """
        q1 = "Cho tôi xem số liệu chỉ tiêu Trang trại năm 2026?"
        res1 = warehouse_agent.run(q1)
        ans1 = res1.get("answer", "")
        history = [
            {"role": "user", "content": q1},
            {"role": "assistant", "content": ans1},
        ]
        q2 = "Các chỉ tiêu thuộc nhiệm vụ Diêm nghiệp?"
        res2 = warehouse_agent.run(q2, history=history)
        ans2 = res2.get("answer", "")
        assert "Diêm nghiệp" in ans2, f"Expected mission Diêm nghiệp in answer, got: {ans2}"
        assert "3 chỉ tiêu Cấp 1" in ans2, f"Expected 3 Level-1 criteria for Diêm nghiệp, got: {ans2}"

    def test_multi_turn_context_inheritance_with_the_con_and_nhom_do(self):
        """
        Regression test: Verify context inheritance succeeds with 'Thế còn' and demonstrative 'nhóm đó'.
        Turn 1: Parent query 'Trang trại' (SC-2.4).
        Turn 2: 'Thế còn chỉ tiêu trồng trọt trong nhóm đó?'
        Must inherit 'Trang trại' parent context and resolve to SINGLE_LEAF (value 26),
        NOT the 4-row multi_parent_rows table.
        """
        q1 = "Cho tôi xem số liệu chỉ tiêu Trang trại năm 2026?"
        res1 = warehouse_agent.run(q1)
        ans1 = res1.get("answer", "")
        history = [
            {"role": "user", "content": q1},
            {"role": "assistant", "content": ans1},
        ]
        q2 = "Thế còn chỉ tiêu trồng trọt trong nhóm đó?"
        res2 = warehouse_agent.run(q2, history=history)
        ans2 = res2.get("answer", "")
        tbl2 = res2.get("tabular_data") or {}

        assert "Trồng trọt" in ans2
        assert "26" in ans2
        assert len(tbl2.get("multi_parent_rows", [])) == 0, (
            f"Expected 0 multi_parent_rows (resolved to Trang trại), but got {len(tbl2.get('multi_parent_rows', []))} rows."
        )

    def test_multi_turn_unaccented_token_con_does_not_trigger_discourse_connective(self):
        """
        Regression test: Unaccented token 'con' must NOT trigger DISCOURSE_CONNECTIVE context leakage.
        Turn 1: Parent query 'Trang trại' (SC-2.4).
        Turn 2: 'Chỉ tiêu con trong năm 2026 là bao nhiêu?'
        Must NOT treat 'con' as connective, 0 parent context leakage from 'Trang trại'.
        """
        q1 = "Cho tôi xem số liệu chỉ tiêu Trang trại năm 2026?"
        res1 = warehouse_agent.run(q1)
        ans1 = res1.get("answer", "")
        history = [
            {"role": "user", "content": q1},
            {"role": "assistant", "content": ans1},
        ]
        q2 = "Chỉ tiêu con trong năm 2026 là bao nhiêu?"
        res2 = warehouse_agent.run(q2, history=history)
        ans2 = res2.get("answer", "")
        tbl2 = res2.get("tabular_data") or {}

        # Should execute general criteria exploration (Level 1 summary), not Trang trại leaf query
        assert "9 chỉ tiêu Cấp 1" in ans2 or "danh sách các chỉ tiêu gốc" in ans2
        assert len(tbl2.get("multi_parent_rows", [])) == 0


    @pytest.mark.asyncio
    async def test_run_stream_with_existing_history_no_name_error(self):
        history = [
            {"role": "user", "content": "Số lượng chỉ tiêu thu thập được trong nửa đầu năm 2026 là bao nhiêu?"},
            {"role": "assistant", "content": "Dưới đây là danh sách các chỉ tiêu gốc (Cấp 1) đã được phê duyệt (9 chỉ tiêu Cấp 1 / 114 bản ghi)."},
        ]
        chunks = []
        async for chunk in warehouse_agent.run_stream(
            query="Cho tôi xem số liệu chỉ tiêu Diện tích muối công nghiệp trong tháng 6 năm 2026?",
            session_id="test_stream_session_v3",
            history=history,
        ):
            chunks.append(chunk)
        joined = "".join(chunks)
        assert "event: done" in joined
        assert "520" in joined


# ==============================================================================
# 4. PA 2.1: TEMPORAL-SAFE TREE HYDRATION (`has_temporal_filter`)
# ==============================================================================
class TestPA21TemporalSafeTreeHydration:
    def test_build_criteria_tree_for_rows_masks_unqueried_siblings_when_temporal_filter_active(self):
        catalog = DuckDBSemanticCatalog()
        leaves = catalog.conn.execute(
            "SELECT id, name, parent_name FROM catalog_criteria_hierarchy WHERE root_name = 'Tổng diện tích sản xuất muối' AND is_leaf = TRUE"
        ).fetchall()
        assert len(leaves) >= 2
        target_cid, target_name, target_parent = leaves[0]

        # Simulate a temporal-filtered SQL result containing ONLY target_cid with a specific period value (999)
        mock_rows = [
            {
                "criteria_id": target_cid,
                "ten_chi_tieu": target_name,
                "nhom_chi_tieu": target_parent,
                "gia_tri_moi_nhat": "999",
            }
        ]

        # When has_temporal_filter=True, sibling nodes NOT in mock_rows must have value=None
        tree_by_root, _ = catalog.build_criteria_tree_for_rows(mock_rows, has_temporal_filter=True)
        assert isinstance(tree_by_root, dict) and len(tree_by_root) == 1
        root = next(iter(tree_by_root.values()))
        assert root["name"] == "Tổng diện tích sản xuất muối"

        queried_values = []
        sibling_values = []
        for child in root.get("children", []):
            if child["id"] == target_cid:
                queried_values.append(str(child["value"]))
            else:
                sibling_values.append(child["value"])

        assert queried_values == ["999"]
        assert len(sibling_values) >= 1
        assert all(v is None for v in sibling_values)

        # Conversely, when has_temporal_filter=False, unqueried siblings fall back to full-year catalog lval
        tree_unfiltered, _ = catalog.build_criteria_tree_for_rows(mock_rows, has_temporal_filter=False)
        root_unfiltered = next(iter(tree_unfiltered.values()))
        sibling_values_unfiltered = [
            ch["value"] for ch in root_unfiltered.get("children", []) if ch["id"] != target_cid
        ]
        assert any(v is not None for v in sibling_values_unfiltered)


# ==============================================================================
# 5. DISCOURSE STATE TRACKER VALIDATION & OOD QUERY REGRESSION
# ==============================================================================
class TestDiscourseStateTrackerCoercionAndOODQuery:
    def test_dialogue_state_frame_coercion(self):
        from IPGov_Chatbot.modules.mod03_router.discourse_state_tracker import DialogueStateFrame
        frame = DialogueStateFrame(
            topic_entity=["HTX nông nghiệp", "Tổ hợp tác nông nghiệp"],
            keywords=[["nested", "kw"], "standalone"],
        )
        assert isinstance(frame.topic_entity, str)
        assert "HTX nông nghiệp" in frame.topic_entity
        assert isinstance(frame.keywords, list)
        assert "nested" in frame.keywords
        assert "kw" in frame.keywords

    def test_ood_agriculture_mission_listing_query_no_validation_error(self):
        query = "Liệt kê danh mục các nhiệm vụ thuộc khối ngành Nông nghiệp và Phát triển nông thôn?"
        res = warehouse_agent.run(query)
        assert res is not None
        assert "answer" in res
        ans = res["answer"]
        assert "nhiệm vụ" in ans.lower()
        assert "Diêm nghiệp" in ans
        assert "Phát triển nông thôn" in ans
        tbl = res.get("tabular_data") or {}
        assert len(tbl.get("rows", [])) >= 2
        assert res.get("status") != "FAILED"
