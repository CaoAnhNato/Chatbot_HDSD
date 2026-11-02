"""
Empirical Challenger Test Suite — M4 Iteration 3
Verifies backend query resolution for Turn 6 (multi-date, multi-domain salt & livestock)
and Turn 11 (date range [01/01/2026, 30/06/2026] area & households), plus adversarial variants.
"""

import pytest
import uuid
import re
from typing import Dict, Any

from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import warehouse_agent
from IPGov_Chatbot.modules.mod03_router.canonical_normalizer import CanonicalSemanticNormalizer

USER_CTX = {
    "role_level": 0,
    "tenant_code": "68",
    "is_unrestricted": True,
    "schema": "dwh_internal",
    "user_id": "challenger_m4_r3",
    "username": "lanhdao_ubnd_lamdong",
    "name": "Lãnh đạo UBND Tỉnh Lâm Đồng",
}

# ==============================================================================
# SECTION 1: DEFECT 1 EMPIRICAL CHALLENGES (Turn 6 Multi-Domain & Multi-Date)
# ==============================================================================

class TestDefect1Turn6Empirical:
    """
    Challenge Defect 1:
    Query: 'Tình hình sản xuất muối và số lượng gia súc ngày 31/7/2026 và 15/10/2026 như thế nào?'
    Must verify:
    1. 'sản xuất muối' is NOT dropped in favour of livestock.
    2. Both salt and livestock criteria are addressed.
    3. No date leakage: '27/10/2026' is NEVER injected into response/table.
    4. Multi-date recognition: both 31/07/2026 and 15/10/2026 are evaluated.
    """

    def test_turn6_exact_query_resolution(self):
        query = "Tình hình sản xuất muối và số lượng gia súc ngày 31/7/2026 và 15/10/2026 như thế nào?"
        sess_id = f"challenger_t6_{uuid.uuid4().hex[:6]}"
        res = warehouse_agent.run(query=query, session_id=sess_id, user_context=USER_CTX)
        ans = res.get("answer", "")
        tab = res.get("tabular_data")

        # 1. Salt must NOT be dropped
        assert "muối" in ans.lower(), f"Turn 6 failed: 'muối' was dropped from answer: {ans}"
        # 2. Livestock must be present
        assert any(w in ans.lower() for w in ("gia súc", "trâu", "bò")), (
            f"Turn 6 failed: livestock missing from answer: {ans}"
        )
        # 3. Date leakage check: 27/10/2026 must NOT be present anywhere in answer or table
        assert "27/10/2026" not in ans, (
            f"Turn 6 failed: Leaked unrequested date '27/10/2026' in answer: {ans}"
        )
        if tab and isinstance(tab, dict):
            for row in tab.get("rows", []):
                for val in row.values():
                    assert "27/10/2026" not in str(val), f"Leaked 27/10/2026 in tabular data: {row}"

        # 4. Dates 31/7/2026 and 15/10/2026 must be addressed in SQL query or answer
        assert any(d in ans for d in ("31/07/2026", "31/7/2026", "2026-07-31")), (
            f"Turn 6 failed: Missing date 31/07/2026 in answer: {ans}"
        )
        assert any(d in ans for d in ("15/10/2026", "15/10", "2026-10-15")), (
            f"Turn 6 failed: Missing date 15/10/2026 in query evaluation: {ans}"
        )

        # 5. Verify tabular data contains both criteria
        if tab and isinstance(tab, dict):
            rows = tab.get("rows", [])
            assert len(rows) >= 2, f"Expected 2 rows in table, got {len(rows)}"
            items_str = " ".join(str(r.get("item", "")) for r in rows).lower()
            assert "muối" in items_str, f"Missing salt row in table: {rows}"
            assert "gia súc" in items_str, f"Missing livestock row in table: {rows}"

    def test_turn6_normalizer_preserves_both_domains(self):
        normalizer = CanonicalSemanticNormalizer()
        query = "Tình hình sản xuất muối và số lượng gia súc ngày 31/7/2026 và 15/10/2026 như thế nào?"
        frame = normalizer.normalize_query(query=query)

        # Check raw metric mentions or canonical names include both domains
        all_metrics_text = " ".join(
            (frame.canonical_metric_names or []) +
            (getattr(frame, "raw_metric_mentions", []) or [])
        ).lower()
        assert "muối" in all_metrics_text or any("muối" in str(x).lower() for x in (frame.canonical_metric_names or [])), (
            f"Normalizer dropped salt! canonical_metric_names: {frame.canonical_metric_names}"
        )
        assert any(w in all_metrics_text for w in ("gia súc", "chăn nuôi", "gia_suc")), (
            f"Normalizer dropped livestock! canonical_metric_names: {frame.canonical_metric_names}"
        )
        # Check time series periods extracted both dates
        periods = getattr(frame, "time_series_periods", []) or []
        periods_str = [str(p)[:10] for p in periods]
        assert "2026-07-31" in periods_str, f"Missing 2026-07-31 in periods: {periods_str}"
        assert "2026-10-15" in periods_str, f"Missing 2026-10-15 in periods: {periods_str}"


