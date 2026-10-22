"""
Bộ Kiểm Thử Toàn Diện Đặc Tả Nghiệp Vụ REQ-Q01 -> REQ-Q04 & SC-1.1 -> SC-4.2 (output.md).
Thực thi trực tiếp trên CSDL PostgreSQL thật `vna_wom_dev` (Zero Blind Mocking).
Bao gồm kiểm thử Invariance (INV), Directional (DIR), Out-of-Distribution (OOD) và kiểm định cấu trúc Pop-up Tree Modal.
"""

import pytest
from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import warehouse_agent


def test_req_q01_and_sc_1_1_half_year_and_tree_modal():
    """
    REQ-Q01 & SC-1.1:
    - 'Số lượng chỉ tiêu thu thập được trong nửa đầu năm 2026 là bao nhiêu?'
    - Phải chuẩn hóa về 2026-01-01 .. 2026-06-30.
    - Chỉ trả về DUY NHẤT 1 bảng Cấp 1 gồm 9 dòng với đúng 6 cột chuẩn mục 2.1.C của output.md:
      STT | Tên chỉ tiêu Cấp 1 | Loại cấu trúc | Giá trị mới nhất | Đơn vị thực hiện | Nhiệm vụ trọng tâm
    """
    res = warehouse_agent.run("Số lượng chỉ tiêu thu thập được trong nửa đầu năm 2026 là bao nhiêu?")
    ans = res["answer"]
    sql = res.get("sql") or ""
    tbl = res.get("tabular_data") or {}

    assert "2026-01-01" in sql and "2026-06-30" in sql
    assert "9 chỉ tiêu Cấp 1 / 114 bản ghi" in ans
    assert "- Xem chi tiết các chỉ tiêu con" in ans
    assert "Chỉ tiêu đơn (Cấp 1)" in ans
    assert ans.count("| STT |") == 1, "REQ-Q01 must emit exactly 1 Markdown table, never 2 tables"
    col_labels = [c["label"] for c in tbl.get("columns", [])]
    assert col_labels == [
        "STT",
        "Tên chỉ tiêu Cấp 1",
        "Loại cấu trúc",
        "Giá trị mới nhất",
        "Chỉ tiêu con",
        "Đơn vị thực hiện",
        "Nhiệm vụ trọng tâm",
    ]
    assert len(tbl.get("rows", [])) == 9
    assert len(tbl.get("level1_rows", [])) == 9
    assert tbl.get("raw_fact_count") == 114
    assert isinstance(tbl.get("tree_modal"), dict) and len(tbl["tree_modal"]) >= 2


def test_sc_1_2_empty_period_honest_refusal():
    """
    SC-1.2:
    - Hỏi kỳ thời gian không có bản ghi phê duyệt (tháng 2 năm 2026).
    - Báo rõ chưa ghi nhận bản ghi chỉ tiêu được phê duyệt trong kỳ và gợi ý tra cứu năm 2026.
    """
    res = warehouse_agent.run("Các chỉ tiêu thu thập trong tháng 2 năm 2026 là gì?")
    ans = res["answer"]
    assert "tháng 02/2026" in ans
    assert "chưa ghi nhận" in ans.lower() or "không tìm thấy chỉ tiêu nào phát sinh số liệu" in ans.lower()
    assert "2026" in ans


def test_req_q02_single_leaf_criterion_with_month():
    """
    REQ-Q02:
    - Hỏi 1 chỉ tiêu lá đơn nhất có số liệu trong kỳ ('Diện tích muối công nghiệp trong tháng 6 năm 2026').
    - Trả về đúng 5 trường chuẩn và giá trị 520 ngày 30/06/2026 trên CSDL vna_wom_dev.
    """
    res = warehouse_agent.run("Cho tôi xem số liệu chỉ tiêu Diện tích muối công nghiệp trong tháng 6 năm 2026?")
    ans = res["answer"]
    assert "Diện tích muối sản xuất công nghiệp" in ans
    assert "- **Giá trị:** 520" in ans
    assert "- **Đơn vị thực hiện:**" in ans and "Chi cục" in ans
    assert "- **Nhiệm vụ trọng tâm:** Diêm nghiệp" in ans
    assert "- **Thời điểm báo cáo:** 30/06/2026" in ans


def test_sc_2_1_duplicate_leaf_across_multiple_parents():
    """
    SC-2.1:
    - Hỏi chỉ tiêu con trùng tên ở nhiều nhóm cha ('Cho tôi xem số liệu chỉ tiêu Thành lập mới năm 2026?').
    - Hiển thị đầy đủ bảng đối chiếu 4 nhánh cha (HTX nông nghiệp: 3, Liên hiệp HTX nông nghiệp: 0, Tổ hợp tác nông nghiệp: 15, Trang trại: 5).
    """
    res = warehouse_agent.run("Cho tôi xem số liệu chỉ tiêu Thành lập mới năm 2026?")
    ans = res["answer"]
    tbl = res.get("tabular_data") or {}
    assert "Nhóm chỉ tiêu (Cấp)" in ans
    assert "HTX nông nghiệp *(Cấp 1)*" in ans
    assert "Liên hiệp HTX nông nghiệp *(Cấp 1)*" in ans
    assert "Tổ hợp tác nông nghiệp *(Cấp 1)*" in ans
    assert "Trang trại *(Cấp 1)*" in ans
    assert "| **3** |" in ans and "| **0** |" in ans and "| **15** |" in ans and "| **5** |" in ans
    assert len(tbl.get("multi_parent_rows", [])) == 4


def test_sc_2_2_left_to_right_date_matching():
    """
    SC-2.2:
    - Hỏi ngày cụ thể ('Số liệu chỉ tiêu Diện tích muối thủ công ngày 15/06/2026 là bao nhiêu?').
    - Khớp trái-qua-phải trong cùng tháng 06/2026 -> chọn bản ghi ngày 30/06/2026 (giá trị 1,000) kèm ghi chú.
    """
    res = warehouse_agent.run("Số liệu chỉ tiêu Diện tích muối thủ công ngày 15/06/2026 là bao nhiêu?")
    ans = res["answer"]
    sql = res.get("sql") or ""
    assert "2026-06-15" in sql
    assert "Diện tích muối sản xuất thủ công" in ans
    assert "1,000" in ans or "1.000" in ans
    assert "30/06/2026" in ans
    assert "15/06/2026" in ans


def test_sc_2_3_leaf_criterion_with_dash_value():
    """
    SC-2.3:
    - Hỏi chỉ tiêu lá chưa có giá trị phê duyệt ('Cho tôi biết số liệu chỉ tiêu Liên kết sản xuất năm 2026?').
    - Không được báo lỗi hoặc trả về rỗng; phải hiển thị 'Chưa có số liệu phê duyệt (-)'.
    """
    res = warehouse_agent.run("Cho tôi biết số liệu chỉ tiêu Liên kết sản xuất năm 2026?")
    ans = res["answer"]
    assert "Liên kết sản xuất" in ans
    assert "Chưa có số liệu phê duyệt (-)" in ans


def test_sc_2_4_parent_criterion_disambiguation_with_child_chips():
    """
    SC-2.4 (SC-2.4a & SC-2.4b):
    - SC-2.4a (Chỉ tiêu cha CÓ số liệu, VD: 'Tổng số lượng chủ thể sản phẩm OCOP trong năm' = 17, 'Tổng diện tích sản xuất muối' = 0):
      Hiển thị Thẻ 5 Trường Chuẩn + bảng 1 dòng + các chips gợi ý chỉ tiêu con.
    - SC-2.4b (Chỉ tiêu cha KHÔNG có số liệu, VD: 'Chương trình OCOP', 'HTX nông nghiệp'):
      Hiển thị thông báo chỉ tiêu cha không có số liệu tổng hợp riêng lẻ (tabular_data = None) + các chips gợi ý chỉ tiêu con.
    """
    res_ocop = warehouse_agent.run("Tổng số lượng chủ thể sản phẩm OCOP trong năm là bao nhiêu?")
    ans_ocop = res_ocop["answer"]
    chips_ocop = res_ocop.get("chips") or []
    assert "- **Chỉ tiêu:** Tổng số lượng chủ thể sản phẩm OCOP trong năm" in ans_ocop
    assert "- **Giá trị:** 17" in ans_ocop
    assert "- **Thời điểm báo cáo:** 30/09/2026" in ans_ocop
    assert res_ocop.get("tabular_data") is not None
    assert len(chips_ocop) >= 3

    res_muoi = warehouse_agent.run("Cho tôi xem số liệu chỉ tiêu Diện tích sản xuất muối năm 2026?")
    ans_muoi = res_muoi["answer"]
    chips_muoi = res_muoi.get("chips") or []
    chip_labels = " ".join(c.get("label", "") for c in chips_muoi)
    assert "- **Chỉ tiêu:** Tổng diện tích sản xuất muối" in ans_muoi
    assert "- **Giá trị:** 0" in ans_muoi
    assert res_muoi.get("tabular_data") is not None
    assert "Diện tích muối sản xuất thủ công" in chip_labels
    assert "Diện tích muối sản xuất công nghiệp" in chip_labels
    assert len(chips_muoi) >= 2

    res_empty_parent = warehouse_agent.run("Cho tôi xem số liệu chỉ tiêu Chương trình OCOP năm 2026?")
    ans_empty = res_empty_parent["answer"]
    chips_empty = res_empty_parent.get("chips") or []
    assert "chỉ tiêu cha (nhóm chỉ tiêu) nên không có số liệu tổng hợp riêng lẻ" in ans_empty.replace("**", "").lower()
    assert "- **Chỉ tiêu:**" not in ans_empty
    assert res_empty_parent.get("tabular_data") is None
    assert len(chips_empty) >= 2


