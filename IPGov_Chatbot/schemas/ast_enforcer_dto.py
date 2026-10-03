"""
Module: IPGov_Chatbot/schemas/ast_enforcer_dto.py
Chức năng: Khế ước dữ liệu DTO cho Module 06 Security Guardrails & AST Enforcer.
Căn cứ:
- Blueprint: 04_SECURITY_GUARDRAILS_VA_AST_ENFORCEMENT.md
- Specification: IPGov_Chatbot/docs/MODULE_06_AST_ENFORCER_SPEC.md
- Tuân thủ: Pydantic v2 strict mode (extra="forbid"), Arc42, IEEE Std 1016-2009.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from IPGov_Chatbot.schemas.sql_compiler_schema import SQLExecutionMode


class ASTViolationType(str, Enum):
    """Phân loại các hành vi vi phạm an ninh tầng AST."""
    NONE = "NONE"
    DDL_DML_MUTATION = "DDL_DML_MUTATION"
    FORBIDDEN_TABLE = "FORBIDDEN_TABLE"
    INVALID_SYNTAX = "INVALID_SYNTAX"
    SEMANTIC_INJECTION = "SEMANTIC_INJECTION"
    MULTIPLE_STATEMENTS = "MULTIPLE_STATEMENTS"
    OUT_OF_SCOPE_CROSS_TENANT = "OUT_OF_SCOPE_CROSS_TENANT"


class SecurityViolationDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    violation_type: ASTViolationType = Field(..., description="Phân loại vi phạm an ninh")
    error_message: str = Field(..., description="Thông điệp mô tả chi tiết lỗi an ninh")
    raw_sql: str = Field(..., description="Câu lệnh SQL nguyên bản gây ra vi phạm")
    forbidden_tokens: List[str] = Field(default_factory=list, description="Danh sách các token/bảng vi phạm")
    trace_id: str = Field(default="", description="Trace ID phân tán")


class SanitizedSubqueryTaskItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(..., description="Định danh duy nhất của tác vụ con")
    sql: str = Field(..., description="Câu lệnh SQL sau khi làm sạch và tiêm HBAC")
    target_metric: Optional[str] = Field(None, description="Mã chỉ tiêu tương ứng")
    target_period: Optional[str] = Field(None, description="Kỳ thời gian tương ứng")
    target_entity: Optional[str] = Field(None, description="Thực thể hành chính tương ứng")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tham số ràng buộc an toàn")


class SanitizedSQLDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_sql: str = Field(..., description="Câu SQL ban đầu từ Module 05")
    sanitized_sql: str = Field(..., description="Câu SQL sau khi bọc ngoặc, tiêm HBAC và LIMIT 500")
    execution_mode: SQLExecutionMode = Field(
        default=SQLExecutionMode.SINGLE_UNIFIED,
        description="Chế độ thực thi: Single Unified, Scatter-Gather hoặc Bypass"
    )
    hbac_injected: bool = Field(default=True, description="Xác nhận đã tiêm vị từ phân quyền HBAC")
    predicates_added: List[str] = Field(
        default_factory=list,
        description="Danh sách các vị từ đã tiêm"
    )
    tables_validated: List[str] = Field(
        default_factory=list,
        description="Danh sách các bảng vật lý được phép trong Whitelist"
    )
    subquery_tasks: List[SanitizedSubqueryTaskItem] = Field(
        default_factory=list,
        description="Danh sách các task con đã làm sạch nếu chạy Scatter-Gather"
    )
    is_safe: bool = Field(default=True, description="Cờ xác nhận an toàn tuyệt đối")
    ast_valid: bool = Field(default=True, description="Đạt chuẩn cú pháp PostgreSQL 16")
    latency_ms: float = Field(default=0.0, description="Thời gian xử lý của Module 06 trong RAM (ms)")
    trace_id: str = Field(default="", description="Trace ID phân tán")
