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
    """Trạng thái thực thi truy vấn trên PostgreSQL DWH."""
    SUCCESS = "SUCCESS"     # Thực thi thành công và có dữ liệu (>= 1 dòng)
    EMPTY = "EMPTY"         # Thực thi thành công nhưng tập kết quả rỗng (0 dòng)
    ERROR = "ERROR"         # Lỗi cú pháp hoặc lỗi engine CSDL
    TIMEOUT = "TIMEOUT"     # Vượt quá statement_timeout (5000ms)
    BYPASS = "BYPASS"       # Bỏ qua truy vấn (Chitchat, Discovery, Security Denial)


class ColumnMetadataDTO(BaseModel):
    """Siêu dữ liệu về kiểu dữ liệu và định danh từng cột trong bảng kết quả."""
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Tên trường dữ liệu")
    data_type: str = Field(..., description="Kiểu dữ liệu phía PostgreSQL (e.g. text, numeric, int4, timestamptz)")


class SubqueryResultItem(BaseModel):
    """Kết quả chi tiết của từng tác vụ con trong chế độ Scatter-Gather."""
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(..., description="Định danh tác vụ con tương ứng")
    columns: List[ColumnMetadataDTO] = Field(default_factory=list, description="Siêu dữ liệu các cột")
    rows: List[Dict[str, Any]] = Field(default_factory=list, description="Dữ liệu các dòng đã làm sạch")
    row_count: int = Field(default=0, ge=0, description="Số lượng dòng kết quả")
    execution_time_ms: float = Field(default=0.0, description="Thời gian thực thi tác vụ con (ms)")
    status: ExecutionStatusEnum = Field(default=ExecutionStatusEnum.SUCCESS, description="Trạng thái thực thi")
    error_message: Optional[str] = Field(None, description="Chi tiết lỗi nếu tác vụ con thất bại")


class QueryResultDTO(BaseModel):
    """
    Hợp đồng dữ liệu đầu ra của Module 07 (Stage 7 DWH Execution Engine).
    Đóng gói kết quả truy vấn thực tế từ Docker PostgreSQL vna_wom_dev,
    sẵn sàng cung cấp làm dữ liệu đầu vào cho Module 08 (Response Synthesizer).
    """
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
    warning_message: Optional[str] = Field(None, description="Cảnh báo nghiệp vụ (e.g. số liệu pending, địa bàn chưa kết nối)")
    subquery_results: List[SubqueryResultItem] = Field(
        default_factory=list,
        description="Danh sách kết quả con nếu chạy Scatter-Gather"
    )
    status: ExecutionStatusEnum = Field(
        default=ExecutionStatusEnum.SUCCESS,
        description="Trạng thái thực thi tổng thể"
    )
    error_code: Optional[str] = Field(None, description="Mã lỗi PostgreSQL (e.g. 57014, 42P01)")
    error_message: Optional[str] = Field(None, description="Thông điệp chi tiết lỗi (nếu có)")
    executed_sql: str = Field(default="", description="Câu lệnh SQL thực tế đã gửi xuống CSDL")
    trace_id: str = Field(default="", description="Trace ID phân tán")
