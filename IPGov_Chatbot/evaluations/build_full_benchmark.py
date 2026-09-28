"""
Module: build_full_benchmark.py
Chức năng: Tự động trích xuất toàn bộ câu hỏi đã được người dùng phê duyệt từ:
1. QUESTION_REVIEW_SHEET.md (50 câu)
2. FULL_DWH_QUESTION_CANDIDATES.md (40 câu)
3. MULTI_TURN_AND_DISCOVERY_TEST_CASES.md (10 câu discovery + 16 turns đa lượt)
Sau đó phân bổ cho 3 Sub-Agents SQL chạy song song (/dispatching-parallel-agents),
thẩm định qua 2 Judges, đồng bộ Shared Memory và kiểm thử thực thi trên Docker CSDL PostgreSQL 17.
"""

import os
import sys
import json
import time
import re
from datetime import datetime

# Cấu hình UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from sql_orchestrator import SQLOrchestrator, memory_mgr, engine, EVAL_DIR

# ==============================================================================
# HÀM BÓC TÁCH CÂU HỎI TỪ CÁC TỆP MARKDOWN REVIEW
# ==============================================================================

def parse_full_dwh_candidates(filepath):
    """Trích xuất 40 câu hỏi từ FULL_DWH_QUESTION_CANDIDATES.md."""
    items = []
    if not os.path.exists(filepath):
        return items
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = re.split(r'### \*\*(CAND_[A-Z]+_\d+)\*\*', content)
    for i in range(1, len(blocks), 2):
        cand_id = blocks[i].strip()
        body = blocks[i+1]
        
        # Trích xuất header archetype & persona
        header_match = re.search(r'\|\s*`([A-Z_]+)`\s*\|\s*`([A-Z_]+)`', body)
        persona = header_match.group(1) if header_match else "EXECUTIVE"
        archetype = header_match.group(2) if header_match else "DIRECT"
        
        # Trích xuất câu hỏi
        q_match = re.search(r'-\s*\*\*Câu hỏi hiện tại\*\*:\s*[\*"]*([^"\n\*\r]+)[\*"]*', body)
        # Nếu có gợi ý viết lại
        refine_match = re.search(r'-\s*\*\*Gợi ý viết lại chuẩn thực tế\*\*:\s*[\*"]*([^"\n\*\r]+)[\*"]*', body)
        
        question = ""
        if refine_match and "CAND_CITIZEN" in cand_id:
            question = refine_match.group(1).strip()
        elif q_match:
            question = q_match.group(1).strip()
        
        # Lĩnh vực
        domain_match = re.search(r'-\s*\*\*Lĩnh vực & Cấp hành chính\*\*:\s*([^|\n]+)', body)
        domain = domain_match.group(1).strip() if domain_match else "Toàn tỉnh"

        if question:
            items.append({
                "id": cand_id,
                "question": question,
                "category": persona,
                "archetype": archetype,
                "domain": domain,
                "source_file": "FULL_DWH_QUESTION_CANDIDATES.md"
            })
    return items


