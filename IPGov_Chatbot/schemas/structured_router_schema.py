"""
Schema: IPGov_Chatbot/schemas/structured_router_schema.py
Đặc tả Pydantic v2 Strict Mode cho Groq Cloud Structured Outputs.
Tuân thủ chuẩn strict mode (extra='forbid', tất cả trường tường minh, không dùng Any).
"""

from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


class TemporalScopeSchema(BaseModel):
    """Lược đồ bóc tách phạm vi thời gian."""
    model_config = ConfigDict(extra="forbid")

    raw_expression: Optional[str] = Field(None, description="Cụm từ chỉ thời gian gốc trong câu hỏi")
    start_year: Optional[int] = Field(None, description="Năm bắt đầu khảo sát (ví dụ 2025)")
    end_year: Optional[int] = Field(None, description="Năm kết thúc nếu là khoảng thời gian hoặc so sánh đa kỳ (ví dụ 2026)")
    quarter: Optional[int] = Field(None, description="Quý (1 đến 4) nếu được nêu rõ")


class SpatialScopeSchema(BaseModel):
    """Lược đồ bóc tách phạm vi địa bàn hành chính."""
    model_config = ConfigDict(extra="forbid")

    location_name: Optional[str] = Field(None, description="Tên địa phương: Đà Lạt, Bảo Lộc, Di Linh, Đức Trọng...")
    admin_level: Optional[str] = Field("province", description="Cấp hành chính: 'province', 'district', 'commune'")

    @field_validator("admin_level", mode="before")
    @classmethod
    def coerce_admin_level(cls, v):
        if not v:
            return "province"
        return v


TemporalScopeDTO = TemporalScopeSchema
SpatialScopeDTO = SpatialScopeSchema


class LLMRouterStructuredOutput(BaseModel):
    """Lược đồ đầu ra bắt buộc của LLM Router (OpenRouter & DashScope)."""
    model_config = ConfigDict(extra="forbid")

    thought_scratchpad: Optional[str] = Field(
        None,
        description="Suy luận ngắn gọn 1-2 câu về bản chất câu hỏi, thực thể, và sự có mặt của mốc năm.",
    )
    confidence_score: Optional[float] = Field(
        1.0,
        description="Mức độ tự tin của mô hình đối với phân loại và trích xuất (0.0 đến 1.0).",
    )
    intent: str = Field(
        ...,
        description="Định tuyến ý định: CHITCHAT_BYPASS, CATALOG_DISCOVERY, TEMPLATE_FAST_TRACK, DYNAMIC_PARALLEL_DAG, SINGLE_SQL, CLARIFICATION, SECURITY_DENIAL, OUT_OF_SCOPE"
    )
    dag_archetype: Optional[str] = Field(
        None,
        description="Nếu là DYNAMIC_PARALLEL_DAG: TEMPORAL_COMPARISON, CROSS_GEO_COMPARISON, MULTI_METRIC_DRILLDOWN, COMPONENT_BREAKDOWN, PIPELINE_STATUS"
    )
    subquery_count: Optional[int] = Field(
        1,
        description="Số lượng subqueries cần phân rã (1 đến 5)"
    )

    @field_validator("subquery_count", mode="before")
    @classmethod
    def coerce_subquery_count(cls, v):
        if v is None:
            return 1
        return v
    complexity: str = Field(
        "LOW_TEMPLATE",
        description="Độ phức tạp thực thi: LOW_TEMPLATE, MEDIUM_SINGLE_SQL, hoặc HIGH_PARALLEL_DAG"
    )
    temporal_scope: Optional[TemporalScopeSchema] = Field(
        None,
        description="Thông tin phạm vi thời gian trích xuất được"
    )
    spatial_scope: Optional[SpatialScopeSchema] = Field(
        None,
        description="Thông tin phạm vi địa bàn trích xuất được"
    )
    dwh_entities: List[str] = Field(
        default_factory=list,
        description="Danh sách các chỉ tiêu, báo cáo, biểu mẫu nghiệp vụ được nhắc tới"
    )
    candidate_clarification_chips: List[str] = Field(
        default_factory=list,
        description="Danh sách các nhãn nút bấm gợi ý làm rõ nếu có"
    )
    is_ambiguous: bool = Field(
        False,
        description="True nếu câu hỏi mơ hồ, thiếu mốc thời gian hoặc thiếu địa bàn cụ thể cần hỏi lại"
    )
    is_topic_shift: bool = Field(
        False,
        description="True nếu câu hỏi chuyển sang một lĩnh vực/chủ đề nghiệp vụ mới hoàn toàn khác với lượt trước"
    )
    clarification_reason: Optional[str] = Field(
        None,
        description="Lý do cần kích hoạt câu hỏi làm rõ nếu is_ambiguous là True"
    )

    @field_validator("complexity", mode="before")
    @classmethod
    def coerce_complexity(cls, v):
        if not v:
            return "LOW_TEMPLATE"
        return v

    @field_validator("is_ambiguous", "is_topic_shift", mode="before")
    @classmethod
    def coerce_booleans(cls, v):
        if v is None:
            return False
        return bool(v)

    @field_validator("dwh_entities", "candidate_clarification_chips", mode="before")
    @classmethod
    def coerce_lists(cls, v):
        if v is None:
            return []
        return v

    @field_validator("confidence_score", mode="before")
    @classmethod
    def coerce_confidence(cls, v):
        if v is None:
            return 1.0
        try:
            val = float(v)
            return max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            return 1.0

    @field_validator("thought_scratchpad", mode="before")
    @classmethod
    def coerce_scratchpad(cls, v):
        if v is None:
            return None
        return str(v).strip()

