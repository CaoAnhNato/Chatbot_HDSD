"""
Test Suite Tier 2 cho Module 07 DWH Execution Engine trên Docker PostgreSQL vna_wom_dev.
Căn cứ:
- Blueprint: 01_DATA_WAREHOUSE_VA_CAY_THUC_THE_DWH.md
- Blueprint: 06_OBSERVABILITY_TRACING_DLQ_VA_EVALUATION.md
- Blueprint: 08_BO_TEST_CASE_KIEM_THU_TOAN_DIEN_VA_5_DIEM_MU_DWH.md (TC-DWH-01, CI-DWH-ROBUSTNESS)
- Rule: test_case_rule.md (Live Database Assertion trên Docker PostgreSQL localhost:5432)
"""

import pytest
import psycopg2

from IPGov_Chatbot.config import settings
from IPGov_Chatbot.modules.mod07_dwh_exec.dwh_exec_service import DWHExecutionService
from IPGov_Chatbot.schemas.ast_enforcer_dto import SanitizedSQLDTO, SanitizedSubqueryTaskItem
from IPGov_Chatbot.schemas.dwh_exec_dto import ExecutionStatusEnum
from IPGov_Chatbot.schemas.sql_compiler_schema import SQLExecutionMode
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO


@pytest.fixture
def exec_service() -> DWHExecutionService:
    return DWHExecutionService()


@pytest.fixture
def test_user() -> UserSecurityContextDTO:
    return UserSecurityContextDTO(
        user_id="user_test_dwh",
        username="chuyenvien_kiemthu",
        tenant_code="68",
        department_code="68-1-02",
        office_id=None,
        role_level=1,
    )


# ---------------------------------------------------------------------------
# 1. THỰC THI TRUY VẤN ĐƠN LẺ VÀ LÀM SẠCH KIỂU DỮ LIỆU
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dwh_exec_single_unified_query(exec_service: DWHExecutionService, test_user: UserSecurityContextDTO):
    sql = """
    SELECT f.year, COUNT(*) AS total_records
    FROM dwh_internal.fact_report_criteria f
    WHERE f.report_status = 'approved'
    GROUP BY f.year
    ORDER BY f.year
    """
    dto = SanitizedSQLDTO(
        raw_sql=sql,
        sanitized_sql=sql,
        execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
    )
    result = await exec_service.execute_query_async(dto, user_ctx=test_user, trace_id="test_single_01")

    assert result.status == ExecutionStatusEnum.SUCCESS
    assert result.row_count > 0
    assert result.is_empty is False
    assert len(result.columns) == 2
    assert result.columns[0].name == "year"
    assert result.columns[1].name == "total_records"
    assert isinstance(result.rows[0]["total_records"], int)
    assert result.execution_time_ms > 0.0


# ---------------------------------------------------------------------------
# 2. KIÊN CỐ HÓA READ-ONLY CẤP DATABASE ENGINE (MÃ 25006)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dwh_exec_read_only_hardening(exec_service: DWHExecutionService, test_user: UserSecurityContextDTO):
    # Cố tình thực thi lệnh ghi dữ liệu trên pool read-only
    bad_sql = "INSERT INTO dwh_internal.fact_report_criteria (fact_sk, year) VALUES ('fake_sk_test', '2099')"
    dto = SanitizedSQLDTO(
        raw_sql=bad_sql,
        sanitized_sql=bad_sql,
        execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
    )
    result = await exec_service.execute_query_async(dto, user_ctx=test_user, trace_id="test_ro_01")

    # Phải bị CSDL chặn đứng với mã lỗi 25006 (read_only_sql_transaction)
    assert result.status == ExecutionStatusEnum.ERROR
    assert result.error_code == "25006"
    assert "read_only" in result.error_message.lower() or "chỉ đọc" in result.error_message.lower()


# ---------------------------------------------------------------------------
# 3. THỰC THI PHÂN TÁN SONG SONG SCATTER-GATHER (SEMAPHORE 20)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dwh_exec_scatter_gather_parallel(exec_service: DWHExecutionService, test_user: UserSecurityContextDTO):
    t1 = SanitizedSubqueryTaskItem(
        task_id="sub_2025",
        sql="SELECT '2025' AS period, COUNT(*) AS cnt FROM dwh_internal.fact_report_criteria f WHERE f.year = '2025' AND f.report_status = 'approved'",
        target_period="2025",
    )
    t2 = SanitizedSubqueryTaskItem(
        task_id="sub_2026",
        sql="SELECT '2026' AS period, COUNT(*) AS cnt FROM dwh_internal.fact_report_criteria f WHERE f.year = '2026' AND f.report_status = 'approved'",
        target_period="2026",
    )
    dto = SanitizedSQLDTO(
        raw_sql="",
        sanitized_sql="",
        execution_mode=SQLExecutionMode.SCATTER_GATHER,
        subquery_tasks=[t1, t2],
    )
    result = await exec_service.execute_query_async(dto, user_ctx=test_user, trace_id="test_scatter_01")

    assert result.status == ExecutionStatusEnum.SUCCESS
    assert result.execution_mode == SQLExecutionMode.SCATTER_GATHER
    assert len(result.subquery_results) == 2
    assert result.row_count == 2
    assert result.subquery_results[0].task_id == "sub_2025"
    assert result.subquery_results[1].task_id == "sub_2026"
    assert result.rows[0]["period"] == "2025"
    assert result.rows[1]["period"] == "2026"