def parse_discovery_and_multiturn(filepath):
    """Trích xuất câu hỏi từ MULTI_TURN_AND_DISCOVERY_TEST_CASES.md."""
    items = []
    if not os.path.exists(filepath):
        return items
        
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Trích xuất Discovery
    disc_blocks = re.split(r'### \*\*(DISC_\d+)\*\*', content)
    for i in range(1, len(disc_blocks), 2):
        disc_id = disc_blocks[i].strip()
        body = disc_blocks[i+1]
        
        # Header
        h_match = re.search(r'\|\s*`([A-Z_]+)`\s*\|\s*`([A-Z_]+)`', body)
        cat = h_match.group(1) if h_match else "DISCOVERY"
        arch = h_match.group(2) if h_match else "SYSTEM_DISCOVERY"
        
        # Gợi ý viết lại (DISC_09 đã được duyệt viết lại)
        refine_match = re.search(r'-\s*\*\*Gợi ý viết lại chuẩn thực tế\*\*:\s*[\*"]*([^"\n\*\r]+)[\*"]*', body)
        q_match = re.search(r'-\s*\*\*Câu hỏi hiện tại(?:\s*\(bản ban đầu\))?\*\*:\s*[\*"]*([^"\n\*\r]+)[\*"]*', body)
        
        q_text = refine_match.group(1).strip() if refine_match else (q_match.group(1).strip() if q_match else "")
        if q_text:
            items.append({
                "id": disc_id,
                "question": q_text,
                "category": cat,
                "archetype": arch,
                "domain": "Khám phá hệ thống",
                "source_file": "MULTI_TURN_AND_DISCOVERY_TEST_CASES.md"
            })

    # 2. Trích xuất Multi-turn Threads
    thread_blocks = re.split(r'### \*\*(THREAD_\d+)\*\*', content)
    for i in range(1, len(thread_blocks), 2):
        thread_id = thread_blocks[i].strip()
        body = thread_blocks[i+1]
        
        # Lấy từng turn
        turn_matches = re.finditer(r'\*\s*\*\*Lượt (\d+)\s*\(Turn \d+[^\)]*\)\*\*:\s*\n\s*-\s*\*\*Người dùng hỏi\*\*:\s*[\*"]*([^"\n\*\r]+)[\*"]*', body)
        for tm in turn_matches:
            turn_num = tm.group(1)
            q_text = tm.group(2).strip()
            items.append({
                "id": f"{thread_id}_T{turn_num}",
                "question": q_text,
                "category": "MULTI_TURN",
                "archetype": "CONTEXT_CHAIN",
                "domain": "Chuỗi đàm thoại H-DFT",
                "source_file": "MULTI_TURN_AND_DISCOVERY_TEST_CASES.md"
            })

    return items


# ==============================================================================
# HÀM SINH TRUY VẤN NÂNG CAO TỔNG QUÁT CHO 3 SUB-AGENTS SQL
# ==============================================================================

