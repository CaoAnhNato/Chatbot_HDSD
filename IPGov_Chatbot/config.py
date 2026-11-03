"""
Module: IPGov_Chatbot/config.py
Chức năng: Tái xuất bản (Re-export) và liên kết trực tiếp cấu hình tập trung từ config.py ở thư mục gốc.
Đảm bảo Single Source of Truth (SSOT) cho toàn bộ API Keys, Model Configs và System Parameters
trong kiến trúc Monorepo 2 dự án (Chatbot_HDSD/ & IPGov_Chatbot/).
Tuân thủ chuẩn Arc42, IEEE Std 1016-2009 và Triết lý Ponytail Lean.
"""

import importlib.util
import sys
from pathlib import Path

_WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(_WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_DIR))

_ROOT_CONFIG_PATH = _WORKSPACE_DIR / "config.py"
if "_root_shared_config" in sys.modules:
    _root_cfg = sys.modules["_root_shared_config"]
else:
    _spec = importlib.util.spec_from_file_location("_root_shared_config", _ROOT_CONFIG_PATH)
    _root_cfg = importlib.util.module_from_spec(_spec)
    sys.modules["_root_shared_config"] = _root_cfg
    assert _spec is not None and _spec.loader is not None
    _spec.loader.exec_module(_root_cfg)

settings = _root_cfg.settings
Settings = _root_cfg.Settings
BACKEND_DIR = _root_cfg.BACKEND_DIR
WORKSPACE_DIR = _root_cfg.WORKSPACE_DIR
HDSD_DIR = _root_cfg.HDSD_DIR
IPGOV_DIR = _root_cfg.IPGOV_DIR

# Alias lớp cấu hình để đảm bảo tương thích ngược 100%
IPGovSettings = Settings

# Re-export cấu hình OpenRouter End-Provider Routing & Reasoning Guard cho Planner
OPENROUTER_PLANNER_MODEL = settings.OPENROUTER_PLANNER_MODEL
OPENROUTER_PLANNER_PROVIDER_ORDER = settings.OPENROUTER_PLANNER_PROVIDER_ORDER
OPENROUTER_PLANNER_ALLOW_FALLBACKS = settings.OPENROUTER_PLANNER_ALLOW_FALLBACKS
OPENROUTER_PLANNER_REASONING_ENABLED = settings.OPENROUTER_PLANNER_REASONING_ENABLED
AGENT_PRIMARY_MODEL = settings.AGENT_PRIMARY_MODEL
CATALOG_AUTO_SYNC_MINUTES = getattr(settings, "CATALOG_AUTO_SYNC_MINUTES", 5)

__all__ = [
    "settings",
    "Settings",
    "IPGovSettings",
    "BACKEND_DIR",
    "WORKSPACE_DIR",
    "HDSD_DIR",
    "IPGOV_DIR",
    "OPENROUTER_PLANNER_MODEL",
    "OPENROUTER_PLANNER_PROVIDER_ORDER",
    "OPENROUTER_PLANNER_ALLOW_FALLBACKS",
    "OPENROUTER_PLANNER_REASONING_ENABLED",
    "AGENT_PRIMARY_MODEL",
    "CATALOG_AUTO_SYNC_MINUTES",
]
