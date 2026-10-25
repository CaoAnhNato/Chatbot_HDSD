# -*- coding: utf-8 -*-
"""
Adversarial Challenger (Round 2) empirical stress-test probe for Milestone 3.
Thoroughly challenges:
1. Branch scoping across all 4 branches for multi-branch leaf criteria (Chăn nuôi, Trồng trọt, Thủy sản, Lâm nghiệp)
2. Out-of-scope non-collision in retrieve_candidate_metrics
3. Out-of-scope execution guard in warehouse_langgraph_agent
4. Non-math date preservation (verifying dates like 30/4/2026 are NOT flagged as arithmetic)
"""

import uuid
import pytest
from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog
from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import warehouse_agent


@pytest.fixture(scope="module")
def catalog():
    cat = DuckDBSemanticCatalog()
    return cat


class TestBranchScopingAdversarialGrid:
    """Stress-tests branch isolation across multiple entities and phrasing variations."""

    @pytest.mark.parametrize("query,expected_code,expected_branch_keyword", [
        # Chăn nuôi across 4 branches
        ("chăn nuôi của liên hiệp htx", "chan_nuoi_", "LHHTX"),
        ("chăn nuôi của liên hiệp hợp tác xã", "chan_nuoi_", "LHHTX"),
        ("chăn nuôi của lhhtx", "chan_nuoi_", "LHHTX"),
        ("chăn nuôi liên hiệp htx", "chan_nuoi_", "LHHTX"),
        ("chăn nuôi của trang trại", "chan_nuoi4", "Trang trại"),
        ("chăn nuôi trang trại", "chan_nuoi4", "Trang trại"),
        ("chăn nuôi của hợp tác xã", "chan_nuoi", "HTX"),
        ("chăn nuôi của htx", "chan_nuoi", "HTX"),
        ("chăn nuôi của tổ hợp tác", "chan_nuoi_3", "THT"),
        ("chăn nuôi của tht", "chan_nuoi_3", "THT"),
        # Trồng trọt across 4 branches
        ("trồng trọt của liên hiệp htx", "trong_trot_", "LHHTX"),
        ("trồng trọt của liên hiệp hợp tác xã", "trong_trot_", "LHHTX"),
        ("trồng trọt của trang trại", "trong_trot4", "Trang trại"),
        ("trồng trọt của hợp tác xã", "trong_trot", "HTX"),
        ("trồng trọt của htx", "trong_trot", "HTX"),
        ("trồng trọt của tổ hợp tác", "trong_trot3", "THT"),
        ("trồng trọt của tht", "trong_trot3", "THT"),
        # Thủy sản across branches (Trang trại has nuoi_trong_thuy_san)
        ("thủy sản của lhhtx", "thuy_san_", "LHHTX"),
        ("thủy sản của liên hiệp htx", "thuy_san_", "LHHTX"),
        ("thủy sản của htx", "thuy_san", "HTX"),
        ("thủy sản của hợp tác xã", "thuy_san", "HTX"),
        ("thủy sản của tổ hợp tác", "thuy_san3", "THT"),
        ("thủy sản của tht", "thuy_san3", "THT"),
        # Lâm nghiệp across 4 branches
        ("lâm nghiệp của liên hiệp htx", "lam_nghiep_", "LHHTX"),
        ("lâm nghiệp của liên hiệp hợp tác xã", "lam_nghiep_", "LHHTX"),
        ("lâm nghiệp của trang trại", "lam_nghiep4", "Trang trại"),
        ("lâm nghiệp của htx", "lam_nghiep", "HTX"),
        ("lâm nghiệp của tổ hợp tác", "lam_nghiep3", "THT"),
        ("lâm nghiệp của tht", "lam_nghiep3", "THT"),
    ])
    def test_branch_scoping_leaf_candidates(self, catalog, query, expected_code, expected_branch_keyword):
        cands, _, _ = catalog.find_top_k_candidates(query, top_k=5)
        assert len(cands) > 0, f"No candidates returned for query: {query}"
        top = cands[0]
        assert top["code"] == expected_code, (
            f"Query '{query}' resolved to '{top['code']}' ({top.get('root_name')}), "
            f"expected '{expected_code}' ({expected_branch_keyword}). All cands: {[(c['code'], c.get('root_name'), c['score']) for c in cands]}"
        )


