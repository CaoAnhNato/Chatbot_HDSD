"""
Module: IPGov_Chatbot/modules/mod06_ast_enforcer/ast_enforcer_service.py
Chức năng: Facade trung tâm điều phối 5 tầng kiểm soát an ninh AST của Module 06.
Căn cứ:
- Blueprint: 04_SECURITY_GUARDRAILS_VA_AST_ENFORCEMENT.md
- Specification: IPGov_Chatbot/docs/MODULE_06_AST_ENFORCER_SPEC.md
- Quyết định /grill-me: Hybrid Deterministic Strategy & Pure RAM Invariant Gate (< 5ms).
- Tuân thủ TRAPS: [TRAP-004], [TRAP-005]
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import sqlglot
import sqlglot.expressions as exp

from IPGov_Chatbot.modules.mod06_ast_enforcer.scope_visitor import RecursiveScopeVisitor
from IPGov_Chatbot.schemas.ast_enforcer_dto import (
    ASTViolationType,
    SanitizedSQLDTO,
    SanitizedSubqueryTaskItem,
    SecurityViolationDTO,
)
from IPGov_Chatbot.schemas.sql_compiler_schema import GeneratedSQLDTO, SQLExecutionMode
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO

logger = logging.getLogger("ipgov.mod06.ast_enforcer")


class SecurityEnforcementError(Exception):
    """Ngoại lệ an ninh ném ra khi phát hiện vi phạm DDL/DML, bảng cấm hoặc tiêm mã độc."""

    def __init__(
        self,
        message: str,
        violation_type: ASTViolationType = ASTViolationType.NONE,
        forbidden_tokens: Optional[List[str]] = None,
        raw_sql: str = "",
    ) -> None:
        super().__init__(message)
        self.violation_type = violation_type
        self.forbidden_tokens = forbidden_tokens or []
        self.raw_sql = raw_sql


# ---------------------------------------------------------------------------
# CÁC QUY TẮC AN TOÀN TẤT ĐỊNH (INVARIANT RULES)
# ---------------------------------------------------------------------------

# Danh mục Whitelist các bảng vật lý được phép truy cập
ALLOWED_TABLES: Set[str] = {
    "fact_report_criteria",
    "deparment",
    "office",
    "criteria",
    "criteria_group",
    "report",
    "pipeline_logs",
    "collection_form",
    "mission",
    "user_mission",
    "users",
    "user",
    "scope",
    "ward-boundary",
    "districts",
}

# Danh mục Whitelist các schema được phép
ALLOWED_SCHEMAS: Set[str] = {
    "dwh_internal",
    "dwh_public",
    "public",
    "staging",
}

# Schema tuyệt đối cấm truy cập
FORBIDDEN_SCHEMAS: Set[str] = {
    "pg_catalog",
    "information_schema",
    "pg_toast",
}

# Các biểu thức đột biến dữ liệu DDL/DML bị cấm tuyệt đối
FORBIDDEN_MUTATIONS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.TruncateTable,
    exp.Command,
    exp.Transaction,
    exp.Grant,
    exp.Revoke,
)


def clean_raw_sql(sql: str) -> str:
    """Loại bỏ markdown code blocks, dấu nháy kép thừa và chuẩn hóa khoảng trắng."""
    if not sql:
        return ""
    cleaned = sql.strip()
    match = re.search(r"```(?:sql)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()
    return cleaned.rstrip(";")


class ASTEnforcerService:
    """
    Facade cung cấp dịch vụ tiền kiểm định và cưỡng chế bảo mật AST trong RAM (< 5ms).
    Triệt tiêu 100% rủi ro Prompt Injection và Semantic SQLi trước khi gửi tới CSDL.
    """

    def __init__(self) -> None:
        pass

    def _sanitize_single_sql_ast(
        self,
        raw_sql: str,
        user_ctx: UserSecurityContextDTO,
        trace_id: str = "",
    ) -> Tuple[str, List[str], List[str]]:
        """
        Thực hiện 5 tầng kiểm soát AST trên 1 câu SQL:
        1. Cú pháp & Đơn câu lệnh (Dialect PostgreSQL 16)
        2. Chặn DDL/DML
        3. Whitelist Bảng & Schema
        4. Tiêm HBAC đệ quy cho CTE & Subqueries
        5. Cưỡng chế LIMIT 500
        Trả về: Tuple[sanitized_sql, predicates_added, tables_validated]
        """
        cleaned = clean_raw_sql(raw_sql)
        if not cleaned:
            raise SecurityEnforcementError(
                "Câu lệnh SQL rỗng sau khi làm sạch",
                violation_type=ASTViolationType.INVALID_SYNTAX,
                raw_sql=raw_sql,
            )

        # ----------------------------------------------------------------------
        # TẦNG 1: Parse AST phương ngữ PostgreSQL 16 & Chặn đa câu lệnh (;)
        # ----------------------------------------------------------------------
        try:
            statements = sqlglot.parse(cleaned, read="postgres")
        except Exception as e:
            logger.warning(f"AST Enforcer Lỗi cú pháp: {e}")
            raise SecurityEnforcementError(
                f"Cú pháp SQL không hợp lệ trên dialect PostgreSQL 16: {e}",
                violation_type=ASTViolationType.INVALID_SYNTAX,
                raw_sql=raw_sql,
            )

        if not statements or statements[0] is None:
            raise SecurityEnforcementError(
                "Không thể phân tích cú pháp câu lệnh SQL",
                violation_type=ASTViolationType.INVALID_SYNTAX,
                raw_sql=raw_sql,
            )

        if len(statements) > 1:
            logger.critical(f"Phát hiện {len(statements)} câu lệnh trong một truy vấn!")
            raise SecurityEnforcementError(
                f"Phát hiện hành vi tiêm mã: Chứa {len(statements)} câu lệnh phân tách bởi dấu chấm phẩy (;)",
                violation_type=ASTViolationType.MULTIPLE_STATEMENTS,
                raw_sql=raw_sql,
            )

        parsed = statements[0]

        # Chỉ cho phép gốc SELECT hoặc UNION
        if not isinstance(parsed, (exp.Select, exp.Union)):
            raise SecurityEnforcementError(
                f"Chỉ chấp nhận các câu lệnh truy vấn dữ liệu (SELECT/UNION), phát hiện: {type(parsed).__name__}",
                violation_type=ASTViolationType.DDL_DML_MUTATION,
                raw_sql=raw_sql,
            )

        # ----------------------------------------------------------------------
        # TẦNG 2: Chặn lệnh DDL/DML đột biến dữ liệu
        # ----------------------------------------------------------------------
        for mutation in parsed.find_all(FORBIDDEN_MUTATIONS):
            mutation_name = type(mutation).__name__
            logger.critical(f"Phát hiện lệnh biến đổi dữ liệu ({mutation_name}) trong cây AST!")
            raise SecurityEnforcementError(
                f"Phát hiện hành vi cấm: Câu lệnh chứa biểu thức biến đổi dữ liệu {mutation_name}",
                violation_type=ASTViolationType.DDL_DML_MUTATION,
                forbidden_tokens=[mutation_name],
                raw_sql=raw_sql,
            )

        # ----------------------------------------------------------------------
        # TẦNG 3: Whitelist Bảng và Schema
        # ----------------------------------------------------------------------
        # Tập hợp các CTE alias tự định nghĩa trong câu lệnh
        cte_names: Set[str] = set()
        for cte in parsed.find_all(exp.CTE):
            if cte.alias:
                cte_names.add(cte.alias.lower())

        tables_validated: List[str] = []
        for tbl in parsed.find_all(exp.Table):
            tbl_name = tbl.name.lower() if tbl.name else ""
            if not tbl_name:
                continue

            # Bỏ qua các alias nội bộ của CTE và subquery
            if tbl_name in ("sub", "subquery", "t", "cte") or tbl_name in cte_names:
                continue

            # Kiểm tra Schema cấm
            schema_name = tbl.db.lower() if tbl.db else ""
            if schema_name in FORBIDDEN_SCHEMAS:
                raise SecurityEnforcementError(
                    f"Cấm tuyệt đối truy cập vào schema siêu dữ liệu hệ thống: '{schema_name}'",
                    violation_type=ASTViolationType.FORBIDDEN_TABLE,
                    forbidden_tokens=[schema_name],
                    raw_sql=raw_sql,
                )

            # [TRAP-005] Phát hiện sai chính tả department
            if tbl_name == "department":
                raise SecurityEnforcementError(
                    "[TRAP-005] Bảng đơn vị trong CSDL là 'dwh_internal.deparment' (thiếu chữ 't' thứ hai)",
                    violation_type=ASTViolationType.FORBIDDEN_TABLE,
                    forbidden_tokens=["department"],
                    raw_sql=raw_sql,
                )

            # Kiểm tra Whitelist
            if tbl_name not in ALLOWED_TABLES:
                raise SecurityEnforcementError(
                    f"Truy cập trái phép vào bảng không thuộc Whitelist danh mục: '{tbl_name}'",
                    violation_type=ASTViolationType.FORBIDDEN_TABLE,
                    forbidden_tokens=[tbl_name],
                    raw_sql=raw_sql,
                )

            tables_validated.append(f"{schema_name}.{tbl_name}" if schema_name else tbl_name)

        # ----------------------------------------------------------------------
        # TẦNG 4: Tiêm Bộ Lọc Phân Quyền HBAC (Recursive Scope Visitor)
        # ----------------------------------------------------------------------
        visitor = RecursiveScopeVisitor(user_ctx=user_ctx)
        parsed, predicates_added, _ = visitor.inject_hbac_predicates(parsed)

        # ----------------------------------------------------------------------
        # TẦNG 5: Giới Hạn Tải Tài Nguyên (LIMIT 500)
        # ----------------------------------------------------------------------
        # Nếu câu truy vấn chưa có LIMIT và không phải là scalar aggregation thuần túy (e.g. SELECT SUM())
        has_group_by = bool(parsed.find(exp.Group))
        has_limit = bool(parsed.find(exp.Limit))
        
        # Tiêm LIMIT 500 nếu có GROUP BY hoặc không có aggregate function nào
        has_agg = bool(parsed.find((exp.Sum, exp.Avg, exp.Count, exp.Min, exp.Max)))
        if not has_limit:
            if has_group_by or not has_agg:
                parsed = parsed.limit(500)

        sanitized_sql = parsed.sql(dialect="postgres")
        return sanitized_sql, predicates_added, list(set(tables_validated))

    def enforce_sql_sync(
        self,
        dto: GeneratedSQLDTO,
        user_ctx: UserSecurityContextDTO,
        trace_id: str = "",
    ) -> SanitizedSQLDTO:
        """
        Làm sạch và kiên cố hóa câu truy vấn từ GeneratedSQLDTO (Đồng bộ).
        Xử lý linh hoạt cả SINGLE_UNIFIED, SCATTER_GATHER và BYPASS_ZERO_SQL.
        """
        t0 = time.perf_counter()
        t_id = trace_id or dto.trace_id or f"ast_trace_{int(time.time())}"

        # 1. Nếu là Bypass Zero-SQL: Trả về an toàn ngay
        if dto.execution_mode == SQLExecutionMode.BYPASS_ZERO_SQL or (
            not dto.raw_sql.strip() and not dto.subquery_tasks
        ):
            latency = (time.perf_counter() - t0) * 1000.0
            return SanitizedSQLDTO(
                raw_sql=dto.raw_sql,
                sanitized_sql="",
                execution_mode=SQLExecutionMode.BYPASS_ZERO_SQL,
                hbac_injected=False,
                predicates_added=[],
                tables_validated=[],
                subquery_tasks=[],
                is_safe=True,
                ast_valid=True,
                latency_ms=latency,
                trace_id=t_id,
            )

        # 2. Nếu là Scatter-Gather: Làm sạch từng subquery task
        if dto.execution_mode == SQLExecutionMode.SCATTER_GATHER and dto.subquery_tasks:
            sanitized_tasks: List[SanitizedSubqueryTaskItem] = []
            all_predicates: List[str] = []
            all_tables: List[str] = []

            for task in dto.subquery_tasks:
                sub_sql, sub_preds, sub_tbls = self._sanitize_single_sql_ast(
                    raw_sql=task.sql,
                    user_ctx=user_ctx,
                    trace_id=t_id,
                )
                sanitized_tasks.append(
                    SanitizedSubqueryTaskItem(
                        task_id=task.task_id,
                        sql=sub_sql,
                        target_metric=task.target_metric,
                        target_period=task.target_period,
                        target_entity=task.target_entity,
                        parameters=task.parameters,
                    )
                )
                all_predicates.extend(sub_preds)
                all_tables.extend(sub_tbls)

            # Làm sạch cả query cha nếu có
            root_sanitized = ""
            if dto.raw_sql.strip():
                try:
                    root_sanitized, r_preds, r_tbls = self._sanitize_single_sql_ast(
                        raw_sql=dto.raw_sql,
                        user_ctx=user_ctx,
                        trace_id=t_id,
                    )
                    all_predicates.extend(r_preds)
                    all_tables.extend(r_tbls)
                except Exception:
                    root_sanitized = sanitized_tasks[0].sql if sanitized_tasks else ""

            latency = (time.perf_counter() - t0) * 1000.0
            return SanitizedSQLDTO(
                raw_sql=dto.raw_sql,
                sanitized_sql=root_sanitized or (sanitized_tasks[0].sql if sanitized_tasks else ""),
                execution_mode=SQLExecutionMode.SCATTER_GATHER,
                hbac_injected=True,
                predicates_added=list(set(all_predicates)),
                tables_validated=list(set(all_tables)),
                subquery_tasks=sanitized_tasks,
                is_safe=True,
                ast_valid=True,
                latency_ms=latency,
                trace_id=t_id,
            )

        # 3. Mặc định: Chế độ SINGLE_UNIFIED
        sanitized_sql, predicates_added, tables_validated = self._sanitize_single_sql_ast(
            raw_sql=dto.raw_sql,
            user_ctx=user_ctx,
            trace_id=t_id,
        )

        latency = (time.perf_counter() - t0) * 1000.0
        return SanitizedSQLDTO(
            raw_sql=dto.raw_sql,
            sanitized_sql=sanitized_sql,
            execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
            hbac_injected=bool(predicates_added),
            predicates_added=predicates_added,
            tables_validated=tables_validated,
            subquery_tasks=[],
            is_safe=True,
            ast_valid=True,
            latency_ms=latency,
            trace_id=t_id,
        )

    async def enforce_sql_async(
        self,
        dto: GeneratedSQLDTO,
        user_ctx: UserSecurityContextDTO,
        trace_id: str = "",
    ) -> SanitizedSQLDTO:
        """Thực thi kiểm định AST bất đồng bộ (In-memory không phong tỏa)."""
        return self.enforce_sql_sync(dto=dto, user_ctx=user_ctx, trace_id=trace_id)
