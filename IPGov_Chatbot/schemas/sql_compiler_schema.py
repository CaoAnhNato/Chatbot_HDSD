"""
Module: IPGov_Chatbot/schemas/sql_compiler_schema.py
Chức năng: Khế ước dữ liệu DTO cho Module 05 Text-to-SQL Compiler & Scatter-Gather Engine.
Căn cứ:
- Blueprint: 05_MULTI_AGENT_WORKFLOW_DIN_MAC_SQL.md
- Specification: IPGov_Chatbot/docs/MODULE_05_SQL_COMPILER_SPEC.md
- Tuân thủ: Pydantic v2 strict mode (extra="forbid"), Arc42, IEEE Std 1016-2009.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class SQLExecutionMode(str, Enum):
    """Chế độ thực thi truy vấn SQL được chọn bởi SQL Compiler."""
    SINGLE_UNIFIED = "SINGLE_UNIFIED"       # Đẩy gộp 1 query có Window Functions / CTEs (Ưu tiên)
    SCATTER_GATHER = "SCATTER_GATHER"       # Phân rã N queries song song (Trường hợp đặc thù)
    BYPASS_ZERO_SQL = "BYPASS_ZERO_SQL"     # Không sinh SQL (Discovery / Chitchat / Out-of-Scope)


class SubqueryTaskItem(BaseModel):
    """Mỗi tác vụ truy vấn con khi thực thi ở chế độ Scatter-Gather."""
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(..., description="Định danh duy nhất của tác vụ con")
    sql: str = Field(..., description="Câu lệnh SQL riêng biệt cho tác vụ")
    target_metric: Optional[str] = Field(None, description="Mã chỉ tiêu tương ứng")
    target_period: Optional[str] = Field(None, description="Kỳ thời gian tương ứng")
    target_entity: Optional[str] = Field(None, description="Thực thể hành chính tương ứng")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tham số ràng buộc")


class MetricFilter(BaseModel):
    """Bộ lọc chỉ tiêu trong Track A Deterministic Compiler."""
    model_config = ConfigDict(extra="forbid")

    field: str = Field(..., description="Tên trường lọc (e.g. 'year', 'department_code')")
    operator: Literal["eq", "in", "gte", "lte"] = Field(..., description="Toán tử so sánh")
    value: Any = Field(..., description="Giá trị so sánh")


class MetricSpecDTO(BaseModel):
    """Đặc tả chỉ tiêu chuẩn tắc cho Track A Deterministic Semantic AST Compiler."""
    model_config = ConfigDict(extra="forbid")

    metric_code: str = Field(..., description="Mã chỉ tiêu kỹ thuật (e.g. 'kinh_phi_khuyen_cong')")
    metric_name: Optional[str] = Field(None, description="Tên tiếng Việt của chỉ tiêu")
    aggregation_func: Literal["SUM", "COUNT", "AVG", "MIN", "MAX"] = Field(
        default="SUM", description="Hàm tổng hợp SQL"
    )
    grain: Literal["leaf_criteria", "department", "office"] = Field(
        default="leaf_criteria", description="Độ mịn tính toán"
    )
    filters: List[MetricFilter] = Field(
        default_factory=list, description="Danh sách các bộ lọc bổ trợ"
    )
    group_by: List[str] = Field(
        default_factory=lambda: ["year"], description="Các cột gom nhóm"
    )


class TextToSQLStructuredOutput(BaseModel):
    """
    Hợp đồng đầu ra của LLM Text-to-SQL Generator (Node 4b) với Chain-of-Thought.
    Ép kiểu nghiêm ngặt (extra="forbid") phục vụ call_structured_with_fallback.
    """
    model_config = ConfigDict(extra="forbid")

    thought_scratchpad: str = Field(
        ...,
        description="Suy luận từng bước về JOINs, điều kiện lọc, chỉ tiêu và phân quyền"
    )
    sql_query: str = Field(
        ...,
        description="Câu lệnh SELECT PostgreSQL 16 chuẩn cú pháp"
    )
    tables_used: List[str] = Field(
        ...,
        description="Danh sách các bảng/view vật lý được sử dụng"
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Độ tin cậy tự đánh giá của mô hình (ngưỡng >= 0.70)"
    )
    sql_ast_explanation: Optional[str] = Field(
        default=None,
        description="Giải thích cấu trúc cây AST và các vị từ lọc"
    )


class GeneratedSQLDTO(BaseModel):
    """
    Hợp đồng dữ liệu đầu ra toàn diện của Module 05 (Stage 5 SQL Generation).
    Được truyền tiếp sang Module 06 (AST Security Guardrails) và Module 07 (DWH Executor).
    """
    model_config = ConfigDict(extra="forbid")

    raw_sql: str = Field(
        ...,
        description="Câu lệnh SQL hoàn chỉnh sẵn sàng cho AST Enforcer"
    )
    execution_mode: SQLExecutionMode = Field(
        default=SQLExecutionMode.SINGLE_UNIFIED,
        description="Chế độ thực thi: Single Unified SQL hay Scatter-Gather"
    )
    dag_archetype: Optional[str] = Field(
        default=None,
        description="Tên Archetype Kimball được áp dụng (e.g. TEMPORAL_COMPARISON, RANKING_TOP_K...)"
    )
    subquery_tasks: List[SubqueryTaskItem] = Field(
        default_factory=list,
        description="Danh sách task con nếu thực thi ở chế độ Scatter-Gather"
    )
    tables_referenced: List[str] = Field(
        default_factory=list,
        description="Danh sách các bảng vật lý được truy vấn"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Các tham số ràng buộc an toàn (nếu có)"
    )
    generator_track: Literal["TRACK_A_COMPILER", "TRACK_B_LLM"] = Field(
        ...,
        description="Nhánh xử lý: Track A tất định (85%) hay Track B LLM (15%)"
    )
    thought_scratchpad: Optional[str] = Field(
        default=None,
        description="Chuỗi suy luận Chain-of-Thought nếu sinh qua Track B"
    )
    llm_provider: Optional[str] = Field(
        default=None,
        description="Mô hình LLM đã sinh SQL (e.g. google/gemini-3.5-flash-lite, google/gemini-3.8-flash)"
    )
    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Độ tin cậy tổng thể của câu lệnh SQL sinh ra"
    )
    fallback_triggered: bool = Field(
        default=False,
        description="Cờ ghi nhận có phải kích hoạt Heavy Fallback Stage 2 không"
    )
    prompt_cache_hit: bool = Field(
        default=False,
        description="Cờ ghi nhận Cache Hit tại LLM Gateway"
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Số lần tự sửa lỗi (0, 1, 2)"
    )
    ast_valid: bool = Field(
        default=True,
        description="Đã vượt qua kiểm duyệt cú pháp AST PostgreSQL 16"
    )
    latency_ms: float = Field(
        default=0.0,
        description="Thời gian xử lý của Module 05 (miligiây)"
    )
    trace_id: str = Field(
        default="",
        description="Trace ID phân tán"
    )