# ==============================================================================
# SECTION 2: DEFECT 3 EMPIRICAL CHALLENGES (Turn 11 Date Range [01/01/2026, 30/06/2026])
# ==============================================================================

class TestDefect3Turn11Empirical:
    """
    Challenge Defect 3:
    Query: 'Tổng diện tích sản xuất muối và tổng số hộ sản xuất muối trong 6 tháng đầu năm 2026 là bao nhiêu?'
    Must verify:
    1. Range [01/01/2026, 30/06/2026] is NOT rejected as out-of-bounds.
    2. Correctly matches and aggregates warehouse facts (1,520 ha, 660 households).
    3. Multi-criteria conformed table rendered.
    """

    def test_turn11_exact_query_resolution(self):
        query = "Tổng diện tích sản xuất muối và tổng số hộ sản xuất muối trong 6 tháng đầu năm 2026 là bao nhiêu?"
        sess_id = f"challenger_t11_{uuid.uuid4().hex[:6]}"
        res = warehouse_agent.run(query=query, session_id=sess_id, user_context=USER_CTX)
        ans = res.get("answer", "")
        tab = res.get("tabular_data")

        # 1. Must NOT trigger out of bounds
        assert "nằm ngoài phạm vi kỳ báo cáo có dữ liệu" not in ans.lower(), (
            f"Turn 11 failed: Erroneously triggered out-of-bounds response: {ans}"
        )
        assert "ngoài phạm vi thời gian" not in ans.lower(), (
            f"Turn 11 failed: Erroneously triggered out-of-bounds response: {ans}"
        )

        # 2. Must contain area 1,520 ha and 660 households
        area_matched = ("1,520" in ans or "1520" in ans)
        hh_matched = "660" in ans
        assert area_matched, f"Turn 11 failed: Area value 1,520 ha missing from answer: {ans}"
        assert hh_matched, f"Turn 11 failed: Household value 660 missing from answer: {ans}"

        # 3. Tabular data verification
        if tab and isinstance(tab, dict):
            rows = tab.get("rows", [])
            assert len(rows) >= 2, f"Expected at least 2 criteria rows in table, got {len(rows)}"
            table_str = str(rows)
            assert "1,520" in table_str or "1520" in table_str
            assert "660" in table_str

    def test_turn11_normalizer_date_range_extraction(self):
        normalizer = CanonicalSemanticNormalizer()
        query = "Tổng diện tích sản xuất muối và tổng số hộ sản xuất muối trong 6 tháng đầu năm 2026 là bao nhiêu?"
        frame = normalizer.normalize_query(query=query)

        assert frame.date_from is not None, "Normalizer failed to extract date_from for 6 months 2026"
        assert frame.date_to is not None, "Normalizer failed to extract date_to for 6 months 2026"
        d_from_str = str(frame.date_from)[:10]
        d_to_str = str(frame.date_to)[:10]
        assert d_from_str == "2026-01-01", f"Expected date_from 2026-01-01, got {d_from_str}"
        assert d_to_str == "2026-06-30", f"Expected date_to 2026-06-30, got {d_to_str}"


