"""
Adversarial Stress-Testing Suite for Milestone 2
Targeting:
1. Branch-Scoped Disambiguation (R2.5)
2. Negative / Unconstrained Queries (SC-2.1)
3. Temporal Breakdown Edge Cases (R2.3)
4. Salt Production Alias Resolution
5. Canonical Warehouse Ordering (R2.1)
"""

import pytest
import uuid
import sys
from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import warehouse_agent
from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog


@pytest.fixture(scope="module")
def catalog():
    return DuckDBSemanticCatalog()


class TestBranchScopedDisambiguation:
    """R2.5: Branch-Scoped Single Criterion Disambiguation"""

    def test_chan_nuoi_lhhtx_with_date(self):
        """Query specifying LHHTX branch and 30/4 date filter."""
        query = "cho tôi biết số liệu chăn nuôi của liên hiệp hợp tác xã ngày 30/4"
        session_id = f"test_adv_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(query=query, session_id=session_id)
        ans = res.get("final_answer", "")

        assert not res.get("is_clarification_needed"), f"Should not clarify: {ans}"
        assert "Tổng số LHHTX phân theo lĩnh vực" in ans or "Liên hiệp HTX" in ans or "LHHTX" in ans, f"Wrong branch: {ans}"
        assert "31/03/2026" in ans, f"Milestone date 31/03/2026 missing for 30/4 query: {ans}"
        assert "1" in ans, f"Value 1 missing: {ans}"
        assert "Trang trại" not in ans or "Bảng so sánh" not in ans, f"Must not be 4-branch table: {ans}"

    def test_chan_nuoi_htx(self):
        """Query specifying HTX branch."""
        query = "cho tôi biết chăn nuôi của hợp tác xã"
        session_id = f"test_adv_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(query=query, session_id=session_id)
        ans = res.get("final_answer", "")

        assert not res.get("is_clarification_needed"), f"Should not clarify: {ans}"
        assert "Số lượng HTX phân theo lĩnh vực" in ans or "HTX" in ans, f"Should mention HTX branch: {ans}"
        assert "25" in ans, f"HTX chăn nuôi latest value 25 missing: {ans}"
        assert "Trang trại" not in ans and "Tổ hợp tác" not in ans, f"Must be single branch, found multi-branch: {ans}"

    def test_trong_trot_tht(self):
        """Query specifying THT branch."""
        query = "cho tôi biết trồng trọt của tổ hợp tác"
        session_id = f"test_adv_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(query=query, session_id=session_id)
        ans = res.get("final_answer", "")

        assert not res.get("is_clarification_needed"), f"Should not clarify: {ans}"
        assert "THT" in ans or "Tổ hợp tác" in ans, f"Should mention THT: {ans}"
        assert "Trang trại" not in ans and "Liên hiệp" not in ans, f"Must be single branch: {ans}"

    def test_chan_nuoi_trang_trai(self):
        """Query specifying Trang trại branch."""
        query = "cho tôi biết chăn nuôi của trang trại"
        session_id = f"test_adv_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(query=query, session_id=session_id)
        ans = res.get("final_answer", "")

        assert not res.get("is_clarification_needed"), f"Should not clarify: {ans}"
        assert "Trang trại" in ans or "TT" in ans, f"Should mention Trang trại: {ans}"
        assert "Liên hiệp" not in ans and "Tổ hợp tác" not in ans, f"Must be single branch: {ans}"

    def test_acronym_lhhtx(self):
        """Query using acronym LHHTX directly."""
        query = "cho tôi biết chăn nuôi của lhhtx"
        session_id = f"test_adv_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(query=query, session_id=session_id)
        ans = res.get("final_answer", "")

        assert not res.get("is_clarification_needed"), f"Should not clarify: {ans}"
        assert "LHHTX" in ans or "Liên hiệp" in ans, f"Should route to LHHTX: {ans}"
        assert "Trang trại" not in ans and "Tổ hợp tác" not in ans, f"Must be single branch: {ans}"

    def test_acronym_tht(self):
        """Query using acronym THT directly."""
        query = "cho tôi biết trồng trọt của tht"
        session_id = f"test_adv_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(query=query, session_id=session_id)
        ans = res.get("final_answer", "")

        assert not res.get("is_clarification_needed"), f"Should not clarify: {ans}"
        assert "THT" in ans or "Tổ hợp tác" in ans, f"Should route to THT: {ans}"
        assert "Trang trại" not in ans and "Liên hiệp" not in ans, f"Must be single branch: {ans}"

    def test_inverted_order_lhhtx(self):
        """Adversarial: Inverted word order 'liên hiệp hợp tác xã chăn nuôi số liệu bao nhiêu'."""
        query = "liên hiệp hợp tác xã chăn nuôi số liệu bao nhiêu"
        session_id = f"test_adv_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(query=query, session_id=session_id)
        ans = res.get("final_answer", "")

        assert not res.get("is_clarification_needed"), f"Should not clarify: {ans}"
        assert "LHHTX" in ans or "Liên hiệp" in ans, f"Should route to LHHTX: {ans}"
        assert "Trang trại" not in ans and "Tổ hợp tác" not in ans, f"Must be single branch: {ans}"

    def test_other_sector_thuy_san_htx(self):
        """Adversarial: Sector 'thủy sản' for HTX."""
        query = "cho tôi biết số liệu thủy sản của hợp tác xã"
        session_id = f"test_adv_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(query=query, session_id=session_id)
        ans = res.get("final_answer", "")

        assert not res.get("is_clarification_needed"), f"Should not clarify: {ans}"
        assert "HTX" in ans or "Hợp tác xã" in ans, f"Should route to HTX: {ans}"
        assert "Trang trại" not in ans and "Liên hiệp" not in ans, f"Must be single branch: {ans}"

    def test_other_sector_lam_nghiep_lhhtx(self):
        """Adversarial: Sector 'lâm nghiệp' for LHHTX."""
        query = "cho tôi biết lâm nghiệp của liên hiệp htx"
        session_id = f"test_adv_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(query=query, session_id=session_id)
        ans = res.get("final_answer", "")

        assert not res.get("is_clarification_needed"), f"Should not clarify: {ans}"
        assert "LHHTX" in ans or "Liên hiệp" in ans, f"Should route to LHHTX: {ans}"
        assert "Trang trại" not in ans and "Tổ hợp tác" not in ans, f"Must be single branch: {ans}"


