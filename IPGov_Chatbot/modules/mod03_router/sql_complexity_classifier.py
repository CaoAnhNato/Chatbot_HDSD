"""
IPGov Chatbot - Module 03: SQL Complexity Classifier
Phân loại cấp độ phức tạp SQL theo DIN-SQL & MAC-SQL:
- LOW_TEMPLATE: Truy vấn chỉ tiêu đơn chuẩn tắc -> TEMPLATE_FAST_TRACK
- HIGH_PARALLEL_DAG: Truy vấn phân tích đa chiều -> DYNAMIC_PARALLEL_DAG
- MEDIUM_SINGLE_SQL: Truy vấn ad-hoc kiểm toán dữ liệu rác, rỗng, NULL -> SINGLE_SQL
"""

from __future__ import annotations
import re
from typing import Optional, Tuple

from IPGov_Chatbot.schemas.router_dto import IntentEnum


class SQLComplexityClassifier:
    """Bộ phân loại độ phức tạp câu truy vấn SQL."""

    def __init__(self) -> None:
        # Nhận diện các mẫu câu hỏi ad-hoc audit, đối soát dữ liệu rác/null/rỗng/bất thường
        self._adhoc_audit_pat = re.compile(
            r"\b(null hoac rong|null target|bi null|gia tri null|null hoac zero|value null|bi rong|rong hoac null|data dump|raw sql|ad-hoc|ad hoc|để trống hoặc bằng 0|de trong hoac bang 0|để trống hoặc ghi nhận bằng 0|trùng lặp nhiều dòng|trùng lặp|trễ hạn bất thường|thời hạn kết thúc trong tháng|thanh tra và kiểm toán tuân thủ quy chế nộp báo cáo)\b",
            re.IGNORECASE
        )
        self._adhoc_short_syntax_pat = re.compile(
            r"^(ds\s+.*(null|rong|zero)|select\s+|kiem toan\s+.*(null|rong|zero)|bc\s+.*(null|zero))",
            re.IGNORECASE
        )

    def classify_ad_hoc(self, text: str) -> Tuple[bool, Optional[str], Optional[IntentEnum]]:
        """
        Kiểm tra xem câu hỏi có thuộc nhóm ad-hoc kiểm toán ngoài catalog chuẩn hay không.
        Trả về: (is_adhoc, complexity, intent)
        """
        raw = text.strip()
        low = raw.lower()

        if self._adhoc_audit_pat.search(low) or self._adhoc_short_syntax_pat.search(low):
            return True, "MEDIUM_SINGLE_SQL", IntentEnum.COMPLEX_RAW_SQL

        return False, None, None
