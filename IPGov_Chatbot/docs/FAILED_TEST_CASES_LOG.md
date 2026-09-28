# NHẬT KÝ THEO DÕI & PHÂN TÍCH CA KIỂM THỬ THẤT BẠI (FAIL TEST CASES LOG)

> **Tài liệu tham chiếu kiến trúc gốc (SSOT):**
> - [08_BO_TEST_CASE_KIEM_THU_TOAN_DIEN_VA_5_DIEM_MU_DWH.md](../blueprints/08_BO_TEST_CASE_KIEM_THU_TOAN_DIEN_VA_5_DIEM_MU_DWH.md)
> - [03_SEMANTIC_LAYER_MDL_VA_IN_MEMORY_CATALOG.md](../blueprints/03_SEMANTIC_LAYER_MDL_VA_IN_MEMORY_CATALOG.md)
> - [05_MULTI_AGENT_WORKFLOW_DIN_MAC_SQL.md](../blueprints/05_MULTI_AGENT_WORKFLOW_DIN_MAC_SQL.md)
> - [TEST_CASES_GENEALOGY_AND_MAPPING_GUIDE.md](./TEST_CASES_GENEALOGY_AND_MAPPING_GUIDE.md)
> - **Kho bẫy lỗi hệ thống:** [TRAPS.md](../../TRAPS.md)

---

## 1. Danh Mục Phân Loại Ca Test Lỗi (Failure Taxonomy - MMSQL & Dr.Spider)

| Nhóm Phân Loại | Đặc Điểm Nhận Diện | Tác Động Hệ Thống |
| :--- | :--- | :--- |
| **Nhóm 1: Interface Contract & Disconnected Pipeline** | Lệch pha kiểu dữ liệu giữa các module (ví dụ `str` vs `RouterOutputDTO`), ngắt luồng tại SSE gateway. | Chặn đứng toàn bộ luồng xử lý từ Module 3 sang Module 4 và Module 5. |
| **Nhóm 2: State Amnesia & Cache Contamination** | Trạng thái phiên trong Redis bị rỗng khi trúng Decision Cache hoặc lưu trữ dữ liệu dơ giữa các lần chạy test. | Phá hủy tính đúng đắn của hội thoại đa lượt và gây sai lệch kết quả kiểm thử hồi quy. |
| **Nhóm 3: Intent Swallowing & Boundary Leakage** | Router hoặc Capability Engine nuốt nhầm câu hỏi Fact hoặc Dimension vào nhánh phản hồi tĩnh/chitchat. | Mất sạch bảng Fact hoặc bảng danh mục cần thiết, sinh lỗi SQL hoặc trả lời sai nghiệp vụ. |
| **Nhóm 4: Grounded DB & Schema Inconsistency** | CSDL thật thiếu cột so với query (như `row_count`) hoặc Steiner Tree ép JOIN qua bảng không có quan hệ bắt buộc. | Rơi rụng dòng dữ liệu thực tế (34 dòng Fact có `office_id IS NULL`), liệt đồng bộ Live DB. |

---

## 2. Chi Tiết Các Ca Kiểm Thử Thất Bại & Kế Hoạch Khắc Phục

---

### [FAIL-001] Test Suite `test_clarification_cases` thất bại do nhiễm bẩn trạng thái phiên Redis
- **Mức độ nghiêm trọng:** HIGH (Phá vỡ tính tất định của Pytest)
- **Tệp kiểm thử:** `IPGov_Chatbot/tests/test_mod03_router_all_tracks.py::test_clarification_cases`
- **Kết quả thực tế:** `AssertionError: assert RouteTypeEnum.TEMPLATE_FAST_TRACK == RouteTypeEnum.CLARIFICATION`
- **Kết quả kỳ vọng (Ground Truth):** Câu hỏi thiếu mốc thời gian và đơn vị (*"cho tôi xem kinh phí khuyến công"*) bắt buộc phải được định tuyến vào `RouteTypeEnum.CLARIFICATION` kèm danh sách action chips gợi ý.
- **Phân tích nguyên nhân gốc rễ (Root Cause):**
  - Fixture `router` trong `test_mod03_router_all_tracks.py` không gọi hàm xóa session hoặc dọn dẹp Decision Cache.
  - Session cố định `sess_clarify_test` đã từng được thực thi ở lần chạy trước, lưu trữ trong Redis với `status: COMMITTED`, `turn_count: 3`, và slot `temporal_val: '2025'`.
  - Khi test case chạy lại, Router tại `intent_router.py:480-482` thấy đã có đủ slot từ phiên trước trong Redis, liền tự động kích hoạt logic chuyển đổi hủy bỏ `CLARIFICATION` và gán thành `TEMPLATE_FAST_TRACK`.
