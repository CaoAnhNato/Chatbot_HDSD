"""
Module: IPGov_Chatbot/modules/mod05_sql_compiler/archetype_patterns.py
Chức năng: Thư viện 5 mẫu hình phân tích DWH (Kimball Analytical Archetypes).
Đặc tính: Single Unified SQL đẩy toàn bộ phép tính xuống PostgreSQL 16 Window Functions.
Căn cứ:
- Blueprint: 05_MULTI_AGENT_WORKFLOW_DIN_MAC_SQL.md (Mục 5)
- Specification: IPGov_Chatbot/docs/MODULE_05_SQL_COMPILER_SPEC.md (Mục 5.2)
- Tuân thủ TRAPS: [TRAP-004], [TRAP-005], [TRAP-007]
"""

from __future__ import annotations

from typing import Dict, List, Optional


class ArchetypePatternCatalog:
    """Thư viện mẫu Single Unified SQL Window Functions cho 5 Kimball Archetypes."""

    TEMPORAL_COMPARISON = "TEMPORAL_COMPARISON"
    CROSS_ENTITY_COMPARISON = "CROSS_ENTITY_COMPARISON"
    RANKING_TOP_K = "RANKING_TOP_K"
    PART_TO_WHOLE = "PART_TO_WHOLE"
    MULTI_DIMENSIONAL_PIVOT = "MULTI_DIMENSIONAL_PIVOT"

    @classmethod
    def get_supported_archetypes(cls) -> List[str]:
        return [
            cls.TEMPORAL_COMPARISON,
            cls.CROSS_ENTITY_COMPARISON,
            cls.RANKING_TOP_K,
            cls.PART_TO_WHOLE,
            cls.MULTI_DIMENSIONAL_PIVOT,
        ]

    @classmethod
    def build_temporal_comparison_sql(
        cls,
        metric_code: str = "",
        metric_name: str = "",
        years: Optional[List[str]] = None,
        tenant_code: str = "68",
        department_code: Optional[str] = None,
        office_id: Optional[str] = None,
    ) -> str:
        """Mẫu 1: So sánh chuỗi thời gian liên hoàn (YoY, MoM) qua hàm LAG()."""
        comp_years = sorted(list(set(years))) if years else []
        where_conds = [
            "f.report_status = 'approved'",
            f"f.tenant_code = '{tenant_code}'",
        ]
        if comp_years:
            years_in = ", ".join(f"'{y}'" for y in comp_years)
            where_conds.append(f"f.year_code IN ({years_in})")
        crit_conds = []
        if metric_code:
            crit_conds.append(f"c.code = '{metric_code}' OR f.code = '{metric_code}'")
        if metric_name:
            clean_name = metric_name.strip().replace("'", "''")
            crit_conds.append(f"c.name ILIKE '%{clean_name}%' OR f.name ILIKE '%{clean_name}%'")
        elif metric_code:
            words = metric_code.replace('_', ' ')
            crit_conds.append(f"c.name ILIKE '%{words}%' OR f.name ILIKE '%{words}%'")
        if crit_conds:
            where_conds.append(f"({' OR '.join(crit_conds)})")
        if department_code:
            where_conds.append(f"f.department_code = '{department_code}'")
        if office_id:
            where_conds.append(f"f.office_id = '{office_id}'")
        where_str = "\n      AND ".join(where_conds)

        return f"""WITH latest_fact AS (
    SELECT f.criteria_id, f.office_id, f.year_code,
           NULLIF(TRIM(f.value), '')::numeric AS numeric_val,
           ROW_NUMBER() OVER (
               PARTITION BY TRIM(LOWER(f.name)), f.year_code, COALESCE(f.office_id, '00000000-0000-0000-0000-000000000000'::uuid)
               ORDER BY f.report_date DESC, f.version DESC
           ) AS rn

    FROM dwh_internal.fact_report_criteria f
    LEFT JOIN dwh_internal.criteria c ON f.criteria_id = c.id
    WHERE {where_str}
),
annual_stat AS (
    SELECT 
        year_code AS nam,
        SUM(numeric_val) AS tong_gia_tri
    FROM latest_fact
    WHERE rn = 1
    GROUP BY year_code
)
SELECT 
    nam,
    tong_gia_tri,
    LAG(tong_gia_tri) OVER (ORDER BY nam ASC) AS tong_nam_truoc,
    tong_gia_tri - LAG(tong_gia_tri) OVER (ORDER BY nam ASC) AS bien_dong_tuyet_doi,
    ROUND(
        ((tong_gia_tri - LAG(tong_gia_tri) OVER (ORDER BY nam ASC)) / 
         NULLIF(LAG(tong_gia_tri) OVER (ORDER BY nam ASC), 0)) * 100.0, 
        2
    ) AS ty_le_tang_truong_pct
FROM annual_stat
ORDER BY nam DESC;"""

    @classmethod
    def build_ranking_top_k_sql(
        cls,
        metric_code: str = "",
        metric_name: str = "",
        year: Optional[str] = None,
        top_k: int = 5,
        tenant_code: str = "68",
        order_dir: str = "DESC",
    ) -> str:
        """Mẫu 3: Xếp hạng phân vị Top-K qua DENSE_RANK() kèm khoảng biến độ spread_val."""
        year_filter_clause = f"AND f.year_code = '{year}'" if year else ""
        if not metric_code and not metric_name:
            return f"""SELECT f.department_code AS ma_phong_ban, 
       COALESCE(SUM(NULLIF(f.value, '')::numeric), 0) AS tong_so_luong, 
       COUNT(DISTINCT f.report_id) AS so_bao_cao_approved 
FROM dwh_internal.fact_report_criteria f 
WHERE f.tenant_code = '{tenant_code}' {year_filter_clause} AND LOWER(f.report_status) = 'approved' AND f.report_delete_date IS NULL 
GROUP BY f.department_code 
ORDER BY tong_so_luong {order_dir}, f.department_code ASC LIMIT {top_k};"""

        where_conds = [
            "f.report_status = 'approved'",
            f"f.tenant_code = '{tenant_code}'",
        ]
        if year:
            where_conds.append(f"f.year_code = '{year}'")
        crit_conds = []
        if metric_code:
            crit_conds.append(f"c.code = '{metric_code}' OR f.code = '{metric_code}'")
        if metric_name:
            clean_name = metric_name.strip().replace("'", "''")
            crit_conds.append(f"c.name ILIKE '%{clean_name}%' OR f.name ILIKE '%{clean_name}%'")
        elif metric_code:
            words = metric_code.replace('_', ' ')
            crit_conds.append(f"c.name ILIKE '%{words}%' OR f.name ILIKE '%{words}%'")
        if crit_conds:
            where_conds.append(f"({' OR '.join(crit_conds)})")
        where_str = "\n      AND ".join(where_conds)

        return f"""WITH latest_fact AS (
    SELECT f.criteria_id, f.office_id, f.department_code,
           NULLIF(TRIM(f.value), '')::numeric AS numeric_val,
           ROW_NUMBER() OVER (
               PARTITION BY TRIM(LOWER(f.name)), COALESCE(f.office_id, '00000000-0000-0000-0000-000000000000'::uuid)
               ORDER BY f.report_date DESC, f.version DESC
           ) AS rn

    FROM dwh_internal.fact_report_criteria f
    LEFT JOIN dwh_internal.criteria c ON f.criteria_id = c.id
    WHERE {where_str}
),
ranked_entities AS (
    SELECT 
        COALESCE(o.office_name, lf.department_code) AS ten_don_vi,
        SUM(lf.numeric_val) AS tong_gia_tri,
        DENSE_RANK() OVER (ORDER BY SUM(lf.numeric_val) {order_dir}) AS rank_pos,
        MAX(SUM(lf.numeric_val)) OVER () - 
        MIN(SUM(lf.numeric_val)) OVER () AS khoang_bien_do
    FROM latest_fact lf
    LEFT JOIN dwh_internal.office o ON lf.office_id = o.id
    WHERE lf.rn = 1
    GROUP BY o.office_name, lf.department_code
)
SELECT ten_don_vi, tong_gia_tri, rank_pos, khoang_bien_do
FROM ranked_entities
WHERE rank_pos <= {top_k}
ORDER BY rank_pos ASC;"""

    @classmethod
    def build_cross_entity_comparison_sql(
        cls,
        metric_code: str = "",
        metric_name: str = "",
        year: Optional[str] = None,
        tenant_code: str = "68",
        department_code: Optional[str] = None,
    ) -> str:
        """Mẫu 2: Đối chuẩn ngang hàng đa thực thể qua AVG() OVER () và độ lệch chuẩn."""
        where_conds = [
            "f.report_status = 'approved'",
            f"f.tenant_code = '{tenant_code}'",
        ]
        if year:
            where_conds.append(f"f.year_code = '{year}'")
        crit_conds = []
        if metric_code:
            crit_conds.append(f"c.code = '{metric_code}' OR f.code = '{metric_code}'")
        if metric_name:
            clean_name = metric_name.strip().replace("'", "''")
            crit_conds.append(f"c.name ILIKE '%{clean_name}%' OR f.name ILIKE '%{clean_name}%'")
        elif metric_code:
            words = metric_code.replace('_', ' ')
            crit_conds.append(f"c.name ILIKE '%{words}%' OR f.name ILIKE '%{words}%'")
        if crit_conds:
            where_conds.append(f"({' OR '.join(crit_conds)})")
        if department_code:
            where_conds.append(f"f.department_code = '{department_code}'")
        where_str = "\n  AND ".join(where_conds)

        return f"""WITH latest_fact AS (
    SELECT f.criteria_id, f.office_id,
           NULLIF(TRIM(f.value), '')::numeric AS numeric_val,
           ROW_NUMBER() OVER (
               PARTITION BY TRIM(LOWER(f.name)), COALESCE(f.office_id, '00000000-0000-0000-0000-000000000000'::uuid)
               ORDER BY f.report_date DESC, f.version DESC
           ) AS rn

    FROM dwh_internal.fact_report_criteria f
    LEFT JOIN dwh_internal.criteria c ON f.criteria_id = c.id
    WHERE {where_str}
)
SELECT 
    COALESCE(o.office_name, 'Trực thuộc cơ quan chủ quản') AS ten_don_vi,
    SUM(lf.numeric_val) AS tong_gia_tri,
    AVG(SUM(lf.numeric_val)) OVER () AS trung_binh_nhom,
    SUM(lf.numeric_val) - AVG(SUM(lf.numeric_val)) OVER () AS chenh_lech_so_voi_tb
FROM latest_fact lf
LEFT JOIN dwh_internal.office o ON lf.office_id = o.id
WHERE lf.rn = 1
GROUP BY o.office_name
ORDER BY tong_gia_tri DESC;"""

    @classmethod
    def build_part_to_whole_sql(
        cls,
        year: Optional[str] = None,
        tenant_code: str = "68",
        department_code: Optional[str] = None,
        scope_name: Optional[str] = None,
    ) -> str:
        """Mẫu 4: Tỷ trọng cấu phần trên tổng thể qua hàm SUM() OVER ()."""
        where_conds = [
            "f.report_status = 'approved'",
            f"f.tenant_code = '{tenant_code}'",
        ]
        if year:
            where_conds.append(f"f.year_code = '{year}'")
        if department_code:
            where_conds.append(f"f.department_code = '{department_code}'")
        if scope_name:
            where_conds.append(f"f.scope_name ILIKE '%{scope_name}%'")

        where_str = " AND ".join(where_conds)

        return f"""WITH latest_fact AS (
    SELECT f.criteria_id, f.office_id, f.name,
           NULLIF(TRIM(f.value), '')::numeric AS numeric_val,
           ROW_NUMBER() OVER (
               PARTITION BY TRIM(LOWER(f.name)), COALESCE(f.office_id, '00000000-0000-0000-0000-000000000000'::uuid)
               ORDER BY f.report_date DESC, f.version DESC
           ) AS rn
    FROM dwh_internal.fact_report_criteria f
    WHERE {where_str}
)
SELECT 
    lf.name AS ten_thanh_phan,
    SUM(lf.numeric_val) AS gia_tri_thanh_phan,
    SUM(SUM(lf.numeric_val)) OVER () AS tong_so_toan_tinh,
    ROUND(
        (SUM(lf.numeric_val) / 
         NULLIF(SUM(SUM(lf.numeric_val)) OVER (), 0)) * 100.0, 
        2
    ) AS ty_trong_pct
FROM latest_fact lf
WHERE lf.rn = 1
GROUP BY lf.name
ORDER BY gia_tri_thanh_phan DESC;"""

    @classmethod
    def build_multi_dimensional_pivot_sql(
        cls,
        metric_code: str = "",
        metric_name: str = "",
        year_start: Optional[str] = None,
        year_end: Optional[str] = None,
        tenant_code: str = "68",
        department_code: Optional[str] = None,
    ) -> str:
        """Mẫu 5: Ma trận phân tích chéo đa chiều qua FILTER (WHERE year_code = ...)."""
        where_conds = [
            "f.report_status = 'approved'",
            f"f.tenant_code = '{tenant_code}'",
        ]
        pivot_years = [y for y in [year_start, year_end] if y]
        if pivot_years:
            years_in = ", ".join(f"'{y}'" for y in pivot_years)
            where_conds.append(f"f.year_code IN ({years_in})")
        crit_conds = []
        if metric_code:
            crit_conds.append(f"c.code = '{metric_code}' OR f.code = '{metric_code}'")
        if metric_name:
            clean_name = metric_name.strip().replace("'", "''")
            crit_conds.append(f"c.name ILIKE '%{clean_name}%' OR f.name ILIKE '%{clean_name}%'")
        elif metric_code:
            words = metric_code.replace('_', ' ')
            crit_conds.append(f"c.name ILIKE '%{words}%' OR f.name ILIKE '%{words}%'")
        if crit_conds:
            where_conds.append(f"({' OR '.join(crit_conds)})")
        if department_code:
            where_conds.append(f"f.department_code = '{department_code}'")
        where_str = "\n  AND ".join(where_conds)

        y_start_label = year_start or "truoc"
        y_end_label = year_end or "sau"

        return f"""WITH latest_fact AS (
    SELECT f.criteria_id, f.office_id, f.year_code,
           NULLIF(TRIM(f.value), '')::numeric AS numeric_val,
           ROW_NUMBER() OVER (
               PARTITION BY TRIM(LOWER(f.name)), f.year_code, COALESCE(f.office_id, '00000000-0000-0000-0000-000000000000'::uuid)
               ORDER BY f.report_date DESC, f.version DESC
           ) AS rn

    FROM dwh_internal.fact_report_criteria f
    LEFT JOIN dwh_internal.criteria c ON f.criteria_id = c.id
    WHERE {where_str}
)
SELECT 
    COALESCE(o.office_name, 'Cơ quan chủ quản') AS ten_phong_ban,
    SUM(lf.numeric_val) FILTER (WHERE lf.year_code = '{year_start}') AS nam_{y_start_label},
    SUM(lf.numeric_val) FILTER (WHERE lf.year_code = '{year_end}') AS nam_{y_end_label},
    ROUND(
        ((SUM(lf.numeric_val) FILTER (WHERE lf.year_code = '{year_end}') -
          SUM(lf.numeric_val) FILTER (WHERE lf.year_code = '{year_start}')) /
         NULLIF(SUM(lf.numeric_val) FILTER (WHERE lf.year_code = '{year_start}'), 0)) * 100.0, 
        2
    ) AS tang_truong_pct
FROM latest_fact lf
LEFT JOIN dwh_internal.office o ON lf.office_id = o.id
WHERE lf.rn = 1
GROUP BY o.office_name
ORDER BY nam_{y_end_label} DESC;"""
