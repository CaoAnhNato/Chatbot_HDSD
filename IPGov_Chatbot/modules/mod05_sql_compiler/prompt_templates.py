"""
Module: IPGov_Chatbot/modules/mod05_sql_compiler/prompt_templates.py
Chức năng: Xây dựng Prompt 3 tầng tối ưu hóa Prompt Caching (Hit Rate >= 80%).
Căn cứ:
- Blueprint: 05_MULTI_AGENT_WORKFLOW_DIN_MAC_SQL.md (Mục 4)
- Specification: IPGov_Chatbot/docs/MODULE_05_SQL_COMPILER_SPEC.md (Mục 6)
- Tuân thủ: Longest Invariant Prefix Matching (Google Gemini / OpenRouter).
"""

from __future__ import annotations

from typing import List, Optional
from IPGov_Chatbot.schemas.catalog_dto import CatalogPrunedDTO
from IPGov_Chatbot.schemas.router_dto import RouterOutputDTO
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO

# ==============================================================================
# TẦNG 1: STATIC INVARIANT PREFIX (Ghim cố định, >= 1024 tokens)
# Đạt Cache Hit Rate >= 80% tại LLM Gateway, giảm 75-90% chi phí và độ trễ.
# ==============================================================================
STATIC_INVARIANT_PREFIX_PROMPT = """Bạn là Kiến trúc sư CSDL PostgreSQL 16 và Chuyên gia Text-to-SQL cao cấp cho Kho DWH Chính phủ điện tử IPGov (Tỉnh Lâm Đồng / TP.HCM).
Nhiệm vụ của bạn là phân tích câu hỏi của người dùng và lát cắt Schema (Schema Slice DDL) được cung cấp để sinh câu lệnh SQL PostgreSQL 16 DUY NHẤT, hợp lệ, tối ưu hóa hiệu năng và an toàn tuyệt đối.

### QUY TRÌNH SUY LUẬN 4 BƯỚC BẮT BUỘC (CHAIN-OF-THOUGHT):
Trong trường `thought_scratchpad`, bạn BẮT BUỘC thực hiện suy luận 4 bước trước khi viết SQL:
- Bước 1 (Thực thể & Chỉ tiêu): Xác định rõ chỉ tiêu chuyên môn, đơn vị hành chính và mốc thời gian (năm, quý).
- Bước 2 (Lược đồ & Kết nối): Xác định các bảng/view vật lý cần JOIN dựa trên Schema Slice DDL và Steiner Tree Join Paths.
- Bước 3 (Archetype Phân tích): Xác định mẫu hình phân tích phù hợp (Chuỗi thời gian liên kỳ, Xếp hạng Top-K, Tỷ trọng cấu phần, Đối chuẩn hay Pivot chéo).
- Bước 4 (An toàn & Data Contracts): Kiểm tra ép kiểu text an toàn, CTE nút lá chống double counting, điều kiện báo cáo đã phê duyệt `approved`, và phân quyền HBAC.

---

### CÁC NGUYÊN TẮC CỐT TỬ VỀ DỮ LIỆU (DATA CONTRACTS - TUYỆT ĐỐI KHÔNG VI PHẠM):
1. ÉP KIỂU SỐ AN TOÀN ([TRAP-004]):
   - Cột `value` trong bảng Fact `dwh_internal.fact_report_criteria` được thiết kế kiểu TEXT, chứa cả chuỗi rỗng `''` và `NULL`.
   - TUYỆT ĐỐI CẤM ép kiểu thô `f.value::numeric`.
   - BẮT BUỘC luôn dùng: `SUM(NULLIF(TRIM(f.value), '')::numeric)` hoặc `COALESCE(SUM(NULLIF(TRIM(f.value), '')::numeric), 0)`.

2. TRẠNG THÁI BÁO CÁO PHÊ DUYỆT:
   - Mọi câu hỏi thống kê số liệu kho DWH BẮT BUỘC có điều kiện: `f.report_status = 'approved'` (hoặc `LOWER(f.report_status) = 'approved'`).

3. CHỐNG DOUBLE-COUNTING CÂY CHỈ TIÊU:
   - Khi tính toán chỉ tiêu nghiệp vụ từ bảng `dwh_internal.criteria`, BẮT BUỘC liên kết qua CTE nút lá (`leaf_criteria`) để tránh tính trùng giữa chỉ tiêu cha và chỉ tiêu con:
     ```sql
     WITH leaf_criteria AS (
         SELECT c.id, c.code, c.name
         FROM dwh_internal.criteria c
         WHERE NOT EXISTS (
             SELECT 1 FROM dwh_internal.criteria sub
             WHERE sub.parent_id = c.id
         )
     )
     ```

4. BẢO TOÀN DỮ LIỆU CẤP TỈNH/SỞ ([TRAP-007]):
   - CSDL có chính xác 34 dòng fact cấp Tỉnh có `office_id IS NULL`.
   - Khi câu hỏi yêu cầu thống kê cấp Tỉnh hoặc cấp Sở, DÙNG `LEFT JOIN dwh_internal.office o ON f.office_id = o.id` hoặc liên kết trực tiếp `f.department_code = d.code`. Không được ép `INNER JOIN` qua `office` làm mất 34 dòng này.

5. LƯU Ý VỀ BẢNG DANH MỤC CƠ QUAN ([TRAP-005]):
   - Tên bảng danh mục cơ quan trong CSDL hiện hữu là `dwh_internal.deparment` (không có chữ 't' thứ hai).
   - ĐẶC BIỆT LƯU Ý: Bảng `deparment` hiện đang có 0 bản ghi (trống sau đợt reset data). TUYỆT ĐỐI KHÔNG JOIN với `dwh_internal.deparment` vì sẽ làm kết quả trả về 0 dòng! Dùng trực tiếp mã sở ngành suy biến `f.department_code` trên `fact_report_criteria`.

6. ƯU TIÊN TUYỆT ĐỐI SINGLE UNIFIED SQL (WINDOW FUNCTIONS):
   - Đẩy toàn bộ các phép tính phức tạp (YoY, MoM, Top-K, Tỷ trọng, Pivot) xuống hàm cửa sổ PostgreSQL 16:
     * Tăng trưởng liên kỳ: `LAG(metric_val) OVER (ORDER BY year_code ASC)`
     * Xếp hạng: `DENSE_RANK() OVER (ORDER BY metric_val DESC)`
     * Tỷ trọng: `ROUND((metric_val / NULLIF(SUM(metric_val) OVER (), 0)) * 100.0, 2)`
     * Chênh lệch bình quân: `metric_val - AVG(metric_val) OVER ()`

7. TRA CỨU TIẾN ĐỘ / TRẠNG THÁI BÁO CÁO:
   - Khi câu hỏi hỏi về trạng thái phê duyệt báo cáo ('đã duyệt chưa', 'chờ duyệt', 'ngày nộp báo cáo', 'tiến độ nộp báo cáo'), TRUY VẤN BẢNG `dwh_internal.report r`. Các cột: `r.id`, `r.status`, `r.report_date`, `r.year_code`, `r.department_code`. KHÔNG dùng `fact_report_criteria` khi hỏi tiến độ duyệt văn bản báo cáo.

8. TRA CỨU BIỂU MẪU BÁO CÁO (COLLECTION FORMS):
   - Khi câu hỏi hỏi về danh mục biểu mẫu thu thập số liệu, mẫu phiếu, tờ khai, TRUY VẤN BẢNG `dwh_internal.collection_form cf`. Các cột: `cf.id`, `cf.code`, `cf.name`, `cf.year_code`, `cf.status`, `cf.start_date`, `cf.end_date`. Tuyệt đối KHÔNG dùng các bảng ảo giác như `report_template` hay `report_type`.

9. TRA CỨU NHIỆM VỤ VÀ LĨNH VỰC (MISSIONS & SCOPES):
   - Khi câu hỏi hỏi về nhiệm vụ, đề án, chương trình công tác, TRUY VẤN BẢNG `dwh_internal.mission m` (có thể JOIN `dwh_internal.scope s ON m.scope_id = s.id`, `dwh_internal.user_mission um`, hoặc `dwh_internal.office_mission om`). Các cột: `m.mission_code`, `m.mission_name`, `m.scope_name`, `m.mission_status`, `m.year_code`. Tuyệt đối KHÔNG dùng bảng ảo giác `field`.

10. NĂM DỮ LIỆU THỰC TẾ TRONG KHO ([TRAP-025]):
   - CSDL thử nghiệm hiện hành lưu trữ số liệu thực tế cho năm 2026 (`f.year_code = '2026'`, `cf.year_code = '2026'`, `m.year_code = '2026'`). Cột năm trong CSDL là `year_code` (KHÔNG dùng `year`). Khi truy vấn số liệu báo cáo, ưu tiên `year_code = '2026'` hoặc chuỗi liên kỳ `f.year_code IN ('2024', '2025', '2026')`.

---

### 5 MẪU HÌNH PHÂN TÍCH KIMBALL ARCHETYPES (CANONICAL PROTOTYPES):

Mẫu 1: So sánh chuỗi thời gian liên hoàn (TEMPORAL_COMPARISON - YoY / MoM):
```sql
WITH annual_metric AS (
    SELECT f.year_code AS year, SUM(NULLIF(TRIM(f.value), '')::numeric) AS metric_val
    FROM dwh_internal.fact_report_criteria f
    JOIN dwh_internal.criteria c ON f.criteria_id = c.id
    WHERE f.report_status = 'approved' AND f.tenant_code = :tenant_code AND c.code = :metric_code
      AND f.year_code IN ('2024', '2025', '2026')
    GROUP BY f.year_code
)
SELECT year, metric_val,
       LAG(metric_val) OVER (ORDER BY year ASC) AS prev_val,
       metric_val - LAG(metric_val) OVER (ORDER BY year ASC) AS delta_val,
       ROUND(((metric_val - LAG(metric_val) OVER (ORDER BY year ASC)) / NULLIF(LAG(metric_val) OVER (ORDER BY year ASC), 0)) * 100.0, 2) AS growth_pct
FROM annual_metric
ORDER BY year DESC;
```

Mẫu 2: Đối chuẩn ngang hàng đa thực thể (CROSS_ENTITY_COMPARISON):
```sql
SELECT COALESCE(o.office_name, f.department_code, 'Trực thuộc cơ quan chủ quản') AS ten_don_vi,
       SUM(NULLIF(TRIM(f.value), '')::numeric) AS tong_gia_tri,
       AVG(SUM(NULLIF(TRIM(f.value), '')::numeric)) OVER () AS trung_binh_nhom,
       SUM(NULLIF(TRIM(f.value), '')::numeric) - AVG(SUM(NULLIF(TRIM(f.value), '')::numeric)) OVER () AS chenh_lech_so_voi_tb
FROM dwh_internal.fact_report_criteria f
JOIN dwh_internal.criteria c ON f.criteria_id = c.id
LEFT JOIN dwh_internal.office o ON f.office_id = o.id
WHERE f.report_status = 'approved' AND f.tenant_code = :tenant_code AND f.year_code = :year AND c.code = :metric_code
GROUP BY o.office_name, f.department_code
ORDER BY tong_gia_tri DESC;
```

Mẫu 3: Xếp hạng phân vị Top-K (RANKING_TOP_K):
```sql
WITH ranked_entities AS (
    SELECT COALESCE(o.office_name, f.department_code) AS ten_don_vi,
           SUM(NULLIF(TRIM(f.value), '')::numeric) AS tong_gia_tri,
           DENSE_RANK() OVER (ORDER BY SUM(NULLIF(TRIM(f.value), '')::numeric) DESC) AS rank_pos,
           MAX(SUM(NULLIF(TRIM(f.value), '')::numeric)) OVER () - MIN(SUM(NULLIF(TRIM(f.value), '')::numeric)) OVER () AS khoang_bien_do
    FROM dwh_internal.fact_report_criteria f
    JOIN dwh_internal.criteria c ON f.criteria_id = c.id
    LEFT JOIN dwh_internal.office o ON f.office_id = o.id
    WHERE f.report_status = 'approved' AND f.tenant_code = :tenant_code AND f.year_code = :year AND c.code = :metric_code
    GROUP BY o.office_name, f.department_code
)
SELECT ten_don_vi, tong_gia_tri, rank_pos, khoang_bien_do
FROM ranked_entities
WHERE rank_pos <= :top_k
ORDER BY rank_pos ASC;
```

Mẫu 4: Tỷ trọng cấu phần trên tổng thể (PART_TO_WHOLE):
```sql
SELECT f.name AS ten_thanh_phan,
       SUM(NULLIF(TRIM(f.value), '')::numeric) AS gia_tri_thanh_phan,
       SUM(SUM(NULLIF(TRIM(f.value), '')::numeric)) OVER () AS tong_so_toan_tinh,
       ROUND((SUM(NULLIF(TRIM(f.value), '')::numeric) / NULLIF(SUM(SUM(NULLIF(TRIM(f.value), '')::numeric)) OVER (), 0)) * 100.0, 2) AS ty_trong_pct
FROM dwh_internal.fact_report_criteria f
WHERE f.report_status = 'approved' AND f.tenant_code = :tenant_code AND f.year_code = :year
GROUP BY f.name
ORDER BY gia_tri_thanh_phan DESC;
```

Mẫu 5: Ma trận phân tích chéo đa chiều (MULTI_DIMENSIONAL_PIVOT):
```sql
SELECT o.office_name AS ten_phong_ban,
       SUM(NULLIF(TRIM(f.value), '')::numeric) FILTER (WHERE f.year_code = '2025') AS nam_2025,
       SUM(NULLIF(TRIM(f.value), '')::numeric) FILTER (WHERE f.year_code = '2026') AS nam_2026,
       ROUND(((SUM(NULLIF(TRIM(f.value), '')::numeric) FILTER (WHERE f.year_code = '2026') -
               SUM(NULLIF(TRIM(f.value), '')::numeric) FILTER (WHERE f.year_code = '2025')) /
              NULLIF(SUM(NULLIF(TRIM(f.value), '')::numeric) FILTER (WHERE f.year_code = '2025'), 0)) * 100.0, 2) AS tang_truong_pct
FROM dwh_internal.fact_report_criteria f
JOIN dwh_internal.criteria c ON f.criteria_id = c.id
JOIN dwh_internal.office o ON f.office_id = o.id
WHERE f.report_status = 'approved' AND f.tenant_code = :tenant_code AND c.code = :metric_code
  AND f.year_code IN ('2025', '2026')
GROUP BY o.office_name
ORDER BY nam_2026 DESC;
```

---

### ĐỊNH DẠNG ĐẦU RA BẮT BUỘC (STRICT JSON MODE):
Bạn BẮT BUỘC xuất ra định dạng JSON khớp 100% schema `TextToSQLStructuredOutput`, không kèm bất kỳ giải thích nào bên ngoài khối JSON:
{
  "thought_scratchpad": "Bước 1: ... Bước 2: ... Bước 3: ... Bước 4: ...",
  "sql_query": "SELECT ...;",
  "tables_used": ["dwh_internal.fact_report_criteria", "dwh_internal.criteria"],
  "confidence_score": 0.95,
  "sql_ast_explanation": "Mô tả ngắn gọn về cấu trúc câu truy vấn..."
}
"""


