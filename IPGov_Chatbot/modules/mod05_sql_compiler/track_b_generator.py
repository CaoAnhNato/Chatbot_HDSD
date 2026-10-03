"""
Module: IPGov_Chatbot/modules/mod05_sql_compiler/track_b_generator.py
Chức năng: Động cơ sinh SQL phức tạp (Track B - 15% traffic) qua Gated 2-Stage Confidence Fallback.
Căn cứ:
- Blueprint: 05_MULTI_AGENT_WORKFLOW_DIN_MAC_SQL.md (Mục 3)
- Specification: IPGov_Chatbot/docs/MODULE_05_SQL_COMPILER_SPEC.md (Mục 5)
- Mô hình chính (Fast Gate): google/gemini-3.5-flash-lite (enable_thinking=False, thought_scratchpad CoT)
- Mô hình dự phòng (Heavy Fallback): deepseek/deepseek-v4.1-flash (reasoning=true, effort='medium')
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from IPGov_Chatbot.core.llm_gateway import (
    call_structured_with_fallback,
    call_structured_with_fallback_async,
)
from IPGov_Chatbot.modules.mod05_sql_compiler.ast_validator import (
    clean_sql_string,
    invariant_sql_validator,
)
from IPGov_Chatbot.modules.mod05_sql_compiler.prompt_templates import (
    STATIC_INVARIANT_PREFIX_PROMPT,
    build_3tier_text_to_sql_prompt,
)
from IPGov_Chatbot.schemas.catalog_dto import CatalogPrunedDTO
from IPGov_Chatbot.schemas.router_dto import RouterOutputDTO
from IPGov_Chatbot.schemas.sql_compiler_schema import (
    GeneratedSQLDTO,
    SQLExecutionMode,
    TextToSQLStructuredOutput,
)
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO

logger = logging.getLogger("ipgov.mod05.track_b_generator")


class TrackBGenerator:
    """
    Trình sinh SQL phức tạp Track B sử dụng kiến trúc Gated 2-Stage Fallback:
    Fast Gate (Gemini 3.5 Lite) -> Invariant Gate (RAM) -> Heavy Fallback (DeepSeek v4.1 Flash).
    """

    def __init__(
        self,
        primary_model: str = "google/gemini-3.5-flash-lite",
        fallback_model: str = "deepseek/deepseek-v4.1-flash",
    ) -> None:
        self.primary_model = primary_model
        self.fallback_model = fallback_model

    async def generate_sql_async(
        self,
        catalog_pruned: CatalogPrunedDTO,
        router_output: RouterOutputDTO,
        security_context: UserSecurityContextDTO,
        negative_constraints: Optional[str] = None,
        trace_id: str = "",
    ) -> GeneratedSQLDTO:
        """Sinh câu lệnh SQL bất đồng bộ qua Gated 2-Stage Fallback."""
        t0 = time.perf_counter()

        user_prompt = build_3tier_text_to_sql_prompt(
            catalog_pruned=catalog_pruned,
            router_output=router_output,
            security_context=security_context,
            negative_constraints=negative_constraints,
        )

        candidate_tables = list(
            set(catalog_pruned.selected_tables + catalog_pruned.bridge_tables)
        )
        if not candidate_tables:
            candidate_tables = [
                "dwh_internal.fact_report_criteria",
                "dwh_internal.criteria",
                "dwh_internal.deparment",
                "dwh_internal.office",
            ]

        def validator(res: TextToSQLStructuredOutput) -> bool:
            return invariant_sql_validator(res, candidate_tables)

        parsed_res, model_used, usage, gateway_latency_ms = (
            await call_structured_with_fallback_async(
                prompt=user_prompt,
                schema=TextToSQLStructuredOutput,
                system_prompt=STATIC_INVARIANT_PREFIX_PROMPT,
                primary_model=self.primary_model,
                fallback_model=self.fallback_model,
                min_confidence=0.70,
                confidence_attr="confidence_score",
                invariant_validator=validator,
                temperature=0.0,
            )
        )

        fallback_triggered = self.fallback_model in model_used
        total_latency_ms = (time.perf_counter() - t0) * 1000.0

        cleaned_sql = clean_sql_string(parsed_res.sql_query)
        cache_hit = usage.get("cached_tokens", 0) > 0 if isinstance(usage, dict) else False

        return GeneratedSQLDTO(
            raw_sql=cleaned_sql,
            execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
            dag_archetype=router_output.dag_archetype,
            tables_referenced=parsed_res.tables_used,
            parameters={"tenant_code": security_context.tenant_code},
            generator_track="TRACK_B_LLM",
            thought_scratchpad=parsed_res.thought_scratchpad,
            llm_provider=model_used,
            confidence_score=parsed_res.confidence_score,
            fallback_triggered=fallback_triggered,
            prompt_cache_hit=cache_hit,
            retry_count=0,
            ast_valid=True,
            latency_ms=total_latency_ms,
            trace_id=trace_id or router_output.session_id,
        )

    def generate_sql_sync(
        self,
        catalog_pruned: CatalogPrunedDTO,
        router_output: RouterOutputDTO,
        security_context: UserSecurityContextDTO,
        negative_constraints: Optional[str] = None,
        trace_id: str = "",
    ) -> GeneratedSQLDTO:
        """Sinh câu lệnh SQL đồng bộ qua Gated 2-Stage Fallback."""
        t0 = time.perf_counter()

        user_prompt = build_3tier_text_to_sql_prompt(
            catalog_pruned=catalog_pruned,
            router_output=router_output,
            security_context=security_context,
            negative_constraints=negative_constraints,
        )

        candidate_tables = list(
            set(catalog_pruned.selected_tables + catalog_pruned.bridge_tables)
        )
        if not candidate_tables:
            candidate_tables = [
                "dwh_internal.fact_report_criteria",
                "dwh_internal.criteria",
                "dwh_internal.deparment",
                "dwh_internal.office",
            ]

        def validator(res: TextToSQLStructuredOutput) -> bool:
            return invariant_sql_validator(res, candidate_tables)

        parsed_res, model_used, usage, gateway_latency_ms = (
            call_structured_with_fallback(
                prompt=user_prompt,
                schema=TextToSQLStructuredOutput,
                system_prompt=STATIC_INVARIANT_PREFIX_PROMPT,
                primary_model=self.primary_model,
                fallback_model=self.fallback_model,
                min_confidence=0.70,
                confidence_attr="confidence_score",
                invariant_validator=validator,
                temperature=0.0,
            )
        )

        fallback_triggered = self.fallback_model in model_used
        total_latency_ms = (time.perf_counter() - t0) * 1000.0

        cleaned_sql = clean_sql_string(parsed_res.sql_query)
        cache_hit = usage.get("cached_tokens", 0) > 0 if isinstance(usage, dict) else False

        return GeneratedSQLDTO(
            raw_sql=cleaned_sql,
            execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
            dag_archetype=router_output.dag_archetype,
            tables_referenced=parsed_res.tables_used,
            parameters={"tenant_code": security_context.tenant_code},
            generator_track="TRACK_B_LLM",
            thought_scratchpad=parsed_res.thought_scratchpad,
            llm_provider=model_used,
            confidence_score=parsed_res.confidence_score,
            fallback_triggered=fallback_triggered,
            prompt_cache_hit=cache_hit,
            retry_count=0,
            ast_valid=True,
            latency_ms=total_latency_ms,
            trace_id=trace_id or router_output.session_id,
        )
