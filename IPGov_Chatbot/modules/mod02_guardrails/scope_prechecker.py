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

        # 1. Kiểm tra các câu hỏi ngoại vực dị biệt (dầu khí Lâm Đồng, giải trí...)
        out_match = cls._RE_OUT_OF_SCOPE_SPECIFIC.search(text)
        if out_match:
            details["pattern"] = "geographical_or_domain_mismatch"
            details["matched_topic"] = out_match.group(0)
            
            # Xử lý riêng biệt ca dầu khí Lâm Đồng
            if "dầu khí" in text.lower() or "giàn khoan" in text.lower():
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

        return (False, "", {})