def test_req_q03_and_sc_3_1_missions_by_scope_and_time():
    """
    REQ-Q03 & SC-3.1:
    - 'Lĩnh vực Nông nghiệp trong tháng 6 năm 2026 đang có các nhiệm vụ nào?'
    - Trả về bảng 5 cột (STT, Mã nhiệm vụ, Tên nhiệm vụ, Lĩnh vực, Đơn vị phụ trách) gồm Diêm nghiệp và Phát triển nông thôn.
    """
    res = warehouse_agent.run("Lĩnh vực Nông nghiệp trong tháng 6 năm 2026 đang có các nhiệm vụ nào?")
    ans = res["answer"]
    tbl = res.get("tabular_data") or {}
    assert "Mã nhiệm vụ" in ans and "Lĩnh vực" in ans and "Đơn vị phụ trách" in ans
    assert "Diêm nghiệp" in ans and "Phát triển nông thôn" in ans
    assert "NV_DN_01" in ans and "NV_PTNT_02" in ans
    assert len(tbl.get("rows", [])) == 2


def test_sc_3_2_non_existent_scope_refusal_with_chips():
    """
    SC-3.2 (OOD / Out-of-Scope):
    - Hỏi lĩnh vực không có trong DB ('Lĩnh vực Hàng không vũ trụ hiện tại đang có các nhiệm vụ nào?').
    - Báo rõ không có lĩnh vực 'Hàng không vũ trụ' và gợi ý 2 lĩnh vực hiện có ('Nông nghiệp', 'lĩnh vực 1').
    """
    res = warehouse_agent.run("Lĩnh vực Hàng không vũ trụ hiện tại đang có các nhiệm vụ nào?")
    ans = res["answer"]
    chips = res.get("chips") or []
    assert "không có lĩnh vực 'hàng không vũ trụ'" in ans.lower()
    assert "nông nghiệp" in ans.lower() and "lĩnh vực 1" in ans.lower()
    assert len(chips) >= 2


def test_req_q04_and_sc_4_1_mission_level1_criteria_and_tree_modal():
    """
    REQ-Q04 & SC-4.1:
    - 'Nhiệm vụ Diêm nghiệp năm 2026 bao gồm các chỉ tiêu gốc Cấp 1 nào?'
    - Chỉ liệt kê 3 chỉ tiêu gốc Cấp 1 của nhiệm vụ Diêm nghiệp ('Tổng diện tích sản xuất muối', 'Tổng hộ sản xuất muối', 'Tổng sản lượng muối');
      các nhóm cha hiển thị '- (Xem chi tiết con)' kèm tree_modal.
    """
    res = warehouse_agent.run("Nhiệm vụ Diêm nghiệp năm 2026 bao gồm các chỉ tiêu gốc Cấp 1 nào?")
    ans = res["answer"]
    tbl = res.get("tabular_data") or {}
    assert "Tên chỉ tiêu Cấp 1" in ans
    assert "Loại cấu trúc Cấp 1" in ans
    assert "Tổng diện tích sản xuất muối" in ans
    assert "Tổng sản lượng muối" in ans
    assert "Tổng hộ sản xuất muối" in ans
    assert "- Xem chi tiết các chỉ tiêu con" in ans
    assert len(tbl.get("rows", [])) == 3
    assert isinstance(tbl.get("tree_modal"), dict) and len(tbl["tree_modal"]) >= 2


def test_sc_4_2_mission_without_approved_criteria_rows():
    """
    SC-4.2:
    - Hỏi nhiệm vụ có trong danh mục dwh_internal.mission nhưng chưa có chỉ tiêu báo cáo phê duyệt ('Nhiệm vụ Cải cách hành chính năm 2026 có các chỉ tiêu nào?').
    - Phản hồi rõ đã có trong danh mục nhiệm vụ nhưng chưa phát sinh bản ghi chỉ tiêu báo cáo nào được phê duyệt.
    """
    res = warehouse_agent.run("Nhiệm vụ Cải cách hành chính năm 2026 có các chỉ tiêu nào?")
    ans = res["answer"]
    assert "Cải cách hành chính" in ans
    assert "chưa phát sinh bản ghi chỉ tiêu báo cáo nào được phê duyệt" in ans


def test_checklist_invariance_and_directional_mission_hierarchy():
    """
    CheckList Behavioral Test (INV + DIR):
    - INV (Hoán vị thực thể nhiệm vụ & từ đệm công vụ): Đổi 'Diêm nghiệp' -> 'Phát triển nông thôn' kèm từ đệm 'Kính gửi chatbot, vui lòng thống kê giúp'.
      Cấu trúc bảng 6 cột Cấp 1 giữ nguyên, trả về đúng 6 gốc Cấp 1 của Phát triển nông thôn.
    - DIR (Bổ sung điều kiện lọc thời gian): Khi lọc thêm 'trong tháng 5 năm 2026', câu SQL bắt buộc có điều kiện lọc tháng 5.
    """
    res_inv = warehouse_agent.run("Kính gửi chatbot, vui lòng thống kê giúp nhiệm vụ Phát triển nông thôn năm 2026 có các chỉ tiêu Cấp 1 nào?")
    tbl_inv = res_inv.get("tabular_data") or {}
    assert len(tbl_inv.get("rows", [])) == 6
    assert "Chương trình OCOP" in res_inv["answer"]
    assert "- Xem chi tiết các chỉ tiêu con" in res_inv["answer"]

    res_dir = warehouse_agent.run("Nhiệm vụ Diêm nghiệp trong tháng 5 năm 2026 có các chỉ tiêu nào?")
    sql_dir = res_dir.get("sql") or ""
    assert "EXTRACT(MONTH FROM" in sql_dir and "= 5" in sql_dir


def test_req_q04_diverse_synonyms_and_structural_expressions_tieu_chi_cap_1():
    """
    REQ-Q04 Robustness & Anti-Overfitting (Case 2):
    Verify that diverse synonyms ('tiêu chí cấp 1', 'chỉ tiêu cấp đầu', 'tiêu chí bậc 1', 'nhóm tiêu chí gốc')
    correctly route to DIMENSION_LISTING (Level 1 criteria table for the target mission),
    and NEVER route to METADATA_EXPLORATION (which mistakenly lists missions).
    """
    # Variant 1: "các tiêu chí cấp 1 của nhiệm vụ phát triển nông thôn" (exact user failing query)
    res1 = warehouse_agent.run("các tiêu chí cấp 1 của nhiệm vụ phát triển nông thôn")
    tbl1 = res1.get("tabular_data") or {}
    assert res1.get("intent") != "METADATA_EXPLORATION", (
        f"Query routed incorrectly to METADATA_EXPLORATION (mission listing)! res: {res1.get('intent')}"
    )
    assert len(tbl1.get("rows", [])) == 6, (
        f"Expected 6 Level-1 criteria for 'Phát triển nông thôn', got {len(tbl1.get('rows', []))}. "
        f"Answer: {res1.get('answer')[:150]}"
    )
    assert "Tên chỉ tiêu Cấp 1" in res1["answer"]
    assert "Chương trình OCOP" in res1["answer"]

    # Variant 2: "Danh sách các chỉ tiêu cấp đầu hiện có trong nhiệm vụ phát triển nông thôn là gì ?"
    res2 = warehouse_agent.run("Danh sách các chỉ tiêu cấp đầu hiện có trong nhiệm vụ phát triển nông thôn là gì ?")
    tbl2 = res2.get("tabular_data") or {}
    assert len(tbl2.get("rows", [])) == 6
    assert "HTX nông nghiệp" in res2["answer"]

    # Variant 3: "Nhiệm vụ Diêm nghiệp có những tiêu chí bậc 1 nào ?"
    res3 = warehouse_agent.run("Nhiệm vụ Diêm nghiệp có những tiêu chí bậc 1 nào ?")
    tbl3 = res3.get("tabular_data") or {}
    assert len(tbl3.get("rows", [])) == 3
    assert "Tổng diện tích sản xuất muối" in res3["answer"]


