"""
Module: IPGov_Chatbot/modules/mod07_dwh_exec/connection_pool.py
Chức năng: Quản lý vòng đời kết nối CSDL PostgreSQL DWH (vna_wom_dev) kiên cố hóa 2 tầng.
Căn cứ:
- Blueprint: 00_TECH_STACK_VA_KIEN_TRUC_TONG_THE.md
- Blueprint: 01_DATA_WAREHOUSE_VA_CAY_THUC_THE_DWH.md
- Quyết định /grill-me: asyncpg.Pool với default_transaction_read_only = on & statement_timeout = 5000ms.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, Optional

import asyncpg

from IPGov_Chatbot.config import settings

logger = logging.getLogger("ipgov.mod07.connection_pool")


class DWHConnectionPool:
    """
    Singleton quản lý asyncpg.Pool kết nối tới PostgreSQL DWH vna_wom_dev.
    Kiên cố hóa 2 tầng:
    1. Cấp CSDL: server_settings={"default_transaction_read_only": "on"} (Chặn ghi dữ liệu)
    2. Cấp Engine: command_timeout = 5.0s (Safety Circuit Breaker chống treo luồng)
    """

    _instance: Optional[DWHConnectionPool] = None
    _pool: Optional[asyncpg.Pool] = None
    _lock = asyncio.Lock()

    def __init__(self) -> None:
        self.host = settings.DWH_HOST
        self.port = int(settings.DWH_PORT)
        self.dbname = settings.DWH_DB
        self.user = settings.DWH_USER
        self.password = getattr(settings, "DWH_PASSWORD", None) or getattr(settings, "DWH_PASS", "postgres")
        self.min_size = getattr(settings, "DWH_POOL_MIN_SIZE", 2)
        self.max_size = getattr(settings, "DWH_POOL_MAX_SIZE", 20)
        self.command_timeout = getattr(settings, "DWH_TIMEOUT_SECONDS", 5.0)

    @classmethod
    def get_instance(cls) -> DWHConnectionPool:
        if cls._instance is None:
            cls._instance = DWHConnectionPool()
        return cls._instance

    async def init_pool(self) -> asyncpg.Pool:
        """Khởi tạo asyncpg connection pool nếu chưa có hoặc loop đã đổi."""
        current_loop = asyncio.get_running_loop()
        if self._pool is not None and not self._pool._closed:
            if getattr(self._pool, "_loop", None) is current_loop:
                return self._pool
            else:
                try:
                    self._pool.terminate()
                except Exception:
                    pass
                self._pool = None

        try:
            dsn = getattr(settings, "DWH_DATABASE_URL", None) or os.getenv("DATABASE_URL")
            if dsn:
                clean_dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
                self._pool = await asyncpg.create_pool(
                    dsn=clean_dsn,
                    min_size=self.min_size,
                    max_size=self.max_size,
                    command_timeout=self.command_timeout,
                    server_settings={
                        "default_transaction_read_only": "on",
                        "statement_timeout": "5000",
                    },
                )
                logger.info(
                    f"Đã khởi tạo asyncpg.Pool qua DSN ({self.min_size}-{self.max_size} connections, READ-ONLY, timeout=5s)."
                )
            else:
                self._pool = await asyncpg.create_pool(
                    host=self.host,
                    port=self.port,
                    database=self.dbname,
                    user=self.user,
                    password=self.password,
                    min_size=self.min_size,
                    max_size=self.max_size,
                    command_timeout=self.command_timeout,
                    server_settings={
                        "default_transaction_read_only": "on",
                        "statement_timeout": "5000",
                    },
                )
                logger.info(
                    f"Đã khởi tạo asyncpg.Pool [{self.dbname}] ({self.min_size}-{self.max_size} connections, READ-ONLY, timeout=5s)."
                )
            return self._pool
        except Exception as e:
            logger.error(f"Lỗi khởi tạo asyncpg.Pool: {e}")
            raise

    async def get_pool(self) -> asyncpg.Pool:
        """Lấy pool đang hoạt động hoặc tự động khởi tạo."""
        current_loop = asyncio.get_running_loop()
        if (
            self._pool is None
            or self._pool._closed
            or getattr(self._pool, "_loop", None) is not current_loop
        ):
            return await self.init_pool()
        return self._pool

    async def close_pool(self) -> None:
        """Đóng an toàn connection pool khi tắt ứng dụng."""
        if self._pool is not None and not self._pool._closed:
            try:
                current_loop = asyncio.get_running_loop()
                if getattr(self._pool, "_loop", None) is current_loop:
                    await self._pool.close()
                else:
                    self._pool.terminate()
            except Exception:
                self._pool.terminate()
            logger.info("Đã đóng asyncpg.Pool an toàn.")
            self._pool = None

    def execute_sync_fallback(
        self, sql: str, parameters: Optional[Dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        """
        Bộ chuyển đổi đồng bộ (Sync Fallback) dùng psycopg2 cho các kịch bản chạy đồng bộ.
        Cưỡng chế phiên READ ONLY.
        """
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(
            host=self.host,
            port=self.port,
            dbname=self.dbname,
            user=self.user,
            password=self.password,
            connect_timeout=2,
            options="-c default_transaction_read_only=on -c statement_timeout=5000",
        )
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if parameters:
                    cur.execute(sql, parameters)
                else:
                    cur.execute(sql)
                if cur.description is not None:
                    rows = cur.fetchall()
                    return [dict(r) for r in rows]
                return []
        finally:
            conn.close()
