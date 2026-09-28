"""
Unit tests for IPGov Chatbot LLM Gateway & Template API Call Functions.
Kiểm thử tính năng gọi mô hình Google Gemini qua shopaikey gateway:
- gemini-3.5-flash-lite cho tác vụ thông thường (chat, structured output, streaming)
- gemini-3.7-flash cho tác vụ khó (raw SQL generation)
"""

import pytest
from pydantic import BaseModel, Field

from IPGov_Chatbot.config import settings
from IPGov_Chatbot.core.llm_gateway import (
    call_chat,
    call_chat_sync,
    call_structured,
    call_structured_sync,
    call_raw_sql,
    call_raw_sql_sync,
    call_stream,
    call_structured_with_fallback,
    call_structured_with_fallback_async,
    get_llm_gateway,
)


class SampleDecisionSchema(BaseModel):
    intent: str = Field(description="Mục đích người dùng")
    confidence: float = Field(description="Độ tin cậy từ 0 đến 1")
    notes: str = Field(description="Ghi chú ngắn gọn")


@pytest.mark.asyncio
async def test_call_chat_async():
    """Kiểm thử gọi sinh văn bản bất đồng bộ qua gemini-3.5-flash-lite."""
    res = await call_chat(
        prompt="Hãy phản hồi duy nhất một từ: PONG",
        system_prompt="Bạn là trợ lý kiểm thử hệ thống.",
        temperature=0.0,
    )
    assert len(res.strip()) > 0
    assert "PONG" in res.upper()


def test_call_chat_sync():
    """Kiểm thử gọi sinh văn bản đồng bộ qua gemini-3.5-flash-lite."""
    res = call_chat_sync(
        prompt="Hãy phản hồi duy nhất một từ: PONG_SYNC",
        system_prompt="Bạn là trợ lý kiểm thử hệ thống.",
        temperature=0.0,
    )
    assert len(res.strip()) > 0
    assert "PONG_SYNC" in res.upper()


@pytest.mark.asyncio
async def test_call_structured_async():
    """Kiểm thử trích xuất JSON tuân thủ Pydantic Schema bất đồng bộ."""
    prompt = (
        "Phân tích yêu cầu: Người dùng hỏi 'Chào bạn'. "
        "Hãy xuất JSON với intent='CHITCHAT', confidence=1.0, notes='Chào hỏi xã giao'."
    )
    result = await call_structured(
        prompt=prompt,
        schema=SampleDecisionSchema,
        temperature=0.0,
    )
    assert isinstance(result, SampleDecisionSchema)
    assert result.intent == "CHITCHAT"
    assert result.confidence >= 0.9


def test_call_structured_sync():
    """Kiểm thử trích xuất JSON tuân thủ Pydantic Schema đồng bộ."""
    prompt = (
        "Phân tích yêu cầu: Người dùng hỏi 'Xin chào buổi sáng'. "
        "Hãy xuất JSON với intent='GREETING', confidence=0.98, notes='Chào hỏi buổi sáng'."
    )
    result = call_structured_sync(
        prompt=prompt,
        schema=SampleDecisionSchema,
        temperature=0.0,
    )
    assert isinstance(result, SampleDecisionSchema)
    assert result.intent == "GREETING"
    assert result.confidence >= 0.9


@pytest.mark.asyncio
async def test_call_raw_sql_async():
    """Kiểm thử sinh SQL bằng mô hình gemini-3.7-flash (Hard task)."""
    schema_context = (
        "CREATE TABLE fact_economic_metric (\n"
        "    id SERIAL PRIMARY KEY,\n"
        "    metric_code VARCHAR(50),\n"
        "    year INT,\n"
        "    value NUMERIC\n"
        ");"
    )
    prompt = "Lấy tổng giá trị value theo từng năm từ bảng fact_economic_metric, sắp xếp theo năm giảm dần."
    sql = await call_raw_sql(
        prompt=prompt,
        schema_context=schema_context,
    )
    assert len(sql.strip()) > 0
    # SQL không được chứa markdown code block
    assert "```" not in sql
    assert "SELECT" in sql.upper()
    assert "FACT_ECONOMIC_METRIC" in sql.upper()


def test_call_raw_sql_sync():
    """Kiểm thử sinh SQL đồng bộ bằng mô hình gemini-3.7-flash (Hard task)."""
    prompt = "Đếm số lượng bản ghi trong bảng fact_economic_metric năm 2025."
    sql = call_raw_sql_sync(
        prompt=prompt,
    )
    assert len(sql.strip()) > 0
    assert "```" not in sql
    assert "SELECT" in sql.upper()


@pytest.mark.asyncio
async def test_call_stream():
    """Kiểm thử truyền phát phản hồi luồng token SSE."""
    collected = []
    async for chunk in call_stream(
        prompt="Đếm từ 1 đến 3: 1, 2, 3",
        temperature=0.0,
    ):
        collected.append(chunk)
    full_text = "".join(collected)
    assert len(full_text.strip()) > 0
    assert "1" in full_text


def test_call_structured_with_fallback_sync():
    """Kiểm thử call_structured_with_fallback đồng bộ với primary model."""
    prompt = "Phân tích: Người dùng chào 'Chào bạn'. Xuất JSON với intent='GREETING', confidence_score=0.95."
    
    class TestFallbackSchema(BaseModel):
        intent: str
        confidence_score: float = 0.95

    parsed, model_used, usage, latency_ms = call_structured_with_fallback(
        prompt=prompt,
        schema=TestFallbackSchema,
        min_confidence=0.7,
    )
    assert isinstance(parsed, TestFallbackSchema)
    assert parsed.intent == "GREETING"
    assert parsed.confidence_score >= 0.7
    assert latency_ms > 0
    assert len(model_used) > 0


def test_call_structured_with_fallback_triggered_by_validator():
    """Kiểm thử fallback sang model dự phòng (google/gemini-3.8-flash) khi invariant validator không đạt."""
    prompt = "Phân tích: Người dùng hỏi 'Tình hình kinh tế năm 2025'. Xuất JSON với intent='ANALYTICS', confidence_score=0.99."
    
    class TestFallbackSchema(BaseModel):
        intent: str
        confidence_score: float = 0.99

    # Ép validator trả về False ở lần 1 để kiểm tra trigger fallback
    call_count = 0
    def trigger_fallback_on_first(obj: TestFallbackSchema) -> bool:
        nonlocal call_count
        call_count += 1
        return call_count > 1  # Lần 1 trả về False để kích hoạt fallback

    parsed, model_used, usage, latency_ms = call_structured_with_fallback(
        prompt=prompt,
        schema=TestFallbackSchema,
        invariant_validator=trigger_fallback_on_first,
        min_confidence=0.7,
    )
    assert isinstance(parsed, TestFallbackSchema)
    assert parsed.intent == "ANALYTICS"
    assert call_count >= 1
    # Fallback model được kích hoạt
    assert model_used == getattr(settings, "OPENROUTER_HEAVY_MODEL", "google/gemini-3.8-flash")

