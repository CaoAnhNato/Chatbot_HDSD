"""
Module: IPGov_Chatbot/config.py
Chức năng: Tái xuất bản (Re-export) và liên kết trực tiếp cấu hình tập trung từ backend/config.py.
Đảm bảo Single Source of Truth (SSOT) cho toàn bộ API Keys, Model Configs và System Parameters
trong toàn bộ hệ sinh thái dự án (IPGov_Chatbot & Chatbot HDSD).
Tuân thủ chuẩn Arc42, IEEE Std 1016-2009 và Triết lý Ponytail Lean.
"""

import sys
from pathlib import Path

# Đảm bảo đường dẫn gốc project có trong sys.path để import chéo ổn định
_WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(_WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_DIR))

# Nhập khẩu cấu hình thống nhất từ backend/config.py
try:
    from backend.config import settings, Settings, BACKEND_DIR, WORKSPACE_DIR
except ImportError:
    from config import settings, Settings, BACKEND_DIR, WORKSPACE_DIR

# Alias lớp cấu hình để đảm bảo tương thích ngược 100%
IPGovSettings = Settings

__all__ = [
    "settings",
    "Settings",
    "IPGovSettings",
    "BACKEND_DIR",
    "WORKSPACE_DIR",
]
