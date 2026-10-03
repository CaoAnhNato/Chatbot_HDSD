"""
Module: IPGov_Chatbot/tests/test_tenant_scoped_catalog.py
Chức năng: Kiểm thử độc lập cơ chế Tenant Scoping và Role Scoping tại Tầng Ngữ Nghĩa (Module 04).
Căn cứ: Kế hoạch kỹ thuật tenant_and_role_scoped_semantic_plan.md
"""

import pytest
from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog


@pytest.fixture(scope="module")
def catalog():
    return DuckDBSemanticCatalog()


def test_tenant_scoping_isolation_lam_dong(catalog):
    """
    Kiểm thử cô lập địa phương:
    Khi tenant_code='68' (Lâm Đồng), câu hỏi 'Tổng số người bị tai nạn lao động'
    BẮT BUỘC trả về mã tong_so_nguoi_bi_tai_nan_lao_dong_2 (có 34 dòng fact thực tế),
    tuyệt đối không được chọn mã tong_so_nguoi_bi_tai_nan_lao_dong của TP.HCM (tenant 79).
    """
    res = catalog.find_criteria_by_name(
        query="Tổng số người bị tai nạn lao động",
        limit=1,
        top_k_candidates=5,
        use_llm_disambiguation=True,
        tenant_code="68"
    )
    assert len(res) == 1, "Phải trả về kết quả phân giải"
    matched_code = res[0]["code"]
    assert matched_code == "tong_so_nguoi_bi_tai_nan_lao_dong_2", (
        f"Lâm Đồng phải match mã _2, nhưng lại nhận: {matched_code}"
    )


def test_tenant_scoping_isolation_hcm(catalog):
    """
    Kiểm thử cô lập địa phương:
    Khi tenant_code='79' (TP.HCM), câu hỏi 'Tổng số người bị tai nạn lao động'
    BẮT BUỘC trả về mã tong_so_nguoi_bi_tai_nan_lao_dong,
    tuyệt đối không được chọn mã _2 của Lâm Đồng (tenant 68).
    """
    res = catalog.find_criteria_by_name(
        query="Tổng số người bị tai nạn lao động",
        limit=1,
        top_k_candidates=5,
        use_llm_disambiguation=True,
        tenant_code="79"
    )
    assert len(res) == 1, "Phải trả về kết quả phân giải"
    matched_code = res[0]["code"]
    assert matched_code == "tong_so_nguoi_bi_tai_nan_lao_dong", (
        f"TP.HCM phải match mã gốc, nhưng lại nhận: {matched_code}"
    )


def test_failed_benchmark_cases_resolution_bm12(catalog):
    """Tái kiểm tra BM-12: Năm 2026 toàn tỉnh có bao nhiêu người bị thương tích khi làm việc?"""
    res = catalog.find_criteria_by_name(
        query="Năm 2026 toàn tỉnh có bao nhiêu người bị thương tích khi làm việc?",
        limit=1,
        top_k_candidates=5,
        use_llm_disambiguation=True,
        tenant_code="68"
    )
    assert len(res) == 1
    assert res[0]["code"] in ("tong_so_nguoi_bi_tai_nan_lao_dong_2", "so_nguoi_bi_tai_nan_lao_dong_2", "so_nguoi_bi_tnld")


def test_failed_benchmark_cases_resolution_bm17(catalog):
    """Tái kiểm tra BM-17: Thời gian công nhân phải nghỉ vì tai nạn lao động năm 2026"""
    res = catalog.find_criteria_by_name(
        query="Thời gian công nhân phải nghỉ vì tai nạn lao động năm 2026",
        limit=1,
        top_k_candidates=5,
        use_llm_disambiguation=True,
        tenant_code="68"
    )
    assert len(res) == 1
    assert res[0]["code"] == "so_ngay_cong_nghi_vi_tai_nan_lao_dong_2"


def test_failed_benchmark_cases_resolution_bm28(catalog):
    """Tái kiểm tra BM-28: Chi phí bồi thường và trợ cấp tai nạn lao động năm 2026 của toàn tỉnh"""
    res = catalog.find_criteria_by_name(
        query="Chi phí bồi thường và trợ cấp tai nạn lao động năm 2026 của toàn tỉnh",
        limit=1,
        top_k_candidates=5,
        use_llm_disambiguation=True,
        tenant_code="68"
    )
    assert len(res) == 1
    assert res[0]["code"] == "tong_chi_phi_tai_nan_lao_dong_2"


def test_failed_benchmark_cases_resolution_bm29(catalog):
    """Tái kiểm tra BM-29: Số người bị nạn nặng do tai nạn lao động năm 2026"""
    res = catalog.find_criteria_by_name(
        query="Số người bị nạn nặng do tai nạn lao động năm 2026",
        limit=1,
        top_k_candidates=5,
        use_llm_disambiguation=True,
        tenant_code="68"
    )
    assert len(res) == 1
    assert res[0]["code"] in ("tong_so_nguoi_bi_tai_nan_lao_dong_2", "so_nguoi_bi_tai_nan_lao_dong_2", "so_nguoi_bi_tnld")
