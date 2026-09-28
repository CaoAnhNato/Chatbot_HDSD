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

# Đảm bảo mã hóa UTF-8 an toàn trên console Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from IPGov_Chatbot.config import settings
from IPGov_Chatbot.modules.mod01_gateway.gateway_endpoint import router as chat_router
from IPGov_Chatbot.modules.mod01_gateway.feedback_endpoint import router as feedback_router

# Khởi tạo thời gian khởi động
START_TIME = time.time()

# Khởi tạo ứng dụng FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Hệ sinh thái Backend phục vụ Chatbot Tra Cứu Kho Dữ Liệu Hành Chính Công (DWH).\n\n"
        "• **Module 1**: API Gateway & Context Extraction (Xác thực JWT HS256, HBAC Role Level 0-3, SSE Stream).\n"
        "• **Module 2**: Pre-Router Security Guardrails (Lọc PII theo NĐ 13/2023, Chặn DDL/DML, Kiểm soát địa lý Lâm Đồng).\n"
        "• **Module 3**: Query Router & Dialogue Tracker H-DFT (Chitchat Bypass, H-DFT 2 Tầng RAM/Episodic, Action Chips).\n"
        "• **Test Bench UI**: Truy cập trực tiếp tại `/bench` để thử nghiệm trực quan luồng phân quyền và an ninh."
    ),
    docs_url="/docs",
    redoc_url="/redoc"
)

# Cấu hình CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký Router các Module
app.include_router(chat_router)
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
    Kiểm tra tình trạng hoạt động của các module backend trong giai đoạn MVP:
    - Module 1 (Gateway): Sẵn sàng
    - Module 2 (Guardrails): Sẵn sàng
    - Module 3 (Router & Dialogue Tracker): Sẵn sàng
    """
    uptime_seconds = round(time.time() - START_TIME, 2)
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "uptime_seconds": uptime_seconds,
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
            }
        ]
    }


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
    uvicorn.run("IPGov_Chatbot.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
    # Trigger uvicorn auto-reload for Module 03 v2.0

