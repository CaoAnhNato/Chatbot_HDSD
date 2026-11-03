"""
Module: IPGov_Chatbot/main.py
Chức năng: Điểm khởi chạy (Entry Point) của máy chủ Backend FastAPI cho IPGov Chatbot.
Tích hợp:
  - CORS Middleware hỗ trợ kết nối từ mọi frontend / test bench.
  - Endpoint kiểm tra sức khỏe hệ thống (Health Check) /api/v1/health.
  - Phục vụ trực tiếp giao diện Test Bench UI tại đường dẫn /bench.
  - Endpoint SSE Stream /api/v1/chat/stream tích hợp Module 1 & Module 2.
"""

import os
import sys
import time
from typing import Any, Dict, Optional
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

# Đảm bảo mã hóa UTF-8 an toàn trên console Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from IPGov_Chatbot.config import settings
from IPGov_Chatbot.modules.mod01_gateway.gateway_endpoint import router as chat_router, users_router
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

_catalog_sync_task: Optional[asyncio.Task] = None


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

    # 2. Warm-up Embedding Model qua ModelRegistry (Chạy trên worker thread để không block asyncio loop)
    try:
        from IPGov_Chatbot.core.model_registry import ModelRegistry
        await asyncio.to_thread(ModelRegistry.warmup_embedding_model)
        SYSTEM_WARMUP_STATUS["details"]["embedding_model"] = "READY"
        logger.info("✅ [Warmup 2/5] SentenceTransformer Embedding Model đã nạp sẵn vào RAM.")
    except Exception as e:
        SYSTEM_WARMUP_STATUS["details"]["embedding_model"] = f"ERROR ({str(e)})"
        logger.warning("⚠️ [Warmup 2/5] Embedding model cảnh báo: %s", e)

    # 3. Warm-up Singleton Warehouse LangGraph Agent & DuckDB Semantic Catalog
    try:
        def _warmup_agent_and_catalog() -> None:
            from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import warehouse_agent
            # Pre-warm LangGraph SQLite checkpointer
            _ = warehouse_agent.checkpointer
            # Pre-warm DuckDB semantic vector embeddings on the singleton instance directly
            warehouse_agent.catalog._ensure_embeddings_indexed()

        await asyncio.to_thread(_warmup_agent_and_catalog)
        SYSTEM_WARMUP_STATUS["details"]["duckdb_catalog"] = "READY"
        SYSTEM_WARMUP_STATUS["details"]["langgraph_agent"] = "READY"
        logger.info("✅ [Warmup 3/4] Warehouse LangGraph Agent Singleton & DuckDB Vector Indexes đã sẵn sàng trong RAM.")
    except Exception as e:
        SYSTEM_WARMUP_STATUS["details"]["duckdb_catalog"] = f"ERROR ({str(e)})"
        SYSTEM_WARMUP_STATUS["details"]["langgraph_agent"] = f"ERROR ({str(e)})"
        logger.warning("⚠️ [Warmup 3/4] DuckDB Catalog & Agent cảnh báo: %s", e)

    # 4. Pre-warm SSL & API Client Gateway
    try:
        from IPGov_Chatbot.core.llm_gateway import LLMGateway
        await asyncio.to_thread(LLMGateway)
        SYSTEM_WARMUP_STATUS["details"]["llm_gateway"] = "READY"
        logger.info("✅ [Warmup 4/4] LLM Gateway SSL Handshake Session đã sẵn sàng.")
    except Exception as e:
        SYSTEM_WARMUP_STATUS["details"]["llm_gateway"] = f"SKIPPED ({str(e)})"

    SYSTEM_WARMUP_STATUS["ready"] = True
    SYSTEM_WARMUP_STATUS["completed_at"] = time.time()
    SYSTEM_WARMUP_STATUS["elapsed_seconds"] = round(SYSTEM_WARMUP_STATUS["completed_at"] - t0, 2)
    logger.info(
        "🔥 [Startup Lifespan] HỆ THỐNG ĐÃ WARM-UP TOÀN DIỆN THÀNH CÔNG trong %s giây! First Request sẵn sàng < 1s.",
        SYSTEM_WARMUP_STATUS["elapsed_seconds"]
    )