def test_multi_turn_bidirectional_parent_to_duplicate_leaf_isolation():
    """
    Multi-Turn Bidirectional Test (Case 1 on Live DB):
    Turn 1: Ask parent criterion 'Trang trại' (SC-2.4).
    Turn 2 (SAME session): Ask independent duplicate leaf query 'Chỉ tiêu trồng trọt hiện đạt bao nhiêu?' (SC-2.1).
    MUST return all 4 branches without leaking Turn 1's parent context!
    """
    res1 = warehouse_agent.run("Cho tôi xem số liệu chỉ tiêu Trang trại năm 2026?")
    ans1 = res1.get("answer", "")
    assert "chỉ tiêu cha" in ans1.lower()

    history = [
        {"role": "user", "content": "Cho tôi xem số liệu chỉ tiêu Trang trại năm 2026?"},
        {"role": "assistant", "content": ans1},
    ]
    res2 = warehouse_agent.run("Chỉ tiêu trồng trọt hiện đạt bao nhiêu?", history=history)
    tbl2 = res2.get("tabular_data") or {}
    assert len(tbl2.get("multi_parent_rows", [])) == 4, (
        f"Leaked parent context from Turn 1! Got {len(tbl2.get('multi_parent_rows', []))} rows instead of 4."
    )


def test_regression_capability_inquiry_ban_co_the_giup_gi_toi():
    """
    Kiểm thử hồi quy bắt buộc:
    - 'Bạn có thể giúp gì tôi ?' phải nhận diện là CAPABILITY_INTRO (giới thiệu năng lực hệ thống),
      tuyệt đối không nhầm thành lời chào tạm biệt (GREETING_FAREWELL).
    """
    res = warehouse_agent.run("Bạn có thể giúp gì tôi ?")
    ans = res["answer"]
    assert "trợ lý ai tra cứu kho dữ liệu" in ans.lower() or "hỗ trợ anh/chị" in ans.lower()
    assert "4 lĩnh vực trọng tâm" in ans.lower()
    assert "hẹn gặp lại" not in ans.lower()


def test_sc_1_1_office_mission_mapping_and_multi_quarter():
    """
    SC-1.1:
    - 'Liệt kê danh sách chỉ tiêu của Phòng nông nghiệp trong quý 2 và quý 3?'
    - Chuẩn hóa khoảng thời gian liên quý 2026-04-01 .. 2026-09-30.
    - Ánh xạ 'Phòng nông nghiệp' qua dwh_internal.office_mission -> trả về 9 chỉ tiêu Cấp 1 (114 bản ghi) kèm tree_modal.
    """
    res = warehouse_agent.run("Liệt kê danh sách chỉ tiêu của Phòng nông nghiệp trong quý 2 và quý 3?")
    ans = res["answer"]
    sql = res.get("sql") or ""
    tbl = res.get("tabular_data") or {}
    assert "2026-04-01" in sql and "2026-09-30" in sql
    assert "office_mission" in sql
    assert "9 chỉ tiêu Cấp 1 / 114 bản ghi" in ans
    assert len(tbl.get("rows", [])) == 9
    assert tbl.get("raw_fact_count") == 114


def test_req_q03_scope_mission_no_clarification_and_empty_period_sc_3_1():
    """
    REQ-Q03 & SC-3.1:
    - 'Lĩnh vực Nông nghiệp có những nhiệm vụ nào?' không bị chặn bởi Clarification Engine (HTX),
      trả về đầy đủ 2 nhiệm vụ thuộc lĩnh vực Nông nghiệp (Diêm nghiệp, Phát triển nông thôn).
    - 'Liệt kê các nhiệm vụ thuộc lĩnh vực Nông nghiệp có báo cáo trong tháng 2 năm 2026?'
      trả về thông báo trung thực chưa phát sinh báo cáo phê duyệt trong tháng 02/2026.
    """
    res_all = warehouse_agent.run("Lĩnh vực Nông nghiệp có những nhiệm vụ nào?")
    ans_all = res_all["answer"]
    tbl_all = res_all.get("tabular_data") or {}
    assert res_all.get("intent") != "CLARIFICATION_REQUIRED"
    assert "Diêm nghiệp" in ans_all and "Phát triển nông thôn" in ans_all
    assert len(tbl_all.get("rows", [])) == 2

    res_empty = warehouse_agent.run("Liệt kê các nhiệm vụ thuộc lĩnh vực Nông nghiệp có báo cáo trong tháng 2 năm 2026?")
    ans_empty = res_empty["answer"]
    assert "tháng 02/2026" in ans_empty
    assert "chưa phát sinh bản ghi báo cáo nhiệm vụ nào được phê duyệt" in ans_empty.lower()


def test_sc_2_1_tong_so_hien_co_duplicate_leaf():
    """
    SC-2.1:
    - 'Số liệu của chỉ tiêu Tổng số hiện có là bao nhiêu?'
    - Ánh xạ về chỉ tiêu lá trùng tên ở 4 nhánh cha ('Đang hoạt động') và trả về bảng đối chiếu 4 dòng.
    """
    res = warehouse_agent.run("Số liệu của chỉ tiêu Tổng số hiện có là bao nhiêu?")
    ans = res["answer"]
    tbl = res.get("tabular_data") or {}
    assert "Nhóm chỉ tiêu (Cấp)" in ans
    assert len(tbl.get("multi_parent_rows", [])) == 4


def test_sc_2_2_doanh_thu_htx_20_3_and_muoi_30_9_nonzero():
    """
    SC-2.2:
    - 'Số liệu chỉ tiêu doanh thu hợp tác xã ngày 20/3 là bao nhiêu?' -> khớp ngày 31/03/2026 (giá trị 1,300).
    - 'Cho tôi biết số liệu chỉ tiêu tổng hộ sản xuất muối vào ngày 30/9?' -> khớp bản ghi được phê duyệt mới nhất tính đến 30/09/2026 là 31/07/2026 (giá trị 0).
    - 'Cho tôi biết số liệu chỉ tiêu tổng hộ sản xuất muối trong tháng 6 năm 2026?' -> khớp bản ghi kỳ 30/06/2026 (giá trị 660).
    """
    res1 = warehouse_agent.run("Số liệu chỉ tiêu doanh thu hợp tác xã ngày 20/3 là bao nhiêu?")
    ans1 = res1["answer"]
    assert "Doanh thu bình quân trong năm của một hợp tác xã nông nghiệp" in ans1
    assert "- **Giá trị:** 1,300" in ans1 or "- **Giá trị:** 1.300" in ans1
    assert "31/03/2026" in ans1 and "20/03/2026" in ans1

    res2 = warehouse_agent.run("Cho tôi biết số liệu chỉ tiêu tổng hộ sản xuất muối vào ngày 30/9?")
    ans2 = res2["answer"]
    assert "Tổng hộ sản xuất muối" in ans2
    assert "- **Giá trị:** 0" in ans2
    assert "31/07/2026" in ans2 and "30/09/2026" in ans2

    res3 = warehouse_agent.run("Cho tôi biết số liệu chỉ tiêu tổng hộ sản xuất muối trong tháng 6 năm 2026?")
    ans3 = res3["answer"]
    assert "Tổng hộ sản xuất muối" in ans3
    assert "- **Giá trị:** 660" in ans3
    assert "30/06/2026" in ans3


