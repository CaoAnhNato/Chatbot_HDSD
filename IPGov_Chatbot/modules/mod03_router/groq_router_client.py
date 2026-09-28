"""
IPGov Chatbot - Module 03 Router Client Adapter
Tái xuất bản (Re-export) từ DashScopeRouterClient để đảm bảo tương thích ngược 100%.
Toàn bộ logic định tuyến SSOT LLM đã chuyển sang Alibaba DashScope API.
"""

from IPGov_Chatbot.modules.mod03_router.dashscope_router_client import (
    DashScopeRouterClient,
    GroqRouterClient,
    SYSTEM_ROUTER_PROMPT,
)

__all__ = [
    "DashScopeRouterClient",
    "GroqRouterClient",
    "SYSTEM_ROUTER_PROMPT",
]
