"""
IPGov Chatbot - Module 04 Data Transfer Objects & Schemas
Căn cứ: Blueprints 03_SEMANTIC_LAYER_MDL_VA_IN_MEMORY_CATALOG.md
Tuân thủ: .agents/rules/ipgov-coding-rules.md (Pydantic v2, Immutable/Frozen DTOs)
"""

from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class JoinPathDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_table: str = Field(..., description="Bảng nguồn")
    target_table: str = Field(..., description="Bảng đích")
    on_clause: str = Field(..., description="Mệnh đề liên kết ON")
    join_type: Literal["INNER JOIN", "LEFT JOIN", "RIGHT JOIN"] = Field(
        default="INNER JOIN", description="Kiểu phép JOIN"
    )


class ColumnMetadataDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    column_name: str
    data_type: str
    description: str = ""
    is_pk: bool = False
    is_fk: bool = False
    fk_target_table: Optional[str] = None
    fk_target_column: Optional[str] = None


class TableMetadataDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    table_name: str
    schema_name: str = "dwh_internal"
    description: str = ""
    columns: List[ColumnMetadataDTO] = Field(default_factory=list)
    primary_key: Optional[str] = None
    row_count_estimate: int = 0


class CatalogPrunedDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    selected_tables: List[str] = Field(
        default_factory=list, description="Danh sách các bảng DWH được chọn"
    )
    bridge_tables: List[str] = Field(
        default_factory=list, description="Danh sách các bảng cầu nối"
    )
    join_paths: List[JoinPathDTO] = Field(
        default_factory=list, description="Các mệnh đề ON JOIN giữa các bảng trong cây khung"
    )
    schema_slice_ddl: str = Field(
        default="", description="Lát cắt DDL tối thiểu cung cấp cho bộ sinh Text-to-SQL"
    )
    data_contracts: List[str] = Field(
        default_factory=list, description="Các quy tắc hợp đồng dữ liệu bắt buộc"
    )
    discovery_response: Optional[str] = Field(
        default=None, description="Câu trả lời công vụ hoàn chỉnh nếu là câu hỏi Capability Discovery"
    )
    suggested_action_chips: List[str] = Field(
        default_factory=list, description="Danh sách nút bấm Interactive Action Chips gợi ý"
    )
    latency_ms: float = Field(
        default=0.0, description="Thời gian thực thi trích xuất và lọc catalog"
    )
    trace_id: str = Field(
        default="", description="Trace ID phân tán"
    )
    confidence_score: float = Field(
        default=1.0, description="Độ tin cậy của thuật toán so khớp ngữ nghĩa"
    )
