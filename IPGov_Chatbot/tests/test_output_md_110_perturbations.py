"""
Test Suite: test_output_md_110_perturbations.py
Kiểm thử toàn diện 22 Quest gốc × 4 Biến thể Perturbation (88 Perturbations = 110 câu hỏi)
theo đúng đặc tả implementation_plan.md & output.md:
- P1 (+Noise): Thêm từ nhiễu/từ đệm hành chính vào đầu/giữa/cuối câu hỏi
- P2 (-Reduce): Rút gọn các từ phụ trong câu hỏi (giữ nguyên từ khóa quan trọng)
- P3 (~Invert): Đảo vị trí các từ/cụm từ trong câu hỏi
- P4 (*Combo): Tổ hợp đảo vị trí + thêm từ nhiễu/rút gọn
Đảm bảo 100% bất biến hành vi (Behavioral Invariance) trên toàn bộ 110 câu hỏi và thực thi E2E trên PostgreSQL DWH (`vna_wom_dev`).
"""

import pytest
from IPGov_Chatbot.schemas.canonical_query_frame import CanonicalIntentEnum
from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog
from IPGov_Chatbot.modules.mod03_router.canonical_normalizer import CanonicalSemanticNormalizer
from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import WarehouseLangGraphAgent


PERTURBATION_MATRIX_22X5 = [
    # ==========================================================================
    # NHÓM 1: REQ-Q01, SC-1.1, SC-1.2 (4 Quest gốc × 5 = 20 câu)
    # ==========================================================================
    {
        "id": "Q01-B1",
        "type": "REQ-Q01",
        "base": "Liệt kê số lượng các chỉ tiêu từ tháng 2 đến tháng 8 năm nay?",
        "perturbations": [
            "Dạ đồng chí ơi, vui lòng kiểm tra và liệt kê giúp tôi xem số lượng các chỉ tiêu từ tháng 2 đến tháng 8 năm nay hiện đang có trên hệ thống là như thế nào?",
            "Số lượng các chỉ tiêu từ tháng 2 đến tháng 8 năm nay?",
            "Từ tháng 2 đến tháng 8 năm nay thì liệt kê được số lượng các chỉ tiêu nào?",
            "Trong năm nay, tính từ tháng 2 đến tháng 8 thì hệ thống liệt kê số lượng các chỉ tiêu ra sao?",
        ],
        "expected_intent": CanonicalIntentEnum.DIMENSION_LISTING,
        "expected_date_from": "2026-02-01",
        "expected_date_to": "2026-08-31",
        "expected_substrings": ["Tổng diện tích sản xuất muối", "Chương trình OCOP", "Chi cục"],
    },
    {
        "id": "Q01-B2",
        "type": "REQ-Q01",
        "base": "Cho tôi các chỉ tiêu thu thập được trong tháng 9 năm nay?",
        "perturbations": [
            "Xin chào hệ thống, hãy tra cứu và cho tôi biết danh sách các chỉ tiêu thu thập được trong tháng 9 năm nay trên kho dữ liệu nhé?",
            "Các chỉ tiêu thu thập trong tháng 9 năm nay?",
            "Trong tháng 9 năm nay có các chỉ tiêu nào thu thập được?",
            "Tính riêng trong tháng 9 năm nay thôi thì hệ thống thu thập được các chỉ tiêu nào vậy?",
        ],
        "expected_intent": CanonicalIntentEnum.DIMENSION_LISTING,
        "expected_month": 9,
        "expected_substrings": ["Chương trình OCOP", "HTX nông nghiệp", "Chi cục"],
    },
    {
        "id": "Q01-B3",
        "type": "SC-1.1",
        "base": "Liệt kê số lượng các tiêu chí trong nửa đầu năm 2026?",
        "perturbations": [
            "Đồng chí làm ơn thống kê và liệt kê chi tiết giúp tôi số lượng các tiêu chí trong nửa đầu năm 2026 của tỉnh mình với?",
            "Số lượng các tiêu chí nửa đầu năm 2026?",
            "Trong nửa đầu năm 2026, hãy liệt kê số lượng các chỉ tiêu cấp đầu?",
            "Năm 2026 tính trong nửa đầu năm thì liệt kê được số lượng các chỉ tiêu nào trên kho?",
        ],
        "expected_intent": CanonicalIntentEnum.DIMENSION_LISTING,
        "expected_date_from": "2026-01-01",
        "expected_date_to": "2026-06-30",
        "expected_substrings": ["Tổng diện tích sản xuất muối", "Chương trình OCOP", "Chi cục"],
    },
    {
        "id": "Q01-B4",
        "type": "SC-1.2",
        "base": "Các chỉ tiêu thu thập trong tháng 1 năm 2024 là gì?",
        "perturbations": [
            "Cho tôi hỏi thăm một chút là các chỉ tiêu thu thập trong tháng 1 năm 2024 trên hệ thống báo cáo hiện nay là gì vậy?",
            "Các chỉ tiêu thu thập tháng 1 năm 2024?",
            "Trong tháng 1 năm 2024 có các chỉ tiêu nào được thu thập?",
            "Vào năm 2024, cụ thể là trong tháng 1 thì có các chỉ tiêu thu thập nào được ghi nhận không?",
        ],
        "expected_intent": CanonicalIntentEnum.DIMENSION_LISTING,
        "expected_year": "2024",
        "expected_month": 1,
        "expected_substrings": ["chưa ghi nhận bản ghi chỉ tiêu nào được phê duyệt", "01/2024"],
    },
    # ==========================================================================
    # NHÓM 2: REQ-Q02, SC-2.1, SC-2.2, SC-2.3, SC-2.4 (7 Quest gốc × 5 = 35 câu)
    # ==========================================================================
    {
        "id": "Q02-B5",
        "type": "REQ-Q02",
        "base": "Cho tôi biết tổng hộ sản xuất muối năm 2026 là bao nhiêu?",
        "perturbations": [
            "Chào trợ lý ảo, đồng chí hãy tra cứu và cho tôi biết chính xác tổng hộ sản xuất muối năm 2026 hiện đang ghi nhận là bao nhiêu nhé?",
            "Tổng hộ sản xuất muối năm 2026 bao nhiêu?",
            "Năm 2026, tổng hộ sản xuất muối là bao nhiêu, cho tôi biết?",
            "Hiện tại trong năm 2026 thì số liệu tổng hộ sản xuất muối là bao nhiêu vậy đồng chí?",
        ],
        "expected_intent": CanonicalIntentEnum.METRIC_POINT_INQUIRY,
        "expected_substrings": [
            "- **Chỉ tiêu:** Tổng hộ sản xuất muối",
            "- **Giá trị:** 0",
            "- **Đơn vị thực hiện:** Chi cục",
            "- **Nhiệm vụ trọng tâm:** Diêm nghiệp",
        ],
    },
    {
        "id": "Q02-B6",
        "type": "REQ-Q02",
        "base": "Số lượng sản phẩm OCOP 3 sao đã được công nhận là bao nhiêu?",
        "perturbations": [
            "Làm ơn kiểm tra giúp tôi xem hiện nay trên địa bàn tỉnh thì số lượng sản phẩm OCOP 3 sao đã được công nhận là bao nhiêu rồi?",
            "Số lượng sản phẩm OCOP 3 sao đã được công nhận?",
            "Đã được công nhận là bao nhiêu đối với số lượng sản phẩm OCOP 3 sao?",
            "Tính đến nay thì đã được công nhận số lượng sản phẩm OCOP 3 sao là bao nhiêu trên hệ thống?",
        ],
        "expected_intent": CanonicalIntentEnum.METRIC_POINT_INQUIRY,
        "expected_substrings": [
            "- **Chỉ tiêu:** Số lượng sản phẩm OCOP 3 sao",
            "- **Giá trị:** 143",
            "- **Đơn vị thực hiện:** Chi cục",
        ],
    },
    {
        "id": "Q02-B7",
        "type": "SC-2.1",
        "base": "Chỉ tiêu thành lập mới hiện tại là bao nhiêu?",
        "perturbations": [
            "Dạ cho tôi hỏi chút là theo số liệu báo cáo thì chỉ tiêu thành lập mới hiện tại đang được ghi nhận là bao nhiêu vậy?",
            "Chỉ tiêu thành lập mới hiện tại bao nhiêu?",
            "Hiện tại là bao nhiêu đối với chỉ tiêu thành lập mới?",
            "Trên kho dữ liệu hiện tại thì chỉ tiêu thành lập mới đạt bao nhiêu?",
        ],
        "expected_intent": CanonicalIntentEnum.METRIC_POINT_INQUIRY,
        "expected_substrings": [
            "HTX nông nghiệp",
            "Liên hiệp HTX nông nghiệp",
            "Tổ hợp tác",
            "Trang trại",
            "Chi cục",
        ],
    },
    {
        "id": "Q02-B8",
        "type": "SC-2.2",
        "base": "Số liệu chỉ tiêu trang trại ngày 23/4 là bao nhiêu?",
        "perturbations": [
            "Đồng chí vui lòng tra cứu giúp tôi xem số liệu chỉ tiêu trang trại ngày 23/4 trên hệ thống báo cáo là bao nhiêu nhé?",
            "Số liệu chỉ tiêu trang trại ngày 23/4?",
            "Vào ngày 23/4, số liệu chỉ tiêu trang trại là bao nhiêu?",
            "Tính tại thời điểm ngày 23/4 thì hệ thống ghi nhận số liệu chỉ tiêu trang trại bao nhiêu?",
        ],
        "expected_intent": CanonicalIntentEnum.METRIC_POINT_INQUIRY,
        "expected_specific_date": "2026-04-23",
        "expected_substrings": ["Trang trại", "31/03/2026"],
    },
    {
        "id": "Q02-B9",
        "type": "SC-2.2",
        "base": "Số lượng chỉ tiêu trang trại trong nửa đầu năm nay là bao nhiêu?",
        "perturbations": [
            "Cho tôi hỏi thêm là tổng hợp số lượng chỉ tiêu trang trại trong nửa đầu năm nay theo báo cáo đã duyệt là bao nhiêu?",
            "Số lượng chỉ tiêu trang trại nửa đầu năm nay?",
            "Trong nửa đầu năm nay, số lượng chỉ tiêu trang trại là bao nhiêu?",
            "Xét trong nửa đầu năm nay thôi thì số lượng chỉ tiêu trang trại đạt bao nhiêu vậy?",
        ],
        "expected_intent": CanonicalIntentEnum.METRIC_POINT_INQUIRY,
        "expected_date_from": "2026-01-01",
        "expected_date_to": "2026-06-30",
        "expected_substrings": ["Trang trại", "2026-06-30"],
    },
    {
        "id": "Q02-B10",
        "type": "SC-2.3",
        "base": "Chỉ tiêu liên kết sản xuất của Tổ hợp tác năm 2026 là bao nhiêu?",
        "perturbations": [
            "Xin hỏi hệ thống, hiện tại chỉ tiêu liên kết sản xuất của Tổ hợp tác năm 2026 đang có số liệu báo cáo là bao nhiêu?",
            "Chỉ tiêu liên kết sản xuất Tổ hợp tác năm 2026?",
            "Năm 2026, của Tổ hợp tác thì chỉ tiêu liên kết sản xuất là bao nhiêu?",
            "Trong năm 2026 này, đối với Tổ hợp tác thì chỉ tiêu liên kết sản xuất ghi nhận bao nhiêu?",
        ],
        "expected_intent": CanonicalIntentEnum.METRIC_POINT_INQUIRY,
        "expected_substrings": [
            "- **Chỉ tiêu:** Liên kết sản xuất",
            "- **Giá trị:** Chưa có số liệu phê duyệt (-)",
            "- **Đơn vị thực hiện:** Chi cục",
            "- **Nhiệm vụ trọng tâm:** Phát triển nông thôn",
        ],
    },
    {
        "id": "Q02-B11",
        "type": "SC-2.4",
        "base": "Cho tôi biết số liệu chỉ tiêu Liên hiệp HTX nông nghiệp?",
        "perturbations": [
            "Đồng chí ơi, làm ơn kiểm tra và cho tôi biết thông tin số liệu chỉ tiêu Liên hiệp HTX nông nghiệp hiện nay trên kho dữ liệu nhé?",
            "Số liệu chỉ tiêu Liên hiệp HTX nông nghiệp?",
            "Đối với chỉ tiêu Liên hiệp HTX nông nghiệp thì cho tôi biết số liệu?",
            "Hiện nay đối với chỉ tiêu Liên hiệp HTX nông nghiệp thì hệ thống ghi nhận số liệu thế nào?",
        ],
        "expected_intent": CanonicalIntentEnum.METRIC_POINT_INQUIRY,
        "expected_substrings": ["Liên hiệp HTX nông nghiệp", "chỉ tiêu cha", "chỉ tiêu con"],
    },
    # ==========================================================================
    # NHÓM 3: REQ-Q03, SC-3.1, SC-3.2 (3 Quest gốc × 5 = 15 câu)
    # ==========================================================================
    {
        "id": "Q03-B12",
        "type": "REQ-Q03",
        "base": "Liệt kê các nhiệm vụ trong lĩnh vực Nông nghiệp?",
        "perturbations": [
            "Dạ vui lòng tra cứu danh mục và liệt kê đầy đủ giúp tôi các nhiệm vụ trong lĩnh vực Nông nghiệp hiện đang quản lý nhé?",
            "Các nhiệm vụ lĩnh vực Nông nghiệp?",
            "Trong lĩnh vực Nông nghiệp hiện có các nhiệm vụ nào, hãy liệt kê?",
            "Đối với lĩnh vực Nông nghiệp trên hệ thống hiện nay thì đang có các nhiệm vụ nào vậy?",
        ],
        "expected_intent": CanonicalIntentEnum.METADATA_EXPLORATION,
        "expected_target_table": "mission",
        "expected_substrings": ["Diêm nghiệp", "Phát triển nông thôn", "Chi cục"],
        "forbidden_substrings": ["Cải cách hành chính"],
    },
    {
        "id": "Q03-B13",
        "type": "SC-3.1",
        "base": "Lĩnh vực Nông nghiệp trong nửa đầu năm có những nhiệm vụ nào?",
        "perturbations": [
            "Cho tôi hỏi là tính riêng lĩnh vực Nông nghiệp trong nửa đầu năm thì trên hệ thống báo cáo đang có những nhiệm vụ nào?",
            "Nhiệm vụ lĩnh vực Nông nghiệp nửa đầu năm?",
            "Trong nửa đầu năm, lĩnh vực Nông nghiệp có những nhiệm vụ nào?",
            "Xét trong nửa đầu năm thôi thì có những nhiệm vụ nào thuộc lĩnh vực Nông nghiệp được báo cáo?",
        ],
        "expected_intent": CanonicalIntentEnum.METADATA_EXPLORATION,
        "expected_target_table": "mission",
        "expected_date_from": "2026-01-01",
        "expected_date_to": "2026-06-30",
        "expected_substrings": ["Diêm nghiệp", "Phát triển nông thôn", "Chi cục"],
    },
    {
        "id": "Q03-B14",
        "type": "SC-3.2",
        "base": "Liệt kê các nhiệm vụ thuộc lĩnh vực Hàng không vũ trụ?",
        "perturbations": [
            "Đồng chí kiểm tra thử trên kho dữ liệu xem và liệt kê giúp tôi các nhiệm vụ thuộc lĩnh vực Hàng không vũ trụ hiện có nhé?",
            "Các nhiệm vụ lĩnh vực Hàng không vũ trụ?",
            "Thuộc lĩnh vực Hàng không vũ trụ thì có các nhiệm vụ nào, hãy liệt kê?",
            "Hiện tại trong lĩnh vực Hàng không vũ trụ trên hệ thống có các nhiệm vụ nào không?",
        ],
        "expected_intent": CanonicalIntentEnum.METADATA_EXPLORATION,
        "expected_target_table": "mission",
        "expected_substrings": ["không có lĩnh vực 'Hàng không vũ trụ'", "Nông nghiệp", "Lĩnh vực 1"],
    },
    # ==========================================================================
    # NHÓM 4: REQ-Q04, SC-4.1, SC-4.2 (4 Quest gốc × 5 = 20 câu)
    # ==========================================================================
    {
        "id": "Q04-B15",
        "type": "REQ-Q04",
        "base": "Hiển thị các tiêu chí cấp 1 của nhiệm vụ Phát triển nông thôn?",
        "perturbations": [
            "Xin chào, đồng chí vui lòng truy xuất dữ liệu và hiển thị đầy đủ các tiêu chí cấp 1 của nhiệm vụ Phát triển nông thôn giúp tôi nhé?",
            "Danh sách các chỉ tiêu cấp đầu hiện có trong nhiệm vụ phát triển nông thôn là gì?",
            "Của nhiệm vụ Phát triển nông thôn thì hiển thị các nhóm tiêu chí gốc nào?",
            "Đối với nhiệm vụ Phát triển nông thôn hiện nay, hãy hiển thị xem có các tiêu chí bậc 1 nào?",
        ],
        "expected_intent": CanonicalIntentEnum.DIMENSION_LISTING,
        "expected_substrings": ["Chương trình OCOP", "HTX nông nghiệp", "Chi cục"],
    },
    {
        "id": "Q04-B16",
        "type": "REQ-Q04",
        "base": "Nhiệm vụ Diêm nghiệp có những tiêu chí bậc 1 nào?",
        "perturbations": [
            "Cho tôi hỏi thăm là hiện tại trên hệ thống thì nhiệm vụ Diêm nghiệp có những tiêu chí cấp 1 nào đang được theo dõi vậy?",
            "Các tiêu chí cấp đầu nhiệm vụ Diêm nghiệp?",
            "Có những nhóm chỉ tiêu gốc nào thuộc về nhiệm vụ Diêm nghiệp?",
            "Trên kho dữ liệu báo cáo, những tiêu chí bậc 1 nào là của nhiệm vụ Diêm nghiệp?",
        ],
        "expected_intent": CanonicalIntentEnum.DIMENSION_LISTING,
        "expected_substrings": ["Tổng diện tích sản xuất muối", "Tổng sản lượng muối", "Tổng hộ sản xuất muối", "Chi cục"],
    },
    {
        "id": "Q04-B17",
        "type": "SC-4.1",
        "base": "Trong quý 3, nhiệm vụ Diêm nghiệp có những chỉ tiêu cấp 1 nào được báo cáo?",
        "perturbations": [
            "Đồng chí kiểm tra giúp tôi xem tính trong quý 3 vừa qua thì nhiệm vụ Diêm nghiệp có những chỉ tiêu cấp 1 nào được báo cáo trên hệ thống?",
            "Chỉ tiêu cấp 1 nhiệm vụ Diêm nghiệp quý 3?",
            "Nhiệm vụ Diêm nghiệp có những chỉ tiêu cấp 1 nào được báo cáo trong quý 3?",
            "Có những chỉ tiêu cấp 1 nào được báo cáo của nhiệm vụ Diêm nghiệp tính trong quý 3 vậy?",
        ],
        "expected_intent": CanonicalIntentEnum.DIMENSION_LISTING,
        "expected_date_from": "2026-07-01",
        "expected_date_to": "2026-09-30",
        "expected_substrings": ["Tổng diện tích sản xuất muối", "Tổng hộ sản xuất muối", "Chi cục"],
    },
    {
        "id": "Q04-B18",
        "type": "SC-4.2",
        "base": "Hiển thị các chỉ tiêu cấp 1 của nhiệm vụ Cải cách hành chính năm 2026?",
        "perturbations": [
            "Dạ làm ơn tra cứu và hiển thị giúp tôi danh sách các chỉ tiêu cấp 1 của nhiệm vụ Cải cách hành chính năm 2026 trên kho dữ liệu nhé?",
            "Các chỉ tiêu cấp 1 nhiệm vụ Cải cách hành chính năm 2026?",
            "Năm 2026, của nhiệm vụ Cải cách hành chính thì hiển thị các chỉ tiêu cấp 1 nào?",
            "Đối với nhiệm vụ Cải cách hành chính trong năm 2026, hãy hiển thị các chỉ tiêu cấp 1 hiện có?",
        ],
        "expected_intent": CanonicalIntentEnum.DIMENSION_LISTING,
        "expected_substrings": ["Cải cách hành chính", "chưa phát sinh bản ghi chỉ tiêu báo cáo nào được phê duyệt"],
    },
    # ==========================================================================
    # NHÓM 5: REQ-Q05 (SC-5.1a, SC-5.1b, SC-5.2, SC-5.3) (4 Quest gốc × 5 = 20 câu)
    # ==========================================================================
    {
        "id": "Q05-B19",
        "type": "SC-5.1a",
        "base": "Liệt kê trạng thái các kỳ báo cáo năm 2026, ngày nộp và những báo cáo nào đang ở trạng thái nháp chưa nộp?",
        "perturbations": [
            "Đồng chí ơi, vui lòng rà soát toàn bộ hệ thống và liệt kê giúp tôi trạng thái các kỳ báo cáo năm 2026, ngày nộp và những báo cáo nào đang ở trạng thái nháp chưa nộp nhé?",
            "Trạng thái các kỳ báo cáo năm 2026, ngày nộp và báo cáo nháp chưa nộp?",
            "Năm 2026, những báo cáo nào đang ở trạng thái nháp chưa nộp, ngày nộp và liệt kê trạng thái các kỳ báo cáo?",
            "Trên kho dữ liệu năm 2026 hiện nay, hãy liệt kê ngày nộp, trạng thái các kỳ báo cáo cùng những báo cáo nào đang ở trạng thái nháp chưa nộp?",
        ],
        "expected_intent": CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT,
        "expected_audit_sub_intent": "REPORT_SUBMISSION_STATUS",
        "expected_substrings": ["9 kỳ báo cáo", "tzyalnh", "Chi cục"],
    },
    {
        "id": "Q05-B20",
        "type": "SC-5.1b",
        "base": "Cho biết chi tiết các chỉ tiêu trong các kỳ báo cáo nháp của nhiệm vụ Diêm nghiệp năm 2026 và đối chiếu chênh lệch với bản đã phê duyệt?",
        "perturbations": [
            "Xin hãy kiểm tra sâu hơn và cho tôi biết chi tiết các chỉ tiêu trong các kỳ báo cáo nháp của nhiệm vụ Diêm nghiệp năm 2026 và đối chiếu chênh lệch với bản đã phê duyệt nhé?",
            "Chi tiết chỉ tiêu các kỳ báo cáo nháp nhiệm vụ Diêm nghiệp năm 2026 và đối chiếu chênh lệch bản đã phê duyệt?",
            "Của nhiệm vụ Diêm nghiệp năm 2026, hãy đối chiếu chênh lệch với bản đã phê duyệt và cho biết chi tiết các chỉ tiêu trong các kỳ báo cáo nháp?",
            "Trong năm 2026 đối với nhiệm vụ Diêm nghiệp, vui lòng cho biết chi tiết các chỉ tiêu trong các kỳ báo cáo nháp kèm đối chiếu chênh lệch với bản đã phê duyệt?",
        ],
        "expected_intent": CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT,
        "expected_audit_sub_intent": "REPORT_SUBMISSION_STATUS",
        "expected_substrings": ["Diêm nghiệp", "Đối chiếu chênh lệch", "Chi cục"],
    },
    {
        "id": "Q05-B21",
        "type": "SC-5.2",
        "base": "Hệ thống hiện có những biểu mẫu thu thập hoặc bộ thu thập chỉ tiêu nào đang áp dụng năm 2026?",
        "perturbations": [
            "Cho tôi hỏi thăm là trên phần mềm hệ thống hiện có những biểu mẫu thu thập hoặc bộ thu thập chỉ tiêu nào đang áp dụng năm 2026 vậy đồng chí?",
            "Những biểu mẫu thu thập hoặc bộ thu thập chỉ tiêu đang áp dụng năm 2026?",
            "Năm 2026 đang áp dụng những biểu mẫu thu thập hoặc bộ thu thập chỉ tiêu nào trên hệ thống?",
            "Tính trong năm 2026 này thì những bộ thu thập chỉ tiêu hoặc biểu mẫu thu thập nào đang áp dụng trên hệ thống?",
        ],
        "expected_intent": CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT,
        "expected_audit_sub_intent": "FORM_CRITERIA_GROUP",
        "expected_substrings": ["Bộ thu thập Diêm nghiệp", "Bộ thu thập Phát triển nông thôn"],
    },
    {
        "id": "Q05-B22",
        "type": "SC-5.3",
        "base": "Hiển thị ma trận phân công nhiệm vụ năm 2026 giữa các phòng ban và cá nhân phụ trách?",
        "perturbations": [
            "Dạ đồng chí làm ơn tổng hợp và hiển thị rõ ràng giúp tôi bảng ma trận phân công nhiệm vụ năm 2026 giữa các phòng ban và cá nhân phụ trách trên hệ thống nhé?",
            "Ma trận phân công nhiệm vụ năm 2026 giữa các phòng ban và cá nhân phụ trách?",
            "Giữa các phòng ban và cá nhân phụ trách năm 2026, hãy hiển thị ma trận phân công nhiệm vụ?",
            "Trong năm 2026 này, giữa các phòng ban và cá nhân phụ trách thì ma trận phân công nhiệm vụ được hiển thị như thế nào?",
        ],
        "expected_intent": CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT,
        "expected_audit_sub_intent": "MISSION_ASSIGNMENT_MATRIX",
        "expected_substrings": ["Diêm nghiệp", "Phát triển nông thôn", "Cải cách hành chính", "Chi cục"],
    },
]


