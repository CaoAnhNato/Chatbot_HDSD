---
doc_id: "BP-INDEX"
title: "Bản Đồ Kiến Trúc Hệ Thống (System Design Blueprints Index)"
role: "SSOT_INDEX"
scope: "System Architecture, Design Specifications & Taxonomy"
ssot_of:
  - "IPGov_Chatbot/docs/MASTER_PLAN_AND_PROGRESS_TRACKING.md"
depends_on: []
related_docs:
  - "IPGov_Chatbot/blueprints/00_TECH_STACK_VA_KIEN_TRUC_TONG_THE.md"
  - "IPGov_Chatbot/blueprints/01_DATA_WAREHOUSE_VA_CAY_THUC_THE_DWH.md"
  - "IPGov_Chatbot/blueprints/05_MULTI_AGENT_WORKFLOW_DIN_MAC_SQL.md"
  - "IPGov_Chatbot/blueprints/08_BO_TEST_CASE_KIEM_THU_TOAN_DIEN_VA_5_DIEM_MU_DWH.md"
  - "IPGov_Chatbot/docs/BACKEND_RUN_GUIDE.md"
---

# HỆ THỐNG TÀI LIỆU THIẾT KẾ KIẾN TRÚC IPGOV CHATBOT
## BỘ BẢN VẼ THIẾT KẾ HỆ THỐNG (SYSTEM DESIGN BLUEPRINTS)

> **Dự án:** Hệ thống Trợ lý ảo Tra cứu Dữ liệu Kho DWH Chính phủ điện tử (`IPGov_Chatbot`)  
> **Cơ sở dữ liệu thực tế:** PostgreSQL DWH `vna_wom_dev` (Docker `localhost:5432`)  
> **Chuẩn mực tuân thủ:** Arc42 Architectural Template, IEEE Std 1016-2009 (Software Design Descriptions), C4 Model, và O'Reilly Agentic Architectural Patterns (2026).

---

### 1. TỔNG QUAN VÀ BẢN ĐỒ TRA CỨU BLUEPRINT (BLUEPRINT NAVIGATION MAP)

Toàn bộ tài liệu thiết kế hệ thống được tổ chức nhất quán, liền mạch từ bối cảnh kinh doanh, ngăn xếp công nghệ, kiến trúc dữ liệu, cơ chế phân quyền, tầng ngữ nghĩa, hàng rào bảo mật, quy trình điều phối Multi-Agent đến giao diện người dùng và hệ thống quan sát:

