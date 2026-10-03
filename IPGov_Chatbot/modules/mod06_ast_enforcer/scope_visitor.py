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

    def _build_hbac_predicates(
        self, table_ref: str, table_name: str, has_status_filter: bool = False
    ) -> List[str]:
        """
        Xây dựng danh sách các vị từ HBAC bắt buộc dựa trên UserSecurityContextDTO.
        Level 0 (Tỉnh): tenant_code
        Level 1 (Sở): tenant_code + department_code
        Level 2 (Phòng): tenant_code + department_code + office_id
        Level 3 (Công dân/Public): tenant_code + public view restriction
        """
        conditions: List[str] = []

        # 1. Cưỡng chế phân vùng địa bàn tỉnh (tenant_code)
        if self.user_ctx.tenant_code:
            tenant_safe = self.user_ctx.tenant_code.replace("'", "''")
            conditions.append(f"{table_ref}.tenant_code = '{tenant_safe}'")

        # 2. Cưỡng chế phân quyền cấp cơ quan (department_code) cho Level 1 & 2
        if self.user_ctx.role_level >= 1 and self.user_ctx.department_code:
            dept_safe = self.user_ctx.department_code.replace("'", "''")
            conditions.append(f"{table_ref}.department_code = '{dept_safe}'")

        # 3. Cưỡng chế phân quyền cấp phòng ban chuyên môn (office_id) cho Level 2
        if self.user_ctx.role_level >= 2 and self.user_ctx.office_id:
            office_safe = self.user_ctx.office_id.replace("'", "''")
            conditions.append(f"{table_ref}.office_id = '{office_safe}'")

        # 4. Cưỡng chế mặc định lọc báo cáo đã phê duyệt chính thức (report_status = 'approved')
        if not has_status_filter:
            if table_name == "fact_report_criteria":
                conditions.append(f"{table_ref}.report_status = 'approved'")
            elif table_name == "report":
                conditions.append(f"{table_ref}.status = 'approved'")

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

                # Kiểm tra xem trong scope này đã có sẵn bộ lọc report_status / status chưa
                has_status_filter = False
                existing_where = scope.expression.args.get("where")
                if existing_where:
                    where_sql = existing_where.sql(dialect="postgres").lower()
                    if "report_status" in where_sql or "status" in where_sql:
                        has_status_filter = True

                # Xây dựng danh sách vị từ HBAC cần tiêm
                predicates = self._build_hbac_predicates(
                    table_ref=table_ref,
                    table_name=source_tbl_name,
                    has_status_filter=has_status_filter,
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
