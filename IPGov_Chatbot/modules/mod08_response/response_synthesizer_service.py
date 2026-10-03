"""
Dịch vụ Điều phối Tổng hợp Câu trả lời và Thẻ Nguồn gốc Dữ liệu (Module 08 Facade).
Tích hợp JinjaSlotEngine (Zero-Cost RAM < 0.05ms) và LLMSynthesizer (Gemini-2.5-flash-lite).
Đạt chuẩn DoD Giai đoạn 4 IPGov Chatbot.
"""

import time
import logging
import re
from typing import Any, Optional
from IPGov_Chatbot.schemas.response_synthesizer_dto import (
    LineageBadgeDTO,
    RenderModeEnum,
    SynthesizerOutputDTO,
    TabularDataDTO,
    TableColumnDTO,
    ColumnAlignEnum,
    ColumnTypeEnum,
)
from IPGov_Chatbot.modules.mod08_response.jinja_slot_engine import JinjaSlotEngine
from IPGov_Chatbot.modules.mod08_response.llm_synthesizer import LLMSynthesizer
from IPGov_Chatbot.modules.mod08_response.lineage_badge_builder import LineageBadgeBuilder

logger = logging.getLogger("ipgov.mod08.response_synthesizer")


def _append_collapsible_sql(content: str, sql: Optional[str]) -> str:
    """Tự động gắn kèm khối SQL thu gọn vào cuối phản hồi phục vụ minh bạch hóa truy vấn."""
    if not sql or not sql.strip():
        return content
    clean_sql = sql.strip().rstrip(";") + ";"
    return content + f"\n\n<details>\n<summary>🔍 Xem câu lệnh truy vấn (SQL Query)</summary>\n\n```sql\n{clean_sql}\n```\n</details>"


def _build_tabular_dto(query_result: Any) -> Optional[TabularDataDTO]:
    """Trích xuất TabularDataDTO từ QueryResultDTO cho các kết quả có >= 2 dòng."""
    rows = getattr(query_result, "rows", [])
    if not rows or len(rows) < 2:
        return None
    sample = rows[0]
    cols = [k for k in sample.keys() if not k.endswith("_id")] or list(sample.keys())
    columns = []
    for c in cols:
        is_num = any(c.startswith(p) or c.endswith(p) for p in ["tong_", "gia_tri", "value", "so_luong", "kinh_phi"])
        is_badge = any(c.startswith(p) or c.endswith(p) for p in ["status", "trang_thai"])
        align = ColumnAlignEnum.RIGHT if is_num else (ColumnAlignEnum.CENTER if is_badge else ColumnAlignEnum.LEFT)
        col_type = ColumnTypeEnum.BADGE if is_badge else (ColumnTypeEnum.NUMBER if is_num else ColumnTypeEnum.TEXT)
        label = c.replace("_", " ").title()
        columns.append(TableColumnDTO(
            key=c,
            label=label,
            align=align,
            data_type=col_type
        ))
    return TabularDataDTO(
        columns=columns,
        rows=rows[:50],
        total_records=len(rows)
    )