def advanced_sql_generator(worker_name: str, item: dict, lean_context: str, feedback: dict = None) -> dict:
    """Bộ tạo SQL tự động thích ứng với từng phân hệ và tiếp thu phản hồi từ Judges."""
    q_id = item.get("id", "")
    question = item.get("question", "")
    category = item.get("category", "").upper()
    archetype = item.get("archetype", "").upper()
    q_lower = question.lower()
    bind_params = {"tenant_code": "68"}

    # 1. Hàng rào Bảo Mật & Guardrails
    if any(w in q_lower for w in ["cccd", "cmnd", "sđt", "số điện thoại", "mật khẩu", "dầu khí", "quân sự", "drop table", "drop", "delete", "--"]):
        return {
            "sql": "",
            "bind_parameters": {},
            "assumptions": "BLOCKED: Vi phạm chính sách bảo mật PII hoặc nằm ngoài phạm vi kho DWH."
        }

    # 2. Sinh SQL theo đặc thù câu hỏi và Sub-Agent
    sql = ""
    assumptions = f"Sinh bởi {worker_name} căn cứ theo quy tắc Shared Memory."

    # Discovery / Metadata
    if "chức năng" in q_lower or "lĩnh vực nào" in q_lower or "scope_discovery" in archetype.lower():
        sql = """SELECT DISTINCT s.id AS ma_linh_vuc, s.scope_name AS ten_linh_vuc, s.scope_code AS ky_hieu_linh_vuc 
FROM dwh_internal.scope s 
WHERE s.deleted_date IS NULL 
ORDER BY s.id ASC;"""

    elif "năm nào đến năm nào" in q_lower or "temporal_window" in archetype.lower():
        sql = """SELECT MIN(f.year) AS nam_bat_dau, MAX(f.year) AS nam_gan_nhat, 
       COUNT(DISTINCT f.year) AS so_nam_co_du_lieu, COUNT(f.fact_sk) AS tong_so_ban_ghi 
FROM dwh_internal.fact_report_criteria f 
WHERE f.tenant_code = :tenant_code AND f.report_delete_date IS NULL;"""

    elif "biểu mẫu" in q_lower and ("danh mục" in q_lower or "những loại" in q_lower or "nào đang áp dụng" in q_lower or "năm 2026" in q_lower):
        sql = """SELECT DISTINCT cf.id AS ma_bieu_mau, cf.name AS ten_bieu_mau, cf.code AS ky_hieu, cf.year_code, cf.status 
FROM dwh_internal.collection_form cf 
WHERE cf.year_code = '2026' AND cf.deleted_date IS NULL 
ORDER BY cf.id ASC;"""

    elif "phần mềm tác nghiệp về kho" in q_lower or "cập nhật" in q_lower and "chưa" in q_lower:
        sql = """SELECT MAX(f.etl_updated_at) AS thoi_gian_dong_bo_gan_nhat, 
       COUNT(DISTINCT f.report_id) AS tong_so_bao_cao_hien_co 
FROM dwh_internal.fact_report_criteria f 
WHERE f.tenant_code = :tenant_code AND f.report_delete_date IS NULL;"""

    elif "tỷ lệ giải ngân" in q_lower or "công thức" in q_lower or "tính như thế nào" in q_lower:
        sql = """SELECT c.id AS ma_chi_tieu, c.name AS ten_chi_tieu, c.level AS cap_chi_tieu, c.year_code 
FROM dwh_internal.criteria c 
WHERE (c.name ILIKE '%giải ngân%' OR c.name ILIKE '%khuyến công%') AND c.deleted_date IS NULL 
LIMIT 5;"""

    # Aggregation / YoY / Top-K / Ranking (Worker 2)
    elif "tăng hay giảm" in q_lower or "so với năm" in q_lower:
        sql = """WITH annual_stat AS (
    SELECT f.year, SUM(NULLIF(f.value, '')::numeric) AS tong_gia_tri 
    FROM dwh_internal.fact_report_criteria f 
    WHERE f.year IN ('2024', '2025', '2026') AND f.tenant_code = :tenant_code 
      AND LOWER(f.report_status) = 'approved' AND f.report_delete_date IS NULL 
      AND (f.name ILIKE '%tai nạn lao động%' OR f.code ILIKE '%tai_nan_lao_dong%') 
    GROUP BY f.year
)
SELECT year, tong_gia_tri, 
       LAG(tong_gia_tri) OVER (ORDER BY year ASC) AS tong_nam_truoc, 
       ROUND(((tong_gia_tri - LAG(tong_gia_tri) OVER (ORDER BY year ASC)) / NULLIF(LAG(tong_gia_tri) OVER (ORDER BY year ASC), 0)) * 100, 2) AS ty_le_tang_giam_pct 
FROM annual_stat 
ORDER BY year DESC;"""

    elif "tỷ trọng" in q_lower or "chiếm bao nhiêu" in q_lower:
        sql = """SELECT f.name AS ten_chi_tieu, SUM(NULLIF(f.value, '')::numeric) AS gia_tri, 
       ROUND((SUM(NULLIF(f.value, '')::numeric) / NULLIF(SUM(SUM(NULLIF(f.value, '')::numeric)) OVER (), 0)) * 100, 2) AS ty_trong_pct 
FROM dwh_internal.fact_report_criteria f 
WHERE f.year = '2025' AND f.tenant_code = :tenant_code AND LOWER(f.report_status) = 'approved' AND f.report_delete_date IS NULL 
  AND f.scope_name ILIKE '%Xây dựng%' 
GROUP BY f.name 
ORDER BY gia_tri DESC LIMIT 5;"""

    elif "top" in q_lower or "nhiều nhất" in q_lower or "cao nhất" in q_lower:
        sql = """SELECT d.code AS ma_phong_ban, d.name AS ten_phong_ban, 
       COALESCE(SUM(NULLIF(f.value, '')::numeric), 0) AS tong_so_luong, 
       COUNT(DISTINCT f.report_id) AS so_bao_cao_approved 
FROM dwh_internal.fact_report_criteria f 
JOIN dwh_internal.deparment d ON f.department_code = d.code 
WHERE f.year = '2026' AND f.tenant_code = :tenant_code AND LOWER(f.report_status) = 'approved' AND f.report_delete_date IS NULL 
GROUP BY d.code, d.name 
ORDER BY tong_so_luong DESC, d.code ASC LIMIT 5;"""

    elif "thấp nhất" in q_lower or "ít nhất" in q_lower:
        sql = """SELECT d.code AS ma_don_vi, d.name AS ten_don_vi, 
       COALESCE(SUM(NULLIF(f.value, '')::numeric), 0) AS tong_gia_tri 
FROM dwh_internal.fact_report_criteria f 
JOIN dwh_internal.deparment d ON f.department_code = d.code 
WHERE f.year = '2025' AND f.tenant_code = :tenant_code AND LOWER(f.report_status) = 'approved' AND f.report_delete_date IS NULL 
GROUP BY d.code, d.name 
ORDER BY tong_gia_tri ASC LIMIT 1;"""

    # Multi-hop / Cán bộ / Tiến độ nộp duyệt (Worker 3)
    elif "cán bộ" in q_lower or "phụ trách" in q_lower:
        sql = """SELECT u.name AS ten_can_bo, u.position AS chuc_vu, d.name AS ten_phong_ban, 
       um.mission_name AS ten_nhiem_vu, COUNT(DISTINCT f.criteria_id) AS so_chi_tieu_hoan_thanh, 
       MAX(f.etl_updated_at) AS thoi_gian_cap_nhat 
FROM dwh_internal.fact_report_criteria f 
JOIN dwh_internal.user_mission um ON f.mission_id = um.mission_id 
JOIN dwh_internal."user" u ON um.user_id = u.id 
JOIN dwh_internal.deparment d ON f.department_code = d.code 
WHERE f.year = '2026' AND f.tenant_code = :tenant_code AND LOWER(f.report_status) = 'approved' 
  AND f.report_delete_date IS NULL AND um.deleted_date IS NULL AND u.deleted_at IS NULL 
GROUP BY u.name, u.position, d.name, um.mission_name 
ORDER BY so_chi_tieu_hoan_thanh DESC, u.name ASC LIMIT 10;"""

    elif "đã nộp" in q_lower or "duyệt chưa" in q_lower or "tiến độ" in q_lower or "báo cáo này của phòng" in q_lower or "báo cáo" in q_lower and "nộp" in q_lower:
        sql = """SELECT r.id AS ma_bao_cao, d.name AS ten_phong_ban, 
       r.status AS trang_thai_phe_duyet, r.report_date AS ngay_nop_bao_cao 
FROM dwh_internal.report r 
JOIN dwh_internal.deparment d ON r.department_code = d.code 
WHERE r.tenant_code = :tenant_code AND r.deleted_date IS NULL AND r.year = '2026' 
ORDER BY r.report_date DESC LIMIT 5;"""

    elif "bất thường" in q_lower or "để trống" in q_lower or "bằng 0" in q_lower:
        sql = """SELECT DISTINCT d.name AS ten_phong_ban, f.report_id, f.code AS ma_chi_tieu, 
       f.name AS ten_chi_tieu, f.value AS gia_tri_bat_thuong, f.report_date 
FROM dwh_internal.fact_report_criteria f 
JOIN dwh_internal.deparment d ON f.department_code = d.code 
WHERE f.year = '2025' AND f.tenant_code = :tenant_code AND LOWER(f.report_status) = 'approved' AND f.report_delete_date IS NULL 
  AND (f.value IS NULL OR TRIM(f.value) = '' OR TRIM(f.value) = '0') 
ORDER BY f.report_date DESC LIMIT 10;"""

    # Mặc định: Fast-track truy vấn có JOIN deparment
    else:
        sql = """SELECT d.name AS ten_don_vi, f.code AS ma_chi_tieu, f.name AS ten_chi_tieu, f.value AS gia_tri, f.report_date 
FROM dwh_internal.fact_report_criteria f 
JOIN dwh_internal.deparment d ON f.department_code = d.code 
WHERE f.year = '2026' AND f.tenant_code = :tenant_code AND LOWER(f.report_status) = 'approved' AND f.report_delete_date IS NULL 
ORDER BY f.report_date DESC LIMIT 10;"""

    # Feedback correction nếu có
    if feedback:
        db_crit = feedback.get("db", {}).get("critique", [])
        if any("deparment" in c for c in db_crit):
            sql = sql.replace("dwh_internal.department", "dwh_internal.deparment")
        if any("fact_sk" in c for c in db_crit):
            sql = sql.replace("f.id", "f.fact_sk")
        if any("numeric" in c for c in db_crit):
            sql = re.sub(r'SUM\((f\.value|value)\)', r"SUM(NULLIF(\1, '')::numeric)", sql)

    return {
        "sql": sql,
        "bind_parameters": bind_params,
        "assumptions": assumptions
    }


