"""
Module: IPGov_Chatbot/modules/mod04_catalog/schema_pruner.py
Chức năng: Điều phối rút tỉa và liên kết Schema (Lean 2-Stage Retrieval)
kết hợp DuckDB FTS, RapidFuzz, NetworkX Minimal Steiner Tree và Capability Discovery Engine.
Căn cứ: Blueprint 03_SEMANTIC_LAYER_MDL_VA_IN_MEMORY_CATALOG.md
"""

from __future__ import annotations
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Union

from IPGov_Chatbot.schemas.catalog_dto import CatalogPrunedDTO, JoinPathDTO
from IPGov_Chatbot.schemas.router_dto import RouterOutputDTO, RouteTypeEnum
from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog
from IPGov_Chatbot.modules.mod04_catalog.steiner_tree_builder import SteinerTreeBuilder
from IPGov_Chatbot.modules.mod04_catalog.capability_discovery_engine import CapabilityDiscoveryEngine


class SchemaPruner:
    """
    Bộ điều phối rút tỉa Schema và tầng ngữ nghĩa trung gian của Module 04.
    """

    def __init__(
        self,
        catalog: Optional[DuckDBSemanticCatalog] = None,
        steiner_builder: Optional[SteinerTreeBuilder] = None,
        discovery_engine: Optional[CapabilityDiscoveryEngine] = None,
    ) -> None:
        self.catalog = catalog or DuckDBSemanticCatalog()
        self.steiner_builder = steiner_builder or SteinerTreeBuilder()
        self.discovery_engine = discovery_engine or CapabilityDiscoveryEngine()

    def prune_schema(
        self,
        prompt: Union[str, RouterOutputDTO],
        user_ctx: Optional[Dict[str, Any]] = None,
        trace_id: str = "",
    ) -> CatalogPrunedDTO:
        """
        Thực hiện quy trình rút tỉa Schema và phân giải ngữ nghĩa:
        1. Hỗ trợ đầu vào đa hình: str hoặc RouterOutputDTO (Khắc phục FAIL-008).
        2. Nếu Router phân nhánh Fact (FAST_TRACK, DAG, SINGLE_SQL) -> Không nuốt nhầm vào Dimension (Khắc phục FAIL-006).
        3. Kiểm tra câu hỏi Capability Discovery (DISC_01 -> DISC_10) -> Trả lời siêu tốc < 50ms (Zero Fact SQL).
        4. Kiểm tra câu hỏi Danh mục Bảng Chiều (GOLDEN_021 -> GOLDEN_028) -> Rút DDL bảng chiều.
        5. Thực hiện Lean 2-Stage Retrieval (BM25/Fuzzy + Steiner Tree) cho câu hỏi phân tích Fact.
        """
        start_time = time.perf_counter()
        req_trace = trace_id or str(uuid.uuid4())
        ctx = user_ctx or {}

        router_dto: Optional[RouterOutputDTO] = None
        if isinstance(prompt, RouterOutputDTO):
            router_dto = prompt
            raw_text = prompt.query_sanitized or ""
            req_trace = prompt.session_id or req_trace
        else:
            raw_text = str(prompt) if prompt is not None else ""

        raw_text_clean = raw_text.strip()
        candidate_tables: List[str] = []

        is_fact_route = False
        if router_dto:
            is_fact_route = router_dto.route in [
                RouteTypeEnum.TEMPLATE_FAST_TRACK,
                RouteTypeEnum.DYNAMIC_PARALLEL_DAG,
                RouteTypeEnum.SINGLE_SQL,
            ]

        # -------------------------------------------------------------------
        # BƯỚC 1: Kiểm tra câu hỏi Khám phá Năng lực (chỉ khi không phải Fact route)
        # -------------------------------------------------------------------
        if not is_fact_route:
            cap_match = self.discovery_engine.match_capability_query(raw_text_clean)
            if cap_match:
                disc_id, response_text, chips = cap_match
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                return CatalogPrunedDTO(
                    selected_tables=["dwh_internal.pipeline_logs"],
                    bridge_tables=[],
                    join_paths=[],
                    schema_slice_ddl="-- Capability Discovery Query: Tra cứu trực tiếp từ In-Memory Metadata Catalog",
                    data_contracts=["Zero Fact SQL - Response directly from RAM Catalog"],
                    discovery_response=response_text,
                    suggested_action_chips=chips,
                    latency_ms=round(latency_ms, 2),
                    trace_id=req_trace,
                    confidence_score=1.0,
                )

        # -------------------------------------------------------------------
        # BƯỚC 2: Kiểm tra câu hỏi Tra cứu Danh mục Bảng Chiều
        # -------------------------------------------------------------------
        has_year = bool(re.search(r"\b(202[4-6])\b", raw_text_clean))
        has_fact_keywords = any(k in raw_text_clean.lower() for k in [
            "thống kê", "số liệu", "tổng số", "tỷ lệ", "kinh phí", "bao nhiêu", "đạt bao nhiêu"
        ])
        is_fact_query = is_fact_route or has_year or has_fact_keywords

        dim_intent = None
        if not is_fact_route:
            dim_intent = self.discovery_engine.detect_dimension_intent(raw_text_clean)

        if dim_intent:
            candidate_tables.append(dim_intent)

        # 3.1. Thử so khớp từ viết tắt/danh xưng qua RapidFuzz
        abbr_match = self.catalog.match_alias_or_abbreviation(raw_text_clean)
        if abbr_match:
            tgt_tbl = abbr_match.get("target_table")
            if tgt_tbl and tgt_tbl not in candidate_tables:
                candidate_tables.append(tgt_tbl)

        # 3.2. Quét từ khóa qua DuckDB BM25 search
        kw_tables = self.catalog.search_tables_by_keywords(raw_text_clean)
        for kt in kw_tables:
            t_name = kt["table_name"]
            if t_name not in candidate_tables:
                candidate_tables.append(t_name)

        # Nếu là câu hỏi Fact hoặc chưa có bảng nào được chọn, bổ sung 4 bảng Star-Schema cốt lõi
        if is_fact_query or not candidate_tables:
            core_fact_tables = [
                "dwh_internal.fact_report_criteria",
                "dwh_internal.criteria",
                "dwh_internal.deparment",
                "dwh_internal.office",
            ]
            for ct in core_fact_tables:
                if ct not in candidate_tables:
                    candidate_tables.append(ct)

        # -------------------------------------------------------------------
        # BƯỚC 4: Bù đắp bảng cầu nối bằng NetworkX Minimal Steiner Tree
        # -------------------------------------------------------------------
        all_nodes, bridge_tables, join_paths = self.steiner_builder.resolve_connected_subgraph(candidate_tables)

        # -------------------------------------------------------------------
        # BƯỚC 5: Sinh lát cắt DDL tối thiểu và tiêm Business Data Contracts
        # -------------------------------------------------------------------
        ddl_parts: List[str] = []
        for tbl_name in all_nodes:
            tbl_meta = self.catalog.get_table_metadata(tbl_name)
            if tbl_meta:
                col_defs = []
                for c in tbl_meta.columns:
                    col_defs.append(f"    {c.column_name} {c.data_type} -- {c.description}")
                cols_str = ",\n".join(col_defs)
                ddl_parts.append(f"CREATE TABLE {tbl_name} (\n{cols_str}\n);")
            else:
                ddl_parts.append(f"-- Schema DDL for {tbl_name}")

        schema_slice_ddl = "\n\n".join(ddl_parts)

        # Tiêm các khế ước dữ liệu bắt buộc (Data Contracts)
        data_contracts = [
            "NULLIF(TRIM(f.value), '')::numeric",
            "report_status = 'approved'",
            "WITH leaf_criteria AS (SELECT c.id, c.code, c.name FROM dwh_internal.criteria c WHERE NOT EXISTS (SELECT 1 FROM dwh_internal.criteria sub WHERE sub.parent_id = c.id))",
        ]

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        return CatalogPrunedDTO(
            selected_tables=all_nodes,
            bridge_tables=bridge_tables,
            join_paths=join_paths,
            schema_slice_ddl=schema_slice_ddl,
            data_contracts=data_contracts,
            discovery_response=None,
            suggested_action_chips=[],
            latency_ms=round(latency_ms, 2),
            trace_id=req_trace,
            confidence_score=0.95,
        )
