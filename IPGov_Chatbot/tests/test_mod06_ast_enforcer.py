"""
Unit Test Suite cho Module 06 Security Guardrails & AST Enforcer.
Căn cứ:
- Blueprint: 04_SECURITY_GUARDRAILS_VA_AST_ENFORCEMENT.md
- Skill: bonsai-test (Tier 1: Focused Unit Test Loop < 2s trong RAM)
- Rule: test_case_rule.md (Zero Security Violation: 0.0%)
"""

import pytest

from IPGov_Chatbot.modules.mod06_ast_enforcer.ast_enforcer_service import (
    ASTEnforcerService,
    SecurityEnforcementError,
)
from IPGov_Chatbot.schemas.ast_enforcer_dto import ASTViolationType
from IPGov_Chatbot.schemas.sql_compiler_schema import (
    GeneratedSQLDTO,
    SQLExecutionMode,
    SubqueryTaskItem,
)
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO


@pytest.fixture
def ast_service() -> ASTEnforcerService:
    return ASTEnforcerService()


@pytest.fixture
def province_user() -> UserSecurityContextDTO:
    return UserSecurityContextDTO(
        user_id="user_ld_01",
        username="lanhdao_lamdong",
        tenant_code="68",
        department_code=None,
        office_id=None,
        role_level=0,
    )


@pytest.fixture
def department_user() -> UserSecurityContextDTO:
    return UserSecurityContextDTO(
        user_id="user_nv_01",
        username="chuyenvien_so_noivu",
        tenant_code="79",
        department_code="79-1-01",
        office_id=None,
        role_level=1,
    )


@pytest.fixture
def office_user() -> UserSecurityContextDTO:
    return UserSecurityContextDTO(
        user_id="user_xd_01",
        username="chuyenvien_phong_xaydung",
        tenant_code="79",
        department_code="79-1-02",
        office_id="3c9f3cb2-30b2-42ed-9fd0-35e6bce92ac4",
        role_level=2,
    )


# ---------------------------------------------------------------------------
# TẦNG 1: KIỂM ĐỊNH CÚ PHÁP & CHỐNG ĐA CÂU LỆNH
# ---------------------------------------------------------------------------

def test_ast_enforcer_valid_syntax(ast_service: ASTEnforcerService, province_user: UserSecurityContextDTO):
    raw_sql = "SELECT f.year, SUM(NULLIF(TRIM(f.value), '')::numeric) FROM dwh_internal.fact_report_criteria f GROUP BY f.year"
    dto = GeneratedSQLDTO(
        raw_sql=raw_sql,
        execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
        generator_track="TRACK_A_COMPILER",
    )
    result = ast_service.enforce_sql_sync(dto, province_user)
    assert result.is_safe is True
    assert result.ast_valid is True
    assert "dwh_internal.fact_report_criteria" in result.sanitized_sql
    assert "tenant_code = '68'" in result.sanitized_sql


def test_ast_enforcer_multiple_statements_blocked(ast_service: ASTEnforcerService, province_user: UserSecurityContextDTO):
    raw_sql = "SELECT 1 FROM dwh_internal.fact_report_criteria; DROP TABLE dwh_internal.fact_report_criteria;"
    dto = GeneratedSQLDTO(
        raw_sql=raw_sql,
        execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
        generator_track="TRACK_B_LLM",
    )
    with pytest.raises(SecurityEnforcementError) as exc_info:
        ast_service.enforce_sql_sync(dto, province_user)
    assert exc_info.value.violation_type == ASTViolationType.MULTIPLE_STATEMENTS


def test_ast_enforcer_invalid_syntax_rejected(ast_service: ASTEnforcerService, province_user: UserSecurityContextDTO):
    raw_sql = "SELECT FROM WHERE GROUP BY ;;"
    dto = GeneratedSQLDTO(
        raw_sql=raw_sql,
        execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
        generator_track="TRACK_B_LLM",
    )
    with pytest.raises(SecurityEnforcementError) as exc_info:
        ast_service.enforce_sql_sync(dto, province_user)
    assert exc_info.value.violation_type == ASTViolationType.INVALID_SYNTAX