| Số Thứ Tự | Tên Tài Liệu Bản Vẽ Thiết Kế | Tiêu Chuẩn Áp Dụng | Nội Dung Kỹ Thuật Trọng Tâm |
| :---: | :--- | :--- | :--- |
| **00** | [00_OVERVIEW_VA_BAI_HOC_THAT_BAI_GOVGRAPH.md](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/blueprints/00_OVERVIEW_VA_BAI_HOC_THAT_BAI_GOVGRAPH.md) | Arc42 Sec 1, 2, 3<br>IEEE Context View | Bối cảnh DWH công, phân tích 6 nguyên nhân thất bại cốt lõi của `GovGraph`, định nghĩa NFRs và Error Budget theo chuẩn Spider/BIRD. |
| **00-Tech**| [00_TECH_STACK_VA_KIEN_TRUC_TONG_THE.md](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/blueprints/00_TECH_STACK_VA_KIEN_TRUC_TONG_THE.md) | Arc42 Sec 4, 7<br>C4 Level 2 Container | Ngăn xếp kỹ thuật tinh giản: FastAPI, LangGraph, OpenRouter Gated LLM Gateway (`gemini-2.5-flash-lite` P0 + `gemini-3.8-flash` P1 Gated Fallback với Ponytail helper `call_structured_with_fallback`), Redis (`ipgov-redis`) Distributed Session Store, SQLGlot, DuckDB In-Memory, RapidFuzz, asyncpg, Pydantic v2, Jinja2, PostgreSQL 16; kèm **4 Nguyên Tắc Kiến Trúc Tinh Giản Ponytail** (Zero-Extra-Services, Database-First, Stdlib Over Custom Boilerplate, YAGNI). |
| **01** | [01_DATA_WAREHOUSE_VA_CAY_THUC_THE_DWH.md](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/blueprints/01_DATA_WAREHOUSE_VA_CAY_THUC_THE_DWH.md) | Arc42 Sec 8<br>IEEE Information View | Kiến trúc 4 schema vật lý `vna_wom_dev`, Cây tổ chức đa sở hữu của `fact_report_criteria` (Tỉnh $\to$ Sở $\to$ Phòng $\to$ Dòng Fact), **Thuật toán SQL `WITH RECURSIVE` (< 0.5ms)** chống double-counting và chính sách mặc định lọc `report_status = 'approved'`. |
| **02** | [02_PHAN_QUYEN_PHAN_CAP_HBAC.md](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/blueprints/02_PHAN_QUYEN_PHAN_CAP_HBAC.md) | Arc42 Sec 9<br>IEEE Security View | Mô hình phân quyền phân cấp hình cây (Tree HBAC): Cấp tỉnh $\to$ Cấp sở $\to$ Cấp phòng. Logic vị từ phạm vi (Scope Predicate Logic). |
| **03** | [03_SEMANTIC_LAYER_MDL_VA_IN_MEMORY_CATALOG.md](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/blueprints/03_SEMANTIC_LAYER_MDL_VA_IN_MEMORY_CATALOG.md) | Arc42 Sec 5<br>C4 Component View | Tầng ngữ nghĩa In-Memory Semantic Model, DuckDB DDL Catalog tra cứu siêu dữ liệu $<2\text{ms}$ với ART Index, Chiến lược đồng bộ 3 tầng (Cold-start, Webhook, 5-phút Polling), Tự khám phá năng lực, Bảng đăng ký `INDICATOR_SENSITIVITY_REGISTRY`, **Bộ biên dịch Hybrid Semantic AST Compiler**, và **Kỹ thuật Đẩy Tính toán Thống kê Xuống Database (SQL Window Functions Push-Down)**. |
| **04** | [04_SECURITY_GUARDRAILS_VA_AST_ENFORCEMENT.md](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/blueprints/04_SECURITY_GUARDRAILS_VA_AST_ENFORCEMENT.md) | Arc42 Sec 9<br>Cross-cutting Security | 5 tầng kiểm soát an toàn AST bằng SQLGlot, Whitelist bảng, và **Thuật toán Duyệt Phạm vi Đệ quy (Recursive Scope Visitor)** tiêm bộ lọc phân quyền HBAC chính xác vào các CTE và Subquery lồng nhau mà không làm hỏng cú pháp SQL gốc. |
| **05** | [05_MULTI_AGENT_WORKFLOW_DIN_MAC_SQL.md](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/blueprints/05_MULTI_AGENT_WORKFLOW_DIN_MAC_SQL.md) | Arc42 Sec 5, 6<br>O'Reilly Agent Patterns | **Sơ đồ LangGraph StateGraph 3 Node Tinh Giản (YAGNI - Triệt tiêu Agent Bloat)**, OpenRouter Gated 2-Stage Router (`gemini-2.5-flash-lite` + `gemini-3.8-flash` Gated Fallback với Ponytail helper `call_structured_with_fallback`), **Redis Distributed Session Memory Pipeline (Dual-Context, LTRIM Sliding Window, Decision Cache < 50ms)**, Khung Phân Tích Đa Hình (5 Kimball Archetypes), Động cơ Thống kê Cổng Lọc Kép (Dual-Gate Gating), và **Động cơ Render `JinjaSlotEngine` trong RAM ($< 0.05\text{ms}$)**. |
| **06** | [06_OBSERVABILITY_TRACING_DLQ_VA_EVALUATION.md](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/blueprints/06_OBSERVABILITY_TRACING_DLQ_VA_EVALUATION.md) | Arc42 Sec 10, 11<br>IEEE Quality View | Hệ thống phân tán Tracing với Langfuse/OpenTelemetry, bảng lưu trữ lỗi Dead-Letter-Queue (DLQ), bộ chỉ số đánh giá Spider/BIRD và ma trận FMEA. |
| **07** | [07_ADVANCED_REASONING_PROVENANCE_AND_STREAMING_UX.md](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/blueprints/07_ADVANCED_REASONING_PROVENANCE_AND_STREAMING_UX.md) | Arc42 Sec 6, 7<br>C4 Presentation View | Giao thức Server-Sent Events (SSE) 10 sự kiện tiến trình suy luận, hợp đồng dữ liệu Dấu vết Nguồn gốc chứng cứ (`LineageBadgeDTO`), cơ chế phản hồi Fast-track SSE, Progressive Hybrid UX, **Khung tối ưu độ trễ Track B qua Polymorphic Speculative Overlap và Jinja2 render**, và **Mã mẫu Client SSE Streaming Parser React/TypeScript** (`useChatStream.ts` kèm Popover/Drawer component). |
| **08** | [08_BO_TEST_CASE_KIEM_THU_TOAN_DIEN_VA_5_DIEM_MU_DWH.md](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/blueprints/08_BO_TEST_CASE_KIEM_THU_TOAN_DIEN_VA_5_DIEM_MU_DWH.md) | Arc42 Sec 11<br>IEEE Verification View | Bộ tiêu chuẩn kiểm thử 24 Test Cases và Đặc tả Độ phủ Kiểm thử Chatbot qua 4 Phân hệ (Kỹ thuật DWH, Hội thoại Đa lượt H-DFT & Redis Session Memory, Nghiệp vụ Công vụ, và Bảo mật Đối kháng Red-team). |

