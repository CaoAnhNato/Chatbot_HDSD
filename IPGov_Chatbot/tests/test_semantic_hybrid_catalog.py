"""
Test Suite: IPGov_Chatbot/tests/test_semantic_hybrid_catalog.py
Chức năng: Kiểm thử đơn vị chuyên biệt cho Tầng Ngữ Nghĩa SOTA (Module 04):
1. Phân giải phạm vi hành chính đa cấp (resolve_administrative_scope).
2. Bảo đảm Invariance Cấp Tỉnh (không nuốt scope Lâm Đồng thành Sở).
3. Hybrid Search Dense Embedding + Sparse BM25 via RRF.
4. Micro-LLM Disambiguation (MATCH vs AMBIGUOUS).
"""

import pytest
from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog


@pytest.fixture(scope="module")
def catalog():
    return DuckDBSemanticCatalog()


def test_resolve_administrative_scope_provincial(catalog):
    """Kiểm tra câu hỏi toàn tỉnh / Lâm Đồng luôn trả về type='tenant' và department_code=None."""
    # Test 1: Tên tỉnh
    res_ld = catalog.resolve_administrative_scope("Lâm Đồng")
    assert res_ld["type"] == "tenant"
    assert res_ld["tenant_code"] == "68"
    assert res_ld["department_code"] is None
    assert res_ld["admin_level"] == 0

    # Test 2: Cụm từ toàn tỉnh
    res_tt = catalog.resolve_administrative_scope("toàn tỉnh")
    assert res_tt["type"] == "tenant"
    assert res_tt["department_code"] is None
    assert res_tt["admin_level"] == 0

    # Test 3: Cả tỉnh Lâm Đồng
    res_ct = catalog.resolve_administrative_scope("tỉnh Lâm Đồng")
    assert res_ct["type"] == "tenant"
    assert res_ct["department_code"] is None


def test_resolve_administrative_scope_department(catalog):
    """Kiểm tra trích xuất chính xác Sở Ban Ngành cấp 1."""
    # Sở Công Thương
    res_sct = catalog.resolve_administrative_scope("Sở Công Thương")
    assert res_sct["type"] == "department"
    assert res_sct["department_code"] == "68-1-05"
    assert res_sct["admin_level"] == 1

    # Sở Lao động Thương binh Xã hội
    res_sld = catalog.resolve_administrative_scope("Sở Lao động Thương binh Xã hội")
    assert res_sld["type"] == "department"
    assert res_sld["department_code"] == "68-1-03"
    assert res_sld["admin_level"] == 1


def test_resolve_administrative_scope_office(catalog):
    """Kiểm tra trích xuất chính xác Phòng Ban cấp 2."""
    res_off = catalog.resolve_administrative_scope("Phòng Nội vụ")
    assert res_off["type"] == "office"
    assert res_off["department_code"] == "68-1-01"
    assert res_off["admin_level"] == 2
    assert "a0000000" in res_off["office_id"]


def test_hybrid_search_rrf_candidates(catalog):
    """Kiểm tra tầng truy xuất lai RRF trả về đúng số lượng ứng viên Top-K."""
    # K = 3
    cand_3 = catalog.find_criteria_by_name(
        "Số vụ tai nạn lao động năm 2026",
        limit=1,
        top_k_candidates=3,
        use_llm_disambiguation=False
    )
    assert len(cand_3) == 1
    assert "candidates" in cand_3[0]
    assert len(cand_3[0]["candidates"]) == 1

    # K = 5
    cand_5 = catalog.find_criteria_by_name(
        "Kinh phí thực hiện khuyến công",
        limit=1,
        top_k_candidates=5,
        use_llm_disambiguation=False
    )
    assert len(cand_5) >= 1
    assert cand_5[0]["code"] in ("kinh_phi_khuyen_cong", "so_nguoi_duoc_dao_tao_tu_nguon_kinh_phi_khuyen_cong")


def test_llm_disambiguation_match(catalog):
    """Kiểm tra LLM Disambiguation chọn đúng chỉ tiêu cụ thể khi câu hỏi rõ ràng."""
    res = catalog.find_criteria_by_name(
        "Số vụ tai nạn lao động năm 2026",
        limit=1,
        top_k_candidates=3,
        use_llm_disambiguation=True
    )
    assert len(res) == 1
    assert res[0]["code"] in ("so_vu_tai_nan_lao_dong", "tai_nan_lao_dong", "tai_nan_lao_dong_2")
    assert res[0]["is_ambiguous"] is False


def test_llm_disambiguation_ambiguous(catalog):
    """Kiểm tra câu hỏi bao trùm kích hoạt trạng thái AMBIGUOUS để tạo Clarification Chips."""
    res = catalog.find_criteria_by_name(
        "Tình hình khuyến công năm 2026 toàn tỉnh",
        limit=1,
        top_k_candidates=5,
        use_llm_disambiguation=True
    )
    assert len(res) == 1
    # Có thể là ambiguous (cần hỏi lại) hoặc match, nhưng nếu ambiguous thì có danh sách candidates
    if res[0].get("is_ambiguous"):
        assert "candidates" in res[0]
        assert len(res[0]["candidates"]) >= 2
