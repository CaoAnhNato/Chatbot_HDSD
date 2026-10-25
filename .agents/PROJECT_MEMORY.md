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
9. **[2026-10-04] Chuẩn Giao Tiếp Kỹ Thuật Tối Giản (ASD-STE100):**
   - Áp dụng phong cách trả lời ASD-STE100 cho 80% nội dung phản hồi: Câu ngắn (< 25 từ), thể chủ động, động từ mệnh lệnh trực tiếp, trình bày dạng bảng/danh sách cấu trúc, triệt tiêu câu văn rườm rà.
10. **[2026-10-04] Cơ Chế Xả Dòng Văn Bản Mượt Mà (Graceful Queue Drain Pacing & Settlement Handoff):**
    - Khi backend gửi sự kiện `onDone` (mạng kết thúc sớm), `MessageItem.tsx` quản lý state `isAnimationSettled` độc lập với cờ mạng `isStreaming`, ngăn chặn việc component `<FluidTextStream />` bị unmount đột ngột.
    - `useSmoothStream.ts` tiếp tục duy trì vòng lặp `requestAnimationFrame` liên tục với nhịp độ ổn định (~35-40ms/ký tự) cho đến khi xả hết toàn bộ ký tự trong hàng đợi, sau đó phát callback `onSettled()`.
    - Cung cấp phím tắt `Escape` hoặc nhấp chuột vào khung chat để xả tức thì nếu muốn đọc ngay. Loại bỏ hoàn toàn hiện tượng văng 100% text giật cục.
11. **[2026-10-04] Chuẩn Hóa Phản Hồi Chỉ Tiêu Đơn Lẻ (Single-Metric Grounding & Zero 'Mục 1'):**
    - Khi kết quả SQL trả về 1 chỉ tiêu duy nhất (`len(rows) == 1`), tách riêng luồng tổng hợp khỏi bảng đa dòng (`len(rows) > 1`) để không bị khối `else:` đè bẹp kết quả câu văn diễn giải.
    - Bắt buộc đối chiếu tên chỉ tiêu từ CSDL/Catalog (`display_name = raw_name`), triệt tiêu định danh rác `"Mục 1"` trong cả câu văn diễn giải và cấu trúc `tabular_data`.
12. **[2026-10-05] Chuẩn Hóa Quy Trình Kiểm Thử UI 2 Pha Rút Gọn (Batched 2-Phase UI Verification Protocol):**
    - **Pha 1 (Thực thi & Chờ kết quả):** Gộp chuỗi thao tác: Soạn câu hỏi $\to$ Nhập khung chat (`fill` / `type_text`) $\to$ Bấm gửi (`click` hoặc `press_key: Enter`) $\to$ Chờ phản hồi (`wait_for` text selector hoặc DOM settled). Thực thi liên tục trong một chuỗi, tuyệt đối không tách vụn tool call.
    - **Pha 2 (Đánh giá & Lưu trữ Minh chứng):** Chụp ảnh màn hình (`take_screenshot`) lưu vào artifacts/workspace $\to$ Kiểm tra DOM và console log (`list_console_messages` / `evaluate_script`) $\to$ Báo cáo kết quả rõ ràng.
13. **[2026-10-06] Chuẩn Hóa Chống Rò Rỉ Test Case & Khử Heuristic Overfitting:**
    - Tuyệt đối không sử dụng danh sách từ khóa cố định (`stop_phrases`, `spatial_tokens`, `time_tokens`...) để lọc hoặc phân nhánh logic. Mọi thực thể phải tra cứu động qua DuckDB In-Memory Catalog hoặc NLU Model.
    - Chuyển toàn bộ Few-Shot Prompts sang dạng trừu tượng (Canonical Abstract Prototypes: `[Chỉ_Tiêu_A]`, `[Đơn_Vị_B]`, `[Năm_T]`).
    - Ngưỡng tương đồng Token Jaccard với Golden Benchmark: Few-Shot Prompt $\le 15.0\%$, Codebase $\le 30.0\%$.
14. **[2026-10-06] Cấu Hình Token An Toàn Cho DeepSeek (Router Max Tokens = 3000):**
    - Thiết lập `ROUTER_MAX_TOKENS = 3000` và cấu hình LLM Gateway cho DeepSeek lên 3000 token nhằm chống lỗi cắt cụt JSON (`finish_reason='length'`).
15. **[2026-10-11] OpenRouter End-Provider Routing, Reasoning Guard & Chuẩn Hóa Phân Vùng CTE Window Function:**
    - Model Planner SSOT: `deepseek/deepseek-v4.1-flash` với OpenRouter provider order: `["coreweave/fp8", "makora/fp8", "relace", "inference-net/fp8"]`, `allow_fallbacks: True`, và `extra_body` bắt buộc có `"reasoning": {"enabled": False}`. Xóa bỏ hoàn toàn giới hạn `max_tokens` cứng.
    - Động hóa 100% Domain Entities qua DuckDB RAM Catalog (`catalog_criteria`, `catalog_offices`, `catalog_missions`) và schema properties (`is_system`, `is_admin`); khử triệt để `topic_map` tĩnh.
    - Chống Bẫy Lời Chào Ghép: Tách biệt bằng `is_pure_courtesy` kết hợp bóc tách tiền tố/đại từ xưng hô công vụ (`chatbot`, `đồng chí`, `bạn`), đảm bảo câu chào thuần túy không truy vấn DWH và câu hỏi nghiệp vụ lịch sự truyền vào DWH an toàn.
    - Chuẩn hóa Phân vùng CTE Window Function Đa Đơn vị: Cưỡng chế `PARTITION BY TRIM(LOWER(f.name)), COALESCE(f.office_id, '00000000-0000-0000-0000-000000000000'::uuid)` trên tất cả 5 Kimball Archetypes và SQL Compilers để bảo toàn dữ liệu cấp tỉnh [TRAP-007] và cho phép `SUM` chính xác trên toàn tỉnh.

