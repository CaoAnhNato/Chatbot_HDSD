"""
IPGov Chatbot - Module 03 Data Transfer Objects & Enums
Căn cứ: Blueprints 00_CORE, 02_ROUTER, 05_MULTI_AGENT, 07_STREAMING_UX
Tuân thủ: .agents/rules/ipgov-coding-rules.md (Pydantic v2, Immutable/Frozen DTOs)
"""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# 1. ENUMS
# ---------------------------------------------------------------------------

class RouteTypeEnum(str, Enum):
    """Phân loại đường dẫn định tuyến chính (Routing Track)."""
    CHITCHAT_BYPASS = "CHITCHAT_BYPASS"         # Xã giao công vụ siêu tốc (< 2ms, zero token LLM, zero SQL)
    CATALOG_DISCOVERY = "CATALOG_DISCOVERY"     # Khám phá danh mục & năng lực (< 50ms, zero SQL fact)
    TEMPLATE_FAST_TRACK = "TEMPLATE_FAST_TRACK" # 85% traffic - Biên dịch chỉ số đơn sang SQL template
    SINGLE_SQL = "SINGLE_SQL"                   # Text-to-SQL phi quy chuẩn 1 bước
    DYNAMIC_PARALLEL_DAG = "DYNAMIC_PARALLEL_DAG" # Phân tích đa chiều / N sub-queries song song
    CLARIFICATION = "CLARIFICATION"             # Hỏi làm rõ khi khuyết thiếu slot hoặc đa nghĩa
    SECURITY_DENIAL = "SECURITY_DENIAL"         # Chặn truy cập vượt thẩm quyền HBAC / vi phạm PII / SQLi


class IntentEnum(str, Enum):
    """Phân loại ý định chi tiết của câu hỏi."""
    # Nhóm Chitchat Bypass
    GREETING = "GREETING"
    GRATITUDE = "GRATITUDE"
    FAREWELL = "FAREWELL"
    PRAISE = "PRAISE"
    STATUS_INQUIRY = "STATUS_INQUIRY"

    # Nhóm Discovery
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

    # Nhóm Nghiệp vụ & Điều hướng
    FAST_METRIC_COMPILER = "FAST_METRIC_COMPILER"
    COMPLEX_DAG_ANALYTICS = "COMPLEX_DAG_ANALYTICS"
    COMPLEX_RAW_SQL = "COMPLEX_RAW_SQL"
    CLARIFICATION_NEEDED = "CLARIFICATION_NEEDED"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    SECURITY_DENIAL = "SECURITY_DENIAL"


class PersonaEnum(str, Enum):
    """6 Personas người dùng công vụ theo đặc tả hệ thống."""
    EXECUTIVE = "EXECUTIVE"     # Lãnh đạo cấp Tỉnh/Sở (ngắn gọn, tổng quan, định dạng dashboard)
    SPECIALIST = "SPECIALIST"   # Chuyên viên phòng ban (chi tiết, bảng biểu, công thức)
    CITIZEN = "CITIZEN"         # Người dân / Doanh nghiệp (dễ hiểu, giải thích tường minh)
    AUDITOR = "AUDITOR"         # Kiểm toán / Thanh tra (đối chiếu, nguồn gốc, freshness)
    COLLOQUIAL = "COLLOQUIAL"   # Khẩu ngữ, ngôn ngữ đời thường
    JUNIOR = "JUNIOR"           # Cán bộ mới tiếp cận hệ thống


class QuestStatusEnum(str, Enum):
    """Trạng thái vòng đời Quest trong kiến trúc 2-Tier Quest State Machine."""
    PENDING_SLOTS = "PENDING_SLOTS"  # Đang thiếu slot, chờ người dùng bổ sung qua chip/chat
    COMMITTED = "COMMITTED"          # Đủ slot, sẵn sàng chuyển sang tầng biên dịch SQL
    RESOLVED = "RESOLVED"            # Đã thực thi xong và trả kết quả
    CANCELLED = "CANCELLED"          # Người dùng hủy bỏ hoặc đổi đề tài (Topic Shift)