def test_sc_2_4_general_all_16_parent_criteria():
    """
    Fix 1 (SC-2.4 Generalization — SC-2.4a & SC-2.4b):
    - Kiểm tra danh sách các nhóm chỉ tiêu cha Cấp 1 & Cấp 2 thực tế trong dwh_internal.criteria.
    - Nhóm cha KHÔNG có số liệu (SC-2.4b): giải thích là chỉ tiêu cha không có số liệu tổng hợp riêng lẻ, tabular_data is None + gợi ý chips con.
    - Nhóm cha CÓ số liệu (SC-2.4a): hiển thị Thẻ 5 Trường Chuẩn + tabular_data (1 dòng) + gợi ý chips con.
    """
    parent_without_val_queries = [
        ("Cho tôi xem số liệu chỉ tiêu Chương trình OCOP năm 2026?", "Chương trình OCOP"),
        ("Cho tôi xem số liệu chỉ tiêu Làng nghề năm 2026?", "Làng nghề"),
        ("Cho tôi xem số liệu chỉ tiêu HTX nông nghiệp năm 2026?", "HTX nông nghiệp"),
        ("Cho tôi xem số liệu chỉ tiêu Liên hiệp HTX nông nghiệp năm 2026?", "Liên hiệp HTX nông nghiệp"),
        ("Cho tôi xem số liệu chỉ tiêu Tổ hợp tác nông nghiệp năm 2026?", "Tổ hợp tác nông nghiệp"),
        ("Cho tôi xem số liệu chỉ tiêu Trang trại năm 2026?", "Trang trại"),
    ]
    for q, expected_name in parent_without_val_queries:
        res = warehouse_agent.run(q)
        ans = res["answer"]
        chips = res.get("chips") or []
        assert res.get("intent") != "CLARIFICATION_REQUIRED", f"Parent query triggered clarification: {q}"
        assert expected_name.lower() in ans.lower(), f"Missing parent name {expected_name} in {q}"
        assert "chỉ tiêu cha (nhóm chỉ tiêu) nên không có số liệu tổng hợp riêng lẻ" in ans.replace("**", "").lower(), f"Missing SC-2.4b parent explanation in {q}"
        assert "- **Chỉ tiêu:**" not in ans, f"Unexpected 5-line header in SC-2.4b parent response for {q}"
        assert res.get("tabular_data") is None, f"tabular_data must be None for SC-2.4b parent query: {q}"
        assert len(chips) >= 1, f"Missing child chips for {q}"

    parent_with_val_queries = [
        ("Cho tôi xem số liệu chỉ tiêu Tổng số lượng chủ thể sản phẩm OCOP trong năm 2026?", "Tổng số lượng chủ thể sản phẩm OCOP trong năm", "17"),
        ("Cho tôi xem số liệu chỉ tiêu Lũy kế tổng số lượng sản phẩm OCOP đến thời điểm báo cáo năm 2026?", "sản phẩm OCOP đến thời điểm báo cáo", "197"),
        ("Cho tôi xem số liệu chỉ tiêu Tổng số lượng sản phẩm OCOP trong năm 2026?", "Tổng số lượng sản phẩm OCOP trong năm", "32"),
        ("Cho tôi xem số liệu chỉ tiêu Số lượng HTX phân theo lĩnh vực năm 2026?", "Số lượng HTX phân theo lĩnh vực", "138"),
        ("Cho tôi xem số liệu chỉ tiêu Hiệu quả hoạt động năm 2026?", "Hiệu quả hoạt động", None),
        ("Cho tôi xem số liệu chỉ tiêu Tổng diện tích sản xuất muối năm 2026?", "Tổng diện tích sản xuất muối", "0"),
        ("Cho tôi xem số liệu chỉ tiêu Tổng sản lượng muối năm 2026?", "Tổng sản lượng muối", "0"),
    ]
    for q, expected_name, expected_val in parent_with_val_queries:
        res = warehouse_agent.run(q)
        ans = res["answer"]
        chips = res.get("chips") or []
        assert res.get("intent") != "CLARIFICATION_REQUIRED", f"Parent query triggered clarification: {q}"
        assert expected_name.lower() in ans.lower(), f"Missing parent name {expected_name} in {q}"
        assert "- **Chỉ tiêu:**" in ans, f"Missing 5-Field Card header in SC-2.4a response for {q}"
        if expected_val is not None:
            assert f"- **Giá trị:** {expected_val}" in ans, f"Expected value {expected_val} for {q}, got:\n{ans}"
        assert res.get("tabular_data") is not None, f"tabular_data must be present for SC-2.4a parent query: {q}"
        assert len(chips) >= 1, f"Missing child chips for {q}"


def test_sc_2_1_general_all_17_duplicate_leaf_criteria():
    """
    Fix 2 (SC-2.1 Generalization):
    - Kiểm tra các chỉ tiêu lá trùng tên ở nhiều nhóm cha khác nhau thực tế trong dwh_internal.criteria
      (Thành viên, Đang hoạt động, Lâm nghiệp, Trồng trọt, Chăn nuôi, Thủy sản, Nước sạch NT, Nghề truyền thống...).
    - Hiển thị bảng đối chiếu đa nhóm cha gồm 6 cột chuẩn và gán tabular_data['rows'] = multi_rows.
    """
    dup_queries = [
        ("Cho tôi xem số liệu chỉ tiêu Thành viên năm 2026?", 4),
        ("Cho tôi xem số liệu chỉ tiêu Đang hoạt động năm 2026?", 4),
        ("Cho tôi xem số liệu chỉ tiêu Lâm nghiệp năm 2026?", 4),
        ("Cho tôi xem số liệu chỉ tiêu Trồng trọt năm 2026?", 4),
        ("Cho tôi xem số liệu chỉ tiêu Chăn nuôi năm 2026?", 4),
        ("Cho tôi xem số liệu chỉ tiêu Thủy sản năm 2026?", 3),
        ("Cho tôi xem số liệu chỉ tiêu Nước sạch NT năm 2026?", 3),
        ("Cho tôi xem số liệu chỉ tiêu Nghề truyền thống năm 2026?", 2),
    ]
    for q, expected_branches in dup_queries:
        res = warehouse_agent.run(q)
        ans = res["answer"]
        tbl = res.get("tabular_data") or {}
        assert res.get("intent") != "CLARIFICATION_REQUIRED", f"Duplicate leaf triggered clarification: {q}"
        assert "Nhóm chỉ tiêu (Cấp)" in ans, f"Missing multi-parent comparison table header for {q}"
        assert len(tbl.get("multi_parent_rows", [])) == expected_branches, f"Expected {expected_branches} branches for {q}"
        assert len(tbl.get("rows", [])) == expected_branches, f"tabular_data['rows'] not synced with multi_parent_rows for {q}"


def test_sc_2_3_and_req_q02_parent_disambiguated_dash_and_zero_leaves():
    """
    Fix 3 & Fix 4:
    - 'Cho tôi biết số liệu chỉ tiêu Liên kết sản xuất năm 2026?' -> giá trị '-' phải trả về 'Chưa có số liệu phê duyệt (-)'
      với đúng 5 trường chuẩn, không bị lỗi ép kiểu numeric.
    - 'Số liệu chỉ tiêu Liên kết sản xuất của Tổ hợp tác là bao nhiêu?' -> phân định nhánh Tổ hợp tác (lien_ket_san_xuat3) và trả về 'Chưa có số liệu phê duyệt (-)'.
    - 'Cho tôi xem số liệu chỉ tiêu Thành lập mới của Liên hiệp HTX nông nghiệp năm 2026?' -> bảo toàn giá trị hợp lệ '0' tại kỳ 30/09/2026.
    """
    res_dash = warehouse_agent.run("Cho tôi biết số liệu chỉ tiêu Liên kết sản xuất năm 2026?")
    ans_dash = res_dash["answer"]
    sql_dash = res_dash.get("sql") or ""
    assert "- **Chỉ tiêu:** Liên kết sản xuất" in ans_dash
    assert "- **Giá trị:** Chưa có số liệu phê duyệt (-)" in ans_dash
    assert "- **Đơn vị thực hiện:**" in ans_dash
    assert "- **Nhiệm vụ trọng tâm:** Phát triển nông thôn" in ans_dash
    assert "- **Thời điểm báo cáo:**" in ans_dash
    assert "CAST(NULLIF(TRIM(f.value), '') AS DECIMAL)" not in sql_dash

    res_dash_tht = warehouse_agent.run("Số liệu chỉ tiêu Liên kết sản xuất của Tổ hợp tác là bao nhiêu?")
    ans_dash_tht = res_dash_tht["answer"]
    sql_dash_tht = res_dash_tht.get("sql") or ""
    assert "lien_ket_san_xuat3" in sql_dash_tht
    assert "- **Chỉ tiêu:** Liên kết sản xuất" in ans_dash_tht
    assert "- **Giá trị:** Chưa có số liệu phê duyệt (-)" in ans_dash_tht

    res_zero = warehouse_agent.run("Cho tôi xem số liệu chỉ tiêu Thành lập mới của Liên hiệp HTX nông nghiệp năm 2026?")
    ans_zero = res_zero["answer"]
    assert "- **Chỉ tiêu:** Thành lập mới" in ans_zero
    assert "- **Giá trị:** 0" in ans_zero
    assert "- **Thời điểm báo cáo:** 30/09/2026" in ans_zero


def test_sc_2_1_no_single_leaf_preamble_and_multi_branch_sql():
    """
    Fix 3.2:
    - SC-2.1 không được chèn khối 5 gạch đầu dòng đơn lẻ ('- **Chỉ tiêu:** ... / - **Giá trị:** ...') phía trên bảng đối chiếu đa nhóm cha.
    - Câu SQL thực thi phải JOIN dwh_internal.criteria p và trả về đầy đủ các nhánh cha.
    """
    res = warehouse_agent.run("Cho tôi xem số liệu chỉ tiêu Thành lập mới năm 2026?")
    ans = res["answer"]
    sql = res.get("sql") or ""
    assert not ans.lstrip().startswith("- **Chỉ tiêu:**"), f"SC-2.1 must not start with single-leaf 5-bullet block: {ans[:200]}"
    assert "- **Thời điểm báo cáo:**" not in ans, f"SC-2.1 must not contain single-leaf 5-bullet block: {ans[:200]}"
    assert "LEFT JOIN dwh_internal.criteria AS p" in sql or "LEFT JOIN dwh_internal.criteria p" in sql
    assert "CAST(NULLIF(TRIM(f.value), '') AS DECIMAL)" not in sql