class TestUnconstrainedDuplicateLeaf:
    """Negative tests: unconstrained queries MUST trigger SC-2.1 duplicate leaf comparison"""

    def test_unconstrained_chan_nuoi(self):
        """Query 'cho tôi biết số liệu chăn nuôi' without branch must compare all branches."""
        query = "cho tôi biết số liệu chăn nuôi"
        session_id = f"test_adv_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(query=query, session_id=session_id)
        ans = res.get("final_answer", "")

        assert not res.get("is_clarification_needed"), f"Should not clarify: {ans}"
        assert "Nhóm chỉ tiêu (Cấp)" in ans or "Nhóm chỉ tiêu" in ans, f"Must have branch comparison table: {ans}"
        branches_found = sum(1 for b in ["Trang trại", "HTX", "THT", "LHHTX"] if b in ans or b.lower() in ans.lower())
        assert branches_found >= 3, f"Must show multiple branches in comparison table: {ans}"

    def test_unconstrained_trong_trot(self):
        """Query 'cho tôi biết số liệu trồng trọt' without branch must compare all branches."""
        query = "cho tôi biết số liệu trồng trọt"
        session_id = f"test_adv_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(query=query, session_id=session_id)
        ans = res.get("final_answer", "")

        assert not res.get("is_clarification_needed"), f"Should not clarify: {ans}"
        assert "Nhóm chỉ tiêu" in ans, f"Must have comparison table: {ans}"
        branches_found = sum(1 for b in ["Trang trại", "HTX", "THT", "LHHTX"] if b in ans or b.lower() in ans.lower())
        assert branches_found >= 3, f"Must show multiple branches: {ans}"

    def test_unconstrained_thuy_san(self):
        """Query 'cho tôi biết số liệu thủy sản' without branch must compare all branches."""
        query = "cho tôi biết số liệu thủy sản"
        session_id = f"test_adv_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(query=query, session_id=session_id)
        ans = res.get("final_answer", "")

        assert not res.get("is_clarification_needed"), f"Should not clarify: {ans}"
        assert "Nhóm chỉ tiêu" in ans, f"Must have comparison table: {ans}"
        branches_found = sum(1 for b in ["Trang trại", "HTX", "THT", "LHHTX"] if b in ans or b.lower() in ans.lower())
        assert branches_found >= 3, f"Must show multiple branches: {ans}"

    def test_unconstrained_lam_nghiep(self):
        """Query 'cho tôi biết số liệu lâm nghiệp' without branch must compare all branches."""
        query = "cho tôi biết số liệu lâm nghiệp"
        session_id = f"test_adv_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(query=query, session_id=session_id)
        ans = res.get("final_answer", "")

        assert not res.get("is_clarification_needed"), f"Should not clarify: {ans}"
        assert "Nhóm chỉ tiêu" in ans, f"Must have comparison table: {ans}"
        branches_found = sum(1 for b in ["Trang trại", "HTX", "THT", "LHHTX"] if b in ans or b.lower() in ans.lower())
        assert branches_found >= 3, f"Must show multiple branches: {ans}"


