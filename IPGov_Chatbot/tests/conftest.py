"""
Module: IPGov_Chatbot/tests/conftest.py
Chức năng: Cấu hình môi trường kiểm thử pytest và chèn đường dẫn root vào sys.path.
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Đảm bảo thư mục gốc dự án có trong sys.path để import IPGov_Chatbot.*
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def pytest_addoption(parser):
    """Đăng ký cờ tùy biến cho Pytest."""
    parser.addoption(
        "--run-golden-123",
        action="store_true",
        default=False,
        help="Chạy toàn bộ 123 Live LLM Golden Benchmark (chỉ dùng cho nghiệm thu/CI)"
    )
    parser.addoption(
        "--run-golden-106",
        action="store_true",
        default=False,
        help="Chạy toàn bộ 106 Golden SQL Benchmark trên Live PostgreSQL DWH (chỉ dùng cho Module 05)"
    )