def test_req_q04_non_existent_mission_refusal_with_chips():
    """
    Fix 6 (REQ-Q04 vs SC-4.2):
    - Hỏi nhiệm vụ không tồn tại trong dwh_internal.mission ('Nhiệm vụ Phát triển du lịch vũ trụ năm 2026 có các chỉ tiêu nào?').
    - Báo rõ không có / không tồn tại nhiệm vụ được hỏi và gợi ý các nhiệm vụ hợp lệ (Diêm nghiệp, Phát triển nông thôn, Cải cách hành chính).
    """
    res = warehouse_agent.run("Nhiệm vụ Phát triển du lịch vũ trụ năm 2026 có các chỉ tiêu nào?")
    ans = res["answer"]
    chips = res.get("chips") or []
    assert "không có nhiệm vụ" in ans.lower() or "không tồn tại nhiệm vụ" in ans.lower()
    assert "phát triển du lịch vũ trụ" in ans.lower()
    assert "diêm nghiệp" in ans.lower() and "phát triển nông thôn" in ans.lower()
    assert len(chips) >= 2


def test_fix7_role_selector_bench_html_dynamic_tree_modal_and_table_renderer():
    """
    Fix 7 (Frontend role_selector_bench.html):
    - Không còn dữ liệu giả lập cứng ('default_salt', 'default_coop').
    - Có hàm renderMarkdownTableBlock, findMatchingTreeNode, và truyền tham số động vào openCriteriaTreeModal.
    - Có vùng cuộn max-h-[80vh] overflow-y-auto và sự kiện đóng modal qua nút X / vùng nền ngoài.
    - Bảo toàn khối <details><summary>...</summary>...</details> thu gọn SQL trên DOM.
    """
    from pathlib import Path
    html_path = Path(__file__).resolve().parents[1] / "frontend" / "role_selector_bench.html"
    content = html_path.read_text(encoding="utf-8")

    assert "default_salt" not in content
    assert "default_coop" not in content
    assert "window.__latestTreeModalData = {};" in content
    assert "renderMarkdownTableBlock" in content
    assert "findMatchingTreeNode" in content
    assert "openCriteriaTreeModal('${arg}')" in content
    assert ">- Xem chi tiết các chỉ tiêu con</button>" in content
    assert "max-h-[80vh] overflow-y-auto" in content
    assert 'id="criteria-tree-modal-backdrop"' in content
    assert 'id="criteria-tree-modal-close"' in content
    assert '<details class="mt-2 rounded-xl' in content


def test_rc_r2_02_provincial_inventory_not_hijacked_by_attribute_lookup():
    """
    RC-R2-02:
    - 'Tỉnh Lâm Đồng thu thập những chỉ tiêu nào?' phải định tuyến sang DIMENSION_LISTING (kiểm kê 9 chỉ tiêu Cấp 1 / 114 bản ghi),
      không bị resolve_attribute_lookup chặn thành ENTITY_ATTRIBUTE_LOOKUP 1 dòng.
    """
    res = warehouse_agent.run("Tỉnh Lâm Đồng thu thập những chỉ tiêu nào?")
    ans = res["answer"]
    tbl = res.get("tabular_data") or {}
    assert "9 chỉ tiêu Cấp 1 / 114 bản ghi" in ans
    assert len(tbl.get("rows", [])) == 9
    assert tbl.get("raw_fact_count") == 114


def test_rc_r2_03_department_name_not_hijacked_as_mission_and_lunar_months():
    """
    RC-R2-03:
    - 'Sở Nông nghiệp và Phát triển nông thôn trong tháng 6 năm 2026 có các chỉ tiêu nào?'
      không bị lọc nhầm sang mission_name ILIKE '%Phát triển nông thôn%' (phải bao gồm cả Diêm nghiệp và Phát triển nông thôn = 9 gốc Cấp 1 / 114 bản ghi).
    - Hỗ trợ 'tháng giêng' (tháng 1) và 'tháng chạp' (tháng 12).
    """
    res = warehouse_agent.run("Sở Nông nghiệp và Phát triển nông thôn trong tháng 6 năm 2026 có các chỉ tiêu nào?")
    ans = res["answer"]
    tbl = res.get("tabular_data") or {}
    assert "Diêm nghiệp" in ans and "Phát triển nông thôn" in ans
    assert len(tbl.get("rows", [])) == 9
    assert tbl.get("raw_fact_count") == 114

    res_gieng = warehouse_agent.run("Tháng giêng năm 2026 có những chỉ tiêu nào?")
    assert "EXTRACT(MONTH FROM" in (res_gieng.get("sql") or "") and "= 1" in (res_gieng.get("sql") or "")
    assert "tháng 01/2026" in res_gieng["answer"]

    res_chap = warehouse_agent.run("Tháng chạp năm 2026 có những chỉ tiêu nào?")
    assert "EXTRACT(MONTH FROM" in (res_chap.get("sql") or "") and "= 12" in (res_chap.get("sql") or "")
    assert "tháng 12/2026" in res_chap["answer"]


def test_rc_r2_04_thang_ba_specific_date_not_hijacked_by_position_ba():
    """
    RC-R2-04:
    - 'Số liệu chỉ tiêu diện tích muối công nghiệp vào ngày 10 tháng ba năm 2026 là bao nhiêu?'
      không bị 'ba' khớp nhầm vào chức vụ 'BA' (OFFICER_ASSIGNMENT), phải trích xuất specific_date='2026-03-10'
      và khớp mốc gần nhất 31/03/2026 (giá trị 520).
    """
    res = warehouse_agent.run("Số liệu chỉ tiêu diện tích muối công nghiệp vào ngày 10 tháng ba năm 2026 là bao nhiêu?")
    ans = res["answer"]
    assert "Diện tích muối sản xuất công nghiệp" in ans
    assert "520" in ans
    assert "31/03/2026" in ans and "10/03/2026" in ans


def test_rc_r2_05_htx_parent_group_not_hijacked_as_ward_or_clarification():
    """
    RC-R2-05:
    - 'Nhóm chỉ tiêu Lĩnh vực hoạt động của hợp tác xã có những chỉ tiêu nào?'
      không bị trích xuất nhầm 'xã có' làm xã/phường và không bật Clarification HTX sai.
      Vì 'Số lượng HTX phân theo lĩnh vực' có số liệu (138), hệ thống hiển thị Thẻ 5 Trường Chuẩn + bảng 1 dòng + chips chỉ tiêu con.
    """
    res = warehouse_agent.run("Nhóm chỉ tiêu Lĩnh vực hoạt động của hợp tác xã có những chỉ tiêu nào?")
    ans = res["answer"]
    chips = res.get("chips") or []
    assert res.get("intent") != "CLARIFICATION_REQUIRED"
    assert "Số lượng HTX phân theo lĩnh vực" in ans
    assert "- **Giá trị:** 138" in ans
    assert res.get("tabular_data") is not None
    assert len(chips) >= 6


def test_rc_r2_06_short_dash_leaves_and_leading_chi_tieu_strip():
    """
    RC-R2-06:
    - 'Số liệu chỉ tiêu tạm ngừng hoạt động năm 2026 là bao nhiêu?' -> trả về 5 gạch đầu dòng chuẩn với 'Chưa có số liệu phê duyệt (-)'.
    - 'Số liệu chỉ tiêu giải thể của hợp tác xã năm 2026 là bao nhiêu?' -> không bị Clarification HTX chặn, trả về 'Chưa có số liệu phê duyệt (-)'.
    """
    res1 = warehouse_agent.run("Số liệu chỉ tiêu tạm ngừng hoạt động năm 2026 là bao nhiêu?")
    ans1 = res1["answer"]
    assert "- **Chỉ tiêu:** Tạm ngừng hoạt động" in ans1
    assert "- **Giá trị:** Chưa có số liệu phê duyệt (-)" in ans1

    res2 = warehouse_agent.run("Số liệu chỉ tiêu giải thể của hợp tác xã năm 2026 là bao nhiêu?")
    ans2 = res2["answer"]
    assert res2.get("intent") != "CLARIFICATION_REQUIRED"
    assert "- **Chỉ tiêu:** Giải thể" in ans2
    assert "- **Giá trị:** Chưa có số liệu phê duyệt (-)" in ans2


def test_rc_r2_07_no_dummy_mission_and_no_raw_nbsp():
    """
    RC-R2-07:
    - Khi hỏi nhiệm vụ hoặc lĩnh vực không tồn tại, không hiển thị '&nbsp;' thô và không gợi ý nhiệm vụ rác 'nhiệm vụ 1'.
    """
    res_m = warehouse_agent.run("Nhiệm vụ Khai thác sao Hỏa năm 2026 có các chỉ tiêu nào?")
    ans_m = res_m["answer"]
    chips_m = res_m.get("chips") or []
    assert "&nbsp;" not in ans_m
    assert "nhiệm vụ 1" not in ans_m.lower()
    assert all("nhiệm vụ 1" not in (c.get("label") or "").lower() for c in chips_m)

    res_s = warehouse_agent.run("Lĩnh vực Hàng không vũ trụ hiện tại đang có các nhiệm vụ nào?")
    assert "&nbsp;" not in res_s["answer"]