# ==============================================================================
# SECTION 3: ADVERSARIAL VARIATIONS & STRESS HARNESS
# ==============================================================================

class TestAdversarialVariations:
    """
    Adversarial stress testing against edge cases, boundary perturbations,
    and alternative phrasings.
    """

    # --- Defect 1 Variations ---

    def test_adv_turn6_reversed_dates(self):
        """Query with inverted date order: 15/10/2026 before 31/7/2026."""
        query = "Tình hình sản xuất muối và số lượng gia súc ngày 15/10/2026 và 31/7/2026 như thế nào?"
        sess_id = f"adv_t6_rev_{uuid.uuid4().hex[:6]}"
        res = warehouse_agent.run(query=query, session_id=sess_id, user_context=USER_CTX)
        ans = res.get("answer", "")

        assert "muối" in ans.lower(), "Reversed dates query dropped salt!"
        assert any(w in ans.lower() for w in ("gia súc", "trâu", "bò")), "Reversed dates query dropped livestock!"
        assert "27/10/2026" not in ans, "Reversed dates query leaked 27/10/2026!"

    def test_adv_turn6_synonym_phrasing(self):
        """Alternative phrasing: 'Các chỉ số sản xuất muối và chăn nuôi...'"""
        query = "Các chỉ số sản xuất muối và chăn nuôi ngày 31/7/2026 và 15/10/2026"
        sess_id = f"adv_t6_syn_{uuid.uuid4().hex[:6]}"
        res = warehouse_agent.run(query=query, session_id=sess_id, user_context=USER_CTX)
        ans = res.get("answer", "")

        assert "muối" in ans.lower(), "Synonym query dropped salt!"
        assert "27/10/2026" not in ans, "Synonym query leaked 27/10/2026!"

    def test_adv_single_domain_salt_with_general_phrase(self):
        """Single domain salt with 'tình hình' must NOT be expanded to livestock."""
        query = "Tình hình sản xuất muối ngày 31/7/2026"
        sess_id = f"adv_salt_single_{uuid.uuid4().hex[:6]}"
        res = warehouse_agent.run(query=query, session_id=sess_id, user_context=USER_CTX)
        ans = res.get("answer", "")

        assert "muối" in ans.lower(), "Salt query dropped salt!"
        assert "trâu" not in ans.lower() and "bò" not in ans.lower(), (
            f"Salt query unexpectedly expanded to livestock: {ans}"
        )
        assert "27/10/2026" not in ans, "Leaked 27/10/2026 in single salt query!"

    def test_adv_single_domain_livestock_with_general_phrase(self):
        """Single domain livestock with 'tình hình' should resolve livestock metrics."""
        query = "Tình hình chăn nuôi gia súc ngày 15/10/2026"
        sess_id = f"adv_live_single_{uuid.uuid4().hex[:6]}"
        res = warehouse_agent.run(query=query, session_id=sess_id, user_context=USER_CTX)
        ans = res.get("answer", "")

        assert any(w in ans.lower() for w in ("gia súc", "trâu", "bò")), (
            f"Livestock query failed to resolve livestock: {ans}"
        )
        assert "muối" not in ans.lower(), "Livestock query unexpectedly hallucinated salt!"

    def test_adv_three_dates_no_leakage(self):
        """Three valid dates in 2026 must not leak 27/10/2026."""
        query = "Tình hình sản xuất muối và số lượng gia súc ngày 31/3/2026, 30/6/2026 và 31/7/2026"
        sess_id = f"adv_3dates_{uuid.uuid4().hex[:6]}"
        res = warehouse_agent.run(query=query, session_id=sess_id, user_context=USER_CTX)
        ans = res.get("answer", "")

        assert "muối" in ans.lower()
        assert "27/10/2026" not in ans, "3-date query leaked 27/10/2026!"

    # --- Defect 3 Variations ---

    def test_adv_turn11_explicit_tu_den(self):
        """Query with explicit 'từ ngày 01/01/2026 đến ngày 30/06/2026'."""
        query = "Tổng diện tích sản xuất muối và tổng số hộ sản xuất muối từ ngày 01/01/2026 đến ngày 30/06/2026 là bao nhiêu?"
        sess_id = f"adv_t11_tuden_{uuid.uuid4().hex[:6]}"
        res = warehouse_agent.run(query=query, session_id=sess_id, user_context=USER_CTX)
        ans = res.get("answer", "")

        assert "nằm ngoài phạm vi kỳ báo cáo có dữ liệu" not in ans.lower()
        assert ("1,520" in ans or "1520" in ans)
        assert "660" in ans

    def test_adv_turn11_q1_range_in_bounds(self):
        """Query with Q1 date range: from 01/01/2026 to 31/03/2026."""
        query = "Tổng diện tích sản xuất muối từ ngày 01/01/2026 đến ngày 31/03/2026"
        sess_id = f"adv_t11_q1_{uuid.uuid4().hex[:6]}"
        res = warehouse_agent.run(query=query, session_id=sess_id, user_context=USER_CTX)
        ans = res.get("answer", "")

        assert "nằm ngoài phạm vi kỳ báo cáo có dữ liệu" not in ans.lower()
        assert "muối" in ans.lower()

    def test_adv_turn11_past_range_out_of_bounds(self):
        """Range completely in past (2025) MUST be rejected as out-of-bounds."""
        query = "Tổng diện tích sản xuất muối và tổng số hộ sản xuất muối từ ngày 01/01/2025 đến ngày 30/06/2025"
        sess_id = f"adv_past_oob_{uuid.uuid4().hex[:6]}"
        res = warehouse_agent.run(query=query, session_id=sess_id, user_context=USER_CTX)
        ans = res.get("answer", "")

        assert any(k in ans.lower() for k in ("ngoài phạm vi", "chưa có số liệu", "không có dữ liệu")), (
            f"Past range 2025 was expected to be out-of-bounds: {ans}"
        )

    def test_adv_turn11_future_range_out_of_bounds(self):
        """Range completely in future (2027) MUST be rejected as out-of-bounds."""
        query = "Tổng diện tích sản xuất muối và tổng số hộ sản xuất muối từ ngày 01/01/2027 đến ngày 30/06/2027"
        sess_id = f"adv_future_oob_{uuid.uuid4().hex[:6]}"
        res = warehouse_agent.run(query=query, session_id=sess_id, user_context=USER_CTX)
        ans = res.get("answer", "")

        assert any(k in ans.lower() for k in ("ngoài phạm vi", "chưa có số liệu", "không có dữ liệu")), (
            f"Future range 2027 was expected to be out-of-bounds: {ans}"
        )

    def test_adv_turn11_single_date_past_out_of_bounds(self):
        """Discrete date in 2025 (e.g. 31/12/2025) must be rejected as out-of-bounds."""
        query = "Cho tôi xem sản lượng muối ngày 31/12/2025"
        sess_id = f"adv_single_past_{uuid.uuid4().hex[:6]}"
        res = warehouse_agent.run(query=query, session_id=sess_id, user_context=USER_CTX)
        ans = res.get("answer", "")

        assert any(k in ans.lower() for k in ("ngoài phạm vi", "chưa có số liệu", "không có dữ liệu")), (
            f"Date 31/12/2025 was expected to be out-of-bounds: {ans}"
        )