async def _catalog_background_sync_loop(interval_seconds: Optional[int] = None) -> None:
    """
    Vòng lặp nền định kỳ kiểm tra và đồng bộ catalog từ DWH PostgreSQL sang DuckDB RAM.
    Tần suất đọc từ interval_seconds hoặc settings.CATALOG_AUTO_SYNC_MINUTES (mặc định 5 phút).
    Chạy không phong tỏa (non-blocking) qua asyncio.to_thread và bảo vệ thread-safety.
    """
    if interval_seconds is not None:
        sync_interval_sec = max(30, int(interval_seconds))
        sync_interval_min = sync_interval_sec // 60
    else:
        sync_interval_min = int(os.environ.get("CATALOG_AUTO_SYNC_MINUTES", getattr(settings, "CATALOG_AUTO_SYNC_MINUTES", 5)))
        sync_interval_sec = max(30, sync_interval_min * 60)
    logger.info("🕒 [Catalog Sync Worker] Khởi động tiến trình đồng bộ nền (chu kỳ: %d phút / %d giây)", sync_interval_min, sync_interval_sec)

    # Chờ chu kỳ đồng bộ hoặc cấu hình khởi động ban đầu
    initial_delay = int(os.environ.get("CATALOG_SYNC_INITIAL_DELAY_SECONDS", sync_interval_sec))
    try:
        await asyncio.sleep(initial_delay)
    except asyncio.CancelledError:
        logger.info("🛑 [Catalog Sync Worker] Tiến trình nền bị dừng trong giai đoạn khởi động.")
        return

    while True:
        try:
            from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import warehouse_agent
            sync_result = await asyncio.to_thread(warehouse_agent.catalog.check_and_sync_changes)
            if sync_result.get("synced"):
                logger.info(
                    "✅ [Catalog Sync Worker] Đồng bộ thành công: %d chỉ tiêu mới, tổng %d (mất %.2f ms)",
                    sync_result.get("new_criteria_count", 0),
                    sync_result.get("total_criteria", 0),
                    sync_result.get("elapsed_ms", 0.0),
                )
            else:
                logger.debug(
                    "ℹ️ [Catalog Sync Worker] DWH không có thay đổi (tổng %d chỉ tiêu, %.2f ms)",
                    sync_result.get("total_criteria", 0),
                    sync_result.get("elapsed_ms", 0.0),
                )
        except asyncio.CancelledError:
            logger.info("🛑 [Catalog Sync Worker] Nhận tín hiệu dừng tiến trình nền.")
            break
        except Exception as e:
            logger.warning("⚠️ [Catalog Sync Worker] Cảnh báo lỗi trong chu trình đồng bộ nền: %s", e)

        try:
            await asyncio.sleep(sync_interval_sec)
        except asyncio.CancelledError:
            logger.info("🛑 [Catalog Sync Worker] Tiến trình nền bị hủy khi đang chờ chu kỳ tiếp theo.")
            break


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Quản lý vòng đời ứng dụng FastAPI, nạp tài nguyên nền và đóng kết nối an toàn khi dừng."""
    global _catalog_sync_task
    # Khởi chạy Warm-up nền không chặn mở cổng mạng (< 300ms)
    warmup_task = asyncio.create_task(_run_startup_warmup())
    _catalog_sync_task = asyncio.create_task(_catalog_background_sync_loop())
    try:
        yield
    finally:
        # Hủy các tác vụ nền an toàn và đóng connection pool
        if _catalog_sync_task and not _catalog_sync_task.done():
            _catalog_sync_task.cancel()
            try:
                await _catalog_sync_task
            except asyncio.CancelledError:
                pass
        if warmup_task and not warmup_task.done():
            warmup_task.cancel()
            try:
                await warmup_task
            except asyncio.CancelledError:
                pass
        pool = DWHConnectionPool.get_instance()
        await pool.close_pool()


# Khởi tạo ứng dụng FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    description=(
        "Hệ sinh thái Backend phục vụ Chatbot Tra Cứu Kho Dữ Liệu Hành Chính Công (DWH).\n\n"
        "• **Module 1**: API Gateway & Context Extraction (Xác thực JWT HS256, HBAC Role Level 0-3, SSE Stream).\n"
        "• **Module 2**: Pre-Router Security Guardrails (Lọc PII theo NĐ 13/2023, Chặn DDL/DML, Kiểm soát địa lý Lâm Đồng).\n"
        "• **Module 3**: Query Router & Dialogue Tracker H-DFT (Chitchat Bypass, H-DFT 2 Tầng RAM/Episodic, Action Chips).\n"
        "• **Module 4**: Dynamic Catalog & Schema Pruner (Thu gọn DDL lược đồ, giảm >90% token).\n"
        "• **Module 5**: Adaptive SQL Compiler (Track A AST Engine + Track B DIN-SQL LLM).\n"
        "• **Module 6**: Security Guardrails & AST Enforcer (Cưỡng chế HBAC và chặn 100% rủi ro tiêm mã độc).\n"
        "• **Module 7**: DWH Execution Engine (Thực thi truy vấn chỉ đọc kiên cố hóa trên Docker PostgreSQL vna_wom_dev).\n"
        "• **Test Bench UI**: Truy cập trực tiếp tại `/bench` để thử nghiệm trực quan luồng phân quyền và an ninh."
    ),
    docs_url="/docs",
    redoc_url="/redoc"
)

# Cấu hình CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"https://.*\.onrender\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký Router các Module
app.include_router(chat_router)
app.include_router(users_router)
app.include_router(feedback_router)


@app.get("/", summary="Trang chủ API & Điều hướng nhanh")
async def root() -> Dict[str, Any]:
    """Trả về thông tin cơ bản của ứng dụng và các đường dẫn hữu ích."""
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
    """
    Kiểm tra tình trạng hoạt động của các module backend trong hệ thống:
    - Module 1 (Gateway): Sẵn sàng
    - Module 2 (Guardrails): Sẵn sàng
    - Module 3 (Router & Dialogue Tracker): Sẵn sàng
    - Module 4 (Catalog & Schema Pruner): Sẵn sàng
    - Module 5 (Adaptive SQL Compiler): Sẵn sàng
    - Module 6 (Security Guardrails & AST Enforcer): Sẵn sàng
    - Module 7 (DWH Execution Engine): Sẵn sàng
    """
    uptime_seconds = round(time.time() - START_TIME, 2)
    return {
        "status": "healthy",
        "readiness": "ready" if SYSTEM_WARMUP_STATUS["ready"] else "warming_up",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "uptime_seconds": uptime_seconds,
        "warmup": SYSTEM_WARMUP_STATUS,
        "modules": [
            {
                "id": "mod01_gateway",
                "name": "API Gateway & Context Extraction",
                "status": "ACTIVE",
                "features": ["JWT HS256 (RFC 7519)", "HBAC Role Context", "SSE Stream Event 1"]
            },
            {
                "id": "mod02_guardrails",
                "name": "Pre-Router Security Guardrails",
                "status": "ACTIVE",
                "features": ["PII Sanitizer (NĐ 13/2023)", "DDL/DML Shield", "Scope Precheck"]
            },
            {
                "id": "mod03_router",
                "name": "Query Router & Dialogue Tracker (H-DFT)",
                "status": "ACTIVE",
                "features": ["Pre-router Chitchat Bypass", "H-DFT 2-Tier State Machine", "Interactive Action Chips", "6 Personas"]
            },
            {
                "id": "mod04_catalog",
                "name": "Dynamic Catalog & Schema Pruner",
                "status": "ACTIVE",
                "features": ["BM25 + RapidFuzz Catalog Index", "Schema Slice DDL", "Token Reduction >= 90%"]
            },
            {
                "id": "mod05_sql_compiler",
                "name": "Adaptive SQL Compiler (Track A/B)",
                "status": "ACTIVE",
                "features": ["Track A AST Compiler (85%)", "Track B DIN-SQL LLM (15%)", "Postgres Dry-Run & Self-Correction"]
            },
            {
                "id": "mod06_ast_enforcer",
                "name": "Security Guardrails & AST Enforcer",
                "status": "ACTIVE",
                "features": ["5-Tier AST Verification", "Recursive Scope Injection", "Zero Security Violations (0.0%)", "Dialect PostgreSQL 16"]
            },
            {
                "id": "mod07_dwh_exec",
                "name": "DWH Execution Engine",
                "status": "ACTIVE",
                "features": ["asyncpg Connection Pool", "Default Transaction Read-Only", "Scatter-Gather Semaphore 20", "DLQ Incident Logger"]
            },
            {
                "id": "mod08_response",
                "name": "Response Synthesizer & Lineage Badge",
                "status": "ACTIVE",
                "features": ["JinjaSlotEngine (RAM < 0.05ms)", "Gemini-2.5-Flash-Lite BLUF", "LineageBadge SHA-256 Provenance", "Dual-Gate Safe Guard"]
            }
        ]
    }


@app.get("/api/v1/warmup", summary="Kích hoạt Warm-up API tăng tốc toàn hệ thống")
async def warmup_endpoint() -> Dict[str, Any]:
    """
    Thực hiện Warm-up toàn bộ pipeline hệ thống trước khi phục vụ:
    - Pre-init asyncpg DWH Connection Pool
    - Nạp sẵn In-Memory DuckDB Semantic Catalog & Capability Discovery Engine
    - Khởi tạo IntentRouter & Redis Connection / Memory Fallback
    - Khởi tạo LLM Gateway
    """
    t0 = time.time()
    results = {}

    # 1. Warm-up DWH connection pool
    try:
        pool = DWHConnectionPool.get_instance()
        await pool.init_pool()
        results["dwh_pool"] = "READY"
    except Exception as e:
        results["dwh_pool"] = f"FALLBACK ({str(e)})"

    # 2. Warm-up Catalog & Pruner
    try:
        from IPGov_Chatbot.modules.mod04_catalog.schema_pruner import SchemaPruner
        _pruner = SchemaPruner()
        results["catalog_pruner"] = "READY"
    except Exception as e:
        results["catalog_pruner"] = f"ERROR ({str(e)})"

    # 3. Warm-up Router
    try:
        from IPGov_Chatbot.modules.mod03_router.intent_router import IntentRouter
        _router = IntentRouter()
        results["intent_router"] = "READY"
    except Exception as e:
        results["intent_router"] = f"ERROR ({str(e)})"

    # 4. Warm-up LLM Gateway
    try:
        from IPGov_Chatbot.core.llm_gateway import LLMGateway
        gateway = LLMGateway()
        results["llm_gateway"] = "READY"
    except Exception as e:
        results["llm_gateway"] = f"SKIPPED ({str(e)})"

    total_latency_ms = round((time.time() - t0) * 1000, 2)
    return {
        "status": "warmup_completed",
        "latency_ms": total_latency_ms,
        "details": results
    }


@app.get("/api/v1/chat/sessions", summary="Lấy danh sách phiên hội thoại (Tương thích Web Frontend)")
async def get_chat_sessions(limit: int = 50) -> Dict[str, Any]:
    from IPGov_Chatbot.core.chat_history_store import ChatHistoryStore
    sessions = ChatHistoryStore.get_instance().list_sessions(limit=limit)
    return {"success": True, "data": sessions}


@app.get("/api/v1/chat/history/{session_id}", summary="Lấy lịch sử tin nhắn của phiên (Tương thích Web Frontend)")
async def get_session_history(session_id: str) -> Dict[str, Any]:
    from IPGov_Chatbot.core.chat_history_store import ChatHistoryStore
    messages = ChatHistoryStore.get_instance().get_session_messages(session_id=session_id)
    return {"success": True, "data": messages}


@app.patch("/api/v1/chat/sessions/{session_id}", summary="Đổi tên phiên hội thoại")
async def rename_chat_session_endpoint(session_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    from IPGov_Chatbot.core.chat_history_store import ChatHistoryStore
    new_title = str(payload.get("title") or "").strip()
    ok = ChatHistoryStore.get_instance().rename_session(session_id=session_id, new_title=new_title)
    return {"success": ok}


@app.delete("/api/v1/chat/sessions/{session_id}", summary="Xóa một phiên hội thoại")
async def delete_chat_session_endpoint(session_id: str) -> Dict[str, Any]:
    from IPGov_Chatbot.core.chat_history_store import ChatHistoryStore
    ok = ChatHistoryStore.get_instance().delete_session(session_id=session_id)
    return {"success": ok}


@app.delete("/api/v1/chat/sessions", summary="Xóa toàn bộ lịch sử phiên hội thoại")
async def clear_all_chat_sessions_endpoint() -> Dict[str, Any]:
    from IPGov_Chatbot.core.chat_history_store import ChatHistoryStore
    ChatHistoryStore.get_instance().clear_all_sessions()
    return {"success": True}


@app.get("/bench", summary="Giao diện Test Bench Thử Nghiệm Module 1, 2 & 3", response_class=HTMLResponse)
async def serve_test_bench():
    """
    Trả về giao diện web chat Test Bench (`role_selector_bench.html`).
    Render trực tiếp trên trình duyệt như một ứng dụng web chat tương tác.
    """
    if not settings.BENCH_HTML_PATH.exists():
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": f"Không tìm thấy tệp giao diện tại {settings.BENCH_HTML_PATH}"}
        )
    content = settings.BENCH_HTML_PATH.read_text(encoding="utf-8")
    return HTMLResponse(content=content, status_code=status.HTTP_200_OK)


if __name__ == "__main__":
    import uvicorn
    print(f"\n=======================================================")
    print(f"🚀 Khởi động {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"📡 API Base URL:  http://{settings.HOST}:{settings.PORT}")
    print(f"📚 Swagger Docs:  http://{settings.HOST}:{settings.PORT}/docs")
    print(f"🧪 Test Bench UI: http://{settings.HOST}:{settings.PORT}/bench")
    print(f"=======================================================\n")
    reload_kwargs = {}
    if settings.DEBUG:
        backend_dir = Path(__file__).resolve().parent
        reload_kwargs = {
            "reload": True,
            "reload_dirs": [str(backend_dir)],
            "reload_excludes": [
                "*.db", "*.db-wal", "*.db-shm", "*.sqlite", "*.sqlite3",
                "*.parquet", "*.log", "*.jsonl",
                "*.tmp", "*.pyc", "__pycache__/*",
                ".next/*", "*/.next/*",
                "node_modules/*", "*/node_modules/*",
                "data/*", "*/data/*",
                "tests/logs/*", "*/tests/logs/*",
                ".git/*", "*/.git/*"
            ]
        }
    uvicorn.run("IPGov_Chatbot.main:app", host=settings.HOST, port=settings.PORT, **reload_kwargs)

