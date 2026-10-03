"""
Module: IPGov_Chatbot/schemas/dwh_exec_dto.py
Chức năng: Khế ước dữ liệu DTO cho Module 07 DWH Execution Engine.
Căn cứ:
- Blueprint: 01_DATA_WAREHOUSE_VA_CAY_THUC_THE_DWH.md
- Blueprint: 06_OBSERVABILITY_TRACING_DLQ_VA_EVALUATION.md
- Specification: IPGov_Chatbot/docs/MODULE_07_DWH_EXEC_SPEC.md
- Tuân thủ: Pydantic v2 strict mode (extra="forbid"), Arc42, IEEE Std 1016-2009.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from IPGov_Chatbot.schemas.sql_compiler_schema import SQLExecutionMode


class ExecutionStatusEnum(str, Enum):
    SUCCESS = "SUCCESS"
    EMPTY = "EMPTY"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"
    BYPASS = "BYPASS"


class ColumnMetadataDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Tên trường dữ liệu")
    data_type: str = Field(..., description="Kiểu dữ liệu phía PostgreSQL (e.g. text, numeric, int4, timestamptz)")


class SubqueryResultItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(..., description="Định danh tác vụ con tương ứng")
    columns: List[ColumnMetadataDTO] = Field(default_factory=list, description="Siêu dữ liệu các cột")
    rows: List[Dict[str, Any]] = Field(default_factory=list, description="Dữ liệu các dòng đã làm sạch")
    row_count: int = Field(default=0, ge=0, description="Số lượng dòng kết quả")
    execution_time_ms: float = Field(default=0.0, description="Thời gian thực thi tác vụ con (ms)")
    status: ExecutionStatusEnum = Field(default=ExecutionStatusEnum.SUCCESS, description="Trạng thái thực thi")
    error_message: Optional[str] = Field(None, description="Chi tiết lỗi nếu tác vụ con thất bại")


class QueryResultDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    columns: List[ColumnMetadataDTO] = Field(default_factory=list, description="Danh sách cột và kiểu dữ liệu")
    rows: List[Dict[str, Any]] = Field(default_factory=list, description="Dữ liệu các bản ghi chuẩn hóa JSON primitives")
    row_count: int = Field(default=0, ge=0, description="Số dòng kết quả thực tế")
    execution_time_ms: float = Field(default=0.0, description="Độ trễ thực thi trên Docker CSDL (ms)")
    execution_mode: SQLExecutionMode = Field(
        default=SQLExecutionMode.SINGLE_UNIFIED,
        description="Chế độ thực thi: Single Unified, Scatter-Gather hoặc Bypass"
    )
    is_empty: bool = Field(default=False, description="True nếu không có bản ghi nào khớp (0 dòng)")
    warning_message: Optional[str] = Field(None, description="Cảnh báo nghiệp vụ")
    subquery_results: List[SubqueryResultItem] = Field(
        default_factory=list,
        description="Danh sách kết quả con nếu chạy Scatter-Gather"
    )
    status: ExecutionStatusEnum = Field(
        default=ExecutionStatusEnum.SUCCESS,
        description="Trạng thái thực thi tổng thể"
    )
    error_code: Optional[str] = Field(None, description="Mã lỗi PostgreSQL")
    error_message: Optional[str] = Field(None, description="Thông điệp chi tiết lỗi (nếu có)")
    executed_sql: str = Field(default="", description="Câu lệnh SQL thực tế đã gửi xuống CSDL")
    trace_id: str = Field(default="", description="Trace ID phân tán")
