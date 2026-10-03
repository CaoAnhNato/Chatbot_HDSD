"""
Module: IPGov_Chatbot/modules/mod02_guardrails/scope_prechecker.py
Chức năng: Kiểm tra phạm vi dữ liệu công vụ của câu hỏi đối chiếu với 8 lĩnh vực DWH vna_wom_dev.
Từ chối sớm các câu hỏi phi lý (ví dụ: dầu khí ngoài khơi ở Lâm Đồng, giải trí, thời sự quốc tế).
"""

import re
from typing import Dict, Any, Tuple


class ScopePrechecker:
    """Bộ lọc tiền kiểm phạm vi thẩm quyền và dữ liệu của Kho DWH."""

    # 1. Các chủ đề cấm / hoàn toàn không tồn tại trong kho DWH công nghiệp địa phương
    # Đặc biệt: Lâm Đồng là tỉnh vùng núi Tây Nguyên không có biển, không có giàn khoan dầu khí ngoài khơi
    _RE_OUT_OF_SCOPE_SPECIFIC = re.compile(
        r"(?:(?:(?:khai\s+thác\s+)?dầu\s+khí(?:\s+ngoài\s+khơi)?|giàn\s+khoan(?:\s+dầu\s+khí)?|điện\s+hạt\s+nhân|lọc\s+dầu|nhà\s+máy\s+lọc\s+dầu)|"
        r"\b(?:tiền\s+ảo|crypto|bitcoin|ethereum|tử\s+vi|bói\s+toán|soi\s+kèo|đánh\s+bạc|cá\s+độ|cá\s+cược|chiến\s+tranh\s+(?:quốc\s+tế|ukraine|thế\s+giới|nga\s*-\s*ukraine|trung\s+đông)|bầu\s+cử\s+(?:tổng\s+thống\s+)?(?:mỹ|hoa\s+kỳ|nước\s+ngoài))\b)",
        re.IGNORECASE
    )

    # 2. Thủ tục hành chính công (Dịch vụ công một cửa: CCCD, hộ chiếu, hộ khẩu, khai sinh...)
    _RE_ADMINISTRATIVE_PROCEDURE = re.compile(
        r"\b(?:thủ\s+tục|giấy\s+tờ|hồ\s+sơ|quy\s+trình\s+xin|xin\s+cấp|hướng\s+dẫn\s+làm)\b.*\b(?:căn\s+cước|cccd|hộ\s+chiếu|passport|kết\s+hôn|khai\s+sinh|giấy\s+phép\s+lái\s+xe|gplx|sổ\s+đỏ|hộ\s+khẩu|tạm\s+trú|thường\s+trú)\b|"
        r"\b(?:căn\s+cước\s+công\s+dân|cccd\s+gắn\s+chip)\b",
        re.IGNORECASE
    )

    # 3. Thời tiết, đời sống, du lịch giải trí
    _RE_WEATHER_LIFESTYLE = re.compile(
        r"\b(?:thời\s+tiết|dự\s+báo\s+thời\s+tiết|nhiệt\s+độ\s+hôm\s+nay|trời\s+mưa\s+không|quán\s+ăn|nhà\s+hàng|khách\s+sạn|tour\s+du\s+lịch)\b",
        re.IGNORECASE
    )

    # 4. Lãnh đạo Đảng, Chính trị ngoài phạm vi phân công chuyên môn DWH
    _RE_POLITICAL_LEADERSHIP = re.compile(
        r"\b(?:bí\s+thư\s+tỉnh\s+ủy|phó\s+bí\s+thư\s+tỉnh\s+ủy|tổng\s+bí\s+thư|chủ\s+tịch\s+nước|thủ\s+tướng|bộ\s+chính\s+trị|đại\s+hội\s+đảng)\b",
        re.IGNORECASE
    )

    # 5. Tác vụ sáng tác tự do, văn bản hành chính tự sinh
    _RE_CREATIVE_GENERATIVE = re.compile(
        r"\b(?:viết|soạn|làm)\s+(?:cho\s+tôi\s+)?(?:bài\s+phát\s+biểu|diễn\s+văn|bài\s+văn|thơ|bài\s+thơ|đơn\s+xin|kịch\s+bản|bài\s+báo)\b",
        re.IGNORECASE
    )

    # 6. Đánh giá định tính chủ quan về mức độ tin cậy
    _RE_QUALITATIVE_APPRAISAL = re.compile(
        r"\b(?:đáng\s+tin\s+cậy\s+không|có\s+đáng\s+tin\s+không|có\s+chuẩn\s+không|có\s+chính\s+xác\s+không|làm\s+tốt\s+không|đánh\s+giá\s+(?:chất\s+lượng\s+số\s+liệu|xem\s+sở\s+nào\s+tốt))\b",
        re.IGNORECASE
    )

    # 8 Lĩnh vực quản trị cốt lõi được phép xử lý
    VALID_DOMAINS = [
        "nội vụ & lao động", "xây dựng", "công thương", "y tế",
        "giáo dục và đào tạo", "văn hóa - xã hội",
        "nông nghiệp & phát triển nông thôn", "tài nguyên & môi trường"
    ]

    @classmethod
    def check_scope(cls, text: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Kiểm tra câu hỏi có thuộc phạm vi giải quyết của hệ thống hay không.
        
        Args:
            text: Nội dung câu hỏi.
            
        Returns:
            Tuple[bool, str, Dict[str, Any]]:
                - is_violation: True nếu câu hỏi nằm ngoài phạm vi dữ liệu DWH.
                - message: Lời giải thích và hướng dẫn tra cứu đúng phạm vi.
                - details: Chi tiết kỹ thuật.
        """
        details = {}
        clean_text = text.strip()

        # 1. Kiểm tra các câu hỏi ngoại vực dị biệt (dầu khí Lâm Đồng, giải trí...)
        out_match = cls._RE_OUT_OF_SCOPE_SPECIFIC.search(clean_text)
        if out_match:
            details["pattern"] = "geographical_or_domain_mismatch"
            details["matched_topic"] = out_match.group(0)
            
            # Xử lý riêng biệt ca dầu khí Lâm Đồng
            if "dầu khí" in clean_text.lower() or "giàn khoan" in clean_text.lower():
                return (
                    True,
                    "Thông tin phạm vi: Tỉnh Lâm Đồng thuộc khu vực Tây Nguyên, không giáp biển và không có hoạt động khai thác dầu khí ngoài khơi, nằm ngoài phạm vi dữ liệu của hệ thống. "
                    "Kho dữ liệu DWH không có số liệu về chỉ tiêu này. Bạn có thể tra cứu các lĩnh vực thế mạnh của tỉnh như: Nông nghiệp, Khuyến công, An toàn lao động hoặc Xây dựng.",
                    details
                )
            
            return (
                True,
                "Yêu cầu nằm ngoài phạm vi dữ liệu của Hệ thống Trợ lý ảo Tra cứu DWH Chính phủ điện tử. "
                "Hệ thống chỉ hỗ trợ 8 lĩnh vực quản lý nhà nước số hóa.",
                details
            )

        # 2. Kiểm tra thủ tục hành chính công (CCCD, hộ chiếu...)
        proc_match = cls._RE_ADMINISTRATIVE_PROCEDURE.search(clean_text)
        if proc_match:
            details["pattern"] = "administrative_procedure"
            details["matched_topic"] = proc_match.group(0)
            return (
                True,
                "Thông tin phạm vi: Câu hỏi của đồng chí thuộc nhóm Thủ tục Hành chính Công (Dịch vụ công trực tuyến). "
                "Hệ thống hiện tại chuyên trách tra cứu Kho Dữ Liệu Báo Cáo Điều Hành (DWH). "
                "Đồng chí vui lòng tra cứu thủ tục này tại Cổng Dịch vụ công Quốc gia (dichvucong.gov.vn) hoặc Hệ thống Thông tin Giải quyết Thủ tục Hành chính tỉnh Lâm Đồng.",
                details
            )

        # 3. Kiểm tra thời tiết, đời sống, du lịch
        weather_match = cls._RE_WEATHER_LIFESTYLE.search(clean_text)
        if weather_match:
            details["pattern"] = "weather_lifestyle"
            details["matched_topic"] = weather_match.group(0)
            return (
                True,
                "Thông tin phạm vi: Câu hỏi về thời tiết, đời sống nằm ngoài phạm vi phục vụ của Hệ thống Trợ lý ảo Tra cứu Kho Dữ Liệu DWH tỉnh Lâm Đồng. "
                "Đồng chí vui lòng tra cứu thông tin dự báo thời tiết tại Đài Khí tượng Thủy văn hoặc các ứng dụng chuyên dụng.",
                details
            )

        # 4. Kiểm tra nhân sự chính trị ngoài DWH
        pol_match = cls._RE_POLITICAL_LEADERSHIP.search(clean_text)
        if pol_match:
            details["pattern"] = "political_leadership_out_of_scope"
            details["matched_topic"] = pol_match.group(0)
            return (
                True,
                "Thông tin phạm vi: Thông tin về nhân sự cấp ủy, lãnh đạo Tỉnh ủy/Chính trị nằm ngoài phạm vi dữ liệu quản lý báo cáo chuyên môn của Kho DWH. "
                "Hệ thống chỉ quản lý danh mục phân công nhiệm vụ chuyên môn của cán bộ công chức thuộc các sở ban ngành theo các đề án và kỳ báo cáo đã phê duyệt.",
                details
            )

        # 5. Kiểm tra tác vụ sáng tác tự do
        gen_match = cls._RE_CREATIVE_GENERATIVE.search(clean_text)
        if gen_match:
            details["pattern"] = "generative_task_out_of_scope"
            details["matched_topic"] = gen_match.group(0)
            return (
                True,
                "Thông tin phạm vi: Yêu cầu sáng tác văn bản, soạn bài phát biểu nằm ngoài phạm vi của Trợ lý ảo Tra cứu DWH. "
                "Hệ thống chuyên trách cung cấp số liệu thống kê, danh mục báo cáo và nhiệm vụ điều hành chính quyền số.",
                details
            )

        # 6. Kiểm tra câu hỏi định tính chủ quan
        qual_match = cls._RE_QUALITATIVE_APPRAISAL.search(clean_text)
        if qual_match:
            details["pattern"] = "qualitative_appraisal_out_of_scope"
            details["matched_topic"] = qual_match.group(0)
            return (
                True,
                "Thông tin phạm vi: Hệ thống Trợ lý ảo DWH cung cấp số liệu thực tế được trích xuất nguyên trạng từ các báo cáo đã được phê duyệt chính thức trong kho dữ liệu, "
                "không đưa ra nhận định hoặc đánh giá định tính chủ quan về mức độ tin cậy của các cơ quan ban ngành.",
                details
            )

        return (False, "", {})
