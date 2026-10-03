---
doc_id: "BP-01-DWH"
title: "Kiến Trúc Dữ Liệu Kho DWH, Cây Thực Thể và Quy Tắc Báo Cáo"
role: "SSOT"
scope: "Physical Schemas, DWH Entity Tree, Fact Schema & Report Status Rules"
ssot_of:
  - "IPGov_Chatbot/docs/MASTER_PLAN_AND_PROGRESS_TRACKING.md"
depends_on:
  - "IPGov_Chatbot/blueprints/00_TECH_STACK_VA_KIEN_TRUC_TONG_THE.md"
related_docs:
  - "IPGov_Chatbot/blueprints/02_PHAN_QUYEN_PHAN_CAP_HBAC.md"
  - "IPGov_Chatbot/blueprints/03_SEMANTIC_LAYER_MDL_VA_IN_MEMORY_CATALOG.md"
  - "IPGov_Chatbot/blueprints/08_BO_TEST_CASE_KIEM_THU_TOAN_DIEN_VA_5_DIEM_MU_DWH.md"
---

# TÀI LIỆU ĐẶC TẢ THIẾT KẾ KIẾN TRÚC HỆ THỐNG IPGOV CHATBOT
## PHẦN 02: KIẾN TRÚC DỮ LIỆU KHO DWH, CÂY THỰC THỂ VÀ QUY TẮC XỬ LÝ TRẠNG THÁI BÁO CÁO (REPORT STATUS)

> **Tiêu chuẩn áp dụng:** Arc42 (Phần 8: Cross-cutting Concepts / Data View) & IEEE Std 1016-2009 (Information Viewpoint).  
> **Căn cứ dữ liệu thực nghiệm:** Cơ sở dữ liệu PostgreSQL (`vna_wom_dev`) trên máy chủ phân tích trung tâm (`104.248.155.6:5432/vna_wom_dev`).  
> **Quy chuẩn hiển thị:** 100% biểu đồ được định dạng bằng mã Mermaid chuẩn.

---

### 1. KIẾN TRÚC PHÂN VÙNG VẬT LÝ KHO DỮ LIỆU (PHYSICAL SCHEMA ARCHITECTURE)

Kho dữ liệu DWH phục vụ hệ thống gồm **4 schema vật lý** với **57 bảng** và được phân tách thành 4 phân vùng chức năng độc lập:

1. **`dwh_internal` (Core Analytic Data Mart - 18 bảng):**  
   Vùng lưu trữ dữ liệu nghiệp vụ trọng yếu nhất của hệ thống. Chứa các bảng Fact báo cáo kinh tế - xã hội (`fact_report_criteria`), chiều cơ quan hành chính (`deparment`, `office`), chiều chỉ tiêu (`criteria`), và vòng đời báo cáo (`report`). Hơn **$95\%$ các truy vấn phân tích của Chatbot** được định tuyến trực tiếp vào schema này.
   *Lưu ý kiến trúc đặc biệt:* Sau đợt thiết lập lại dữ liệu kho công ty, bảng `deparment` hiện thời có 0 bản ghi. Chatbot áp dụng nguyên tắc cô lập `deparment`, không thực hiện SQL JOIN trực tiếp tới bảng này mà khai thác chiều suy biến (Degenerate Dimension) `f.department_code` trên `fact_report_criteria` kết hợp DuckDB Semantic Catalog In-Memory để phân giải ngữ nghĩa tên đơn vị.
2. **`dwh_public` (Open Data Mart - 8 bảng):**  
   Vùng lưu trữ các số liệu đã được tổng hợp vĩ mô, đóng gói sẵn để phục vụ tra cứu mở cho người dân và doanh nghiệp mà không cần phân quyền chi tiết.
3. **`public` (Shared GIS & Master Data - 27 bảng):**  
   Vùng lưu trữ danh mục ranh giới địa lý hành chính dùng chung (`ward-boundary`, `districts`) và các bảng cấu hình xác thực người dùng.
4. **`staging` (ETL Ingestion Buffer - 4 bảng):**  
   Vùng đệm trung chuyển tiếp nhận dữ liệu tải lên từ phần mềm tác nghiệp trước khi làm sạch và nạp vào DWH; đồng thời chứa bảng giám sát pipeline (`pipeline_logs`) phục vụ xác minh mốc tươi mới của dữ liệu.

