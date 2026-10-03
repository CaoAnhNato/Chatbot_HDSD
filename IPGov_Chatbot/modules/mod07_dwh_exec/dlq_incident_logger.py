"""
Module: IPGov_Chatbot/modules/mod07_dwh_exec/dlq_incident_logger.py
Chức năng: Ghi nhận sự cố truy vấn vào hàng đợi Dead-Letter-Queue (public.chatbot_dlq_incidents).
Căn cứ:
- Blueprint: 06_OBSERVABILITY_TRACING_DLQ_VA_EVALUATION.md (Mục 2)
- Quyết định /grill-me: Tự động xuất bản ghi sự cố khi xảy ra lỗi cú pháp, vi phạm AST hoặc timeout.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import psycopg2

from IPGov_Chatbot.config import settings

logger = logging.getLogger("ipgov.mod07.dlq_logger")

CREATE_DLQ_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS public.chatbot_dlq_incidents (
    incident_id UUID PRIMARY KEY,
    trace_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    tenant_code VARCHAR(64) NOT NULL,
    department_code VARCHAR(64),
    raw_prompt TEXT NOT NULL,
    generated_sql TEXT,
    error_stage VARCHAR(32) NOT NULL,
    error_message TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved BOOLEAN DEFAULT FALSE
);
"""

INSERT_DLQ_SQL = """
INSERT INTO public.chatbot_dlq_incidents (
    incident_id, trace_id, user_id, tenant_code, department_code,
    raw_prompt, generated_sql, error_stage, error_message, created_at, resolved
) VALUES (
    %(incident_id)s, %(trace_id)s, %(user_id)s, %(tenant_code)s, %(department_code)s,
    %(raw_prompt)s, %(generated_sql)s, %(error_stage)s, %(error_message)s, CURRENT_TIMESTAMP, FALSE
);
"""


class DLQIncidentLogger:
    """
    Ghi nhận sự cố Dead-Letter-Queue.
    Sử dụng kết nối ghi riêng biệt (không dùng pool read-only của analytics queries).
    Có cơ chế Fallback ghi ra tệp JSON Lines nếu CSDL mất kết nối.
    """

    def __init__(self) -> None:
        self.host = settings.DWH_HOST
        self.port = int(settings.DWH_PORT)
        self.dbname = settings.DWH_DB
        self.user = settings.DWH_USER
        self.password = getattr(settings, "DWH_PASSWORD", None) or getattr(settings, "DWH_PASS", "postgres")
        self.fallback_file = Path("data/logs/dlq_incidents.jsonl")
        self._ensure_table_exists()

    def _ensure_table_exists(self) -> None:
        """Đảm bảo bảng public.chatbot_dlq_incidents đã tồn tại."""
        try:
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                connect_timeout=2,
            )
            with conn.cursor() as cur:
                cur.execute(CREATE_DLQ_TABLE_SQL)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Không thể khởi tạo bảng DLQ trên PostgreSQL (sẽ dùng file log fallback): {e}")

    def _fallback_log_to_file(self, incident_data: Dict[str, Any]) -> None:
        """Ghi sự cố ra tệp JSON Lines khi CSDL không khả dụng."""
        try:
            self.fallback_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.fallback_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(incident_data, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Lỗi nghiêm trọng khi ghi fallback DLQ file: {e}")

    def log_incident_sync(
        self,
        trace_id: str,
        user_id: str,
        tenant_code: str,
        department_code: Optional[str],
        raw_prompt: str,
        generated_sql: str,
        error_stage: str,
        error_message: str,
    ) -> str:
        """Ghi nhận sự cố đồng bộ (Sync). Trả về incident_id dạng UUID chuỗi."""
        inc_id = str(uuid.uuid4())
        data = {
            "incident_id": inc_id,
            "trace_id": trace_id or "unknown_trace",
            "user_id": user_id or "anonymous",
            "tenant_code": tenant_code or "68",
            "department_code": department_code,
            "raw_prompt": raw_prompt or "",
            "generated_sql": generated_sql or "",
            "error_stage": error_stage,
            "error_message": error_message,
        }

        try:
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                connect_timeout=2,
            )
            with conn.cursor() as cur:
                cur.execute(INSERT_DLQ_SQL, data)
            conn.commit()
            conn.close()
            logger.info(f"Đã ghi nhận sự cố DLQ [{inc_id}] vào PostgreSQL (Stage: {error_stage}).")
            return inc_id
        except Exception as e:
            logger.warning(f"Lỗi ghi DLQ vào PostgreSQL ({e}). Chuyển sang fallback file.")
            data["timestamp"] = time.time()
            self._fallback_log_to_file(data)
            return inc_id

    async def log_incident_async(
        self,
        trace_id: str,
        user_id: str,
        tenant_code: str,
        department_code: Optional[str],
        raw_prompt: str,
        generated_sql: str,
        error_stage: str,
        error_message: str,
    ) -> str:
        """Ghi nhận sự cố bất đồng bộ (Non-blocking)."""
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self.log_incident_sync,
            trace_id,
            user_id,
            tenant_code,
            department_code,
            raw_prompt,
            generated_sql,
            error_stage,
            error_message,
        )
