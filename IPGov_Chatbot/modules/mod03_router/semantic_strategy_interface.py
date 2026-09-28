"""
IPGov Chatbot - Module 03: Semantic Strategy Interface Contract
Tuân thủ Strategy Pattern theo quy tắc Rule 9 và Blueprints 02_ROUTER_SPEC.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from IPGov_Chatbot.schemas.router_dto import (
    IntentEnum,
    RouteTypeEnum,
    SlotClarificationOption,
)


class SemanticMatchResult(BaseModel):
    """Kết quả đối sánh định lượng từ một Strategy Router."""
    model_config = ConfigDict(frozen=True)

    confidence_score: float = Field(default=0.0, description="Điểm tin cậy [0.0 - 1.0]")
    matched_track: Optional[RouteTypeEnum] = Field(None, description="Routing track phù hợp")
    intent: Optional[IntentEnum] = Field(None, description="Ý định phân loại")
    extracted_slots: Dict[str, Any] = Field(default_factory=dict, description="Các slots trích xuất được")
    candidate_options: List[SlotClarificationOption] = Field(default_factory=list, description="Các action chips đề xuất nếu cần làm rõ")
    dag_archetype: Optional[str] = Field(None, description="Mẫu hình DAG nếu là DYNAMIC_PARALLEL_DAG")
    subquery_count: Optional[int] = Field(None, description="Số subquery dự kiến")
    complexity: Optional[str] = Field(None, description="Mức độ phức tạp")
    bypass_response: Optional[str] = Field(None, description="Câu trả lời trực tiếp từ metadata catalog")
    action_chips: List[str] = Field(default_factory=list, description="Danh sách nhãn Action Chips gợi ý")
    explanation: Optional[str] = Field(None, description="Giải thích lý do khớp")


class SemanticRouterStrategy(ABC):
    """Giao diện trừu tượng của Tầng Ngữ nghĩa Tổng quát."""

    @abstractmethod
    def evaluate(self, text: str, context: Optional[Any] = None) -> SemanticMatchResult:
        """
        Thực hiện đánh giá định lượng cho một câu truy vấn văn bản.
        """
        pass
