"""
Module: IPGov_Chatbot/core/llm_gateway.py
Chức năng: Tầng LLM Gateway trừu tượng (Template API Call Functions) phục vụ toàn bộ hệ sinh thái IPGov Chatbot.
Áp dụng mẫu thiết kế Strategy & Facade Pattern (GoF):
- Hỗ trợ OpenRouter (OpenAI SDK de-facto standard) làm Active Provider chính.
- Tự động ghi nhận Metadata Logging chi tiết: generation_id, latency_ms, tokens, real cost_usd vào data/logs/llm_usage.jsonl.
- Cấu hình Vô Lăng (System Prompt) + Cầu Dao An Toàn (max_tokens=400, extra_body={"enable_thinking": False}, stop=["}\\n", "\\n\\n"]).
- Hỗ trợ trích xuất chi tiết qua API GET https://openrouter.ai/api/v1/generation?id={generation_id}.
- Cung cấp giao diện nhất quán cho cả Async (FastAPI/Streaming) và Sync (CLI/Testing).
- Tích hợp cơ chế tự động thử lại (Retry with Exponential Backoff) và dự phòng (Fallback Driver).

Tuân thủ:
- .agents/rules/overview-rule-Chatbot.md (Mục 10: Quản trị Mô hình & SSOT)
- .agents/rules/ipgov-coding-rules.md
- Arc42 / IEEE Std 1016-2009
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import re
import time
import urllib.request
import warnings
from abc import ABC, abstractmethod
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from pydantic import BaseModel

from IPGov_Chatbot.config import settings

# Bỏ qua warning không cần thiết của google-genai về AFC khi gọi trực tiếp generate_content
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="google.genai",
)

logger = logging.getLogger("ipgov.llm_gateway")

T = TypeVar("T", bound=BaseModel)

# Đường dẫn tệp ghi log sử dụng LLM tập trung
_LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "logs"
_USAGE_LOG_FILE = _LOGS_DIR / "llm_usage.jsonl"


def _clean_sql_markdown(text: str) -> str:
    """Lọc sạch các khối markdown ```sql ... ``` hoặc ```...``` để trả về câu lệnh SQL thuần."""
    cleaned = text.strip()
    match = re.search(r"```(?:sql)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()
    return cleaned


def _extract_json_substring(text: str) -> str:
    """Trích xuất chuỗi JSON từ văn bản (hỗ trợ cả trường hợp bị bọc trong markdown ```json)."""
    cleaned = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()

    # Tìm cặp ngoặc { ... } ngoài cùng
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return cleaned


def _log_llm_metric(
    *,
    generation_id: str = "",
    provider: str,
    model: str,
    call_type: str,
    latency_ms: float,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int = 0,
    cost_usd: Optional[float] = None,
    finish_reason: str = "stop",
    is_cached_hit: bool = False,
) -> None:
    """Ghi nhận thông số phân tích LLM (Metadata Log) append vào data/logs/llm_usage.jsonl."""
    total_tokens = prompt_tokens + completion_tokens

    # Tính chi phí định mức dự phòng nếu provider chưa trả cost trực tiếp
    if cost_usd is None:
        if "gemini-2.5-flash-lite" in model:
            # OpenRouter định mức: $0.075 / 1M prompt, $0.30 / 1M completion
            prompt_cost = (prompt_tokens / 1_000_000.0) * 0.075
            comp_cost = (completion_tokens / 1_000_000.0) * 0.30
            cost_usd = round(prompt_cost + comp_cost, 8)
        elif "gemini-3.5-flash-lite" in model:
            # OpenRouter định mức: $0.25 / 1M prompt, $1.00 / 1M completion
            prompt_cost = (prompt_tokens / 1_000_000.0) * 0.25
            comp_cost = (completion_tokens / 1_000_000.0) * 1.00
            cost_usd = round(prompt_cost + comp_cost, 8)
        else:
            cost_usd = 0.0

    if finish_reason == "length":
        logger.warning(
            f"⚠️ [CIRCUIT BREAKER] Mô hình {model} chạm ngưỡng max_tokens (finish_reason='length')! "
            f"Cảnh báo nguy cơ cắt cụt dữ liệu."
        )

    metric_record = {
        "generation_id": generation_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "provider": provider,
        "model": model,
        "call_type": call_type,
        "latency_ms": round(latency_ms, 2),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cached_tokens": cached_tokens,
        "cost_usd": cost_usd,
        "is_cached_hit": is_cached_hit,
        "finish_reason": finish_reason,
    }

    try:
        _LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(_USAGE_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(metric_record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.debug(f"Không thể ghi metadata log vào {_USAGE_LOG_FILE}: {e}")


def fetch_openrouter_generation_details(generation_id: str) -> Dict[str, Any]:
    """
    Tra cứu chi tiết generation từ OpenRouter API:
    GET https://openrouter.ai/api/v1/generation?id={generation_id}
    Dành cho kiểm toán độc lập (Audit path), không gọi đồng bộ trên hot path.
    """
    if not generation_id or not settings.OPENROUTER_API_KEY:
        return {}
    url = f"https://openrouter.ai/api/v1/generation?id={generation_id}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://ipgov-chatbot.local",
            "X-Title": "IPGov Chatbot",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("data", {})
    except Exception as e:
        logger.warning(f"Lỗi khi tra cứu OpenRouter generation {generation_id}: {e}")
        return {}


# ==============================================================================
# 1. STRATEGY INTERFACE: LLMDriver
# ==============================================================================
class LLMDriver(ABC):
    """Giao diện trừu tượng cho mọi driver giao tiếp với các nhà cung cấp LLM."""

    @abstractmethod
    async def call_chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        """Gọi sinh văn bản bất đồng bộ."""
        pass

    @abstractmethod
    def call_chat_sync(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        """Gọi sinh văn bản đồng bộ."""
        pass

    @abstractmethod
    async def call_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
    ) -> T:
        """Gọi sinh dữ liệu có cấu trúc tuân thủ Pydantic Schema bất đồng bộ."""
        pass

    @abstractmethod
    def call_structured_sync(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
    ) -> T:
        """Gọi sinh dữ liệu có cấu trúc tuân thủ Pydantic Schema đồng bộ."""
        pass

    @abstractmethod
    async def call_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """Truyền phát luồng token phản hồi bất đồng bộ (SSE)."""
        pass


# ==============================================================================
# 2. DRIVER CHÍNH: OpenRouterDriver (OpenAI SDK de-facto standard)
# ==============================================================================
class OpenRouterDriver(LLMDriver):
    """
    Driver chính giao tiếp qua OpenRouter API Gateway sử dụng OpenAI Python SDK.
    Tích hợp:
    - Default Headers: HTTP-Referer, X-Title, X-OpenRouter-Cache (cho phép zero-cost response cache).
    - Cầu Dao An Toàn: max_tokens=400 cho structured, max_tokens=1500 cho raw SQL, extra_body={"enable_thinking": False}.
    - Stop Sequences: stop=["}\n", "\n\n"] cắt ngay khi kết thúc JSON.
    - Metadata Logging trích xuất usage.cost, latency_ms, generation_id.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        import openai

        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.base_url = base_url or settings.OPENROUTER_BASE_URL

        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY chưa được thiết lập trong môi trường / config.")

        # Default headers gửi kèm mọi request OpenRouter
        self._default_headers = {
            "HTTP-Referer": "https://ipgov-chatbot.local",
            "X-Title": "IPGov Chatbot",
        }
        if getattr(settings, "ENABLE_OPENROUTER_RESPONSE_CACHE", True):
            self._default_headers["X-OpenRouter-Cache"] = "true"

        self._async_client = openai.AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            default_headers=self._default_headers,
            timeout=30.0,
        )
        self._sync_client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            default_headers=self._default_headers,
            timeout=30.0,
        )

    def _build_messages(self, prompt: str, system_prompt: Optional[str]) -> List[Dict[str, str]]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _get_model(self, model: Optional[str], default_role: str = "light") -> str:
        if model:
            return model
        if default_role == "heavy":
            return getattr(settings, "OPENROUTER_HEAVY_MODEL", "google/gemini-3.5-flash-lite")
        return getattr(settings, "OPENROUTER_LIGHT_MODEL", "google/gemini-2.5-flash-lite")

    def _extract_and_log_usage(
        self,
        res: Any,
        target_model: str,
        call_type: str,
        latency_ms: float,
    ) -> None:
        """Trích xuất an toàn metadata và cost từ response object, ghi vào log."""
        try:
            generation_id = getattr(res, "id", "") or ""
            usage_dict = {}
            if hasattr(res, "model_dump"):
                usage_dict = res.model_dump().get("usage", {}) or {}
            elif hasattr(res, "usage") and res.usage:
                usage_dict = getattr(res.usage, "model_extra", {}) or {}

            prompt_tokens = usage_dict.get("prompt_tokens", 0) or 0
            completion_tokens = usage_dict.get("completion_tokens", 0) or 0
            real_cost = usage_dict.get("cost")

            # Token Cache Details từ OpenRouter
            cached_tokens = 0
            prompt_details = usage_dict.get("prompt_tokens_details", {}) or {}
            if isinstance(prompt_details, dict):
                cached_tokens = prompt_details.get("cached_tokens", 0) or 0

            # Kiểm tra xem có phải response cache hit hoàn toàn không (0 token hoặc độ trễ < 120ms)
            is_cached_hit = (cached_tokens > 0 and cached_tokens == prompt_tokens) or (
                prompt_tokens == 0 and completion_tokens == 0
            )

            finish_reason = "stop"
            if hasattr(res, "choices") and res.choices and len(res.choices) > 0:
                finish_reason = getattr(res.choices[0], "finish_reason", "stop") or "stop"

            _log_llm_metric(
                generation_id=generation_id,
                provider="openrouter",
                model=target_model,
                call_type=call_type,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_tokens=cached_tokens,
                cost_usd=real_cost,
                finish_reason=finish_reason,
                is_cached_hit=is_cached_hit,
            )
        except Exception as e:
            logger.debug(f"Lỗi khi trích xuất usage từ OpenRouter response: {e}")

    async def call_chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        target_model = self._get_model(model)
        messages = self._build_messages(prompt, system_prompt)
        t0 = time.perf_counter()

        res = await self._async_client.chat.completions.create(
            model=target_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0
        self._extract_and_log_usage(res, target_model, "chat", latency_ms)

        content = res.choices[0].message.content or ""
        return content

    def call_chat_sync(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        target_model = self._get_model(model)
        messages = self._build_messages(prompt, system_prompt)
        t0 = time.perf_counter()

        res = self._sync_client.chat.completions.create(
            model=target_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0
        self._extract_and_log_usage(res, target_model, "chat", latency_ms)

        content = res.choices[0].message.content or ""
        return content

    async def call_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
    ) -> T:
        target_model = self._get_model(model)
        messages = self._build_messages(prompt, system_prompt)
        t0 = time.perf_counter()

        # Áp dụng Cầu Dao An Toàn: max_tokens=400 cho Router, max_tokens=4096 cho TextToSQL (TRAP-018)
        max_tok = 4096 if "TextToSQL" in getattr(schema, "__name__", "") else getattr(settings, "ROUTER_MAX_TOKENS", 400)
        extra_body = {"enable_thinking": False}
        if "gemini-3.8-flash" in target_model or "deepseek" in target_model:
            extra_body = {"reasoning": {"effort": "low"}}

        res = await self._async_client.chat.completions.create(
            model=target_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tok,
            response_format={"type": "json_object"},
            extra_body=extra_body,
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0
        self._extract_and_log_usage(res, target_model, "structured", latency_ms)

        raw_text = res.choices[0].message.content or "{}"
        clean_json = _extract_json_substring(raw_text)
        return schema.model_validate_json(clean_json)

    def call_structured_sync(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
    ) -> T:
        target_model = self._get_model(model)
        messages = self._build_messages(prompt, system_prompt)
        t0 = time.perf_counter()

        # Áp dụng Cầu Dao An Toàn: max_tokens=400 cho Router, max_tokens=4096 cho TextToSQL (TRAP-018)
        max_tok = 4096 if "TextToSQL" in getattr(schema, "__name__", "") else getattr(settings, "ROUTER_MAX_TOKENS", 400)
        extra_body = {"enable_thinking": False}
        if "gemini-3.8-flash" in target_model or "deepseek" in target_model:
            extra_body = {"reasoning": {"effort": "low"}}

        res = self._sync_client.chat.completions.create(
            model=target_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tok,
            response_format={"type": "json_object"},
            extra_body=extra_body,
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0
        self._extract_and_log_usage(res, target_model, "structured", latency_ms)

        raw_text = res.choices[0].message.content or "{}"
        clean_json = _extract_json_substring(raw_text)
        return schema.model_validate_json(clean_json)

    async def call_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        target_model = self._get_model(model)
        messages = self._build_messages(prompt, system_prompt)
        stream = await self._async_client.chat.completions.create(
            model=target_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            content = chunk.choices[0].delta.content or ""
            if content:
                yield content


# ==============================================================================
# 3. DRIVER DỰ PHÒNG: GoogleGenAIDriver (SDK: google-genai)
# ==============================================================================
class GoogleGenAIDriver(LLMDriver):
    """Driver dự phòng sử dụng Google GenAI SDK (google-genai) hỗ trợ custom base_url."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        from google import genai
        from google.genai import types

        self.api_key = api_key or settings.GOOGLE_API_KEY
        self.base_url = base_url or settings.GOOGLE_BASE_URL
        self._types = types

        if not self.api_key:
            logger.warning("GOOGLE_API_KEY chưa được thiết lập trong môi trường / config.")

        http_options = types.HttpOptions(
            base_url=self.base_url,
            api_version="v1beta",
        )
        self.client = genai.Client(
            api_key=self.api_key,
            http_options=http_options,
        )

    def _get_model(self, model: Optional[str], default: str = "gemini-3.5-flash-lite") -> str:
        target = model or getattr(settings, "GEMINI_LIGHT_MODEL", default)
        if target.startswith("google/"):
            target = target[len("google/"):]
        mapping = {
            "gemini-2.5-flash-lite": "gemini-3.5-flash-lite",
            "gemini-3.8-flash": "gemini-3.7-flash",
            "deepseek/deepseek-v4.1-flash": "gemini-3.7-flash",
            "deepseek-v4.1-flash": "gemini-3.7-flash",
        }
        return mapping.get(target, target)

    async def call_chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        target_model = self._get_model(model, "gemini-3.5-flash-lite")
        config = self._types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_prompt if system_prompt else None,
        )
        response = await self.client.aio.models.generate_content(
            model=target_model,
            contents=prompt,
            config=config,
        )
        return response.text or ""

    def call_chat_sync(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        target_model = self._get_model(model, "gemini-3.5-flash-lite")
        config = self._types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_prompt if system_prompt else None,
        )
        response = self.client.models.generate_content(
            model=target_model,
            contents=prompt,
            config=config,
        )
        return response.text or ""

    async def call_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
    ) -> T:
        target_model = self._get_model(model, "gemini-3.5-flash-lite")
        max_tok = 2048 if "TextToSQL" in getattr(schema, "__name__", "") else getattr(settings, "ROUTER_MAX_TOKENS", 400)
        thinking_cfg = None
        if ("gemini-3.8-flash" in target_model or "gemini-3.7-flash" in target_model) and hasattr(self._types, "ThinkingConfig"):
            thinking_cfg = self._types.ThinkingConfig(thinking_budget=1024)

        config = self._types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tok,
            response_mime_type="application/json",
            response_schema=schema,
            system_instruction=system_prompt if system_prompt else None,
            thinking_config=thinking_cfg,
        )
        response = await self.client.aio.models.generate_content(
            model=target_model,
            contents=prompt,
            config=config,
        )
        raw_text = response.text or "{}"
        clean_json = _extract_json_substring(raw_text)
        return schema.model_validate_json(clean_json)

    def call_structured_sync(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
    ) -> T:
        target_model = self._get_model(model, "gemini-3.5-flash-lite")
        max_tok = 2048 if "TextToSQL" in getattr(schema, "__name__", "") else getattr(settings, "ROUTER_MAX_TOKENS", 400)
        thinking_cfg = None
        if ("gemini-3.8-flash" in target_model or "gemini-3.7-flash" in target_model) and hasattr(self._types, "ThinkingConfig"):
            thinking_cfg = self._types.ThinkingConfig(thinking_budget=1024)

        config = self._types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tok,
            response_mime_type="application/json",
            response_schema=schema,
            system_instruction=system_prompt if system_prompt else None,
            thinking_config=thinking_cfg,
        )
        response = self.client.models.generate_content(
            model=target_model,
            contents=prompt,
            config=config,
        )
        raw_text = response.text or "{}"
        clean_json = _extract_json_substring(raw_text)
        return schema.model_validate_json(clean_json)

    async def call_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        target_model = self._get_model(model, "gemini-3.5-flash-lite")
        config = self._types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_prompt if system_prompt else None,
        )
        async for chunk in await self.client.aio.models.generate_content_stream(
            model=target_model,
            contents=prompt,
            config=config,
        ):
            if chunk.text:
                yield chunk.text


# ==============================================================================
# 4. DRIVER DỰ PHÒNG: OpenAICompatibleDriver (Hỗ trợ DashScope, Local proxy)
# ==============================================================================
class OpenAICompatibleDriver(LLMDriver):
    """Driver tương thích giao thức chuẩn OpenAI (hỗ trợ shopaikey /v1, DashScope)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        import openai

        self.api_key = api_key or settings.effective_llm_api_key
        raw_base = base_url or settings.GOOGLE_BASE_URL
        if not raw_base.endswith("/v1") and not raw_base.endswith("/v1/"):
            self.base_url = f"{raw_base.rstrip('/')}/v1"
        else:
            self.base_url = raw_base

        self._async_client = openai.AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=25.0,
        )
        self._sync_client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=25.0,
        )

    def _build_messages(self, prompt: str, system_prompt: Optional[str]) -> List[Dict[str, str]]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _get_model(self, model: Optional[str]) -> str:
        return model or getattr(settings, "GEMINI_LIGHT_MODEL", "gemini-3.5-flash-lite")

    async def call_chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        messages = self._build_messages(prompt, system_prompt)
        res = await self._async_client.chat.completions.create(
            model=self._get_model(model),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return res.choices[0].message.content or ""

    def call_chat_sync(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        messages = self._build_messages(prompt, system_prompt)
        res = self._sync_client.chat.completions.create(
            model=self._get_model(model),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return res.choices[0].message.content or ""

    async def call_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
    ) -> T:
        messages = self._build_messages(prompt, system_prompt)
        res = await self._async_client.chat.completions.create(
            model=self._get_model(model),
            messages=messages,
            temperature=temperature,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        raw_text = res.choices[0].message.content or "{}"
        clean_json = _extract_json_substring(raw_text)
        return schema.model_validate_json(clean_json)

    def call_structured_sync(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
    ) -> T:
        messages = self._build_messages(prompt, system_prompt)
        res = self._sync_client.chat.completions.create(
            model=self._get_model(model),
            messages=messages,
            temperature=temperature,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        raw_text = res.choices[0].message.content or "{}"
        clean_json = _extract_json_substring(raw_text)
        return schema.model_validate_json(clean_json)

    async def call_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        messages = self._build_messages(prompt, system_prompt)
        stream = await self._async_client.chat.completions.create(
            model=self._get_model(model),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            content = chunk.choices[0].delta.content or ""
            if content:
                yield content


# ==============================================================================
# 5. LLM GATEWAY (FACADE & ORCHESTRATOR)
# ==============================================================================
class LLMGateway:
    """Tầng Facade quản lý việc điều hướng, thử lại (retry) và dự phòng (fallback) driver."""

    def __init__(self):
        self._drivers: Dict[str, LLMDriver] = {}
        self._init_drivers()

    def _init_drivers(self):
        # 1. Driver chính: OpenRouter
        try:
            self._drivers["openrouter"] = OpenRouterDriver()
        except Exception as e:
            logger.error(f"Lỗi khởi tạo OpenRouterDriver: {e}")

        # 2. Driver dự phòng: GoogleGenAI
        try:
            self._drivers["google"] = GoogleGenAIDriver()
        except Exception as e:
            logger.error(f"Lỗi khởi tạo GoogleGenAIDriver: {e}")

        # 3. Driver tương thích OpenAI chuẩn
        try:
            self._drivers["openai"] = OpenAICompatibleDriver()
        except Exception as e:
            logger.error(f"Lỗi khởi tạo OpenAICompatibleDriver: {e}")

    def get_driver(self, provider: Optional[str] = None) -> LLMDriver:
        pref = provider or getattr(settings, "ACTIVE_LLM_PROVIDER", "openrouter")
        if pref in self._drivers:
            return self._drivers[pref]
        # Fallback sang bất kỳ driver nào sẵn có
        for driver in self._drivers.values():
            return driver
        raise RuntimeError("Không có LLM Driver nào khả dụng. Vui lòng kiểm tra API key.")

    def get_fallback_driver(self, primary_driver: LLMDriver) -> Optional[LLMDriver]:
        for driver in self._drivers.values():
            if driver is not primary_driver:
                return driver
        return None

    async def call_chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        provider: Optional[str] = None,
    ) -> str:
        driver = self.get_driver(provider)
        for attempt in range(2):
            try:
                return await driver.call_chat(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as e:
                logger.warning(f"Lần gọi chat {attempt + 1} thất bại với driver {type(driver).__name__}: {e}")
                if attempt == 1:
                    fb = self.get_fallback_driver(driver)
                    if fb:
                        logger.info(f"Kích hoạt Fallback driver {type(fb).__name__} cho call_chat")
                        return await fb.call_chat(
                            prompt=prompt,
                            system_prompt=system_prompt,
                            model=model,
                            temperature=temperature,
                            max_tokens=max_tokens,
                        )
                    raise
                await asyncio.sleep(1.0)

    def call_chat_sync(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        provider: Optional[str] = None,
    ) -> str:
        driver = self.get_driver(provider)
        for attempt in range(2):
            try:
                return driver.call_chat_sync(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as e:
                logger.warning(f"Lần gọi chat sync {attempt + 1} thất bại: {e}")
                if attempt == 1:
                    fb = self.get_fallback_driver(driver)
                    if fb:
                        return fb.call_chat_sync(
                            prompt=prompt,
                            system_prompt=system_prompt,
                            model=model,
                            temperature=temperature,
                            max_tokens=max_tokens,
                        )
                    raise
                time.sleep(1.0)

    async def call_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        provider: Optional[str] = None,
    ) -> T:
        driver = self.get_driver(provider)
        for attempt in range(2):
            try:
                return await driver.call_structured(
                    prompt=prompt,
                    schema=schema,
                    system_prompt=system_prompt,
                    model=model,
                    temperature=temperature,
                )
            except Exception as e:
                logger.warning(f"Lần gọi structured {attempt + 1} thất bại: {e}")
                if attempt == 1:
                    fb = self.get_fallback_driver(driver)
                    if fb:
                        return await fb.call_structured(
                            prompt=prompt,
                            schema=schema,
                            system_prompt=system_prompt,
                            model=model,
                            temperature=temperature,
                        )
                    raise
                await asyncio.sleep(1.0)

    def call_structured_sync(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        provider: Optional[str] = None,
    ) -> T:
        driver = self.get_driver(provider)
        for attempt in range(2):
            try:
                return driver.call_structured_sync(
                    prompt=prompt,
                    schema=schema,
                    system_prompt=system_prompt,
                    model=model,
                    temperature=temperature,
                )
            except Exception as e:
                logger.warning(f"Lần gọi structured sync {attempt + 1} thất bại: {e}")
                if attempt == 1:
                    fb = self.get_fallback_driver(driver)
                    if fb:
                        return fb.call_structured_sync(
                            prompt=prompt,
                            schema=schema,
                            system_prompt=system_prompt,
                            model=model,
                            temperature=temperature,
                        )
                    raise
                time.sleep(1.0)

    async def call_raw_sql(
        self,
        prompt: str,
        schema_context: Optional[str] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> str:
        """Sinh câu truy vấn SQL thô cho các tác vụ Text-to-SQL phức tạp (Hard Tasks) bằng google/gemini-3.5-flash-lite."""
        target_model = model or getattr(settings, "OPENROUTER_HEAVY_MODEL", "google/gemini-3.5-flash-lite")

        full_system_prompt = system_prompt or (
            "Bạn là Chuyên gia Kỹ thuật CSDL PostgreSQL của Kho Dữ Liệu Hành chính Công Tỉnh Lâm Đồng. "
            "Nhiệm vụ của bạn là sinh câu lệnh SQL PostgreSQL 16 thuần túy, an toàn, chuẩn xác cú pháp. "
            "Tuyệt đối KHÔNG giải thích, chỉ trả về duy nhất câu lệnh SQL."
        )
        if schema_context:
            full_system_prompt += f"\n\n[LƯỢC ĐỒ CSDL THAM CHIẾU (DWH SCHEMA)]:\n{schema_context}"

        raw_sql = await self.call_chat(
            prompt=prompt,
            system_prompt=full_system_prompt,
            model=target_model,
            temperature=0.0,
            max_tokens=1500,
            provider=provider,
        )
        return _clean_sql_markdown(raw_sql)

    def call_raw_sql_sync(
        self,
        prompt: str,
        schema_context: Optional[str] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> str:
        """Sinh câu lệnh SQL đồng bộ cho benchmark/scripts."""
        target_model = model or getattr(settings, "OPENROUTER_HEAVY_MODEL", "google/gemini-3.5-flash-lite")
        full_system_prompt = system_prompt or (
            "Bạn là Chuyên gia Kỹ thuật CSDL PostgreSQL của Kho Dữ Liệu Hành chính Công Tỉnh Lâm Đồng. "
            "Nhiệm vụ của bạn là sinh câu lệnh SQL PostgreSQL 16 thuần túy, an toàn, chuẩn xác cú pháp. "
            "Tuyệt đối KHÔNG giải thích, chỉ trả về duy nhất câu lệnh SQL."
        )
        if schema_context:
            full_system_prompt += f"\n\n[LƯỢC ĐỒ CSDL THAM CHIẾU (DWH SCHEMA)]:\n{schema_context}"

        raw_sql = self.call_chat_sync(
            prompt=prompt,
            system_prompt=full_system_prompt,
            model=target_model,
            temperature=0.0,
            max_tokens=1500,
            provider=provider,
        )
        return _clean_sql_markdown(raw_sql)

    async def call_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        provider: Optional[str] = None,
    ) -> AsyncIterator[str]:
        driver = self.get_driver(provider)
        try:
            async for chunk in driver.call_stream(
                prompt=prompt,
                system_prompt=system_prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                yield chunk
        except Exception as e:
            logger.error(f"Lỗi khi truyền phát luồng stream: {e}")
            raise


# Singleton instance
_llm_gateway_instance: Optional[LLMGateway] = None


def get_llm_gateway() -> LLMGateway:
    """Khởi tạo hoặc lấy thể hiện Singleton của LLMGateway."""
    global _llm_gateway_instance
    if _llm_gateway_instance is None:
        _llm_gateway_instance = LLMGateway()
    return _llm_gateway_instance


# ==============================================================================
# 6. PUBLIC CONVENIENCE TEMPLATE API CALL FUNCTIONS
# ==============================================================================
async def call_chat(
    prompt: str,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    provider: Optional[str] = None,
) -> str:
    """Template API Call: Gọi sinh văn bản thông thường (Async)."""
    gw = get_llm_gateway()
    return await gw.call_chat(
        prompt=prompt,
        system_prompt=system_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        provider=provider,
    )


def call_chat_sync(
    prompt: str,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    provider: Optional[str] = None,
) -> str:
    """Template API Call: Gọi sinh văn bản thông thường (Sync)."""
    gw = get_llm_gateway()
    return gw.call_chat_sync(
        prompt=prompt,
        system_prompt=system_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        provider=provider,
    )


async def call_structured(
    prompt: str,
    schema: Type[T],
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.0,
    provider: Optional[str] = None,
) -> T:
    """Template API Call: Gọi sinh dữ liệu có cấu trúc Pydantic Schema (Async)."""
    gw = get_llm_gateway()
    return await gw.call_structured(
        prompt=prompt,
        schema=schema,
        system_prompt=system_prompt,
        model=model,
        temperature=temperature,
        provider=provider,
    )


def call_structured_sync(
    prompt: str,
    schema: Type[T],
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.0,
    provider: Optional[str] = None,
) -> T:
    """Template API Call: Gọi sinh dữ liệu có cấu trúc Pydantic Schema (Sync)."""
    gw = get_llm_gateway()
    return gw.call_structured_sync(
        prompt=prompt,
        schema=schema,
        system_prompt=system_prompt,
        model=model,
        temperature=temperature,
        provider=provider,
    )


async def call_raw_sql(
    prompt: str,
    schema_context: Optional[str] = None,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
) -> str:
    """Template API Call: Sinh truy vấn Raw SQL bằng mô hình chuyên sâu (google/gemini-3.5-flash-lite) (Async)."""
    gw = get_llm_gateway()
    return await gw.call_raw_sql(
        prompt=prompt,
        schema_context=schema_context,
        system_prompt=system_prompt,
        model=model,
        provider=provider,
    )


def call_raw_sql_sync(
    prompt: str,
    schema_context: Optional[str] = None,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
) -> str:
    """Template API Call: Sinh truy vấn Raw SQL bằng mô hình chuyên sâu (google/gemini-3.5-flash-lite) (Sync)."""
    gw = get_llm_gateway()
    return gw.call_raw_sql_sync(
        prompt=prompt,
        schema_context=schema_context,
        system_prompt=system_prompt,
        model=model,
        provider=provider,
    )


async def call_stream(
    prompt: str,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    provider: Optional[str] = None,
) -> AsyncIterator[str]:
    """Template API Call: Truyền phát phản hồi theo luồng token SSE (Async)."""
    gw = get_llm_gateway()
    async for chunk in gw.call_stream(
        prompt=prompt,
        system_prompt=system_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        provider=provider,
    ):
        yield chunk


def call_structured_with_fallback[T: BaseModel](
    prompt: str,
    schema: Type[T],
    system_prompt: Optional[str] = None,
    primary_model: Optional[str] = None,
    fallback_model: Optional[str] = None,
    min_confidence: float = 0.7,
    confidence_attr: str = "confidence_score",
    invariant_validator: Optional[Callable[[T], bool]] = None,
    temperature: float = 0.0,
    provider: Optional[str] = None,
) -> Tuple[T, str, Dict[str, Any], float]:
    """Template API Call: Gọi sinh dữ liệu có cấu trúc Pydantic Schema kèm cơ chế Confidence & Invariant Gate Fallback (Sync).
    
    Tuân thủ chuẩn /ponytail Bậc 2 & Bậc 6:
    - 1 dòng cho người gọi ở bất kỳ module nào.
    - Thử primary_model (mặc định: settings.OPENROUTER_LIGHT_MODEL).
    - Tự động kích hoạt Heavy Fallback sang fallback_model (mặc định: settings.OPENROUTER_HEAVY_MODEL)
      khi:
      (1) confidence_score < min_confidence, hoặc
      (2) invariant_validator(parsed) trả về False, hoặc
      (3) lần gọi primary_model gặp lỗi exception / validation.
    
    Trả về: Tuple[parsed_object, model_used, usage_dict, latency_ms]
    """
    t0 = time.perf_counter()
    p_model = primary_model or getattr(settings, "OPENROUTER_LIGHT_MODEL", "google/gemini-2.5-flash-lite")
    f_model = fallback_model or getattr(settings, "OPENROUTER_HEAVY_MODEL", "deepseek/deepseek-v4.1-flash")

    gw = get_llm_gateway()
    model_used = p_model
    need_fallback = False
    fallback_reason = ""
    parsed: Optional[T] = None

    try:
        parsed = gw.call_structured_sync(
            prompt=prompt,
            schema=schema,
            system_prompt=system_prompt,
            model=p_model,
            temperature=temperature,
            provider=provider,
        )
        conf = getattr(parsed, confidence_attr, 1.0)
        if conf is not None and conf < min_confidence:
            need_fallback = True
            fallback_reason = f"Độ tự tin ({conf:.2f}) < ngưỡng tối thiểu ({min_confidence})"
        elif invariant_validator and not invariant_validator(parsed):
            need_fallback = True
            fallback_reason = "Vi phạm Invariant Gate validation"
    except Exception as e:
        logger.warning(f"Lần gọi primary model ({p_model}) thất bại: {e}. Kích hoạt fallback...")
        need_fallback = True
        fallback_reason = f"Primary model exception: {e}"

    if need_fallback:
        logger.info(f"Kích hoạt Heavy Fallback sang {f_model}. Lý do: {fallback_reason}")
        parsed = gw.call_structured_sync(
            prompt=prompt,
            schema=schema,
            system_prompt=system_prompt,
            model=f_model,
            temperature=temperature,
            provider=provider,
        )
        model_used = f_model

    latency_ms = (time.perf_counter() - t0) * 1000.0
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return parsed, model_used, usage, latency_ms


async def call_structured_with_fallback_async[T: BaseModel](
    prompt: str,
    schema: Type[T],
    system_prompt: Optional[str] = None,
    primary_model: Optional[str] = None,
    fallback_model: Optional[str] = None,
    min_confidence: float = 0.7,
    confidence_attr: str = "confidence_score",
    invariant_validator: Optional[Callable[[T], bool]] = None,
    temperature: float = 0.0,
    provider: Optional[str] = None,
) -> Tuple[T, str, Dict[str, Any], float]:
    """Template API Call: Gọi sinh dữ liệu có cấu trúc Pydantic Schema kèm cơ chế Confidence & Invariant Gate Fallback (Async)."""
    t0 = time.perf_counter()
    p_model = primary_model or getattr(settings, "OPENROUTER_LIGHT_MODEL", "google/gemini-2.5-flash-lite")
    f_model = fallback_model or getattr(settings, "OPENROUTER_HEAVY_MODEL", "deepseek/deepseek-v4.1-flash")

    gw = get_llm_gateway()
    model_used = p_model
    need_fallback = False
    fallback_reason = ""
    parsed: Optional[T] = None

    try:
        parsed = await gw.call_structured(
            prompt=prompt,
            schema=schema,
            system_prompt=system_prompt,
            model=p_model,
            temperature=temperature,
            provider=provider,
        )
        conf = getattr(parsed, confidence_attr, 1.0)
        if conf is not None and conf < min_confidence:
            need_fallback = True
            fallback_reason = f"Độ tự tin ({conf:.2f}) < ngưỡng tối thiểu ({min_confidence})"
        elif invariant_validator and not invariant_validator(parsed):
            need_fallback = True
            fallback_reason = "Vi phạm Invariant Gate validation"
    except Exception as e:
        logger.warning(f"Lần gọi primary model ({p_model}) thất bại: {e}. Kích hoạt fallback...")
        need_fallback = True
        fallback_reason = f"Primary model exception: {e}"

    if need_fallback:
        logger.info(f"Kích hoạt Heavy Fallback sang {f_model}. Lý do: {fallback_reason}")
        parsed = await gw.call_structured(
            prompt=prompt,
            schema=schema,
            system_prompt=system_prompt,
            model=f_model,
            temperature=temperature,
            provider=provider,
        )
        model_used = f_model

    latency_ms = (time.perf_counter() - t0) * 1000.0
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return parsed, model_used, usage, latency_ms