def test_round3_audit_fixes_department_ptnt_and_multi_quarter_commas():
    """
    Kiểm thử bổ sung Round 3:
    1. 'các chỉ tiêu do Phòng Nông nghiệp và Phát triển nông thôn thực hiện' -> 9 gốc Cấp 1 / 114 bản ghi (không bị lọc nhầm sang nhiệm vụ Phát triển nông thôn 107 bản ghi).
    2. 'trong quý 2, 3 năm 2026 có các chỉ tiêu nào ?' -> chuẩn hóa 2026-04-01 .. 2026-09-30.
    3. 'cho tôi biết những chỉ tiêu nào được thu thập trong tháng 6' -> DIMENSION_LISTING, không bật Clarification.
    4. 'từ tháng chạp năm 2025 đến tháng giêng năm 2026 có các chỉ tiêu nào' -> chuẩn hóa liên năm 2025-12-01 .. 2026-01-31.
    """
    res_dept = warehouse_agent.run("các chỉ tiêu do Phòng Nông nghiệp và Phát triển nông thôn thực hiện")
    tbl_dept = res_dept.get("tabular_data") or {}
    assert len(tbl_dept.get("rows", [])) == 9
    assert tbl_dept.get("raw_fact_count") == 114

    res_q23 = warehouse_agent.run("trong quý 2, 3 năm 2026 có các chỉ tiêu nào ?")
    sql_q23 = res_q23.get("sql") or ""
    assert "2026-04-01" in sql_q23 and "2026-09-30" in sql_q23

    res_m6 = warehouse_agent.run("cho tôi biết những chỉ tiêu nào được thu thập trong tháng 6")
    assert res_m6.get("intent") != "CLARIFICATION_REQUIRED"
    assert "EXTRACT(MONTH FROM" in (res_m6.get("sql") or "") and "= 6" in (res_m6.get("sql") or "")

    f_lunar = warehouse_agent.normalizer.normalize_query("từ tháng chạp năm 2025 đến tháng giêng năm 2026 có các chỉ tiêu nào")
    assert f_lunar.date_from == "2025-12-01" and f_lunar.date_to == "2026-01-31"


def test_round3_audit_fixes_hierarchy_parents_and_unrecorded_leaves():
    """
    Kiểm thử bổ sung Round 3:
    1. 'Tổng hộ sản xuất muối là bao nhiêu?' -> khớp đúng 'Tổng hộ sản xuất muối' với ngày báo cáo mới nhất 31/07/2026 (giá trị 0), không bị 'Sản xuất muôi' (620) chiếm quyền và câu SQL tối giản chuẩn /ponytail.
    2. 'Số lượng HTX hiện nay là bao nhiêu?' -> khớp đúng nhóm cha 'Số lượng HTX phân theo lĩnh vực' theo chuẩn SC-2.4 (kèm các chips chỉ tiêu con).
    3. Phân biệt 2 nhánh cha trùng tên 'Hiệu quả hoạt động' của Trang trại (chips Số TT...) và HTX nông nghiệp (chips Số HTX...).
    4. 'Doanh thu bình quân trong năm của một hợp tác xã nông nghiệp là bao nhiêu?' -> trả về 4,100, không bật Clarification năm sai.
    5. 'Lợi nhuận bình quân của trang trại là bao nhiêu?' -> trả về 'Chưa có số liệu phê duyệt (-)'.
    """
    res_muoi = warehouse_agent.run("Tổng hộ sản xuất muối là bao nhiêu?")
    sql_muoi = res_muoi.get("sql") or ""
    assert "Tổng hộ sản xuất muối" in res_muoi["answer"]
    assert "- **Giá trị:** 0" in res_muoi["answer"]
    assert "31/07/2026" in res_muoi["answer"]
    assert "Diêm nghiệp" not in sql_muoi
    assert "AS gia_tri," not in sql_muoi
    assert "AS ngay_bao_cao," not in sql_muoi
    assert "LIMIT 500" not in sql_muoi
    assert "TRIM(f.name) ILIKE 'Tổng hộ sản xuất muối'" in sql_muoi

    res_htx = warehouse_agent.run("Số lượng HTX hiện nay là bao nhiêu?")
    assert "Số lượng HTX phân theo lĩnh vực" in res_htx["answer"]
    assert "- **Giá trị:** 138" in res_htx["answer"]
    assert len(res_htx.get("chips") or []) >= 6

    res_hq_tt = warehouse_agent.run("Hiệu quả hoạt động của trang trại là bao nhiêu?")
    chips_tt = " ".join(c.get("label", "") for c in (res_hq_tt.get("chips") or []))
    assert "Hiệu quả hoạt động" in res_hq_tt["answer"]
    assert "Số TT nông nghiệp hoạt động hiệu quả tốt" in chips_tt

    res_hq_htx = warehouse_agent.run("Hiệu quả hoạt động của HTX nông nghiệp là bao nhiêu?")
    chips_htx = " ".join(c.get("label", "") for c in (res_hq_htx.get("chips") or []))
    assert "Hiệu quả hoạt động" in res_hq_htx["answer"]
    assert "Số HTX nông nghiệp hoạt động hiệu quả tốt" in chips_htx

    res_dt = warehouse_agent.run("Doanh thu bình quân trong năm của một hợp tác xã nông nghiệp là bao nhiêu?")
    assert res_dt.get("intent") != "CLARIFICATION_REQUIRED"
    assert "4,100" in res_dt["answer"]

    res_ln = warehouse_agent.run("Lợi nhuận bình quân của trang trại là bao nhiêu?")
    assert "Lợi nhuận bình quân" in res_ln["answer"]
    assert "Chưa có số liệu phê duyệt (-)" in res_ln["answer"]


def test_round3_audit_fixes_unaccented_and_multiturn_session_isolation():
    """
    Kiểm thử bổ sung Round 3:
    1. Truy vấn không dấu tiếng Việt cho lĩnh vực ('cac nhiem vu thuoc linh vuc nong nghiep') và chỉ tiêu Cấp 1 ('hien thi cac chi tieu cap 1 cua nhiem vu phat trien nong thon').
    2. Hội thoại đa lượt với custom session_id chuyển từ phạm vi Phòng ban sang toàn tỉnh Lâm Đồng trả về đủ 9 gốc Cấp 1 / 114 bản ghi.
    """
    res_unacc_scope = warehouse_agent.run("cac nhiem vu thuoc linh vuc nong nghiep")
    assert "Diêm nghiệp" in res_unacc_scope["answer"] and "Phát triển nông thôn" in res_unacc_scope["answer"]

    res_unacc_l1 = warehouse_agent.run("hien thi cac chi tieu cap 1 cua nhiem vu phat trien nong thon")
    assert len((res_unacc_l1.get("tabular_data") or {}).get("rows", [])) == 6

    warehouse_agent.run("Các chỉ tiêu của Phòng nông nghiệp", session_id="sess_round3_mt_switch")
    res_mt_prov = warehouse_agent.run("Toàn tỉnh Lâm Đồng hiện có những chỉ tiêu nào?", session_id="sess_round3_mt_switch")
    tbl_mt = res_mt_prov.get("tabular_data") or {}
    assert len(tbl_mt.get("rows", [])) == 9
    assert tbl_mt.get("raw_fact_count") == 114


def test_chat_history_store_sqlite_persistence_and_docs_relocation(tmp_path):
    """
    Kiểm thử:
    1. File đặc tả output.md đã được di chuyển về IPGov_Chatbot/docs/output.md.
    2. ChatHistoryStore lưu trữ bền vững phiên chat, danh sách tin nhắn, tabular_data, đổi tên và xóa phiên.
    """
    from pathlib import Path
    from IPGov_Chatbot.core.chat_history_store import ChatHistoryStore

    docs_output = Path(__file__).resolve().parents[1] / "docs" / "output.md"
    assert docs_output.exists(), "output.md must reside in IPGov_Chatbot/docs/output.md"

    db_file = tmp_path / "test_chat_history.sqlite3"
    store = ChatHistoryStore(db_path=db_file)
    sid = "session-test-durable-001"
    store.save_turn(
        session_id=sid,
        user_prompt="[tenant_code=68, level=0] danh sách các chỉ tiêu từ đầu năm tới nay",
        assistant_answer="Dưới đây là danh sách các chỉ tiêu gốc (Cấp 1)",
        role="lamdong_leader",
        level=0,
        tenant_code="68",
        tabular_data={"columns": [{"key": "stt", "label": "STT"}], "rows": [{"stt": 1}]},
        quick_action_chips=[{"id": "c1", "label": "Diêm nghiệp", "query_text": "Diêm nghiệp"}],
    )

    sessions = store.list_sessions(limit=10)
    assert len(sessions) == 1
    assert sessions[0]["id"] == sid
    assert sessions[0]["title"] == "danh sách các chỉ tiêu từ đầu năm tới nay"
    assert len(sessions[0]["messages"]) == 2
    assert sessions[0]["messages"][1]["tabular_data"]["rows"] == [{"stt": 1}]

    assert store.rename_session(sid, "Báo cáo chỉ tiêu đầu năm 2026")
    assert store.list_sessions(limit=10)[0]["title"] == "Báo cáo chỉ tiêu đầu năm 2026"

    assert store.delete_session(sid)
    assert len(store.list_sessions(limit=10)) == 0


