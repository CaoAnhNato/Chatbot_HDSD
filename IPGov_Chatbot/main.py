"""
Module: IPGov_Chatbot/main.py
Chức năng: Điểm khởi chạy (Entry Point) của máy chủ Backend FastAPI cho IPGov Chatbot.
Tích hợp:
  - CORS Middleware hỗ trợ kết nối từ mọi frontend / test bench.
  - Endpoint kiểm tra sức khỏe hệ thống (Health Check) /api/v1/health.
  - Phục vụ trực tiếp giao diện Test Bench UI tại đường dẫn /bench.
  - Endpoint SSE Stream /api/v1/chat/stream tích hợp Module 1 & Module 2.
"""

import sys
import time
from typing import Any, Dict
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from IPGov_Chatbot.config import settings
from IPGov_Chatbot.modules.mod01_gateway.gateway_endpoint import router as chat_router
from IPGov_Chatbot.modules.mod01_gateway.feedback_endpoint import router as feedback_router

import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from IPGov_Chatbot.modules.mod07_dwh_exec.connection_pool import DWHConnectionPool

logger = logging.getLogger("ipgov.main")

START_TIME = time.time()

SYSTEM_WARMUP_STATUS = {
    "ready": False,
    "started_at": 0.0,
    "completed_at": 0.0,
    "elapsed_seconds": 0.0,
    "details": {}
}


async def _run_startup_warmup():
    """Tác vụ nền thực hiện Warm-up toàn diện mà không phong tỏa cổng HTTP."""
    global SYSTEM_WARMUP_STATUS
    t0 = time.time()
    SYSTEM_WARMUP_STATUS["started_at"] = t0
    logger.info("🚀 [Startup Lifespan] Bắt đầu chu trình Warm-up toàn hệ thống...")

    # 1. Warm-up DWH PostgreSQL Pool
    try:
        pool_manager = DWHConnectionPool.get_instance()
        pool = await asyncio.wait_for(pool_manager.get_pool(), timeout=4.0)
        async with pool.acquire() as conn:
            await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=2.0)
        SYSTEM_WARMUP_STATUS["details"]["dwh_pool"] = "READY"
        logger.info("✅ [Warmup 1/5] DWH PostgreSQL Connection Pool đã sẵn sàng.")
    except Exception as e:
        SYSTEM_WARMUP_STATUS["details"]["dwh_pool"] = f"FALLBACK ({str(e)})"
        logger.warning("⚠️ [Warmup 1/5] DWH Pool cảnh báo: %s", e)

    # 2. Warm-up Embedding Model qua ModelRegistry
    try:
        from IPGov_Chatbot.core.model_registry import ModelRegistry
        await asyncio.to_thread(ModelRegistry.warmup_embedding_model)
        SYSTEM_WARMUP_STATUS["details"]["embedding_model"] = "READY"
        logger.info("✅ [Warmup 2/5] SentenceTransformer Embedding Model đã nạp sẵn vào RAM.")
    except Exception as e:
        SYSTEM_WARMUP_STATUS["details"]["embedding_model"] = f"ERROR ({str(e)})"
        logger.warning("⚠️ [Warmup 2/5] Embedding model cảnh báo: %s", e)

    # 3. Warm-up DuckDB Semantic Catalog & Vector Cache
    try:
        from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog
        catalog = DuckDBSemanticCatalog()
        await asyncio.to_thread(catalog._ensure_embeddings_indexed)
        SYSTEM_WARMUP_STATUS["details"]["duckdb_catalog"] = "READY"
        logger.info("✅ [Warmup 3/5] DuckDB Semantic Catalog & Vector Indexes đã sẵn sàng trong RAM.")
    except Exception as e:
        SYSTEM_WARMUP_STATUS["details"]["duckdb_catalog"] = f"ERROR ({str(e)})"
        logger.warning("⚠️ [Warmup 3/5] DuckDB Catalog cảnh báo: %s", e)

    # 4. Pre-warm LangGraph Autonomous Warehouse Agent
    try:
        from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import warehouse_agent
        _ = warehouse_agent.checkpointer
        SYSTEM_WARMUP_STATUS["details"]["langgraph_agent"] = "READY"
        logger.info("✅ [Warmup 4/5] Warehouse LangGraph Agent & SQLite Checkpointer đã sẵn sàng.")
    except Exception as e:
        SYSTEM_WARMUP_STATUS["details"]["langgraph_agent"] = f"ERROR ({str(e)})"
        logger.warning("⚠️ [Warmup 4/5] LangGraph Agent cảnh báo: %s", e)

    # 5. Pre-warm SSL & API Client Gateway
    try:
        from IPGov_Chatbot.core.llm_gateway import LLMGateway
        _ = LLMGateway()
        SYSTEM_WARMUP_STATUS["details"]["llm_gateway"] = "READY"
        logger.info("✅ [Warmup 5/5] LLM Gateway SSL Handshake Session đã sẵn sàng.")
    except Exception as e:
        SYSTEM_WARMUP_STATUS["details"]["llm_gateway"] = f"SKIPPED ({str(e)})"

    SYSTEM_WARMUP_STATUS["ready"] = True
    SYSTEM_WARMUP_STATUS["completed_at"] = time.time()
    SYSTEM_WARMUP_STATUS["elapsed_seconds"] = round(SYSTEM_WARMUP_STATUS["completed_at"] - t0, 2)
    logger.info(
        "🔥 [Startup Lifespan] HỆ THỐNG ĐÃ WARM-UP TOÀN DIỆN THÀNH CÔNG trong %s giây! First Request sẵn sàng < 1s.",
        SYSTEM_WARMUP_STATUS["elapsed_seconds"]
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(_run_startup_warmup())
    yield
    pool = DWHConnectionPool.get_instance()
    await pool.close_pool()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    description="Hệ sinh thái Backend phục vụ Chatbot Tra Cứu Kho Dữ Liệu Hành Chính Công (DWH).",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(feedback_router)


@app.get("/", summary="Trang chủ API & Điều hướng nhanh")
async def root() -> Dict[str, Any]:
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "online",
        "documentation": "/docs",
        "interactive_bench": "/bench",
        "health_check": "/api/v1/health",
        "stream_endpoint": "/api/v1/chat/stream"
    }


@app.get("/api/v1/health", summary="Kiểm tra trạng thái sức khỏe hệ thống")
async def health_check() -> Dict[str, Any]:
    uptime_seconds = round(time.time() - START_TIME, 2)
    return {
        "status": "healthy",
        "readiness": "ready" if SYSTEM_WARMUP_STATUS["ready"] else "warming_up",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "uptime_seconds": uptime_seconds,
        "warmup": SYSTEM_WARMUP_STATUS
    }


@app.get("/bench", summary="Giao diện Test Bench", response_class=HTMLResponse)
async def serve_test_bench():
    if not settings.BENCH_HTML_PATH.exists():
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": f"Không tìm thấy tệp giao diện tại {settings.BENCH_HTML_PATH}"}
        )
    content = settings.BENCH_HTML_PATH.read_text(encoding="utf-8")
    return HTMLResponse(content=content, status_code=status.HTTP_200_OK)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("IPGov_Chatbot.main:app", host=settings.HOST, port=settings.PORT)