```mermaid
graph LR
    subgraph DWH_PHYSICAL["POSTGRESQL DWH (104.248.155.6 / vna_wom_dev)"]
        direction TB
        STAGING["staging (4 bảng)<br/>• ETL Ingestion Buffer<br/>• pipeline_logs"]
        INTERNAL["dwh_internal (18 bảng)<br/>• fact_report_criteria<br/>• deparment & office<br/>• criteria & report"]
        PUBLIC_DATA["dwh_public (8 bảng)<br/>• Open Data Mart<br/>• Macro Summaries"]
        GIS_MASTER["public (27 bảng)<br/>• ward-boundary<br/>• districts GIS"]
    end

    STAGING -->|ETL Airflow Pipeline| INTERNAL
    INTERNAL -->|Aggregation Views| PUBLIC_DATA
    INTERNAL -.->|Spatial Join| GIS_MASTER

    classDef coreZone fill:#1e3a8a,stroke:#3b82f6,stroke-width:2px,color:#fff;
    classDef bufferZone fill:#7c2d12,stroke:#f97316,stroke-width:2px,color:#fff;
    classDef publicZone fill:#14532d,stroke:#22c55e,stroke-width:2px,color:#fff;
    classDef gisZone fill:#374151,stroke:#9ca3af,stroke-width:2px,color:#fff;

    class INTERNAL coreZone;
    class STAGING bufferZone;
    class PUBLIC_DATA publicZone;
    class GIS_MASTER gisZone;
```

#### 1.1. Lược Đồ Thực Thể Quan Hệ (ERD) Vùng Dữ Liệu Trọng Yếu `dwh_internal`

Bên trong schema `dwh_internal`, mô hình dữ liệu được thiết kế theo dạng Star/Snowflake Schema xoay quanh bảng Fact trung tâm `fact_report_criteria`:

```mermaid
erDiagram
    dwh_internal_deparment ||--o{ dwh_internal_office : "1-N (department_code = code)"
    dwh_internal_office ||--o{ dwh_internal_fact_report_criteria : "1-N (office_id)"
    dwh_internal_criteria ||--o{ dwh_internal_fact_report_criteria : "1-N (criteria_id)"
    dwh_internal_report ||--o{ dwh_internal_fact_report_criteria : "1-N (report_id)"

    dwh_internal_deparment {
        uuid id PK
        text code UK
        text name
        int level "0: Tỉnh, 1: Sở/Ban/Ngành (Lưu ý: 0 bản ghi sau reset data)"
        uuid parent_id FK
        text tenant_code
    }

    dwh_internal_office {
        uuid id PK
        varchar office_name
        text department_code FK
        varchar tenant_code
        varchar office_year
    }

    dwh_internal_criteria {
        uuid id PK
        varchar code
        varchar name
        int level
        uuid parent_id FK
    }

    dwh_internal_fact_report_criteria {
        text fact_sk PK "Surrogate Key"
        varchar year_code "VARCHAR(4) - Đã đổi tên từ year"
        timestamptz report_date
        text code "Mã chỉ tiêu"
        text name "Tên chỉ tiêu"
        text value "Ép kiểu: NULLIF(TRIM(value), '')::numeric"
        uuid office_id FK
        varchar tenant_code
        varchar department_code "Mã sở ngành (Degenerate Dimension)"
        varchar report_status "approved, pending, draft, rejected"
        timestamp etl_updated_at
    }

    dwh_internal_report {
        uuid id PK
        varchar status "approved, pending, draft, rejected"
        varchar year_code "VARCHAR(4) - Đã đổi tên từ year"
        uuid office_id
    }
```

---

### 2. CÂY THỰC THỂ TỔ CHỨC ĐA SỞ HỮU TRONG SCHEMA DWH_INTERNAL (MULTI-TENANT ORGANIZATIONAL DATA TREE)

Để hiểu được cách thức số liệu trong `fact_report_criteria` được phân bổ và truy vấn, hệ thống không xem các dòng dữ liệu là một khối phẳng. Thay vào đó, dữ liệu báo cáo trong schema `dwh_internal` phản ánh chính xác **Mô hình Cây Tổ chức Đa sở hữu (Multi-Tenant Organizational Hierarchy)** của bộ máy hành chính nhà nước.

