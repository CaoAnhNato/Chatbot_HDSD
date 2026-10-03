"""
Module: IPGov_Chatbot/modules/mod07_dwh_exec/dwh_exec_service.py
Chức năng: Facade điều phối toàn bộ Module 07 DWH Execution Engine.
Căn cứ:
- Blueprint: 01_DATA_WAREHOUSE_VA_CAY_THUC_THE_DWH.md
- Blueprint: 06_OBSERVABILITY_TRACING_DLQ_VA_EVALUATION.md
- Specification: IPGov_Chatbot/docs/MODULE_07_DWH_EXEC_SPEC.md
- Quyết định /grill-me: Thực thi trên asyncpg.Pool kiên cố hóa, hỗ trợ Scatter-Gather Semaphore(20) & DLQ logging.
- Tuân thủ TRAPS: [TRAP-004], [TRAP-005]
"""

from __future__ import annotations

import asyncio
import datetime
import decimal
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import asyncpg

from IPGov_Chatbot.modules.mod07_dwh_exec.connection_pool import DWHConnectionPool
from IPGov_Chatbot.modules.mod07_dwh_exec.dlq_incident_logger import DLQIncidentLogger
from IPGov_Chatbot.schemas.ast_enforcer_dto import SanitizedSQLDTO, SanitizedSubqueryTaskItem
from IPGov_Chatbot.schemas.dwh_exec_dto import (
    ColumnMetadataDTO,
    ExecutionStatusEnum,
    QueryResultDTO,
    SubqueryResultItem,
)
from IPGov_Chatbot.schemas.sql_compiler_schema import SQLExecutionMode
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO

logger = logging.getLogger("ipgov.mod07.dwh_exec")


def sanitize_db_value(val: Any) -> Any:
    """Chuyển đổi các kiểu dữ liệu đặc thù của PostgreSQL sang Python native JSON primitives."""
    if val is None:
        return None
    if isinstance(val, uuid.UUID):
        return str(val)
    if isinstance(val, decimal.Decimal):
        # Nếu là số nguyên (ví dụ 1078.00) thì chuyển thành int, ngược lại float
        return int(val) if val % 1 == 0 else float(val)
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val.isoformat()
    if isinstance(val, (bytes, bytearray)):
        return val.decode("utf-8", errors="replace")
    return val


