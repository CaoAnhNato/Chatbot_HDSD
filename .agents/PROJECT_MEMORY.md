# PROJECT MEMORY & CORE DIRECTIVES (IPGOV CHATBOT)

> **LƯU Ý CỐT LÕI (CORE DIRECTIVE):**
> Hệ thống chatbot `GovGraph` là của người trước thực hiện và **đã fail toàn tập**. Dự án này bắt đầu lại hoàn toàn mới với hệ thống trong `IPGov_Chatbot/`.
> Mọi nỗ lực kiến trúc, thiết kế, triển khai Text-to-SQL và phân quyền phân cấp từ thời điểm này sẽ được xây dựng tập trung trong `IPGov_Chatbot/`.

---

## 1. THÔNG TIN KẾT NỐI VÀ DỮ LIỆU KHO DWH POSTGRESQL (vna_wom_dev)
- **Host:** `localhost` | **Port:** `5432` | **Database:** `vna_wom_dev` | **User/Pass:** `postgres`/`postgres`
- **4 Schema chính:**
  - `dwh_internal` (18 bảng): Chứa toàn bộ bảng Fact và Dimension nội bộ có phân quyền.
  - `dwh_public` (8 bảng): Dữ liệu công khai phục vụ tra cứu mở.
  - `public` (27 bảng) & `staging` (4 bảng): Bản đồ hành chính (`ward-boundary`, `districts`) và trung gian ETL.
- **Bảng Fact trọng yếu `dwh_internal.fact_report_criteria` (29 cột):**
  - Khóa thay thế: `fact_sk` (TEXT, PK, không có cột `id`).
  - Năm báo cáo: `year` (VARCHAR(4)).
  - Giá trị báo cáo: `value` (TEXT - **LƯU Ý:** Chứa cả chuỗi rỗng `''` và `NULL`, bắt buộc luôn ép kiểu an toàn: `NULLIF(TRIM(value), '')::numeric`).
  - Các cột liên kết: `office_id` (UUID), `department_code` (VARCHAR(64)), `tenant_code` (VARCHAR(64)), `report_date` (TIMESTAMPTZ), `report_status` (VARCHAR(32)).
- **Bảng Danh mục Cơ quan:**
  - `dwh_internal.deparment` (**LƯU Ý CHÍNH TẢ:** Không có chữ 't' thứ 2). Level 0 (`parent_id IS NULL`, ví dụ `79` TP.HCM), Level 1 (`parent_id` trỏ Level 0, ví dụ `79-1-01` Sở Nội Vụ, `79-1-02` UBND TP.HCM).
  - `dwh_internal.office` (Level 2): 36 phòng ban trực thuộc TP.HCM liên kết qua `department_code = '79-1-02'`.
- **Bảng Giám sát Pipeline:** `dwh_internal.pipeline_logs` lưu mốc chạy ETL gần nhất (`model_name`, `last_run_at`, `status`).

---

## 2. CÂY THỰC THỂ PHÂN CẤP VÀ MÔ HÌNH PHÂN QUYỀN HBAC
- **Cấu trúc cây thực tế:**
  `DWH` $\to$ `tenant_code` ('79' TP.HCM, '68' Lâm Đồng) $\to$ `deparment` (Level 0) $\to$ `deparment` (Level 1: Sở Nội vụ, UBND TP) $\to$ `office` (Level 2: Phòng Xây dựng, Phòng Nội vụ, Phòng Kinh tế...) $\to$ `fact_report_criteria`.
- **Nguyên tắc phân quyền HBAC hình cây:**
  - Cấp cao hơn xem toàn quyền dữ liệu các đơn vị con trực thuộc bên dưới.
  - Tuyệt đối cấm xem ngang hàng: Cán bộ UBND TP không xem Sở Nội vụ; Chuyên viên Phòng Xây dựng không xem Phòng Kinh tế.
  - Tuyệt đối cấm xem liên tỉnh: Tài khoản '79' bị chặn đứng khi cố truy vấn '68'.
  - Cưỡng chế phân quyền bằng việc duyệt cây AST và tiêm điều kiện WHERE bắt buộc qua SQLGlot, không dựa vào LLM.

---

## 3. CHÍNH SÁCH 4 TRẠNG THÁI BÁO CÁO (REPORT_STATUS POLICY)
Trong CSDL có 4 trạng thái: `approved` (1.780 dòng), `pending` (618 dòng), `draft` (527 dòng), `rejected` (372 dòng).
- **Mặc định 100% câu hỏi thống kê số liệu/chỉ tiêu:** Chỉ truy vấn `report_status = 'approved'` để bảo đảm tính pháp lý và độ chính xác của số liệu kho DWH.
- **Câu hỏi theo dõi tiến độ nộp:** Chỉ khi người dùng hỏi rõ về tình trạng báo cáo của chính phòng ban họ, hệ thống mới mở rộng tra cứu `pending`, `draft`, `rejected` và luôn gắn kèm cảnh báo: *⚠️ Số liệu chưa được phê duyệt chính thức*.

