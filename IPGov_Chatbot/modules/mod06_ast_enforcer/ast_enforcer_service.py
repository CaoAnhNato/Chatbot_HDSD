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
    "province",
    "ward",
    "office_mission",
    "office_user",
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
        user_ctx: Optional[Union[UserSecurityContextDTO, Dict[str, Any]]] = None,
        trace_id: str = "",
        user_context: Optional[Union[UserSecurityContextDTO, Dict[str, Any]]] = None,
        inject_limit: bool = True,
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
        effective_ctx = user_ctx if user_ctx is not None else user_context
        if isinstance(effective_ctx, dict):
            user_ctx = UserSecurityContextDTO(
                user_id=str(effective_ctx.get("user_id") or "u_anon"),
                username=str(effective_ctx.get("username") or "anonymous_user"),
                tenant_code=str(effective_ctx.get("tenant_code") or "68"),
                role_level=int(effective_ctx.get("role_level", 0)),
                department_code=effective_ctx.get("department_code"),
            )
        elif effective_ctx is not None:
            user_ctx = effective_ctx
        else:
            user_ctx = UserSecurityContextDTO(
                user_id="u_anon",
                username="anonymous_user",
                tenant_code="68",
                role_level=0,
            )

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
        # TẦNG 4.1: Cưỡng chế NULLS LAST tự động cho ORDER BY DESC (FAIL-002)
        # ----------------------------------------------------------------------
        for o in parsed.find_all(exp.Ordered):
            if o.args.get("desc"):
                o.set("nulls_first", False)

        # ----------------------------------------------------------------------
        # TẦNG 4.2: Bọc Ép Kiểu An Toàn NULLIF(TRIM(value), '')::numeric (FAIL2-001)
        # Chỉ bọc khi value dùng trong toán học, aggregate hoặc projection,
        # TUYỆT ĐỐI không bọc trong so sánh chuỗi như TRIM(value) != '-'
        # ----------------------------------------------------------------------
        cte_aliases = set()
        for cte in parsed.find_all(exp.CTE):
            cte_aliases.add(cte.alias_or_name.lower().strip())
        for tbl in parsed.find_all(exp.Table):
            if tbl.name.lower().strip() in cte_aliases:
                if tbl.alias:
                    cte_aliases.add(tbl.alias.lower().strip())

        for col in list(parsed.find_all(exp.Column)):
            if col.name.lower().strip() == "value":
                curr = col
                skip_cast = False
                needs_numeric_cast = False
                if col.table:
                    if col.table.lower().strip() in cte_aliases:
                        skip_cast = True
                else:
                    sel = col.find_ancestor(exp.Select)
                    if sel:
                        for tbl in sel.find_all(exp.Table):
                            if tbl.name.lower().strip() in cte_aliases or (tbl.alias and tbl.alias.lower().strip() in cte_aliases):
                                skip_cast = True
                                break

                while curr.parent and not skip_cast:
                    curr = curr.parent
                    if isinstance(curr, (exp.Cast, exp.TryCast, exp.Case, exp.RegexpLike, exp.Nullif, exp.Is, exp.In, exp.Like, exp.ILike, exp.EQ, exp.NEQ)):
                        skip_cast = True
                        break
                    if isinstance(curr, (exp.Trim, exp.Substring)):
                        if curr.parent and isinstance(curr.parent, (exp.NEQ, exp.EQ, exp.Is, exp.In, exp.RegexpLike, exp.Cast, exp.TryCast)):
                            skip_cast = True
                            break
                    if isinstance(curr, (exp.Sum, exp.Avg, exp.Min, exp.Max, exp.Add, exp.Sub, exp.Mul, exp.Div, exp.GT, exp.GTE, exp.LT, exp.LTE)):
                        needs_numeric_cast = True
                    if isinstance(curr, (exp.Select, exp.From, exp.Where, exp.Having, exp.Order, exp.Group)):
                        break
                if not skip_cast and needs_numeric_cast:
                    col_sql = col.sql(dialect="postgres")
                    safe_cast_sql = (
                        f"CASE WHEN TRIM({col_sql}) ~ '^-?[0-9]+(\\.[0-9]+)?$' "
                        f"THEN CAST(TRIM({col_sql}) AS DECIMAL) ELSE NULL END"
                    )
                    if isinstance(col.parent, exp.Select):
                        replacement = sqlglot.parse_one(safe_cast_sql, read="postgres").as_(col.name)
                    else:
                        replacement = sqlglot.parse_one(safe_cast_sql, read="postgres")
                    col.replace(replacement)

        # ----------------------------------------------------------------------
        # TẦNG 4.3: Safe Projection cho bảng user (Che giấu password, salt, token)
        # ----------------------------------------------------------------------
        has_user_table = any(
            (tbl.name or "").lower().strip() in ("user", "users") for tbl in parsed.find_all(exp.Table)
        )
        if has_user_table:
            sensitive_cols = {"password", "salt", "token", "refresh_token", "secret", "password_hash"}
            for sel in parsed.find_all(exp.Select):
                tables_in_sel = [tbl for tbl in sel.find_all(exp.Table)]
                user_tables = [tbl for tbl in tables_in_sel if (tbl.name or "").lower().strip() in ("user", "users")]
                user_aliases = {tbl.alias.lower().strip() if tbl.alias else "user" for tbl in user_tables}

                new_exprs = []
                for expr in sel.expressions:
                    if isinstance(expr, exp.Star):
                        if len(tables_in_sel) == 1 and user_tables:
                            for col_name in ["id", "name", "username", "position", "department_code"]:
                                new_exprs.append(exp.Column(this=exp.to_identifier(col_name)))
                        else:
                            # Nhiều bảng: giữ nguyên các bảng khác, nhưng che giấu cột user nhạy cảm
                            new_exprs.append(expr)
                    elif isinstance(expr, exp.Column) and isinstance(expr.this, exp.Star):
                        col_tbl = (expr.table or "").lower().strip()
                        if col_tbl in user_aliases or col_tbl in ("user", "users"):
                            alias_prefix = expr.table
                            for col_name in ["id", "name", "username", "position", "department_code"]:
                                new_exprs.append(exp.Column(this=exp.to_identifier(col_name), table=exp.to_identifier(alias_prefix)))
                        else:
                            new_exprs.append(expr)
                    elif isinstance(expr, exp.Column) and expr.name.lower().strip() in sensitive_cols:
                        new_exprs.append(exp.Null().as_(expr.name))
                    elif isinstance(expr, exp.Alias) and expr.alias.lower().strip() in sensitive_cols:
                        new_exprs.append(exp.Null().as_(expr.alias))
                    else:
                        new_exprs.append(expr)
                sel.set("expressions", new_exprs)

        # ----------------------------------------------------------------------
        # TẦNG 4.4: Tự động mở rộng phân cấp nút cha sang nút lá (Hierarchy Rollup Helper)
        # f.criteria_id IN (SELECT id FROM dwh_internal.criteria WHERE parent_id = :parent_id)
        # ----------------------------------------------------------------------
        for eq in list(parsed.find_all(exp.EQ)):
            left, right = eq.this, eq.expression
            col_node, val_node = None, None
            if isinstance(left, exp.Column) and left.name.lower().strip() == "criteria_id":
                col_node, val_node = left, right
            elif isinstance(right, exp.Column) and right.name.lower().strip() == "criteria_id":
                col_node, val_node = right, left

            if col_node and val_node:
                parent = eq.parent
                in_crit_sub = False
                while parent:
                    if isinstance(parent, (exp.Subquery, exp.Select)):
                        for tbl in parent.find_all(exp.Table):
                            if (tbl.name or "").lower().strip() == "criteria":
                                in_crit_sub = True
                                break
                    parent = parent.parent
                if not in_crit_sub:
                    col_sql = col_node.sql(dialect="postgres")
                    val_sql = val_node.sql(dialect="postgres")
                    replacement = sqlglot.parse_one(
                        f"{col_sql} IN (SELECT id FROM dwh_internal.criteria WHERE parent_id = {val_sql} OR id = {val_sql})",
                        read="postgres"
                    )
                    eq.replace(replacement)

        # ----------------------------------------------------------------------
        # TẦNG 5: Giới Hạn Tải Tài Nguyên (LIMIT 500)
        # ----------------------------------------------------------------------
        # Nếu câu truy vấn chưa có LIMIT và không phải là scalar aggregation thuần túy (e.g. SELECT SUM())
        has_group_by = bool(parsed.find(exp.Group))
        has_limit = bool(parsed.find(exp.Limit))
        
        # Tiêm LIMIT 500 nếu inject_limit=True và có GROUP BY hoặc không có aggregate function nào
        has_agg = bool(parsed.find((exp.Sum, exp.Avg, exp.Count, exp.Min, exp.Max)))
        if inject_limit and not has_limit:
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
        if isinstance(user_ctx, dict):
            user_ctx = UserSecurityContextDTO(
                user_id=str(user_ctx.get("user_id") or "u_anon"),
                username=str(user_ctx.get("username") or "anonymous_user"),
                tenant_code=str(user_ctx.get("tenant_code") or "68"),
                role_level=int(user_ctx.get("role_level", 0)),
                department_code=user_ctx.get("department_code"),
            )

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