# ---------------------------------------------------------------------------
# TẦNG 2: CHẶN LỆNH ĐỘC HẠI DDL / DML
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_sql", [
    "DROP TABLE dwh_internal.fact_report_criteria",
    "DELETE FROM dwh_internal.fact_report_criteria WHERE year = '2025'",
    "UPDATE dwh_internal.fact_report_criteria SET value = '0'",
    "INSERT INTO dwh_internal.fact_report_criteria (year) VALUES ('2025')",
    "ALTER TABLE dwh_internal.fact_report_criteria DROP COLUMN value",
    "TRUNCATE TABLE dwh_internal.fact_report_criteria",
])
def test_ast_enforcer_ddl_dml_rejection(bad_sql: str, ast_service: ASTEnforcerService, province_user: UserSecurityContextDTO):
    dto = GeneratedSQLDTO(
        raw_sql=bad_sql,
        execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
        generator_track="TRACK_B_LLM",
    )
    with pytest.raises(SecurityEnforcementError) as exc_info:
        ast_service.enforce_sql_sync(dto, province_user)
    assert exc_info.value.violation_type == ASTViolationType.DDL_DML_MUTATION


def test_ast_enforcer_hidden_mutation_in_cte(ast_service: ASTEnforcerService, province_user: UserSecurityContextDTO):
    bad_sql = "WITH bad AS (DELETE FROM dwh_internal.fact_report_criteria RETURNING *) SELECT * FROM bad"
    dto = GeneratedSQLDTO(
        raw_sql=bad_sql,
        execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
        generator_track="TRACK_B_LLM",
    )
    with pytest.raises(SecurityEnforcementError) as exc_info:
        ast_service.enforce_sql_sync(dto, province_user)
    assert exc_info.value.violation_type == ASTViolationType.DDL_DML_MUTATION


# ---------------------------------------------------------------------------
# TẦNG 3: WHITELIST BẢNG VÀ CHẶN SCHEMA HỆ THỐNG
# ---------------------------------------------------------------------------

def test_ast_enforcer_forbidden_schema(ast_service: ASTEnforcerService, province_user: UserSecurityContextDTO):
    raw_sql = "SELECT * FROM pg_catalog.pg_tables"
    dto = GeneratedSQLDTO(
        raw_sql=raw_sql,
        execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
        generator_track="TRACK_B_LLM",
    )
    with pytest.raises(SecurityEnforcementError) as exc_info:
        ast_service.enforce_sql_sync(dto, province_user)
    assert exc_info.value.violation_type == ASTViolationType.FORBIDDEN_TABLE


def test_ast_enforcer_trap005_department_spelling(ast_service: ASTEnforcerService, province_user: UserSecurityContextDTO):
    raw_sql = "SELECT d.name FROM dwh_internal.department d"
    dto = GeneratedSQLDTO(
        raw_sql=raw_sql,
        execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
        generator_track="TRACK_B_LLM",
    )
    with pytest.raises(SecurityEnforcementError) as exc_info:
        ast_service.enforce_sql_sync(dto, province_user)
    assert exc_info.value.violation_type == ASTViolationType.FORBIDDEN_TABLE
    assert "TRAP-005" in str(exc_info.value)


# ---------------------------------------------------------------------------
# TẦNG 4: TIÊM VỊ TỪ PHÂN QUYỀN HBAC THEO CẤP BẬC
# ---------------------------------------------------------------------------

def test_ast_enforcer_hbac_level_0_province(ast_service: ASTEnforcerService, province_user: UserSecurityContextDTO):
    raw_sql = "SELECT f.year FROM dwh_internal.fact_report_criteria f WHERE f.year = '2025'"
    dto = GeneratedSQLDTO(raw_sql=raw_sql, execution_mode=SQLExecutionMode.SINGLE_UNIFIED, generator_track="TRACK_A_COMPILER")
    result = ast_service.enforce_sql_sync(dto, province_user)
    
    assert "f.tenant_code = '68'" in result.sanitized_sql
    assert "f.report_status = 'approved'" in result.sanitized_sql
    assert "department_code" not in result.sanitized_sql
    assert "office_id" not in result.sanitized_sql


def test_ast_enforcer_hbac_level_1_department(ast_service: ASTEnforcerService, department_user: UserSecurityContextDTO):
    raw_sql = "SELECT f.year FROM dwh_internal.fact_report_criteria f WHERE f.year = '2025'"
    dto = GeneratedSQLDTO(raw_sql=raw_sql, execution_mode=SQLExecutionMode.SINGLE_UNIFIED, generator_track="TRACK_A_COMPILER")
    result = ast_service.enforce_sql_sync(dto, department_user)
    
    assert "f.tenant_code = '79'" in result.sanitized_sql
    assert "f.department_code = '79-1-01'" in result.sanitized_sql
    assert "f.report_status = 'approved'" in result.sanitized_sql
    assert "office_id" not in result.sanitized_sql


