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
    DDL_DML_MUTATION = "DDL_DML_MUTATION"           # INSERT, UPDATE, DELETE, DROP, ALTER...
    FORBIDDEN_TABLE = "FORBIDDEN_TABLE"             # Truy cập pg_catalog, information_schema, bảng cấm
    INVALID_SYNTAX = "INVALID_SYNTAX"               # Lỗi cú pháp phương ngữ PostgreSQL 16
    SEMANTIC_INJECTION = "SEMANTIC_INJECTION"       # ' OR 1=1 -- cố ý bung dữ liệu
    MULTIPLE_STATEMENTS = "MULTIPLE_STATEMENTS"     # Chèn nhiều câu lệnh qua dấu chấm phẩy ;
    OUT_OF_SCOPE_CROSS_TENANT = "OUT_OF_SCOPE_CROSS_TENANT" # Vi phạm phạm vi địa bàn nghiêm trọng


class SecurityViolationDTO(BaseModel):
    """Chi tiết vi phạm an ninh khi AST Enforcer phát hiện hành vi độc hại."""
    model_config = ConfigDict(extra="forbid")

    violation_type: ASTViolationType = Field(..., description="Phân loại vi phạm an ninh")
    error_message: str = Field(..., description="Thông điệp mô tả chi tiết lỗi an ninh")
    raw_sql: str = Field(..., description="Câu lệnh SQL nguyên bản gây ra vi phạm")
    forbidden_tokens: List[str] = Field(default_factory=list, description="Danh sách các token/bảng vi phạm")
    trace_id: str = Field(default="", description="Trace ID phân tán")


class SanitizedSubqueryTaskItem(BaseModel):
    """Mỗi tác vụ con đã được làm sạch và tiêm HBAC trong chế độ Scatter-Gather."""
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(..., description="Định danh duy nhất của tác vụ con")
    sql: str = Field(..., description="Câu lệnh SQL sau khi làm sạch và tiêm HBAC")
    target_metric: Optional[str] = Field(None, description="Mã chỉ tiêu tương ứng")
    target_period: Optional[str] = Field(None, description="Kỳ thời gian tương ứng")
    target_entity: Optional[str] = Field(None, description="Thực thể hành chính tương ứng")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tham số ràng buộc an toàn")


class SanitizedSQLDTO(BaseModel):
    """
    Hợp đồng dữ liệu đầu ra của Module 06 (Stage 6 AST Enforcer).
    Đã vượt qua 5 tầng kiểm soát an ninh tất định trong RAM (< 5ms)
    và sẵn sàng gửi sang Module 07 (DWH Execution Engine).
    """
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
        description="Danh sách các vị từ đã tiêm (tenant_code, department_code, office_id, report_status)"
    )
    tables_validated: List[str] = Field(
        default_factory=list,
        description="Danh sách các bảng vật lý được phép trong Whitelist"
    )
    subquery_tasks: List[SanitizedSubqueryTaskItem] = Field(
        default_factory=list,
        description="Danh sách các task con đã làm sạch nếu chạy Scatter-Gather"
    )
    is_safe: bool = Field(default=True, description="Cờ xác nhận an toàn tuyệt đối (Security Violation Rate = 0.0%)")
    ast_valid: bool = Field(default=True, description="Đạt chuẩn cú pháp PostgreSQL 16")
    latency_ms: float = Field(default=0.0, description="Thời gian xử lý của Module 06 trong RAM (ms)")
    trace_id: str = Field(default="", description="Trace ID phân tán")