class TestOutputMd110Perturbations:
    @classmethod
    def setup_class(cls):
        cls.catalog = DuckDBSemanticCatalog()
        cls.normalizer = CanonicalSemanticNormalizer(catalog=cls.catalog)
        cls.agent = WarehouseLangGraphAgent()
        # Tắt LLM trong normalizer cho kiểm thử bất biến ngữ nghĩa để tránh độ trễ API mạng và kiểm chứng tính tất định của tầng chuẩn hóa
        cls.normalizer.llm_client = None
        cls.agent.normalizer.llm_client = None

    @pytest.mark.parametrize("quest_group", PERTURBATION_MATRIX_22X5, ids=[g["id"] for g in PERTURBATION_MATRIX_22X5])
    def test_quest_group_5_variants_invariance_and_e2e(self, quest_group):
        queries = [quest_group["base"]] + quest_group["perturbations"]
        assert len(queries) == 5

        base_frame = None
        for idx, q in enumerate(queries):
            variant_label = "BASE" if idx == 0 else f"P{idx}"
            frame = self.normalizer.normalize_query(q, session_tenant="68", session_year="2026")

            assert frame.intent == quest_group["expected_intent"], (
                f"[{quest_group['id']} {variant_label}] Sai intent cho '{q}': {frame.intent} != {quest_group['expected_intent']}"
            )
            if "expected_target_table" in quest_group:
                assert frame.target_table == quest_group["expected_target_table"], (
                    f"[{quest_group['id']} {variant_label}] Sai target_table cho '{q}': {frame.target_table}"
                )
            if "expected_audit_sub_intent" in quest_group:
                assert frame.audit_sub_intent == quest_group["expected_audit_sub_intent"], (
                    f"[{quest_group['id']} {variant_label}] Sai audit_sub_intent cho '{q}': {frame.audit_sub_intent}"
                )
            if "expected_date_from" in quest_group:
                assert frame.date_from == quest_group["expected_date_from"], (
                    f"[{quest_group['id']} {variant_label}] Sai date_from cho '{q}': {frame.date_from}"
                )
            if "expected_date_to" in quest_group:
                assert frame.date_to == quest_group["expected_date_to"], (
                    f"[{quest_group['id']} {variant_label}] Sai date_to cho '{q}': {frame.date_to}"
                )
            if "expected_month" in quest_group:
                assert frame.month_filter == quest_group["expected_month"], (
                    f"[{quest_group['id']} {variant_label}] Sai month_filter cho '{q}': {frame.month_filter}"
                )
            if "expected_specific_date" in quest_group:
                assert frame.specific_date == quest_group["expected_specific_date"], (
                    f"[{quest_group['id']} {variant_label}] Sai specific_date cho '{q}': {frame.specific_date}"
                )
            if "expected_year" in quest_group:
                assert frame.year_code == quest_group["expected_year"], (
                    f"[{quest_group['id']} {variant_label}] Sai year_code cho '{q}': {frame.year_code}"
                )

            if base_frame is None:
                base_frame = frame
            else:
                assert frame.intent == base_frame.intent, f"[{quest_group['id']} {variant_label}] Lệch intent so với Base"
                assert frame.target_table == base_frame.target_table, f"[{quest_group['id']} {variant_label}] Lệch target_table so với Base"
                assert frame.is_level1_hierarchy_view == base_frame.is_level1_hierarchy_view, f"[{quest_group['id']} {variant_label}] Lệch is_level1_hierarchy_view so với Base"
                assert frame.target_scope == base_frame.target_scope, f"[{quest_group['id']} {variant_label}] Lệch target_scope so với Base: {frame.target_scope} != {base_frame.target_scope}"
                assert frame.target_mission == base_frame.target_mission, f"[{quest_group['id']} {variant_label}] Lệch target_mission so với Base: {frame.target_mission} != {base_frame.target_mission}"

            # Thực thi E2E trên CSDL thật cho cả 5 biến thể (BASE + P1..P4)
            res = self.agent.run(q, session_id=f"test_110_{quest_group['id']}_{variant_label}")
            ans = res["answer"]
            assert "Chi cục Phát triển nông thôn" not in ans, (
                f"[{quest_group['id']} {variant_label}] Vẫn còn 'Chi cục Phát triển nông thôn' trong câu trả lời!"
            )
            for sub in quest_group.get("expected_substrings", []):
                assert sub in ans, (
                    f"[{quest_group['id']} {variant_label}] Thiếu chuỗi kỳ vọng '{sub}' trong câu trả lời cho '{q}'.\nAnswer:\n{ans}"
                )
            for f_sub in quest_group.get("forbidden_substrings", []):
                assert f_sub not in ans, (
                    f"[{quest_group['id']} {variant_label}] Xuất hiện chuỗi bị cấm '{f_sub}' trong câu trả lời cho '{q}'."
                )