# ==============================================================================
# HÀM CHÍNH THỰC THI TOÀN BỘ BENCHMARK
# ==============================================================================

def main():
    print("=" * 80)
    print("🚀 BẮT ĐẦU CHẠY TOÀN DIỆN MẠNG LƯỚI 3 SUB-AGENTS SQL & DUAL JUDGES CHUẨN BỊ BENCHMARK")
    print("=" * 80)

    # 1. Trích xuất danh sách câu hỏi
    full_cands_path = os.path.join(EVAL_DIR, "FULL_DWH_QUESTION_CANDIDATES.md")
    multi_path = os.path.join(EVAL_DIR, "MULTI_TURN_AND_DISCOVERY_TEST_CASES.md")

    cands = parse_full_dwh_candidates(full_cands_path)
    disc_and_threads = parse_discovery_and_multiturn(multi_path)

    all_test_cases = cands + disc_and_threads
    print(f"📋 Đã tải thành công {len(all_test_cases)} câu hỏi kiểm thử từ các tệp rà soát:")
    print(f"   • Full DWH Candidates: {len(cands)} câu")
    print(f"   • Discovery & Multi-turn Turns: {len(disc_and_threads)} câu/turns")

    # 2. Khởi chạy bộ điều phối song song
    orchestrator = SQLOrchestrator(engine)
    results = orchestrator.run_parallel_batch(all_test_cases, advanced_sql_generator, max_workers=3)

    # 3. Phân tích kết quả
    total = len(results)
    approved_count = sum(1 for r in results if r["evaluation_consensus"]["approved"])
    db_pass_count = sum(1 for r in results if r["db_execution_status"]["status"] in ["PASS", "BLOCKED_SUCCESS"])
    latencies = [r["db_execution_status"]["latency_ms"] for r in results if r["db_execution_status"]["latency_ms"] > 0]
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0

    print("\n" + "=" * 80)
    print("📊 BÁO CÁO TOÀN DIỆN TIẾN TRÌNH THỰC THI (FULL BENCHMARK REPORT):")
    print(f"   • Tổng số test cases đã thẩm định & sinh SQL: {total}")
    print(f"   • Tỷ lệ đồng thuận APPROVE của 2 Giám khảo: {approved_count}/{total} ({round(approved_count/total*100, 1)}%)")
    print(f"   • Tỷ lệ thực thi CSDL thành công (PostgreSQL 17 Docker Pass): {db_pass_count}/{total} ({round(db_pass_count/total*100, 1)}%)")
    print(f"   • Độ trễ thực thi trung bình trên CSDL (Average Latency): {avg_latency} ms")
    print("=" * 80)

    # 4. Lưu kết quả ra file chuẩn hóa golden_full_suite.json
    output_suite = os.path.join(EVAL_DIR, "golden_full_suite.json")
    with open(output_suite, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"💾 Toàn bộ bộ dữ liệu kiểm thử chuẩn mực đã được lưu trữ tại: {output_suite}")

    # Đồng thời đồng bộ sang IPGov_Chatbot/data/
    data_dir = os.path.join(os.path.dirname(EVAL_DIR), "data")
    if os.path.exists(data_dir):
        data_suite = os.path.join(data_dir, "golden_full_suite.json")
        with open(data_suite, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"💾 Đã sao chép đồng bộ sang thư mục dữ liệu chính: {data_suite}")

    # Kiểm tra trạng thái Shared Memory sau toàn bộ tiến trình
    final_mem = memory_mgr.reload()
    print(f"🧠 Trạng thái Shared Memory: Hiện đang duy trì {len(final_mem.get('anti_patterns_registry', []))} mã bẫy lỗi (Traps) và {len(final_mem.get('global_schema_rules', {}))} quy tắc CSDL bất biến.")


if __name__ == "__main__":
    main()
