"""
IPGov Chatbot - Module 03 Data Transfer Objects & Enums
Căn cứ: Blueprints 00_CORE, 02_ROUTER, 05_MULTI_AGENT, 07_STREAMING_UX
Tuân thủ: .agents/rules/ipgov-coding-rules.md (Pydantic v2, Immutable/Frozen DTOs)
"""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class RouteTypeEnum(str, Enum):
    CHITCHAT_BYPASS = "CHITCHAT_BYPASS"
    CATALOG_DISCOVERY = "CATALOG_DISCOVERY"
    TEMPLATE_FAST_TRACK = "TEMPLATE_FAST_TRACK"
    SINGLE_SQL = "SINGLE_SQL"
    DYNAMIC_PARALLEL_DAG = "DYNAMIC_PARALLEL_DAG"
    CLARIFICATION = "CLARIFICATION"
    SECURITY_DENIAL = "SECURITY_DENIAL"


class IntentEnum(str, Enum):
    GREETING = "GREETING"
    GRATITUDE = "GRATITUDE"
    FAREWELL = "FAREWELL"
    PRAISE = "PRAISE"
    STATUS_INQUIRY = "STATUS_INQUIRY"
    META_CAPABILITY = "META_CAPABILITY"
    SCOPE_DISCOVERY = "SCOPE_DISCOVERY"
    TEMPORAL_WINDOW = "TEMPORAL_WINDOW"
    METRIC_DEFINITION = "METRIC_DEFINITION"
    FORM_CATALOG = "FORM_CATALOG"
    HBAC_DISCOVERY = "HBAC_DISCOVERY"
    EXPORT_CAPABILITY = "EXPORT_CAPABILITY"
    REPORT_STATUS_POLICY = "REPORT_STATUS_POLICY"
    DATA_FRESHNESS = "DATA_FRESHNESS"
    USER_ONBOARDING = "USER_ONBOARDING"
    FAST_METRIC_COMPILER = "FAST_METRIC_COMPILER"
    COMPLEX_DAG_ANALYTICS = "COMPLEX_DAG_ANALYTICS"
    COMPLEX_RAW_SQL = "COMPLEX_RAW_SQL"
    CLARIFICATION_NEEDED = "CLARIFICATION_NEEDED"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    SECURITY_DENIAL = "SECURITY_DENIAL"


class PersonaEnum(str, Enum):
    EXECUTIVE = "EXECUTIVE"
    SPECIALIST = "SPECIALIST"
    CITIZEN = "CITIZEN"
    AUDITOR = "AUDITOR"
    COLLOQUIAL = "COLLOQUIAL"
    JUNIOR = "JUNIOR"


class QuestStatusEnum(str, Enum):
    PENDING_SLOTS = "PENDING_SLOTS"
    COMMITTED = "COMMITTED"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class QuestActionEnum(str, Enum):
    INIT = "INIT"
    PRESERVE = "PRESERVE"
    TEARDOWN = "TEARDOWN"
    CLARIFY = "CLARIFY"
    COMMIT = "COMMIT"
    REFUSE = "REFUSE"


class SlotTypeEnum(str, Enum):
    TEMPORAL = "temporal"
    METRIC_CODE = "metric_code"
    ADMIN_ENTITY = "admin_entity"
    COMPARISON_TARGET = "comparison_target"
    DISAMBIGUATION = "disambiguation"
    OUT_OF_SCOPE = "out_of_scope"