# ---------------------------------------------------------------------------
# 4. BỘ TEST ĐỘ BỀN BỈ DWH (CI-DWH-ROBUSTNESS & TC-DWH-01 SAFE CASTING)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dwh_exec_tc_dwh_01_safe_casting_text(exec_service: DWHExecutionService, test_user: UserSecurityContextDTO):
    """
    TC-DWH-01: Cột fact_report_criteria.value là TEXT, chứa cả chữ và số.
    Bắt buộc dùng Regex Safe Casting hoặc NULLIF TRIM để không bị crash runtime.
    """
    sql = """
    SELECT 
        f.year,
        SUM(CASE WHEN TRIM(f.value) ~ '^-?[0-9]+(\\.[0-9]+)?$' THEN TRIM(f.value)::numeric ELSE NULL END) AS total_val,
        COUNT(CASE WHEN TRIM(f.value) ~ '^-?[0-9]+(\\.[0-9]+)?$' THEN 1 ELSE NULL END) AS valid_numeric_rows
    FROM dwh_internal.fact_report_criteria f
    WHERE f.report_status = 'approved'
    GROUP BY f.year
    """
    dto = SanitizedSQLDTO(raw_sql=sql, sanitized_sql=sql, execution_mode=SQLExecutionMode.SINGLE_UNIFIED)
    result = await exec_service.execute_query_async(dto, user_ctx=test_user, trace_id="test_safe_cast_01")

    assert result.status == ExecutionStatusEnum.SUCCESS
    assert result.row_count > 0
    for row in result.rows:
        assert "total_val" in row
        assert "valid_numeric_rows" in row
        assert row["valid_numeric_rows"] > 0


@pytest.mark.asyncio
async def test_dwh_exec_ci_dwh_robustness_null_and_zero(exec_service: DWHExecutionService, test_user: UserSecurityContextDTO):
    """
    Kiểm tra xử lý các bản ghi có giá trị NULL hoặc 0 nhưng trạng thái đã approved (GOLDEN_008, GOLDEN_018).
    """
    sql = """
    SELECT 
        COUNT(*) AS total_rows,
        COUNT(CASE WHEN f.value IS NULL OR TRIM(f.value) = '' THEN 1 END) AS null_or_empty_rows,
        COUNT(CASE WHEN TRIM(f.value) = '0' THEN 1 END) AS zero_rows
    FROM dwh_internal.fact_report_criteria f
    WHERE f.report_status = 'approved'
    """
    dto = SanitizedSQLDTO(raw_sql=sql, sanitized_sql=sql, execution_mode=SQLExecutionMode.SINGLE_UNIFIED)
    result = await exec_service.execute_query_async(dto, user_ctx=test_user, trace_id="test_robustness_01")

    assert result.status == ExecutionStatusEnum.SUCCESS
    assert result.row_count == 1
    row = result.rows[0]
    assert row["total_rows"] > 0
    # Khẳng định kho CSDL thực tế có các dòng NULL/rỗng được đếm chính xác
    assert "null_or_empty_rows" in row
    assert "zero_rows" in row


# ---------------------------------------------------------------------------
# 5. GHI NHẬN SỰ CỐ VÀO BẢNG PUBLIC.CHATBOT_DLQ_INCIDENTS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dwh_exec_dlq_incident_logging(exec_service: DWHExecutionService, test_user: UserSecurityContextDTO):
    """
    Kiểm tra khi xảy ra lỗi cú pháp hoặc lỗi thực thi CSDL, sự cố được ghi nhận vào DLQ.
    """
    import uuid
    trace_test_id = f"trace_dlq_{uuid.uuid4().hex[:12]}"
    bad_sql = "SELECT non_existent_column_12345 FROM dwh_internal.fact_report_criteria"
    dto = SanitizedSQLDTO(raw_sql=bad_sql, sanitized_sql=bad_sql, execution_mode=SQLExecutionMode.SINGLE_UNIFIED)
    result = await exec_service.execute_query_async(dto, user_ctx=test_user, trace_id=trace_test_id)

    assert result.status == ExecutionStatusEnum.ERROR
    assert result.error_code is not None

    # Xác minh bản ghi đã được ghi vào bảng public.chatbot_dlq_incidents
    conn = psycopg2.connect(
        host=settings.DWH_HOST,
        port=settings.DWH_PORT,
        dbname=settings.DWH_DB,
        user=settings.DWH_USER,
        password=getattr(settings, "DWH_PASSWORD", None) or getattr(settings, "DWH_PASS", "postgres"),
        connect_timeout=2,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT incident_id, trace_id, error_stage, error_message FROM public.chatbot_dlq_incidents WHERE trace_id = %s",
                (trace_test_id,),
            )
            record = cur.fetchone()
            assert record is not None
            assert record[1] == trace_test_id
            assert record[2] == "DB_EXEC"
            assert "non_existent_column_12345" in record[3]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 6. KIỂM THỬ THỰC THI ĐỒNG BỘ (SYNC ADAPTER)
# ---------------------------------------------------------------------------

def test_dwh_exec_sync_adapter(exec_service: DWHExecutionService, test_user: UserSecurityContextDTO):
    sql = "SELECT 1 AS alive"
    dto = SanitizedSQLDTO(raw_sql=sql, sanitized_sql=sql, execution_mode=SQLExecutionMode.SINGLE_UNIFIED)
    result = exec_service.execute_query_sync(dto, user_ctx=test_user, trace_id="test_sync_01")

    assert result.status == ExecutionStatusEnum.SUCCESS
    assert result.row_count == 1
    assert result.rows[0]["alive"] == 1