class QuestActionEnum(str, Enum):
    """Hành động tác động lên Active Quest Frame trong RAM."""
    INIT = "INIT"           # Khởi tạo quest mới
    PRESERVE = "PRESERVE"   # Giữ nguyên khung quest hiện tại cho lượt tiếp theo
    TEARDOWN = "TEARDOWN"   # Dọn dẹp/giải phóng khung quest trong RAM
    CLARIFY = "CLARIFY"     # Yêu cầu bổ sung slot làm rõ
    COMMIT = "COMMIT"       # Đủ điều kiện chuyển sang thực thi
    REFUSE = "REFUSE"       # Từ chối vì lý do bảo mật/ngoài phạm vi


class SlotTypeEnum(str, Enum):
    """Phân loại 6 nhóm slot khuyết thiếu trong khung hội thoại H-DFT."""
    TEMPORAL = "temporal"                   # Thiếu năm, quý, tháng, khoảng thời gian
    METRIC_CODE = "metric_code"             # Thiếu mã chỉ tiêu chi tiết
    ADMIN_ENTITY = "admin_entity"           # Thiếu đơn vị (Sở, Phòng ban, UBND, Huyện/Xã)
    COMPARISON_TARGET = "comparison_target" # Thiếu mốc đối chuẩn / so sánh cùng kỳ (YoY)
    DISAMBIGUATION = "disambiguation"       # Thực thể đa nghĩa / trùng tên
    OUT_OF_SCOPE = "out_of_scope"           # Nằm ngoài phạm vi CSDL


# ---------------------------------------------------------------------------
# 2. DATA TRANSFER OBJECTS (Pydantic v2 Immutable DTOs)
# ---------------------------------------------------------------------------

class SlotClarificationOption(BaseModel):
    """Đặc tả nút bấm tương tác (Interactive Action Chip) làm rõ slot."""
    model_config = ConfigDict(frozen=True)

    label: str = Field(..., description="Nhãn hiển thị trên nút bấm (ví dụ: 'Năm 2025')")
    slot_key: str = Field(..., description="Khóa slot cần điền (ví dụ: 'year', 'criteria_code')")
    value: Any = Field(..., description="Giá trị được gán khi người dùng click")
    preview_description: Optional[str] = Field(None, description="Mô tả bổ trợ")


class ActiveQuestFrameDTO(BaseModel):
    """Tầng 1: Khung Quest hiện tại đang được theo dõi trên RAM (H-DFT State)."""
    model_config = ConfigDict(frozen=False)

    quest_id: str = Field(..., description="Mã định danh duy nhất của Quest")
    intent: Optional[str] = Field(None, description="Ý định hiện thời")
    status: QuestStatusEnum = Field(default=QuestStatusEnum.PENDING_SLOTS, description="Trạng thái quest")
    
    # Các slots đã thu thập
    admin_entity: Optional[str] = Field(None, description="Tên thực thể hành chính (Tỉnh/Huyện/Phòng)")
    admin_level: Optional[int] = Field(None, description="Cấp hành chính (0: Tỉnh, 1: Huyện, 2: Phòng/Xã)")
    temporal_val: Optional[str] = Field(None, description="Thời gian (ví dụ: '2025', '2026', 'Q3/2026')")
    metric_code: Optional[str] = Field(None, description="Mã hoặc tên chỉ tiêu nghiệp vụ")
    comparison_year: Optional[str] = Field(None, description="Năm đối chuẩn (nếu so sánh)")
    extra_slots: Dict[str, Any] = Field(default_factory=dict, description="Các slot bổ trợ khác")
    
    # Trạng thái thiếu slot
    missing_slots: List[str] = Field(default_factory=list, description="Danh sách tên slot còn thiếu")
    slot_types_missing: List[SlotTypeEnum] = Field(default_factory=list, description="Nhóm slot thiếu")
    candidate_clarifications: List[SlotClarificationOption] = Field(default_factory=list, description="Các chip gợi ý làm rõ")
    
    # Metadata theo dõi hội thoại
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
    """Tầng 2: Hồ sơ ngữ cảnh bền vững của cả phiên làm việc (temp_memory)."""
    model_config = ConfigDict(frozen=False)

    session_id: str = Field(..., description="Mã định danh phiên làm việc")
    frequent_entities: List[str] = Field(default_factory=list, description="Thực thể thường xuyên truy vấn")
    default_temporal_window: str = Field(default="2025", description="Năm mặc định ưu tiên (2025 chốt duyệt)")
    preferred_output_format: Literal["TABLE", "TEXT", "CHART"] = Field(default="TABLE", description="Định dạng ưu tiên")
    committed_quest_history: List[str] = Field(default_factory=list, description="Lịch sử các quest đã hoàn thành")
    ttl_seconds: int = Field(default=3600, description="Thời gian sống của bộ nhớ phiên (giây)")
    last_updated_at: Optional[str] = Field(None, description="Dấu thời gian ISO")