---

### 2. TỔNG QUAN NĂNG LỰC NGHIỆP VỤ VÀ CÁC DẠNG CÂU HỎI HỆ THỐNG XỬ LÝ (SUPPORTED QUESTION TAXONOMY & CAPABILITIES)

Dựa trên kết quả khảo sát và phân tích thực nghiệm chuyên sâu (**Exploratory Data Analysis - EDA**) trên cơ sở dữ liệu kho DWH `vna_wom_dev`, hệ thống được thiết kế để xử lý toàn diện các bài toán tra cứu, tổng hợp, đối chuẩn và phân tích dữ liệu công vụ.

#### 2.1. Bản Đồ Không Gian Dữ Liệu Thực Tế (EDA Grounded Reality)

Khảo sát thực tế trên schema `dwh_internal` ghi nhận kho dữ liệu hiện hữu gồm:
* **Quy mô dữ liệu:** `3.297` bản ghi sự kiện (`fact_report_criteria`), `2.133` chỉ tiêu chi tiết (`criteria`), `117` nhóm chỉ tiêu (`criteria_group`), `40` cơ quan hành chính (`deparment`), `63` phòng ban trực thuộc (`office`), `182` báo cáo (`report`), `173` phạm vi lĩnh vực (`scope`), và `288` nhiệm vụ chuyên môn (`mission`).
* **Trục thời gian:** Số liệu tập trung trong các năm `2025` và `2026`, hỗ trợ phân rã theo kỳ báo cáo năm, quý, tháng và mốc thời gian nộp duyệt (`report_date`).
* **8 Lĩnh vực quản trị nhà nước cốt lõi (`scope_name`):**
  1. **Nội vụ & Lao động:** An toàn vệ sinh lao động (34 chỉ tiêu, 1.244 bản ghi fact), Việc làm (48 chỉ tiêu, 375 bản ghi), Thanh niên (18 chỉ tiêu, 116 bản ghi), Bình đẳng giới (5 chỉ tiêu, 90 bản ghi), Cải cách hành chính, Người có công, Tiền lương.
  2. **Xây dựng:** Xây dựng nhà (11 chỉ tiêu, 398 bản ghi fact), Nhà ở và thị trường bất động sản (13 chỉ tiêu, 64 bản ghi), Quy hoạch xây dựng và kiến trúc (3 chỉ tiêu, 18 bản ghi).
  3. **Công thương:** Tiểu thủ công nghiệp & Khuyến công (9 chỉ tiêu, 144 bản ghi fact), Công nghiệp, Năng lượng & Phát thải (7 chỉ tiêu, 98 bản ghi), Thương mại, Quản lý chợ & Thương mại điện tử (12 chỉ tiêu, 48 bản ghi).
  4. **Y tế:** Phòng chống tệ nạn xã hội (26 chỉ tiêu, 204 bản ghi fact), Dân số (3 chỉ tiêu, 6 bản ghi), Kiểm soát dịch bệnh.
  5. **Giáo dục và Đào tạo:** Giáo dục mầm non (21 chỉ tiêu, 81 bản ghi fact), Giáo dục phổ thông (2 chỉ tiêu, 12 bản ghi).
  6. **Văn hóa - Xã hội:** Du lịch và dịch vụ văn hóa (22 chỉ tiêu, 74 bản ghi fact).
  7. **Nông nghiệp & Phát triển nông thôn:** Trồng trọt, Cây trồng hàng năm, Khuyến nông, Thủy lợi, Lâm nghiệp.
  8. **Tài nguyên & Môi trường:** Đất đai, Tài nguyên nước.