class SlotClarificationOption(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: str = Field(..., description="Nhãn hiển thị trên nút bấm")
    slot_key: str = Field(..., description="Khóa slot cần điền")
    value: Any = Field(..., description="Giá trị được gán khi người dùng click")
    preview_description: Optional[str] = Field(None, description="Mô tả bổ trợ")


class ActiveQuestFrameDTO(BaseModel):
    model_config = ConfigDict(frozen=False)

    quest_id: str = Field(..., description="Mã định danh duy nhất của Quest")
    intent: Optional[str] = Field(None, description="Ý định hiện thời")
    status: QuestStatusEnum = Field(default=QuestStatusEnum.PENDING_SLOTS, description="Trạng thái quest")
    admin_entity: Optional[str] = Field(None, description="Tên thực thể hành chính")
    admin_level: Optional[int] = Field(None, description="Cấp hành chính")
    temporal_val: Optional[str] = Field(None, description="Thời gian")
    metric_code: Optional[str] = Field(None, description="Mã hoặc tên chỉ tiêu")
    comparison_year: Optional[str] = Field(None, description="Năm đối chuẩn")
    extra_slots: Dict[str, Any] = Field(default_factory=dict, description="Các slot bổ trợ khác")
    missing_slots: List[str] = Field(default_factory=list, description="Danh sách tên slot còn thiếu")
    slot_types_missing: List[SlotTypeEnum] = Field(default_factory=list, description="Nhóm slot thiếu")
    candidate_clarifications: List[SlotClarificationOption] = Field(default_factory=list, description="Các chip gợi ý")
    confidence_score: float = Field(default=1.0, description="Độ tin cậy của frame")
    turn_count: int = Field(default=1, description="Số lượt tương tác trong quest này")
    last_updated_turn: int = Field(default=1, description="Lượt cập nhật gần nhất")

    @field_validator("admin_level", mode="before")
    @classmethod
    def coerce_admin_level(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            mapping = {"province": 0, "district": 1, "commune": 2, "ward": 2}
            return mapping.get(v.lower(), 1)
        return int(v)


class SessionEpisodicMemoryDTO(BaseModel):
    model_config = ConfigDict(frozen=False)

    session_id: str = Field(..., description="Mã định danh phiên làm việc")
    frequent_entities: List[str] = Field(default_factory=list, description="Thực thể thường xuyên truy vấn")
    default_temporal_window: str = Field(default="2025", description="Năm mặc định ưu tiên")
    preferred_output_format: Literal["TABLE", "TEXT", "CHART"] = Field(default="TABLE", description="Định dạng ưu tiên")
    committed_quest_history: List[str] = Field(default_factory=list, description="Lịch sử các quest đã hoàn thành")
    ttl_seconds: int = Field(default=3600, description="Thời gian sống của bộ nhớ phiên (giây)")
    last_updated_at: Optional[str] = Field(None, description="Dấu thời gian ISO")


class RouterOutputDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str = Field(..., description="Mã phiên làm việc")
    query_sanitized: str = Field(..., description="Câu hỏi đã qua kiểm duyệt bảo mật Module 2")
    route: RouteTypeEnum = Field(..., description="Đường dẫn định tuyến chính")
    routing_track: Optional[str] = Field(None, description="Tên đường dẫn định tuyến dạng chuỗi")
    intent: IntentEnum = Field(..., description="Ý định được phân loại")
    persona: PersonaEnum = Field(default=PersonaEnum.SPECIALIST, description="Persona người dùng")
    confidence_score: float = Field(default=1.0, description="Độ tin cậy định tuyến")
    tokens_used: int = Field(default=0, description="Số token LLM tiêu tốn")
    zero_llm_token: bool = Field(default=True, description="Cờ xác nhận zero LLM token")
    zero_sql: bool = Field(default=True, description="Cờ xác nhận zero SQL query")
    safety_timeout_seconds: float = Field(default=5.0, description="Ngưỡng timeout phòng vệ kỹ thuật chống bế tắc")
    sla_max_latency_ms: Optional[float] = Field(default=10.0, description="Deprecated")
    latency_ms: float = Field(default=0.0, description="Độ trễ đo đạc thực tế")
    dag_archetype: Optional[str] = Field(None, description="Mẫu hình phân tích DAG")
    subquery_count: Optional[int] = Field(None, description="Số lượng subqueries song song")
    complexity: Optional[str] = Field(None, description="Cấp độ phức tạp")
    active_quest: Optional[ActiveQuestFrameDTO] = Field(None, description="Khung quest hiện hành")
    active_quest_preserved: bool = Field(default=False, description="Cờ bảo lưu quest")
    active_quest_action: QuestActionEnum = Field(default=QuestActionEnum.INIT, description="Hành động quest")
    bypass_response: Optional[str] = Field(None, description="Nội dung trả lời trực tiếp nếu bypass")
    action_chips: List[str] = Field(default_factory=list, description="Các action chip tương tác")
    missing_slots: List[str] = Field(default_factory=list, description="Danh sách tên slot thiếu")
    clarification_options: List[SlotClarificationOption] = Field(default_factory=list, description="Chi tiết options làm rõ")

    @property
    def action(self) -> str:
        return self.active_quest_action.value if self.active_quest_action else ""