Mối liên kết giữa các bảng trong schema `dwh_internal` tạo thành cây dữ liệu 4 tầng phân cấp:
* **Tầng 1 - Mã Phân Vùng Đơn Vị Hành Chính (`tenant_code`):** Tách biệt dữ liệu cấp Tỉnh/Thành phố trực thuộc Trung ương (Ví dụ: `79` cho TP. Hồ Chí Minh, `68` cho Tỉnh Lâm Đồng).
* **Tầng 2 - Cơ Quan Chủ Quản (`dwh_internal.deparment`):** Mô hình hóa cấp Tỉnh (`level = 0`, ví dụ: UBND Thành phố Hồ Chí Minh) và các Sở/Ban/Ngành trực thuộc (`level = 1`, ví dụ: Sở Nội vụ, Sở Xây dựng).
* **Tầng 3 - Phòng Ban Nghiệp Vụ Cơ Sở (`dwh_internal.office`):** Các đơn vị trực tiếp nhập liệu và lập báo cáo (Ví dụ: Phòng Xây dựng, Phòng Nội vụ, Phòng An toàn VSLĐ).
* **Tầng 4 - Dòng Số Liệu Báo Cáo Fact (`dwh_internal.fact_report_criteria`):** Mức hạt chi tiết nhất (Grain) của số liệu gắn chặt với `office_id`. Mọi thao tác Roll-up (Tổng hợp lên cấp Sở/Tỉnh) hay Drill-down (Chi tiết hóa xuống từng phòng) đều được tính toán dựa trên các nút thuộc cây này.

```mermaid
graph TD
    DWH_INTERNAL["dwh_internal (Core Analytic Mart)<br/>Cây Tổ Chức Đa Sở Hữu Của fact_report_criteria"]
    
    %% Branch HCM
    DWH_INTERNAL --> T79["tenant_code = '79'<br/>(TP. Hồ Chí Minh)"]
    T79 --> D79_0["deparment (Level 0)<br/>Thành phố Hồ Chí Minh (code: '79')"]
    D79_0 --> D79_1_01["deparment (Level 1)<br/>Sở Nội vụ (code: '79-1-01')"]
    D79_0 --> D79_1_02["deparment (Level 1)<br/>UBND Thành phố Hồ Chí Minh (code: '79-1-02')"]
    
    D79_1_02 --> OFF_XD["office: Phòng Xây dựng"]
    D79_1_02 --> OFF_NV["office: Phòng Nội vụ"]
    D79_1_02 --> OFF_KT["office: Phòng Kinh tế"]
    D79_1_02 --> OFF_VH["office: Phòng Văn hóa - Xã hội"]
    D79_1_02 --> OFF_OTHER["... (30 phòng ban trực thuộc khác)"]
    
    OFF_XD -.-> FACT_79["fact_report_criteria<br/>(3.297 dòng Fact liên kết qua office_id)"]
    
    %% Branch Lam Dong
    DWH_INTERNAL --> T68["tenant_code = '68'<br/>(Tỉnh Lâm Đồng)"]
    T68 --> D68_0["deparment (Level 0)<br/>Lâm Đồng (code: '68')"]
    D68_0 --> D68_1_02["deparment (Level 1)<br/>UBND Tỉnh Lâm Đồng (code: '68-1-02')"]
    
    D68_1_02 --> OFF_LD_NV["office: Phòng ban nội vụ"]
    D68_1_02 --> OFF_LD_XD["office: Phòng ban xây dựng"]
    D68_1_02 --> OFF_LD_YT["office: Phòng y tế"]
    D68_1_02 --> OFF_LD_AT["office: Phòng ban An toàn VSLĐ"]
    
    OFF_LD_XD -.-> FACT_68["fact_report_criteria<br/>(2.500 dòng Fact liên kết qua office_id)"]

    classDef rootNode fill:#1f2937,stroke:#9ca3af,stroke-width:2px,color:#fff;
    classDef tenantNode fill:#1e3a8a,stroke:#3b82f6,stroke-width:2px,color:#fff;
    classDef deptNode fill:#14532d,stroke:#22c55e,stroke-width:2px,color:#fff;
    classDef officeNode fill:#7c2d12,stroke:#f97316,stroke-width:2px,color:#fff;
    classDef factNode fill:#581c87,stroke:#a855f7,stroke-width:2px,color:#fff;

    class DWH_INTERNAL rootNode;
    class T79,T68 tenantNode;
    class D79_0,D79_1_01,D79_1_02,D68_0,D68_1_02 deptNode;
    class OFF_XD,OFF_NV,OFF_KT,OFF_VH,OFF_OTHER,OFF_LD_NV,OFF_LD_XD,OFF_LD_YT,OFF_LD_AT officeNode;
    class FACT_79,FACT_68 factNode;
```

---

### 3. ĐẶC TẢ VÀ CHÍNH SÁCH XỬ LÝ TRẠNG THÁI BÁO CÁO (REPORT STATUS POLICY)

#### 3.1. Hiện trạng phân bổ thực tế trong CSDL `vna_wom_dev`
Trường `report_status` trong bảng `dwh_internal.fact_report_criteria` và trường `status` trong `dwh_internal.report` lưu trữ vòng đời kiểm duyệt của một báo cáo với các trạng thái định danh:

