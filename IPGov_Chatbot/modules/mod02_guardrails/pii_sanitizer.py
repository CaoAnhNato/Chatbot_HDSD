"""
Module: IPGov_Chatbot/modules/mod02_guardrails/pii_sanitizer.py
Chức năng: Phát hiện và ngăn chặn dữ liệu định danh cá nhân (PII) theo Nghị định 13/2023/NĐ-CP.
Tối ưu hóa bằng pre-compiled regex trong RAM để đạt tốc độ xử lý < 5ms.
"""

import re
from typing import Dict, Any, Tuple


class PIISanitizer:
    """Bộ lọc dữ liệu cá nhân nhạy cảm (PII Filter)."""

    # 1. Regex phát hiện số Căn cước công dân (12 chữ số) và CMND (9 chữ số)
    # Hỗ trợ cả trường hợp có hoặc không có dấu phân cách (khoảng trắng, gạch ngang, dấu chấm)
    _RE_CCCD = re.compile(
        r"(?:"
        r"\b\d{12}\b|"
        r"\b\d{3}[\s\.\-]\d{3}[\s\.\-]\d{3}[\s\.\-]\d{3}\b|"
        r"\b\d{4}[\s\.\-]\d{4}[\s\.\-]\d{4}\b|"
        r"\b\d{3}[\s\.\-]\d{3}[\s\.\-]\d{6}\b|"
        r"\b\d{3}[\s\.\-]\d{1}[\s\.\-]\d{2}[\s\.\-]\d{6}\b|"
        r"\b\d{9}\b|"
        r"\b\d{3}[\s\.\-]\d{3}[\s\.\-]\d{3}\b|"
        r"(?:cccd|cmnd|căn cước(?:\s+công dân)?|chứng minh(?:\s+nhân dân)?)\s*[:=\-]?\s*(?:\d[\s\.\-]?){9,12}\b"
        r")",
        re.IGNORECASE
    )

    # 2. Regex phát hiện số điện thoại cá nhân Việt Nam
    # Hỗ trợ đầu số: +84, 03, 05, 07, 08, 09 kèm 7 chữ số tiếp theo (tổng 10 số)
    _RE_PHONE = re.compile(
        r"(?:(?:\+84|0)(?:3[2-9]|5[25689]|7[0-9]|8[1-9]|9[0-9])(?:[\s\.\-]?\d){7}\b|"
        r"(?:sđt|số điện thoại|điện thoại cá nhân|mobile|phone)\s*[:=\-]?\s*(?:\+84|0)?[0-9\s\.\-]{8,14}\b)",
        re.IGNORECASE
    )

    # 3. Regex phát hiện Số tài khoản ngân hàng, mã số thuế cá nhân, tài khoản VNeID
    _RE_FINANCIAL_OR_VNEID = re.compile(
        r"(?:(?:\bstk\b|số tài khoản|tài khoản ngân hàng|mã định danh\s+vneid|\bvneid\b)\s*[:=\-]?\s*[A-Z0-9]{6,20}|"
        r"\b(?:ngân hàng|vietcombank|techcombank|vietinbank|agribank|bidv|mbbank)\s+stk\s*[:=\-]?\s*\d{6,20}\b)",
        re.IGNORECASE
    )

    # 4. Từ khóa định danh cá nhân cần ngăn chặn khi hỏi thông tin riêng tư cán bộ
    _RE_PII_SOLICITATION = re.compile(
        r"(?:xin\s+(?:số\s+)?(?:điện\s+thoại|sđt)|"
        r"(?:kèm\s+theo\s+)?số\s+(?:căn\s+cước(?:\s+công\s+dân)?|cccd|cmnd|chứng\s+minh(?:\s+nhân\s+dân)?)|"
        r"\bcccd\s+(?:lanh\s+dao|lãnh\s+đạo|can\s+bo|cán\s+bộ|ubnd)\b|"
        r"số\s+(?:cccd|căn\s+cước|cmnd|chứng\s+minh)(?:\s+của|\s*\(cccd\))|"
        r"số\s+tài\s+khoản\s+(?:ngân\s+hàng\s+)?cá\s+nhân|"
        r"mã\s+định\s+danh\s+vneid|"
        r"số\s+điện\s+thoại\s+(?:và|kèm)\s+số\s+cccd)",
        re.IGNORECASE
    )

    @classmethod
    def detect_pii(cls, text: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Kiểm tra câu hỏi có chứa hoặc yêu cầu thông tin định danh cá nhân hay không.
        
        Args:
            text: Nội dung câu hỏi của người dùng.
            
        Returns:
            Tuple[bool, str, Dict[str, Any]]:
                - is_violation: True nếu phát hiện PII.
                - message: Thông báo cảnh báo vi phạm.
                - details: Chi tiết loại PII được nhận diện.
        """
        details = {}
        
        # Kiểm tra hành vi xin số điện thoại / CCCD cá nhân
        if cls._RE_PII_SOLICITATION.search(text):
            details["pattern"] = "pii_solicitation"
            return (
                True,
                "Yêu cầu bị từ chối: Không được phép thu thập hoặc tra cứu số điện thoại, CCCD hoặc thông tin cá nhân của cán bộ theo quy định bảo vệ bí mật đời tư công vụ (Nghị định 13/2023/NĐ-CP).",
                details
            )

        # Kiểm tra số CCCD / CMND cụ thể
        cccd_match = cls._RE_CCCD.search(text)
        if cccd_match:
            details["pattern"] = "cccd_detected"
            details["matched_snippet"] = cccd_match.group(0)[:6] + "******"
            return (
                True,
                "Yêu cầu bị từ chối do chứa số Căn cước công dân/CMND. Hệ thống không xử lý dữ liệu định danh cá nhân theo Nghị định 13/2023/NĐ-CP.",
                details
            )

        # Kiểm tra Số điện thoại cụ thể
        phone_match = cls._RE_PHONE.search(text)
        if phone_match:
            details["pattern"] = "phone_detected"
            details["matched_snippet"] = phone_match.group(0)[:4] + "****"
            return (
                True,
                "Yêu cầu bị từ chối do chứa hoặc yêu cầu số điện thoại cá nhân theo quy định của Nghị định 13/2023/NĐ-CP.",
                details
            )

        # Kiểm tra Số tài khoản / VNeID
        fin_match = cls._RE_FINANCIAL_OR_VNEID.search(text)
        if fin_match:
            details["pattern"] = "bank_or_vneid_detected"
            return (
                True,
                "Yêu cầu bị từ chối: Không được phép truy vấn hoặc cung cấp số tài khoản ngân hàng hoặc mã định danh VNeID cá nhân.",
                details
            )

        return (False, "", {})