* **Cấu trúc phân cấp đơn vị hành chính 3 tầng (Tree Hierarchy):**
  - **Level 0 (Cấp Tỉnh / TP):** UBND TP. Hồ Chí Minh (`79`), UBND Tỉnh Lâm Đồng (`68`), Tỉnh An Giang (`91`), Tỉnh Đồng Tháp (`82`), Cao Bằng (`04`), Điện Biên (`11`), Đắk Lắk (`66`), Hà Tĩnh (`42`), Đồng Nai (`75`)...
  - **Level 1 (Cấp Sở / Ban / Ngành / UBND Huyện):** UBND Tỉnh Lâm Đồng (`68-1-02`), UBND TP.HCM (`79-1-02`), UBND Tỉnh An Giang (`91-1-01`), Sở Nội Vụ (`79-1-01`)...
  - **Level 2 (Cấp Phòng ban chuyên môn):** `Phòng Văn Hoá` (1.204 bản ghi fact), `Phòng ban An toàn vệ sinh lao động` (806 bản ghi), `Văn hoá` (233 bản ghi), `Phòng ban xây dựng` (231 bản ghi), `Phòng Kinh tế` (225 bản ghi), `Đoàn thanh niên` (115 bản ghi), `Phòng nội vụ` (107 bản ghi), `Phòng công thương` (73 bản ghi), `Phòng ban y tế` (18 bản ghi), `Phòng y tế Công đồng 2` (18 bản ghi)...

---

#### 2.2. Ma Trận Phân Loại 10 Dạng Câu Hỏi Hệ Thống Có Thể Xử Lý (Supported Question Archetypes)

Hệ thống phân tách năng lực xử lý câu hỏi thành 10 dạng rõ ràng, tương ứng với các luồng thực thi chuyên biệt:

| Dạng Câu Hỏi | Tên Năng Lực & Mã Định Tuyến | Bản Chất Kỹ Thuật & Luồng Xử Lý | Ví Dụ Câu Hỏi Thực Tế (Grounded Query) | Kết Quả Phản Hồi Kỳ Vọng |
| :---: | :--- | :--- | :--- | :--- |
| **Dạng 1** | **Tra cứu chỉ tiêu thực tế đơn lẻ**<br>`TEMPLATE_FAST_TRACK` | • Fast Track qua DuckDB Compiler & Jinja2 Template.<br>• Phản hồi chuẩn xác, loại bỏ ảo giác số liệu.<br>• Tự động tiêm phân quyền HBAC và leaf criteria. | *"Năm 2025, tổng số người được đào tạo từ nguồn kinh phí khuyến công tại Phòng Kinh tế là bao nhiêu?"* | *"Theo số liệu báo cáo đã phê duyệt năm 2025 của Phòng Kinh tế (Lâm Đồng), tổng số người được đào tạo khuyến công là: **1.078 người**."* kèm Lineage Badge. |
| **Dạng 2** | **Tổng hợp số liệu phân cấp chống trùng lặp**<br>`TEMPLATE_FAST_TRACK` / `SINGLE_SQL` | • Sử dụng SQL `WITH RECURSIVE` (< 0.5ms) chỉ quét các nút lá (`leaf_criteria`).<br>• Triệt tiêu triệt để nguy cơ double-counting từ báo cáo cấp cha. | *"Tổng số lao động được giải quyết việc làm (hoặc tổng số vụ tai nạn lao động) trên toàn tỉnh Lâm Đồng trong năm 2025 là bao nhiêu?"* | Bảng tổng hợp các phòng ban trực thuộc + Con số tổng lá chuẩn xác của toàn tỉnh (không cộng dồn dòng tổng cấp Sở). |
| **Dạng 3** | **Phân tích chuỗi thời gian đa kỳ (YoY, QoQ)**<br>`DYNAMIC_PARALLEL_DAG` | • Phân rã tùy ý $N$ Sub-queries độc lập ($N \ge 2$).<br>• Bắn song song $N$ truy vấn vào asyncpg pool kết hợp song song hóa LLM speculative drafting.<br>• Cổng lọc kép Dual-Gate triệt tiêu Small Base Effect. | *"So sánh số lao động được đào tạo khuyến công qua 4 quý năm 2025 tại UBND Tỉnh Lâm Đồng và tính tốc độ tăng trưởng liên hoàn?"* | Bảng ma trận 4 quý + Tỷ lệ tăng trưởng điều chuẩn $\delta_{\text{reg}}$ + Đánh giá thống kê (`STABLE` / `SIGNIFICANT`) + Khung nhận định xu hướng. |
| **Dạng 4** | **Đối chuẩn ngang hàng & Xếp hạng Top-K**<br>`DYNAMIC_PARALLEL_DAG` | • Phân rã song song $N$ đơn vị cần so sánh.<br>• Đẩy tính toán xếp hạng xuống CSDL bằng Window Functions (`DENSE_RANK()`). | *"Xếp hạng 5 phòng ban có kinh phí thực hiện công tác bình đẳng giới cao nhất trong năm 2025?"* | Bảng xếp hạng Top 5 phòng ban, kèm giá trị kinh phí, tỷ lệ % và khoảng cách chênh lệch so với đơn vị trung vị. |
| **Dạng 5** | **Phân tích cơ cấu & Tỷ trọng thành phần**<br>`DYNAMIC_PARALLEL_DAG` | • SQL Window Function `SUM() OVER ()` tính tỷ trọng đóng góp % của từng đơn vị con trên cấp cha.<br>• Nhận diện đơn vị trọng điểm chiếm ưu thế. | *"Trong tổng kinh phí khuyến công tại Lâm Đồng năm 2025, kinh phí khuyến công quốc gia chiếm bao nhiêu %?"* | Con số tỷ trọng % chính xác + Thứ hạng đóng góp của nguồn vốn quốc gia trên toàn bộ các nguồn kinh phí. |
| **Dạng 6** | **Ma trận chéo đa chiều (Multi-Dimensional)**<br>`DYNAMIC_PARALLEL_DAG` | • Phân rã $M \times K$ Sub-queries song song không giới hạn.<br>• Tận dụng năng lực xử lý đồng thời hàng chục API calls để tổng hợp bảng dữ liệu 2 chiều. | *"Lập bảng ma trận tổng hợp 3 chỉ tiêu: Số cơ sở CNNT được hỗ trợ, Số lao động đào tạo và Kinh phí khuyến công qua các năm 2025-2026 của 5 phòng ban"* | Bảng Pivot 2 chiều (Đơn vị x Chỉ tiêu x Năm) hoàn chỉnh, điền slot trong RAM $<0.05\text{ms}$. |
| **Dạng 7** | **Giám sát chu trình & Tiến độ nộp duyệt**<br>`TEMPORAL_AUDIT` | • Quét trạng thái `report_status` (`approved`, `pending`, `draft`, `rejected`) và mốc ETL `pipeline_logs`.<br>• Cảnh báo tính chất dữ liệu chưa chốt. | *"Hiện có những báo cáo nào thuộc lĩnh vực Y tế đang ở trạng thái pending chưa được duyệt?"* | Danh sách các báo cáo kèm đơn vị nộp, ngày tạo, trạng thái hiện tại kèm cảnh báo: *"Dữ liệu chưa duyệt, chỉ tham khảo nội bộ"*. |
| **Dạng 8** | **Tự khám phá siêu dữ liệu & Danh mục**<br>`CATALOG_DISCOVERY` | • Tra cứu siêu dữ liệu trên DuckDB In-Memory Catalog trong $<50\text{ms}$.<br>• Không thực hiện truy vấn bảng Fact. | *"Chatbot có thể cung cấp cho tôi những dữ liệu về lĩnh vực nào trong năm 2025?"* | Bảng tổng mục hiển thị 8 lĩnh vực, số lượng nhóm chỉ tiêu và danh sách các cơ quan hành chính có dữ liệu sẵn sàng. |
| **Dạng 9** | **Hội thoại tương tác làm rõ khe khuyết đa dạng**<br>`CLARIFICATION` | • H-DFT nhận diện 6 nhóm khe khuyết (Thời gian, Chỉ tiêu, Đơn vị, Đối chuẩn, Đa nghĩa, Ngoại vực).<br>• Trả Interactive Action Chips để người dùng bấm chọn 1 chạm. | • *"Cho xem diện tích cây trồng"* (Thiếu năm)<br>• *"Tình hình khuyến công thế nào"* (Thiếu chỉ tiêu cụ thể)<br>• *"Báo cáo Phòng Văn hóa"* (Đa nghĩa 3 phòng) | Phản hồi thông điệp làm rõ kèm danh sách nút bấm tương tác: `[Năm 2025]`, `[Năm 2026]`, `[Chỉ tiêu cụ thể]`, `[Chọn đúng phòng ban]`. |
| **Dạng 10** | **Xã giao công vụ, Chào hỏi, Cảm ơn & Tạm biệt**<br>`CHITCHAT_BYPASS` | • Pre-Router Fast Bypass bằng Regex tĩnh & RapidFuzz C++ in-memory.<br>• Xử lý trực tiếp trong RAM, Zero LLM token cost, không quét Fact.<br>• Quản lý vòng đời ActiveQuestFrame (khởi tạo, bảo lưu, dọn dẹp RAM). | • *"Xin chào bạn"*<br>• *"Cảm ơn trợ lý"*<br>• *"Tạm biệt nhé"* | Lời chào/cảm ơn chuẩn mực văn hóa công vụ kèm Interactive Action Chips điều hướng ngay vào tác vụ tra cứu, tránh bẫy dead-end. |