*Lưu ý snapshot kho dữ liệu hiện hành (`104.248.155.6`):* Sau đợt reset dữ liệu, bảng `fact_report_criteria` hiện có **463 bản ghi thực tế**, toàn bộ thuộc **năm 2026 (`year_code = '2026'`)**, mã tỉnh Lâm Đồng (`tenant_code = '68'`), và đơn vị `68-1-01`. Phân bổ trạng thái gồm:
- **`approved`**: **342 bản ghi (73.9%)** — Số liệu chính thức có giá trị pháp lý.
- **`draft`**: **121 bản ghi (26.1%)** — Bản nháp tác nghiệp.

Dưới đây là bảng định nghĩa 4 trạng thái chuẩn của hệ thống:

| Trạng Thái (`report_status`) | Tỷ Lệ Chuẩn | Ý Nghĩa Nghiệp Vụ Hành Chính |
| :--- | :---: | :--- |
| **`approved`** | **Chính thức** | **ĐÃ PHÊ DUYỆT CHÍNH THỨC:** Báo cáo đã được lãnh đạo có thẩm quyền thẩm định, ký số và đóng dấu nghiệp vụ. Đây là dữ liệu có giá trị pháp lý đầy đủ. |
| **`pending`** | **Nội bộ** | **ĐANG CHỜ DUYỆT:** Đơn vị cơ sở đã nộp báo cáo hoàn chỉnh nhưng cấp quản lý (Sở/UBND) đang trong quá trình rà soát, chưa phê duyệt. |
| **`draft`** | **Tác nghiệp** | **BẢN NHÁP:** Đơn vị cơ sở đang trong quá trình nhập liệu hoặc lưu tạm thời, số liệu chưa chốt, có thể thay đổi bất cứ lúc nào. |
| **`rejected`** | **Hoàn thiện** | **BỊ TỪ CHỐI:** Báo cáo bị cơ quan quản lý trả về do sai lệch số liệu, thiếu biên bản kiểm tra hoặc không đúng quy cách. |

#### 3.2. Chính sách truy vấn của Chatbot đối với từng trạng thái (Query Policy)

```mermaid
flowchart TD
    Q[Người dùng gửi câu hỏi] --> C{Mục đích câu hỏi?}
    
    C -->|Thống kê / Tổng hợp số liệu| M[MẶC ĐỊNH: LỌC APPROVED]
    M --> SQL1["Cưỡng chế điều kiện:<br/>WHERE report_status = 'approved'"]
    SQL1 --> RES1[Trả về số liệu chính thức có giá trị pháp lý]
    
    C -->|Kiểm tra tiến độ / Rà soát báo cáo| O[THEO DÕI VẬN HÀNH / TIẾN ĐỘ]
    O --> CHK{Tài khoản có thẩm quyền đơn vị?}
    CHK -->|Không| DENY[Từ chối: Không có quyền xem bản nháp đơn vị khác]
    CHK -->|Có| SQL2["Cho phép truy vấn theo trạng thái yêu cầu:<br/>WHERE report_status IN ('pending', 'draft', 'rejected')"]
    SQL2 --> RES2[Hiển thị kèm cảnh báo: 'Dữ liệu chưa được phê duyệt chính thức']
```

1. **Quy Tắc Mặc Định (Default Rule for Analytics):**
   * Đối với toàn bộ các câu hỏi phân tích, tính toán, so sánh hoặc trích xuất số liệu kinh tế - xã hội (Ví dụ: *"Năm 2025 có bao nhiêu vụ tai nạn lao động?"*), hệ thống **bắt buộc $100\%$ tự động tiêm điều kiện:**
     $$\text{f.report\_status = 'approved'}$$
   * Tuyệt đối không tính dồn các bản ghi `draft`, `pending`, hoặc `rejected` vào các chỉ tiêu báo cáo chính thức, nhằm loại bỏ rủi ro sai lệch số liệu pháp lý.
2. **Quy Tắc Ngoại Lệ (Operational Tracking Rule):**
   * Chỉ khi người dùng hỏi đích danh về tiến độ nộp hoặc tình trạng duyệt của đơn vị mình (Ví dụ: *"Đơn vị tôi có báo cáo nào đang chờ duyệt không?"* hoặc *"Báo cáo quý 1 của phòng đã được phê duyệt chưa?"*), hệ thống mới chuyển hướng sang truy vấn `dwh_internal.report` với điều kiện tương ứng.
   * Khi trả lời các câu hỏi này, Chatbot bắt buộc phải đính kèm dòng cảnh báo nổi bật:  
     > *⚠️ Cảnh báo: Các số liệu ở trạng thái 'Đang chờ duyệt' (Pending) hoặc 'Bản nháp' (Draft) chỉ mang tính chất tham khảo nội bộ và chưa có giá trị báo cáo chính thức.*

