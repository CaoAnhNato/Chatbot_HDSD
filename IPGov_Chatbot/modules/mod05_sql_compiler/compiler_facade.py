"""
Module: IPGov_Chatbot/modules/mod05_sql_compiler/compiler_facade.py
Chức năng: Facade trung tâm điều phối toàn bộ Module 05 (Stage 5 SQL Generation).
Kết nối: Track A (85%), Track B (15%), Invariant Gate, Redis Error Cache, DB Dry-Run & Self-Correction.
Căn cứ:
- Blueprint: 05_MULTI_AGENT_WORKFLOW_DIN_MAC_SQL.md
- Specification: IPGov_Chatbot/docs/MODULE_05_SQL_COMPILER_SPEC.md
- Tuân thủ TRAPS: [TRAP-004], [TRAP-005], [TRAP-007], [TRAP-015]
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from IPGov_Chatbot.modules.mod05_sql_compiler.ast_validator import validate_ast_syntax
from IPGov_Chatbot.modules.mod05_sql_compiler.db_dry_run import DatabaseDryRunner
from IPGov_Chatbot.modules.mod05_sql_compiler.error_cache_service import (
    RedisSQLErrorCache,
    map_postgres_error_to_constraint,
)
from IPGov_Chatbot.modules.mod05_sql_compiler.scatter_gather_dispatcher import (
    ScatterGatherDispatcher,
)
from IPGov_Chatbot.modules.mod05_sql_compiler.track_a_compiler import TrackACompiler
from IPGov_Chatbot.modules.mod05_sql_compiler.track_b_generator import TrackBGenerator
from IPGov_Chatbot.schemas.catalog_dto import CatalogPrunedDTO
from IPGov_Chatbot.schemas.router_dto import IntentEnum, RouteTypeEnum, RouterOutputDTO
from IPGov_Chatbot.schemas.sql_compiler_schema import (
    GeneratedSQLDTO,
    MetricSpecDTO,
    SQLExecutionMode,
)
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO

logger = logging.getLogger("ipgov.mod05.facade")


class SQLCompilerFacade:
    """
    Facade duy nhất cung cấp giao diện lập trình cho Module 05.
    Tự động phân tầng: Track A (In-memory AST) -> Invariant Gate -> Track B (LLM) -> Dry-Run -> Self-Correction.
    """

    def __init__(
        self,
        catalog: Optional[Any] = None,
        primary_model: str = "google/gemini-3.5-flash-lite",
        fallback_model: str = "google/gemini-3.8-flash",
        enable_live_db_dry_run: bool = True,
    ) -> None:
        if catalog is None:
            try:
                from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import (
                    DuckDBSemanticCatalog,
                )
                self.catalog = DuckDBSemanticCatalog()
            except Exception as e:
                logger.warning(f"Không thể khởi tạo DuckDBSemanticCatalog: {e}")
                self.catalog = None
        else:
            self.catalog = catalog

        self.track_a = TrackACompiler(catalog=self.catalog)
        self.track_b = TrackBGenerator(primary_model=primary_model, fallback_model=fallback_model)
        self.dry_runner = DatabaseDryRunner()
        self.error_cache = RedisSQLErrorCache()
        self.scatter_gather = ScatterGatherDispatcher()
        self.enable_live_db_dry_run = enable_live_db_dry_run

    def _is_bypass_route(self, router_output: RouterOutputDTO) -> bool:
        """Kiểm tra xem câu hỏi có thuộc nhóm bypass zero-SQL không."""
        sql_routes = (
            RouteTypeEnum.TEMPLATE_FAST_TRACK,
            RouteTypeEnum.DYNAMIC_PARALLEL_DAG,
            RouteTypeEnum.SINGLE_SQL,
            "TEMPLATE_FAST_TRACK",
            "DYNAMIC_PARALLEL_DAG",
            "SINGLE_SQL",
        )
        if router_output.route in sql_routes:
            return False

        bypass_routes = (
            RouteTypeEnum.CHITCHAT_BYPASS,
            RouteTypeEnum.CATALOG_DISCOVERY,
            RouteTypeEnum.SECURITY_DENIAL,
            RouteTypeEnum.CLARIFICATION,
            "CHITCHAT_BYPASS",
            "CATALOG_DISCOVERY",
            "SECURITY_DENIAL",
            "CLARIFICATION",
        )
        if router_output.route in bypass_routes:
            return True
        if getattr(router_output, "zero_sql", False):
            return True
        return False

    def compile_sql_sync(
        self,
        catalog_pruned: CatalogPrunedDTO,
        router_output: RouterOutputDTO,
        security_context: UserSecurityContextDTO,
        trace_id: str = "",
    ) -> GeneratedSQLDTO:
        """Biên dịch câu lệnh SQL đồng bộ (Sync) qua Adaptive Cascading Engine."""
        t0 = time.perf_counter()
        t_id = trace_id or router_output.session_id or f"trace_{int(time.time())}"

        # ----------------------------------------------------------------------
        # BƯỚC 1: Xử lý Bypass Zero-SQL (Chitchat, Discovery, Security Denial)
        # ----------------------------------------------------------------------
        if self._is_bypass_route(router_output):
            latency = (time.perf_counter() - t0) * 1000.0
            return GeneratedSQLDTO(
                raw_sql="",
                execution_mode=SQLExecutionMode.BYPASS_ZERO_SQL,
                dag_archetype="BYPASS",
                tables_referenced=[],
                generator_track="TRACK_A_COMPILER",
                thought_scratchpad="Bypass câu hỏi không yêu cầu sinh SQL Fact.",
                llm_provider=None,
                confidence_score=router_output.confidence_score,
                fallback_triggered=False,
                prompt_cache_hit=False,
                retry_count=0,
                ast_valid=True,
                latency_ms=latency,
                trace_id=t_id,
            )

        # ----------------------------------------------------------------------
        # BƯỚC 2: Thử nghiệm Track A Deterministic Semantic AST Compiler (85%)
        # ----------------------------------------------------------------------
        can_compile_a, dto_a = self.track_a.compile_from_router(
            router_output=router_output,
            user_ctx=security_context,
            trace_id=t_id,
        )

        if can_compile_a and dto_a:
            # Kiểm định Invariant Gate trong RAM
            valid_ast, err_ast, _ = validate_ast_syntax(dto_a.raw_sql)
            if valid_ast:
                # Nếu bật kiểm định Live DB Dry-run
                if self.enable_live_db_dry_run:
                    is_valid, pg_code, err_msg, _ = self.dry_runner.dry_run_explain_sync(
                        dto_a.raw_sql, dto_a.parameters
                    )
                    if is_valid:
                        dto_a.latency_ms = (time.perf_counter() - t0) * 1000.0
                        return dto_a
                    else:
                        logger.info(f"Track A Dry-Run không đạt [PG {pg_code}]. Kích hoạt Fallthrough sang Track B.")
                else:
                    dto_a.latency_ms = (time.perf_counter() - t0) * 1000.0
                    return dto_a

        # ----------------------------------------------------------------------
        # BƯỚC 3: Track B Gated 2-Stage Generator & Vòng lặp Self-Correction
        # ----------------------------------------------------------------------
        prompt = router_output.query_sanitized or ""
        candidate_tables = list(set(catalog_pruned.selected_tables + catalog_pruned.bridge_tables))

        # Tra cứu vết lỗi trước đó trong Redis Error Cache
        err_trace = self.error_cache.get_error_trace(prompt, candidate_tables)
        negative_constraints = err_trace.get("negative_constraint") if err_trace else None

        current_dto: Optional[GeneratedSQLDTO] = None
        max_retries = 2
        retry_count = 0

        while retry_count <= max_retries:
            try:
                current_dto = self.track_b.generate_sql_sync(
                    catalog_pruned=catalog_pruned,
                    router_output=router_output,
                    security_context=security_context,
                    negative_constraints=negative_constraints,
                    trace_id=t_id,
                )
            except Exception as e:
                logger.warning(f"Track B LLM Exception: {e}")
                break

            current_dto.retry_count = retry_count

            # Dry-run kiểm tra cú pháp và kế hoạch thực thi trên PostgreSQL thật
            if self.enable_live_db_dry_run and current_dto.raw_sql:
                is_valid, pg_code, err_msg, _ = self.dry_runner.dry_run_explain_sync(
                    current_dto.raw_sql, current_dto.parameters
                )
                if is_valid:
                    current_dto.ast_valid = True
                    current_dto.latency_ms = (time.perf_counter() - t0) * 1000.0
                    return current_dto
                else:
                    # Ghi nhận lỗi và ánh xạ thành Ràng buộc Phủ định
                    negative_constraints = self.error_cache.record_error(
                        prompt=prompt,
                        failed_sql=current_dto.raw_sql,
                        error_layer="POSTGRES_RUNTIME_ERROR",
                        pg_code=pg_code or "UNKNOWN",
                        error_message=err_msg or "Cú pháp không hợp lệ",
                        candidate_tables=candidate_tables,
                    )
                    logger.warning(
                        f"Track B Dry-Run thất bại lần {retry_count + 1} [PG {pg_code}]: {err_msg}. "
                        f"Tiêm Negative Constraint: {negative_constraints}"
                    )
                    retry_count += 1
            else:
                # Không kiểm tra live DB hoặc SQL rỗng
                current_dto.latency_ms = (time.perf_counter() - t0) * 1000.0
                return current_dto

        # Nếu vượt quá số lần retry: chuyển sang trạng thái Fallback Graceful
        logger.error(f"Module 05: Kiệt sức {max_retries} lần Self-Correction cho câu hỏi: {prompt}")
        if current_dto:
            current_dto.ast_valid = False
            current_dto.confidence_score = 0.40
            current_dto.latency_ms = (time.perf_counter() - t0) * 1000.0
            return current_dto

        # Trường hợp hy hữu không sinh được DTO
        return GeneratedSQLDTO(
            raw_sql="SELECT 1 WHERE 1=0;",
            execution_mode=SQLExecutionMode.BYPASS_ZERO_SQL,
            generator_track="TRACK_B_LLM",
            confidence_score=0.0,
            ast_valid=False,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            trace_id=t_id,
        )

    async def compile_sql_async(
        self,
        catalog_pruned: CatalogPrunedDTO,
        router_output: RouterOutputDTO,
        security_context: UserSecurityContextDTO,
        trace_id: str = "",
    ) -> GeneratedSQLDTO:
        """Biên dịch câu lệnh SQL bất đồng bộ (Async) qua Adaptive Cascading Engine."""
        t0 = time.perf_counter()
        t_id = trace_id or router_output.session_id or f"trace_{int(time.time())}"

        # Bước 1: Bypass Zero-SQL
        if self._is_bypass_route(router_output):
            latency = (time.perf_counter() - t0) * 1000.0
            return GeneratedSQLDTO(
                raw_sql="",
                execution_mode=SQLExecutionMode.BYPASS_ZERO_SQL,
                dag_archetype="BYPASS",
                tables_referenced=[],
                generator_track="TRACK_A_COMPILER",
                thought_scratchpad="Bypass câu hỏi không yêu cầu sinh SQL Fact.",
                llm_provider=None,
                confidence_score=router_output.confidence_score,
                fallback_triggered=False,
                prompt_cache_hit=False,
                retry_count=0,
                ast_valid=True,
                latency_ms=latency,
                trace_id=t_id,
            )

        # Bước 2: Track A Compiler
        can_compile_a, dto_a = self.track_a.compile_from_router(
            router_output=router_output,
            user_ctx=security_context,
            trace_id=t_id,
        )

        if can_compile_a and dto_a:
            valid_ast, err_ast, _ = validate_ast_syntax(dto_a.raw_sql)
            if valid_ast:
                if self.enable_live_db_dry_run:
                    is_valid, pg_code, err_msg, _ = await self.dry_runner.dry_run_explain_async(
                        dto_a.raw_sql, dto_a.parameters
                    )
                    if is_valid:
                        dto_a.latency_ms = (time.perf_counter() - t0) * 1000.0
                        return dto_a
                else:
                    dto_a.latency_ms = (time.perf_counter() - t0) * 1000.0
                    return dto_a

        # Bước 3: Track B Generator
        prompt = router_output.query_sanitized or ""
        candidate_tables = list(set(catalog_pruned.selected_tables + catalog_pruned.bridge_tables))

        err_trace = self.error_cache.get_error_trace(prompt, candidate_tables)
        negative_constraints = err_trace.get("negative_constraint") if err_trace else None

        current_dto: Optional[GeneratedSQLDTO] = None
        max_retries = 2
        retry_count = 0

        while retry_count <= max_retries:
            try:
                current_dto = await self.track_b.generate_sql_async(
                    catalog_pruned=catalog_pruned,
                    router_output=router_output,
                    security_context=security_context,
                    negative_constraints=negative_constraints,
                    trace_id=t_id,
                )
            except Exception as e:
                logger.warning(f"Track B Async LLM Exception: {e}")
                break

            current_dto.retry_count = retry_count

            if self.enable_live_db_dry_run and current_dto.raw_sql:
                is_valid, pg_code, err_msg, _ = await self.dry_runner.dry_run_explain_async(
                    current_dto.raw_sql, current_dto.parameters
                )
                if is_valid:
                    current_dto.ast_valid = True
                    current_dto.latency_ms = (time.perf_counter() - t0) * 1000.0
                    return current_dto
                else:
                    negative_constraints = self.error_cache.record_error(
                        prompt=prompt,
                        failed_sql=current_dto.raw_sql,
                        error_layer="POSTGRES_RUNTIME_ERROR",
                        pg_code=pg_code or "UNKNOWN",
                        error_message=err_msg or "Cú pháp không hợp lệ",
                        candidate_tables=candidate_tables,
                    )
                    retry_count += 1
            else:
                current_dto.latency_ms = (time.perf_counter() - t0) * 1000.0
                return current_dto

        if current_dto:
            current_dto.ast_valid = False
            current_dto.confidence_score = 0.40
            current_dto.latency_ms = (time.perf_counter() - t0) * 1000.0
            return current_dto

        return GeneratedSQLDTO(
            raw_sql="SELECT 1 WHERE 1=0;",
            execution_mode=SQLExecutionMode.BYPASS_ZERO_SQL,
            generator_track="TRACK_B_LLM",
            confidence_score=0.0,
            ast_valid=False,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            trace_id=t_id,
        )
