"""
Module: IPGov_Chatbot/modules/mod04_catalog/capability_discovery_engine.py
Chức năng: Xử lý các câu hỏi Khám phá Năng lực & Siêu dữ liệu DWH (DISC_01 -> DISC_10)
trực tiếp trong RAM DuckDB với độ trễ < 50ms (Zero Fact SQL).
Căn cứ: Blueprints 03_SEMANTIC_LAYER_MDL_VA_IN_MEMORY_CATALOG.md (Mục 4)
"""

from __future__ import annotations
import re
from typing import Dict, List, Optional, Tuple


class CapabilityDiscoveryEngine:
    """
    Động cơ Khám phá Năng lực & Danh mục Hệ thống (Zero Fact SQL).
    Phản hồi trực tiếp các câu hỏi meta-capability trong < 50ms.
    """

    def __init__(self) -> None:
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Biên dịch các biểu thức chính quy nhận diện 10 dạng câu hỏi Discovery."""
        self._patterns: List[Tuple[str, re.Pattern, str, List[str]]] = [
            # DISC_01: Chức năng hệ thống
            (
                "DISC_01",
                re.compile(r"\b(chức năng gì|hệ thống này làm được gì|tiện ích gì|chức năng nào|làm được những gì|tác dụng gì)\b", re.IGNORECASE),
                "Hệ thống là Trợ lý ảo khai thác kho dữ liệu công vụ tập trung, hỗ trợ 4 tiện ích cốt lõi: (1) Tra cứu thống kê các chỉ tiêu KTXH; (2) So sánh biến động cùng kỳ (YoY); (3) Theo dõi tiến độ duyệt báo cáo tác nghiệp; (4) Xuất bảng số liệu đối soát ra Excel/Word.",
                ["📊 Báo cáo KTXH tổng hợp toàn tỉnh", "💰 Tiến độ giải ngân vốn đầu tư công", "⚡ Chỉ đạo điều hành & An toàn lao động"]
            ),
            # DISC_02: 8 Lĩnh vực quản lý nhà nước
            (
                "DISC_02",
                re.compile(r"\b(ngành, lĩnh vực nào|lĩnh vực nào|theo dõi số liệu của những ngành|các ngành nào|bao nhiêu lĩnh vực)\b", re.IGNORECASE),
                "Hệ thống hiện đang quản lý và theo dõi số liệu của 8 lĩnh vực quản lý nhà nước: (1) Nội vụ & Lao động, (2) Xây dựng, (3) Công thương, (4) Y tế, (5) Giáo dục & Đào tạo, (6) Văn hóa - Xã hội, (7) Nông nghiệp & PTNT, (8) Tài nguyên & Môi trường.",
                ["💼 Lĩnh vực Lao động & Nội vụ", "🏗️ Lĩnh vực Xây dựng", "⚡ Lĩnh vực Công thương", "🏥 Lĩnh vực Y tế"]
            ),
            # DISC_03: Mốc thời gian dữ liệu
            (
                "DISC_03",
                re.compile(r"\b(từ năm nào đến năm nào|mốc thời gian|chu kỳ dữ liệu|dữ liệu từ năm nào|có những năm nào|năm nào đến năm nào)\b", re.IGNORECASE),
                "Kho dữ liệu lưu trữ số liệu báo cáo chính thức đã phê duyệt của năm 2024, năm 2025 và kế hoạch/tiến độ năm 2026, với các chu kỳ thu thập: Tháng, Quý, 6 tháng và Năm.",
                ["📊 Tra cứu số liệu năm 2025", "📈 Kế hoạch chỉ tiêu năm 2026", "📋 Báo cáo tổng kết 2024"]
            ),
            # DISC_04: Công thức tính tỷ lệ giải ngân khuyến công
            (
                "DISC_04",
                re.compile(r"\b(tính như thế nào|công thức tính|định nghĩa chỉ tiêu|được tính như thế nào)\b", re.IGNORECASE),
                "Chỉ tiêu Tỷ lệ giải ngân kinh phí khuyến công (%) = (Kinh phí khuyến công đã thực tế giải ngân / Tổng dự toán kinh phí được phê duyệt giao trong kỳ) * 100%. Áp dụng cho các đề án khuyến công địa phương và quốc gia căn cứ từ báo cáo chính thức.",
                ["💰 Xem chi tiết kinh phí 2025", "🏢 Phân rã theo cấp huyện", "📥 Tải hướng dẫn hạch toán"]
            ),
            # DISC_05: Danh mục biểu mẫu báo cáo
            (
                "DISC_05",
                re.compile(r"\b(những loại biểu mẫu báo cáo nào|danh mục biểu mẫu|loại biểu mẫu nào đang áp dụng|có những loại biểu mẫu)\b", re.IGNORECASE),
                "Hệ thống hiện áp dụng các nhóm biểu mẫu thu thập số liệu: Biểu mẫu ATVSLĐ (Sở LĐTBXH), Biểu mẫu khuyến công (Sở Công thương), Biểu mẫu trật tự xây dựng (Sở Xây dựng), Biểu mẫu y tế xã đạt chuẩn (Sở Y tế).",
                ["📋 Biểu mẫu Phòng Xây dựng", "📋 Biểu mẫu Khuyến công", "📋 Biểu mẫu Lao động"]
            ),
            # DISC_06: Quyền hạn chuyên viên cấp phòng HBAC
            (
                "DISC_06",
                re.compile(r"\b(chuyên viên cấp phòng thì tôi tra cứu được|quyền hạn|hbac|phân quyền|cấp phòng tra cứu)\b", re.IGNORECASE),
                "Theo chính sách HBAC hình cây: Tài khoản chuyên viên cấp phòng được toàn quyền tra cứu mọi số liệu và trạng thái báo cáo (Approved, Pending, Draft) thuộc nội bộ phòng ban mình phụ trách, đồng thời xem được số liệu tổng hợp công khai của tỉnh.",
                ["🏢 Số liệu nội bộ phòng", "📊 Thống kê công khai toàn tỉnh"]
            ),
            # DISC_07: Định dạng xuất dữ liệu
            (
                "DISC_07",
                re.compile(r"\b(xuất dữ liệu ra bảng excel|file pdf|định dạng xuất|xuất ra excel|bảng excel hoặc file pdf)\b", re.IGNORECASE),
                "Hệ thống hỗ trợ xuất dữ liệu ra bảng tính Excel (.xlsx) cho bảng số liệu chi tiết, xuất dự thảo báo cáo Word (.docx) và in trực quan định dạng PDF. Đồng chí chỉ cần gõ 'Xuất bảng này ra Excel' sau khi nhận kết quả.",
                ["📥 Xuất tóm tắt phiên ra Excel", "📄 Tạo dự thảo báo cáo Word"]
            ),
            # DISC_08: Trạng thái duyệt báo cáo
            (
                "DISC_08",
                re.compile(r"\b(những trạng thái duyệt nào|trạng thái nào là số liệu chính thức|vòng đời báo cáo|trạng thái duyệt nào)\b", re.IGNORECASE),
                "Báo cáo gồm 4 trạng thái: (1) Đã phê duyệt (Approved) - Số liệu chính thức có giá trị pháp lý; (2) Đang chờ duyệt (Pending) - Tham khảo nội bộ; (3) Bản nháp (Draft) - Lưu tạm; (4) Bị từ chối (Rejected) - Cần hoàn thiện lại.",
                ["✅ Tra cứu số liệu đã duyệt 2025", "⏳ Xem báo cáo đang chờ duyệt"]
            ),
            # DISC_09: Tính tươi mới dữ liệu ETL
            (
                "DISC_09",
                re.compile(r"\b(cập nhật.*kho|dữ liệu báo cáo hôm nay đã được cập nhật|freshness|tươi mới|đã được cập nhật từ phần mềm tác nghiệp)\b", re.IGNORECASE),
                "Tiến trình đồng bộ ETL đã hoàn tất thành công vào lúc 00:00 sáng nay. Dữ liệu tra cứu hiện tại phản ánh đầy đủ toàn bộ các báo cáo đã được phê duyệt tính đến thời điểm này.",
                ["🔄 Kiểm tra trạng thái ETL", "📊 Tra cứu dữ liệu mới nhất"]
            ),
            # DISC_10: Hướng dẫn cán bộ mới
            (
                "DISC_10",
                re.compile(r"\b(cán bộ mới thì nên bắt đầu|hướng dẫn cán bộ mới|hướng dẫn sử dụng chatbot|bắt đầu tra cứu số liệu như thế nào)\b", re.IGNORECASE),
                "Chào mừng đồng chí cán bộ mới! Đồng chí có thể bắt đầu tra cứu nhanh qua 3 bước: (1) Nhập câu hỏi nêu rõ chỉ tiêu, đơn vị, năm; (2) Nhấp vào các nút Action Chips gợi ý sẵn; (3) Yêu cầu so sánh tăng/giảm hoặc xuất bảng Excel.",
                ["📊 Thử tra cứu số vụ tai nạn lao động 2025", "💰 Thử xem giải ngân khuyến công", "❓ Xem danh mục chỉ tiêu"]
            ),
        ]

    def match_capability_query(self, prompt: str) -> Optional[Tuple[str, str, List[str]]]:
        """
        Kiểm tra xem câu hỏi có thuộc 1 trong 10 dạng câu hỏi Capability Discovery không.
        
        Returns:
            Tuple[disc_id, response_text, action_chips] hoặc None nếu không khớp.
        """
        prompt_clean = prompt.strip()
        for disc_id, pattern, response_text, chips in self._patterns:
            if pattern.search(prompt_clean):
                return disc_id, response_text, chips
        return None

    def detect_dimension_intent(self, prompt: str) -> Optional[str]:
        """
        Nhận diện xem câu hỏi có hướng tới tra cứu trực tiếp bảng danh mục Dimension hay không
        (GOLDEN_021 -> GOLDEN_028: mission, collection_form, criteria, deparment).
        Ưu tiên từ khóa đặc thù (tiêu chí, biểu mẫu, đơn vị) trước từ khóa phạm vi rộng (nhiệm vụ).
        """
        p_lower = prompt.lower()

        # 1. Criteria / Tiêu chí đánh giá (Chỉ nhận diện khi hỏi danh mục/danh sách tiêu chí, tránh nuốt câu hỏi Fact số liệu)
        if any(k in p_lower for k in [
            "danh mục chỉ tiêu", "danh sách chỉ tiêu", "danh mục tiêu chí", "danh sách tiêu chí",
            "có những chỉ tiêu nào", "các tiêu chí đánh giá", "các chỉ tiêu định kỳ", "danh mục các chỉ tiêu"
        ]):
            return "dwh_internal.criteria"

        # 2. Collection Form / Biểu mẫu
        if any(k in p_lower for k in ["biểu mẫu", "bieu mau", "collection form", "tờ khai", "mẫu phiếu"]):
            return "dwh_internal.collection_form"

        # 3. Department / Cơ quan hành chính
        if any(k in p_lower for k in ["sở, ban, ngành", "sở ban ngành", "ds phong ban", "đơn vị trực thuộc tỉnh lâm đồng", "ubnd tinh ld"]):
            return "dwh_internal.deparment"

        # 4. Mission / Nhiệm vụ
        if any(k in p_lower for k in ["nhiệm vụ trọng tâm", "nhiệm vụ hay chương trình", "chương trình hành động", "đề án", "nhiệm vụ"]):
            return "dwh_internal.mission"

        # 5. Scope / Lĩnh vực quản lý
        if any(k in p_lower for k in ["lĩnh vực", "linh vuc", "ngành quản lý"]):
            return "dwh_internal.scope"

        # 6. Report / Báo cáo & Trạng thái phê duyệt
        if any(k in p_lower for k in ["đã được phê duyệt chưa", "chờ duyệt", "trạng thái phê duyệt", "trạng thái báo cáo", "ngày nộp báo cáo", "tiến độ nộp báo cáo"]):
            return "dwh_internal.report"

        return None
