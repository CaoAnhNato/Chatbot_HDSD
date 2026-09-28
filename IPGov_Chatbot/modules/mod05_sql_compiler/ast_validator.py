"""
Module: IPGov_Chatbot/modules/mod05_sql_compiler/ast_validator.py
Chức năng: Hàng rào kiểm định Invariant Gate trong RAM bằng SQLGlot AST Parser.
Căn cứ:
- Blueprint: 05_MULTI_AGENT_WORKFLOW_DIN_MAC_SQL.md (Mục 3)
- Specification: IPGov_Chatbot/docs/MODULE_05_SQL_COMPILER_SPEC.md (Mục 5.1)
- Tuân thủ TRAPS: [TRAP-004], [TRAP-005], [TRAP-007]
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional, Set, Tuple

import sqlglot
import sqlglot.expressions as exp

from IPGov_Chatbot.schemas.sql_compiler_schema import TextToSQLStructuredOutput

logger = logging.getLogger("ipgov.mod05.ast_validator")


def clean_sql_string(sql: str) -> str:
    """Loại bỏ markdown code blocks, dấu nháy kép thừa và chuẩn hóa khoảng trắng."""
    if not sql:
        return ""
    cleaned = sql.strip()
    # Loại bỏ code block ```sql ... ```
    match = re.search(r"```(?:sql)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()
    return cleaned


# Tập hợp các loại câu lệnh biến đổi dữ liệu (DDL / DML) tuyệt đối bị cấm
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
)


def validate_ast_syntax(
    sql: str,
) -> Tuple[bool, Optional[str], Optional[exp.Expression]]:
    """
    Kiểm định cú pháp dialect PostgreSQL 16 qua SQLGlot AST trong RAM (< 0.5ms).
    Đảm bảo:
    1. Đúng 1 câu truy vấn SQL đọc dữ liệu (chống chèn nhiều lệnh qua dấu chấm phẩy ;).
    2. Gốc là SELECT hoặc UNION.
    3. Quét toàn bộ cây AST (kể cả trong CTE và Subquery) để triệt tiêu mọi đột biến DDL/DML.
    """
    cleaned = clean_sql_string(sql)
    if not cleaned:
        return False, "Câu lệnh SQL rỗng", None

    try:
        statements = sqlglot.parse(cleaned, read="postgres")
    except Exception as e:
        logger.warning(f"Invariant Gate: Lỗi cú pháp SQLGlot: {e}")
        return False, f"Cú pháp SQL không hợp lệ trên dialect PostgreSQL 16: {e}", None

    if not statements or statements[0] is None:
        return False, "Không thể phân tích cú pháp câu lệnh SQL", None

    if len(statements) > 1:
        logger.warning(f"Invariant Gate: Phát hiện {len(statements)} câu lệnh trong một truy vấn!")
        return (
            False,
            f"Chỉ cho phép đúng 1 câu truy vấn SQL đơn lẻ, phát hiện {len(statements)} câu lệnh phân tách bởi dấu chấm phẩy (;)",
            None,
        )

    parsed = statements[0]

    # Chặn DDL/DML mutation ở gốc (chỉ cho phép SELECT, UNION)
    valid_root_types = (exp.Select, exp.Union)
    if not isinstance(parsed, valid_root_types):
        logger.warning(f"Invariant Gate: Loại câu lệnh gốc không được phép: {type(parsed)}")
        return False, f"Chỉ cho phép câu lệnh SELECT / UNION, phát hiện: {type(parsed).__name__}", None

    # Quét toàn bộ cây AST để ngăn chặn DDL/DML lẩn trốn trong CTE hoặc Subquery
    for mutation in parsed.find_all(FORBIDDEN_MUTATIONS):
        mutation_name = type(mutation).__name__
        logger.critical(f"Invariant Gate: Phát hiện lệnh đột biến dữ liệu ({mutation_name}) lẩn trốn trong cây AST!")
        return (
            False,
            f"Phát hiện hành vi vi phạm an toàn dữ liệu: Câu lệnh chứa biểu thức biến đổi dữ liệu {mutation_name} (chỉ cho phép đọc dữ liệu)",
            None,
        )

    return True, None, parsed


def validate_schema_grounding(
    parsed: exp.Expression,
    candidate_tables: List[str],
) -> Tuple[bool, Optional[str]]:
    """
    Kiểm định Schema Grounding: Triệt tiêu hoàn toàn ảo giác bảng và cột.
    Mọi bảng xuất hiện trong cây AST bắt buộc phải nằm trong candidate_tables hoặc là CTE tự định nghĩa.
    """
    if not candidate_tables:
        # Nếu không cung cấp candidate_tables (e.g. bypass), bỏ qua
        return True, None

    # Tập hợp các CTE alias tự định nghĩa trong câu lệnh
    cte_names: Set[str] = set()
    for cte in parsed.find_all(exp.CTE):
        if cte.alias:
            cte_names.add(cte.alias.lower())

    # Danh sách các bảng cho phép (hỗ trợ cả full name 'dwh_internal.x' và simple name 'x')
    allowed_tables: Set[str] = set()
    for t in candidate_tables:
        t_clean = t.strip().lower()
        allowed_tables.add(t_clean)
        if "." in t_clean:
            allowed_tables.add(t_clean.split(".")[-1])

    # Duyệt toàn bộ các nút Table trong AST
    for tbl in parsed.find_all(exp.Table):
        tbl_name = tbl.name.lower() if tbl.name else ""
        if not tbl_name:
            continue

        # Các alias nội bộ hợp lệ
        if tbl_name in ("sub", "subquery", "t", "cte"):
            continue
        if tbl_name in cte_names:
            continue

        # Kiểm tra xem bảng có nằm trong allowed_tables không
        full_tbl = f"{tbl.db.lower()}.{tbl_name}" if tbl.db else tbl_name
        if tbl_name not in allowed_tables and full_tbl not in allowed_tables:
            logger.warning(f"Invariant Gate: Bảng ảo giác '{tbl_name}' không nằm trong Schema Slice!")
            return False, f"Bảng '{tbl_name}' không tồn tại trong Schema Slice được cung cấp"

    return True, None


def validate_data_contracts(parsed: exp.Expression) -> Tuple[bool, Optional[str]]:
    """
    Kiểm định các Data Contracts bắt buộc:
    1. [TRAP-004]: Ép kiểu an toàn cột 'value' trong fact_report_criteria (bắt buộc dùng NULLIF/TRIM).
    2. [TRAP-005]: Chính tả tên bảng danh mục 'deparment'.
    """
    sql_str = parsed.sql(dialect="postgres").lower()

    # Bẫy TRAP-005: phát hiện 'department' (sai chính tả bảng thực tế deparment)
    for tbl in parsed.find_all(exp.Table):
        if tbl.name and tbl.name.lower() == "department":
            return False, "[TRAP-005] Bảng đơn vị trong CSDL là 'dwh_internal.deparment' (thiếu chữ 't' thứ hai)"
    if "dwh_internal.department" in sql_str:
        return False, "[TRAP-005] Bảng đơn vị trong CSDL là 'dwh_internal.deparment' (thiếu chữ 't' thứ hai)"

    # Bẫy TRAP-004: Tính toán tổng hợp trực tiếp trên cột 'value' mà không qua CAST
    for agg in parsed.find_all((exp.Sum, exp.Avg, exp.Min, exp.Max)):
        for col in agg.find_all(exp.Column):
            if col.name and col.name.lower() == "value":
                ancestor = col.parent
                has_cast = False
                while ancestor and ancestor is not agg:
                    if isinstance(ancestor, exp.Cast):
                        has_cast = True
                        break
                    ancestor = ancestor.parent
                if not has_cast:
                    return (
                        False,
                        "[TRAP-004] Cột 'value' là kiểu TEXT trong CSDL, không thể tính toán trực tiếp mà không ép kiểu qua NULLIF(TRIM(value), '')::numeric",
                    )

    # Bẫy TRAP-004: Ép kiểu thô cột 'value' không bọc NULLIF
    for cast in parsed.find_all(exp.Cast):
        cols = [c.name.lower() for c in cast.find_all(exp.Column) if c.name]
        if "value" in cols:
            nullifs = list(cast.find_all(exp.Nullif))
            if not nullifs:
                return (
                    False,
                    "[TRAP-004] Cột 'value' chứa chuỗi rỗng/text, bắt buộc ép kiểu an toàn qua NULLIF(TRIM(value), '')::numeric",
                )

    return True, None


def invariant_sql_validator(
    res: TextToSQLStructuredOutput,
    candidate_tables: List[str],
) -> bool:
    """
    Hàng rào Invariant Gate hoàn chỉnh:
    1. Cú pháp AST PostgreSQL 16 hợp lệ (SQLGlot)
    2. Schema Grounding: bảng thuộc candidate_tables hoặc CTE
    3. Ngưỡng tin cậy tự đánh giá: confidence_score >= 0.70
    4. Tuân thủ Data Contracts cốt tử
    """
    # 1. Kiểm tra confidence_score
    if res.confidence_score < 0.70:
        logger.warning(f"Invariant Gate: Confidence ({res.confidence_score}) < 0.70")
        return False

    # 2. Kiểm tra cú pháp AST
    valid_ast, err_msg, parsed = validate_ast_syntax(res.sql_query)
    if not valid_ast or parsed is None:
        logger.warning(f"Invariant Gate Fail: {err_msg}")
        return False

    # 3. Kiểm tra Schema Grounding
    valid_schema, err_msg = validate_schema_grounding(parsed, candidate_tables)
    if not valid_schema:
        logger.warning(f"Invariant Gate Fail: {err_msg}")
        return False

    # 4. Kiểm tra Data Contracts
    valid_contracts, err_msg = validate_data_contracts(parsed)
    if not valid_contracts:
        logger.warning(f"Invariant Gate Fail: {err_msg}")
        return False

    return True