class TestTemporalBreakdownEdgeCases:
    """R2.3: Hierarchy breakdown with/without temporal filters"""

    def test_breakdown_with_date_filter(self):
        """Breakdown with specific date '30/04/2026'."""
        query = "số lượng lĩnh vực của HTX nông nghiệp ngày 30/04/2026"
        session_id = f"test_adv_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(query=query, session_id=session_id)
        ans = res.get("final_answer", "")

        assert not res.get("is_clarification_needed"), f"Should not clarify: {ans}"
        assert "8" in ans, f"Must mention 8 fields: {ans}"
        assert "30/04/2026" in ans or "31/03/2026" in ans or "quý" in ans.lower() or "kỳ" in ans.lower(), f"Temporal info missing: {ans}"
        tab_data = res.get("tabular_data")
        assert tab_data is not None, "Must have tabular data"
        assert len(tab_data.get("rows", [])) == 8, f"Table must have 8 rows, got {len(tab_data.get('rows', []))}"

    def test_breakdown_without_date_filter(self):
        """Breakdown without date filter."""
        query = "số lượng lĩnh vực của HTX nông nghiệp"
        session_id = f"test_adv_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(query=query, session_id=session_id)
        ans = res.get("final_answer", "")

        assert not res.get("is_clarification_needed"), f"Should not clarify: {ans}"
        assert "8" in ans, f"Must mention 8 fields: {ans}"
        tab_data = res.get("tabular_data")
        assert tab_data is not None, "Must have tabular data"
        assert len(tab_data.get("rows", [])) == 8, f"Table must have 8 rows, got {len(tab_data.get('rows', []))}"

    def test_breakdown_quy_1(self):
        """Breakdown in Q1."""
        query = "số lượng lĩnh vực của HTX nông nghiệp trong quý 1"
        session_id = f"test_adv_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(query=query, session_id=session_id)
        ans = res.get("final_answer", "")

        assert not res.get("is_clarification_needed"), f"Should not clarify: {ans}"
        assert "8" in ans, f"Must mention 8 fields: {ans}"
        tab_data = res.get("tabular_data")
        assert tab_data is not None, "Must have tabular data"
        assert len(tab_data.get("rows", [])) == 8

    def test_salt_breakdown_with_date(self):
        """Breakdown of salt with date filter."""
        query = "đang có bao nhiêu loại tổng sản lượng muối 30/4"
        session_id = f"test_adv_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(query=query, session_id=session_id)
        ans = res.get("final_answer", "")

        assert not res.get("is_clarification_needed"), f"Should not clarify: {ans}"
        assert "muối" in ans.lower(), f"Should mention salt: {ans}"
        tab_data = res.get("tabular_data")
        assert tab_data is not None, "Must have tabular data"

    def test_salt_area_breakdown_with_date(self):
        """Breakdown of salt area with date filter."""
        query = "cho tôi biết đang có các loại diện tích sản xuất muối gì ngày 30/4"
        session_id = f"test_adv_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(query=query, session_id=session_id)
        ans = res.get("final_answer", "")

        assert not res.get("is_clarification_needed"), f"Should not clarify: {ans}"
        assert "muối" in ans.lower(), f"Should mention salt: {ans}"
        tab_data = res.get("tabular_data")
        assert tab_data is not None, "Must have tabular data"