---

### 3. MA TRẬN TRUY VẾT YÊU CẦU NGHIỆP VỤ (REQUIREMENTS TRACEABILITY MATRIX)

| Mã Yêu Cầu SRS | Mô Tả Yêu Cầu Nghiệp Vụ | Tài Liệu Blueprint Giải Quyết | Cơ Chế Kỹ Thuật Hiện Thực Hóa |
| :--- | :--- | :--- | :--- |
| **REQ-01** | Tra cứu số liệu báo cáo chỉ tiêu kinh tế - xã hội bằng ngôn ngữ tự nhiên. | `03_SEMANTIC_LAYER...`<br>`05_MULTI_AGENT...` | Hybrid Semantic AST Compiler ($85\%$) biên dịch `MetricSpecDTO` và DIN-SQL / MAC-SQL Prompting ($15\%$) kết hợp ép kiểu `NULLIF(TRIM(value), '')::numeric`. |
| **REQ-02** | Phân quyền truy cập theo cấu trúc cơ quan: Tỉnh $\to$ Sở $\to$ Phòng ban. | `02_PHAN_QUYEN_HBAC`<br>`04_SECURITY_AST...` | Ma trận quyền hình cây (Tree HBAC) và bộ tiêm vị từ phân quyền tất định vào AST của SQLGlot. |
| **REQ-03** | Khám phá năng lực: Cho biết chatbot có dữ liệu gì, năm nào, thuộc đơn vị nào. | `03_SEMANTIC_LAYER...` | Capability Discovery Engine tra cứu DuckDB In-Memory Catalog trong $<50\text{ms}$, không tải Fact. |
| **REQ-04** | Tránh trùng lặp khi tính toán số liệu vĩ mô (Double-counting). | `01_DATA_WAREHOUSE...` | Thuật toán tổng hợp chỉ quét các nút lá qua SQL `WITH RECURSIVE` ($<0.5\text{ms}$). |
| **REQ-05** | Truy vết nguồn gốc số liệu: Đơn vị nộp, phòng ban tạo, ngày phê duyệt, mốc đồng bộ DWH. | `01_DATA_WAREHOUSE...`<br>`07_ADVANCED_REASONING...` | Mô hình thời gian 4 tầng kết hợp Hợp đồng dữ liệu `LineageBadgeDTO` phát qua SSE với giao diện mở rộng Popover Drawer. |
| **REQ-06** | Hội thoại đa lượt và làm rõ khe khuyết đa dạng (Generalized Multi-Slot H-DFT Framework). | `05_MULTI_AGENT...` | Hierarchical Dialogue Frame Tracker (H-DFT) nhận diện linh hoạt 6 loại slot khuyết thiếu (Thời gian, Mã chỉ tiêu, Đơn vị, Mốc đối chuẩn, Đa nghĩa thực thể, Ngoại vực) và sinh Interactive Action Chips. |
| **REQ-07** | Tính toán so sánh phức tạp (Tăng trưởng YoY, MoM, tỷ trọng). | `03_SEMANTIC_LAYER...`<br>`05_MULTI_AGENT...` | Đẩy phép toán xuống CSDL bằng Window Functions (`DENSE_RANK()`, `SUM() OVER ()`) kết hợp Jinja2 render. |
| **REQ-08** | Giảm thiểu độ trễ nhận thức của người dùng khi xử lý câu hỏi. | `05_MULTI_AGENT...`<br>`07_ADVANCED_REASONING...` | Fast-Track Template ($<300\text{ms}$) cho câu hỏi thống kê chuẩn; Giao thức SSE phát 10 sự kiện tiến trình liên tục ngay từ $600\text{ms}$ đầu tiên cho câu hỏi phức tạp. |
| **REQ-09** | Giám sát chất lượng, bắt vết lỗi truy vấn và đánh giá độ chính xác thực thi. | `06_OBSERVABILITY...` | Langfuse Distributed Tracing, Dead-Letter-Queue (DLQ) và khung kiểm thử theo chuẩn Spider/BIRD. |
| **REQ-10** | Triệt tiêu lỗi cú pháp SQL và ảo giác số liệu (Zero Syntax Error & Zero Hallucination). | `03_SEMANTIC_LAYER...`<br>`05_MULTI_AGENT...` | Bộ biên dịch Hybrid Semantic AST Compiler chuyển đổi `MetricSpecDTO` $\to$ SQL PostgreSQL qua DuckDB Engine kết hợp Động cơ mẫu trả lời tất định (Deterministic Template Engine). |
| **REQ-11** | Trải nghiệm phản hồi tức thì kèm tùy chọn phân tích sâu (Progressive Hybrid UX). | `07_ADVANCED_REASONING...` | Phản hồi Template chuẩn + Bảng số liệu trong $<300\text{ms}$, đính kèm Collapsible Lineage Badge và Interactive Action Chip `[💡 Yêu cầu AI phân tích xu hướng và đánh giá chuyên sâu]`. |
| **REQ-12** | Đồng bộ Danh mục Metadata tự động và an toàn (Automated Metadata Catalog Sync). | `03_SEMANTIC_LAYER...` | Chiến lược đồng bộ 3 tầng (Cold-start hydration, Airflow Webhook, 5-phút Polling `pipeline_logs`) trên DuckDB RAM. |
| **REQ-13** | Bảo đảm an toàn tuyệt đối cho CTE và Subquery lồng nhau (Nested CTE Scope Isolation). | `04_SECURITY_GUARDRAILS...` | Thuật toán Recursive Scope Visitor sử dụng `traverse_scope` của SQLGlot tiêm vị từ HBAC tại đúng Scope con, bảo toàn cú pháp SQL gốc. |
| **REQ-14** | Điều phối xử lý song song bậc cao không xung đột cho tùy ý N Sub-queries (High-Concurrency Parallel Map-Reduce & Speculative LLM Calls). | `05_MULTI_AGENT...` | Bắn đồng thời tùy ý $N$ Sub-queries độc lập xuống `asyncpg` connection pool và đồng thời gọi song song các LLM speculative drafting calls; gom kết quả an toàn qua Reducer `operator.ior` trong RAM $<0.1\text{ms}$. |
| **REQ-15** | Giao tiếp Client SSE hai chiều với đầy đủ chứng cứ nguồn gốc (Production Client SSE). | `07_ADVANCED_REASONING...` | React Custom Hook `useChatStream` sử dụng `fetch` + `ReadableStream` (hỗ trợ JWT Auth Header) và Popover Drawer hiển thị `LineageBadgeDTO`. |
| **REQ-16** | Khung phân tích đa hình và động cơ thống kê cổng lọc kép triệt tiêu hiệu ứng số nhỏ (Polymorphic Speculative Framework & Dual-Gate Volatility Engine). | `03_SEMANTIC_LAYER...`<br>`05_MULTI_AGENT...`<br>`07_ADVANCED_REASONING...` | Pydantic v2 Discriminated Unions cho 5 Kimball Archetypes, Cổng lọc kép Dual-Gate ($|\Delta x| \ge \Delta_{\min}$ và Tăng trưởng điều chuẩn $\delta_{\text{reg}}$) kết hợp `IndicatorConfig` và `JinjaSlotEngine` điền slot trong RAM $<0.05\text{ms}$ tối ưu hóa độ trễ phản hồi. |
| **REQ-17** | Kiến trúc Tinh Giản Ponytail: Jinja2 Template Engine, Database Window Functions & StateGraph 3 Node (Ponytail Lean Architecture). | `00_TECH_STACK...`<br>`01_DATA_WAREHOUSE...`<br>`03_SEMANTIC_LAYER...`<br>`05_MULTI_AGENT...` | Loại bỏ regex custom thay bằng `Jinja2 Environment`, đẩy toàn bộ phép tính toán thống kê xuống SQL (`DENSE_RANK()`, `PERCENTILE_CONT`, `WITH RECURSIVE` $<0.5\text{ms}$), và cô đọng StateGraph thành 3 Node tối giản (triệt tiêu Agent Bloat & Zero Extra Container Services). |
| **REQ-18** | Xã giao công vụ & Cơ chế Chitchat Bypass siêu tốc (Zero Token Cost & Fast-path in RAM). | `05_MULTI_AGENT...`<br>`README.md` | Pre-Router Fast Bypass lọc regex in-memory triệt tiêu $100\%$ chi phí LLM token cho câu chào hỏi/cảm ơn/tạm biệt; tích hợp Jinja2 template công vụ và Interactive Action Chips; điều phối vòng đời ActiveQuestFrame chuẩn xác. |