def test_sc_2_2_interval_distance_and_time_range_latest_report_date():
    """
    Kiểm thử toàn diện:
    1. 5 trường hợp biên của resolve_nearest_report_date theo thuật toán khoảng [A, B]:
       - Nhỏ hơn cận dưới (a < d_1 -> d_1)
       - Thuộc [A, B] gần A hơn (delta_A < delta_B -> A, VD: 23/04 trên [31/03, 30/06, 30/09] -> 31/03)
       - Thuộc [A, B] gần B hơn (delta_A > delta_B -> B, VD: 20/03 trên [13/03, 23/03, 25/03] -> 23/03)
       - Thuộc [A, B] cách đều 2 cận (delta_A == delta_B -> mặc định chọn cận trên B, VD: 18/03 trên [13/03, 23/03, 25/03] -> 23/03)
       - Lớn hơn cận trên (a > d_k -> d_k, VD: 29/03 trên [13/03, 23/03, 25/03] -> 25/03)
    2. Full pipeline ngày cụ thể: 'số lượng chỉ tiêu trang trại ngày 23/4' -> chọn ngày 31/03/2026 (giá trị 45).
    3. Full pipeline khoảng thời gian: 'số lượng chỉ tiêu trang trại trong nửa đầu năm nay' -> luôn lấy report_date mới nhất trong khoảng (30/06/2026) là 'Chưa có số liệu phê duyệt (-)' (NULL).
    4. Full pipeline chỉ tiêu cha SC-2.4: 'số lượng chỉ tiêu HTX nông nghiệp' -> khớp đúng văn bản output.md, không lặp bảng hay thẻ 5 dòng.
    """
    from IPGov_Chatbot.modules.mod03_router.canonical_normalizer import resolve_nearest_report_date

    dates_q = ["2026-03-31", "2026-06-30", "2026-09-30"]
    assert resolve_nearest_report_date(dates_q, "2026-01-15") == "2026-03-31"
    assert resolve_nearest_report_date(dates_q, "2026-04-23") == "2026-03-31"
    assert resolve_nearest_report_date(dates_q, "2026-06-10") == "2026-06-30"
    assert resolve_nearest_report_date(dates_q, "2026-11-15") == "2026-09-30"

    dates_m3 = ["2026-03-13", "2026-03-23", "2026-03-25"]
    assert resolve_nearest_report_date(dates_m3, "2026-03-01") == "2026-03-13"
    assert resolve_nearest_report_date(dates_m3, "2026-03-20") == "2026-03-23"
    assert resolve_nearest_report_date(dates_m3, "2026-03-18") == "2026-03-23"
    assert resolve_nearest_report_date(dates_m3, "2026-03-29") == "2026-03-25"

    res_spec = warehouse_agent.run("số lượng chỉ tiêu trang trại ngày 23/4")
    ans_spec = res_spec["answer"]
    assert "31/03/2026" in ans_spec and "23/04/2026" in ans_spec
    assert "Trang trại" in ans_spec
    assert len(res_spec.get("chips") or []) >= 2

    res_range = warehouse_agent.run("số lượng chỉ tiêu trang trại trong nửa đầu năm nay")
    ans_range = res_range["answer"]
    assert "Trang trại" in ans_range
    assert "30/06/2026" in ans_range
    assert len(res_range.get("chips") or []) >= 2

    res_dup_time = warehouse_agent.run("số lượng chỉ tiêu trồng trọt ngày 30/4")
    ans_dup_time = res_dup_time["answer"]
    tbl_dup_time = res_dup_time.get("tabular_data") or {}
    assert "Trồng trọt" in ans_dup_time
    assert "31/03/2026" in ans_dup_time and "30/04/2026" in ans_dup_time
    assert "Nhóm chỉ tiêu (Cấp)" in ans_dup_time
    assert len(tbl_dup_time.get("multi_parent_rows", [])) == 4

    res_parent = warehouse_agent.run("số lượng chỉ tiêu HTX nông nghiệp")
    ans_parent = res_parent["answer"]
    assert "Chỉ tiêu **'HTX nông nghiệp'** là một **chỉ tiêu cha (nhóm chỉ tiêu)** nên không có số liệu tổng hợp riêng lẻ." in ans_parent
    assert "- **Chỉ tiêu:**" not in ans_parent
    assert "| STT |" not in ans_parent
    assert res_parent.get("tabular_data") is None
    assert len(res_parent.get("chips") or []) >= 5


def test_req_q03_single_office_null_dash_and_sc_3_1_temporal_filters():
    """
    Kiểm thử toàn diện REQ-Q03 & SC-3.1:
    1. TC-Q03-01 (1 đơn vị phụ trách duy nhất):
       'lĩnh vực nông nghiệp hiện đang có những nhiệm vụ nào' -> Diêm nghiệp và Phát triển nông thôn chỉ hiển thị 'Chi cục'
       (tuyệt đối không còn 'Chi cục, Phòng nông nghiệp').
    2. TC-Q03-02 (Xử lý NULL thành '-'):
       'Lĩnh vực 1 hiện có những nhiệm vụ nào?' -> Cải cách hành chính hiển thị 'Phòng kinh tế',
       nhiệm vụ 2 và nhiệm vụ 3 (chưa gán đơn vị trong kho) hiển thị '-'.
    3. TC-Q03-03 (Lọc theo nửa đầu năm, quý 1, quý 2, từ đầu năm tới giờ, từ tháng 2 đến tháng 9, quý 4 rỗng):
       - 'Lĩnh vực nông nghiệp trong nửa đầu năm có những nhiệm vụ nào?' -> 2026-01-01..2026-06-30, 2 nhiệm vụ ('Chi cục').
       - 'Các nhiệm vụ thuộc lĩnh vực nông nghiệp trong quý 1?' -> 2026-01-01..2026-03-31, 2 nhiệm vụ.
       - 'Lĩnh vực nông nghiệp trong quý 2 có nhiệm vụ nào?' -> 2026-04-01..2026-06-30, 2 nhiệm vụ.
       - 'Từ đầu năm tới giờ lĩnh vực nông nghiệp có những nhiệm vụ nào?' -> 2026-01-01..2026-12-31, 2 nhiệm vụ.
       - 'Từ tháng 2 đến tháng 9 lĩnh vực nông nghiệp có những nhiệm vụ nào?' -> 2026-02-01..2026-09-30, 2 nhiệm vụ.
       - 'Trong quý 4 năm nay lĩnh vực nông nghiệp có nhiệm vụ nào không?' -> 2026-10-01..2026-12-31, thông báo chưa phát sinh báo cáo phê duyệt.
    """
    # 1. TC-Q03-01: 1 đơn vị phụ trách duy nhất
    res_nn = warehouse_agent.run("[tenant_code=68, level=0] lĩnh vực nông nghiệp hiện đang có những nhiệm vụ nào")
    ans_nn = res_nn["answer"]
    tbl_nn = res_nn.get("tabular_data") or {}
    assert "Chi cục, Phòng nông nghiệp" not in ans_nn
    assert len(tbl_nn.get("rows", [])) == 2
    for r in tbl_nn["rows"]:
        assert r["office_name"] == "Chi cục"

    # 2. TC-Q03-02: Xử lý NULL thành '-'
    res_lv1 = warehouse_agent.run("Lĩnh vực 1 hiện có những nhiệm vụ nào?")
    ans_lv1 = res_lv1["answer"]
    tbl_lv1 = res_lv1.get("tabular_data") or {}
    rows_by_name = {r["mission_name"]: r["office_name"] for r in tbl_lv1.get("rows", [])}
    assert rows_by_name.get("Cải cách hành chính") == "Phòng kinh tế"
    assert rows_by_name.get("nhiệm vụ 2") == "-"
    assert rows_by_name.get("nhiệm vụ 3") == "-"
    assert "Chưa phân công" not in ans_lv1 and "Cấp tỉnh" not in ans_lv1

    # 3. TC-Q03-03: Lọc nhiệm vụ theo mốc thời gian (SC-3.1)
    res_h1 = warehouse_agent.run("Lĩnh vực nông nghiệp trong nửa đầu năm có những nhiệm vụ nào?")
    sql_h1 = res_h1.get("sql") or ""
    assert "2026-01-01" in sql_h1 and "2026-06-30" in sql_h1
    assert "nửa đầu năm 2026" in res_h1["answer"]
    assert len((res_h1.get("tabular_data") or {}).get("rows", [])) == 2

    res_q1 = warehouse_agent.run("Các nhiệm vụ thuộc lĩnh vực nông nghiệp trong quý 1?")
    sql_q1 = res_q1.get("sql") or ""
    assert "2026-01-01" in sql_q1 and "2026-03-31" in sql_q1
    assert "Quý 1/2026" in res_q1["answer"]
    assert len((res_q1.get("tabular_data") or {}).get("rows", [])) == 2

    res_q2 = warehouse_agent.run("Lĩnh vực nông nghiệp trong quý 2 có nhiệm vụ nào?")
    sql_q2 = res_q2.get("sql") or ""
    assert "2026-04-01" in sql_q2 and "2026-06-30" in sql_q2
    assert "Quý 2/2026" in res_q2["answer"]
    assert len((res_q2.get("tabular_data") or {}).get("rows", [])) == 2

    res_ytd = warehouse_agent.run("Từ đầu năm tới giờ lĩnh vực nông nghiệp có những nhiệm vụ nào?")
    sql_ytd = res_ytd.get("sql") or ""
    assert "2026-01-01" in sql_ytd and "2026-12-31" in sql_ytd
    assert "đầu năm 2026 đến nay" in res_ytd["answer"]
    assert len((res_ytd.get("tabular_data") or {}).get("rows", [])) == 2

    res_m29 = warehouse_agent.run("Từ tháng 2 đến tháng 9 lĩnh vực nông nghiệp có những nhiệm vụ nào?")
    sql_m29 = res_m29.get("sql") or ""
    assert "2026-02-01" in sql_m29 and "2026-09-30" in sql_m29
    assert "01/02/2026 đến 30/09/2026" in res_m29["answer"]
    assert len((res_m29.get("tabular_data") or {}).get("rows", [])) == 2

    res_q4 = warehouse_agent.run("Trong quý 4 năm nay lĩnh vực nông nghiệp có nhiệm vụ nào không?")
    ans_q4 = res_q4["answer"]
    assert "Quý 4/2026" in ans_q4
    assert "chưa phát sinh bản ghi báo cáo nhiệm vụ nào được phê duyệt" in ans_q4.lower()


