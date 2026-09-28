"""
IPGov Chatbot - Module 03: Persona Classifier
Phân loại 6 Personas công vụ phục vụ thích ứng văn phong và định dạng phản hồi.
Căn cứ: Blueprints 02_ROUTER_SPEC, 07_ADVANCED_REASONING
"""

from __future__ import annotations
import re
from typing import Tuple

from IPGov_Chatbot.schemas.router_dto import PersonaEnum


class PersonaClassifier:
    """
    Phân loại Persona người dùng dựa trên từ vựng công vụ và cấu trúc câu hỏi.
    - EXECUTIVE (Lãnh đạo cấp Tỉnh/Sở)
    - SPECIALIST (Chuyên viên cấp Sở/Phòng ban)
    - CITIZEN (Người dân / Doanh nghiệp)
    - AUDITOR (Kiểm toán / Thanh tra công vụ)
    - COLLOQUIAL (Giao tiếp thường nhật / Khẩu ngữ)
    - JUNIOR (Cán bộ mới nhận nhiệm vụ)
    """

    def __init__(self) -> None:
        self._rules = [
            (
                PersonaEnum.JUNIOR,
                re.compile(r"\b(cán bộ mới|mới vào|người mới|hướng dẫn bắt đầu|bắt đầu tra cứu như thế nào|lần đầu sử dụng)\b", re.IGNORECASE),
            ),
            (
                PersonaEnum.AUDITOR,
                re.compile(r"\b(kiểm toán|thanh tra|đối chiếu|đối soát|chuẩn xác|lineage|truy vết|nguồn gốc|etl|freshness|tươi mới|bất thường|sai lệch|trách nhiệm công vụ)\b", re.IGNORECASE),
            ),
            (
                PersonaEnum.EXECUTIVE,
                re.compile(r"\b(lãnh đạo|thường trực|ubnd tỉnh|ubnd thành phố|toàn tỉnh|chỉ đạo điều hành|tổng hợp ktxh|chiến lược|nghỉ thôi|tổng quan)\b", re.IGNORECASE),
            ),
            (
                PersonaEnum.CITIZEN,
                re.compile(r"\b(doanh nghiệp|người dân|công dân|thủ tục hành chính|hỏi về|cho tôi hỏi|tra cứu biểu mẫu)\b", re.IGNORECASE),
            ),
            (
                PersonaEnum.COLLOQUIAL,
                re.compile(r"\b(hello|hi\b|nhé|nhe|ạ|thế nhỉ|vậy em|chuẩn đấy|xịn|ngon|alo|nghỉ thôi)\b", re.IGNORECASE),
            ),
            (
                PersonaEnum.SPECIALIST,
                re.compile(r"\b(chuyên viên|phòng ban|báo cáo của phòng|chi tiết|kỳ trước|yoy|biểu mẫu|chỉ tiêu|mã|quyết định|số liệu|giải ngân)\b", re.IGNORECASE),
            ),
        ]

    def classify(self, text: str) -> PersonaEnum:
        """Phân loại Persona từ nội dung câu hỏi."""
        cleaned = text.strip()
        for persona, pattern in self._rules:
            if pattern.search(cleaned):
                return persona

        # Mặc định cho hệ thống hành chính công là SPECIALIST
        return PersonaEnum.SPECIALIST
