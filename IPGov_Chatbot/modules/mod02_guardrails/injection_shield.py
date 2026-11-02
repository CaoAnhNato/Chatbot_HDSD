"""
Module: IPGov_Chatbot/modules/mod02_guardrails/injection_shield.py
Chức năng: Phát hiện và chặn đứng tấn công Prompt Injection, Jailbreaking và các lệnh phá hoại DDL/DML.
SLA: < 2ms (Duyệt từ khóa tĩnh và cấu trúc AST tiền kiểm).
"""

import re
from typing import Dict, Any, Tuple


class InjectionShield:
    """Hàng rào ngăn chặn can thiệp phá hoại CSDL và thao túng LLM."""

    # 1. Các lệnh DDL / DML nguy hiểm tuyệt đối bị cấm tại tầng Gateway
    _RE_DDL_DML = re.compile(
        r"(?:\b(?:drop\s+table|drop\s+database|truncate\s+table|delete\s+from|alter\s+table|"
        r"create\s+table|grant\s+all|revoke\s+all|insert\s+into|update\s+[a-zA-Z0-9_\.]+\s+set)\b|"
        r"\b(?:xóa\s+(?:bỏ\s+)?dữ\s+liệu|hủy\s+biên\s+bản|xóa\s+(?:bỏ\s+)?biên\s+bản|sửa\s+dữ\s+liệu|chỉnh\s+sửa\s+báo\s+cáo|can\s+thiệp\s+csdl)\b|"
        r"\b(?:chạy\s+lệnh\s+cập\s+nhật|cập\s+nhật\s+(?:lại\s+)?.*?\b(?:trong\s+(?:db|database|csdl))|sửa\s+lại\s+.*?\b(?:trong\s+(?:db|database|csdl))|"
        r"copy\s+.*?\bsang\s+.*?\b(?:trong\s+(?:db|database|csdl))|xóa\s*(?:\(delete\)\s*)?(?:các\s+)?bản\s+ghi\b.*?\b(?:khỏi\s+(?:db|database|csdl)))\b|"
        r"(?:;|['\"]|\b(?:select|update|delete|drop|insert|alter|truncate|exec|union|where|from|having)\b)\s*--|\/\*|\*\/)",
        re.IGNORECASE
    )

    # 1b. Các mẫu khai thác cấu trúc bảng hệ thống nội bộ và thông tin định danh / kết nối CSDL
    _RE_SCHEMA_CREDENTIAL_EXFIL = re.compile(
        r"(?:\b(?:information_schema(?:\.tables|\.columns)?|pg_catalog|pg_shadow|pg_authid|current_user|session_user|connection\s+string)\b|"
        r"\b(?:chuỗi\s+kết\s+nối|tài\s+khoản\s+đăng\s+nhập\s+(?:db|database|csdl)|mật\s+khẩu\s+(?:db|database|csdl))\b)",
        re.IGNORECASE
    )

    # 2. Các mẫu tấn công Prompt Injection / Jailbreaking
    _RE_PROMPT_INJECTION = re.compile(
        r"(?:\b(?:ignore\s+all\s+previous\s+instructions|system\s+prompt|jailbreak|bypass\s+rules|"
        r"act\s+as\s+admin|you\s+are\s+now|DAN\s+mode|unfiltered)\b|"
        r"(?:bỏ\s+qua\s+(?:toàn\s+bộ|mọi)\s+(?:chỉ\s+dẫn|quy\s+tắc)|tiết\s+lộ\s+prompt|quên\s+hết\s+quy\s+tắc|đóng\s+vai\s+quản\s+trị\s+viên))",
        re.IGNORECASE
    )

    @classmethod
    def detect_injection(cls, text: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Kiểm tra câu hỏi có chứa hành vi phá hoại CSDL hoặc Prompt Injection không.
        
        Args:
            text: Nội dung câu hỏi.
            
        Returns:
            Tuple[bool, str, Dict[str, Any]]:
                - is_violation: True nếu phát hiện hành vi tấn công.
                - message: Thông báo từ chối an toàn.
                - details: Chi tiết kỹ thuật vi phạm để đẩy vào DLQ.
        """
        details = {}

        # 1. Kiểm tra DDL / DML
        ddl_match = cls._RE_DDL_DML.search(text)
        if ddl_match:
            details["violation"] = "destructive_sql_command"
            details["matched_pattern"] = ddl_match.group(0)
            return (
                True,
                "CẢNH BÁO AN NINH: Hệ thống từ chối yêu cầu chứa câu lệnh sửa đổi, sao chép hoặc xóa dữ liệu (DDL/DML: UPDATE, INSERT, DELETE). "
                "Trợ lý ảo chỉ vận hành ở chế độ chỉ đọc (Read-Only) để bảo toàn tính toàn vẹn của Kho Dữ Liệu (DWH). "
                "Để cập nhật hoặc chỉnh sửa số liệu báo cáo, đề nghị đồng chí thực hiện trực tiếp trên giao diện phần mềm nhập liệu nguồn theo đúng quy trình phê duyệt.",
                details
            )

        # 1b. Kiểm tra khai thác cấu trúc hệ thống nội bộ / thông tin kết nối nhạy cảm
        exfil_match = cls._RE_SCHEMA_CREDENTIAL_EXFIL.search(text)
        if exfil_match:
            details["violation"] = "schema_or_credential_exfiltration"
            details["matched_pattern"] = exfil_match.group(0)
            return (
                True,
                "CẢNH BÁO AN NINH: Hệ thống từ chối cung cấp thông tin cấu trúc bảng hệ thống nội bộ, tài khoản đăng nhập CSDL hoặc chuỗi kết nối bảo mật. "
                "Trợ lý ảo chỉ hỗ trợ tra cứu số liệu báo cáo kinh tế - xã hội công vụ trong phạm vi được phân quyền.",
                details
            )

        # 2. Kiểm tra Prompt Injection
        inj_match = cls._RE_PROMPT_INJECTION.search(text)
        if inj_match:
            details["violation"] = "prompt_injection_attempt"
            details["matched_pattern"] = inj_match.group(0)
            return (
                True,
                "Yêu cầu bị từ chối do vi phạm chính sách an toàn hệ thống (Phát hiện mẫu Prompt Injection).",
                details
            )

        return (False, "", {})