---

## 4. CÁC QUYẾT ĐỊNH THIẾT KẾ ĐÃ CHỐT QUA PHIÊN /GRILL-ME
1. **Chống Double-Counting Cây Chỉ Tiêu:** Chỉ tổng hợp trên các nút lá (Leaf Criteria) của bảng `dwh_internal.criteria` bằng CTE kiểm tra không tồn tại nút con.
2. **Xử Lý Câu Hỏi Mơ Hồ (Ambiguous):** Chặn ở Clarification Node; phản hồi câu hỏi làm rõ kèm danh sách các nút bấm gợi ý (`Interactive Suggestion Chips`) lấy từ DuckDB Catalog.
3. **Quản Lý Ngữ Cảnh Đa Lượt (H-DFT):** Quản lý qua LangGraph Checkpointer (Redis / Sqlite session cache) với thời hạn hết hạn (TTL) 30 phút, hỗ trợ nút "Tạo phiên chat mới" để reset state.
4. **Dấu Vết Nguồn Gốc Dữ Liệu (Lineage Badge):** Hiển thị thẻ tóm tắt tinh gọn dưới bảng kết quả; khi click thì mở ngăn chi tiết (Drawer / Popover) hiển thị mốc ETL DWH, số dòng Fact và mã hash SHA-256 xác thực.
5. **Quy Chuẩn Định Dạng Bản Vẽ:** 100% sơ đồ dùng cú pháp Mermaid chuẩn; loại bỏ hoàn toàn ASCII art.
6. **[2026-09-26] Cơ Chế Ghi Nhận Lỗi Lập Trình & Tự Động Cập Nhật Bẫy (Traps Recording Cycle):** Trong quá trình chạy code, nếu phát sinh bất kỳ lần chạy code nào lỗi thì lập tức ghi lại lỗi đó; sau khi sửa và test pass thì ghi nhận thông tin fix vào `TRAPS.md` và `.agents/PROJECT_MEMORY.md` theo skill `project-memory-and-traps`. Mọi bước thực thi sau đó bắt buộc tham khảo các bẫy này để tránh lặp lại lỗi, giảm thiểu số lần retry.
7. **[2026-09-28] Chuyển đổi LLM Gateway sang OpenRouter & Cơ chế Tối ưu Chi phí / Pilot Probe Testing:**
   - Cập nhật nhà cung cấp mặc định sang OpenRouter với OpenAI SDK (`openai>=1.40.0`).
   - Phân bổ model: `google/gemini-2.5-flash-lite` (Router, Chitchat, Clarification) và `google/gemini-3.5-flash-lite` (Hard Tasks, Raw SQL Generator).
   - Thu thập metadata log: `generation_id` (`response.id`), `latency_ms`, `prompt_tokens`, `completion_tokens`, `cached_tokens`, và `cost_usd` thực tế từ OpenRouter `usage.cost` (fallback định mức nếu null). Ghi vào `data/logs/llm_usage.jsonl`.
   - Cơ chế kép: Vô Lăng Định Hướng (System Prompt tối ưu + Schema Pruning) + Cầu Dao An Toàn (`max_tokens=400` cho Router, `max_tokens=1500` cho SQL, `stop=["}\n", "\n\n"]`).
   - Pilot Probe Testing: Thực nghiệm 35 câu (5 câu trọng yếu x 7 nhánh) thuần túy với `google/gemini-2.5-flash-lite`, đo lường phân phối token [Min, Mean, P95, Max], chạy 4-7 biến thể prompt để tìm System Prompt tối ưu nhất trước khi chạy toàn bộ test suite.
8. **[2026-10-04] Nguyên Tắc An Toàn Pre-Push Import & Runtime Check:**
   - Trước khi thực hiện `git push`, luôn kiểm tra cú pháp import bằng cách chạy thử trong môi trường ảo local (`.\.venv\Scripts\python.exe -c "import IPGov_Chatbot.main"` hoặc `.\.venv\Scripts\python.exe -m uvicorn IPGov_Chatbot.main:app`) để bảo đảm không phát sinh lỗi phụ thuộc runtime hoặc thiếu package trên môi trường triển khai Cloud (Render).

---