class ResponseSynthesizerService:
    """
    Facade Service chính thức của Module 08.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.jinja_engine = JinjaSlotEngine()
        self.llm_synth = LLMSynthesizer(model_name=model_name)
        self.badge_builder = LineageBadgeBuilder()

    async def synthesize_async(
        self,
        query_result: Any,
        sanitized_dto: Optional[Any] = None,
        router_output: Optional[Any] = None,
        user_ctx: Optional[Any] = None,
        user_prompt: str = "",
        trace_id: str = "",
    ) -> SynthesizerOutputDTO:
        """
        Tổng hợp câu trả lời bất đồng bộ (sử dụng trong luồng SSE streaming của Gateway).
        """
        t0 = time.perf_counter()

        # 1. Trích xuất thông tin cơ sở
        entities = getattr(router_output, "extracted_entities", {}) or {}
        prompt_text = user_prompt or getattr(router_output, "raw_prompt", "") or "Tra cứu số liệu DWH"

        # 2. Xử lý trường hợp lỗi từ CSDL (Module 07 ERROR)
        status_val = str(getattr(query_result, "status", "")).lower()
        if "error" in status_val or "timeout" in status_val:
            err_msg = getattr(query_result, "error_message", "Không thể hoàn tất truy vấn CSDL.")
            content = f"⚠️ Yêu cầu tra cứu không thể hoàn tất do lỗi cơ sở dữ liệu: {err_msg}"
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return SynthesizerOutputDTO(
                content=content,
                render_mode=RenderModeEnum.ERROR_NOTIFICATION,
                lineage_badge=None,
                table_rendered=False,
                latency_ms=round(latency_ms, 2),
                tokens_used=0,
                trace_id=trace_id,
            )

        # 3. Xử lý trường hợp tập kết quả rỗng (Dual-Gate Safe Handler)
        row_count = getattr(query_result, "row_count", 0)
        is_empty = getattr(query_result, "is_empty", False) or row_count == 0
        if is_empty:
            # Nhận thức ngữ cảnh thời gian (Temporal Awareness)
            query_year = None
            if router_output and hasattr(router_output, "slots") and router_output.slots:
                query_year = router_output.slots.get("year") or router_output.slots.get("time_range")
            if not query_year and user_prompt:
                year_match = re.search(r"\b(202[0-9])\b", user_prompt)
                if year_match:
                    query_year = year_match.group(1)

            context_vars = {
                "query_year": query_year,
                "suggested_year": "2026" if str(query_year) != "2026" else None,
            }
            content = self.jinja_engine.render("EMPTY_RESULT", context_vars)
            badge = self.badge_builder.build_badge(
                query_result=query_result,
                sanitized_dto=sanitized_dto,
                router_output=router_output,
                user_ctx=user_ctx,
            )
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return SynthesizerOutputDTO(
                content=content,
                render_mode=RenderModeEnum.EMPTY_NOTIFICATION,
                lineage_badge=badge,
                table_rendered=False,
                latency_ms=round(latency_ms, 2),
                tokens_used=0,
                trace_id=trace_id,
            )

        # 4. Thử nghiệm Dynamic Jinja Template (Fast Path: RAM < 0.05ms, 0 LLM token)
        jinja_res = self.jinja_engine.try_render_dwh_result(
            query_result=query_result,
            router_output=router_output,
            sanitized_dto=sanitized_dto,
        )

        executed_sql = (
            getattr(sanitized_dto, "final_sql", None)
            or getattr(sanitized_dto, "sanitized_sql", None)
            or getattr(query_result, "sql", None)
            or getattr(query_result, "executed_sql", None)
        )

        if jinja_res is not None:
            content, table_rendered, tpl_name = jinja_res
            content = _append_collapsible_sql(content, executed_sql)
            badge = self.badge_builder.build_badge(
                query_result=query_result,
                sanitized_dto=sanitized_dto,
                router_output=router_output,
                user_ctx=user_ctx,
            )
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return SynthesizerOutputDTO(
                content=content,
                render_mode=RenderModeEnum.DETERMINISTIC_TEMPLATE,
                lineage_badge=badge,
                table_rendered=table_rendered,
                tabular_data=_build_tabular_dto(query_result) if table_rendered else None,
                latency_ms=round(latency_ms, 2),
                tokens_used=0,
                trace_id=trace_id,
            )

        # 5. Nếu không khớp Jinja Template: Chuyển tiếp LLM Synthesizer (Gemini-2.5-flash-lite)
        content, table_rendered, tokens_used = await self.llm_synth.synthesize_async(
            query_result=query_result,
            user_prompt=prompt_text,
            extracted_entities=entities,
            trace_id=trace_id,
        )
        content = _append_collapsible_sql(content, executed_sql)

        badge = self.badge_builder.build_badge(
            query_result=query_result,
            sanitized_dto=sanitized_dto,
            router_output=router_output,
            user_ctx=user_ctx,
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0

        return SynthesizerOutputDTO(
            content=content,
            render_mode=RenderModeEnum.LLM_SYNTHESIS,
            lineage_badge=badge,
            table_rendered=table_rendered,
            tabular_data=_build_tabular_dto(query_result) if table_rendered else None,
            latency_ms=round(latency_ms, 2),
            tokens_used=tokens_used,
            trace_id=trace_id,
        )

    def synthesize_sync(
        self,
        query_result: Any,
        sanitized_dto: Optional[Any] = None,
        router_output: Optional[Any] = None,
        user_ctx: Optional[Any] = None,
        user_prompt: str = "",
        trace_id: str = "",
    ) -> SynthesizerOutputDTO:
        """
        Tổng hợp câu trả lời đồng bộ (phục vụ Benchmark và Batch Test Runner).
        """
        t0 = time.perf_counter()

        entities = getattr(router_output, "extracted_entities", {}) or {}
        prompt_text = user_prompt or getattr(router_output, "raw_prompt", "") or "Tra cứu số liệu DWH"

        # Lỗi CSDL
        status_val = str(getattr(query_result, "status", "")).lower()
        if "error" in status_val or "timeout" in status_val:
            err_msg = getattr(query_result, "error_message", "Không thể hoàn tất truy vấn CSDL.")
            content = f"⚠️ Yêu cầu tra cứu không thể hoàn tất do lỗi cơ sở dữ liệu: {err_msg}"
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return SynthesizerOutputDTO(
                content=content,
                render_mode=RenderModeEnum.ERROR_NOTIFICATION,
                lineage_badge=None,
                table_rendered=False,
                latency_ms=round(latency_ms, 2),
                tokens_used=0,
                trace_id=trace_id,
            )

        # Rỗng
        row_count = getattr(query_result, "row_count", 0)
        is_empty = getattr(query_result, "is_empty", False) or row_count == 0
        if is_empty:
            # Nhận thức ngữ cảnh thời gian (Temporal Awareness)
            query_year = None
            if router_output and hasattr(router_output, "slots") and router_output.slots:
                query_year = router_output.slots.get("year") or router_output.slots.get("time_range")
            if not query_year and user_prompt:
                year_match = re.search(r"\b(202[0-9])\b", user_prompt)
                if year_match:
                    query_year = year_match.group(1)

            context_vars = {
                "query_year": query_year,
                "suggested_year": "2026" if str(query_year) != "2026" else None,
            }
            content = self.jinja_engine.render("EMPTY_RESULT", context_vars)
            badge = self.badge_builder.build_badge(
                query_result=query_result,
                sanitized_dto=sanitized_dto,
                router_output=router_output,
                user_ctx=user_ctx,
            )
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return SynthesizerOutputDTO(
                content=content,
                render_mode=RenderModeEnum.EMPTY_NOTIFICATION,
                lineage_badge=badge,
                table_rendered=False,
                latency_ms=round(latency_ms, 2),
                tokens_used=0,
                trace_id=trace_id,
            )

        executed_sql = (
            getattr(sanitized_dto, "final_sql", None)
            or getattr(sanitized_dto, "sanitized_sql", None)
            or getattr(query_result, "sql", None)
            or getattr(query_result, "executed_sql", None)
        )

        # Jinja Fast Path
        jinja_res = self.jinja_engine.try_render_dwh_result(
            query_result=query_result,
            router_output=router_output,
            sanitized_dto=sanitized_dto,
        )

        if jinja_res is not None:
            content, table_rendered, tpl_name = jinja_res
            content = _append_collapsible_sql(content, executed_sql)
            badge = self.badge_builder.build_badge(
                query_result=query_result,
                sanitized_dto=sanitized_dto,
                router_output=router_output,
                user_ctx=user_ctx,
            )
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return SynthesizerOutputDTO(
                content=content,
                render_mode=RenderModeEnum.DETERMINISTIC_TEMPLATE,
                lineage_badge=badge,
                table_rendered=table_rendered,
                tabular_data=_build_tabular_dto(query_result) if table_rendered else None,
                latency_ms=round(latency_ms, 2),
                tokens_used=0,
                trace_id=trace_id,
            )

        # LLM Synthesis
        content, table_rendered, tokens_used = self.llm_synth.synthesize_sync(
            query_result=query_result,
            user_prompt=prompt_text,
            extracted_entities=entities,
            trace_id=trace_id,
        )
        content = _append_collapsible_sql(content, executed_sql)

        badge = self.badge_builder.build_badge(
            query_result=query_result,
            sanitized_dto=sanitized_dto,
            router_output=router_output,
            user_ctx=user_ctx,
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0

        return SynthesizerOutputDTO(
            content=content,
            render_mode=RenderModeEnum.LLM_SYNTHESIS,
            lineage_badge=badge,
            table_rendered=table_rendered,
            tabular_data=_build_tabular_dto(query_result) if table_rendered else None,
            latency_ms=round(latency_ms, 2),
            tokens_used=tokens_used,
            trace_id=trace_id,
        )