---

### 4. TÍNH CHÂN THỰC DỮ LIỆU (GROUNDED DATA REALITY)

Tất cả các bản vẽ thiết kế trong bộ tài liệu này đều được đối chiếu và kiểm chứng trực tiếp trên cơ sở dữ liệu **PostgreSQL DWH `vna_wom_dev`** đang chạy trên môi trường Docker của dự án:
* **Host:** `localhost` | **Port:** `5432` | **Database:** `vna_wom_dev`
* **4 Schema:** `dwh_internal` (18 bảng), `dwh_public` (8 bảng), `public` (27 bảng), `staging` (4 bảng).
* **Bảng Fact trọng yếu:** `dwh_internal.fact_report_criteria` (29 cột, khóa thay thế `fact_sk`, giá trị `value` kiểu `TEXT`, phân cấp `tenant_code`, `department_code`, `office_id`).
* **Bảng Danh mục cơ quan:** `dwh_internal.deparment` (lưu ý chính tả không có chữ 't' thứ 2, cấp độ 0 và 1) và `dwh_internal.office` (cấp độ 2 trực thuộc).
* **Bảng Giám sát Pipeline:** `dwh_internal.pipeline_logs` ghi nhận mốc đồng bộ ETL mới nhất.
* **Chính sách trạng thái báo cáo (`report_status`):** Mặc định $100\%$ các truy vấn phân tích vĩ mô và vi mô chỉ quét dữ liệu đã được phê duyệt chính thức (`report_status = 'approved'`). Các trạng thái nghiệp vụ `pending`, `draft`, `rejected` chỉ được truy vấn khi người dùng hỏi rõ ràng về tiến trình nộp duyệt báo cáo của chính cơ quan/đơn vị mình.
