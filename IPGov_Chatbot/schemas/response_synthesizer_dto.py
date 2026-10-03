"""
Khế ước DTO chuẩn cho Module 08: Response Synthesizer & Lineage Badge
Tuân thủ Pydantic v2 (extra="forbid"), Blueprint 07 và SSOT.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RenderModeEnum(str, Enum):
    """Chế độ render câu trả lời tổng hợp."""
    DETERMINISTIC_TEMPLATE = "DETERMINISTIC_TEMPLATE"
    LLM_SYNTHESIS = "LLM_SYNTHESIS"
    EMPTY_NOTIFICATION = "EMPTY_NOTIFICATION"
    ERROR_NOTIFICATION = "ERROR_NOTIFICATION"


class ColumnAlignEnum(str, Enum):
    """Quy chuẩn căn lề cột."""
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class ColumnTypeEnum(str, Enum):
    """Kiểu dữ liệu cột hiển thị."""
    TEXT = "text"
    NUMBER = "number"
    BADGE = "badge"
    DATE = "date"


class TableColumnDTO(BaseModel):
    """Đặc tả siêu dữ liệu của một cột trong bảng số liệu."""
    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., description="Định danh duy nhất của cột (slug)")
    label: str = Field(..., description="Tiêu đề hiển thị tiếng Việt chuẩn công vụ")
    align: ColumnAlignEnum = Field(default=ColumnAlignEnum.LEFT, description="Hướng căn lề")
    data_type: ColumnTypeEnum = Field(default=ColumnTypeEnum.TEXT, description="Kiểu dữ liệu để render component")


class TabularDataDTO(BaseModel):
    """
    Cấu trúc dữ liệu bảng đã chuẩn hóa (Semantic Tabular Contract).
    Phục vụ render Smart Table tại Frontend và xuất file CSV/Excel.
    """
    model_config = ConfigDict(extra="forbid")

    columns: List[TableColumnDTO] = Field(..., description="Danh sách cấu hình các cột")
    rows: List[Dict[str, Any]] = Field(..., description="Dữ liệu các dòng (chứa cả raw value và formatted)")
    total_records: int = Field(default=0, ge=0, description="Tổng số bản ghi thực tế trong CSDL")
    title: Optional[str] = Field(None, description="Tiêu đề mô tả bảng nếu có")


class LineageBadgeDTO(BaseModel):
    """
    Thẻ chứng minh nguồn gốc dữ liệu (Data Provenance & Audit Trail)
    Được đính kèm trong mọi câu trả lời có số liệu từ kho DWH.
    """
    model_config = ConfigDict(extra="forbid")

    department_code: str = Field(..., description="Mã cơ quan chủ quản, ví dụ: '79', '79-1-01', '68'")
    department_name: str = Field(..., description="Tên cơ quan, ví dụ: 'UBND Tỉnh Lâm Đồng', 'Sở Nội Vụ'")
    office_id: Optional[str] = Field(None, description="UUID phòng ban trực thuộc nếu có")
    office_name: Optional[str] = Field(None, description="Tên phòng ban trực thuộc nếu có")
    criteria_code: str = Field(default="", description="Mã chỉ tiêu chính tham gia tính toán")
    criteria_name: str = Field(default="", description="Tên chỉ tiêu chính tham gia tính toán")
    report_period: str = Field(..., description="Kỳ báo cáo, ví dụ: '2024', '2025', 'Q1/2025'")
    operational_signoff_date: Optional[str] = Field(None, description="Thời điểm phê duyệt ký số")
    dwh_pipeline_synced_at: Optional[str] = Field(None, description="Thời điểm ETL đồng bộ vào kho DWH")
    report_status: str = Field(default="approved", description="Trạng thái báo cáo pháp lý (mặc định 'approved')")
    record_count: int = Field(default=0, ge=0, description="Số dòng Fact thực tế tham gia tính toán")
    verification_hash: str = Field(..., description="Mã SHA-256 xác thực bất biến của bản ghi tổng hợp")


class SynthesizerOutputDTO(BaseModel):
    """
    Kết quả tổng hợp câu trả lời từ Module 08 sẵn sàng phục vụ người dùng.
    """
    model_config = ConfigDict(extra="forbid")

    content: str = Field(..., description="Nội dung câu trả lời chuẩn BLUF (1 dòng kết luận + bảng markdown + nhận xét)")
    render_mode: RenderModeEnum = Field(..., description="Phương thức sinh câu trả lời")
    lineage_badge: Optional[LineageBadgeDTO] = Field(None, description="Thẻ nguồn gốc dữ liệu")
    table_rendered: bool = Field(default=False, description="Cờ đánh dấu có bảng Markdown được render hay không")
    tabular_data: Optional[TabularDataDTO] = Field(None, description="Dữ liệu bảng có cấu trúc chuẩn hóa cho Smart Table")
    latency_ms: float = Field(default=0.0, ge=0.0, description="Thời gian xử lý của Module 08 (ms)")
    tokens_used: int = Field(default=0, ge=0, description="Số token LLM đã tiêu thụ (0 nếu render qua Jinja2)")
    trace_id: str = Field(default="", description="Mã định danh trace phiên làm việc")