## 5. TIẾN ĐỘ THI CÔNG & TRẠNG THÁI HIỆN TẠI (UPDATED 2026-09-26)
- **Module 1 (API Gateway & Context Extraction):** 🟢 Hoàn thành 100%. JWT HS256 Zero-external-dependency, trích xuất `UserSecurityContextDTO` (Role Level 0-3), phát Event 1 `connected` với TTFE < 2ms (SLA < 50ms).
- **Module 2 (Pre-Router Security Guardrails):** 🟢 Hoàn thành 100%. Lọc PII theo NĐ 13/2023, chặn DDL/DML mutation, chặn hỏi dầu khí Lâm Đồng. Đạt 7/7 test cases `CI-SEC-GUARDRAILS` với Latency ~0.05ms (SLA < 30ms).
- **Module 3 (Query Router & H-DFT Dialogue Tracker with Redis Session Memory):** 🟢 Hoàn thành 100% (v3.2.0).
  - Áp dụng kiến trúc SSOT LLM Structured Outputs (`Pydantic v2 extra="forbid"`) với Alibaba DashScope API (`deepseek-v4.1-flash`, fallback `deepseek-v4-flash-0731` và `qwen3.8-flash`), khắc phục triệt để Boundary Leakage của regex.
  - Tích hợp Redis Session Manager (`ipgov-redis`, `localhost:6379`) quản lý phân tán ActiveQuestFrame, hồ sơ phiên TempMemory, Sliding Window 3 turns (6 messages) bằng `LTRIM`, và Semantic Decision Cache Lượt 1 (`cache:router:{hash}`) phản hồi < 50ms (0 token LLM).
  - Vượt qua toàn bộ 47/47 test cases (100% Pass) bao gồm kiểm thử bộ nhớ Redis, 8 Adversarial Quests, 12 Golden Chitchat cases, 10 Catalog Discovery cases và 5 Multi-turn Threads.
- **Module 4 (DuckDB Semantic Catalog & Capability Discovery Engine):** 🟢 Hoàn thành 100%.
  - Triển khai Hybrid Dual-Mode Hydration (PostgreSQL DWH `vna_wom_dev` + JSON Seed Baseline `catalog_seed_metadata.json`).
  - DuckDB In-Memory Semantic Catalog với BM25 FTS < 2ms và RapidFuzz C++ alias matching.
  - NetworkX Minimal Steiner Tree giải quyết tự động bảng bắc cầu (`office`, `report`, `fact_report_criteria`) với trọng số cạnh nhận thức ngữ cảnh.
  - Capability Discovery Engine phản hồi trực tiếp 18 ca kiểm thử HITL (`CI-CATALOG-DISCOVERY`: 10 `DISC_01`–`DISC_10` & 8 `GOLDEN_021`–`GOLDEN_028`) trong < 50ms (0 fact query).
  - Vượt qua toàn bộ 28/28 unit/integration tests (100% Pass) và 39/39 regression tests toàn hệ thống.
- **Snapshot Test Harness:** Đã sinh Snapshot Baseline Stage 1 (`stage_1_gateway/snapshot_baseline.json`), Stage 2 (`stage_2_prerouter/snapshot_baseline.json`), Stage 3 (`stage_3_router_hdft/snapshot_baseline.json`), và Stage 4 (`stage_4_catalog/snapshot_baseline.json`).
- **Frontend Test Bench:** `IPGov_Chatbot/frontend/role_selector_bench.html` (Test Bench UI trực quan) hỗ trợ Debug Mode và hiển thị trạng thái kết nối Redis.
- **Backend App & CLI Runner:** `IPGov_Chatbot/main.py` và `run_server.py`. Lệnh chạy: `python -m IPGov_Chatbot.run_server`.
- **Tài liệu kỹ thuật:** Xuất bản `MODULE_01_GATEWAY_SPEC.md`, `MODULE_02_GUARDRAILS_SPEC.md`, `MODULE_03_ROUTER_SPEC.md`, `MODULE_04_CATALOG_SPEC.md`, và `BACKEND_RUN_GUIDE.md`.
- **Giai đoạn tiếp theo:** Sẵn sàng chuyển tiếp sang **Module 5 (Text-to-SQL Compiler & Scatter-Gather: Track A 85% Rule-based & Track B 15% MAC-SQL LLM)** sau khi xử lý các điểm nghẽn cốt tử của Module 3 & 4.

---

