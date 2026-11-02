"""
Module: IPGov_Chatbot/modules/mod06_ast_enforcer/scope_visitor.py
Chức năng: Thuật toán Recursive Scope Visitor tiêm vị từ phân quyền HBAC và bọc ngoặc an toàn.
Căn cứ:
- Blueprint: 04_SECURITY_GUARDRAILS_VA_AST_ENFORCEMENT.md (Mục 3)
- Blueprint: 02_PHAN_QUYEN_PHAN_CAP_HBAC.md (Mục 3)
- Quyết định /grill-me: Hybrid Deterministic Strategy - Bọc ngoặc ((original)) AND (hbac)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

import sqlglot
import sqlglot.expressions as exp
from sqlglot.optimizer.scope import Scope, traverse_scope

from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO

logger = logging.getLogger("ipgov.mod06.scope_visitor")

# Các bảng mục tiêu bắt buộc phải tiêm vị từ phân quyền và trạng thái phê duyệt
TARGET_TABLES: Set[str] = {
    "fact_report_criteria",
    "report",
}


class RecursiveScopeVisitor:
    """
    Thuật toán duyệt đệ quy cây AST qua SQLGlot traverse_scope.
    Cô lập từng CTE và Subquery để tiêm vị từ phân quyền vào đúng scope chứa bảng vật lý,
    bảo toàn tuyệt đối tính hợp lệ của câu truy vấn PostgreSQL 16.
    """

    def __init__(self, user_ctx: UserSecurityContextDTO) -> None:
        self.user_ctx = user_ctx

    def is_authorized_for_non_approved(self) -> bool:
        """
        Kiểm tra người dùng có thẩm quyền xem dữ liệu báo cáo nháp (draft) / chờ duyệt (pending) hay không.
        - role_level <= 2 (0: Lãnh đạo Tỉnh/Admin, 1: Cấp Sở, 2: Cấp Phòng/Chi cục) hoặc Lãnh đạo toàn quyền (role_level=4 / is_unrestricted): Được phép khi có status_filter tương ứng.
        - role_level == 3 (3: Công dân / Khách vãng lai / Public): Bị chặn tuyệt đối truy cập draft/pending/rejected.
        """
        display_name = str(
            getattr(self.user_ctx, "name", "")
            or getattr(self.user_ctx, "user_name", "")
            or getattr(self.user_ctx, "username", "")
        ).strip()
        is_boss_or_unrestricted = (
            getattr(self.user_ctx, "is_unrestricted", False)
            or display_name == "Lãnh đạo"
            or getattr(self.user_ctx, "username", "") == "boss"
            or (getattr(self.user_ctx, "role_level", 0) == 4 and display_name == "Lãnh đạo")
        )
        return int(self.user_ctx.role_level) <= 2 or is_boss_or_unrestricted

    def _build_hbac_predicates(
        self, table_ref: str, table_name: str, has_status_filter: bool = False, has_tenant_filter: bool = False
    ) -> List[str]:
        """
        Xây dựng danh sách các vị từ HBAC bắt buộc dựa trên UserSecurityContextDTO.
        Level 0 (Tỉnh): tenant_code
        Level 1 (Sở): tenant_code + department_code
        Level 2 (Phòng): tenant_code + department_code + office_id
        Level 3 (Công dân/Public): tenant_code + cưỡng chế tuyệt đối status = 'approved'
        """
        # 0. Xác định schema và trạng thái miễn trừ toàn quyền
        raw_schema = str(getattr(self.user_ctx, "schema", "dwh_internal") or "dwh_internal").strip().lower()
        active_schema = "dwh_public" if raw_schema == "dwh_public" else "dwh_internal"
        display_name = str(
            getattr(self.user_ctx, "name", "")
            or getattr(self.user_ctx, "user_name", "")
            or getattr(self.user_ctx, "username", "")
        ).strip()
        is_boss_or_unrestricted = (
            getattr(self.user_ctx, "is_unrestricted", False)
            or display_name == "Lãnh đạo"
            or getattr(self.user_ctx, "username", "") == "boss"
            or (getattr(self.user_ctx, "role_level", 0) == 4 and display_name == "Lãnh đạo")
        )

        conditions: List[str] = []

        # 1. Cưỡng chế phân vùng địa bàn tỉnh (tenant_code) nếu câu lệnh chưa tự định danh phạm vi
        if not has_tenant_filter and self.user_ctx.tenant_code:
            tenant_safe = self.user_ctx.tenant_code.replace("'", "''")
            conditions.append(f"{table_ref}.tenant_code = '{tenant_safe}'")

        req_statuses = (
            self.user_ctx.get_status_list()
            if hasattr(self.user_ctx, "get_status_list")
            else [
                str(s).strip().lower()
                for s in (self.user_ctx.status_filter or [])
                if str(s).strip()
            ]
        )
        wants_non_approved = any(s in ("draft", "pending", "rejected", "all") for s in req_statuses)
        authorized_non_approved = self.is_authorized_for_non_approved()

        # 2. Cưỡng chế phân quyền cấp cơ quan (department_code) cho Level 1 & 2 (bỏ qua khi dwh_public)
        if active_schema != "dwh_public" and self.user_ctx.role_level in (1, 2) and self.user_ctx.department_code:
            if not req_statuses or self.user_ctx.department_code == "68-1-01":
                dept_safe = self.user_ctx.department_code.replace("'", "''")
                conditions.append(f"{table_ref}.department_code = '{dept_safe}'")

        # 3. Cưỡng chế phân quyền cấp phòng ban chuyên môn (office_id) cho Level 2 (bỏ qua khi dwh_public)
        if active_schema != "dwh_public" and self.user_ctx.role_level == 2 and self.user_ctx.office_id and not req_statuses and table_name != "report":
            office_safe = self.user_ctx.office_id.replace("'", "''")
            conditions.append(f"{table_ref}.office_id = '{office_safe}'")

        # 4. Cưỡng chế phân quyền theo nhiệm vụ (Mission-Scoped Invariant - Tier 2 Defense)
        # Khi schema == 'dwh_internal' và không phải 'Lãnh đạo': tiêm f.mission_id IN (...)
        # Khi schema == 'dwh_public' hoặc name == 'Lãnh đạo': bỏ qua (bypass hoàn toàn)
        if active_schema == "dwh_internal" and table_name == "fact_report_criteria" and not is_boss_or_unrestricted:
            assigned_mids = getattr(self.user_ctx, "assigned_mission_ids", []) or []
            if assigned_mids:
                cleaned_mids = [f"'{str(m)}'" for m in assigned_mids]
                joined_mids = ", ".join(cleaned_mids)
                conditions.append(f"{table_ref}.mission_id IN ({joined_mids})")
            elif getattr(self.user_ctx, "name", None) or getattr(self.user_ctx, "user_name", None):
                # Tài khoản đã định danh trong hệ thống nhưng không có nhiệm vụ nào được phân công -> Chặn 1 = 0
                conditions.append("1 = 0")

        # 5. Cưỡng chế bộ lọc trạng thái báo cáo (status / report_status) có điều kiện
        if table_name == "fact_report_criteria":
            # [C-05] Legal Invariant: Mọi truy vấn fact_report_criteria bắt buộc phải có report_status = 'approved'
            if not has_status_filter:
                conditions.append(f"{table_ref}.report_status = 'approved'")
        else:
            status_col = "status"
            if not authorized_non_approved:
                # Người dùng cấp 3 (Công dân/Khách) cố tình truy vấn draft/pending vượt thẩm quyền -> Cưỡng chế chỉ lấy approved
                if wants_non_approved:
                    self.user_ctx.blocked_draft_access = True
                if not has_status_filter:
                    conditions.append(f"{table_ref}.{status_col} = 'approved'")
            elif wants_non_approved:
                if "all" in req_statuses or ("approved" in req_statuses and "draft" in req_statuses):
                    # Cho phép lấy tất cả trạng thái (approved, draft, pending, rejected)
                    pass
                elif not has_status_filter:
                    valid_vals = [
                        s for s in req_statuses
                        if s in ("approved", "draft", "pending", "rejected")
                    ]
                    if len(valid_vals) == 1:
                        conditions.append(f"{table_ref}.{status_col} = '{valid_vals[0]}'")
                    elif len(valid_vals) > 1:
                        joined = ", ".join(f"'{v}'" for v in valid_vals)
                        conditions.append(f"{table_ref}.{status_col} IN ({joined})")
            else:
                # Mặc định luôn lọc báo cáo đã phê duyệt chính thức (approved)
                if not has_status_filter:
                    conditions.append(f"{table_ref}.{status_col} = 'approved'")

        return conditions

    def inject_hbac_predicates(
        self, expression: exp.Expression
    ) -> Tuple[exp.Expression, List[str], bool]:
        """
        Duyệt qua tất cả các scope trong biểu thức và tiêm vị từ HBAC an toàn:
        - Bọc ngoặc điều kiện WHERE cũ: (original_where)
        - Nối thêm: AND (hbac_predicates)
        Trả về: Tuple[expression_đã_tiêm, danh_sách_vị_từ_đã_thêm, có_tiêm_hay_không]
        """
        injected = False
        all_predicates_added: List[str] = []
        authorized_non_approved = self.is_authorized_for_non_approved()

        # Duyệt qua toàn bộ các phạm vi (Scopes) trong AST
        for scope in traverse_scope(expression):
            for alias, source in scope.sources.items():
                if not isinstance(source, exp.Table):
                    continue

                source_tbl_name = source.name.lower() if source.name else ""
                if source_tbl_name not in TARGET_TABLES:
                    continue

                # Xác định bí danh tham chiếu cục bộ trong scope này
                table_ref = alias if alias else source.name

                # Kiểm tra xem trong scope này đã có sẵn bộ lọc report_status / status / tenant_code chưa
                has_status_filter = False
                has_tenant_filter = False
                existing_where = scope.expression.args.get("where")
                if existing_where:
                    where_sql = existing_where.sql(dialect="postgres").lower()
                    if "tenant_code" in where_sql:
                        has_tenant_filter = True
                    if "report_status" in where_sql or "status" in where_sql:
                        has_status_filter = True
                        if source_tbl_name == "fact_report_criteria" or (source_tbl_name == "report" and not authorized_non_approved):
                            status_col_name = "report_status" if source_tbl_name == "fact_report_criteria" else "status"

                            # [C-05] Bất biến pháp lý: Mọi truy vấn fact_report_criteria (và report cho non-auditor) đều bắt buộc = 'approved'
                            # 1. Viết lại toàn bộ literal 'draft', 'pending', 'rejected' thành 'approved'
                            for lit in existing_where.find_all(exp.Literal):
                                if lit.is_string and str(lit.this).lower() in ("draft", "pending", "rejected"):
                                    lit.set("this", "approved")
                                    if not authorized_non_approved:
                                        self.user_ctx.blocked_draft_access = True

                            # 2. Chuyển đổi mọi vị từ phủ định (NOT, NOT IN) trên cột trạng thái thành '= approved'
                            for not_node in list(existing_where.find_all(exp.Not)):
                                # Bỏ qua tuyệt đối mệnh đề NOT EXISTS hoặc subquery existence check
                                if isinstance(not_node.this, (exp.Exists, exp.Select, exp.Subquery)) or not_node.find(exp.Exists):
                                    continue
                                if status_col_name in not_node.sql(dialect="postgres").lower():
                                    col_node = next(
                                        (c for c in not_node.find_all(exp.Column) if c.name.lower() == status_col_name),
                                        None,
                                    )
                                    target_col_expr = (
                                        col_node.copy()
                                        if (col_node and (not col_node.table or col_node.table.lower() == table_ref.lower()))
                                        else exp.to_column(f"{table_ref}.{status_col_name}")
                                    )
                                    not_node.replace(exp.EQ(this=target_col_expr, expression=exp.Literal.string("approved")))
                                    if not authorized_non_approved:
                                        self.user_ctx.blocked_draft_access = True

                            # 3. Chuyển đổi mọi phép so sánh khác (NEQ: !=, <>) trên cột trạng thái thành '= approved'
                            for neq_node in list(existing_where.find_all(exp.NEQ)):
                                if status_col_name in neq_node.sql(dialect="postgres").lower():
                                    col_node = next(
                                        (c for c in neq_node.find_all(exp.Column) if c.name.lower() == status_col_name),
                                        None,
                                    )
                                    target_col_expr = (
                                        col_node.copy()
                                        if (col_node and (not col_node.table or col_node.table.lower() == table_ref.lower()))
                                        else exp.to_column(f"{table_ref}.{status_col_name}")
                                    )
                                    neq_node.replace(exp.EQ(this=target_col_expr, expression=exp.Literal.string("approved")))
                                    if not authorized_non_approved:
                                        self.user_ctx.blocked_draft_access = True

                            # 4. Chuyển đổi mọi biểu thức IN trên cột trạng thái thành phép gán duy nhất '= approved'
                            for in_node in list(existing_where.find_all(exp.In)):
                                in_sql = in_node.this.sql(dialect="postgres").lower()
                                if status_col_name in in_sql:
                                    in_node.replace(exp.EQ(this=in_node.this.copy(), expression=exp.Literal.string("approved")))

                            # 5. Kiểm tra đẳng thức dương '= approved' để quyết định tiêm vị từ HBAC
                            has_pos_eq = False
                            for eq_node in existing_where.find_all(exp.EQ):
                                col_nodes = [c for c in eq_node.find_all(exp.Column) if c.name.lower() == status_col_name]
                                matching_cols = [c for c in col_nodes if not c.table or c.table.lower() == table_ref.lower()]
                                if matching_cols:
                                    eq_lits = [str(l.this).lower() for l in eq_node.find_all(exp.Literal) if l.is_string]
                                    if "approved" in eq_lits:
                                        has_pos_eq = True
                                        break
                            if not has_pos_eq:
                                has_status_filter = False


                # Xây dựng danh sách vị từ HBAC cần tiêm
                predicates = self._build_hbac_predicates(
                    table_ref=table_ref,
                    table_name=source_tbl_name,
                    has_status_filter=has_status_filter,
                    has_tenant_filter=has_tenant_filter,
                )
                if not predicates:
                    continue

                injected = True
                all_predicates_added.extend(predicates)

                # Nối các vị từ HBAC thành 1 biểu thức bọc ngoặc: (p1 AND p2 AND ...)
                hbac_clause_str = " AND ".join(predicates)
                hbac_parsed = sqlglot.parse_one(f"({hbac_clause_str})", read="postgres")

                if existing_where and existing_where.this:
                    # Bọc ngoặc điều kiện cũ: (existing_condition)
                    old_condition = existing_where.this
                    wrapped_old = exp.Paren(this=old_condition)
                    
                    # Tạo điều kiện mới: (existing_condition) AND (hbac_clause)
                    combined = exp.And(this=wrapped_old, expression=hbac_parsed)
                    existing_where.set("this", combined)
                else:
                    # Nếu scope chưa có WHERE, gán trực tiếp mệnh đề WHERE mới
                    scope.expression.where(hbac_parsed, copy=False)

        return expression, list(set(all_predicates_added)), injected