- **Hành động khắc phục (Remediation):**
  1. Trong fixture `router`, bắt buộc gọi `router.session_manager.clear_decision_cache()` và khởi tạo `session_id` ngẫu nhiên qua UUID cho từng bài test.
  2. Áp dụng quy tắc dứt điểm theo `[TRAP-007]`.
- **Liên kết Trap liên đới:** [`[TRAP-007]`](../../TRAPS.md#trap-007-lỗi-bẫy-semantic-decision-cache-trong-pytest-suites)
- **Trạng thái:** RESOLVED (Đã xác minh bằng cách xóa key Redis và test pass 100%).

---

### [FAIL-002] Đứt gãy luồng tích hợp Live SSE Pipeline tại Gateway Endpoint (`FACT_001`)
- **Mức độ nghiêm trọng:** CRITICAL (Blocker đường ống E2E)
- **Vị trí phát hiện:** `IPGov_Chatbot/modules/mod01_gateway/gateway_endpoint.py:121-123`
- **Prompt đầu vào:** `"Năm 2025, tổng số người được đào tạo từ nguồn kinh phí khuyến công tại Phòng Kinh tế là bao nhiêu?"`
- **Kết quả thực tế:** Luồng Server-Sent Events phát các event: `connected` $\to$ `thought_progress` $\to$ `router_routed` $\to$ `done (status: ready_for_router)` và dừng hẳn kết nối.
- **Kết quả kỳ vọng (Ground Truth):** Luồng SSE phải tiếp tục chuyển tiếp `RouterOutputDTO` sang Module 4 (`SchemaPruner`), phát event `thought_progress` (hoặc `schema_pruned`) mang theo DDL lát cắt an toàn (`CatalogPrunedDTO`) sẵn sàng cho Module 5 sinh SQL.
- **Phân tích nguyên nhân gốc rễ (Root Cause):**
  - `gateway_endpoint.py` chỉ mới nối dây đến Module 3 (`IntentRouter`), chưa được tích hợp singleton `SchemaPruner` của Module 4.
  - Phân tích đồ thị GitNexus MCP xác nhận không có bất kỳ dòng production code nào trong repo gọi tới Module 4.
- **Hành động khắc phục (Remediation):**
  1. Khởi tạo `_schema_pruner = SchemaPruner()` trong `gateway_endpoint.py`.
  2. Tại dòng 125-142, đối với các route Fact/DAG/Dimension, gọi `pruned_schema = _schema_pruner.prune_schema(router_output, user_ctx=user_ctx.model_dump())` và phát event `thought_progress (step="schema_pruned")` chứa `ddl_slice` và `selected_tables`, tiếp sau là `done (status="ready_for_sql_generator")`.
- **Minh chứng kiểm thử:** Đã kiểm chứng 100% qua test case `test_fail_002_live_sse_pipeline_gateway_to_mod04` trong `IPGov_Chatbot/tests/test_bottlenecks_and_fail_cases.py`.
- **Trạng thái:** RESOLVED (Đã tích hợp hoàn tất E2E Pipeline từ Gateway $\to$ Router $\to$ Schema Pruner).

---

### [FAIL-003] Router nuốt nhầm câu hỏi tra cứu danh mục bảng chiều (`GOLDEN_021`) thành Chitchat Bypass
- **Mức độ nghiêm trọng:** HIGH (Mất mát dữ liệu danh mục)
- **Vị trí phát hiện:** `IPGov_Chatbot/modules/mod03_router/intent_router.py:550-584`
- **Prompt đầu vào:** `"Cán bộ cho tôi hỏi, ở tỉnh Lâm Đồng trong năm nay có những nhiệm vụ hay chương trình nào về hỗ trợ việc làm và đào tạo nghề cho người lao động vậy?"` (`GOLDEN_021`)
- **Kết quả thực tế:** Router nhận diện `route: CATALOG_DISCOVERY`, nhưng do không khớp 10 mẫu regex `DISC_01` $\to$ `DISC_10`, hệ thống rơi vào nhánh fallback gán đoạn văn tĩnh: *"Hệ thống là Trợ lý ảo khai thác kho dữ liệu công vụ tập trung..."* và phát trực tiếp qua `bypass_response`, ngắt kết nối stream.
- **Kết quả kỳ vọng (Ground Truth):** Router phải giữ nguyên yêu cầu, chuyển sang Module 4 để `detect_dimension_intent` chọn bảng `dwh_internal.mission` và sinh SQL danh mục nhiệm vụ.
- **Phân tích nguyên nhân gốc rễ (Root Cause):**
  - Router áp đặt giả định sai lầm rằng mọi câu `CATALOG_DISCOVERY` đều phải khớp 10 câu regex mẫu; nếu không khớp thì ép thành câu giới thiệu tĩnh thay vì chuyển tiếp xuống tầng hạ nguồn.
- **Hành động khắc phục (Remediation):**
  - Xóa bỏ việc gán văn bản tĩnh vào `bypass_response` khi không khớp 10 regex DISC tại `intent_router.py:555-585`. Thiết lập `zero_sql=False`, `bypass_response=None`, `intent=IntentEnum.SCOPE_DISCOVERY` để Module 4 trích xuất bảng Dimension `dwh_internal.mission`.
- **Liên kết Trap liên đới:** [`[TRAP-009]`](../../TRAPS.md#trap-009-lỗi-nuốt-intent-chiều-khi-từ-khóa-phổ-rộng-được-ưu-tiên-trước-từ-khóa-đặc-thù)
- **Minh chứng kiểm thử:** Đã kiểm chứng 100% qua test case `test_fail_003_catalog_discovery_bypass_swallowing` trong `IPGov_Chatbot/tests/test_bottlenecks_and_fail_cases.py`.
- **Trạng thái:** RESOLVED.

---

### [FAIL-004] Lỗi Mất Trí Nhớ Phiên (Decision Cache Amnesia Bug) phá hủy hội thoại Đa lượt Turn 2
- **Mức độ nghiêm trọng:** CRITICAL (Liệt năng lực hội thoại H-DFT)
- **Vị trí phát hiện:** `IPGov_Chatbot/modules/mod03_router/intent_router.py:289-302`
- **Kịch bản kiểm thử:**
  - Turn 1: Hỏi chỉ tiêu khuyến công năm 2025 tại Phòng Kinh tế (Trúng Decision Cache trong Redis).
  - Turn 2: *"Thế còn kinh phí thực hiện ở đó là bao nhiêu?"* (Tỉnh lược anaphora).
- **Kết quả thực tế:** Turn 2 rơi vào `RouteTypeEnum.CLARIFICATION` yêu cầu người dùng chọn lại năm và đơn vị hành chính từ đầu.
- **Kết quả kỳ vọng (Ground Truth):** Kế thừa toàn bộ slot `admin_entity: "Phòng Kinh tế"` và `temporal_val: "2025"` từ Turn 1 để chuyển thẳng vào `TEMPLATE_FAST_TRACK` cho chỉ tiêu mới.
- **Phân tích nguyên nhân gốc rễ (Root Cause):**
  - Khi Turn 1 trúng Decision Cache, hàm `route_query` lập tức `return RouterOutputDTO(**cached_dto)` mà không gọi `_finalize_output()`.
  - Do đó, `session_manager.save_active_quest(...)` và `append_message(...)` không được kích hoạt. Session trong Redis hoàn toàn rỗng.
  - Khi sang Turn 2, Router đọc Redis thấy `curr_quest = None`, coi Turn 2 là một câu hỏi mới độc lập nhưng thiếu thông tin nên yêu cầu làm rõ.
- **Hành động khắc phục (Remediation):**
  - Cập nhật nhánh Decision Cache Hit tại `intent_router.py:295-315`: Trước khi return DTO, bắt buộc tái nạp `output_dto.active_quest` vào Redis Session của `session_id`, đồng thời append tin nhắn user/assistant vào lịch sử.
- **Liên kết Trap liên đới:** [`[TRAP-011]`](../../TRAPS.md#trap-011-lỗi-mất-trí-nhớ-phiên-decision-cache-amnesia-khi-trúng-cache-lượt-1)
- **Minh chứng kiểm thử:** Đã kiểm chứng 100% qua test case `test_fail_004_decision_cache_amnesia_multi_turn` trong `IPGov_Chatbot/tests/test_bottlenecks_and_fail_cases.py`.
- **Trạng thái:** RESOLVED.

---

### [FAIL-005] Liệt cơ chế đồng bộ CSDL Live PostgreSQL trong DuckDB Catalog (`_hydrate_catalog`)
- **Mức độ nghiêm trọng:** MEDIUM (Suy thoái âm thầm thành Offline Seed)
- **Vị trí phát hiện:** `IPGov_Chatbot/modules/mod04_catalog/duckdb_semantic_catalog.py:154-162`
- **Kết quả thực tế:** Mỗi khi khởi động với CSDL Docker PostgreSQL `vna_wom_dev`, hàm nạp metadata luôn nhảy vào khối `except: pass` và báo log: *"Hoạt động ở chế độ Offline/Seed Hydration"*.
- **Kết quả kỳ vọng (Ground Truth):** Đọc thành công mốc chạy ETL gần nhất từ bảng `dwh_internal.pipeline_logs` trên Docker PostgreSQL để cập nhật `catalog_sync_meta`.
- **Phân tích nguyên nhân gốc rễ (Root Cause):**
  - Câu SQL tại dòng 154 viết: `SELECT model_name, last_run_at, status, row_count FROM dwh_internal.pipeline_logs`.
  - Trên CSDL PostgreSQL thực tế, bảng `pipeline_logs` chỉ có 3 cột: `model_name`, `last_run_at`, `status`. Hoàn toàn không có cột `row_count`.
  - Lỗi `psycopg2.errors.UndefinedColumn` bị nuốt chửng bởi khối `try/except: pass`.
- **Hành động khắc phục (Remediation):**
  - Sửa câu SQL tại `duckdb_semantic_catalog.py:151-157` thành `SELECT model_name, last_run_at, status FROM dwh_internal.pipeline_logs`.
- **Liên kết Trap liên đới:** [`[TRAP-012]`](../../TRAPS.md#trap-012-lỗi-truy-vấn-cột-ảo-row_count-trên-dwh_internalpipeline_logs)
- **Minh chứng kiểm thử:** Đã kiểm chứng 100% qua test case `test_fail_005_pipeline_logs_no_row_count_column` trong `IPGov_Chatbot/tests/test_bottlenecks_and_fail_cases.py`.
- **Trạng thái:** RESOLVED.

---

### [FAIL-006] Nuốt Intent câu hỏi Fact chứa từ khóa "chỉ tiêu" trong Module 4
- **Mức độ nghiêm trọng:** CRITICAL (Biến mất bảng Fact khỏi Schema Pruning)
- **Vị trí phát hiện:** `IPGov_Chatbot/modules/mod04_catalog/capability_discovery_engine.py:119` & `schema_pruner.py:73-98`
- **Prompt đầu vào:** `"Báo cáo thống kê số liệu chỉ tiêu khuyến công năm 2025"`
- **Kết quả thực tế:** `selected_tables` chỉ chứa `['dwh_internal.criteria']`. Bảng Fact `dwh_internal.fact_report_criteria` bị biến mất hoàn toàn.
- **Kết quả kỳ vọng (Ground Truth):** Lát cắt Schema bắt buộc phải có `dwh_internal.fact_report_criteria` và các bảng chiều liên quan (`office`, `criteria`).
- **Phân tích nguyên nhân gốc rễ (Root Cause):**
  - Hàm `detect_dimension_intent()` gom từ khóa `"chỉ tiêu"`, `"chi tieu"` vào Dimension `criteria`.
  - Trong `schema_pruner.py`, nếu `detect_dimension_intent` trả về giá trị, hệ thống lập tức bỏ qua toàn bộ Bước 3 (Fact Retrieval), khiến câu hỏi Fact bị đối xử như câu hỏi tra cứu danh mục.
- **Hành động khắc phục (Remediation):**
  - Tại `capability_discovery_engine.py:115-125`, thu hẹp từ khóa regex nhận diện dimension `criteria` thành các cụm từ danh mục chuẩn hóa (`"danh mục chỉ tiêu"`, `"danh sách chỉ tiêu"`, `"tiêu chí đánh giá"`).
  - Tại `schema_pruner.py:65-75`, khi đầu vào là `RouterOutputDTO` và route thuộc nhóm Fact (`TEMPLATE_FAST_TRACK`, `DYNAMIC_PARALLEL_DAG`, `SINGLE_SQL`) hoặc prompt chứa từ khóa thống kê số liệu/năm, bỏ qua hoàn toàn Dimension bypass và cưỡng chế giữ lại `dwh_internal.fact_report_criteria`.
- **Liên kết Trap liên đới:** [`[TRAP-010]`](../../TRAPS.md#trap-010-lỗi-nuốt-intent-fact-khi-câu-hỏi-chứa-từ-khóa-chỉ-tiêu)
- **Minh chứng kiểm thử:** Đã kiểm chứng 100% qua test case `test_fail_006_fact_keyword_swallowing_mod04` trong `IPGov_Chatbot/tests/test_bottlenecks_and_fail_cases.py`.
- **Trạng thái:** RESOLVED.

---

### [FAIL-007] Rơi rụng 34 dòng Fact có `office_id IS NULL` do ép buộc JOIN qua bảng `office` trong Steiner Tree
- **Mức độ nghiêm trọng:** HIGH (Sai lệch số liệu thống kê cấp Tỉnh/Sở)
- **Vị trí phát hiện:** `IPGov_Chatbot/modules/mod04_catalog/steiner_tree_builder.py:37-83`
- **Bằng chứng CSDL Live PostgreSQL `vna_wom_dev`:**
  - Bảng `fact_report_criteria` có tổng cộng **3.297 dòng Fact**.
  - Trong đó có chính xác **34 dòng có `office_id IS NULL`** (đây là các báo cáo được nộp trực tiếp từ cấp Sở hoặc Văn phòng UBND Tỉnh, không thuộc phòng ban trực thuộc nào).
- **Kết quả thực tế:** Đồ thị Steiner Tree không có cạnh trực tiếp `fact_report_criteria` $\leftrightarrow$ `deparment`. Mọi đường đi nối từ Fact sang Department đều bị ép qua `office`: `fact` $\to$ `office` $\to$ `deparment`.
- **Hậu quả:** Khi sinh SQL với `INNER JOIN office ON f.office_id = office.id`, 34 dòng Fact có `office_id IS NULL` bị loại bỏ sạch sẽ, khiến câu hỏi thống kê cấp tỉnh bị sai số hoàn toàn.
- **Hành động khắc phục (Remediation):**
  - Tại `steiner_tree_builder.py:50-58`, bổ sung cạnh trực tiếp:
    ```python
    ("dwh_internal.fact_report_criteria", "dwh_internal.deparment", {"weight": 1.1, "on": "{fact}.department_code = {deparment}.code", "role": "direct_dept"})
    ```
  - Bổ sung helper `build_steiner_tree()` công khai và cập nhật test case bảo đảm khi truy vấn cấp sở không có `office`, đường đi trực tiếp được ưu tiên và 34 dòng Fact NULL office được bảo toàn nguyên vẹn.
- **Minh chứng kiểm thử:** Đã kiểm chứng 100% qua test case `test_fail_007_steiner_tree_direct_edge_preserves_null_office_rows` trong `IPGov_Chatbot/tests/test_bottlenecks_and_fail_cases.py`.
- **Trạng thái:** RESOLVED.

---

### [FAIL-008] Lệch pha khế ước giao tiếp giữa Module 3 và Module 4 (`RouterOutputDTO` vs `str`)
- **Mức độ nghiêm trọng:** HIGH (Phá vỡ tính toàn vẹn DTO)
- **Vị trí phát hiện:** `IPGov_Chatbot/modules/mod04_catalog/schema_pruner.py:34-45`
- **Kết quả thực tế:** Khi truyền trực tiếp `RouterOutputDTO` vào `prune_schema`, code sập với lỗi `AttributeError: 'RouterOutputDTO' object has no attribute 'strip'`.
- **Kết quả kỳ vọng (Ground Truth):** `SchemaPruner` chấp nhận đa hình cả `str` lẫn `RouterOutputDTO`, trích xuất `effective_prompt = input_data.query_sanitized` và tận dụng toàn bộ các slot entity đã được bóc tách từ Module 3.
- **Hành động khắc phục (Remediation):**
  - Nâng cấp chữ ký hàm tại `schema_pruner.py:32-45`: `def prune_schema(self, input_data: Union[str, RouterOutputDTO], user_ctx: Optional[Dict[str, Any]] = None, trace_id: str = "") -> CatalogPrunedDTO:`.
  - Tự động trích xuất `effective_prompt = input_data.query_sanitized` và khai thác các slot `temporal_val`, `admin_entity` từ `input_data.active_quest`.
- **Minh chứng kiểm thử:** Đã kiểm chứng 100% qua test case `test_fail_008_schema_pruner_polymorphic_router_output_dto` trong `IPGov_Chatbot/tests/test_bottlenecks_and_fail_cases.py`.
- **Trạng thái:** RESOLVED.

---

### [FAIL-009] Regex Nuốt Toán Tử Ép Kiểu PostgreSQL (`::numeric` $\to$ `:'68'`) & Unquoted Varchar `year=2026`
- **Mức độ nghiêm trọng:** CRITICAL (Làm sập 83/106 ca kiểm thử Live PostgreSQL Benchmark)
- **Vị trí phát hiện:** `IPGov_Chatbot/tests/test_module_05_sql_suites.py:155-163` và `IPGov_Chatbot/modules/mod05_sql_compiler/db_dry_run.py:54-64`
- **Triệu chứng & Kết quả thực tế:**
  - `syntax error at or near ":"` do `SUM(NULLIF(TRIM(f.value), ''):'68')`.
  - `operator does not exist: character varying = integer` do `WHERE f.year = 2026` và `f.tenant_code = 68`.
  - Valid SQL Rate ban đầu chỉ đạt 21.70% (23/106 cases) dù LLM đã sinh ra câu truy vấn hoàn toàn chính xác.
- **Phân tích nguyên nhân gốc rễ (Root Cause):**
  - Regex thay thế bind param `r":([a-zA-Z_0-9]+)\b"` không dùng Negative Lookbehind `(?<!:)`, vô tình khớp dấu hai chấm thứ hai trong toán tử ép kiểu của PostgreSQL `::numeric` hoặc `::text`.
  - Hàm chuẩn hóa coi `str(v).isdigit()` là tín hiệu để unquote giá trị, làm cho trường varchar `year` và `tenant_code` bị gỡ bỏ nháy đơn `'2026'`, `'68'`.
- **Hành động khắc phục (Remediation):**
  1. Thêm Negative Lookbehind `(?<!:)` cho mọi regex thay thế bind parameter trong cả `db_dry_run.py` và `test_module_05_sql_suites.py`.
  2. Chỉ cho phép unquoted integer cho các tham số phân trang (`top_k`, `limit`, `offset`). Các trường mã hóa nghiệp vụ bắt buộc bọc trong nháy đơn.
- **Liên kết Trap liên đới:** [`[TRAP-020]`](../../TRAPS.md#trap-020), [`[TRAP-021]`](../../TRAPS.md#trap-021).
- **Trạng thái:** RESOLVED (Sau khi sửa, Valid SQL Rate đạt 100.0% trên toàn bộ 106 ca kiểm thử có SQL).

---

### [FAIL-010] Sập Tiến Trình Khi Xuất Bản Baseline Snapshot Stage 5 Do `date`, `Decimal`, `UUID` Không Thể JSON Serialize
- **Mức độ nghiêm trọng:** HIGH (Phá vỡ quá trình xuất bản artifact nghiệm thu Snapshot Stage 5)
- **Vị trí phát hiện:** `IPGov_Chatbot/tests/test_module_05_sql_suites.py:355`
- **Triệu chứng & Kết quả thực tế:**
  - `TypeError: Object of type date is not JSON serializable` khi gọi `json.dump(snapshot_payload, f)`.
  - Tệp `snapshot_baseline.json` bị cắt cụt ở dòng 1620, làm fail toàn bộ test suite ở bước cuối cùng sau khi đã chạy 27 phút.
- **Phân tích nguyên nhân gốc rễ (Root Cause):**
  - Trình điều khiển `psycopg2` chuyển đổi các trường `report_date`, `value`, `criteria_id` thành các đối tượng Python chuyên biệt (`datetime.date`, `decimal.Decimal`, `uuid.UUID`).
  - Hàm `json.dump()` tiêu chuẩn của Python không hỗ trợ serialize các kiểu dữ liệu này nếu không có fallback serializer.
- **Hành động khắc phục (Remediation):**
  - Bổ sung `default=str` vào mọi lệnh gọi `json.dump(snapshot_payload, f, default=str, ensure_ascii=False, indent=2)`.
- **Liên kết Trap liên đới:** [`[TRAP-022]`](../../TRAPS.md#trap-022).
- **Trạng thái:** RESOLVED (Tệp `snapshot_baseline.json` được xuất bản thành công với 3.214 dòng JSON hợp lệ 100%).

