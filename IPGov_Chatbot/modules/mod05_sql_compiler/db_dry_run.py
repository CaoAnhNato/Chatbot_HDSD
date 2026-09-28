"""
Module: IPGov_Chatbot/modules/mod05_sql_compiler/db_dry_run.py
Chức năng: Kiểm định thực thi trực tiếp trên PostgreSQL qua EXPLAIN (FORMAT JSON).
Căn cứ:
- Blueprint: 05_MULTI_AGENT_WORKFLOW_DIN_MAC_SQL.md (Mục 6)
- Specification: IPGov_Chatbot/docs/MODULE_05_SQL_COMPILER_SPEC.md (Mục 7.1)
- Tuân thủ: Tầng 2 Live DB Dry-run (< 5ms) trước khi trả về DTO.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("ipgov.mod05.db_dry_run")


class DatabaseDryRunner:
    """
    Trình kiểm tra cú pháp và kế hoạch thực thi trực tiếp trên CSDL PostgreSQL.
    Chạy lệnh `EXPLAIN (FORMAT JSON) <query>` trên Docker localhost:5432 để đảm bảo
    100% câu SQL trả về hợp lệ trên dialect PostgreSQL 16.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        dbname: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        self.host = host or os.getenv("DWH_HOST", "localhost")
        self.port = int(port or os.getenv("DWH_PORT", "5432"))
        self.dbname = dbname or os.getenv("DWH_DB", "vna_wom_dev")
        self.user = user or os.getenv("DWH_USER", "postgres")
        self.password = password or os.getenv("DWH_PASS", "postgres")
        self._async_pool = None

    def _replace_named_parameters(self, sql: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Thay thế các bind parameters dạng :param bằng giá trị cụ thể để chạy EXPLAIN."""
        res_sql = sql
        defaults = {
            "tenant_code": "68",
            "year": "2026",
            "metric_code": "kinh_phi_khuyen_cong",
            "top_k": "5",
            "limit": "5",
            "offset": "0",
        }
        if params:
            defaults.update({k: str(v) for k, v in params.items()})

        int_param_names = {"top_k", "limit", "offset", "k", "n", "page_size", "count"}
        for k, v in defaults.items():
            pattern = re.compile(rf"(?<!:):{k}\b", re.IGNORECASE)
            if (k.lower() in int_param_names or str(v).isdigit()) and str(v).isdigit():
                res_sql = pattern.sub(str(v), res_sql)
            else:
                val_clean = str(v).replace("'", "''")
                res_sql = pattern.sub(f"'{val_clean}'", res_sql)

        # Xử lý các tham số theo sau LIMIT hoặc OFFSET (phải là số nguyên)
        res_sql = re.sub(
            r"(?i)\b(LIMIT|OFFSET)\s+(?<!:):([a-zA-Z_0-9]+)\b",
            lambda m: f"{m.group(1)} 5" if m.group(1).upper() == "LIMIT" else f"{m.group(1)} 0",
            res_sql,
        )

        # Thay thế bất kỳ :param nào còn sót lại (dùng số nếu tên tham số có vẻ là số, ngược lại dùng chuỗi)
        def _fallback_param_repl(m: re.Match) -> str:
            name = m.group(1).lower()
            if name in int_param_names:
                return "5"
            return "'default_val'"

        res_sql = re.sub(r"(?<!:):([a-zA-Z_0-9]+)\b", _fallback_param_repl, res_sql)
        return res_sql

    def dry_run_explain_sync(
        self,
        sql: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[Dict[str, Any]]]:
        """
        Kiểm tra câu lệnh SQL bằng psycopg2 EXPLAIN (Sync).
        Trả về: Tuple[is_valid, pg_code, error_message, plan_dict]
        """
        clean_sql = sql.strip().rstrip(";")
        prepared_sql = self._replace_named_parameters(clean_sql, parameters)
        explain_query = f"EXPLAIN (FORMAT JSON) {prepared_sql};"

        try:
            import psycopg2
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                connect_timeout=2,
            )
            with conn.cursor() as cur:
                cur.execute(explain_query)
                row = cur.fetchone()
                plan_json = row[0] if row else None
            conn.close()
            return True, None, None, plan_json
        except Exception as e:
            pg_code = getattr(e, "pgcode", "UNKNOWN")
            err_msg = str(e)
            logger.warning(f"Live DB Dry-Run thất bại [PG Code: {pg_code}]: {err_msg}")
            return False, pg_code, err_msg, None

    async def dry_run_explain_async(
        self,
        sql: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[Dict[str, Any]]]:
        """
        Kiểm tra câu lệnh SQL bằng asyncpg EXPLAIN (Async).
        Trả về: Tuple[is_valid, pg_code, error_message, plan_dict]
        """
        clean_sql = sql.strip().rstrip(";")
        prepared_sql = self._replace_named_parameters(clean_sql, parameters)
        explain_query = f"EXPLAIN (FORMAT JSON) {prepared_sql};"

        try:
            import asyncpg
            conn = await asyncpg.connect(
                host=self.host,
                port=self.port,
                database=self.dbname,
                user=self.user,
                password=self.password,
                timeout=2.0,
            )
            try:
                row = await conn.fetchval(explain_query)
                return True, None, None, row
            finally:
                await conn.close()
        except Exception as e:
            pg_code = getattr(e, "sqlstate", "UNKNOWN")
            err_msg = str(e)
            logger.warning(f"Async Live DB Dry-Run thất bại [PG Code: {pg_code}]: {err_msg}")
            return False, pg_code, err_msg, None
