"""
IPGov Chatbot - Module 04 Data Transfer Objects & Schemas
Căn cứ: Blueprints 03_SEMANTIC_LAYER_MDL_VA_IN_MEMORY_CATALOG.md
Tuân thủ: .agents/rules/ipgov-coding-rules.md (Pydantic v2, Immutable/Frozen DTOs)
"""

from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class JoinPathDTO(BaseModel):
    """Định nghĩa đường dẫn liên kết giữa hai bảng trên đồ thị quan hệ khóa ngoại."""
    model_config = ConfigDict(frozen=True)

    source_table: str = Field(..., description="Bảng nguồn (vd: dwh_internal.fact_report_criteria)")
    target_table: str = Field(..., description="Bảng đích (vd: dwh_internal.office)")
    on_clause: str = Field(..., description="Mệnh đề liên kết ON (vd: f.office_id = office.id)")
    join_type: Literal["INNER JOIN", "LEFT JOIN", "RIGHT JOIN"] = Field(
        default="INNER JOIN", description="Kiểu phép JOIN"
    )


class ColumnMetadataDTO(BaseModel):
    """Siêu dữ liệu chi tiết của từng cột thuộc bảng DWH."""
    model_config = ConfigDict(frozen=True)

    column_name: str
    data_type: str
    description: str = ""
    is_pk: bool = False
    is_fk: bool = False
    fk_target_table: Optional[str] = None
    fk_target_column: Optional[str] = None


class TableMetadataDTO(BaseModel):
    """Siêu dữ liệu cấp bảng."""
    model_config = ConfigDict(frozen=True)

    table_name: str
    schema_name: str = "dwh_internal"
    description: str = ""
    columns: List[ColumnMetadataDTO] = Field(default_factory=list)
    primary_key: Optional[str] = None
    row_count_estimate: int = 0


class CatalogPrunedDTO(BaseModel):
    """
    Khế ước DTO đầu ra của Module 04 (Stage 4).
    Chứa lát cắt Schema tối thiểu, bảng cầu nối bổ sung và các hợp đồng nghiệp vụ cho Module 05;
    hoặc chứa phản hồi trực tiếp cho câu hỏi Khám phá Năng lực (Discovery).
    """
    model_config = ConfigDict(frozen=True)

    selected_tables: List[str] = Field(
        default_factory=list, description="Danh sách các bảng DWH được chọn sau khi kết nối qua Steiner Tree"
    )
    bridge_tables: List[str] = Field(
        default_factory=list, description="Danh sách các bảng cầu nối (Bridge Tables) được tự động bổ sung"
    )
    join_paths: List[JoinPathDTO] = Field(
        default_factory=list, description="Các mệnh đề ON JOIN giữa các bảng trong cây khung"
    )
    schema_slice_ddl: str = Field(
        default="", description="Lát cắt DDL tối thiểu cung cấp cho bộ sinh Text-to-SQL"
    )
    data_contracts: List[str] = Field(
        default_factory=list, description="Các quy tắc hợp đồng dữ liệu bắt buộc (NULLIF TRIM, status='approved', leaf_criteria)"
    )
    discovery_response: Optional[str] = Field(
        default=None, description="Câu trả lời công vụ hoàn chỉnh nếu là câu hỏi Capability Discovery"
    )
    suggested_action_chips: List[str] = Field(
        default_factory=list, description="Danh sách nút bấm Interactive Action Chips gợi ý cho người dùng"
    )
    latency_ms: float = Field(
        default=0.0, description="Thời gian thực thi trích xuất và lọc catalog (miligiây)"
    )
    trace_id: str = Field(
        default="", description="Trace ID phân tán"
    )
    confidence_score: float = Field(
        default=1.0, description="Độ tin cậy của thuật toán so khớp ngữ nghĩa"
    )