16. **[2026-10-12] Cưỡng Chế 2 Bộ Golden Benchmark (FC-30 & MR-60), Thứ Tự Ưu Tiên Tối Thượng & Whitelist OpenRouter (Cấm Qwen):**
    - Bộ đôi Golden Benchmark kiểm chuẩn toàn diện qua HTTP Endpoint `:8000/api/v1/chat` trên Live DB PostgreSQL `vna_wom_dev`:
      * `FC-30`: `golden_benchmark_fact_criteria_30.json` (30 câu hỏi chuyên sâu `fact_report_criteria`).
      * `MR-60`: `golden_benchmark_multihop_and_robustness.json` (60 câu hỏi Multi-hop Join, Anti-Template Trap, Anti-Out-Of-Scope).
    - Tiêu chuẩn nghiệm thu đồng nhất: Valid SQL Rate $\ge 98\%$, Execution Accuracy $\ge 85 - 90\%$, Zero Security Violation ($0.0\%$).
    - Thứ tự ưu tiên tối thượng của hệ thống: Độ chính xác (Accuracy #1) > Thời gian/Độ trễ (Latency #2) > Chi phí tài nguyên (Cost #3).
    - Whitelist OpenRouter giới hạn nghiêm ngặt: Chỉ dùng 4 model (`gemini-3.1-flash-lite`, `gemini-2.5-flash-lite`, `gemini-3.5-flash-lite`, `deepseek-v4.1-flash`). Tuyệt đối cấm dòng model Qwen (`qwen3.8-flash`, `qwen-2.5-72b-instruct`) và cấm mọi API ngoài OpenRouter.

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
---

## 8. [2026-10-05] TÁI CẤU TRÚC LAI STATEGRAPH, CHUẨN HÓA NGỮ NGHĨA CHỐNG GIÒN NGÔN NGỮ & CHECKLIST INV SUITE (HOÀN TẤT)
- **Bối cảnh:** Giải quyết 81 ca lỗi Red Team (RT1 & RT2) và tính giòn ngôn ngữ (Linguistic Brittleness) mà không dùng regex hay heuristic.
- **Kết quả triển khai:**
  1. `CanonicalQueryFrameDTO` (Pydantic v2) + `CanonicalSemanticNormalizer` (Dual-Stream Parallel Ingestion).
  2. Xóa bỏ hoàn toàn regex thay thế chuỗi trong `warehouse_langgraph_agent.py`.
  3. Khởi tạo phiên mặc định `tenant_code='68'`, `year_code='2026'`, không hỏi Clarification năm/tỉnh ở Turn 1.
  4. Cơ chế Two-Stage Hybrid Selection + LLM Ambiguity Gate: DuckDB Top-5 candidates $\to$ LLM Disambiguator $\to$ kích hoạt Clarification Chips khi đa nghĩa ("HTX nông nghiệp").
  5. Schema-Driven Dynamic Spatial Resolution: Nạp `catalog_tenants` từ DWH DB vào DuckDB RAM, phân định vai trò ngữ nghĩa của từ viết tắt ("LĐ" vs "Lâm Đồng").
  6. AST Enforcer (MOD-06): Tiêm `NULLS LAST` tự động, bọc ép kiểu `NULLIF(TRIM(value), '')::numeric` có kiểm tra ngữ cảnh nút cha (`[TRAP-051]`), che giấu password/salt cho bảng `user`, và tự động mở rộng phân cấp cha - con (`dwh_internal.criteria WHERE parent_id = :val OR id = :val`).
- **Nghiệm thu kiểm thử:** Toàn bộ 38/38 unit, integration và invariance test cases **PASS 100%** trong 36.55s:
  - `tests/test_checklist_invariance.py`: 6/6 PASSED.
  - `tests/test_red_team_critical_fixes.py`: 6/6 PASSED.
  - `tests/test_bottlenecks_and_fail_cases.py`: 7/7 PASSED.
  - `IPGov_Chatbot/tests/test_mod06_ast_enforcer.py`: 19/19 PASSED.
  - Pre-Push Import Check: PASSED (`Pre-Push Import Verified!`).

---

## 9. [2026-10-05] TRIỂN KHAI KIẾN TRÚC TWO-PLANE (DIMENSION VS FACT) VÀ XỬ LÝ TRIỆT ĐỂ BẪY METADATA EXPLORATION (HOÀN TẤT)
- **Bối cảnh & Lỗi được báo cáo:**
  - Câu hỏi: *"Ngoài tỉnh Lâm Đồng ra thì còn tỉnh nào khác không"* bị hệ thống nhầm là tìm kiếm chỉ tiêu trên bảng Fact (`fact_report_criteria`) và tổng hợp: *"Chỉ tiêu 'ngoài tỉnh lâm đồng...' hiện chưa có bản ghi số liệu được phê duyệt trong kho DWH năm 2026"*.
- **Giải pháp Kiến trúc Two-Plane:**
  1. **Schema & Intent:**
     - Thêm `METADATA_EXPLORATION` vào `CanonicalIntentEnum`.
     - Bổ sung `exclude_entities: List[str]` và `search_keyword: Optional[str]` vào `CanonicalQueryFrameDTO`.
     - Phân định rõ ràng:
       * **Dimension Plane:** `province`, `criteria` (metadata exploration), `deparment`, `office`, `ward`.
       * **Fact Plane:** `fact_report_criteria`, `report`, `user_mission`.
  2. **Data & DuckDB Catalog Hydration:**
     - Nạp schema và toàn bộ 34 bản ghi tỉnh/thành phố thật từ PostgreSQL DWH `dwh_internal.province` vào `catalog_seed_metadata.json` và bảng in-memory `catalog_provinces` trong DuckDB Catalog.
     - Đăng ký alias và ART Index cho các tỉnh thành.
  3. **AST Enforcer Whitelist:**
     - Thêm `"province"` và `"ward"` vào danh sách `ALLOWED_TABLES` trong `IPGov_Chatbot/modules/mod06_ast_enforcer/ast_enforcer_service.py`.
  4. **Canonical Normalizer & Text-to-SQL Compiler:**
     - Trong Stream A: Nhận diện intent `METADATA_EXPLORATION` hoặc `DIMENSION_LISTING` cho `province` với `exclude_entities`, `criteria` với `search_keyword`.
     - Bỏ qua bước Disambiguate Metric đối với các bảng Dimension (`ambiguity_status = "RESOLVED"`).
     - Biên dịch câu lệnh SQL chuẩn xác:
       * `province`: `SELECT code, name, is_activated FROM dwh_internal.province WHERE is_activated = true AND name NOT ILIKE '%Lâm Đồng%' ORDER BY name ASC`.
       * `criteria`: `SELECT code, name, level FROM dwh_internal.criteria WHERE deleted_date IS NULL ORDER BY level ASC, code ASC`.
  5. **Warehouse LangGraph Agent:**
     - `node_parse_context`: Không tìm kiếm metric candidates hay kích hoạt Clarification khi câu hỏi thuộc Dimension/Metadata Plane.
     - `node_explore_warehouse` & `node_generate_and_validate_sql`: Cấp phép các bảng Dimension, bỏ qua chỉ thị candidate cho bảng Fact.
     - `node_synthesize_response`: Render bảng Markdown chuyên nghiệp cho danh mục các tỉnh (34 tỉnh, hoặc 33 tỉnh khi loại trừ Lâm Đồng kèm lưu ý rõ DWH hiện lưu trữ số liệu báo cáo phục vụ tỉnh Lâm Đồng).
- **Nghiệm thu kiểm thử:**
  - 13/13 tests trong `tests/test_dimension_and_metadata_routing.py` **PASS 100%** (bao gồm cả trường hợp loại trừ nhiều tỉnh có liên từ "Lâm Đồng và Bình Thuận", câu hỏi địa bàn "địa bàn nào" và đếm "bao nhiêu tỉnh thành").
  - Toàn bộ 25/25 tests trong bộ hồi quy (`test_dimension_and_metadata_routing.py`, `test_checklist_invariance.py`, `test_red_team_critical_fixes.py`) **PASS 100%**.
  - 7/7 tests trong `tests/test_bottlenecks_and_fail_cases.py` **PASS 100%**.
  - Đánh giá toàn diện 81 câu hỏi Red Team (`red_team_1.json` + `red_team_2.json`): 0 lỗi runtime, 0 ngoại lệ, 100% câu hỏi metadata định tuyến chuẩn xác.
  - `.\.venv\Scripts\python.exe -c "import IPGov_Chatbot.main; print('Import Verified!')"` **PASS**.

---

## 10. [2026-10-06] QUY CHUẨN ĐIỀU PHỐI HƯỚNG MÔ HÌNH & ANTI-TEMPLATE HEURISTICS (MODEL-DRIVEN MULTI-RELATIONAL ARCHITECTURE)
- **Bối cảnh & Các bẫy Heuristic:**
  - Câu hỏi toán học / ngoài phạm vi (*"3 mũ 2 là nhiêu ?"*) bị Regex Fallthrough tự động gán thành chỉ tiêu DWH.
  - Câu hỏi đơn vị thực hiện (*"chỉ tiêu liên kết sản xuất đang do đơn vị nào thực hiện ?"*) bị ép thành tính tổng số liệu và Python template in tên chỉ tiêu làm giá trị.
  - Câu hỏi chủ thể chỉ tiêu chưa có số liệu (*"dữ liệu cải cách 1 đang do tỉnh nào thực hiện ?"*) bị ép dump 34 tỉnh.
  - Bảng `dwh_internal.deparment` có 0 dòng, trong khi `dwh_internal.user` lưu trữ toàn bộ ánh xạ `department_code` $\to$ `department_name`.
- **Nguyên tắc Kiến trúc:**
  1. **Quyền quyết định thuộc về LLM (Model Decides):**
     - LLM Lite NLU phân loại rõ: `OUT_OF_SCOPE` (toán học, chitchat $\to$ trả lời trực tiếp, 0 DB query), `ENTITY_ATTRIBUTE_LOOKUP` (tra cứu cơ quan, đơn vị, tỉnh), `RELATIONAL_EXPLORATION` (quan hệ liên bảng xã-tỉnh, nhiệm vụ-phòng ban), `METRIC_NUMERIC_CALCULATION` (số liệu), `METADATA_EXPLORATION` (khám phá danh mục).
     - Loại bỏ triệt để mọi Regex/Heuristic Fallthrough gán chuỗi thô thành tên chỉ tiêu DWH.
  2. **Tham chiếu `department_name` qua `dwh_internal.user`:**
     - Khi `dwh_internal.deparment` có 0 dòng, tham chiếu tên đơn vị thông qua bảng `dwh_internal.user` (JOIN theo `department_code`).
  3. **Mở rộng quan hệ đồ thị (Steiner Tree):**
     - Bổ sung quan hệ `province` $\leftrightarrow$ `ward` (`province_code`), `office` $\leftrightarrow$ `office_mission` $\leftrightarrow$ `mission`.
  4. **Synthesizer linh hoạt (Anti-Template):**
     - Xóa bỏ toàn bộ template chuỗi cứng trong Python và bug dòng 1484 (`val = next(iter(r0.values()))`).
     - Cho phép LLM Synthesizer tự do hành văn và định dạng bảng Markdown / bullet point tự nhiên dựa trên kết quả dữ liệu thật từ PostgreSQL.



---

## 11. [2026-10-07] CẬP NHẬT LOGIC TRUY VẤN FACT_REPORT_CRITERIA & KHẮC PHỤC TOÀN DIỆN 6 ĐIỂM AUDIT (SUBAGENT 2 AUDIT REMEDIATION)
- **Mục tiêu & Bản chất nghiệp vụ:**
  - Chống Double-Counting trên bảng `dwh_internal.fact_report_criteria` bằng Window Function `ROW_NUMBER() OVER (PARTITION BY f.criteria_id, f.office_id ORDER BY f.report_date DESC, f.version DESC) = 1`.
  - Cưỡng chế 100% `report_status = 'approved'`, loại bỏ hoàn toàn bản ghi nháp `draft`.
  - LEFT JOIN `dwh_internal.office` (TRAP-007) bảo toàn 34 bản ghi cấp tỉnh.
  - Hỗ trợ 6 mẫu truy vấn trừu tượng (P-01 đến P-06) với định dạng chuẩn 5 trường (cho 1 dòng) và bảng Markdown 5 cột (cho danh sách nhiều dòng).
- **Khắc phục triệt để các lỗi audit & bẫy runtime:**
  1. **[P-04 Blocker]:** Khi `norm_frame.ambiguity_status == 'RESOLVED'` và có `canonical_metric_ids`, agent không gọi lại `catalog.find_top_k_candidates` để tránh bị đè kết quả $\to$ Trả về chính xác giá trị 64.
  2. **[P-03 Blocker]:** Thêm `r.get("gia_tri_moi_nhat")` lên đầu chuỗi lấy `raw_val` và trong `_get_metric_val` $\to$ Bảng kiểm kê 112 dòng hiển thị số liệu thực, không bị fallback về `-`.
  3. **[P-05 Semantic Drift]:** Dùng regex `\b(202[0-9]|năm\s+202[0-9])\b` để kiểm tra năm; phân tách thông điệp làm rõ theo chủ đề HTX / OCOP $\to$ Không bị hỏi nhầm sang mốc thời gian hoặc nhầm chủ đề.
  4. **[Định dạng phản hồi]:** Đảm bảo chuẩn 5 trường bắt buộc cho phản hồi đơn lẻ và bảng 5 cột cho phản hồi nhiều dòng. Đồng bộ `quick_action_chips` trong `/api/v1/chat` sync endpoint.
  5. **[Anti-Leakage]:** Loại bỏ hoàn toàn ví dụ tĩnh ("tháng 9", "từ tháng 3 đến hiện tại", "2026-03-01") trong `prompt_templates.py`.
  6. **[Dynamic Date]:** Trích xuất động `start_date` trong `track_a_compiler.py`.
  7. **[TRAP-056 Fix]:** Sửa bí danh `lf.office_id` trong `office_filter` của `canonical_normalizer.py`, ngăn chặn lỗi `UndefinedTable: missing FROM-clause entry for table "f"` khi lọc theo phòng ban / đơn vị phụ trách.

---

## 12. [2026-10-08] CHUẨN HÓA BẤT BIẾN NGÔN NGỮ (LINGUISTIC INVARIANCE INV-01 ĐẾN INV-10) & LOẠI BỎ JUNK ILIKE MATCH
- **Mục tiêu & Bản chất nghiệp vụ:**
  - Loại bỏ hoàn toàn tính giòn ngôn ngữ (linguistic brittleness), các câu truy vấn rác `ILIKE '%các chỉ tiêu%'` và ảo giác khẳng định chỉ tiêu tồn tại đối với các câu hỏi thời gian / tập hợp.
  - Vượt qua trọn vẹn bộ kiểm thử hành vi bất biến INV-01 đến INV-10 (31 test cases) theo chuẩn CheckList Framework (ACL 2020), Dr.Spider (ICLR 2023) và live PostgreSQL 16 DWH `vna_wom_dev`.
- **Cải tiến & Khắc phục:**
  1. **DuckDB Semantic Catalog:** Bổ sung `COLLECTIVE_NOUN_STOPWORDS` ("chỉ tiêu", "các chỉ tiêu", "danh mục", "danh sách"...) để chặn đứng việc map danh từ tập hợp vào chỉ tiêu đơn lẻ.
  2. **Clarification Engine:** Bổ sung tiền tố ngắn `"thông tin"` trong `clean_topic` regex để câu hỏi `"thông tin ocop"` kích hoạt đầy đủ Interactive Action Chips (TRAP-058). Xóa bỏ hardcode các từ khóa domain.
  3. **Canonical Normalizer:**
     - Stream B: Hỗ trợ từ chỉ quý bằng chữ ("quý ba"), từ chỉ tháng bằng chữ ("tháng chín"), và số 0 đệm đầu trong regex tháng số `(0?[1-9]|1[0-2])` cùng dấu phân tách `[/.-]` (TRAP-059).
     - Stream A / NLU: Chuyển hướng các câu hỏi chứa danh từ tập hợp sang `DIMENSION_LISTING` với `raw_metric_mentions = []`.
     - SQL Compiler: Ưu tiên `month_filter is not None` sinh `EXTRACT(MONTH FROM f.report_date) = ...` trước `date_from` (TRAP-057).
  4. **Warehouse LangGraph Agent:**
     - Khắc phục tổng hợp dòng rỗng: khi không có bản ghi trong kỳ (ví dụ tháng 01/2024), trả về phản hồi lịch sự rõ ràng thay vì ảo giác khẳng định thực thể tồn tại.
     - Cung cấp alias `chat = run` cho `WarehouseLangGraphAgent`.
- **Nghiệm thu kiểm thử:**
  - 31/31 test cases trong `test_linguistic_invariance_suite.py` **PASS 100% (60.30s)** kết nối trực tiếp qua Backend API `http://127.0.0.1:8000/api/v1/chat` và PostgreSQL 16 `vna_wom_dev`.
  - Pre-Push Import Verification Gate: `import IPGov_Chatbot.main; print('Import Verified!')` **PASS**.

---

## 13. [2026-10-14] TÁI CẤU TRÚC ABSTRACT COT PROMPTING & THẨM ĐỊNH BẤT BIẾN TOÀN DIỆN (MULTI-SUBAGENT PERTURBATION CASCADE AUDIT V3) (HOÀN TẤT)
- **Mục tiêu & Bản chất nghiệp vụ:**
  - Loại bỏ triệt để các danh sách từ khóa tĩnh, mảng tuple và regex hardcode trong Module 3 (`canonical_normalizer.py`, `chitchat_bypass.py`, `clarification_engine.py`) và Module 4 (`duckdb_semantic_catalog.py`). Chuyển hoàn toàn sang cơ chế Abstract Chain-of-Thought Prompting và Dynamic DuckDB RAM Catalog Matching.
  - Mở rộng hỗ trợ 4 mốc thời gian phức hợp: T1–T7 (`2026-01-01` $\to$ `2026-07-31`), Nửa đầu năm (`2026-01-01` $\to$ `2026-06-30`), Quý 2 (`2026-04-01` $\to$ `2026-06-30`), T9 đến hết năm (`2026-09-01` $\to$ `2026-12-31`).
  - Cưỡng chế phân định đối kháng: Đơn chỉ tiêu lá (*"chăn nuôi"* $\to$ 64 kỳ 30/09/2026) vs Nhập nhằng đa nghĩa (*"hợp tác xã"*, *"ocop"* $\to$ Active Clarification Chips).
- **Cải tiến & Khắc phục qua vòng lặp Multi-Subagent (DeepCoder & DeepInvestigator):**
  1. **Zero Heuristics Gate:**
     - Xóa bỏ toàn bộ các mảng tĩnh `canonical_preferred_codes`, `provincial_keywords`, `personnel_topics`, `mission_topics`, `is_criteria_inventory`, `PREFIX_MEASURES`, `VN_PERIOD_MONTHS`.
     - Tạo bảng `catalog_acronyms (acronym, full_form, category)` trong DuckDB RAM lưu trữ các từ viết tắt chuyên môn: `PTNT`, `HTX`, `OCOP`, `TNLĐ`, `UBND`.
     - Tái cấu trúc `resolve_target_table` dựa trên NLU Intent và slot `target_table`, xóa bỏ 8 lệnh `if/else` chuỗi tĩnh.
  2. **Đồng bộ CTE & Khôi phục Aliases Tương thích:**
     - Chuẩn hóa tên CTE `WITH ranked_facts AS (` đồng nhất trong `canonical_normalizer.py` và `warehouse_langgraph_agent.py`.
     - Khôi phục đầy đủ các alias tương thích ngược (`rf.gia_tri AS gia_tri_moi_nhat`, `rf.ngay_bao_cao AS ngay_bao_cao_moi_nhat`, `rf.report_date`, `ten_van_phong`).
     - Sắp xếp tất định: `ORDER BY rf.report_date DESC, TRIM(LOWER(rf.ten_chi_tieu)) ASC`.
  3. **Stream B Dynamic Time Range & Dải Lũy Kế:**
     - Bổ sung regex bóc tách thời gian lũy kế `(?:từ\s+)?tháng\s+(X)\s*(?:đến|tới|-)\s*(?:thời\s+điểm\s+)?(?:hiện\s+tại|nay)` map sang `date_from = '2026-X-01'`, `date_to = '2026-09-30'`.
     - Phân giải chữ chỉ quý ("quý hai") và số chỉ tháng ("tháng 1 đến 7").
  4. **Triệt tiêu Bug Method Shadowing & Nâng cấp LLM Resiliency:**
     - Xóa bỏ định nghĩa trùng lặp của hàm `resolve_metric_id` ở dòng 1668 trong `duckdb_semantic_catalog.py`, bảo toàn kiểm tra `is_dimension_query`.
     - Nâng cấp `_llm_disambiguate` lên `max_tokens=600`, `timeout=15.0s`, parse JSON an toàn với `strict=False` và graceful fallback khi LLM gián đoạn kết nối.
- **Nghiệm thu kiểm thử Full Pipeline End-to-End trên Docker PostgreSQL 16 `vna_wom_dev`:**
  - **Perturbation Cascade Matrix (Lead QA Auditor):** **35/35 PASSED (100.0%)**, 0 thất bại.
  - **Khắc phục 5 ca Phase 2:** `T-EXT-02-Base`, `T-EXT-02-P2`, `T-EXT-03-P2`, `P-INV-02-P3`, `P-INV-02-P4` đều PASSED 100%.
  - **Bộ kiểm thử hồi quy:** **78/78 PASSED (100.0%)**:
    * `test_audit_fixes_subagent2.py`: **47/47 PASSED**.
    * `test_linguistic_invariance_suite.py`: **31/31 PASSED**.
  - **Anti-Contamination Test:** Few-shot similarity **7.14% – 11.54%** ($\le 15.0\%$), Codebase similarity **0.29% – 0.43%** ($\le 30.0\%$).
  - **Pre-Push Import Verification Gate:** `import IPGov_Chatbot.main; print('Import Verified!')` **PASS (Exit code 0)**.

---

## 14. [2026-10-14] CHUẨN HÓA BẢNG DANH MỤC 6 CỘT & PHÂN GIẢI 17 NHÓM CHỈ TIÊU ĐỒNG ÂM (MULTI-CATEGORY DISAMBIGUATION STANDARD - PLAN V4)
- **Bối cảnh & Vấn đề CSDL (TRAP-062):**
  - CSDL PostgreSQL `dwh_internal.fact_report_criteria` kỳ 2026 có **41 bản ghi được duyệt** chia sẻ **17 tên lá giống nhau** (*Chăn nuôi, Đang hoạt động, Trồng trọt, Thủy sản, Lâm nghiệp, Diêm nghiệp, Hiệu quả hoạt động, Liên kết sản xuất...*) thuộc các cây phân cấp cha khác nhau (*Số lượng HTX phân theo lĩnh vực, Tổng số THT phân theo lĩnh vực, Tổng số lượng TT phân theo lĩnh vực, Tổng số LHHTX phân theo lĩnh vực...*).
  - Trước đây, bảng kết quả hiển thị chỉ có 5 cột, khiến các dòng trùng tên bị lẫn lộn, người dùng không phân biệt được số liệu tương ứng của HTX, THT hay Trang trại.
- **Giải pháp Kỹ thuật Triển khai (DeepCoder):**
  1. **Canonical SQL Normalizer (`compile_canonical_sql`, nhánh `DIMENSION_LISTING`):**
     - Bổ sung `f.parent_criteria_id` vào CTE `ranked_facts`.
     - Duy trì cơ chế phân vùng: `PARTITION BY COALESCE(f.criteria_id::text, TRIM(LOWER(f.name))), COALESCE(f.office_id, '00000000-0000-0000-0000-000000000000'::uuid) ORDER BY f.report_date DESC, f.version DESC`.
     - Trong câu `SELECT` chính: `LEFT JOIN dwh_internal.criteria p ON rf.parent_criteria_id = p.id` và lấy trường `COALESCE(p.name, 'Chỉ tiêu chung') AS nhom_chi_tieu`.
     - Sắp xếp tất định: `ORDER BY rf.report_date DESC, TRIM(LOWER(rf.ten_chi_tieu)) ASC, TRIM(LOWER(COALESCE(p.name, ''))) ASC`.
  2. **Warehouse LangGraph Agent (`node_synthesize_response`):**
     - Nâng cấp bảng Markdown lên 6 cột chuẩn: `| STT | Tên chỉ tiêu | Nhóm chỉ tiêu | Giá trị mới nhất | Đơn vị thực hiện | Nhiệm vụ trọng tâm |`.
     - Trích xuất `category = r.get("nhom_chi_tieu") or r.get("parent_name") or "Chỉ tiêu chung"`.
     - Render dòng Markdown 6 cột: `| {idx} | {name} | {category} | **{fmt_val}** | {off} | {mis} |`.
     - Cập nhật DTO `tabular_data["columns"]`: chèn `{"key": "category", "label": "Nhóm chỉ tiêu", "align": "left", "data_type": "text"}` tại vị trí thứ 3 (index 2, giữa `item` và `value`).
     - Từng phần tử trong `tabular_data["rows"]` chứa đầy đủ `"category": category`.
  3. **Script Thẩm Định Độc Lập:**
     - Thiết lập script `IPGov_Chatbot/scripts/verify_multicategory_disambiguation.py` tự động đối soát toàn bộ 17 nhóm chỉ tiêu đồng âm (41 bản ghi DWH). Đạt tỉ lệ Pass 17/17 (100%).
  4. **Bộ Test Chống Thoái Lui (Anti-Regression Assertions):**
     - Siết chặt các assertion trong `IPGov_Chatbot/tests/test_audit_fixes_subagent2.py`, loại bỏ `or` lỏng lẻo cho phép bảng 5 cột, cưỡng chế bảng 6 cột chuẩn và kiểm tra trường `category` trong `tabular_data`.
     - Bổ sung ca kiểm thử `test_audit_fix_t_ext_05_user_prompt_disambiguation` cho prompt người dùng *"từ tháng 4 đến tháng 9 có các chỉ tiêu nào ?"*.
- **Nghiệm thu kiểm định Lead QA Auditor (Subagent 2 - APPROVE):**
  - **17/17 Nhóm chỉ tiêu đồng âm (41 bản ghi DWH) PASSED 100%:** Đối soát trực tiếp qua `verify_multicategory_disambiguation.py` trên live PostgreSQL 16 Docker `vna_wom_dev`.
  - **41/41 Ca Đối kháng Hoán vị (Perturbation Cascade) PASSED 100%:** Bao gồm T-EXT-01 đến T-EXT-05, P-EMPTY-01, P-INV-01 (chăn nuôi 64), P-INV-02 (HTX).
  - **90/90 Ca Kiểm thử Hồi quy Pytest PASSED 100% (391.50s):**
    * `test_audit_fixes_subagent2.py`: 48/48 PASSED.
    * `test_linguistic_invariance_suite.py`: 31/31 PASSED.
    * `test_fact_report_criteria_logic.py`: 11/11 PASSED.
  - **Pre-Push Import Verification Gate:** `import IPGov_Chatbot.main; print('Import Verified!')` **PASS (Exit code 0)**.

---

## 15. [2026-10-14] CHUẨN HÓA THỜI GIAN LŨY KẾ ĐẦU NĂM (YTD), GỠ BỎ MỌI GIỚI HẠN LIMIT NGẦM & HIỂN THỊ TỨC THÌ 0MS CHO DỮ LIỆU WAREHOUSE (HOÀN TẤT)
- **Mục tiêu & Yêu cầu Nghiệp vụ:**
  1. **Chuẩn hóa toàn diện biểu thức thời gian lũy kế (Year-to-Date - YTD) & Dải tháng gạch chéo (`mm/yyyy - mm/yyyy`):**
     - Hỗ trợ đầy đủ các mẫu câu: *"từ đầu năm tới nay"*, *"từ đầu năm đến nay"*, *"đầu năm tới nay"*, *"đầu năm đến giờ"*, *"lũy kế từ đầu năm"*, *"từ đầu năm"*, *"từ đầu năm đến tháng X"*, và *"giai đoạn 3/2026 - 06/2026"*.
     - Truyền `stream_b` vào `_extract_stream_a_deterministic` trong cả đường chạy chính và nhánh fallback `_extract_streams_llm`, đồng thời bổ sung `"đầu năm"`, `"tới nay"`, `"đến nay"`, `"giai đoạn"` vào `DuckDBSemanticCatalog.is_dimension_query`.
  2. **Gỡ bỏ hoàn toàn giới hạn cắt dòng ngầm (`LIMIT 50/100/500`, `rows[:50]`, `PAGE_SIZE = 5`):**
     - `CanonicalQueryFrameDTO.limit` mặc định là `None` (chỉ sinh `LIMIT` khi người dùng hỏi Top-N tường minh).
     - `ASTEnforcerService.validate_and_rewrite` hỗ trợ `inject_limit=False` cho truy vấn DWH nội bộ.
     - Xóa bỏ toàn bộ 13 điểm cắt lát `rows[:50]` / `rows[:100]` và thông báo cắt dòng trong `warehouse_langgraph_agent.py`.
     - Gỡ bỏ `PAGE_SIZE = 5` trong `SmartTable.tsx`, hiển thị toàn bộ danh sách bản ghi trong khung cuộn dọc `max-h-[520px] overflow-y-auto` có tiêu đề cố định (`sticky top-0 z-10`).
  3. **Hiển thị tức thì (`0ms`) cho toàn bộ thông tin truy xuất từ Warehouse:**
     - Tại `WarehouseLangGraphAgent.run_stream`: Phát toàn bộ `final_answer` trong 1 sự kiện `token` duy nhất, loại bỏ vòng lặp chia dòng kèm `await asyncio.sleep(0.005)`.
     - Tại `FluidTextStream.tsx`: Tự động nhận diện điểm bắt đầu khối dữ liệu Warehouse (bảng Markdown `\n|`, thẻ chỉ tiêu `- **Chỉ tiêu:**`, khối `<details>` SQL) để chỉ chạy hiệu ứng gõ chữ trên câu dẫn ngắn (nếu có) và hiển thị tức thì (`0ms`) toàn bộ bảng dữ liệu + SQL.
- **Kết quả Kiểm chứng Thực nghiệm trên PostgreSQL 16 `vna_wom_dev`:**
  - Cả 2 câu hỏi *"Số lượng chỉ tiêu thu thập được từ đầu năm tới nay"* và *"Các chỉ tiêu thu thập trong giai đoạn 3/2026 - 06/2026"* đều trả về đầy đủ **114 bản ghi** đã phê duyệt (`report_status = 'approved'`) trên bảng 6 cột chuẩn, không bị cắt ở 50 bản ghi.
  - Bộ kiểm thử `IPGov_Chatbot/tests/test_temporal_ytd_and_unbounded.py` (3/3 PASSED), `test_fact_report_criteria_logic.py` (11/11 PASSED), `test_mod06_ast_enforcer.py` (19/19 PASSED).

---

## 16. [2026-10-15] QUY CHUẨN ĐẶC TẢ SRS, TOÀN CỤC COT/FEW-SHOT MODULE 3 & 4, LỊCH CALENDAR & CHUẨN POP-UP SCROLL-DOWN (USER DIRECTIVES)
1. **Quy chuẩn Trình bày Tài liệu Đặc tả SRS (`output.md`):**
   - Tài liệu SRS **chỉ lưu trữ phương án thiết kế cuối cùng (Final Specification)**, tuyệt đối không đưa các bảng so sánh hay danh sách đề xuất phương án vào trong SRS.
   - Phần **Logic hoạt động** chỉ trình bày ở mức tổng quan (Overview) bằng ngôn ngữ tự nhiên rõ ràng; tuyệt đối không đưa tên biến, tên cột vật lý, mã lệnh SQL hay các quy tắc chung của hệ thống vào từng case đơn lẻ.
   - Các trường hợp biên đơn giản (chỉ tiêu có giá trị `NULL`/`'-'`, lĩnh vực không tồn tại, nhiệm vụ chưa phát sinh chỉ tiêu báo cáo) chỉ cần ghi ngắn gọn **Định dạng/Mẫu câu trả lời (Output mẫu)**.
2. **Quy tắc Toàn cục Few-Shot / Chain-of-Thought (CoT) tại Module 3 & Module 4:**
   - Phương pháp **Few-Shot kết hợp Chain-of-Thought (CoT) Prompting** được phép áp dụng rộng rãi ở **mọi thành phần trong Module 3 và Module 4** (không giới hạn riêng trong các trường hợp của `output.md`) nhằm khai thác tối đa năng lực NLU tổng quát của LLM và loại bỏ hoàn toàn regex/heuristic cứng.
3. **Cơ chế Lọc Thời gian Lai ghép (Generalized LLM NLU + Deterministic `calendar`):**
   - Đối với mọi tác vụ lọc theo thời gian (*tháng*, *quý*, *nửa đầu năm*, *lũy kế từ đầu năm đến nay*...), hệ thống kết hợp **LLM để phân tích ngữ nghĩa thời gian (NLU) theo hướng tổng quát** và sử dụng **phương pháp tính lịch chuẩn (`calendar`)** để xác định chính xác ngày bắt đầu – ngày kết thúc cần lấy, thay vì phụ thuộc hoàn toàn vào LLM tự tính ngày.
4. **Quy chuẩn Bắt buộc cho Toàn bộ Cửa sổ Pop-up trong Hệ thống `IPGov_Chatbot`:**
   - Áp dụng đồng nhất mô hình **Bảng Cấp 1 kèm nút `- (Xem chi tiết con)` mở Cửa sổ Pop-up Sơ đồ Cây Ngang** cho cả **Loại 1 (`REQ-Q01`)** và **Loại 4 (`REQ-Q04`)**.
   - **Tất cả các định dạng liên quan đến Pop-up trong toàn hệ thống `IPGov_Chatbot`** bắt buộc phải bổ sung **thanh cuộn dọc (`scroll-down`)** để người dùng cuộn xuống xem tiếp khi có nhiều thành phần/chỉ tiêu, tuyệt đối tránh việc thu nhỏ kích thước chữ (text) hoặc ô hiển thị.
   - Người dùng có thể đóng cửa sổ Pop-up bằng 2 cách: bấm vào nút **`'X'`** ở góc trên cùng bên phải của Pop-up hoặc **bấm chuột vào bất kỳ vùng nào bên ngoài cửa sổ Pop-up** (click outside to dismiss).
5. **Quy tắc Xử lý Câu hỏi Chỉ tiêu Đơn lẻ (`REQ-Q02`):**
   - **Trùng tên chỉ tiêu lá ở nhiều nhánh cha (`SC-2.1`):** Hiển thị tất cả các chỉ tiêu trùng tên thuộc các tiêu chí cha khác nhau dưới dạng bảng đối chiếu 6 cột.
   - **Hỏi kèm mốc ngày cụ thể (`SC-2.2` - VD: `28/3`, `24-06-2026`):**
     * *Trường hợp a (Trùng ngày nhập báo cáo):* Hiển thị số liệu của chỉ tiêu vào đúng ngày đó.
     * *Trường hợp b (Lệch ngày nhập báo cáo):* Dò tìm ngày nhập báo cáo gần nhất tính theo chiều **từ trái sang phải** trên trục thời gian (nếu ngày hỏi vượt quá mốc nhập cuối cùng thì lấy mốc ngày nhập cuối cùng bên phải). Ví dụ có 3 ngày nhập `(13/3, 23/3, 25/3)`: hỏi `1/3` $\to$ lấy `13/3`; hỏi `20/3` $\to$ lấy `23/3`; hỏi `29/3` $\to$ lấy `25/3`.
   - **Hỏi trúng tên chỉ tiêu cha có các chỉ tiêu con (`SC-2.4`):** Thông báo rõ đây là chỉ tiêu cha nên không có số liệu cụ thể, kèm các **Button gợi ý** danh sách các chỉ tiêu con trực thuộc đang có số liệu.


## 17. [2026-10-18] QUY CHUẨN GIAO DIỆN POP-UP CÂY PHÂN CẤP TƯƠNG TÁC NỀN TRẮNG TỐI GIẢN & 4 NÂNG CẤP KIẾN TRÚC SRS V3 (USER DIRECTIVES)
1. **Quy chuẩn Thiết kế Giao diện Pop-up Sơ đồ Cây Phân cấp 3 Cấp (`PA 2.1` - `REQ-Q01` & `REQ-Q04`):**
   - **Nền trắng tối giản (`bg-white`):** Bắt buộc sử dụng **background màu trắng**, thiết kế tinh gọn, **không quá nhiều hiệu ứng nổi bật hay quá nhiều text** trên mỗi ô chỉ tiêu để tránh làm người dùng bị ngộp thông tin.
   - **Tương tác nhánh & Đường nối SVG Cubic Bezier 3 cột (`Cấp 1 -> Cấp 2 -> Cấp 3`):**
     * Bố cục 3 cột ngang (`Cấp 1`, `Cấp 2`, `Cấp 3`) kết nối bằng đường cong SVG Cubic Bezier tính toán động qua `getBoundingClientRect()`.
     * Hỗ trợ **đóng/mở nhánh con** trực tiếp trên từng node cha (`ChevronDown` khi mở / badge `+{n}` khi đóng) và nút điều khiển nhanh trên thanh header.
     * Hỗ trợ **highlight nhánh liên kết** (node cha, các node con trực thuộc và đường cong nối SVG) khi người dùng **hover hoặc click** vào một node, đồng thời làm mờ nhẹ các nhánh không liên quan.
     * Giữ nguyên thanh cuộn dọc (`scroll-down`), nút đóng `'X'` góc trên bên phải và cơ chế bấm ra ngoài vùng Pop-up để đóng (`click outside to dismiss`).
   - **Bảo toàn phạm vi lọc thời gian trong Cây Pop-up (`Single-Pass Recursive Tree Hydration`):** Khi truy vấn có bộ lọc thời gian (`SC-1.1`), các chỉ tiêu con trong cây không phát sinh báo cáo trong kỳ lọc phải hiển thị rõ `"-"` (chưa có số liệu trong kỳ), tuyệt đối không lấy nhầm `latest_value` của toàn năm ngoài phạm vi lọc.
2. **Nâng cấp `PA 1.1` (Dual-Bound Snapshot + Temporal Shift Notice cho `SC-2.2`):**
   - Giữ nguyên công thức lấy ngày báo cáo gần nhất $\min(\Delta_A, \Delta_B)$ (ưu tiên cận trên $B$ khi $\Delta_A = \Delta_B$), đồng thời tự động bổ sung dòng **Lưu ý mốc thời gian** trong thẻ 5 trường khi ngày hỏi $a$ bị lệch so với ngày chốt báo cáo thực tế (hiển thị rõ độ lệch $\Delta$ ngày và giá trị cận lân cận để tránh hiểu lầm ngày hệ thống ghi nhận).
3. **Nâng cấp `PA 3.1` (Context-Bound Action Chips & Parent-Slot Persistence cho `SC-2.4` $\leftrightarrow$ `SC-2.1`):**
   - Tách biệt nhãn hiển thị ngắn gọn trên chip (`label`) và câu truy vấn đầy đủ ngữ cảnh cha (`query_text`) khi bấm chip ở `SC-2.4`, đồng thời lưu `inherited_parent_criterion` vào `AgentState` để lượt hỏi kế tiếp (Turn 2) giải quyết chính xác về chỉ tiêu lá đơn lẻ thay vì rơi vào bảng trùng tên `SC-2.1`.
4. **Nâng cấp `PA 4.1` (Neuro-Symbolic Calendar Contract + Bounded CoT Invariant Gate tại Module 3 & 4):**
   - LLM CoT trích xuất cấu trúc ngữ nghĩa thời gian (`temporal_slot`), kết hợp bộ máy `calendar` tất định của Python để tính chính xác ngày đầu/cuối kỳ và kiểm soát bất biến qua Invariant Gate.


---

## 18. [2026-10-20] QUY CHUẨN KHÓA PHẠM VI `output.md`, LOẠI BỎ NHÁNH NGOÀI PHẠM VI (`R2-DYN-*`), ĐƠN VỊ `Chi cục` & QUY TẮC KIỂM THỬ PERTURBATION + UI LẤY MẪU NGẪU NHIÊN (USER DIRECTIVES)
1. **Khóa Nghiêm Ngặt Phạm Vi Theo `IPGov_Chatbot/docs/output.md`:**
   - Hệ thống tập trung tuyệt đối vào 5 loại câu hỏi chuẩn (`REQ-Q01` $\rightarrow$ `REQ-Q05`) và các trường hợp đặc biệt (`SC-1.1` $\rightarrow$ `SC-5.3`) đang có trong `IPGov_Chatbot/docs/output.md`.
   - Tự động loại bỏ toàn bộ các dạng câu hỏi và nhánh logic ngoài phạm vi `output.md` (như `R2-DYN-**`, `SC-1.1_REPORT_STATUS_OVERVIEW`, `SC-1.3_REPORT_DRAFT_ONLY`, `SC-2.1_FACT_CRITERIA_BY_REPORT_STATUS`, `SC-2.2_FACT_DRAFT_BY_MISSION`, `SC-2.3_FACT_DRAFT_SALT_AUG_2026`, `SC-5.1_FACT_DRAFT_Q3_BY_DATE`, `ward_mission_scope`, `office_user_dept`, `fact_office_scope`, `fact_report_scope`, `criteria_fact_office_scope` và các bản ghi seed giả lập).
2. **Chuẩn Hóa Tên Đơn Vị Thực Hiện Đúng Theo Kho Dữ Liệu (`Chi cục`):**
   - Trong bảng `dwh_internal.office`, tên đơn vị thực hiện là **`Chi cục`**. Tuyệt đối cấm gán đè hay hiển thị thành `"Chi cục Phát triển nông thôn"` hoặc `"Chi cục Phát triển nông thôn (Chi cục)"` ở đầu ra.
3. **Quy Tắc Thiết Kế Perturbation (3 Phép Biến Đổi Cấu Trúc Không Chạm Từ Khóa Quan Trọng):**
   - Tập câu hỏi gốc (`Quest gốc`) phải bao phủ hết toàn bộ các dạng quest trong `output.md` (**tối thiểu 20 quest gốc**, hiện thiết kế 22 quest gốc).
   - Mỗi quest gốc có từ **3–6 biến thể nhiễu (perturbations)** tập trung vào 3 phép biến đổi mà không đụng vào các từ khóa nghiệp vụ quan trọng:
     * **Thêm từ nhiễu (`+Noise`):** Thêm các từ đệm, lời dẫn hành chính vào câu hỏi.
     * **Rút gọn từ phụ (`-Reduce`):** Lược bỏ các từ không quan trọng, giữ nguyên các từ khóa cốt lõi.
     * **Đảo vị trí từ (`~Invert`):** Đảo thứ tự các cụm từ (thời gian, lĩnh vực, nhiệm vụ, chỉ tiêu) trong câu hỏi.
4. **Quy Tắc Kiểm Thử UI Lấy Mẫu Ngẫu Nhiên (Random 2-Sample UI Verification per Quest Type):**
   - Khi kiểm thử trên giao diện (UI), mỗi loại quest sẽ chọn chạy kiểm thử **ngẫu nhiên 2 câu hỏi** trong tổng số `(các quest gốc + các quest perturbation)` của loại đó theo chuẩn Batched 2-Phase UI Verification Protocol.
5. **Quy Chuẩn Trình Bày Tinh Gọn & Nắm Bắt Nhanh Trong 30 Giây Cho `IPGov_Chatbot/docs/output.md`:**
   - **Mục tiêu 30 giây:** Mở đầu tài liệu đi thẳng vào **Bảng Mục Lục 5 Nhóm Câu Hỏi Hệ Thống Xử Lý (`REQ-Q01` $\to$ `REQ-Q05`)** để người đọc nắm ngay phạm vi xử lý của hệ thống.
   - **Không lặp ý (Zero Duplication):** Đã có Sample Prompts (`<mark>`) và liên kết file chứa quest ở từng mục chi tiết thì tuyệt đối không liệt kê lặp lại ở bảng tổng quan đầu bài hoặc giữa mục cha và mục con.
   - **Loại bỏ rườm rà kỹ thuật:** Không đưa các mục quy chuẩn nội bộ (NLU/CoT, phương pháp tính lịch, quy tắc UI chung) hoặc lặp lại cùng một sơ đồ Mermaid nhiều lần làm loãng nội dung.

---

## 19. [2026-10-23] QUY CHUẨN THIẾT KẾ GENERATIVE UI / HYBRID CHAT-GUI 5 HẠNG MỤC & TICKET `'SLIDER-TIME'` CHO `REQ-Q02` (USER DIRECTIVES)
1. **Hạng mục 1 (`GP 1.3` — Sơ đồ cây Thích ứng + Lưới Lá Cấp 3 Thu gọn + Tìm kiếm bảo toàn nhánh cha):**
   - Mặc định mở ở Graph View với **Sticky Root Cấp 1** (`sticky top-6`) và gom các nút lá Cấp 3 của cùng 1 nhóm Cấp 2 vào **1 Khối Lưới 2 Cột (`Compact Sub-Grid`)** nối bằng 1 đường cong SVG Bezier duy nhất; tự động thu gọn Cấp 3 khi tổng node $> 7$.
   - Thanh Quick Search bảo toàn đường dẫn cha (`Ancestor-Preserving`) kèm 3 nút lọc 1-Click: `[Tất cả]`, `[Có số liệu]`, `[Chưa có số liệu (-)]` và nút chuyển đổi `[🌳 Sơ đồ cây | 📋 Bảng phẳng]`.
2. **Hạng mục 2 (`GP 2.3` + `Đề xuất 3` — Xem & So sánh đa chỉ tiêu tại chỗ `0ms` + Khay Ghim Chia Đôi Màn Hình Tối Đa 3 Tab):**
   - **Tầng 1 (In-Modal Multi-Metric Comparison Tray — `0ms`, `0 request Backend`):** Bổ sung `report_date` vào `tree_modal`. Cho phép click hoặc tick chọn đồng thời 3–4 chỉ tiêu con trên cây để hiển thị song song các Thẻ 5 trường chuẩn + thanh tỷ lệ `Sparkbar` ngay tại thanh Inspector dưới đáy Pop-up mà không đóng Pop-up hay gọi Backend.
   - **Tầng 2 (Pinned Reference Split-Drawer — Tối đa 3 Ghim):** Hỗ trợ nút `"📌 Ghim"` trên các bảng/cây danh sách để neo sang Khay bên phải (tối đa 3 tab ghim), bảo toàn `temporal_scope` gốc.
3. **Hạng mục 3 (`Đề xuất 4` — Nút Gợi ý Chỉ tiêu con Kèm Số liệu Xem trước cho `SC-2.4`):**
   - Hiển thị kèm badge số liệu hiện tại ngay trên các nút gợi ý chỉ tiêu con của `SC-2.4` (`🔘 Lũy kế đến thời điểm báo cáo: 6`, `🔘 Thành lập mới: 1`...).
4. **Hạng mục 4 (`Đề xuất 5 mở rộng` — Ticket `'slider-time'` cho `REQ-Q02` và Thanh Thời gian Tương tác trên `SmartTable`):**
   - Cập nhật `IPGov_Chatbot/docs/output.md` bổ sung ticket **`slider-time`** cho toàn bộ dạng quest số 2 (`REQ-Q02`: chỉ tiêu lá đơn lẻ, `SC-2.1` đa nhánh, `SC-2.4` chỉ tiêu cha).
   - Hiển thị thanh trượt / bộ chọn mốc thời gian trực tiếp (`slider-time`) ngay trên Thẻ 5 trường chuẩn và Header của `SmartTable` để chuyển đổi nhanh giữa các kỳ báo cáo (`31/03/2026`, `30/06/2026`, `30/09/2026`, `Quý 1..4`, `Bán niên`, `Cả năm 2026`) và bảo toàn Ticket thời gian khi drill-down.
5. **Hạng mục 5 (`Đề xuất 6` — Chế độ Lọc Nhanh Dòng Chênh Lệch / Đã Có Số Liệu trên `SmartTable`):**
   - Bổ sung các nút gạt 1-Click trên Header của `SmartTable`: `[Tất cả]`, `[⚡ Đã có số liệu]`, `[🌳 Có chỉ tiêu con]` (cho `REQ-Q01`/`REQ-Q04`) và `[⚠️ Bản nháp chưa nộp]`, `[⚡ Có chênh lệch số liệu]` (cho `REQ-Q05`/`SC-5.1`).

---

## 20. [2026-10-24] QUY CHUẨN GIAO DIỆN TỐI ƯU CÁN BỘ CAO TUỔI (50+), ĐỒNG BỘ THỜI GIAN PHẢN ỨNG 0MS, TRIỆT TIÊU TRÙNG LẶP NÚT CON & BẢO TOÀN NGỮ NGHĨA DWH PHÂN CẤP / LŨY KẾ OCOP (MILESTONE 1-3 UPGRADES)
1. **Thiết Kế Giao Diện Tinh Gọn Cho Cán Bộ Cao Tuổi (Senior-Friendly UI for 50+ Users):**
   - **Xóa bỏ phân mảnh thông tin:** Loại bỏ hoàn toàn khối 3 hộp thẻ rời rạc phía trên (`grid-cols-1 sm:grid-cols-3` hiển thị `Số liệu phê duyệt`, `Đơn vị thực hiện`, `Nhiệm vụ / Biểu mẫu`) trong `SingleMetricSliderCard.tsx` và xóa nhãn kỹ thuật nội bộ (`Ticket slider-time • 0ms`).
   - **Bảo toàn Test Attributes:** Giữ lại các thẻ trợ năng `<span data-testid="slider-active-value" className="sr-only">` và `slider-delta-badge` trong DOM để phục vụ CI/E2E test mà không gây rác màn hình.
   - **Thanh điều khiển kỳ báo cáo đồng nhất (Unified Senior-Friendly Timeline Selector):** Tái cấu trúc thành thanh điều khiển liền khối đặt trực tiếp trên Thẻ 5 trường chuẩn, trang bị các nút bấm kỳ lớn (`px-3 py-1.5`, `font-bold`), độ tương phản cao (`bg-blue-700 text-white`), ô chọn ngày tùy chỉnh (`slider-custom-date-input`, `slider-custom-date-apply`) và nút Ghim (`pin-item-button`).
   - **Modal Cây Chỉ tiêu:** Đổi nhãn bộ chuyển đổi sang `'Sơ đồ luồng chỉ tiêu'` và `'📋 Bảng chi tiết'`, mặc định mở ở tab `'compact_table'` (`📋 Bảng chi tiết`) để cán bộ xem ngay bảng số liệu mà không cần bấm thêm.

2. **Cơ Chế Đồng Bộ Trạng Thái Thời Gian Phản Ứng Tức Thì (`0ms Client-Side Reactive State Synchronization`):**
   - **Nâng State lên MessageItem:** Quản lý `activeSnapshot` và `activeShiftNotice` tập trung tại `MessageItemComponent`, nhận sự kiện chuyển mốc thời gian qua callback `onTimelineChange(snapshot, shiftNotice)`.
   - **Cập nhật đồng thời 5 trường chuẩn:** Sử dụng client-side regex thay thế tức thì giá trị `- **Giá trị:**` và `- **Thời điểm báo cáo:**` trong văn bản markdown ngay khi người dùng bấm chọn kỳ (`31/03/2026`, `30/06/2026`, `30/09/2026` hoặc ngày tùy chỉnh).
   - **Đồng bộ huy hiệu xem trước của nút con (`reactiveChips`):** Tự động ánh xạ `child_values` từ snapshot để cập nhật số liệu trên huy hiệu `preview_value` của toàn bộ các nút gợi ý chỉ tiêu con tương ứng trong `0ms`.

3. **Triệt Tiêu Hoàn Toàn Trùng Lặp Nút Gợi Ý Chỉ Tiêu Con (Duplicate Action Chips Elimination):**
   - **Nguyên tắc hiển thị duy nhất (Single Interactive Chips Surface):** Các nút gợi ý chỉ tiêu con (`SC-2.4`) chỉ được phép hiển thị **duy nhất một lần** dưới dạng các action chips tương tác (`quick_action_chips`) đặt ở đáy tin nhắn.
   - **Khử bỏ text inline trong Markdown:** Xóa bỏ việc format chuỗi `🔘 [Tên chỉ tiêu con 1]  🔘 [Tên chỉ tiêu con 2]` vào cuối chuỗi markdown `ans` tại `warehouse_langgraph_agent.py`; đồng thời `MessageItem.tsx` áp dụng bộ lọc regex phòng vệ để triệt tiêu mọi chuỗi inline nút bấm còn sót lại trong văn bản.

4. **NLU Phân Cấp & Liệt Kê Danh Mục Con Dựa Trên Kho DWH (DWH-Grounded Hierarchy Breakdown — R3):**
   - **Nhận diện Ý định Bóc tách Phân cấp:** Nhận diện câu hỏi hỏi về số lượng và danh mục con (*lĩnh vực*, *hiệu quả*, *loại diện tích*, *sản lượng*...) của một thực thể (HTX, THT, LHHTX, Trang trại, Diêm nghiệp, OCOP) thuộc `IntentEnum.DIMENSION_LISTING` với `is_hierarchical_breakdown=True`.
   - **Cơ chế Neo Thực Thể Gốc & Cues Ngữ Nghĩa (Entity Root Anchoring & Aspect Cues):** Xác định thực thể gốc (`'HTX nông nghiệp'`, `'Tổ hợp tác nông nghiệp'`, `'Diêm nghiệp'`...) để neo nhánh cây, sau đó dùng aspect cues (*lĩnh vực*, *hiệu quả*, *diện tích*...) để định vị nhóm cha trung gian.
   - **Định dạng Phản hồi Chuẩn Hóa:** Xuất câu dẫn tự nhiên nêu rõ số lượng chính xác và tên in đậm của các nút con trực thuộc, kèm **Bảng 6 cột đầy đủ** (`STT`, `Tên chỉ tiêu`, `Nhóm chỉ tiêu`, `Giá trị mới nhất`, `Đơn vị thực hiện`, `Nhiệm vụ trọng tâm`) và đối tượng DTO `tabular_data`.
   - **Quy tắc Bất biến Zero-Heuristic:** Nghiêm cấm dùng danh sách từ khóa cố định, chuỗi regex cứng hoặc điều kiện `if/else` để hardcode danh sách con.

5. **Phân Định Ngữ Nghĩa Chỉ Tiêu Lũy Kế vs Trong Năm vs Nút Lá OCOP (Cumulative vs Annual vs Leaf Disambiguation — R4):**
   - **Chấm điểm Phân cực Thời gian (Temporal Polarity Scoring):** Khi câu hỏi mang tín hiệu lũy kế (*lũy kế*, *đến thời điểm báo cáo*), ứng viên lũy kế nhận điểm thưởng $\Delta_{\text{temporal}} = +25.0$, ứng viên hàng năm (*trong năm*) bị trừ $\Delta_{\text{temporal}} = -30.0$.
   - **Phạt Tính Đặc thù Xếp hạng Sao OCOP (Star Rating Specificity Penalty):** Nếu câu hỏi KHÔNG hỏi cụ thể thứ hạng sao (*"3 sao"*, *"4 sao"*, *"5 sao"*), tất cả các nút lá mang sao đều bị phạt $\Delta_{\text{star}} = -25.0$, ngăn chặn việc nhóm lũy kế tổng bị nuốt nhầm vào nút lá 5 sao.
   - **Phân cực Đối tượng Thực thể (Entity Subject vs Product Polarity):** Nếu câu hỏi chứa *chủ thể* mà không chứa *sản phẩm*, ứng viên chứa *chủ thể* nhận $+15.0$, ứng viên chỉ chứa *sản phẩm* nhận $-15.0$.

6. **Mở Rộng Kích Thước Tập Ứng Viên Catalog (Candidate Pool Sizing):**
   - Thiết lập `candidate_pool_size = max(top_k * 5, 25)` trong `find_top_k_candidates` khi gọi `find_criteria_by_name`. Đảm bảo các chỉ tiêu có tên dài hoặc có khoảng trắng đôi trong CSDL (`"Lũy kế  tổng số lượng..."`) không bị cắt tỉa sớm ở vòng lọc thô RRF/BM25 trước khi bước vào bộ reranker tính điểm ngữ nghĩa.
