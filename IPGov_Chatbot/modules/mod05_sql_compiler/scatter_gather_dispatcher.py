"""
Module: IPGov_Chatbot/modules/mod05_sql_compiler/scatter_gather_dispatcher.py
Chức năng: Điều phối thu thập song song đa truy vấn Scatter-Gather bằng asyncio.gather và asyncpg.
Căn cứ:
- Blueprint: 05_MULTI_AGENT_WORKFLOW_DIN_MAC_SQL.md (Mục 5.4)
- Specification: IPGov_Chatbot/docs/MODULE_05_SQL_COMPILER_SPEC.md (Mục 5.4)
- Chỉ kích hoạt khi các nguồn dữ liệu độc lập không thể gộp thành Single Unified SQL.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional

from IPGov_Chatbot.schemas.sql_compiler_schema import SubqueryTaskItem

logger = logging.getLogger("ipgov.mod05.scatter_gather")


class ScatterGatherDispatcher:
    """
    Bộ điều phối Scatter-Gather thu thập kết quả từ N subquery tasks song song.
    Sử dụng asyncpg connection pool và asyncio.Semaphore để kiểm soát tải.
    """

    def __init__(
        self,
        max_concurrency: int = 20,
        host: Optional[str] = None,
        port: Optional[int] = None,
        dbname: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.host = host or os.getenv("DWH_HOST", "localhost")
        self.port = int(port or os.getenv("DWH_PORT", "5432"))
        self.dbname = dbname or os.getenv("DWH_DB", "vna_wom_dev")
        self.user = user or os.getenv("DWH_USER", "postgres")
        self.password = password or os.getenv("DWH_PASS", "postgres")
        self._pool: Optional[Any] = None

    async def get_pool(self) -> Any:
        """Khởi tạo hoặc tái sử dụng asyncpg Connection Pool."""
        if self._pool is None:
            import asyncpg
            self._pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.dbname,
                user=self.user,
                password=self.password,
                min_size=2,
                max_size=20,
                command_timeout=10.0,
            )
        return self._pool

    async def close(self) -> None:
        """Đóng connection pool giải phóng tài nguyên."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def _execute_single_task(
        self,
        task: SubqueryTaskItem,
        pool: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Thực thi một subquery task đơn lẻ trong phạm vi Semaphore bằng connection pool."""
        async with self.semaphore:
            t0 = time.perf_counter()
            try:
                import asyncpg
                if pool is not None:
                    async with pool.acquire() as conn:
                        rows = await conn.fetch(task.sql)
                else:
                    conn_str = f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"
                    conn = await asyncpg.connect(conn_str, timeout=5.0)
                    try:
                        rows = await conn.fetch(task.sql)
                    finally:
                        await conn.close()

                latency = (time.perf_counter() - t0) * 1000.0
                return {
                    "task_id": task.task_id,
                    "status": "SUCCESS",
                    "row_count": len(rows),
                    "rows": [dict(r) for r in rows],
                    "latency_ms": latency,
                    "target_metric": task.target_metric,
                    "target_period": task.target_period,
                    "target_entity": task.target_entity,
                }
            except Exception as e:
                latency = (time.perf_counter() - t0) * 1000.0
                logger.warning(f"Lỗi khi chạy task {task.task_id}: {e}")
                return {
                    "task_id": task.task_id,
                    "status": "FAILED",
                    "error": str(e),
                    "row_count": 0,
                    "rows": [],
                    "latency_ms": latency,
                }

    async def dispatch_scatter_gather(
        self,
        tasks: List[SubqueryTaskItem],
    ) -> Dict[str, Any]:
        """Thu thập kết quả từ toàn bộ tasks qua asyncio.gather và connection pool."""
        if not tasks:
            return {"total_tasks": 0, "results": []}

        pool = None
        try:
            pool = await self.get_pool()
        except Exception as e:
            logger.warning(f"Không thể khởi tạo pool trong ScatterGather: {e}, fallback sang single connection")

        coros = [self._execute_single_task(t, pool) for t in tasks]
        results = await asyncio.gather(*coros)

        success_count = sum(1 for r in results if r["status"] == "SUCCESS")
        return {
            "total_tasks": len(tasks),
            "successful_tasks": success_count,
            "failed_tasks": len(tasks) - success_count,
            "results": list(results),
        }