def test_task1_sc_4_1_quarter_3_label_and_sql():
    """
    Task 1: SC-4.1 với tham số Quý 3:
    'Trong quý 3, nhiệm vụ Diêm nghiệp có những chỉ tiêu cấp 1 nào được báo cáo?'
    - SQL bắt buộc lọc đúng khoảng thời gian Quý 3: 2026-07-01 .. 2026-09-30 và f.year_code = '2026'.
    - Lời dẫn và tiêu đề bảng phải hiển thị Quý 3/2026 (01/07/2026 - 30/09/2026).
    - Dữ liệu thực tế vna_wom_dev trong Quý 3 (kỳ 2026-07-31 / 2026-09-20):
      Tổng diện tích sản xuất muối = '0', Tổng hộ sản xuất muối = '0', Tổng sản lượng muối = '0'.
    """
    res = warehouse_agent.run("Trong quý 3, nhiệm vụ Diêm nghiệp có những chỉ tiêu cấp 1 nào được báo cáo?")
    ans = res["answer"]
    sql = res.get("sql") or ""
    tbl = res.get("tabular_data") or {}

    assert "2026-07-01" in sql and "2026-09-30" in sql
    assert "year_code = '2026'" in sql or "year_code" in sql
    assert "Quý 3/2026" in ans or "Quý 3" in ans
    assert "01/07/2026 - 30/09/2026" in ans
    assert "Quý 3/2026" in tbl.get("title", "")
    assert len(tbl.get("rows", [])) == 3
    for r in tbl.get("rows", []):
        assert r["value"] == "0"


def test_task2_l1_table_7_columns_and_no_value_overwrite():
    """
    Task 2: Tách thành 2 cột 'Giá trị mới nhất' và 'Chỉ tiêu con' (Bảng Cấp 1 7 cột chuẩn output.md):
    - REQ-Q01 (nửa đầu năm 2026):
      STT | Tên chỉ tiêu Cấp 1 | Loại cấu trúc | Giá trị mới nhất | Chỉ tiêu con | Đơn vị thực hiện | Nhiệm vụ trọng tâm
      Với 'Tổng diện tích sản xuất muối': Giá trị mới nhất là '1.520' (không bị ghi đè thành '- (Xem chi tiết con)'),
      và Chỉ tiêu con là '- (Xem chi tiết con)' hoặc '- Xem chi tiết các chỉ tiêu con'.
      Với 'Tổng hộ sản xuất muối': Giá trị mới nhất là '660', Chỉ tiêu con là 'Không có'.
    - REQ-Q04 (nhiệm vụ Diêm nghiệp):
      STT | Nhiệm vụ | Tên chỉ tiêu Cấp 1 | Loại cấu trúc Cấp 1 | Giá trị mới nhất | Chỉ tiêu con | Đơn vị thực hiện
    """
    # 1. Kiểm tra REQ-Q01 / SC-1.1
    res_q01 = warehouse_agent.run("Số lượng chỉ tiêu thu thập được trong nửa đầu năm 2026 là bao nhiêu?")
    tbl_q01 = res_q01.get("tabular_data") or {}
    cols_q01 = [c["label"] for c in tbl_q01.get("columns", [])]
    assert cols_q01 == [
        "STT",
        "Tên chỉ tiêu Cấp 1",
        "Loại cấu trúc",
        "Giá trị mới nhất",
        "Chỉ tiêu con",
        "Đơn vị thực hiện",
        "Nhiệm vụ trọng tâm",
    ]
    rows_q01 = {r["item"]: r for r in tbl_q01.get("rows", [])}
    assert "Tổng diện tích sản xuất muối" in rows_q01
    dt_muoi = rows_q01["Tổng diện tích sản xuất muối"]
    assert dt_muoi["value"] == "1.520"
    assert "chi tiết con" in dt_muoi["child_action"].lower()

    assert "Tổng hộ sản xuất muối" in rows_q01
    ho_muoi = rows_q01["Tổng hộ sản xuất muối"]
    assert ho_muoi["value"] == "660"
    assert ho_muoi["child_action"] == "Không có"

    # 2. Kiểm tra REQ-Q04
    res_q04 = warehouse_agent.run("Nhiệm vụ Diêm nghiệp năm 2026 bao gồm các chỉ tiêu gốc Cấp 1 nào?")
    tbl_q04 = res_q04.get("tabular_data") or {}
    cols_q04 = [c["label"] for c in tbl_q04.get("columns", [])]
    assert cols_q04 == [
        "STT",
        "Nhiệm vụ",
        "Tên chỉ tiêu Cấp 1",
        "Loại cấu trúc Cấp 1",
        "Giá trị mới nhất",
        "Chỉ tiêu con",
        "Đơn vị thực hiện",
    ]
    rows_q04 = {r["item"]: r for r in tbl_q04.get("rows", [])}
    assert "Tổng diện tích sản xuất muối" in rows_q04
    assert rows_q04["Tổng diện tích sản xuất muối"]["value"] in ("1.520", "0")
    assert "chi tiết con" in rows_q04["Tổng diện tích sản xuất muối"]["child_action"].lower()
    assert rows_q04["Tổng hộ sản xuất muối"]["child_action"] == "Không có"


def test_sc_2_1_and_sc_2_4_temporal_ticket_filtering():
    """
    Update 1 & Update 2:
    - SC-2.1 + Ticket Thời Gian ('số lượng chỉ tiêu trồng trọt ngày 30/4'):
      must return the 6-column comparison table (4 branches) at nearest report date 31/03/2026
      with temporal shift notice ('Lưu ý mốc thời gian:').
    - SC-2.4a + Ticket Thời Gian ('Tổng diện tích sản xuất muối ngày 30/6/2026 là bao nhiêu?'):
      must return 5-Field Card with value '1.520' at 30/06/2026 + child suggestion chips.
    """
    # 1. SC-2.1 + Ticket Thời Gian
    res_21 = warehouse_agent.run("số lượng chỉ tiêu trồng trọt ngày 30/4")
    ans_21 = res_21["answer"]
    tbl_21 = res_21.get("tabular_data") or {}
    multi_rows = tbl_21.get("multi_parent_rows", [])
    assert len(multi_rows) == 4
    assert "30/04/2026" in ans_21 and "31/03/2026" in ans_21
    assert "Lưu ý mốc thời gian:" in ans_21
    assert all(r["report_date"] == "31/03/2026" for r in multi_rows)
    assert "31/03/2026" in tbl_21.get("title", "")

    # 2. SC-2.4a + Ticket Thời Gian
    res_24a = warehouse_agent.run("Tổng diện tích sản xuất muối ngày 30/6/2026 là bao nhiêu?")
    ans_24a = res_24a["answer"]
    tbl_24a = res_24a.get("tabular_data") or {}
    chips_24a = res_24a.get("chips") or []
    assert "- **Chỉ tiêu:** Tổng diện tích sản xuất muối" in ans_24a
    assert "- **Giá trị:** 1,520" in ans_24a or "- **Giá trị:** 1.520" in ans_24a
    assert "- **Thời điểm báo cáo:** 30/06/2026" in ans_24a
    assert len(tbl_24a.get("rows", [])) == 1
    assert len(chips_24a) == 2
    chip_labels = " ".join(c["label"] for c in chips_24a)
    assert "Diện tích muối sản xuất công nghiệp" in chip_labels
    assert "Diện tích muối sản xuất thủ công" in chip_labels