def sanitize_row_dict(record_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Làm sạch toàn bộ một dòng dữ liệu từ CSDL."""
    return {k: sanitize_db_value(v) for k, v in record_dict.items()}


class DWHExecutionService:
    """
    Dịch vụ thực thi truy vấn an toàn trên cơ sở dữ liệu PostgreSQL DWH (vna_wom_dev).
    Quản lý luồng thực thi bất đồng bộ và đồng bộ, kiểm soát lỗi và ghi nhận sự cố DLQ.
    """

    def __init__(
        self,
        pool: Optional[DWHConnectionPool] = None,
        dlq_logger: Optional[DLQIncidentLogger] = None,
    ) -> None:
        self.pool = pool or DWHConnectionPool.get_instance()
        self.dlq_logger = dlq_logger or DLQIncidentLogger()

    async def _execute_single_sql_async(
        self,
        sql: str,
        trace_id: str = "",
        user_ctx: Optional[UserSecurityContextDTO] = None,
    ) -> Tuple[List[ColumnMetadataDTO], List[Dict[str, Any]], float, Optional[str], Optional[str]]:
        """
        Thực thi một câu SQL đơn lẻ trên connection mượn từ asyncpg pool.
        Trả về: Tuple[columns, rows, execution_time_ms, error_code, error_message]
        """
        t0 = time.perf_counter()
        pool_conn = await self.pool.get_pool()

        try:
            async with pool_conn.acquire() as conn:
                # Chuẩn bị statement để trích xuất siêu dữ liệu cột
                stmt = await conn.prepare(sql)
                attributes = stmt.get_attributes()
                columns = [
                    ColumnMetadataDTO(
                        name=attr.name,
                        data_type=attr.type.name if hasattr(attr.type, "name") else "unknown",
                    )
                    for attr in attributes
                ]

                # Thực thi lấy dữ liệu
                records = await stmt.fetch()
                rows = [sanitize_row_dict(dict(r)) for r in records]
                exec_time = (time.perf_counter() - t0) * 1000.0
                return columns, rows, exec_time, None, None

        except asyncpg.QueryCanceledError as e:
            exec_time = (time.perf_counter() - t0) * 1000.0
            error_msg = f"Truy vấn vượt quá thời gian chờ an toàn (statement_timeout = 5000ms): {e}"
            logger.warning(f"DWH Exec Timeout [57014]: {error_msg}")
            # Ghi nhận DLQ
            await self.dlq_logger.log_incident_async(
                trace_id=trace_id,
                user_id=user_ctx.user_id if user_ctx else "unknown",
                tenant_code=user_ctx.tenant_code if user_ctx else "68",
                department_code=user_ctx.department_code if user_ctx else None,
                raw_prompt="",
                generated_sql=sql,
                error_stage="DB_EXEC",
                error_message=error_msg,
            )
            return [], [], exec_time, "57014", error_msg

        except asyncpg.ReadOnlySQLTransactionError as e:
            exec_time = (time.perf_counter() - t0) * 1000.0
            error_msg = f"Vi phạm giao dịch chỉ đọc: CSDL từ chối hành vi ghi chép [25006]: {e}"
            logger.critical(f"DWH Exec Read-Only Violation [25006]: {error_msg}")
            await self.dlq_logger.log_incident_async(
                trace_id=trace_id,
                user_id=user_ctx.user_id if user_ctx else "unknown",
                tenant_code=user_ctx.tenant_code if user_ctx else "68",
                department_code=user_ctx.department_code if user_ctx else None,
                raw_prompt="",
                generated_sql=sql,
                error_stage="DB_EXEC",
                error_message=error_msg,
            )
            return [], [], exec_time, "25006", error_msg

        except Exception as e:
            exec_time = (time.perf_counter() - t0) * 1000.0
            pg_code = getattr(e, "sqlstate", "ERROR")
            error_msg = str(e)
            logger.error(f"DWH Exec Thất bại [{pg_code}]: {error_msg}")
            await self.dlq_logger.log_incident_async(
                trace_id=trace_id,
                user_id=user_ctx.user_id if user_ctx else "unknown",
                tenant_code=user_ctx.tenant_code if user_ctx else "68",
                department_code=user_ctx.department_code if user_ctx else None,
                raw_prompt="",
                generated_sql=sql,
                error_stage="DB_EXEC",
                error_message=error_msg,
            )
            return [], [], exec_time, str(pg_code), error_msg

    async def execute_query_async(
        self,
        sanitized_dto: SanitizedSQLDTO,
        user_ctx: Optional[UserSecurityContextDTO] = None,
        trace_id: str = "",
    ) -> QueryResultDTO:
        """
        Thực thi truy vấn bất đồng bộ từ SanitizedSQLDTO.
        Tự động phân nhánh: BYPASS_ZERO_SQL, SINGLE_UNIFIED, SCATTER_GATHER.
        """
        t_id = trace_id or sanitized_dto.trace_id or f"exec_{int(time.time())}"

        # ----------------------------------------------------------------------
        # 1. Chế độ Bypass Zero-SQL
        # ----------------------------------------------------------------------
        if sanitized_dto.execution_mode == SQLExecutionMode.BYPASS_ZERO_SQL:
            return QueryResultDTO(
                columns=[],
                rows=[],
                row_count=0,
                execution_time_ms=0.0,
                execution_mode=SQLExecutionMode.BYPASS_ZERO_SQL,
                is_empty=True,
                status=ExecutionStatusEnum.BYPASS,
                executed_sql="",
                trace_id=t_id,
            )

        # ----------------------------------------------------------------------
        # 2. Chế độ Scatter-Gather (Song song hóa qua Semaphore)
        # ----------------------------------------------------------------------
        if sanitized_dto.execution_mode == SQLExecutionMode.SCATTER_GATHER and sanitized_dto.subquery_tasks:
            t0 = time.perf_counter()
            semaphore = asyncio.Semaphore(20)

            async def _run_task(task: SanitizedSubqueryTaskItem) -> SubqueryResultItem:
                async with semaphore:
                    cols, rws, sub_time, err_c, err_m = await self._execute_single_sql_async(
                        sql=task.sql,
                        trace_id=t_id,
                        user_ctx=user_ctx,
                    )
                    status = (
                        ExecutionStatusEnum.ERROR
                        if err_c
                        else (ExecutionStatusEnum.SUCCESS if rws else ExecutionStatusEnum.EMPTY)
                    )
                    return SubqueryResultItem(
                        task_id=task.task_id,
                        columns=cols,
                        rows=rws,
                        row_count=len(rws),
                        execution_time_ms=sub_time,
                        status=status,
                        error_message=err_m,
                    )

            # Bắn song song tất cả các subquery tasks
            subquery_results: List[SubqueryResultItem] = await asyncio.gather(
                *[_run_task(task) for task in sanitized_dto.subquery_tasks]
            )

            total_exec_time = (time.perf_counter() - t0) * 1000.0

            # Gom tất cả các dòng dữ liệu từ các subqueries
            all_rows: List[Dict[str, Any]] = []
            all_cols: List[ColumnMetadataDTO] = []
            seen_col_names = set()

            has_error = False
            for res in subquery_results:
                if res.status == ExecutionStatusEnum.ERROR:
                    has_error = True
                all_rows.extend(res.rows)
                for c in res.columns:
                    if c.name not in seen_col_names:
                        seen_col_names.add(c.name)
                        all_cols.append(c)

            overall_status = (
                ExecutionStatusEnum.ERROR
                if has_error
                else (ExecutionStatusEnum.SUCCESS if all_rows else ExecutionStatusEnum.EMPTY)
            )

            return QueryResultDTO(
                columns=all_cols,
                rows=all_rows,
                row_count=len(all_rows),
                execution_time_ms=total_exec_time,
                execution_mode=SQLExecutionMode.SCATTER_GATHER,
                is_empty=len(all_rows) == 0,
                subquery_results=subquery_results,
                status=overall_status,
                executed_sql=sanitized_dto.sanitized_sql,
                trace_id=t_id,
            )

        # ----------------------------------------------------------------------
        # 3. Chế độ Mặc định: SINGLE_UNIFIED
        # ----------------------------------------------------------------------
        if not sanitized_dto.sanitized_sql.strip():
            return QueryResultDTO(
                columns=[],
                rows=[],
                row_count=0,
                execution_time_ms=0.0,
                execution_mode=SQLExecutionMode.BYPASS_ZERO_SQL,
                is_empty=True,
                status=ExecutionStatusEnum.BYPASS,
                executed_sql="",
                trace_id=t_id,
            )

        columns, rows, exec_time, err_code, err_msg = await self._execute_single_sql_async(
            sql=sanitized_dto.sanitized_sql,
            trace_id=t_id,
            user_ctx=user_ctx,
        )

        if err_code == "57014":
            return QueryResultDTO(
                columns=[],
                rows=[],
                row_count=0,
                execution_time_ms=exec_time,
                execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
                is_empty=True,
                status=ExecutionStatusEnum.TIMEOUT,
                error_code=err_code,
                error_message=err_msg,
                executed_sql=sanitized_dto.sanitized_sql,
                trace_id=t_id,
            )

        if err_code:
            return QueryResultDTO(
                columns=[],
                rows=[],
                row_count=0,
                execution_time_ms=exec_time,
                execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
                is_empty=True,
                status=ExecutionStatusEnum.ERROR,
                error_code=err_code,
                error_message=err_msg,
                executed_sql=sanitized_dto.sanitized_sql,
                trace_id=t_id,
            )

        is_empty = len(rows) == 0
        status = ExecutionStatusEnum.EMPTY if is_empty else ExecutionStatusEnum.SUCCESS

        return QueryResultDTO(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=exec_time,
            execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
            is_empty=is_empty,
            status=status,
            executed_sql=sanitized_dto.sanitized_sql,
            trace_id=t_id,
        )

    def execute_query_sync(
        self,
        sanitized_dto: SanitizedSQLDTO,
        user_ctx: Optional[UserSecurityContextDTO] = None,
        trace_id: str = "",
    ) -> QueryResultDTO:
        """
        Thực thi truy vấn đồng bộ (Sync) qua execute_sync_fallback (psycopg2).
        Thuận tiện cho các script CLI và test runner không đồng bộ.
        """
        t_id = trace_id or sanitized_dto.trace_id or f"exec_sync_{int(time.time())}"

        if sanitized_dto.execution_mode == SQLExecutionMode.BYPASS_ZERO_SQL or not sanitized_dto.sanitized_sql.strip():
            return QueryResultDTO(
                columns=[],
                rows=[],
                row_count=0,
                execution_time_ms=0.0,
                execution_mode=SQLExecutionMode.BYPASS_ZERO_SQL,
                is_empty=True,
                status=ExecutionStatusEnum.BYPASS,
                executed_sql="",
                trace_id=t_id,
            )

        t0 = time.perf_counter()
        try:
            raw_rows = self.pool.execute_sync_fallback(sanitized_dto.sanitized_sql)
            rows = [sanitize_row_dict(r) for r in raw_rows]
            exec_time = (time.perf_counter() - t0) * 1000.0

            columns = []
            if rows:
                columns = [ColumnMetadataDTO(name=col_name, data_type="unknown") for col_name in rows[0].keys()]

            is_empty = len(rows) == 0
            status = ExecutionStatusEnum.EMPTY if is_empty else ExecutionStatusEnum.SUCCESS

            return QueryResultDTO(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                execution_time_ms=exec_time,
                execution_mode=sanitized_dto.execution_mode or SQLExecutionMode.SINGLE_UNIFIED,
                is_empty=is_empty,
                status=status,
                executed_sql=sanitized_dto.sanitized_sql,
                trace_id=t_id,
            )
        except Exception as e:
            exec_time = (time.perf_counter() - t0) * 1000.0
            error_msg = str(e)
            return QueryResultDTO(
                columns=[],
                rows=[],
                row_count=0,
                execution_time_ms=exec_time,
                execution_mode=sanitized_dto.execution_mode or SQLExecutionMode.SINGLE_UNIFIED,
                is_empty=True,
                status=ExecutionStatusEnum.ERROR,
                error_code="SYNC_ERROR",
                error_message=error_msg,
                executed_sql=sanitized_dto.sanitized_sql,
                trace_id=t_id,
            )