class RouterOutputDTO(BaseModel):
    """Kết quả định tuyến toàn diện của Module 3 (Stage 3 Snapshot Contract)."""
    model_config = ConfigDict(frozen=True)

    session_id: str = Field(..., description="Mã phiên làm việc")
    query_sanitized: str = Field(..., description="Câu hỏi đã qua kiểm duyệt bảo mật Module 2")
    
    # Kết quả định tuyến
    route: RouteTypeEnum = Field(..., description="Đường dẫn định tuyến chính (RouteTypeEnum)")
    routing_track: Optional[str] = Field(None, description="Tên đường dẫn định tuyến dạng chuỗi")
    intent: IntentEnum = Field(..., description="Ý định được phân loại")
    persona: PersonaEnum = Field(default=PersonaEnum.SPECIALIST, description="Persona người dùng")
    confidence_score: float = Field(default=1.0, description="Độ tin cậy định tuyến")
    
    # Thông tin tài nguyên và SLA (Nguyên tắc MVP Rule 8: Zero SLA constraints, Safety Timeout = 5.0s)
    tokens_used: int = Field(default=0, description="Số token LLM tiêu tốn (0 cho bypass)")
    zero_llm_token: bool = Field(default=True, description="Cờ xác nhận zero LLM token")
    zero_sql: bool = Field(default=True, description="Cờ xác nhận zero SQL query")
    safety_timeout_seconds: float = Field(default=5.0, description="Ngưỡng timeout phòng vệ kỹ thuật chống bế tắc (s)")
    sla_max_latency_ms: Optional[float] = Field(default=10.0, description="Deprecated - Giữ tương thích ngược")
    latency_ms: float = Field(default=0.0, description="Độ trễ đo đạc thực tế (ms)")
    
    # Phân loại độ phức tạp & DAG Archetype (MAC-SQL & DIN-SQL)
    dag_archetype: Optional[str] = Field(None, description="Mẫu hình phân tích DAG (TEMPORAL_COMPARISON, RANKING_TOP_K,...)")
    subquery_count: Optional[int] = Field(None, description="Số lượng subqueries song song")
    complexity: Optional[str] = Field(None, description="Cấp độ phức tạp (LOW_TEMPLATE, HIGH_PARALLEL_DAG, MEDIUM_SINGLE_SQL)")
    
    # Tương tác H-DFT & Khung Quest
    active_quest: Optional[ActiveQuestFrameDTO] = Field(None, description="Khung quest hiện hành")
    active_quest_preserved: bool = Field(default=False, description="Cờ bảo lưu quest")
    active_quest_action: QuestActionEnum = Field(default=QuestActionEnum.INIT, description="Hành động quest")
    
    # Phản hồi tức thời (cho Chitchat hoặc Capability Bypass)
    bypass_response: Optional[str] = Field(None, description="Nội dung trả lời trực tiếp nếu bypass")
    action_chips: List[str] = Field(default_factory=list, description="Các action chip tương tác dạng text")
    missing_slots: List[str] = Field(default_factory=list, description="Danh sách tên slot thiếu")
    clarification_options: List[SlotClarificationOption] = Field(default_factory=list, description="Chi tiết options làm rõ")

    @property
    def action(self) -> str:
        """Alias cho active_quest_action value (phục vụ verification_rule)."""
        return self.active_quest_action.value if self.active_quest_action else ""