class TestOutOfScopePreRetrievalCollisions:
    """Tests that out-of-scope non-DWH queries return empty candidate lists in retrieve_candidate_metrics."""

    @pytest.mark.parametrize("query", [
        "3 mũ 2",
        "thủ tục làm sổ đỏ",
        "hướng dẫn đăng ký kết hôn",
        "cách làm hộ chiếu online",
        "thời tiết thành phố Đà Lạt hôm nay",
        "xin chào trợ lý ảo",
        "tính 15 nhân 20",
        "đăng ký khai sinh cho con",
        "thủ tục cấp đổi bằng lái xe",
        "hướng dẫn làm thẻ căn cước",
        "giải phương trình bậc 2",
        "2^10",
        "100 chia cho 5",
        "căn bậc 2 của 64",
    ])
    def test_retrieve_candidate_metrics_empty(self, catalog, query):
        res = catalog.retrieve_candidate_metrics(query)
        assert res == [], f"Expected empty candidate list for out-of-scope query '{query}', got: {res}"


class TestOutOfScopeE2EExecutionGuard:
    """Verifies that out-of-scope queries return is_out_of_scope = True with no SQL generated."""

    @pytest.mark.parametrize("query", [
        "3 mũ 2",
        "thủ tục làm sổ đỏ",
        "hướng dẫn đăng ký kết hôn",
        "thời tiết thành phố Đà Lạt hôm nay thế nào ?",
        "tính 10 mũ 3",
        "giải phương trình bậc 2",
        "12 nhân 15",
        "căn bậc 2 của 16",
        "2^8",
        "thủ tục làm hộ chiếu trực tuyến",
    ])
    def test_e2e_oos_execution_guard(self, query):
        session_id = f"test_oos_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(
            query=query,
            session_id=session_id,
            user_context={"role_level": 0, "tenant_code": "68"}
        )
        assert res.get("is_out_of_scope") is True, (
            f"Query '{query}' expected is_out_of_scope=True, got: {res.get('is_out_of_scope')}"
        )
        sql = res.get("sql")
        assert sql is None or sql == "", (
            f"Query '{query}' generated SQL unexpectedly: {sql}"
        )
        final_answer = res.get("final_answer", "")
        # Must not claim that criteria lacks data in 2026
        assert "chưa có bản ghi số liệu được phê duyệt" not in final_answer, (
            f"Query '{query}' produced misleading answer: {final_answer}"
        )


class TestDatePreservationNonMath:
    """Verifies that date-bearing queries are NOT falsely flagged as math division or out-of-scope."""

    @pytest.mark.parametrize("query,expected_not_oos", [
        ("cho tôi biết số liệu chăn nuôi của liên hiệp hợp tác xã ngày 30/4", True),
        ("tổng số lượng htx ngày 30/4/2026", True),
        ("số lượng hợp tác xã ngày 15/08/2025", True),
        ("diện tích muối ngày 01/01/2026", True),
        ("sản lượng muối 30/06/2026", True),
        ("chỉ tiêu trồng trọt đến 31/12/2024", True),
    ])
    def test_date_not_falsely_flagged_as_math(self, query, expected_not_oos):
        session_id = f"test_date_{uuid.uuid4().hex[:8]}"
        res = warehouse_agent.run(
            query=query,
            session_id=session_id,
            user_context={"role_level": 0, "tenant_code": "68"}
        )
        assert res.get("is_out_of_scope") is not True, (
            f"Query '{query}' was falsely flagged as out of scope! Result: {res.get('final_answer')}"
        )
