import sys
import asyncio
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
from IPGov_Chatbot.modules.mod07_dwh_exec.connection_pool import DWHConnectionPool

async def check():
    pool_mgr = DWHConnectionPool.get_instance()
    pool = await pool_mgr.init_pool()
    async with pool.acquire() as conn:
        res2025 = await conn.fetchval("SELECT count(*) FROM dwh_internal.fact_report_criteria WHERE year = '2025';")
        res2026 = await conn.fetchval("SELECT count(*) FROM dwh_internal.fact_report_criteria WHERE year = '2026';")
        res_other = await conn.fetchval("SELECT count(*) FROM dwh_internal.fact_report_criteria WHERE year NOT IN ('2025', '2026');")
        print(f"Total rows in 2025: {res2025}")
        print(f"Total rows in 2026: {res2026}")
        print(f"Total rows in other years: {res_other}")

asyncio.run(check())