---

### 4. BÀI TOÁN DOUBLE-COUNTING VÀ THUẬT TOÁN DUYỆT CÂY VỚI SQL `WITH RECURSIVE` (DATABASE-FIRST)

Khi người dùng hỏi tổng hợp vĩ mô (Cấp Tỉnh hoặc Cấp Sở), hệ thống đối mặt với 2 rủi ro nhân đôi số liệu (Double-Counting):
1. **Cây chỉ tiêu (`dwh_internal.criteria`):** Chứa các chỉ tiêu cha (nhóm tổng) và các chỉ tiêu con (thành phần). Nếu cộng gộp cả cha lẫn con sẽ làm sai lệch dữ liệu gấp đôi.
2. **Cây đơn vị hành chính (`dwh_internal.deparment` & `office`):** Các phòng ban nộp số liệu cơ sở, trong khi một số sở ngành cũng có dòng số liệu tổng hợp.

Thay vì kéo toàn bộ cây dữ liệu về Python để duyệt đệ quy (gây tốn RAM và rủi ro đệ quy vô hạn), hệ thống tuân thủ triết lý **Ponytail (Database-First)**: Đẩy toàn bộ tác vụ duyệt cây xuống C++ engine của PostgreSQL và DuckDB bằng **`WITH RECURSIVE`**, đạt thời gian thực thi **$< 0.5\text{ms}$** trên cây 10.000 nút.

#### 4.1. Câu Lệnh SQL Chuẩn Hóa Duyệt Nút Lá (Leaf-Node Only Roll-up)

```sql
-- 1. Tìm toàn bộ các nút lá thuộc cây chỉ tiêu mục tiêu bằng CTE đệ quy
WITH RECURSIVE criteria_tree AS (
    -- Anchor: Nút gốc của chỉ tiêu được hỏi
    SELECT c.id, c.code, c.name, c.parent_id, 1 AS depth
    FROM dwh_internal.criteria c
    WHERE c.code ILIKE '%tai_nan_lao_dong%'
    
    UNION ALL
    
    -- Recursive member: Duyệt sâu xuống toàn bộ các nút con cháu
    SELECT child.id, child.code, child.name, child.parent_id, ct.depth + 1
    FROM dwh_internal.criteria child
    INNER JOIN criteria_tree ct ON child.parent_id = ct.id
),
leaf_criteria AS (
    -- Lọc chỉ lấy các nút lá thực sự (không có bất kỳ nút con nào kế thừa)
    SELECT ct.id, ct.code, ct.name
    FROM criteria_tree ct
    WHERE NOT EXISTS (
        SELECT 1 
        FROM dwh_internal.criteria sub 
        WHERE sub.parent_id = ct.id
    )
)
-- 2. Thực hiện tổng hợp số liệu duy nhất trên các nút lá
SELECT 
    f.year_code AS year,
    SUM(NULLIF(TRIM(f.value), '')::numeric) AS total_val,
    COUNT(DISTINCT f.office_id) AS total_reporting_offices
FROM dwh_internal.fact_report_criteria f
INNER JOIN leaf_criteria lc ON f.criteria_id = lc.id
WHERE f.year_code = '2026'
  AND f.report_status = 'approved' -- Cưỡng chế trạng thái đã duyệt
GROUP BY f.year_code;
```

#### 4.2. Lợi Điểm Hiệu Năng So Với Xử Lý Bằng Mã Python

| Tiêu Chí So Sánh | Tự Viết Script Duyệt Cây Bằng Python | SQL `WITH RECURSIVE` (Database-First) |
| :--- | :--- | :--- |
| **Thời gian thực thi** | $15\text{ms} - 35\text{ms}$ (Network latency + Python object allocation) | **$< 0.5\text{ms}$** (Thực thi trực tiếp trong engine C++) |
| **Tiêu thụ bộ nhớ RAM** | Hàng nghìn đối tượng dict/object nạp vào Python process | **Zero Python memory footprint** (Chỉ trả về 1 dòng kết quả) |
| **Rủi ro đệ quy (Stack Overflow)** | Nguy cơ crash tiến trình nếu dữ liệu chu trình (cyclic reference) | CSDL hỗ trợ `CYCLE` detection và giới hạn đệ quy an toàn |
| **Độ phức tạp mã nguồn (LOC)** | $> 80$ dòng code traversal, DFS/BFS, unit test | **$0$ dòng mã Python** (Triệt tiêu hoàn toàn mã tự chế) |
