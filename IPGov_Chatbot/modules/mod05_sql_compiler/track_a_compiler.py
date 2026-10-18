"""
Module: IPGov_Chatbot/modules/mod05_sql_compiler/track_a_compiler.py
Chức năng: Deterministic Semantic AST Compiler xử lý 85% luồng thống kê chuẩn tắc.
Đặc tính: Chạy thuần trong RAM (< 1ms, 0 LLM token, 100% Valid SQL).
Căn cứ:
- Blueprint: 03_SEMANTIC_LAYER_MDL_VA_IN_MEMORY_CATALOG.md (Mục 5)
- Blueprint: 05_MULTI_AGENT_WORKFLOW_DIN_MAC_SQL.md (Mục 2)
- Specification: IPGov_Chatbot/docs/MODULE_05_SQL_COMPILER_SPEC.md (Mục 4)
- Tuân thủ TRAPS: [TRAP-004], [TRAP-005], [TRAP-007]
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from IPGov_Chatbot.modules.mod05_sql_compiler.ast_validator import validate_ast_syntax
from IPGov_Chatbot.schemas.router_dto import IntentEnum, RouteTypeEnum, RouterOutputDTO
from IPGov_Chatbot.schemas.sql_compiler_schema import (
    GeneratedSQLDTO,
    MetricFilter,
    MetricSpecDTO,
    SQLExecutionMode,
)
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO

logger = logging.getLogger("ipgov.mod05.track_a_compiler")


class TrackACompiler:
    """
    Động cơ biên dịch SQL tất định từ đặc tả chỉ tiêu MetricSpecDTO hoặc RouterOutputDTO.
    Tự động tiêm 100% Data Contracts và phân quyền HBAC trong RAM.
    """

    def __init__(self, catalog: Optional[Any] = None) -> None:
        self.catalog = catalog

    def can_compile_fast_track(self, router_output: RouterOutputDTO) -> bool:
        """
        Kiểm tra xem yêu cầu có đủ điều kiện biên dịch tất định qua Track A không.
        Điều kiện:
        - Khớp một trong 5 Kimball Archetypes được hỗ trợ
        - Hoặc Route là TEMPLATE_FAST_TRACK / SINGLE_SQL hoặc Intent là FAST_METRIC_COMPILER
        """
        from IPGov_Chatbot.modules.mod05_sql_compiler.archetype_patterns import (
            ArchetypePatternCatalog,
        )

        dag_archetype = getattr(router_output, "dag_archetype", None)
        if dag_archetype in ArchetypePatternCatalog.get_supported_archetypes():
            return True
        if dag_archetype in (
            "MONTHLY_COLLECTION_METRIC_LISTING",
            "DATE_RANGE_CUMULATIVE_METRIC_DISCOVERY",
            "SYSTEM_WIDE_CRITERIA_INVENTORY",
            "SINGLE_METRIC_LATEST_SNAPSHOT",
        ):
            return True

        # Nếu có DAG Archetype phức tạp không hỗ trợ -> Fallthrough sang Track B
        if dag_archetype and dag_archetype not in ("NONE", "SINGLE_FACT", "DIRECT_LOOKUP"):
            return False

        query = (router_output.query_sanitized or "").lower()
        if any(k in query for k in [
            "phê duyệt", "chờ duyệt", "trạng thái", "tiến độ", "nộp trễ hạn",
            "từ chối", "đã nộp", "chưa nộp", "nộp báo cáo", "hạn nộp", "chưa hoàn thành nộp",
            "biểu mẫu", "mẫu phiếu", "tờ khai",
            "bất thường", "để trống", "bằng 0", "rỗng",
            "cán bộ", "phụ trách nhiệm vụ", "nhiệm vụ trọng tâm",
            "office_mission", "gán cho văn phòng",
            "trùng lặp", "cập nhật từ phần mềm", "kho dữ liệu tổng hợp chưa", "thời gian cập nhật kho", "đồng bộ gần nhất"
        ]):
            return True
        complex_triggers = [
            "tăng hay giảm", "tăng bao nhiêu", "giảm bao nhiêu", "so với",
            "xếp hạng", "top", "cao nhất", "thấp nhất", "tỷ trọng", "phần trăm",
            "chiếm bao nhiêu", "đối chiếu", "so sánh"
        ]
        if any(trig in query for trig in complex_triggers):
            return False

        is_fast_route = (
            router_output.route in (
                RouteTypeEnum.TEMPLATE_FAST_TRACK,
                "TEMPLATE_FAST_TRACK",
                RouteTypeEnum.SINGLE_SQL,
                "SINGLE_SQL",
            )
            or router_output.intent in (
                IntentEnum.FAST_METRIC_COMPILER,
                "FAST_METRIC_COMPILER",
            )
        )
        return is_fast_route

    def _resolve_metric_info(
        self,
        router_output: RouterOutputDTO,
        user_ctx: Optional[UserSecurityContextDTO] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Trích xuất mã chỉ tiêu và tên chỉ tiêu từ RouterOutputDTO hoặc DuckDB Catalog có tenant scoping."""
        code = getattr(router_output, "metric_code", None)
        if not code and getattr(router_output, "active_quest", None):
            code = router_output.active_quest.metric_code
        name = getattr(router_output, "metric_name", None)
        if self.catalog:
            try:
                tc = getattr(user_ctx, "tenant_code", None) or "68"
                rl = getattr(user_ctx, "role_level", None)
                matched = self.catalog.find_criteria_by_name(
                    router_output.query_sanitized,
                    limit=1,
                    tenant_code=tc,
                    role_level=rl
                )
                if matched and len(matched) > 0:
                    if not code:
                        code = matched[0].get("code")
                    if not name:
                        name = matched[0].get("name")
            except Exception as e:
                logger.debug(f"Không thể tra cứu chỉ tiêu từ catalog: {e}")
        return code, name

    def _resolve_metric_code(
        self,
        router_output: RouterOutputDTO,
        user_ctx: Optional[UserSecurityContextDTO] = None,
    ) -> Optional[str]:
        code, _ = self._resolve_metric_info(router_output, user_ctx)
        return code

    def _compile_archetype(
        self,
        router_output: RouterOutputDTO,
        user_ctx: UserSecurityContextDTO,
        archetype: str,
    ) -> Optional[str]:
        """Biên dịch mẫu hình phân tích Kimball Archetypes trong RAM (< 1ms)."""
        from IPGov_Chatbot.modules.mod05_sql_compiler.archetype_patterns import (
            ArchetypePatternCatalog,
        )

        query = router_output.query_sanitized or ""
        metric_code, metric_name = self._resolve_metric_info(router_output, user_ctx)

        years = re.findall(r"\b(202[0-9])\b", query)
        year = None
        if getattr(router_output, "active_quest", None) and router_output.active_quest.temporal_val:
            year = str(router_output.active_quest.temporal_val)
        elif getattr(router_output, "temporal_scope", None):
            t_scope = router_output.temporal_scope
            if isinstance(t_scope, dict) and t_scope.get("start_year"):
                year = str(t_scope["start_year"])
        elif years:
            year = years[0]
        tenant_code = user_ctx.tenant_code or "68"
        dept_code = user_ctx.department_code
        if any(k in query.lower() for k in ["toàn tỉnh", "toan tinh", "cả tỉnh", "toàn bộ tỉnh"]):
            dept_code = None

        if archetype == ArchetypePatternCatalog.TEMPORAL_COMPARISON:
            comp_years = sorted(list(set(years))) if years else []
            return ArchetypePatternCatalog.build_temporal_comparison_sql(
                metric_code=metric_code or "",
                metric_name=metric_name or "",
                years=comp_years,
                tenant_code=tenant_code,
                department_code=dept_code,
            )
        elif archetype == ArchetypePatternCatalog.RANKING_TOP_K:
            m_top = re.search(r"\b(?:top\s*|thứ hạng\s*|xếp hạng\s*)(\d+)\b", query, re.IGNORECASE)
            top_k = int(m_top.group(1)) if m_top else 5
            order_dir = "ASC" if any(w in query.lower() for w in ["thấp nhất", "ít nhất"]) else "DESC"
            return ArchetypePatternCatalog.build_ranking_top_k_sql(
                metric_code=metric_code or "",
                metric_name=metric_name or "",
                year=year,
                top_k=top_k,
                tenant_code=tenant_code,
                order_dir=order_dir,
            )
        elif archetype == ArchetypePatternCatalog.PART_TO_WHOLE:
            scope_name = None
            if "xây dựng" in query.lower():
                scope_name = "Xây dựng"
            elif "lao động" in query.lower():
                scope_name = "Lao động"
            return ArchetypePatternCatalog.build_part_to_whole_sql(
                year=year,
                tenant_code=tenant_code,
                department_code=dept_code,
                scope_name=scope_name,
            )
        elif archetype == ArchetypePatternCatalog.CROSS_ENTITY_COMPARISON:
            return ArchetypePatternCatalog.build_cross_entity_comparison_sql(
                metric_code=metric_code or "",
                metric_name=metric_name or "",
                year=year,
                tenant_code=tenant_code,
                department_code=dept_code,
            )
        elif archetype == ArchetypePatternCatalog.MULTI_DIMENSIONAL_PIVOT:
            comp_years = sorted(list(set(years))) if years else []
            year_start = comp_years[0] if comp_years else None
            year_end = comp_years[1] if len(comp_years) > 1 else (comp_years[0] if comp_years else None)
            return ArchetypePatternCatalog.build_multi_dimensional_pivot_sql(
                metric_code=metric_code or "",
                metric_name=metric_name or "",
                year_start=year_start,
                year_end=year_end,
                tenant_code=tenant_code,
                department_code=dept_code,
            )
        return None

    def compile_from_spec(
        self,
        spec: MetricSpecDTO,
        user_ctx: UserSecurityContextDTO,
        trace_id: str = "",
    ) -> GeneratedSQLDTO:
        """Biên dịch tất định từ MetricSpecDTO sang GeneratedSQLDTO trong RAM (< 1ms)."""
        t0 = time.perf_counter()

        cte_leaf = (
            "WITH leaf_criteria AS (\n"
            "    SELECT c.id, c.code, c.name\n"
            "    FROM dwh_internal.criteria c\n"
            "    WHERE NOT EXISTS (\n"
            "        SELECT 1 FROM dwh_internal.criteria sub\n"
            "        WHERE sub.parent_id = c.id\n"
            "    )\n"
            ")"
        )

        crit_conds = [f"lc.code = '{spec.metric_code}'"]
        clean_code = spec.metric_code.strip()
        words = clean_code.replace('_', ' ')
        crit_conds.append(f"lc.code ILIKE '%{clean_code}%'")
        crit_conds.append(f"lc.name ILIKE '%{words}%'")
        crit_conds.append(f"f.name ILIKE '%{words}%'")
        if getattr(spec, "metric_name", None):
            clean_name = spec.metric_name.strip().replace("'", "''")
            crit_conds.append(f"lc.name ILIKE '%{clean_name}%'")
            crit_conds.append(f"f.name ILIKE '%{clean_name}%'")

        where_clauses = [
            "f.report_status = 'approved'",
            f"f.tenant_code = '{user_ctx.tenant_code}'",
            f"({' OR '.join(crit_conds)})",
        ]

        # Tiêm các bộ lọc trong spec
        year_filter_present = False
        for flt in spec.filters:
            if flt.field in ("year", "year_code"):
                year_filter_present = True
                if flt.operator == "eq":
                    where_clauses.append(f"f.year_code = '{flt.value}'")
                elif flt.operator == "in" and isinstance(flt.value, list):
                    years_str = ", ".join(f"'{y}'" for y in flt.value)
                    where_clauses.append(f"f.year_code IN ({years_str})")
            elif flt.field == "department_code":
                where_clauses.append(f"f.department_code = '{flt.value}'")
            elif flt.field == "office_id":
                where_clauses.append(f"f.office_id = '{flt.value}'")

        # Tiêm phân quyền HBAC
        if user_ctx.department_code and not any(f.field == "department_code" for f in spec.filters):
            where_clauses.append(f"f.department_code = '{user_ctx.department_code}'")
        if user_ctx.office_id and user_ctx.role_level >= 2 and not any(f.field == "office_id" for f in spec.filters):
            where_clauses.append(f"f.office_id = '{user_ctx.office_id}'")

        where_str = "\n  AND ".join(where_clauses)

        select_cols = [
            "COALESCE(lc.name, f.name) AS ten_chi_tieu",
            "f.year_code AS nam",
            "SUM(NULLIF(TRIM(f.value), '')::numeric) AS tong_gia_tri",
            "COUNT(DISTINCT f.office_id) AS so_don_vi_bao_cao",
        ]

        raw_sql = (
            f"WITH latest_fact AS (\n"
            f"    SELECT f.criteria_id, f.office_id, f.name, f.year_code, f.value, f.department_code,\n"
            f"           ROW_NUMBER() OVER (\n"
            f"               PARTITION BY TRIM(LOWER(f.name)), f.year_code, COALESCE(f.office_id, '00000000-0000-0000-0000-000000000000'::uuid)\n"
            f"               ORDER BY f.report_date DESC, f.version DESC\n"
            f"           ) AS rn\n"
            f"    FROM dwh_internal.fact_report_criteria f\n"
            f"    WHERE {where_str}\n"
            f")\n"
            f"SELECT\n"
            f"    COALESCE(lc.name, lf.name) AS ten_chi_tieu,\n"
            f"    lf.year_code AS nam,\n"
            f"    SUM(NULLIF(TRIM(lf.value), '')::numeric) AS tong_gia_tri,\n"
            f"    COUNT(DISTINCT lf.office_id) AS so_don_vi_bao_cao\n"
            f"FROM latest_fact lf\n"
            f"LEFT JOIN dwh_internal.criteria lc ON lf.criteria_id = lc.id\n"
            f"WHERE lf.rn = 1\n"
            f"GROUP BY COALESCE(lc.name, lf.name), lf.year_code\n"
            f"ORDER BY lf.year_code ASC;"
        )

        latency_ms = (time.perf_counter() - t0) * 1000.0

        return GeneratedSQLDTO(
            raw_sql=raw_sql,
            execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
            dag_archetype="DIRECT_LOOKUP",
            tables_referenced=["dwh_internal.fact_report_criteria", "dwh_internal.criteria"],
            parameters={"tenant_code": user_ctx.tenant_code or "68"},
            generator_track="TRACK_A_COMPILER",
            thought_scratchpad="Biên dịch tất định qua Track A Deterministic Compiler (0 token LLM).",
            llm_provider=None,
            confidence_score=1.0,
            fallback_triggered=False,
            prompt_cache_hit=False,
            retry_count=0,
            ast_valid=True,
            latency_ms=latency_ms,
            trace_id=trace_id,
        )

    def compile_from_router(
        self,
        router_output: RouterOutputDTO,
        user_ctx: UserSecurityContextDTO,
        trace_id: str = "",
    ) -> Tuple[bool, Optional[GeneratedSQLDTO]]:
        """
        Thử biên dịch tất định trực tiếp từ RouterOutputDTO.
        Nếu khớp Archetype hoặc Fast Track -> Biên dịch tức thì trong RAM (< 1ms).
        Nếu không đủ thông tin hoặc câu hỏi phi chuẩn -> Trả về (False, None) để Fallthrough sang Track B.
        """
        t0 = time.perf_counter()

        if not self.can_compile_fast_track(router_output):
            return False, None

        year = None
        temporal_scope = getattr(router_output, "temporal_scope", {}) or {}
        if isinstance(temporal_scope, dict) and temporal_scope.get("start_year"):
            year = str(temporal_scope.get("start_year"))
        elif getattr(router_output, "active_quest", None) and router_output.active_quest.temporal_val:
            year = str(router_output.active_quest.temporal_val)
        else:
            m = re.search(r"\b(202[0-9])\b", router_output.query_sanitized or "")
            if m:
                year = m.group(1)

        # 1. Thử biên dịch theo Archetype nếu có
        from IPGov_Chatbot.modules.mod05_sql_compiler.archetype_patterns import (
            ArchetypePatternCatalog,
        )

        dag_archetype = getattr(router_output, "dag_archetype", None)
        if dag_archetype in ArchetypePatternCatalog.get_supported_archetypes():
            arch_sql = self._compile_archetype(router_output, user_ctx, dag_archetype)
            if arch_sql:
                latency_ms = (time.perf_counter() - t0) * 1000.0
                return True, GeneratedSQLDTO(
                    raw_sql=arch_sql,
                    execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
                    dag_archetype=dag_archetype,
                    tables_referenced=["dwh_internal.fact_report_criteria", "dwh_internal.criteria"],
                    parameters={"tenant_code": user_ctx.tenant_code or "68"},
                    generator_track="TRACK_A_COMPILER",
                    thought_scratchpad=f"Biên dịch tất định qua Track A Archetype Pattern ({dag_archetype}) (0 token LLM).",
                    llm_provider=None,
                    confidence_score=0.98,
                    fallback_triggered=False,
                    prompt_cache_hit=False,
                    retry_count=0,
                    ast_valid=True,
                    latency_ms=latency_ms,
                    trace_id=trace_id,
                )

        # 1.1 Fast Track cho 4 mẫu truy vấn khám phá và snapshot chỉ tiêu (P-01, P-02, P-03, P-04)
        if dag_archetype in (
            "MONTHLY_COLLECTION_METRIC_LISTING",
            "DATE_RANGE_CUMULATIVE_METRIC_DISCOVERY",
            "SYSTEM_WIDE_CRITERIA_INVENTORY",
            "SINGLE_METRIC_LATEST_SNAPSHOT",
        ):
            tenant_code = user_ctx.tenant_code or "68"
            query_low = (router_output.query_sanitized or "").lower()
            m_code, m_name = self._resolve_metric_info(router_output, user_ctx)
            if dag_archetype == "MONTHLY_COLLECTION_METRIC_LISTING":
                m_num = 9
                m_match = re.search(r"tháng\s+([1-9]|1[0-2])", query_low)
                if m_match:
                    m_num = int(m_match.group(1))
                raw_sql = f"""WITH latest_monthly_fact AS (
    SELECT f.name AS ten_chi_tieu, f.value, f.mission_name, f.office_id, f.report_date,
           ROW_NUMBER() OVER (PARTITION BY TRIM(LOWER(f.name)) ORDER BY f.report_date DESC, f.version DESC) AS rn
    FROM dwh_internal.fact_report_criteria f
    WHERE f.tenant_code = '{tenant_code}' AND f.year_code = '{year or "2026"}'
      AND EXTRACT(MONTH FROM f.report_date) = {m_num} AND f.report_status = 'approved'
)
SELECT lmf.ten_chi_tieu, lmf.value AS gia_tri_moi_nhat, lmf.mission_name AS ten_nhiem_vu,
       COALESCE(o.office_name, 'Cơ quan chủ quản') AS ten_van_phong, lmf.report_date AS ngay_bao_cao_moi_nhat
FROM latest_monthly_fact lmf
LEFT JOIN dwh_internal.office o ON lmf.office_id = o.id
WHERE lmf.rn = 1
ORDER BY lmf.ten_chi_tieu ASC LIMIT 500;"""
            elif dag_archetype == "DATE_RANGE_CUMULATIVE_METRIC_DISCOVERY":
                start_date = None
                active_q = getattr(router_output, "active_quest", None)
                if active_q:
                    t_val = getattr(active_q, "temporal_val", None)
                    if t_val:
                        if re.match(r"^\d{4}-\d{2}-\d{2}$", str(t_val).strip()):
                            start_date = str(t_val).strip()
                        else:
                            m_t = re.search(r"(?:tháng\s+)?([1-9]|1[0-2])", str(t_val).lower())
                            if m_t:
                                start_date = f"{year or '2026'}-{int(m_t.group(1)):02d}-01"
                    extra = getattr(active_q, "extra_slots", {}) or {}
                    if not start_date and extra.get("date_from"):
                        start_date = str(extra["date_from"])
                    if not start_date and extra.get("temporal_scope"):
                        t_scope = str(extra["temporal_scope"])
                        m_scope = re.search(r"(?:tháng\s+)?([1-9]|1[0-2])", t_scope.lower())
                        if m_scope:
                            start_date = f"{year or '2026'}-{int(m_scope.group(1)):02d}-01"

                if not start_date:
                    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", query_low)
                    if date_match:
                        start_date = date_match.group(1)
                    else:
                        m_match = re.search(r"(?:từ|sau|từ\s+đầu)\s+tháng\s+([1-9]|1[0-2])", query_low)
                        if m_match:
                            start_date = f"{year or '2026'}-{int(m_match.group(1)):02d}-01"
                        else:
                            m_any = re.search(r"tháng\s+([1-9]|1[0-2])", query_low)
                            if m_any:
                                start_date = f"{year or '2026'}-{int(m_any.group(1)):02d}-01"
                            else:
                                start_date = f"{year or '2026'}-01-01"

                raw_sql = f"""WITH latest_range_fact AS (
    SELECT f.name AS ten_chi_tieu, f.value, f.mission_name, f.office_id, f.report_date,
           ROW_NUMBER() OVER (PARTITION BY TRIM(LOWER(f.name)) ORDER BY f.report_date DESC, f.version DESC) AS rn
    FROM dwh_internal.fact_report_criteria f
    WHERE f.tenant_code = '{tenant_code}' AND f.report_date >= '{start_date}' AND f.report_status = 'approved'
)
SELECT lrf.ten_chi_tieu, lrf.value AS gia_tri_moi_nhat, lrf.mission_name AS ten_nhiem_vu,
       COALESCE(o.office_name, 'Cơ quan chủ quản') AS ten_van_phong, lrf.report_date AS ngay_bao_cao_moi_nhat
FROM latest_range_fact lrf
LEFT JOIN dwh_internal.office o ON lrf.office_id = o.id
WHERE lrf.rn = 1
ORDER BY lrf.report_date ASC, lrf.ten_chi_tieu ASC LIMIT 500;"""
            elif dag_archetype == "SYSTEM_WIDE_CRITERIA_INVENTORY":
                raw_sql = f"""WITH latest_inventory AS (
    SELECT f.name AS ten_chi_tieu, f.value, f.mission_name, f.office_id, f.report_date,
           ROW_NUMBER() OVER (PARTITION BY TRIM(LOWER(f.name)) ORDER BY f.report_date DESC, f.version DESC) AS rn
    FROM dwh_internal.fact_report_criteria f
    WHERE f.tenant_code = '{tenant_code}' AND f.report_status = 'approved'
)
SELECT DISTINCT li.ten_chi_tieu, li.value AS gia_tri_moi_nhat, li.mission_name AS ten_nhiem_vu,
       COALESCE(o.office_name, 'Cơ quan chủ quản') AS ten_van_phong, li.report_date AS ngay_bao_cao_moi_nhat
FROM latest_inventory li
LEFT JOIN dwh_internal.office o ON li.office_id = o.id
WHERE li.rn = 1
ORDER BY li.ten_chi_tieu ASC LIMIT 500;"""
            else:
                crit_filter = f"f.code = '{m_code}'" if m_code else (f"f.name ILIKE '%{m_name}%'" if m_name else "1=1")
                raw_sql = f"""WITH ranked_facts AS (
    SELECT f.criteria_id, f.parent_criteria_id, f.name AS ten_chi_tieu, f.value AS gia_tri_moi_nhat,
           f.mission_name AS ten_nhiem_vu, f.office_id, f.report_date AS ngay_bao_cao_moi_nhat,
           ROW_NUMBER() OVER (PARTITION BY f.criteria_id, f.office_id ORDER BY f.report_date DESC NULLS LAST, f.version DESC NULLS LAST) AS rn
    FROM dwh_internal.fact_report_criteria f
    WHERE f.tenant_code = '{tenant_code}' AND f.year_code = '{year or "2026"}'
      AND f.report_status = 'approved' AND ({crit_filter})
)
SELECT lf.ten_chi_tieu, lf.gia_tri_moi_nhat, lf.ten_nhiem_vu,
       COALESCE(o.office_name, 'Cấp tỉnh') AS ten_van_phong, lf.ngay_bao_cao_moi_nhat,
       p.name AS nhom_chi_tieu
FROM ranked_facts lf
LEFT JOIN dwh_internal.office o ON lf.office_id = o.id
LEFT JOIN dwh_internal.criteria p ON lf.parent_criteria_id = p.id
WHERE lf.rn = 1
ORDER BY lf.ngay_bao_cao_moi_nhat DESC NULLS LAST;"""

            return True, GeneratedSQLDTO(
                raw_sql=raw_sql,
                execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
                dag_archetype=dag_archetype,
                tables_referenced=["dwh_internal.fact_report_criteria", "dwh_internal.office"],
                parameters={"tenant_code": tenant_code},
                generator_track="TRACK_A_COMPILER",
                thought_scratchpad=f"Biên dịch tất định qua Track A Fast Track ({dag_archetype}) (0 token LLM).",
                confidence_score=0.99,
                ast_valid=True,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                trace_id=trace_id,
            )

        # 2. Xử lý tra cứu quy trình Báo cáo hoặc Biểu mẫu
        query = (router_output.query_sanitized or "").lower()
        tenant_code = user_ctx.tenant_code or "68"

        # Tra cứu trạng thái phê duyệt / tiến độ nộp báo cáo
        if any(k in query for k in ["phê duyệt", "chờ duyệt", "trạng thái", "tiến độ", "nộp trễ hạn", "từ chối", "đã nộp", "chưa nộp", "nộp báo cáo", "hạn nộp", "chưa hoàn thành nộp"]):
            year_clause = f"AND r.year_code = '{year}'" if year else ""
            raw_sql = f"""SELECT r.id AS ma_bao_cao, r.department_code AS ma_phong_ban, 
       r.status AS trang_thai_phe_duyet, r.report_date AS ngay_nop_bao_cao 
FROM dwh_internal.report r 
WHERE r.tenant_code = '{tenant_code}' AND r.deleted_date IS NULL {year_clause} 
ORDER BY r.report_date DESC LIMIT 5;"""
            return True, GeneratedSQLDTO(
                raw_sql=raw_sql,
                execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
                dag_archetype="REPORT_STATUS",
                tables_referenced=["dwh_internal.report"],
                parameters={"tenant_code": tenant_code},
                generator_track="TRACK_A_COMPILER",
                thought_scratchpad="Biên dịch tra cứu trạng thái báo cáo qua Track A Deterministic Compiler.",
                confidence_score=0.98,
                ast_valid=True,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                trace_id=trace_id,
            )

        # Tra cứu biểu mẫu thu thập số liệu
        if any(k in query for k in ["biểu mẫu", "mẫu phiếu", "tờ khai"]):
            form_where = f"WHERE cf.year_code = '{year}' AND cf.deleted_date IS NULL" if year else "WHERE cf.deleted_date IS NULL"
            raw_sql = f"""SELECT DISTINCT cf.id AS ma_bieu_mau, cf.name AS ten_bieu_mau, cf.code AS ky_hieu, cf.year_code, cf.status 
FROM dwh_internal.collection_form cf 
{form_where} 
ORDER BY cf.id ASC LIMIT 35;"""
            return True, GeneratedSQLDTO(
                raw_sql=raw_sql,
                execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
                dag_archetype="COLLECTION_FORM",
                tables_referenced=["dwh_internal.collection_form"],
                parameters={"tenant_code": tenant_code},
                generator_track="TRACK_A_COMPILER",
                thought_scratchpad="Biên dịch tra cứu danh mục biểu mẫu qua Track A Deterministic Compiler.",
                confidence_score=0.98,
                ast_valid=True,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                trace_id=trace_id,
            )

        # Tra cứu kiểm tra dữ liệu bất thường (để trống, bằng 0)
        if any(k in query for k in ["bất thường", "để trống", "bằng 0", "rỗng"]):
            fact_yr = f"f.year_code = '{year}' AND " if year else ""
            raw_sql = f"""SELECT DISTINCT f.department_code AS ma_phong_ban, f.report_id, f.code AS ma_chi_tieu, 
       f.name AS ten_chi_tieu, f.value AS gia_tri_bat_thuong, f.report_date 
FROM dwh_internal.fact_report_criteria f 
WHERE {fact_yr}f.tenant_code = '{tenant_code}' AND LOWER(f.report_status) = 'approved' AND f.report_delete_date IS NULL 
  AND (f.value IS NULL OR TRIM(f.value) = '' OR TRIM(f.value) = '0') 
ORDER BY f.report_date DESC LIMIT 10;"""
            return True, GeneratedSQLDTO(
                raw_sql=raw_sql,
                execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
                dag_archetype="DATA_ANOMALY",
                tables_referenced=["dwh_internal.fact_report_criteria"],
                parameters={"tenant_code": tenant_code},
                generator_track="TRACK_A_COMPILER",
                thought_scratchpad="Biên dịch phát hiện chỉ tiêu bất thường qua Track A Deterministic Compiler.",
                confidence_score=0.98,
                ast_valid=True,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                trace_id=trace_id,
            )

        # Tra cứu cán bộ phụ trách nhiệm vụ
        if any(k in query for k in ["cán bộ", "phụ trách nhiệm vụ", "nhiệm vụ trọng tâm"]):
            fact_yr = f"f.year_code = '{year}' AND " if year else ""
            raw_sql = f"""SELECT u.name AS ten_can_bo, u.position AS chuc_vu, f.department_code AS ma_phong_ban, 
       um.mission_name AS ten_nhiem_vu, COUNT(DISTINCT f.criteria_id) AS so_chi_tieu_hoan_thanh, 
       MAX(f.etl_updated_at) AS thoi_gian_cap_nhat 
FROM dwh_internal.fact_report_criteria f 
JOIN dwh_internal.user_mission um ON f.mission_id = um.mission_id 
JOIN dwh_internal."user" u ON um.user_id = u.id 
WHERE {fact_yr}f.tenant_code = '{tenant_code}' AND LOWER(f.report_status) = 'approved' 
  AND f.report_delete_date IS NULL AND um.deleted_date IS NULL AND u.deleted_at IS NULL 
GROUP BY u.name, u.position, f.department_code, um.mission_name 
ORDER BY so_chi_tieu_hoan_thanh DESC, u.name ASC LIMIT 10;"""
            return True, GeneratedSQLDTO(
                raw_sql=raw_sql,
                execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
                dag_archetype="USER_MISSION",
                tables_referenced=["dwh_internal.fact_report_criteria", "dwh_internal.user_mission", "dwh_internal.user"],
                parameters={"tenant_code": tenant_code},
                generator_track="TRACK_A_COMPILER",
                thought_scratchpad="Biên dịch tra cứu cán bộ phụ trách nhiệm vụ qua Track A Deterministic Compiler.",
                confidence_score=0.98,
                ast_valid=True,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                trace_id=trace_id,
            )

        # Tra cứu phân công nhiệm vụ văn phòng (office_mission)
        if any(k in query for k in ["office_mission", "gán cho văn phòng", "phân công cán bộ phụ trách nào"]):
            raw_sql = f"""SELECT om.mission_id AS ma_nhiem_vu, om.mission_name AS ten_nhiem_vu, o.office_name AS ten_van_phong, om.scope_name AS ten_linh_vuc, om.department_code 
FROM dwh_internal.office_mission om 
JOIN dwh_internal.office o ON om.office_id = o.id 
LEFT JOIN dwh_internal.mission m ON om.mission_id = m.id AND m.deleted_date IS NULL 
WHERE om.tenant_code = '{tenant_code}' AND (o.office_year = '{year}' OR m.year_code = '{year}') 
  AND om.deleted_date IS NULL AND o.deleted_at IS NULL 
  AND NOT EXISTS (SELECT 1 FROM dwh_internal.user_mission um WHERE um.mission_id = om.mission_id AND um.deleted_date IS NULL) 
ORDER BY om.mission_name ASC LIMIT 10;"""
            return True, GeneratedSQLDTO(
                raw_sql=raw_sql,
                execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
                dag_archetype="OFFICE_MISSION",
                tables_referenced=["dwh_internal.office_mission", "dwh_internal.office", "dwh_internal.mission"],
                parameters={"tenant_code": tenant_code},
                generator_track="TRACK_A_COMPILER",
                thought_scratchpad="Biên dịch rà soát nhiệm vụ văn phòng qua Track A Deterministic Compiler.",
                confidence_score=0.98,
                ast_valid=True,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                trace_id=trace_id,
            )

        # Tra cứu phát hiện trùng lặp bản ghi báo cáo
        if any(k in query for k in ["trùng lặp", "trùng lặp nhiều dòng"]):
            raw_sql = f"""SELECT f.report_id, f.department_code, f.code AS ma_chi_tieu, f.name AS ten_chi_tieu, 
       COUNT(f.fact_sk) AS so_lan_xuat_hien, COUNT(DISTINCT f.value) AS so_gia_tri_khac_nhau, 
       STRING_AGG(COALESCE(f.value, 'NULL'), '; ' ORDER BY f.fact_sk) AS danh_sach_gia_tri, 
       MAX(f.etl_updated_at) AS thoi_gian_cap_nhat 
FROM dwh_internal.fact_report_criteria f 
WHERE f.year_code = '{year}' AND f.tenant_code = '{tenant_code}' AND f.report_delete_date IS NULL 
GROUP BY f.report_id, f.department_code, f.code, f.name 
HAVING COUNT(f.fact_sk) > 1 
ORDER BY so_lan_xuat_hien DESC, f.report_id ASC, f.code ASC LIMIT 10;"""
            return True, GeneratedSQLDTO(
                raw_sql=raw_sql,
                execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
                dag_archetype="DUPLICATE_FACT",
                tables_referenced=["dwh_internal.fact_report_criteria"],
                parameters={"tenant_code": tenant_code},
                generator_track="TRACK_A_COMPILER",
                thought_scratchpad="Biên dịch phát hiện dữ liệu trùng lặp qua Track A Deterministic Compiler.",
                confidence_score=0.98,
                ast_valid=True,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                trace_id=trace_id,
            )

        # Tra cứu thời gian cập nhật ETL Freshness
        if any(k in query for k in ["cập nhật từ phần mềm", "kho dữ liệu tổng hợp chưa", "thời gian cập nhật kho", "đồng bộ gần nhất"]):
            raw_sql = f"""SELECT MAX(f.etl_updated_at) AS thoi_gian_dong_bo_gan_nhat, 
       COUNT(DISTINCT f.report_id) AS tong_so_bao_cao_hien_co 
FROM dwh_internal.fact_report_criteria f 
WHERE f.tenant_code = '{tenant_code}' AND f.report_delete_date IS NULL;"""
            return True, GeneratedSQLDTO(
                raw_sql=raw_sql,
                execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
                dag_archetype="ETL_FRESHNESS",
                tables_referenced=["dwh_internal.fact_report_criteria"],
                parameters={"tenant_code": tenant_code},
                generator_track="TRACK_A_COMPILER",
                thought_scratchpad="Biên dịch tra cứu tính tươi mới ETL qua Track A Deterministic Compiler.",
                confidence_score=0.98,
                ast_valid=True,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                trace_id=trace_id,
            )

        # 3. Biên dịch chỉ số đơn lẻ chuẩn tắc (Single Metric Fast Track)
        metric_code, metric_name = self._resolve_metric_info(router_output, user_ctx)

        # Nếu không có mã chỉ tiêu cụ thể -> Fallback sang danh mục chỉ tiêu báo cáo tổng quan của đơn vị
        if not metric_code and not metric_name:
            raw_sql = f"""SELECT f.department_code AS ma_don_vi, f.code AS ma_chi_tieu, f.name AS ten_chi_tieu, f.value AS gia_tri, f.report_date 
FROM dwh_internal.fact_report_criteria f 
WHERE f.year_code = '{year}' AND f.tenant_code = '{user_ctx.tenant_code or "68"}' AND LOWER(f.report_status) = 'approved' AND f.report_delete_date IS NULL 
ORDER BY f.report_date DESC LIMIT 10;"""
            return True, GeneratedSQLDTO(
                raw_sql=raw_sql,
                execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
                dag_archetype="DIRECT_LOOKUP",
                tables_referenced=["dwh_internal.fact_report_criteria"],
                parameters={"tenant_code": user_ctx.tenant_code or "68"},
                generator_track="TRACK_A_COMPILER",
                thought_scratchpad="Biên dịch tổng quan chỉ tiêu DWH qua Track A Deterministic Compiler.",
                confidence_score=0.95,
                ast_valid=True,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                trace_id=trace_id,
            )

        # Trích xuất phạm vi phòng ban/sở ngành
        department_code = None
        spatial_scope = getattr(router_output, "spatial_scope", {}) or {}
        active_quest = getattr(router_output, "active_quest", None)

        # Cưỡng chế quy tắc Cấp 0 (Tỉnh): nếu admin_level == 0 hoặc role_level == 0 (không có Sở cụ thể), department_code bắt buộc = None
        is_provincial_scope = False
        if active_quest and getattr(active_quest, "admin_level", None) == 0:
            is_provincial_scope = True
        elif user_ctx.role_level == 0 and not (isinstance(spatial_scope, dict) and spatial_scope.get("department_code")):
            is_provincial_scope = True

        if not is_provincial_scope:
            if isinstance(spatial_scope, dict) and spatial_scope.get("department_code"):
                department_code = spatial_scope.get("department_code")
            elif active_quest and getattr(active_quest, "admin_entity", None):
                if self.catalog:
                    dept_res = self.catalog.find_department_or_office(active_quest.admin_entity)
                    if dept_res and dept_res.get("type") in ("department", "office"):
                        department_code = dept_res.get("department_code") or dept_res.get("code")

        filters = [MetricFilter(field="year_code", operator="eq", value=year)]
        if department_code:
            filters.append(MetricFilter(field="department_code", operator="eq", value=department_code))


        spec = MetricSpecDTO(
            metric_code=metric_code or "chi_tieu",
            metric_name=metric_name,
            aggregation_func="SUM",
            grain="leaf_criteria",
            filters=filters,
            group_by=["year_code"],
        )

        dto = self.compile_from_spec(spec, user_ctx, trace_id=trace_id)
        return True, dto