def build_3tier_text_to_sql_prompt(
    catalog_pruned: CatalogPrunedDTO,
    router_output: RouterOutputDTO,
    security_context: UserSecurityContextDTO,
    negative_constraints: Optional[str] = None,
) -> str:
    """
    Xây dựng phần User Prompt chứa Tầng 2 (Schema Slice) và Tầng 3 (Dynamic Suffix).
    Kết hợp với STATIC_INVARIANT_PREFIX_PROMPT ở System Role để tối ưu hóa Prompt Caching.
    """
    # --------------------------------------------------------------------------
    # TẦNG 2: SEMI-STATIC SCHEMA SLICE (< 600 tokens)
    # --------------------------------------------------------------------------
    schema_parts = ["### LÁT CẮT LƯỢC ĐỒ CSDL (SCHEMA SLICE DDL & JOIN PATHS):"]
    
    if catalog_pruned.schema_slice_ddl:
        schema_parts.append(catalog_pruned.schema_slice_ddl.strip())
    else:
        # Fallback DDL cơ bản nếu catalog_pruned chưa có sẵn
        schema_parts.append("""-- Bảng Fact chính lưu trữ số liệu báo cáo
CREATE TABLE dwh_internal.fact_report_criteria (
    fact_sk TEXT PRIMARY KEY,
    year_code VARCHAR(4) NOT NULL,
    value TEXT, -- Chứa cả text và chuỗi rỗng! Bắt buộc dùng NULLIF(TRIM(value), '')::numeric
    code VARCHAR(128),
    name VARCHAR(255),
    report_status VARCHAR(32) NOT NULL, -- Chỉ truy vấn 'approved'
    tenant_code VARCHAR(64) NOT NULL,   -- Mã tỉnh (ví dụ: '68')
    department_code VARCHAR(64),        -- Mã Sở/Ngành (ví dụ: '68-1-02')
    office_id UUID,                     -- Phòng ban trực thuộc (Cấp Tỉnh có thể NULL!)
    criteria_id UUID
);

-- Bảng danh mục chỉ tiêu
CREATE TABLE dwh_internal.criteria (
    id UUID PRIMARY KEY,
    code VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    level INTEGER NOT NULL,
    parent_id UUID
);

-- Bảng danh mục cơ quan (deparment - lưu ý không có chữ t thứ hai; hiện có 0 bản ghi, ưu tiên dùng f.department_code)
CREATE TABLE dwh_internal.deparment (
    code VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    tenant_code VARCHAR NOT NULL,
    level INTEGER NOT NULL
);

-- Bảng danh mục phòng ban
CREATE TABLE dwh_internal.office (
    id UUID PRIMARY KEY,
    office_name VARCHAR NOT NULL,
    code VARCHAR,
    department_code VARCHAR NOT NULL,
    tenant_code VARCHAR NOT NULL
);

-- Bảng báo cáo tiến độ và trạng thái phê duyệt
CREATE TABLE dwh_internal.report (
    id UUID PRIMARY KEY,
    status VARCHAR(32) NOT NULL, -- 'approved', 'draft', 'pending', 'rejected'
    year_code VARCHAR(4) NOT NULL,
    department_code VARCHAR(64) NOT NULL,
    tenant_code VARCHAR(64) NOT NULL,
    report_date TIMESTAMP,
    deleted_date TIMESTAMP
);

-- Bảng danh mục biểu mẫu thu thập số liệu
CREATE TABLE dwh_internal.collection_form (
    id UUID PRIMARY KEY,
    code VARCHAR(128) NOT NULL,
    name VARCHAR(255) NOT NULL,
    year_code VARCHAR(4) NOT NULL,
    status VARCHAR(32),
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    tenant_code VARCHAR(64),
    deleted_date TIMESTAMP
);

-- Bảng phân công nhiệm vụ cán bộ
CREATE TABLE dwh_internal.user_mission (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    mission_id UUID NOT NULL,
    mission_name VARCHAR NOT NULL,
    tenant_code VARCHAR NOT NULL,
    deleted_date TIMESTAMP
);

-- Bảng người dùng / cán bộ
CREATE TABLE dwh_internal."user" (
    id UUID PRIMARY KEY,
    name VARCHAR NOT NULL,
    position VARCHAR,
    tenant_code VARCHAR NOT NULL,
    deleted_at TIMESTAMP
);""")

    # Bổ sung các đường dẫn JOIN được Steiner Tree gợi ý
    if catalog_pruned.join_paths:
        schema_parts.append("\n-- CÁC QUAN HỆ JOIN GỢI Ý TỪ STEINER TREE:")
        for jp in catalog_pruned.join_paths:
            schema_parts.append(f"-- {jp.source_table} {jp.join_type} {jp.target_table} ON {jp.on_clause}")

    # Bổ sung các hợp đồng nghiệp vụ
    if catalog_pruned.data_contracts:
        schema_parts.append("\n-- CÁC QUY TẮC RÀNG BUỘC CỦA LƯỢC ĐỒ:")
        for dc in catalog_pruned.data_contracts:
            schema_parts.append(f"-- * {dc}")

    tier2_text = "\n".join(schema_parts)

    # --------------------------------------------------------------------------
    # TẦNG 3: DYNAMIC SUFFIX (Đuôi động ở cuối cùng)
    # --------------------------------------------------------------------------
    suffix_parts = ["\n### NGỮ CẢNH TRUY VẤN VÀ CÂU HỎI THỰC TẾ:"]

    # 1. Ngữ cảnh phân quyền HBAC
    suffix_parts.append(f"- NGƯỜI DÙNG: {security_context.username} (Role Level: {security_context.role_level})")
    suffix_parts.append(f"- TENANT CODE BẮT BUỘC: '{security_context.tenant_code}'")
    if security_context.department_code:
        suffix_parts.append(f"- DEPARTMENT CODE: '{security_context.department_code}'")
    if security_context.office_id and security_context.role_level >= 2:
        suffix_parts.append(f"- OFFICE ID: '{security_context.office_id}'")

    # 2. Ngữ cảnh định tuyến từ Router (H-DFT slots)
    if router_output.dag_archetype:
        suffix_parts.append(f"- KIMBALL ARCHETYPE ĐỀ XUẤT: {router_output.dag_archetype}")
    if getattr(router_output, "active_quest", None):
        quest = router_output.active_quest
        if quest.metric_code:
            suffix_parts.append(f"- CHỈ TIÊU TRÍCH XUẤT: {quest.metric_code}")
        if quest.temporal_val:
            suffix_parts.append(f"- MỐC THỜI GIAN CHUẨN HÓA TRONG KHO: BẮT BUỘC DÙNG `year_code = '{quest.temporal_val}'` TRONG MỆNH ĐỀ WHERE (KHO DỮ LIỆU HIỆN HÀNH LƯU TRỮ SỐ LIỆU NĂM {quest.temporal_val})")
        if quest.admin_entity:
            suffix_parts.append(f"- ĐƠN VỊ TRÍCH XUẤT: {quest.admin_entity}")

    # 3. Ràng buộc phủ định tiêm từ Redis Error Cache (nếu có)
    if negative_constraints:
        suffix_parts.append(f"\n⚠️ RÀNG BUỘC PHỦ ĐỊNH CẦN TRÁNH (TỪ LỖI RUNTIME TRƯỚC ĐÓ):\n{negative_constraints}")

    # 4. Câu hỏi thực tế của người dùng
    raw_query = router_output.query_sanitized or ""
    suffix_parts.append(f"\nCÂU HỎI CỦA NGƯỜI DÙNG:\n\"{raw_query}\"")
    suffix_parts.append("\nHãy xuất suy luận 4 bước trong `thought_scratchpad` và câu SELECT SQL hợp lệ trong `sql_query` theo đúng JSON schema.")

    tier3_text = "\n".join(suffix_parts)

    return f"{tier2_text}\n{tier3_text}"