## 6. [2026-09-27] KẾT QUẢ THẨM ĐỊNH ĐỘC LẬP & ĐIỂM NGHẼN TRỌNG TÂM MODULE 3 & 4
- **Thực nghiệm CSDL Live PostgreSQL `vna_wom_dev`:**
  - Bảng `fact_report_criteria` có 3.297 dòng Fact, trong đó **chính xác 34 dòng có `office_id IS NULL`**. Việc Steiner Tree ép buộc JOIN qua `office` làm rơi rụng hoàn toàn 34 dòng này trong các báo cáo cấp Tỉnh/Sở. Bắt buộc bổ sung cạnh trực tiếp Fact $\leftrightarrow$ Department.
  - Bảng `pipeline_logs` chỉ có 3 cột: `model_name`, `last_run_at`, `status`. Lỗi SELECT cột ảo `row_count` làm liệt đồng bộ Live DB ngầm (`[TRAP-012]`).
- **Điểm nghẽn Hội thoại & Bộ nhớ (Module 3):**
  - **Lỗi Mất Trí Nhớ Phiên (Decision Cache Amnesia - `[TRAP-011]`):** Lượt 1 trúng cache trả về ngay mà không lưu `active_quest` vào Redis, làm gãy toàn bộ hội thoại đa lượt Turn 2.
  - **Bẫy Nuốt Bảng Chiều:** Router nuốt câu hỏi `GOLDEN_021` thành chitchat bypass thay vì chuyển cho Module 4 chọn bảng `mission`.
- **Điểm nghẽn Khế ước & Rút tỉa Schema (Module 4):**
  - **Lệch pha Khế ước:** `SchemaPruner.prune_schema` nhận chuỗi thô `prompt: str`, không nhận `RouterOutputDTO`, vứt bỏ toàn bộ entity đã bóc tách từ H-DFT Tracker.
  - **Nuốt Intent Fact bởi từ khóa "chỉ tiêu" (`[TRAP-010]`):** Bắt nhầm câu hỏi Fact thành danh mục, loại bỏ hoàn toàn bảng Fact `fact_report_criteria`.
  - **Đứt gãy đường ống Gateway:** `gateway_endpoint.py` ngắt stream tại L122 `ready_for_router`, chưa gọi tới `SchemaPruner`.
- **Tài liệu theo dõi lỗi:** Chi tiết 8 ca kiểm thử thất bại và kế hoạch xử lý được lưu trữ tập trung tại [`IPGov_Chatbot/docs/FAILED_TEST_CASES_LOG.md`](../IPGov_Chatbot/docs/FAILED_TEST_CASES_LOG.md).

---

## 7. [2026-09-27] KẾT QUẢ KHẮC PHỤC TRIỆT ĐỂ BỘ ĐIỂM NGHẼN & VERIFICATION HOÀN TẤT
- **Toàn bộ 8 ca kiểm thử thất bại (`FAIL-001` đến `FAIL-008`) đã được xử lý dứt điểm:**
  1. `FAIL-001` (Redis cache contamination): Dọn dẹp cache trong test fixture, tuân thủ `[TRAP-007]`.
  2. `FAIL-002` (E2E Gateway Pipeline): Nối luồng trực tiếp từ Gateway $\to$ Router $\to$ Schema Pruner, phát event `schema_pruned` và `ready_for_sql_generator`.
  3. `FAIL-003` (Catalog Discovery swallowing): Trả về `zero_sql=False`, `bypass_response=None`, `intent=IntentEnum.SCOPE_DISCOVERY` để Module 4 chọn bảng `mission`.
  4. `FAIL-004` (Decision Cache amnesia): Tái nạp `active_quest` vào Redis session trên cache hit, bảo toàn Turn 2 anaphora `[TRAP-011]`.
  5. `FAIL-005` (Missing `row_count` in ETL log): Loại bỏ cột ảo `row_count`, tuân thủ `[TRAP-012]`.
  6. `FAIL-006` (Fact keyword swallowing): Thu hẹp regex dimension, ưu tiên Fact route giữ lại `fact_report_criteria` `[TRAP-010]`.
  7. `FAIL-007` (Steiner tree NULL office Fact rows): Thêm cạnh trực tiếp `fact_report_criteria` $\leftrightarrow$ `deparment` (weight 1.1), bảo toàn 34 dòng Fact cấp Tỉnh/Sở.
  8. `FAIL-008` (Polymorphic `RouterOutputDTO`): `SchemaPruner.prune_schema` hỗ trợ `Union[str, RouterOutputDTO]`, kế thừa trực tiếp slot entity.
- **Bộ kiểm thử nghiệm thu:** Toàn bộ 7/7 ca kiểm thử trong `tests/test_bottlenecks_and_fail_cases.py` và 4/4 trong `tests/test_mod04_catalog.py` **PASS 100%**.
- **Trạng thái hệ thống:** Module 1, 2, 3, 4 liên kết trơn tru; sẵn sàng thi công **Module 5 (Text-to-SQL Compiler & Multi-Agent Workflow)**.




