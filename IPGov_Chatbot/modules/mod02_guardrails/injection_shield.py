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
        r"--\s*|\/\*|\*\/)",
        re.IGNORECASE
    )

    # 2. Các mẫu tấn công Prompt Injection / Jailbreaking
    _RE_PROMPT_INJECTION = re.compile(
        r"(?:\b(?:ignore\s+all\s+previous\s+instructions|system\s+prompt|jailbreak|bypass\s+rules|"
        r"act\s+as\s+admin|you\s+are\s+now|DAN\s+mode|unfiltered)\b|"
        r"(?:bỏ\s+qua\s+toàn\s+bộ\s+chỉ\s+dẫn|tiết\s+lộ\s+prompt|quên\s+hết\s+quy\s+tắc|đóng\s+vai\s+quản\s+trị\s+viên))",
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
                "CẢNH BÁO AN NINH: Hệ thống từ chối yêu cầu chứa câu lệnh sửa đổi hoặc xóa dữ liệu (DDL/DML). "
                "Trợ lý ảo chỉ vận hành ở chế độ Read-Only tra cứu số liệu công vụ.",
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
