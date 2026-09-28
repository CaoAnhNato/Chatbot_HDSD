import time
import json
from sqlalchemy import create_engine, text

queries = [
    {
        "id": "ITEM_1",
        "sql": """SELECT COALESCE(SUM(NULLIF(f.value, '')::numeric), 0) AS tong_so_vu_tai_nan_lao_dong, MAX(f.etl_updated_at) AS thoi_gian_cap_nhat 
FROM dwh_internal.fact_report_criteria f 
WHERE f.year = '2026' AND f.tenant_code = :tenant_code AND LOWER(f.report_status) = 'approved' AND f.report_delete_date IS NULL 
  AND (f.name ILIKE '%tai nạn lao động%' OR f.code ILIKE '%tai_nan_lao_dong%');""",
        "params": {"tenant_code": "68"}
    },
    {
        "id": "ITEM_2",
        "sql": """SELECT d.name AS ten_don_vi, f.code AS ma_chi_tieu, f.name AS ten_chi_tieu, f.value AS gia_tri, f.report_date, f.report_status, f.etl_updated_at AS thoi_gian_cap_nhat 
FROM dwh_internal.fact_report_criteria f 
JOIN dwh_internal.deparment d ON f.department_code = d.code 
WHERE f.year = '2026' AND f.tenant_code = :tenant_code AND LOWER(f.report_status) = 'approved' AND f.report_delete_date IS NULL 
  AND (f.name ILIKE '%lao động%' OR f.name ILIKE '%việc làm%' OR f.scope_name ILIKE '%lao động%' OR f.mission_name ILIKE '%lao động%') 
ORDER BY f.report_date DESC, f.code ASC LIMIT 5;""",
        "params": {"tenant_code": "68"}
    },
    {
        "id": "ITEM_3",
        "sql": """SELECT COUNT(DISTINCT f.report_id) AS tong_so_bao_cao_phe_duyet, 
       COUNT(DISTINCT CASE WHEN f.scope_name ILIKE '%Y tế%' THEN f.report_id END) AS so_bao_cao_y_te, 
       COUNT(DISTINCT CASE WHEN f.scope_name ILIKE '%Công thương%' THEN f.report_id END) AS so_bao_cao_cong_thuong, 
       MAX(f.etl_updated_at) AS thoi_gian_cap_nhat 
FROM dwh_internal.fact_report_criteria f 
WHERE f.year = '2026' AND f.tenant_code = :tenant_code AND LOWER(f.report_status) = 'approved' AND f.report_delete_date IS NULL 
  AND (f.scope_name ILIKE '%Y tế%' OR f.scope_name ILIKE '%Công thương%');""",
        "params": {"tenant_code": "68"}
    },
    {
        "id": "ITEM_4",
        "sql": """SELECT COALESCE(d.ward_name, d.name) AS ten_xa, d.name AS ten_don_vi, SUM(NULLIF(f.value, '')::numeric) AS tong_so_vu_vi_pham, MAX(f.etl_updated_at) AS thoi_gian_cap_nhat 
FROM dwh_internal.fact_report_criteria f 
JOIN dwh_internal.deparment d ON f.department_code = d.code 
WHERE f.year = '2026' AND f.tenant_code = :tenant_code AND LOWER(f.report_status) = 'approved' AND f.report_delete_date IS NULL 
  AND f.name ILIKE '%vi phạm%' AND (f.name ILIKE '%an toàn%' OR f.name ILIKE '%lao động%') 
GROUP BY COALESCE(d.ward_name, d.name), d.name 
ORDER BY tong_so_vu_vi_pham DESC LIMIT 5;""",
        "params": {"tenant_code": "68"}
    },
    {
        "id": "ITEM_5",
        "sql": """SELECT DISTINCT COALESCE(d.ward_name, d.name) AS ten_xa, d.name AS ten_phong_ban, d.code AS ma_phong_ban, f.scope_name AS linh_vuc, f.code AS ma_chi_tieu, f.name AS ten_chi_tieu, f.value AS gia_tri, f.report_id, f.etl_updated_at AS thoi_gian_cap_nhat 
FROM dwh_internal.fact_report_criteria f 
JOIN dwh_internal.deparment d ON f.department_code = d.code 
WHERE f.year = '2026' AND f.tenant_code = :tenant_code AND LOWER(f.report_status) = 'approved' AND f.report_delete_date IS NULL 
  AND (f.scope_name ILIKE '%Công thương%' OR f.scope_name ILIKE '%Kinh doanh%') AND (f.name ILIKE '%an toàn%' OR f.name ILIKE '%vệ sinh%') 
ORDER BY ten_xa, ten_phong_ban LIMIT 5;""",
        "params": {"tenant_code": "68"}
    },
    {
        "id": "ITEM_6",
        "sql": """SELECT u.name AS ten_can_bo, u.position AS chuc_vu, um.mission_name AS ten_nhiem_vu, COUNT(DISTINCT f.criteria_id) AS tong_so_chi_tieu_hoan_thanh, MAX(f.etl_updated_at) AS thoi_gian_cap_nhat 
FROM dwh_internal.fact_report_criteria f 
JOIN dwh_internal.user_mission um ON f.mission_id = um.mission_id 
JOIN dwh_internal."user" u ON um.user_id = u.id 
WHERE f.year = '2026' AND f.tenant_code = :tenant_code AND LOWER(f.report_status) = 'approved' AND f.report_delete_date IS NULL AND um.deleted_date IS NULL 
  AND (f.scope_name ILIKE '%Nội vụ%' OR um.scope_name ILIKE '%Nội vụ%') AND (f.mission_name ILIKE '%cải cách hành chính%' OR um.mission_name ILIKE '%cải cách hành chính%') 
  AND NULLIF(f.value, '') IS NOT NULL 
GROUP BY u.name, u.position, um.mission_name LIMIT 5;""",
        "params": {"tenant_code": "68"}
    },
    {
        "id": "ITEM_7",
        "sql": """SELECT EXTRACT(MONTH FROM f.report_date)::integer AS thang, TO_CHAR(f.report_date, 'MM/YYYY') AS thang_nam, COUNT(DISTINCT f.report_id) AS so_luong_bao_cao_approved, MAX(f.etl_updated_at) AS thoi_gian_cap_nhat 
FROM dwh_internal.fact_report_criteria f 
WHERE f.year = '2026' AND f.tenant_code = :tenant_code AND LOWER(f.report_status) = 'approved' AND f.report_delete_date IS NULL AND f.scope_name ILIKE '%Y tế%' 
GROUP BY EXTRACT(MONTH FROM f.report_date), TO_CHAR(f.report_date, 'MM/YYYY') 
ORDER BY thang ASC;""",
        "params": {"tenant_code": "68"}
    },
    {
        "id": "ITEM_8",
        "sql": """SELECT DISTINCT COALESCE(d.ward_name, d.name) AS ten_xa, d.name AS ten_phong_ban, d.code AS ma_phong_ban, f.report_id, f.code AS ma_chi_tieu, f.name AS ten_chi_tieu, f.value AS gia_tri_loi, f.report_date, f.etl_updated_at AS thoi_gian_cap_nhat 
FROM dwh_internal.fact_report_criteria f 
JOIN dwh_internal.deparment d ON f.department_code = d.code 
WHERE f.year = '2026' AND f.tenant_code = :tenant_code AND LOWER(f.report_status) = 'approved' AND f.report_delete_date IS NULL 
  AND (f.value IS NULL OR TRIM(f.value) = '') AND (f.name ILIKE '%lao động%' OR f.scope_name ILIKE '%lao động%' OR f.mission_name ILIKE '%lao động%') 
ORDER BY ten_xa, f.name LIMIT 5;""",
        "params": {"tenant_code": "68"}
    }
]

engine = create_engine("postgresql+psycopg2://postgres:postgres@localhost:5432/vna_wom_dev")

results = []
with engine.connect() as conn:
    for item in queries:
        start_time = time.time()
        try:
            res = conn.execute(text(item["sql"]), item["params"])
            rows = res.fetchall()
            latency_ms = (time.time() - start_time) * 1000
            results.append({
                "id": item["id"],
                "status": "PASS",
                "latency_ms": round(latency_ms, 2),
                "row_count": len(rows),
                "sample_first_row": [str(x) for x in rows[0]] if rows else []
            })
        except Exception as e:
            results.append({
                "id": item["id"],
                "status": "FAIL",
                "error": str(e)
            })

import sys
sys.stdout.reconfigure(encoding='utf-8')
with open("C:/Users/Admin/.gemini/antigravity/brain/6a3b727f-88f2-4565-9796-068bd7dcf51f/scratch/results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("SUCCESS: Written to scratch/results.json")
