"""
Module: IPGov_Chatbot/run_server.py
Chức năng: Script khởi chạy máy chủ backend qua dòng lệnh CLI với các tùy chọn linh hoạt.
Ví dụ sử dụng:
    python -m IPGov_Chatbot.run_server
    python -m IPGov_Chatbot.run_server --port 8080 --host 0.0.0.0
"""

import argparse
import sys
import uvicorn

# Đảm bảo mã hóa UTF-8 an toàn trên console Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from IPGov_Chatbot.config import settings


def parse_arguments() -> argparse.Namespace:
    """Xử lý các tham số dòng lệnh."""
    parser = argparse.ArgumentParser(
        description="Khởi chạy hệ sinh thái Backend IPGov Chatbot."
    )
    parser.add_argument(
        "--host",
        type=str,
        default=settings.HOST,
        help=f"Địa chỉ IP máy chủ (mặc định: {settings.HOST})"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.PORT,
        help=f"Cổng lắng nghe (mặc định: {settings.PORT})"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=settings.DEBUG,
        help="Bật tính năng tự động reload khi mã nguồn thay đổi"
    )
    parser.add_argument(
        "--no-reload",
        dest="reload",
        action="store_false",
        help="Tắt tính năng reload"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Số lượng tiến trình worker (mặc định: 1)"
    )
    return parser.parse_args()


def main():
    """Hàm thực thi chính."""
    args = parse_arguments()
    print("\n" + "=" * 65)
    print(f"🚀 IPGov Chatbot Backend Server (FastAPI + Uvicorn)")
    print(f"📡 Địa chỉ phục vụ:  http://{args.host}:{args.port}")
    print(f"📖 Swagger OpenAPI:   http://{args.host}:{args.port}/docs")
    print(f"🩺 Sức khỏe hệ thống: http://{args.host}:{args.port}/api/v1/health")
    print(f"🧪 Test Bench UI:     http://{args.host}:{args.port}/bench")
    print("=" * 65 + "\n")

    uvicorn.run(
        "IPGov_Chatbot.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1
    )


if __name__ == "__main__":
    main()