def test_ast_enforcer_hbac_level_2_office(ast_service: ASTEnforcerService, office_user: UserSecurityContextDTO):
    raw_sql = "SELECT f.year FROM dwh_internal.fact_report_criteria f WHERE f.year = '2025'"
    dto = GeneratedSQLDTO(raw_sql=raw_sql, execution_mode=SQLExecutionMode.SINGLE_UNIFIED, generator_track="TRACK_A_COMPILER")
    result = ast_service.enforce_sql_sync(dto, office_user)
    
    assert "f.tenant_code = '79'" in result.sanitized_sql
    assert "f.department_code = '79-1-02'" in result.sanitized_sql
    assert "f.office_id = '3c9f3cb2-30b2-42ed-9fd0-35e6bce92ac4'" in result.sanitized_sql
    assert "f.report_status = 'approved'" in result.sanitized_sql


def test_ast_enforcer_nested_cte_scope_injection(ast_service: ASTEnforcerService, office_user: UserSecurityContextDTO):
    raw_sql = """
    WITH ranked_reports AS (
        SELECT f.office_id, f.value, f.year
        FROM dwh_internal.fact_report_criteria f
        WHERE f.year = '2025'
    )
    SELECT r.year, SUM(NULLIF(TRIM(r.value), '')::numeric)
    FROM ranked_reports r
    GROUP BY r.year
    """
    dto = GeneratedSQLDTO(raw_sql=raw_sql, execution_mode=SQLExecutionMode.SINGLE_UNIFIED, generator_track="TRACK_B_LLM")
    result = ast_service.enforce_sql_sync(dto, office_user)
    
    # Khẳng định: Vị từ HBAC phải được tiêm vào BÊN TRONG CTE (f.tenant_code), không được tiêm vào outer query (r.tenant_code)
    assert "f.tenant_code = '79'" in result.sanitized_sql
    assert "f.office_id = '3c9f3cb2-30b2-42ed-9fd0-35e6bce92ac4'" in result.sanitized_sql
    assert "ranked_reports.tenant_code" not in result.sanitized_sql


def test_ast_enforcer_semantic_sqli_parentheses_wrapping(ast_service: ASTEnforcerService, province_user: UserSecurityContextDTO):
    # Kịch bản tấn công: Người dùng cố ý tiêm OR 1=1 để bung toàn bộ dữ liệu các tỉnh khác
    raw_sql = "SELECT f.year FROM dwh_internal.fact_report_criteria f WHERE f.name = 'Tai nan' OR 1=1"
    dto = GeneratedSQLDTO(raw_sql=raw_sql, execution_mode=SQLExecutionMode.SINGLE_UNIFIED, generator_track="TRACK_B_LLM")
    result = ast_service.enforce_sql_sync(dto, province_user)
    
    # Kết quả bắt buộc phải bọc ngoặc: (f.name = 'Tai nan' OR 1 = 1) AND (f.tenant_code = '68' AND ...)
    sanitized = result.sanitized_sql
    assert "1 = 1" in sanitized or "1=1" in sanitized
    assert "AND (f.tenant_code = '68'" in sanitized or "AND (f.report_status = 'approved'" in sanitized


# ---------------------------------------------------------------------------
# TẦNG 5: GIỚI HẠN TẢI LIMIT 500 VÀ SCATTER-GATHER
# ---------------------------------------------------------------------------

def test_ast_enforcer_limit_injection(ast_service: ASTEnforcerService, province_user: UserSecurityContextDTO):
    raw_sql = "SELECT f.year, f.value FROM dwh_internal.fact_report_criteria f"
    dto = GeneratedSQLDTO(raw_sql=raw_sql, execution_mode=SQLExecutionMode.SINGLE_UNIFIED, generator_track="TRACK_A_COMPILER")
    result = ast_service.enforce_sql_sync(dto, province_user)
    assert "LIMIT 500" in result.sanitized_sql


def test_ast_enforcer_scatter_gather_tasks(ast_service: ASTEnforcerService, province_user: UserSecurityContextDTO):
    t1 = SubqueryTaskItem(
        task_id="t1",
        sql="SELECT f.year FROM dwh_internal.fact_report_criteria f WHERE f.year = '2025'",
        target_period="2025",
    )
    t2 = SubqueryTaskItem(
        task_id="t2",
        sql="SELECT f.year FROM dwh_internal.fact_report_criteria f WHERE f.year = '2026'",
        target_period="2026",
    )
    dto = GeneratedSQLDTO(
        raw_sql="",
        execution_mode=SQLExecutionMode.SCATTER_GATHER,
        subquery_tasks=[t1, t2],
        generator_track="TRACK_B_LLM",
    )
    result = ast_service.enforce_sql_sync(dto, province_user)
    assert result.execution_mode == SQLExecutionMode.SCATTER_GATHER
    assert len(result.subquery_tasks) == 2
    assert "tenant_code = '68'" in result.subquery_tasks[0].sql
    assert "tenant_code = '68'" in result.subquery_tasks[1].sql