class TestSaltProductionAlias:
    """Salt production vs salt area alias resolution"""

    def test_tong_san_luong_muoi(self, catalog):
        """Query 'tổng sản lượng muối' must resolve to tong_san_luong_muoi_gd23."""
        clf = catalog.classify_criterion_hierarchy("tổng sản lượng muối")
        code = clf.get("matched_code") or clf.get("code")
        assert code == "tong_san_luong_muoi_gd23", f"Expected tong_san_luong_muoi_gd23, got {code} ({clf})"

    def test_dien_tich_san_xuat_muoi(self, catalog):
        """Query 'diện tích sản xuất muối' must resolve to tong_dien_tich_san_xuat_muoi."""
        clf = catalog.classify_criterion_hierarchy("diện tích sản xuất muối")
        code = clf.get("matched_code") or clf.get("code")
        assert code == "tong_dien_tich_san_xuat_muoi", f"Expected tong_dien_tich_san_xuat_muoi, got {code} ({clf})"

    def test_san_luong_muoi_alone(self, catalog):
        """Query 'sản lượng muối' must resolve to tong_san_luong_muoi_gd23."""
        clf = catalog.classify_criterion_hierarchy("sản lượng muối")
        code = clf.get("matched_code") or clf.get("code")
        assert code == "tong_san_luong_muoi_gd23", f"Expected tong_san_luong_muoi_gd23, got {code} ({clf})"

    def test_agent_tong_san_luong_muoi(self):
        """Agent run for 'tổng sản lượng muối'."""
        query = "tổng sản lượng muối"
        session_id = f"test_adv_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(query=query, session_id=session_id)
        ans = res.get("final_answer", "")
        assert not res.get("is_clarification_needed"), f"Should not clarify: {ans}"
        assert "sản lượng muối" in ans.lower(), f"Should mention sản lượng muối: {ans}"

    def test_agent_dien_tich_san_xuat_muoi(self):
        """Agent run for 'diện tích sản xuất muối'."""
        query = "diện tích sản xuất muối"
        session_id = f"test_adv_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(query=query, session_id=session_id)
        ans = res.get("final_answer", "")
        assert not res.get("is_clarification_needed"), f"Should not clarify: {ans}"
        assert "diện tích" in ans.lower(), f"Should mention diện tích: {ans}"


class TestCanonicalOrdering:
    """R2.1: Canonical warehouse ordering preservation"""

    def test_htx_effectiveness_ordering(self):
        """Evaluation levels must be in canonical DWH order: Tốt -> Trung bình -> Kém -> Chưa đủ điều kiện."""
        query = "có bao nhiêu mức đánh giá hiệu quả hoạt động của hợp tác xã nông nghiệp ?"
        session_id = f"test_adv_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(query=query, session_id=session_id)
        ans = res.get("final_answer", "")
        tab_data = res.get("tabular_data")
        assert tab_data is not None, "Tabular data missing"
        rows = tab_data.get("rows", [])
        assert len(rows) == 4, f"Expected 4 rows, got {len(rows)}"
        row_names = [r["item"] for r in rows]
        expected_seq = [
            "Số HTX nông nghiệp hoạt động hiệu quả tốt",
            "Số HTX nông nghiệp hoạt động hiệu quả trung bình",
            "Số HTX nông nghiệp hoạt động kém hiệu quả",
            "Chưa đủ điều kiện đánh giá",
        ]
        assert row_names == expected_seq, f"Ordering mismatch! Expected {expected_seq}, got {row_names}"

    def test_htx_sectors_ordering(self):
        """HTX fields must be in exact warehouse order."""
        query = "cho tôi biết số lĩnh vực của HTX nông nghiệp"
        session_id = f"test_adv_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(query=query, session_id=session_id)
        tab_data = res.get("tabular_data")
        assert tab_data is not None, "Tabular data missing"
        rows = tab_data.get("rows", [])
        assert len(rows) == 8, f"Expected 8 rows, got {len(rows)}"
        row_names = [r["item"] for r in rows]
        expected_seq = [
            "Trồng trọt",
            "Chăn nuôi",
            "Lâm nghiệp",
            "Thủy sản",
            "Diêm nghiệp",
            "Chế biến nông sản",
            "Nước sạch NT",
            "Tổng hợp",
        ]
        assert row_names == expected_seq, f"Ordering mismatch! Expected {expected_seq}, got {row_names}"
