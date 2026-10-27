# 🪤 WORKSPACE TRAPS & ANTI-PATTERNS (IPGov_Chatbot)

Tài liệu hạt nhân lưu trữ các bài học xương máu, bẫy cú pháp và lỗi runtime đã từng xảy ra trong dự án.  
**Mọi Agent và Sub-Agent BẮT BUỘC đọc tài liệu này trước khi lập kế hoạch sửa code hoặc thực thi terminal.**

---

### [TRAP-001] Lỗi cú pháp Escape ký tự khi chạy Python Inline trên PowerShell Windows
- **Môi trường & Công nghệ:** PowerShell 5.1/7 / Windows / Python CLI (`python -c "..."`)
- **Triệu chứng:** `SyntaxError: '[' was never closed` hoặc `SyntaxWarning: "\E" is an invalid escape sequence`.
- **Nguyên nhân gốc rễ:** Ký tự backtick (\`) là ký tự escape của PowerShell, dấu nháy kép `"` bị nuốt, và chuỗi escape `\E` bị Python xem là chuỗi thoát không hợp lệ khi truyền qua tham số dòng lệnh một dòng.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không chạy các đoạn mã Python phức tạp chứa dấu ngoặc vuông, list, hoặc chuỗi có dấu tiếng Việt trực tiếp qua `run_command` dạng inline `python -c "..."`.
  * ✅ **ALWAYS:** Luôn viết mã thử nghiệm ra tệp script tạm (scratch file trong `.gemini/.../scratch/test_xxx.py`) rồi gọi `python path/to/scratch.py`.

---

### [TRAP-002] Lỗi ModuleNotFoundError khi thực thi script Python độc lập
- **Môi trường & Công nghệ:** Python venv / Cấu trúc thư mục module `IPGov_Chatbot`
- **Triệu chứng:** `ModuleNotFoundError: No module named 'IPGov_Chatbot'`.
- **Nguyên nhân gốc rễ:** Khi chạy một script nằm sâu trong thư mục con mà không chạy dạng `-m package.module` từ thư mục gốc, Python không tự động thêm thư mục gốc workspace vào `sys.path`.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không chạy `python IPGov_Chatbot/tools/script.py` từ ngoài mà không khai báo package context.
  * ✅ **ALWAYS:** Luôn chạy dạng module với interpreter venv: `.\.venv\Scripts\python.exe -m IPGov_Chatbot.tools.script` HOẶC chèn `sys.path.insert(0, str(workspace_root))` ở đầu script.

---

### [TRAP-003] Lỗi mở tệp với đường dẫn Windows URL Encoded (file:/// + %20)
- **Môi trường & Công nghệ:** Python `pathlib.Path` / Markdown Links có khoảng trắng và tiếng Việt UTF-8
- **Triệu chứng:** `FileNotFoundError` khi phân tích đường dẫn `file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/...`.
- **Nguyên nhân gốc rễ:** Đường dẫn markdown trỏ tới file trên Windows thường chứa `%20` (khoảng trắng) và mã hex UTF-8 (`%E1%...`). `Path(link)` xem `%20` là tên thư mục thực tế nên báo không tìm thấy tệp.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không truyền trực tiếp chuỗi link markdown vào `Path(link)`.
  * ✅ **ALWAYS:** Bắt buộc chuẩn hóa bằng `urllib.parse.unquote(link.replace("file:///", ""))` trước khi khởi tạo `Path`.

---

### [TRAP-004] Lỗi Ép Kiểu Cột Giá Trị Fact Kho DWH (fact_report_criteria.value)
- **Môi trường & Công nghệ:** PostgreSQL 17 / DWH Schema `dwh_internal`
- **Triệu chứng:** `invalid input syntax for type numeric: ""` hoặc kết quả SUM/AVG bị sai lệch do dính NULL/Chuỗi rỗng.
- **Nguyên nhân gốc rễ:** Cột `value` trong bảng Fact được thiết kế kiểu `TEXT`, chứa cả chuỗi rỗng `''` và `NULL`.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Tuyệt đối không cast trực tiếp `value::numeric`.
  * ✅ **ALWAYS:** Bắt buộc luôn ép kiểu an toàn qua hàm làm sạch: `NULLIF(TRIM(value), '')::numeric`.

---

### [TRAP-005] Lỗi Sai Chính Tả Tên Bảng Danh Mục Đơn Vị (deparment)
- **Môi trường & Công nghệ:** PostgreSQL DWH Catalog
- **Triệu chứng:** `relation "dwh_internal.department" does not exist`.
- **Nguyên nhân gốc rễ:** Tên bảng thực tế trong cơ sở dữ liệu hiện hữu là `deparment` (thiếu chữ 't' thứ hai), là di sản schema legacy.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không viết theo thói quen tiếng Anh chuẩn `department`.
  * ✅ **ALWAYS:** Bắt buộc dùng `dwh_internal.deparment` (hoặc view chuẩn hóa nếu có).

---

### [TRAP-006] Lỗi Pydantic v2 Strict Mode (extra="forbid") Khi Ánh Xạ DTO LLM / Local Fallback
- **Môi trường & Công nghệ:** Pydantic v2 / `LLMRouterStructuredOutput`
- **Triệu chứng:** `pydantic_core._pydantic_core.ValidationError: Extra inputs are not permitted [type=extra_forbidden]`.
- **Nguyên nhân gốc rễ:** Mô hình hoặc hàm fallback truyền thêm các trường không nằm trong định nghĩa schema (như `confidence_score`, `trace_id`) vào constructor của Pydantic class có cấu hình `model_config = ConfigDict(extra="forbid")`.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không truyền các trường mở rộng hoặc thuộc tính cấp cao của `RouterOutputDTO` vào `LLMRouterStructuredOutput`.
  * ✅ **ALWAYS:** Chỉ truyền đúng các trường thuộc schema (`intent`, `dag_archetype`, `subquery_count`, `complexity`, `temporal_scope`, `spatial_scope`, `dwh_entities`, `is_ambiguous`, `is_topic_shift`, `clarification_reason`).

---

### [TRAP-007] Lỗi Bẫy Semantic Decision Cache Trong Pytest Suites
- **Môi trường & Công nghệ:** Pytest / Redis Decision Cache
- **Triệu chứng:** Test case chạy lần đầu pass, chạy lại fail hoặc không kích hoạt nhánh logic mong muốn do bị trả về kết quả cũ từ `cache:router:*`.
- **Nguyên nhân gốc rễ:** Decision Cache lưu trữ kết quả phân loại Lượt 1 bằng SHA-256 hash của prompt với TTL 3600s để tiết kiệm API token. Khi chạy test suites nhiều lần với cùng chuỗi prompt cố định, cache hit sớm che khuất các thay đổi trong logic thực thi.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không phụ thuộc vào việc để cache tự hết hạn giữa các lần chạy pytest.
  * ✅ **ALWAYS:** Trong fixture `router` của Pytest, bắt buộc gọi `r.session_manager.clear_decision_cache()` cùng với `clear_session()` để bảo đảm môi trường kiểm thử hoàn toàn sạch và tất định.

---

### [TRAP-008] Lỗi Bỏ Qua Seed Fixture Khi Cài Đặt Cơ Chế Hybrid Hydration
- **Môi trường & Công nghệ:** DuckDB In-Memory / PostgreSQL Docker `vna_wom_dev` / Hybrid Hydration
- **Triệu chứng:** `assert row[0] > 0` fail (bảng `catalog_criteria` có 0 dòng) và `match_alias_or_abbreviation` trả về `None` dù seed data đã có sẵn.
- **Nguyên nhân gốc rễ:** Trong logic nhánh `try/except`: nếu `psycopg2.connect` thành công với Docker PostgreSQL nhưng bước nạp dòng chi tiết chưa hoàn tất mà đã set cờ `hydrated_from_db = True`, hệ thống sẽ nhảy qua hàm `_hydrate_from_seed_file()`, dẫn đến DuckDB RAM và `_alias_registry` bị rỗng hoàn toàn.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không dùng cờ `if not hydrated_from_db` để bỏ qua bước nạp seed dữ liệu nền tảng.
  * ✅ **ALWAYS:** Luôn nạp toàn bộ cấu trúc schema, aliases, acronyms từ `catalog_seed_metadata.json` trước làm baseline vững chắc; sau đó nếu có kết nối Live DB thì thực hiện query cập nhật hoặc enrich thêm dữ liệu thực tế.

---

### [TRAP-009] Lỗi Nuốt Intent Chiều Khi Từ Khóa Phổ Rộng Được Ưu Tiên Trước Từ Khóa Đặc Thù
- **Môi trường & Công nghệ:** Regex Intent Routing / Semantic Catalog Dimension Dispatcher
- **Triệu chứng:** Câu hỏi `GOLDEN_024` ("cho em xin danh sách các tiêu chí đánh giá thuộc mảng nhiệm vụ Cải cách hành chính...") bị định tuyến nhầm sang `dwh_internal.mission` thay vì `dwh_internal.criteria`.
- **Nguyên nhân gốc rễ:** Từ khóa phạm vi rộng/văn cảnh phụ ("nhiệm vụ", "kế hoạch") được kiểm tra trước từ khóa thực thể cốt lõi ("tiêu chí", "tiêu chí đánh giá", "chỉ tiêu"), khiến câu hỏi chứa cả hai từ khóa bị nuốt sớm vào nhánh `mission`.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không đặt các điều kiện regex chứa từ khóa phụ/rộng ("nhiệm vụ", "kế hoạch") lên đầu chuỗi `if/elif`.
  * ✅ **ALWAYS:** Luôn sắp xếp thứ tự ưu tiên kiểm tra từ thực thể đặc thù cao nhất đến thấp nhất: `criteria` (tiêu chí/chỉ tiêu) $\to$ `collection_form` (biểu mẫu/tờ khai) $\to$ `deparment` (sở ban ngành/đơn vị) $\to$ `mission` (nhiệm vụ trọng tâm/chương trình).

---

### [TRAP-010] Lỗi Nuốt Intent Fact Khi Câu Hỏi Chứa Từ Khóa "Chỉ Tiêu"
- **Môi trường & Công nghệ:** Schema Pruning / Dimension Intent Detection / Semantic Catalog
- **Triệu chứng:** Câu hỏi Fact số liệu ("Báo cáo thống kê số liệu chỉ tiêu khuyến công năm 2025") chỉ chọn ra bảng danh mục `['dwh_internal.criteria']`, bảng Fact `fact_report_criteria` bị biến mất hoàn toàn.
- **Nguyên nhân gốc rễ:** Hàm `detect_dimension_intent()` gom các từ khóa thông dụng công vụ ("chỉ tiêu", "chi tieu") vào danh mục, và `schema_pruner.py` bỏ qua toàn bộ Bước 3 (Fact Retrieval) khi phát hiện Dimension intent.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không kích hoạt `detect_dimension_intent()` khi câu hỏi đã được Module 3 phân loại thuộc các nhóm Fact (`TEMPLATE_FAST_TRACK`, `DYNAMIC_PARALLEL_DAG`, `SINGLE_SQL`).
  * ✅ **ALWAYS:** Khi nhận `RouterOutputDTO`, ưu tiên tuyệt đối phân loại Router của Module 3; chỉ quét Dimension khi Router định tuyến vào `CATALOG_DISCOVERY`.

---

### [TRAP-011] Lỗi Mất Trí Nhớ Phiên (Decision Cache Amnesia) Khi Trúng Cache Lượt 1
- **Môi trường & Công nghệ:** Redis Decision Cache / H-DFT Dialogue Tracker / Multi-turn Anaphora
- **Triệu chứng:** Câu hỏi Lượt 1 trúng Decision Cache trả về kết quả nhanh, nhưng sang Lượt 2 câu hỏi tiếp nối ("Thế còn kinh phí ở đó là bao nhiêu?") bị rơi vào `CLARIFICATION` hỏi lại thông tin từ đầu.
- **Nguyên nhân gốc rễ:** Nhánh trúng Decision Cache tại `intent_router.py:289-302` trả về DTO ngay lập tức mà không gọi `_finalize_output()`, dẫn đến `active_quest` không được lưu vào Redis session.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không return trực tiếp DTO từ cache mà bỏ qua việc đồng bộ trạng thái vào Session Manager.
  * ✅ **ALWAYS:** Luôn gọi `session_manager.save_active_quest(session_id, cached_dto.active_quest)` và ghi nhận lịch sử chat vào Redis trước khi trả về kết quả.

---

### [TRAP-012] Lỗi Truy Vấn Cột Ảo `row_count` Trên Bảng `dwh_internal.pipeline_logs`
- **Môi trường & Công nghệ:** PostgreSQL Docker `vna_wom_dev` / `duckdb_semantic_catalog.py`
- **Triệu chứng:** Kết nối Live DB thành công nhưng hàm `_hydrate_catalog()` luôn rơi vào `except` và fallback về Offline Seed Hydration.
- **Nguyên nhân gốc rễ:** Bảng `dwh_internal.pipeline_logs` trong CSDL PostgreSQL thực tế chỉ có 3 cột: `model_name`, `last_run_at`, `status`. Câu lệnh SQL cố tình SELECT thêm cột `row_count` không tồn tại, gây lỗi `UndefinedColumn` và bị nuốt bởi khối `try/except: pass`.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không suy đoán cột của bảng hệ thống mà không kiểm tra qua `information_schema.columns`.
  * ✅ **ALWAYS:** Chỉ SELECT các cột chắc chắn tồn tại (`model_name, last_run_at, status`) trên `pipeline_logs`.

---

### [TRAP-013] Lỗi Hardcode Bí Danh `f.` Trong Khế Ước Phép JOIN `JoinPathDTO`
- **Môi trường & Công nghệ:** NetworkX Steiner Tree / Text-to-SQL Compiler / PostgreSQL Dialect
- **Triệu chứng:** Câu SQL sinh ra bị lỗi `missing FROM-clause entry for table "f"` khi trình sinh SQL bên ngoài sử dụng alias khác hoặc dùng tên bảng đầy đủ.
- **Nguyên nhân gốc rễ:** Cạnh đồ thị trong `SteinerTreeBuilder` hardcode chuỗi `"f.office_id = office.id"`, giả định bắt buộc `fact_report_criteria` phải đặt alias là `f`.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không hardcode tiền tố bí danh tĩnh vào mệnh đề ON của đồ thị Steiner Tree.
  * ✅ **ALWAYS:** Sử dụng định dạng tham số hóa `{fact}.office_id = {office}.id` hoặc `{source}.col = {target}.col` để tầng sinh SQL ngoài tự do map alias theo ngữ cảnh.

---

### [TRAP-014] Lỗi Trôi Tên Thành Viên Enum (IntentEnum Member Name Drift)
- **Môi trường & Công nghệ:** Pydantic Enum / `IntentEnum` (`router_dto.py`)
- **Triệu chứng:** `AttributeError: type object 'IntentEnum' has no attribute 'SCHEMA_DISCOVERY'`.
- **Nguyên nhân gốc rễ:** Trong `router_dto.py`, enum định danh ý định khám phá danh mục được đặt tên là `SCOPE_DISCOVERY`, không phải `SCHEMA_DISCOVERY`. Việc gọi theo thói quen trực giác gây crash runtime.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không tự ý bịa tên enum hoặc suy đoán tên member mà không kiểm tra định nghĩa trong `router_dto.py`.
  * ✅ **ALWAYS:** Luôn dùng `IntentEnum.SCOPE_DISCOVERY` cho các bài toán khám phá danh mục/phạm vi dữ liệu DWH.

---

### [TRAP-015] Lỗi Độ Trễ Socket Timeout Của Redis Trong Môi Trường Dev/CI Offline
- **Môi trường & Công nghệ:** Redis Client (`redis-py`) / Pytest CI / Local Development
- **Triệu chứng:** Test suites chạy chậm bất thường (mất 60-90 giây dù chỉ chạy vài chục unit test in-memory).
- **Nguyên nhân gốc rễ:** Khi Redis service chưa bật (offline), mỗi lệnh gọi `redis.ping()` hoặc `redis.get()` mặc định treo theo `socket_connect_timeout` (2s) kèm cơ chế retry, nhân số lần gọi trong các fixtures/methods làm phình thời gian chạy test.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không khởi tạo Redis client mà không cấu hình thời gian timeout kết nối ngắn.
  * ✅ **ALWAYS:** Cấu hình `socket_connect_timeout=0.2s`, `retry_on_timeout=False`, kèm cơ chế Circuit Breaker ghi nhớ trạng thái offline tạm thời (5s) và fallback sang bộ nhớ RAM cục bộ (`_local_cache`) để phục vụ kiểm thử tức thì.

---

### [TRAP-016] Lỗi UnicodeEncodeError ('charmap' / cp1252) khi In Ký Tự Tiếng Việt trên Windows Console
- **Môi trường & Công nghệ:** Python 3.12+ / Windows PowerShell / Windows cmd (mã hóa mặc định cp1252 / cp437)
- **Triệu chứng:** `UnicodeEncodeError: 'charmap' codec can't encode character '\u1ede' in position 2: character maps to <undefined>`.
- **Nguyên nhân gốc rễ:** Trên môi trường Windows, `sys.stdout.encoding` mặc định có thể là `cp1252` thay vì `utf-8`. Khi script in các chuỗi tiếng Việt có dấu phức tạp hoặc emoji ra console, bộ mã hóa charmap không tìm thấy ký tự tương ứng và quăng ngoại lệ làm crash tiến trình.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không viết các script in ấn tiếng Việt độc lập mà không kiểm soát encoding của stdout/stderr.
  * ✅ **ALWAYS:** Luôn thêm khối cấu hình `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` và `sys.stderr.reconfigure(encoding='utf-8', errors='replace')` ở đầu tệp script Python trước bất kỳ lệnh `print()` nào.

---

### [TRAP-017] Lỗi Cắt Cụt Nested JSON Do Dùng Stop Sequence Trùng Với Cú Pháp Đóng Object (`}\n`)
- **Môi trường & Công nghệ:** OpenAI SDK / OpenRouter API / Structured JSON Decoding
- **Triệu chứng:** `pydantic_core._pydantic_core.ValidationError: 1 validation error for LLMRouterStructuredOutput: Invalid JSON: EOF while parsing an object at line ...`.
- **Nguyên nhân gốc rễ:** Cấu hình `stop=["}\n", "\n\n"]` nhằm ép mô hình dừng ngay khi kết thúc JSON. Tuy nhiên, khi schema có các object con lồng nhau (như `spatial_scope: {"location_name": "...", "admin_level": "..."}\n`), chuỗi `}\n` của object con kích hoạt stop condition của inference engine ngay lập tức! Kết quả là engine cắt đứt khi root object chưa kịp đóng, gây lỗi EOF Parse Error trên toàn bộ các câu hỏi có trường lồng nhau.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không dùng `stop=["}\n"]` khi schema có các object con lồng nhau.
  * ✅ **ALWAYS:** Chỉ dùng `response_format` JSON mode chuẩn của API hoặc để mô hình tự kết thúc theo cú pháp JSON hợp lệ.

---

### [TRAP-018] Lỗi Cắt Cụt Chuỗi JSON Do Cấu Hình `max_tokens` Quá Thấp Khi Thêm Trường Suy Luận (CoT / Scratchpad)
- **Môi trường & Công nghệ:** OpenAI SDK / OpenRouter API / Structured Output JSON
- **Triệu chứng:** `pydantic_core._pydantic_core.ValidationError: Invalid JSON: EOF while parsing a string at line ...`.
- **Nguyên nhân gốc rễ:** Cấu hình `max_tokens` là trần cắt đứt cứng của API server, không có tác dụng chỉ dẫn mô hình viết ngắn lại (như lưu ý chuẩn xác từ người dùng). Khi bổ sung trường suy luận tự hồi quy `thought_scratchpad` ở đầu schema JSON, mô hình cần tiêu tốn thêm ~100-200 completion tokens. Nếu giữ nguyên `max_tokens=400` quá chặt, phản hồi bị cắt ngang giữa chuỗi ký tự string, làm vỡ cú pháp JSON và gây lỗi EOF không thể parse.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không đặt `max_tokens` quá sát mức tối thiểu khi schema có chứa trường văn bản tự do hoặc suy luận CoT/Scratchpad.
  * ✅ **ALWAYS:** Cấu hình `max_tokens >= 800` để có headroom an toàn đầy đủ cho JSON object; đồng thời sử dụng chỉ dẫn trong `system_prompt` ("Suy luận 1-2 câu ngắn gọn") để kiểm soát độ dài sinh thực tế của mô hình.

---

### [TRAP-019] Lỗi Bất Tương Thích Định Danh Model Khi Fallback Giữa Các LLM Providers (OpenRouter vs ShopAIKey)
- **Môi trường & Công nghệ:** LLMGateway Fallback / OpenRouter vs ShopAIKey Proxy / Google GenAI SDK
- **Triệu chứng:** `503 model_not_found: No available channel for model google/gemini-3.8-flash under group gemini_fast (distributor)`.
- **Nguyên nhân gốc rễ:** OpenRouter yêu cầu tiền tố định danh nhà phát hành (ví dụ: `google/gemini-3.8-flash`, `google/gemini-2.5-flash-lite`). Trong khi đó, ShopAIKey proxy sử dụng API trực tiếp kiểu Google AI Studio, chỉ chấp nhận tên định danh thuần không có prefix (ví dụ: `gemini-3.7-flash`, `gemini-3.5-flash-lite`). Khi chuỗi fallback kích hoạt từ OpenRouter sang GoogleGenAIDriver mà truyền nguyên chuỗi model của OpenRouter, proxy sẽ báo lỗi không tìm thấy model.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không truyền trực tiếp chuỗi model name của provider này sang provider khác mà không qua tầng chuyển đổi định danh.
  * ✅ **ALWAYS:** Trong driver của từng provider (như `GoogleGenAIDriver._get_model`), luôn tự động bóc tách tiền tố `google/` và có bảng ánh xạ alias (như `gemini-3.8-flash` $\to$ `gemini-3.7-flash`, `gemini-2.5-flash-lite` $\to$ `gemini-3.5-flash-lite`) để bảo đảm fallback trơn tru không bao giờ văng 503.

---

### [TRAP-020] Lỗi Regex Thay Thế Bind Parameter Nuốt Toán Tử Ép Kiểu PostgreSQL (`::type` $\to$ `:'val'`)
- **Môi trường & Công nghệ:** Python Regex / PostgreSQL SQL Formatting / Text-to-SQL Dry-Run
- **Triệu chứng:** `syntax error at or near ":"` -> `SUM(NULLIF(TRIM(f.value), ''):'68') AS tong_dien_tich...`.
- **Nguyên nhân gốc rễ:** Khi thay thế bind parameters dạng `:param` bằng regex `r":([a-zA-Z_0-9]+)\b"`, regex vô tình khớp dấu hai chấm thứ hai trong toán tử ép kiểu của PostgreSQL `::numeric` hoặc `::text`, biến `::numeric` thành `:'68'` và làm gãy hoàn toàn cú pháp SQL.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không dùng regex `r":param\b"` hoặc `r":([a-zA-Z_0-9]+)\b"` mà không kiểm tra ký tự đứng trước.
  * ✅ **ALWAYS:** Bắt buộc dùng Negative Lookbehind `r"(?<!:):param\b"` và `r"(?<!:):([a-zA-Z_0-9]+)\b"` để không bao giờ nuốt toán tử `::` của PostgreSQL.

---

### [TRAP-021] Lỗi Ép Kiểu Ngầm Định Giữa Kiểu Số và Kiểu Chuỗi trên PostgreSQL (`character varying = integer`)
- **Môi trường & Công nghệ:** PostgreSQL 16 / psycopg2 / asyncpg / Data Warehouse
- **Triệu chứng:** `operator does not exist: character varying = integer` tại mệnh đề `WHERE f.year = 2026` hoặc `WHERE f.tenant_code = 68`.
- **Nguyên nhân gốc rễ:** Cột `year` và `tenant_code` trong bảng `fact_report_criteria` được thiết kế kiểu `VARCHAR(4)` và `VARCHAR(64)`. Khi script chuẩn hóa SQL kiểm tra `str(val).isdigit()` và bỏ qua dấu nháy đơn, PostgreSQL 16 từ chối so sánh trực tiếp giữa `varchar` và `integer` mà không có hàm ép kiểu tường minh.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không tự tiện coi các trường chỉ chứa số như `year` hoặc `tenant_code` là số nguyên literal không có nháy.
  * ✅ **ALWAYS:** Chỉ cho phép số nguyên unquoted cho các mệnh đề phân trang như `LIMIT :top_k` hoặc `OFFSET :offset`. Mọi trường mã hóa phân vùng nghiệp vụ (`year`, `tenant_code`, `code`) bắt buộc phải bọc trong nháy đơn `'2026'`, `'68'`.

---

### [TRAP-022] Lỗi TypeError Khi JSON Serialize Kết Quả Truy Vấn PostgreSQL (`date`, `Decimal`, `UUID`)
- **Môi trường & Công nghệ:** Python `json.dump` / psycopg2 / asyncpg / Test Suite Benchmarking
- **Triệu chứng:** `TypeError: Object of type date is not JSON serializable` (hoặc `Decimal`, `UUID`) làm sập tiến trình test khi xuất bản snapshot baseline JSON.
- **Nguyên nhân gốc rễ:** psycopg2 mặc định chuyển đổi các kiểu dữ liệu PostgreSQL như `DATE`, `NUMERIC`, `UUID` thành các đối tượng Python chuyên biệt (`datetime.date`, `decimal.Decimal`, `uuid.UUID`). Hàm `json.dump` mặc định của Python không hỗ trợ serialize các đối tượng này nếu không cung cấp tham số `default`.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không gọi `json.dump(...)` hoặc `json.dumps(...)` trên dữ liệu chứa sample rows từ CSDL mà không có custom serializer.
  * ✅ **ALWAYS:** Luôn chỉ định `default=str` khi gọi `json.dump(payload, f, default=str, ensure_ascii=False, indent=2)`.

---

### [TRAP-023] Lỗ Hổng Bảo Mật Cho Phép DDL/DML Đột Biến Ngầm Định Trong Mệnh Đề CTE & Subqueries
- **Môi trường & Công nghệ:** SQLGlot / Tầng AST Guardrail Module 02 & Module 05 / Text-to-SQL / PostgreSQL 16
- **Triệu chứng:** Câu lệnh chứa đột biến độc hại dạng `WITH malicious AS (DELETE FROM table RETURNING *) SELECT * FROM malicious` hoặc `INSERT INTO ... RETURNING ...` lọt qua tầng kiểm tra AST nếu chỉ assert câu lệnh gốc là `isinstance(stmt, exp.Select)`.
- **Nguyên nhân gốc rễ:** Trong chuẩn SQL-99 và dialect PostgreSQL 16, mệnh đề CTE (Common Table Expression) cho phép nhúng các biểu thức DML (`exp.Insert`, `exp.Update`, `exp.Delete`) có mệnh đề `RETURNING` bên trong khối `WITH`, trong khi câu lệnh tổng thể ngoài cùng vẫn là một `exp.Select` hợp lệ. Nếu hàm AST Guardrail chỉ kiểm tra root expression mà không duyệt đệ quy toàn bộ cây cú pháp AST (via `expression.find_all(...)`), các câu lệnh sửa đổi dữ liệu sẽ bị nhận diện sai là câu lệnh đọc thuần túy.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không chỉ kiểm tra node gốc `isinstance(statement, exp.Select)` để xác nhận câu lệnh an toàn.
  * ✅ **ALWAYS:** Bắt buộc dùng `ast.find_all(exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create, exp.Command, exp.Truncate)` duyệt đệ quy toàn bộ cây AST; nếu phát hiện bất kỳ node đột biến nào trong CTE, Subquery hay Window Function, lập tức chặn đứng với mã lỗi `SecurityViolationError` đảm bảo tỷ lệ vi phạm bảo mật bằng tuyệt đối **0.0%**.

---

### [TRAP-024] Lệch Pha Schema Giữa Catalog Seed Metadata và CSDL PostgreSQL Thực Tế
- **Môi trường & Công nghệ:** In-Memory DuckDB Catalog / PostgreSQL 16 DWH / Data Contracts / Schema Slice DDL
- **Triệu chứng:** Live DB Dry-Run thất bại với lỗi `column does not exist [42703]` (ví dụ: `column c.unit does not exist`, `column c.is_leaf does not exist`, hoặc `cannot cast type uuid to bigint`).
- **Nguyên nhân gốc rễ:** File seed `catalog_seed_metadata.json` được soạn thảo dựa trên bản thiết kế khái niệm (chứa các cột giả định như `criteria.unit`, `criteria.is_leaf`, kiểu `BIGINT` cho `criteria_id`), trong khi bảng vật lý trên PostgreSQL `vna_wom_dev` sử dụng kiểu `UUID` cho tất cả khóa ngoại và không có các cột trên. Khi DuckDB Catalog nạp metadata lệch pha này vào RAM và tiêm vào Schema Slice DDL, LLM cố gắng ép kiểu `c.id::bigint` hoặc `SELECT c.unit`, làm hỏng toàn bộ quá trình biên dịch Text-to-SQL.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không tự ý khai báo schema DDL trong metadata catalog bằng phỏng đoán mà không đối chiếu trực tiếp với `information_schema.columns` của CSDL live.
  * ✅ **ALWAYS:** Mọi metadata catalog (`catalog_seed_metadata.json`, `prompt_templates.py`, `schema_pruner.py`) bắt buộc phải được đồng bộ chính xác 100% với kiểu dữ liệu vật lý trên PostgreSQL (`UUID` cho ID, `VARCHAR` cho code/year, loại bỏ cột ảo không tồn tại).

---

### [TRAP-025] Bẫy So Khớp Mờ Chuỗi Ngắn (Token Set Ratio Short String Traps) trong Catalog Gây Nuốt Lệch Truy Vấn DWH
- **Môi trường & Công nghệ:** DuckDB In-Memory Catalog / RapidFuzz `fuzz.token_set_ratio` / Text-to-SQL Compiler / PostgreSQL DWH
- **Triệu chứng:** Câu hỏi tổng quan công vụ hoặc câu hỏi kiểm toán chất lượng dữ liệu bị trả về `0 rows` vì bộ sinh SQL cố tình lọc theo một mã chỉ tiêu rác không có dữ liệu thực tế (như `dulieuma213`, `phong_tam`, `du_lieu_moi`, `san_luong_cay_lau_nam`).
- **Nguyên nhân gốc rễ:** Thuật toán `fuzz.token_set_ratio` bỏ qua độ dài tương đối của câu hỏi và chỉ kiểm tra tập hợp token giao nhau. Khi người dùng đặt câu hỏi dài chứa các từ thông dụng ("dữ liệu", "phòng", "mới", "thống kê"), các chỉ tiêu thử nghiệm hoặc chuỗi test ngắn trong danh mục (ví dụ "dữ liệu mã 213", "phòng tạm", "dữ liệu mới") đạt điểm tương đồng rất cao (> 80%). Catalog trả về mã rác này cho Router/Compiler, khiến câu truy vấn SQL bị ép lọc theo chỉ tiêu không tồn tại số liệu thực tế trong bảng Fact thay vì truy vấn các bảng nghiệp vụ tương ứng (`report`, `collection_form`, hoặc tổng quan đơn vị).
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không sử dụng `token_set_ratio` trực tiếp trên danh mục chỉ tiêu mà không có danh sách blacklist các mã rác/mã test (`ignore_codes`).
  * ✅ **ALWAYS:** Bắt buộc bổ sung các mã chỉ tiêu rác, không có dữ liệu vào `ignore_codes` của Catalog. Đồng thời, thiết kế các nhánh Template biên dịch chuyên biệt cho các ý định nghiệp vụ DWH phổ biến (`REPORT_STATUS`, `COLLECTION_FORM`, `DATA_ANOMALY`, `USER_MISSION`, `ETL_FRESHNESS`) để định tuyến chính xác trước khi tra cứu chỉ tiêu đơn lẻ.

---

### [TRAP-026] Thiếu Thư Viện Chuyển Tiếp Runtime & Lỗi Import-Time Boot Khi Deploy Cloud (Render)
- **Môi trường & Công nghệ:** Render Cloud / FastAPI / Uvicorn / Python venv / Gitignore / HuggingFace ZeroGPU
- **Triệu chứng:** Web Service trên Render build thành công (`buildStatus: succeeded`) nhưng container lập tức thoát với mã lỗi `nonZeroExit: 1` ngay khi chạy lệnh khởi động `python -m uvicorn IPGov_Chatbot.main:app --host 0.0.0.0 --port $PORT`.
- **Nguyên nhân gốc rễ:**
  1. **Thiếu thư viện chuyển tiếp runtime:** Khi tách `requirements_render.txt` riêng nhằm triệt tiêu PyTorch (tiết kiệm ~2GB RAM để không vỡ giới hạn 512MB RAM free tier của Render), việc cắt gọt quá tay đã vô tình bỏ sót 6 package bổ trợ chuyển tiếp giữa các module (`PyJWT`, `jinja2`, `networkx`, `PyYAML`, `redis`, `SQLAlchemy`).
  2. **Bẫy `.gitignore` vô tình chặn file cache tĩnh:** File vector embedding danh mục chỉ tiêu (`criteria_embeddings_v2_name_only.npy` 512KB) có sẵn ở local nhưng nằm trong thư mục `IPGov_Chatbot/data/cache/` bị `.gitignore` chặn, không được đẩy lên GitHub. Khi Render khởi động container mới không tìm thấy file cache, catalog buộc phải gọi mạng tính toán lại 125 vector.
  3. **Anti-pattern "Import-Time Blocking Network Call":** Khởi tạo `warehouse_agent = WarehouseLangGraphAgent()` ngay ở phạm vi module-level global trong `warehouse_langgraph_agent.py`. Khi `uvicorn` nạp file lúc boot, nó kích hoạt gọi mạng đồng bộ tới HuggingFace Space ZeroGPU. Khi HF Space gặp sự cố/cold-start (`event: error; data: null`), exception văng ra làm sập container trước cả khi FastAPI kịp mở cổng `$PORT` để trả lời health check.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không bao giờ push mã nguồn lên remote git mà chưa kiểm tra cây import; không bao giờ đặt các tác vụ gọi I/O mạng đồng bộ tại module-level global scope; không để `.gitignore` chặn các file cache tĩnh phục vụ fast-boot.
  * ✅ **ALWAYS:** Trước mỗi lần `git push`, bắt buộc chạy thử nạp module trong môi trường `.venv` local: `.\.venv\Scripts\python.exe -c "import IPGov_Chatbot.main; print('Import Verified!')"` hoặc `.\.venv\Scripts\python.exe -m uvicorn IPGov_Chatbot.main:app --host 127.0.0.1 --port 8000`. Đồng thời, luôn thiết kế fallback an toàn sang BM25 / Fuzzy Matching trong catalog để container không bao giờ bị crash nếu dịch vụ AI bên ngoài gặp sự cố.



---

### [TRAP-027] Thiếu Cấu Hình Biến Môi Trường Trên Cloud Dẫn Tới Rơi Vào Nhánh Fallback SQL Rỗng
- **Môi trường & Công nghệ:** Render Cloud / FastAPI / LangGraph Autonomous Agent / Text-to-SQL
- **Triệu chứng:** Cùng một câu hỏi truy vấn dữ liệu (ví dụ: *'Danh mục các nhiệm vụ trọng tâm năm 2026 của tỉnh Lâm Đồng?'*), môi trường local trả về bảng 5 bản ghi nhưng trên Cloud Render trả về thông báo *'Yêu cầu tra cứu hiện chưa có bản ghi số liệu phù hợp trong kho DWH năm 2026'*.
- **Nguyên nhân gốc rễ:**
  1. Service Render Backend được tạo mới nhưng chưa được thiết lập danh sách biến môi trường (`env-vars` trả về rỗng `[]`). Do thiếu `OPENROUTER_API_KEY` và `GOOGLE_API_KEY`, các hàm gọi mô hình LLM (`_call_llm_cascade`) bị thất bại im lặng (silent fail) và trả về chuỗi rỗng `""`.
  2. Tầng Fallback SQL tự động kích hoạt nhưng logic mặc định chỉ xét bảng Fact `fact_report_criteria` thay vì các bảng nghiệp vụ liên quan (`mission`, `collection_form`, `user_mission`, `report`), dẫn đến câu lệnh SQL cố tình tìm kiếm theo chuỗi thô người dùng trên bảng Fact và trả về 0 dòng.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không bao giờ deploy backend lên Cloud mà không đồng bộ đầy đủ các API keys và thông số cấu hình từ `.env` local.
  * ✅ **ALWAYS:** Luôn cấu hình đầy đủ biến môi trường thông qua Render API / Dashboard. Đồng thời, thiết kế tầng Fallback Deterministic SQL nhận diện linh hoạt 5 bảng nghiệp vụ DWH (`mission`, `collection_form`, `user_mission`, `report`, `fact_report_criteria`) để hệ thống luôn trả về dữ liệu chính xác ngay cả khi LLM gặp sự cố gián đoạn mạng.

---

### [TRAP-047] Bẫy Mặc Định Phụ Thuộc Dịch Vụ Ngoài (Remote Cloud) Khi Chạy Môi Trường Local & Fallback Bất Đối Xứng
- **Môi trường & Công nghệ:** Hugging Face Space ZeroGPU / SentenceTransformer / ModelRegistry / Uvicorn Server Runner / FastAPI Lifespan
- **Triệu chứng:** Khi chạy server backend ở môi trường cục bộ bằng lệnh `.\.venv\Scripts\python.exe -m IPGov_Chatbot.run_server`, terminal in ra hàng loạt lỗi retry mạng:
  `⚠️ [RemoteHFEmbedding] Lỗi kết nối HF Space (thử lần 1/3): Gradio Space trả về error event: event: error data: null`
  `⚠️ [Warmup 2/5] Embedding model cảnh báo: Không thể kết nối HF Space sau 3 lần thử`
  Quá trình khởi động bị nghẽn 10-15s và tầng Embedding không sẵn sàng.
- **Nguyên nhân gốc rễ:**
  1. **Sensible Defaults Violation:** Biến cấu hình `USE_REMOTE_EMBEDDING` trong `backend/config.py` được gán giá trị mặc định là `"true"` (vốn được tối ưu tạm thời cho Render Free Tier 512MB RAM). Khi lập trình viên chạy local mà không khai báo biến này trong file `.env`, hệ thống tự động gán `True`, ép buộc kết nối ra Hugging Face Space bên ngoài dù ổ cứng máy trạm đã có sẵn 2.27 GB model cache.
  2. **Asymmetric Fallback Trap:** `ModelRegistry` chỉ thiết kế 1 chiều fallback (Local lỗi $\to$ Remote), nhưng khi người dùng chọn Remote mà dịch vụ bên ngoài bị ngủ (ZeroGPU Sleeping), tạm ngưng hoặc lỗi mạng thì hệ thống không có cơ chế tự động chuyển đổi ngược về Local In-Memory `SentenceTransformer`.
  3. **Thiếu cờ dòng lệnh CLI:** `run_server.py` thiếu các tùy chọn tường minh (`--local-embedding`, `--remote-embedding`), khiến lập trình viên không thể điều khiển chế độ nạp model qua CLI.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Tuyệt đối không để cấu hình mặc định (default fallback) của môi trường development phụ thuộc vào dịch vụ mạng bên ngoài (vi phạm nguyên tắc Offline-First & Locality Principle). Không thiết kế cơ chế fallback 1 chiều khi tích hợp dịch vụ Cloud.
  * ✅ **ALWAYS:**
    - Cấu hình mặc định trong code (`config.py`) và `.env` cho `USE_REMOTE_EMBEDDING` phải luôn là `False` (Local In-Memory). Chỉ kích hoạt Remote khi có cờ tường minh hoặc biến môi trường trên Cloud Render.
    - Cung cấp cờ CLI `--local-embedding` và `--remote-embedding` trong script runner `run_server.py` và in rõ ràng trạng thái lên banner khởi động.
    - Xây dựng cơ chế **Bi-directional Graceful Fallback**: Bất kể chọn Local hay Remote, nếu tầng được chỉ định gặp sự cố runtime, hệ thống phải tự động bắt lỗi và chuyển giao sang tầng còn lại để đảm bảo tính sẵn sàng 100%.

---

### [TRAP-048] Bẫy Nuốt Trường Trạng Thái (Key Drop) Trong LangGraph Do Thiếu Khai Báo Trong AgentState TypedDict
- **Môi trường & Công nghệ:** LangGraph 0.1+ / Python `typing.TypedDict` / FastAPI SSE Streaming
- **Triệu chứng:** Node thực thi (ví dụ `node_synthesize_response`) trả về dictionary chứa `{"tabular_data": {...}}`, nhưng kết quả đầu ra của đồ thị `graph.invoke()` hoặc `graph.stream()` hoàn toàn bị mất trường này, trả về `None` hoặc giá trị khởi tạo.
- **Nguyên nhân gốc rễ:** `AgentState` được kế thừa từ `typing.TypedDict` với danh sách thuộc tính tường minh. LangGraph lọc bỏ tất cả các key không được định nghĩa trong schema của `AgentState` khi hợp nhất (merge) output của node vào state chung.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Tuyệt đối không tự ý bổ sung key mới trong return dict của bất kỳ node LangGraph nào mà không cập nhật TypedDict `AgentState`.
  * ✅ **ALWAYS:** Bắt buộc khai báo đầy đủ mọi trường trạng thái mới trong `AgentState(TypedDict)` (ví dụ `tabular_data: Optional[Dict[str, Any]]`) đồng thời trong cả `run()` và `run_stream()` payload mapping.

---

### [TRAP-049] Bẫy Mã Hóa Ký Tự Tiếng Việt cp1252 Trên Windows Terminal / PowerShell CLI
- **Môi trường & Công nghệ:** Windows 10/11 / PowerShell 5.1/7 / Python 3.10+ `sys.stdout`
- **Triệu chứng:** `UnicodeEncodeError: 'charmap' codec can't encode character '\u1ed1' in position X: character maps to <undefined>`.
- **Nguyên nhân gốc rễ:** Mặc định `sys.stdout.encoding` trên Windows shell kế thừa mã trang OEM/ANSI cục bộ (`cp1252`), không thể encode toàn bộ bảng mã Unicode tiếng Việt khi in chuỗi hoặc serialize JSON `ensure_ascii=False` ra terminal.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không chạy script Python in dữ liệu tiếng Việt trực tiếp ra terminal Windows mà không cấu hình lại mã hóa stdout/stderr.
  * ✅ **ALWAYS:** Luôn đặt `if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")` ở đầu tất cả script CLI và test runners, hoặc khởi chạy với biến môi trường `PYTHONIOENCODING=utf-8`.

---

### [TRAP-050] Bẫy Ternary Unmount Component Streaming Khi Tín Hiệu Mạng Kết Thúc (Abrupt Streaming Snap)
- **Môi trường & Công nghệ:** React 18+ / Next.js App Router / SSE Streaming Text / requestAnimationFrame Animation Loop
- **Triệu chứng:** Người dùng chỉ kịp nhìn thấy 1-2 chữ đầu tiên xuất hiện dạng streaming, sau đó toàn bộ đoạn văn bản ập ra đột ngột trên màn hình mà không có hiệu ứng xả mượt mà theo nhịp đọc tự nhiên.
- **Nguyên nhân gốc rễ:**
  1. Component cha kiểm tra cờ mạng trực tiếp: `message.isStreaming ? <StreamingComponent /> : <SettledComponent />`. Khi backend gửi sự kiện `onDone`, `isStreaming` lập tức chuyển thành `false`.
  2. Việc này làm React unmount ngay lập tức `<StreamingComponent />`, hủy bỏ vòng lặp `requestAnimationFrame` và toàn bộ cơ chế Graceful Queue Drain Pacing bên trong hook `useSmoothStream`.
  3. `<SettledComponent />` được render lập tức với 100% nội dung `doneData.full_answer`.
  4. Ngoài ra, việc gán lại `lastTickRef.current = performance.now()` trên mỗi render của `rawContent` gây hiện tượng Clock Starvation, làm đóng băng đồng hồ đếm nhịp xả khi các token mạng đến dồn dập.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không điều kiện hóa việc unmount component streaming trực tiếp bằng cờ mạng `message.isStreaming`. Không hủy/reset đồng hồ RAF trên mỗi token mới đến.
  * ✅ **ALWAYS:**
    - Quản lý trạng thái chuyển giao riêng biệt `isAnimationSettled` trong component message. Component streaming tiếp tục duy trì và xả hết hàng đợi backlog theo nhịp đọc ổn định (~35-40ms) ngay cả khi `isStreaming === false`.
    - Chỉ chuyển giao sang view tĩnh khi component streaming phát tín hiệu callback `onSettled()`.
    - Bổ sung phím tắt `Escape` và sự kiện click để người dùng có thể chủ động bỏ qua animation khi muốn đọc toàn bộ nội dung ngay lập tức.

---

### [TRAP-051] Bẫy Ép Kiểu Numeric Mù Quáng Trong AST Enforcer Gây Lỗi function trim(numeric) does not exist
- **Môi trường & Công nghệ:** SQLGlot AST Transformation / PostgreSQL 16 Dialect / Text-to-SQL Dynamic Enforcer
- **Triệu chứng:** `ERROR: function trim(numeric) does not exist` khi câu truy vấn SQL chứa điều kiện kiểm tra chuỗi trên fact value (ví dụ: `WHERE TRIM(f.value) != '-'`).
- **Nguyên nhân gốc rễ:** Bộ duyệt AST (Visitor) thay thế mù quáng mọi node cột có tên `value` thành biểu thức `CAST(NULLIF(TRIM(value), '') AS DECIMAL)`. Nếu biểu thức gốc đã là `TRIM(f.value) != '-'`, việc thay thế tạo ra `TRIM(CAST(NULLIF(TRIM(value), '') AS DECIMAL)) <> '-'`. PostgreSQL không hỗ trợ hàm `trim()` trên kiểu dữ liệu số `numeric`/`decimal`, dẫn tới văng lỗi runtime 500.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không bao giờ thay thế ép kiểu số cho cột chuỗi mà không kiểm tra ngữ cảnh nút cha (parent node) trong cây AST.
  * ✅ **ALWAYS:** Chỉ bọc ép kiểu `NULLIF(TRIM(value), '')::numeric` khi node cột nằm trong ngữ cảnh tính toán số học (`exp.Add`, `exp.Sub`, `exp.Mul`, `exp.Div`), hàm tổng hợp (`exp.Sum`, `exp.Avg`), hoặc phép so sánh số. Bắt buộc bỏ qua khi node cột nằm trực tiếp dưới các hàm chuỗi (`Trim`, `Substring`, `Like`, `ILike`) hoặc phép kiểm tra rỗng (`IS NOT NULL`, `<> '-'`).

---

### [TRAP-052] Bẫy Nhầm Lẫn Giữa Dimension Plane và Fact Plane Gây Fallthrough Báo Thiếu Số Liệu Ảo
- **Môi trường & Công nghệ:** DWH Semantic Router / Canonical Normalizer / LangGraph Text-to-SQL / PostgreSQL 16
- **Triệu chứng:** Người dùng hỏi câu hỏi khám phá danh mục địa phương hoặc siêu dữ liệu (ví dụ: *"Ngoài tỉnh Lâm Đồng ra thì còn tỉnh nào khác không?"*, *"Hệ thống có những tỉnh nào?"*, *"Kho dữ liệu có những chỉ tiêu nào?"*), chatbot lại tổng hợp câu trả lời ngô nghê: *"Chỉ tiêu 'ngoài tỉnh lâm đồng ra thì còn tỉnh nào khác không' hiện chưa có bản ghi số liệu được phê duyệt trong kho DWH năm 2026"*.
- **Nguyên nhân gốc rễ:**
  1. **Thiếu Two-Plane Architecture:** Router mặc định coi mọi câu hỏi chưa khớp bảng nghiệp vụ cố định (`report`, `mission`, `collection_form`) là truy vấn số liệu trên bảng Fact (`fact_report_criteria`).
  2. Bảng `dwh_internal.province` không được cấp phép trong `ALLOWED_TABLES` của AST Enforcer và không được khai báo trong DuckDB Semantic Catalog.
  3. LLM Router hoặc Stream A Fallback cố ép toàn bộ câu hỏi vào việc tìm kiếm tên chỉ tiêu (Metric Disambiguation), dẫn đến so khớp mờ câu hỏi vào các chỉ tiêu không liên quan và trả về 0 dòng từ Fact Plane.
  4. **LangGraph Checkpointer Concurrency Trap:** `SqliteSaver` dựa trên module chuẩn `sqlite3` của Python chỉ hỗ trợ thực thi đồng bộ (`invoke()`) và văng lỗi `NotImplementedError` nếu gọi bất đồng bộ (`ainvoke()`).
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không bao giờ để các câu hỏi siêu dữ liệu, danh mục địa bàn hành chính (`province`, `deparment`, `office`, `ward`) rơi vào luồng Metric Disambiguation của bảng Fact. Không gọi `ainvoke()` trên LangGraph agent khi checkpointer là `SqliteSaver` đồng bộ.
  * ✅ **ALWAYS:**
    - Triển khai kiến trúc 2 mặt phẳng (**Two-Plane Architecture**): Dimension Plane (`province`, `criteria` metadata, `deparment`, `office`) và Fact Plane (`fact_report_criteria`, `report`, `user_mission`).
    - Bổ sung `METADATA_EXPLORATION` vào `CanonicalIntentEnum`, trích xuất `exclude_entities` (ví dụ `Lâm Đồng`) và `search_keyword`.
    - Biên dịch câu lệnh SQL trực tiếp sang bảng Dimension tương ứng (ví dụ: `SELECT code, name, is_activated FROM dwh_internal.province WHERE is_activated = true AND name NOT ILIKE '%Lâm Đồng%' ORDER BY name ASC`).
    - Định dạng câu trả lời rõ ràng dưới dạng Markdown table, giải thích rành mạch dữ liệu danh mục DWH đi kèm lưu ý về phạm vi số liệu thực tế hiện hành.

---

### [TRAP-053] Bẫy Regex Phép Tính Số Học Bắt Nhầm Chuỗi Ngày Tháng dd/mm/yyyy Thành Phép Chia Số Học
- **Môi trường & Công nghệ:** Python `re` / Canonical Semantic Normalizer / Stream A Deterministic Fallback
- **Triệu chứng:** Câu hỏi so sánh tăng trưởng hoặc tra cứu chỉ tiêu chứa mốc ngày tháng định dạng ngày/tháng/năm (ví dụ: *"Doanh thu bình quân 1 HTX nông nghiệp đợt 30/06/2026 vs 30/09/2026 tăng trưởng bao nhiêu %?"*) bị phân loại nhầm thành `OUT_OF_SCOPE` và trả về kết quả phép tính chia ngô nghê: `Kết quả phép tính: 30 / 6 = 5`.
- **Nguyên nhân gốc rễ:** Regex kiểm tra phép tính số học `\b(\d+)\s*([-+*/x]|cộng|trừ|nhân|chia)\s*(\d+)\b` khớp với chuỗi `30/06` trong `30/06/2026` và xem dấu gạch chéo `/` phân tách ngày tháng là toán tử chia số học.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Tuyệt đối không kiểm tra biểu thức số học trên chuỗi câu hỏi thô khi chưa lọc bỏ các mốc ngày tháng.
  * ✅ **ALWAYS:** Bắt buộc khử / mask các chuỗi ngày tháng trước khi chạy regex số học: `q_math = re.sub(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", " ", q_low)`.

---

### [TRAP-054] Bẫy Test Leakage & Hardcoding Câu Hỏi Test Case Vào Guardrail Thay Vì Sử Dụng NLU Model-Driven Dynamic Parser
- **Môi trường & Công nghệ:** Pre-Router Guardrails (`ScopePrechecker`) / Model-Driven NLU (`CanonicalSemanticNormalizer`) / Pytest Evaluation
- **Triệu chứng:** Câu hỏi toán học trong test case (như `"3 mũ 2 là nhiêu ?"`) pass test kiểm tra chữ số `"9"`, nhưng mọi câu hỏi toán học khác trong thực tế (như `"7 mũ 2"`, `"15 + 25"`, `"căn bậc 2 của 16"`) đều trả về thông báo ngoài phạm vi rỗng không có kết quả tính toán.
- **Nguyên nhân gốc rễ:** Lập trình viên/Agent sử dụng thang kiểm tra hardcode `if "3 mũ 2" in text: hint = "..."` bên trong tầng Guardrail để "hack điểm kiểm thử". Tầng guardrail này chặn đứng câu hỏi trước khi nó kịp chuyển giao cho NLU Model-Driven parser và bộ tính toán động, vi phạm nghiêm trọng Nguyên Tắc Chống Khớp Quá Mức Heuristic & Rò Rỉ Kiểm Thử (Rule 9).
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Tuyệt đối không hardcode câu hỏi hay đáp án mẫu của test case vào logic guardrail hay mã nguồn cốt lõi.

---

### [TRAP-055] Bẫy Cưỡng Bức Ghi Đè Ngữ Cảnh Đa Lượt (CQR Context Hijacking) Khi Dùng Heuristic Fallback Cho Câu Hỏi Độc Lập
- **Môi trường & Công nghệ:** LangGraph Conversational Agent / NeuralCQREngine / DiscourseStateTracker / Multi-turn Dialogue State Management
- **Triệu chứng:** Câu hỏi độc lập ở lượt sau (Turn 3) trong phiên hội thoại đa lượt bị cưỡng bức ghi đè thành câu hỏi của lượt trước (Turn 1). Ví dụ: Turn 1 hỏi toán học *"3 mũ 2 là nhiêu ?"*, Turn 2 hỏi quan hệ *"Chi cục phụ trách những nhiệm vụ nào ?"*, sang Turn 3 hỏi số liệu độc lập *"Số liệu chỉ tiêu liên kết sản xuất năm 2026 là bao nhiêu ?"* nhưng chatbot lại trả về kết quả toán học *"3 mũ 2 bằng 9"*.
- **Nguyên nhân gốc rễ:** `standalone_hint` được `DiscourseStateTracker` tạo ra cho mục đích gợi ý hòa mạng khi câu hỏi khuyết thực thể. Tuy nhiên, tại `warehouse_langgraph_agent.py`, logic điều phối được viết theo dạng:
  ```python
  if cqr_res.is_dependent and cqr_res.standalone_query:
      effective_query = cqr_res.standalone_query
  elif standalone_hint:
      effective_query = standalone_hint
  ```
  Khi câu hỏi của Turn 3 là độc lập (`cqr_res.is_dependent == False`), nhánh `if` bị bỏ qua và rơi vào `elif standalone_hint:`, dẫn tới việc `effective_query` bị cưỡng ép ghi đè bằng `standalone_hint` của chủ đề cũ, chiếm đoạt toàn bộ ngữ cảnh xử lý (Context Hijacking).
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Tuyệt đối không áp dụng `standalone_hint` ngoài phạm vi khi CQR đã phân định câu hỏi là độc lập (`is_dependent == False`).
  * ✅ **ALWAYS:** Chỉ cho phép sử dụng `standalone_hint` làm phương án dự phòng bên trong nhánh phụ thuộc:

---

### [TRAP-057] Bẫy Đảo Thứ Tự Ưu Tiên Giữa Khoảng Thời Gian (`date_from`) và Tháng Đơn Lẻ (`month_filter`) Trong Bộ Biên Dịch SQL
- **Môi trường & Công nghệ:** CanonicalSemanticNormalizer / SQL Synthesis / PostgreSQL 16
- **Triệu chứng:** Câu hỏi truy vấn tháng đơn lẻ (ví dụ: *"Trong tháng 9/2026 có những chỉ tiêu nào đã thu thập ?"*) bị sinh mệnh đề `f.report_date >= '2026-09-01' AND f.report_date::date <= '2026-09-30'` thay vì `EXTRACT(MONTH FROM f.report_date) = 9`.
- **Nguyên nhân gốc rễ:** Trong Stream B của bộ chuẩn hóa cú pháp, khi phát hiện tháng đơn lẻ, cả hai biến `month_filter` và cặp `(date_from, date_to)` đều được tính toán để dự phòng. Khi biên dịch SQL ở `compile_canonical_sql`, nhánh `if frame.date_from is not None` được đặt trước nhánh `elif frame.month_filter is not None`, làm nuốt mất điều kiện lọc tháng chuyên biệt.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không đặt nhánh khoảng ngày chung (`date_from`) lên trước bộ lọc tháng đơn lẻ (`month_filter`) khi cả hai có thể cùng tồn tại trong frame DTO.
  * ✅ **ALWAYS:** Luôn ưu tiên `if frame.month_filter is not None:` trước `elif frame.date_from is not None:` trong các bộ biên dịch SQL phục vụ Dimension Listing.

---

### [TRAP-058] Bẫy Bỏ Sót Tiền Tố Ngắn ("thông tin") Trong Regex Chuẩn Hóa Chủ Đề Làm Rõ (Clarification Engine)
- **Môi trường & Công nghệ:** ClarificationEngine / DuckDB Semantic Catalog / Ambiguous Metric Disambiguation
- **Triệu chứng:** Câu hỏi *"thông tin ocop"* không kích hoạt được Action Chips làm rõ đa nghĩa (AMBIGUOUS), trong khi *"ocop"* hoặc *"chỉ tiêu ocop"* kích hoạt bình thường.
- **Nguyên nhân gốc rễ:** Regex tiền tố chỉ loại bỏ `"thông tin về\s+"` mà không có nhánh cho `"thông tin\s+"` đơn lẻ. Do đó, chuỗi truyền vào DuckDB Catalog là `"thông tin ocop"` thay vì `"ocop"`, khiến bộ lọc BM25 / Fuzzy không vượt qua ngưỡng nhận diện đa nghĩa.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không giả định người dùng luôn dùng đầy đủ giới từ ("thông tin về", "dữ liệu về").
  * ✅ **ALWAYS:** Luôn đưa cả dạng đầy đủ và dạng rút gọn vào regex tiền tố: `r"^(?:cho tôi xem|cho xem|xem|tra cứu|thống kê|chỉ tiêu|tình hình|dữ liệu về|thông tin về|thông tin)\s+"`.

---

### [TRAP-059] Bẫy Bỏ Sót Chữ Số 0 Đứng Trước (Leading Zero) Trong Regex Bóc Tách Tháng / Năm Định Dạng Tiếng Việt
- **Môi trường & Công nghệ:** `CanonicalSemanticNormalizer` (`_extract_stream_b_deterministic`) / Regex Temporal Extraction / Python
- **Triệu chứng:** Câu hỏi `"Tháng 01/2024 có chỉ tiêu nào được thu thập ?"` chỉ trích xuất được `year_code = '2024'`, trong khi `month_filter` bị rỗng (`None`). Do đó, câu lệnh SQL sinh ra bị thiếu điều kiện lọc tháng và Agent trả về thông báo rỗng cấp năm (`"trong năm 2024"`) thay vì cấp tháng (`"trong tháng 01/2024"`).
- **Nguyên nhân gốc rễ:** Regex trích xuất tháng dạng số dùng `[1-9]|1[0-2]`, chỉ khớp tháng 1 chữ số (`1` đến `9`) hoặc `10, 11, 12`, hoàn toàn không khớp các tháng có số 0 đệm đầu (`01` đến `09`). Tương tự, regex dải tháng (`m_range_num`, `m_end_num`) và regex gạch chéo (`m_month_slash`) cũng thiếu `0?` hoặc `0[1-9]`.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không sử dụng `[1-9]|1[0-2]` khi trích xuất tháng số trong ngôn ngữ tự nhiên.
  * ✅ **ALWAYS:** Bắt buộc sử dụng `(0?[1-9]|1[0-2])` để bao hàm cả dạng có số 0 đệm (`01` đến `09`) và không có số 0 đệm (`1` đến `9`). Đồng thời chấp nhận các ký tự phân tách ngày tháng linh hoạt `[/.-]`.

---

### [TRAP-060] Bẫy Lời Chào Ghép Nuốt Câu Hỏi Nghiệp Vụ & Lỗi Phân Vùng CTE Window Function Thiếu COALESCE(office_id)
- **Môi trường & Công nghệ:** Intent Router / Cognitive Planner / PostgreSQL 16 DWH / Kimball CTE Window Functions
- **Triệu chứng:**
  1. Câu hỏi lịch sự chứa lời chào (ví dụ: *"Chào bạn, cho tôi biết tình hình sản lượng muối năm 2026?"*) bị router nuốt thành `GREETING_FAREWELL`, trả về lời chào giới thiệu hệ thống thay vì truy vấn kho DWH. Ngược lại, câu chào đa âm tiết lịch sự (*"Cảm ơn bạn, tạm biệt nhé"*) có > 3 từ lại bị văng SQL rác.
  2. Câu lệnh tổng hợp Additive metrics đa phòng ban bị tính sai hoặc nhân dòng do `PARTITION BY TRIM(LOWER(f.name))` không kèm `office_id`, hoặc nếu kèm `office_id` thô thì các bản ghi cấp tỉnh có `office_id IS NULL` bị tách lẻ không kiểm soát.
- **Nguyên nhân gốc rễ:**
  1. Router dùng điều kiện kiểm tra tiền tố naive `q_low.startswith(...)` mà không kiểm tra độ dài nội dung thực tế phía sau hoặc không bóc tách tiền tố/đại từ công vụ (`chatbot`, `đồng chí`, `bạn`).
  2. Phân vùng Window Function thiếu `COALESCE(f.office_id, '00000000-0000-0000-0000-000000000000'::uuid)` khiến 34 bản ghi cấp tỉnh không được gom nhóm tất định.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không dùng `q_low.startswith(p)` để kết luận câu hỏi là greeting nếu chưa kiểm tra phần nội dung còn lại (`is_pure_courtesy`). Không dùng `PARTITION BY TRIM(LOWER(f.name))` trần trụi cho Additive multi-office metrics.
  * ✅ **ALWAYS:** Sử dụng Dual-Gate (`is_pure_courtesy` + vocative stripping) để bóc tách đại từ/tiền tố chào hỏi và truyền câu hỏi nghiệp vụ sạch vào DWH. Luôn cưỡng chế `PARTITION BY TRIM(LOWER(f.name)), COALESCE(f.office_id, '00000000-0000-0000-0000-000000000000'::uuid)` trên toàn bộ 5 Kimball Archetypes.

---

### [TRAP-061] Bẫy Bất Đồng Nhất Tên CTE (ranked_facts vs ranked_fact), Lỗi Ghi Đè Hàm (Method Shadowing) trong DuckDB Catalog & Lỗi Bỏ Sót Dải Lũy Kế Stream B
- **Môi trường & Công nghệ:** `CanonicalSemanticNormalizer` / `WarehouseLangGraphAgent` / `DuckDBRAMCatalog` / Full Pipeline Integration
- **Triệu chứng:**
  1. Thay đổi tên CTE từ `ranked_facts` sang `ranked_fact` làm gãy các bộ test hồi quy cũ assert chuỗi CTE chuẩn.
  2. Khai báo 2 lần hàm `resolve_metric_id` trong cùng 1 file `duckdb_semantic_catalog.py` (dòng 1502 và dòng 1668), hàm thứ hai ghi đè hàm thứ nhất làm mất kiểm tra `is_dimension_query`, dẫn tới câu hỏi danh mục bị nhận diện nhầm thành tra cứu điểm chỉ tiêu đơn lẻ (`METRIC_POINT_INQUIRY`).
  3. Stream B trích xuất thời gian bỏ sót mẫu câu lũy kế "từ tháng X đến hiện tại / đến nay", khiến câu hỏi bị rơi vào tháng đơn lẻ hoặc năm rỗng.
- **Nguyên nhân gốc rễ:**
  1. Không chuẩn hóa tên CTE thống nhất dạng số nhiều `ranked_facts` trên toàn bộ pipeline (cả trong `canonical_normalizer.py` và `warehouse_langgraph_agent.py`).
  2. Trùng tên hàm trong codebase Python không qua static type check linter, dẫn tới hàm sau đè hàm trước làm mất logic kiểm tra Dimension Query.
  3. Regex Stream B chỉ có dải 2 đầu số cố định ("từ tháng X đến tháng Y") mà thiếu nhánh cho thời điểm hiện tại ("đến nay", "đến hiện tại").
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không đổi tên CTE chuẩn `ranked_facts` sang số ít; Không định nghĩa trùng tên phương thức trong class Catalog; Không hardcode dải thời gian hay từ khóa viết tắt.
  * ✅ **ALWAYS:** Chuẩn hóa `WITH ranked_facts AS (` trên toàn bộ pipeline; Kiểm tra AST định kỳ để chống method shadowing; Bổ sung regex lũy kế `(?:từ\s+)?tháng\s+(X)\s*(?:đến|tới|-)\s*(?:thời\s+điểm\s+)?(?:hiện\s+tại|nay)` và map sang `date_from` đầu tháng X đến ngày chốt sổ gần nhất (`2026-09-30`).

---

### [TRAP-062] Bẫy Va Chạm Thuộc Tính Đồng Âm Trong Cây Phân Cấp Kimball Khi Thiếu Cột Nhóm Cha (Multi-Category Disambiguation)
- **Môi trường & Công nghệ:** `CanonicalSemanticNormalizer` (`compile_canonical_sql`) / `WarehouseLangGraphAgent` / PostgreSQL 16 DWH / Kimball Dimensional Modeling
- **Triệu chứng:**
  1. Trong CSDL DWH, tồn tại 17 nhóm chỉ tiêu lá có cùng tên gọi (ví dụ: *"Chăn nuôi"*, *"Trồng trọt"*, *"Đang hoạt động"*, *"Thành lập mới"*, *"Thành viên"*...) thuộc các nhóm phân loại cha khác nhau (HTX, THT, Trang trại, LHHTX). Khi bảng kết quả hiển thị danh mục chỉ có 5 cột (thiếu cột *Nhóm chỉ tiêu*), người dùng nhìn thấy nhiều dòng có cùng một tên gọi nhưng số liệu khác nhau mà không thể biết dòng nào thuộc lĩnh vực/loại hình nào.
  2. Các bộ kiểm thử chấp nhận câu lệnh `assert 5_cols in ans or 6_cols in ans` (test tampering/weakening) khiến hiện tượng thoái lui về bảng 5 cột bị che khuất và lọt qua CI.
- **Nguyên nhân gốc rễ:**
  1. Trong CTE `ranked_facts`, bảng `fact_report_criteria` chứa trường `parent_criteria_id` trỏ tới `criteria.id` của cấp cha, nhưng câu `SELECT` bên ngoài không `LEFT JOIN dwh_internal.criteria` để trích xuất tên nhóm cha `p.name` thành cột `nhom_chi_tieu`.
  2. Bảng Markdown và cấu trúc DTO `tabular_data` trong `warehouse_langgraph_agent.py` chỉ định nghĩa 5 cột (`stt`, `item`, `value`, `office`, `mission`), bỏ sót thuộc tính nhóm phân loại cha theo chuẩn Kimball Conformed Hierarchical Dimensions.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không hiển thị danh mục chỉ tiêu đa phân cấp mà thiếu trường ngữ nghĩa phân cấp cha (`nhom_chi_tieu` / `category`); Không viết assert lỏng lẻo dạng `assert 5_col or 6_col` làm suy yếu khả năng phát hiện lỗi hồi quy.
  * ✅ **ALWAYS:** 
    1. Trong CTE `ranked_facts` của `DIMENSION_LISTING`, bắt buộc chọn `f.parent_criteria_id` và `LEFT JOIN dwh_internal.criteria p ON rf.parent_criteria_id = p.id` để lấy `COALESCE(p.name, 'Chỉ tiêu chung') AS nhom_chi_tieu`.
    2. Cưỡng chế bảng Markdown 6 cột chuẩn: `| STT | Tên chỉ tiêu | Nhóm chỉ tiêu | Giá trị mới nhất | Đơn vị thực hiện | Nhiệm vụ trọng tâm |` và chèn cột `category` ở vị trí thứ 3 (index 2) trong `tabular_data["columns"]`.
    3. Bộ kiểm thử bắt buộc assert chặt chẽ tiêu đề bảng 6 cột và kiểm tra sự hiện diện của trường `category` trong từng dòng dữ liệu.

---

### [TRAP-063] Bẫy Cắt Cụm Dữ Liệu Warehouse Bởi LIMIT 50 Ngầm & Lát Cắt Python (rows[:50] / PAGE_SIZE=5) Kèm Bỏ Sót Mẫu Câu Lũy Kế Đầu Năm (Year-to-Date)
- **Môi trường & Công nghệ:** `CanonicalSemanticNormalizer` / `ASTEnforcerService` / `WarehouseLangGraphAgent` / `SmartTable.tsx`
- **Triệu chứng:**
  1. Câu hỏi *"Số lượng chỉ tiêu thu thập được từ đầu năm tới nay"* chỉ trả về 50 bản ghi, thấp hơn giai đoạn *"3/2026 - 06/2026"* (114 bản ghi).
  2. Trên giao diện React UI, bảng `<SmartTable>` chỉ hiển thị 5 dòng mỗi trang (`PAGE_SIZE = 5`), cắt cụt khả năng đối soát trực quan toàn bộ danh mục.
- **Nguyên nhân gốc rễ:**
  1. Stream B (`_extract_stream_b_deterministic`) chưa có mẫu regex cho cụm lũy kế đầu năm (`"từ đầu năm tới nay"`, `"đầu năm đến nay"`, `"lũy kế từ đầu năm"`) và dải tháng gạch chéo (`"3/2026 - 06/2026"`). Khi câu hỏi rơi vào nhánh mặc định hoặc LLM fallback, `CanonicalQueryFrameDTO.limit` gán mặc định `50`, kết hợp `ASTEnforcerService` tự động tiêm `LIMIT 500` và `node_synthesize_response` cắt `rows[:50]`.
  2. `DuckDBSemanticCatalog.is_dimension_query` thiếu từ khóa `"đầu năm"`, `"tới nay"`, `"đến nay"`, `"giai đoạn"` trong `has_time_term`, và `_extract_streams_llm` chưa truyền `stream_b` vào `_extract_stream_a_deterministic`.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không gán cứng `limit = 50` mặc định trong `CanonicalQueryFrameDTO`; Không cắt `rows[:50]` / `rows[:100]` trong `warehouse_langgraph_agent.py`; Không chia trang cứng 5 dòng (`PAGE_SIZE = 5`) trong `SmartTable.tsx`.
  * ✅ **ALWAYS:**
    1. Đặt `CanonicalQueryFrameDTO.limit: Optional[int] = None` (chỉ thêm `LIMIT` vào SQL khi người dùng yêu cầu Top-N tường minh).
    2. Bổ sung đầy đủ mẫu regex Year-to-Date (`từ đầu năm tới nay`, `đầu năm đến tháng X`) và dải `mm/yyyy - mm/yyyy` trong Stream B.
    3. Hiển thị toàn bộ bản ghi trả về từ Warehouse trong khung cuộn dọc `max-h-[520px] overflow-y-auto` có cố định tiêu đề `sticky top-0`.

---

### [TRAP-064] Bẫy Độ Trễ Hiệu Ứng Gõ Chữ Từng Ký Tự (Typewriter ms Delay) Trên Khối Bảng Dữ Liệu Warehouse
- **Môi trường & Công nghệ:** `WarehouseLangGraphAgent.run_stream` / `FluidTextStream.tsx` / `useSmoothStream.ts`
- **Triệu chứng:**
  - Khi trả về bảng dữ liệu Warehouse lớn (114 dòng x 6 cột $\approx 15.000$ ký tự Markdown), vòng lặp `for line in answer_lines: await asyncio.sleep(0.005)` ở Backend cộng với bộ đệm `useSmoothStream` (~14–42ms/nhịp) ở Frontend khiến bảng dữ liệu mất nhiều giây để vẽ từng ký tự và bị nhảy bố cục liên tục.
- **Nguyên nhân gốc rễ:**
  - Áp dụng chung hiệu ứng gõ chữ từng ký tự (dành cho văn bản hội thoại ngắn) lên toàn bộ khối dữ liệu có cấu trúc (Markdown Table, Card 5 trường, khối `<details>` SQL).
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không chia nhỏ từng dòng Markdown kèm `asyncio.sleep` trong `run_stream` của Backend; Không chạy hiệu ứng gõ chữ `ms` trên bảng dữ liệu hoặc thẻ chỉ tiêu Warehouse.
  * ✅ **ALWAYS:** Phát toàn bộ `final_answer` trong 1 sự kiện `token` duy nhất từ Backend; Tại `FluidTextStream.tsx`, tách phần câu dẫn ngắn (`introText`) và phần khối dữ liệu Warehouse (`warehouseBlock`) để render tức thì (`0ms`) toàn bộ bảng/thẻ số liệu và khối SQL ngay khi nhận phản hồi.

---

### [TRAP-065] Bẫy Ép Kiểu `DECIMAL` Trực Tiếp Trên Cột `f.value` Chứa Ký Tự `'-'` & Va Chạm Thực Thể Tổ Chức - Nhiệm Vụ - Tháng Viết Bằng Chữ
- **Môi trường & Công nghệ:** `ASTEnforcerService` / `CanonicalSemanticNormalizer` / `DuckDBSemanticCatalog` / PostgreSQL 16 (`vna_wom_dev`)
- **Triệu chứng:**
  1. Khi truy vấn các chỉ tiêu lá có giá trị `f.value = '-'` (chưa cập nhật số liệu phê duyệt, thuộc kịch bản `SC-2.3`), `ASTEnforcerService` (TẦNG 4.2) tự động bọc `NULLIF(TRIM(f.value), '')::numeric` hoặc `REGEXP_REPLACE(TRIM(f.value), '[^0-9.-]', '', 'g')::decimal`, giữ lại dấu `'-'` đơn độc và gây lỗi runtime PostgreSQL `invalid input syntax for type numeric: "-"`.
  2. Tên đơn vị hành chính chứa chuỗi con trùng tên nhiệm vụ (như `"Chi cục Phát triển nông thôn"`, `"Phòng Kinh tế hợp tác và Phát triển nông thôn"`) bị `resolve_mission()` nhận diện nhầm thành `target_mission = "Phát triển nông thôn"`, làm rớt mất 7 chỉ tiêu thuộc nhiệm vụ `"Diêm nghiệp"` do cùng đơn vị đó quản lý (`107` dòng thay vì `114` dòng).
  3. Tháng viết bằng chữ `"tháng ba"` (ví dụ `"ngày 10 tháng ba năm 2026"`) bị bộ trích xuất chức vụ khớp nhầm với mã vị trí `"BA"` trong bảng `dwh_internal.users`, hoặc từ `"hợp tác xã"` kích hoạt nhầm bộ lọc đơn vị hành chính cấp `"xã"` (`dwh_internal.ward`).
- **Nguyên nhân gốc rễ:**
  1. Tầng AST Enforcer ép kiểu số vô điều kiện lên cột `value` mà không kiểm tra mẫu số hợp lệ `^-?[0-9]+(\.[0-9]+)?$`.
  2. Chưa loại bỏ (mask/strip) span tên đơn vị tổ chức (`Sở/Phòng/Chi cục ... Phát triển nông thôn`) và cụm từ ghép (`hợp tác xã`, `liên hiệp hợp tác xã`) trước khi chạy bộ dò `mission`, `ward`, và `position`.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không ép kiểu `f.value::numeric` trực tiếp nếu chưa qua biểu thức chính quy kiểm tra chuỗi số; Không quét `mission`, `ward`, `position` trên chuỗi thô chưa mask tên cơ quan/tổ chức và tháng viết bằng chữ.
  * ✅ **ALWAYS:**
    1. Giữ `f.value AS gia_tri` ở dạng chuỗi (`TEXT`) tại mệnh đề `SELECT` ngoài cùng và chỉ dùng `CASE WHEN TRIM(f.value) ~ '^-?[0-9]+(\.[0-9]+)?$' THEN CAST(TRIM(f.value) AS DECIMAL) ELSE NULL END` bên trong các hàm tổng hợp hoặc `ORDER BY`.
    2. Chuẩn hóa tháng viết bằng chữ (`tháng giêng`..`tháng chạp`, `tháng một`..`tháng mười hai`) sang số trước khi trích xuất ngày/tháng, đồng thời mask tên đơn vị (`Chi cục/Phòng/Sở ... Phát triển nông thôn`) và cụm `hợp tác xã` trước khi trích xuất `mission` và `ward`.

---

### [TRAP-066] Bẫy Escape HTML Toàn Cục Làm Vỡ Bảng Markdown, Thẻ `<details>` SQL & Cộng Dồn Trạng Thái `tree_modal` Giữa Các Lượt Chat Trên `/bench`
- **Môi trường & Công nghệ:** `IPGov_Chatbot/frontend/role_selector_bench.html` / `SmartTable.tsx` / `WarehouseLangGraphAgent`
- **Triệu chứng:**
  1. Trên giao diện `/bench`, hàm `formatResponseWithTreeButtons(rawText)` gọi `escapeHtml(rawText)` lên toàn bộ chuỗi phản hồi hoặc xóa bỏ dòng `<details>`/`<summary>`, khiến bảng Markdown hiện ký tự ống `|` thô, câu lệnh SQL bị đổ tràn ra màn hình, và thực thể `&nbsp;` hiển thị nguyên chữ `&nbsp;`.
  2. Nút `- (Xem chi tiết con)` không truyền `rootId` của dòng chỉ tiêu Cấp 1 và biến `window.__latestTreeModalData` dùng `Object.assign` cộng dồn qua nhiều lượt hỏi, khiến khi bấm mở Pop-up Tree Modal ở câu hỏi sau vẫn hiển thị lẫn cây chỉ tiêu của câu hỏi trước.
- **Nguyên nhân gốc rễ:**
  1. Xử lý chuỗi Markdown bằng `escapeHtml` đơn thuần thay vì tách khối bảng Markdown (`<table>`), khối `<details><summary>...</summary>...</details>` và định dạng inline.
  2. Thiếu cơ chế định danh `rootId` (theo `criteria_id` hoặc tên chuẩn hóa của chỉ tiêu Cấp 1 ở cột 2) trong sự kiện `onclick="openCriteriaTreeModal(rootId)"` và không reset `window.__latestTreeModalData` theo từng thông điệp.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không dùng `Object.assign` cộng dồn dữ liệu `tree_modal` cũ qua các lượt chat; Không dùng thực thể `&nbsp;` trong văn bản Markdown gợi ý chip; Không để nút mở Pop-up gọi `openCriteriaTreeModal()` không tham số.
  * ✅ **ALWAYS:** Reset `window.__latestTreeModalData` theo dữ liệu `tabular_data.tree_modal` mới nhất, truyền `rootId` của đúng dòng chỉ tiêu Cấp 1 vào `openCriteriaTreeModal(rootId)`, bảo toàn khối thu gọn `<details>` cho SQL, và cấu hình Pop-up Modal có thanh cuộn dọc (`overflow-y-auto`, `max-h-[80vh]`) cùng 2 cơ chế đóng (nút `'✕'` góc phải trên và click vùng nền backdrop bên ngoài).

---

### [TRAP-067] Bẫy Ghi Đè `tabular_data` Bằng 2 Bảng Trong `REQ-Q01` & Biến Đếm Render Khả Biến Trong React 19 StrictMode
- **Môi trường & Công nghệ:** `IPGov_Chatbot/modules/mod03_router/warehouse_langgraph_agent.py` / `IPGov_Chatbot/frontend/src/components/chat/MessageItem.tsx` / `SmartTable.tsx`
- **Triệu chứng:**
  1. Khi hỏi câu hỏi Loại 1 (`REQ-Q01`: `"Liệt kê số lượng các chỉ tiêu từ tháng 2 đến tháng 8 năm nay"`), giao diện Next.js (`http://localhost:3000`) hiển thị **2 bảng chồng nhau** đều có 114 bản ghi và sai bộ cột quy định trong `output.md` Mục 2.1.C (`STT | Tên chỉ tiêu Cấp 1 | Loại cấu trúc | Giá trị mới nhất | Đơn vị thực hiện | Nhiệm vụ trọng tâm`).
  2. Nếu dùng biến đếm cục bộ khả biến `let tableRenderCount = 0` bên trong thân component `MessageItem` để chỉ truyền `tabularData` cho bảng đầu tiên, trong môi trường phát triển của **React 19 StrictMode** (hoặc khi `useTypingEffect` kích hoạt re-render), component bị gọi hàm 2 lần khiến `tableRenderCount` tăng lên `2` ở lượt render thứ hai và làm mất hoàn toàn `tabularData` (bao gồm `tree_modal`).
- **Nguyên nhân gốc rễ:**
  1. Backend `warehouse_langgraph_agent.py` vừa chèn 2 bảng Markdown vào `answer` (Bảng Cấp 1 + Bảng phẳng 114 dòng), vừa đặt `tabular_data["rows"] = formatted_rows` (114 dòng phẳng). Ở Frontend, `MessageItem.tsx` truyền cùng một `message.tabularData` vào mọi thẻ `<table>` trong `ReactMarkdown`, và `SmartTable.tsx` ưu tiên render `data.rows` thay vì `children` Markdown nên cả 2 bảng đều bị ghi đè thành bảng phẳng 114 dòng.
  2. Biến đếm khả biến đặt trong closure của React functional component vi phạm tính thuần khiết (purity) khi React StrictMode double-invoke render.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không sinh 2 bảng Markdown kèm `tabular_data.rows` lệch cấu trúc cho câu hỏi `REQ-Q01`; Không dùng biến đếm khả biến (`let count = 0`) tăng dần bên trong custom component của `ReactMarkdown`.
  * ✅ **ALWAYS:**
    1. Với `REQ-Q01`, chỉ phát ra **duy nhất 1 bảng Cấp 1** đúng 6 cột chuẩn của `IPGov_Chatbot/docs/output.md` Mục 2.1.C, gán `tabular_data["rows"] = l1_formatted` (9 dòng Cấp 1), và lưu tổng số dòng phẳng vào `tabular_data["raw_fact_count"] = 114`.
    2. Trong `SmartTable.tsx`, sử dụng `w-fit`, `py-2 px-3`, căn trái toàn bộ cột, và vẽ nhánh nối phân cấp kèm đầu mũi tên SVG (`▶`) tới từng box chỉ tiêu con trong Pop-up Tree Modal.

---

### [TRAP-068] Bẫy Đặt Biểu Thức `CASE WHEN` Loại Bỏ Giá Trị `'0'` Lên Trước `f.report_date DESC` Trong `ROW_NUMBER()` & Dư Thừa Cột/JOIN Trong SQL Đơn Chỉ Tiêu
- **Môi trường & Công nghệ:** `CanonicalSemanticNormalizer.compile_canonical_sql` / `DuckDBSemanticCatalog._hydrate_catalog` / `WarehouseLangGraphAgent.execute_safe_sql`
- **Triệu chứng:**
  1. Chỉ tiêu `'Tổng hộ sản xuất muối'` (`tong_ho_san_xuat_muoi`) có bản ghi phê duyệt mới nhất vào ngày `2026-07-31` với `value = '0'`, nhưng hệ thống lại trả về giá trị cũ `660` của ngày `2026-06-30`.
  2. Câu lệnh SQL đơn chỉ tiêu bị phình to không cần thiết do nhân đôi cột hiển thị (`gia_tri` vs `gia_tri_moi_nhat`, `ngay_bao_cao` vs `ngay_bao_cao_moi_nhat`, `ten_phong_ban` vs `ten_van_phong`), nối thừa bảng `dwh_internal.criteria gp` cấp ông, lồng correlated subquery `c_ord.code` trong `ORDER BY`, và bị `execute_safe_sql` tiêm thêm `LIMIT 500` ở cuối CTE `WITH ranked_facts`.
- **Nguyên nhân gốc rễ:**
  1. Trong mệnh đề `ROW_NUMBER() OVER (... ORDER BY ...)` của `ranked_facts` và CTE `fact_nonzero` của DuckDB Catalog, biểu thức `CASE WHEN ... AND NOT (f.mission_name = 'Diêm nghiệp' AND TRIM(f.value) IN ('0', '0.0')) THEN 0 ELSE 1 END ASC` được đặt đứng trước `f.report_date DESC NULLS LAST`, làm đảo thứ tự thời gian thực tế trong Kho dữ liệu.
  2. Chưa thống nhất một chuẩn alias duy nhất giữa tầng sinh SQL và tầng đọc kết quả, đồng thời `execute_safe_sql` gọi `_sanitize_single_sql_ast` với tham số mặc định `inject_limit=True`.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Tuyệt đối không đặt điều kiện lọc/ưu tiên giá trị khác `'0'` đứng trước `f.report_date DESC NULLS LAST, f.version DESC NULLS LAST` trong `ROW_NUMBER()`; Không nhân đôi cột cùng ý nghĩa trong `SELECT`; Không tiêm `LIMIT 500` vào truy vấn đã khử trùng lặp bằng `WITH ranked_facts ... WHERE rn = 1`.
  * ✅ **ALWAYS:**
    1. Xếp hạng bản ghi mới nhất thuần túy theo `ROW_NUMBER() OVER (PARTITION BY f.criteria_id, f.office_id ORDER BY f.report_date DESC NULLS LAST, f.version DESC NULLS LAST)`.
    2. Chỉ loại bỏ chuỗi rỗng `''` và ký tự `'-'` khi kiểm tra giá trị chưa cập nhật; bảo toàn `'0'` và `'0.0'` là số liệu thống kê hợp lệ.
    3. Thống nhất 6 cột tối giản chuẩn `/ponytail` cho truy vấn chỉ tiêu: `ten_chi_tieu`, `gia_tri_moi_nhat`, `ten_nhiem_vu`, `ten_van_phong`, `ngay_bao_cao_moi_nhat`, `nhom_chi_tieu`.

---

### [TRAP-069] Bẫy Nhân Đôi Nội Dung Chỉ Tiêu Cha (`SC-2.4`) & Sai Lệch Thuật Toán Khoảng Cách Ngày Cụ Thể `[A, B]` vs. Khoảng Thời Gian (`SC-2.2`)
- **Môi trường & Công nghệ:** `CanonicalSemanticNormalizer.compile_canonical_sql` / `WarehouseLangGraphAgent.node_synthesize_response` / `MessageItem.tsx` / `QuickActionChips.tsx`
- **Triệu chứng:**
  1. Khi hỏi chỉ tiêu cha (`"số lượng chỉ tiêu HTX nông nghiệp"`), hệ thống chèn lặp 5 khối nội dung (thẻ 5 dòng đầu + câu giải thích + danh sách nút tĩnh `🔘 [...]` trong Markdown + bảng `SmartTable` 8 dòng + danh sách gạch đầu dòng + `QuickActionChips` ở đáy), sai lệch so với quy định tại `IPGov_Chatbot/docs/output.md`.
  2. Khi hỏi mốc ngày cụ thể $a$ (`"số lượng chỉ tiêu trang trại ngày 23/4"` trên tập mốc `[31/3, 30/6, 30/9]` = `[A, B, C]`), câu SQL đặt `CASE WHEN f.report_date::date >= '2026-04-23'::date THEN 0 ELSE 1 END ASC` đứng trước `ABS(...)` nên chọn nhầm `30/06/2026` (cách 68 ngày) thay vì `31/03/2026` (cách 23 ngày).
  3. Khi hỏi chỉ tiêu trong một khoảng thời gian (`"số lượng chỉ tiêu trang trại trong nửa đầu năm nay"` $\to$ `01/01..30/06`), điều kiện `is_parent_case` chỉ kiểm tra `not specific_date` mà chưa kiểm tra `date_from`/`month_filter`, hoặc bộ chọn dòng đơn lẻ lọc `_get_metric_val(r) is not None` làm bỏ qua bản ghi tại `report_date` mới nhất trong khoảng (`30/06/2026` có giá trị `NULL`).
- **Nguyên nhân gốc rễ:**
  1. `is_parent_case` tự sinh thêm bảng phụ và danh sách tóm tắt thay vì chỉ phát ra câu thông báo chuẩn của `output.md` kèm `quick_action_chips` và đặt `tabular_data = None`.
  2. Mệnh đề `ORDER BY` khi có `specific_date` ưu tiên ngày $\ge a$ thay vì tính khoảng cách ngắn nhất tới 2 cận $[A, B]$ (bằng nhau mới ưu tiên cận trên $B$).
  3. Chưa tách bạch điều kiện tra cứu theo khoảng thời gian (`date_from` / `month_filter`) khỏi `is_parent_case` và lọc bỏ `None` khi chọn `matched_single_row`.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không chèn thẻ 5 dòng, bảng phụ hay danh sách lặp vào phản hồi `SC-2.4`; Không đặt `CASE WHEN f.report_date >= spec_d` đứng trước `ABS(f.report_date::date - spec_d::date) ASC`; Không bỏ qua dòng tại `report_date` mới nhất trong khoảng thời gian khi giá trị của nó là `NULL`/`'-'`.
  * ✅ **ALWAYS:**
    1. Với `SC-2.4`, chỉ hiển thị đúng câu thông báo chuẩn `output.md`, đặt `tabular_data = None`, và hiển thị 1 lần các nút `🔘 [Tên chỉ tiêu con]` ngay bên dưới câu thông báo (trước khối SQL).
    2. Với `SC-2.2` khi hỏi ngày cụ thể $a$, dùng `ORDER BY ABS(f.report_date::date - '<spec_d>'::date) ASC, f.report_date DESC NULLS LAST, f.version DESC NULLS LAST` (và hàm `resolve_nearest_report_date`) để chọn cận gần hơn trong khoảng $[A, B]$ (cách đều ưu tiên cận trên $B$).
    3. Với câu hỏi trong một khoảng thời gian (`date_from` / `date_to` / `month_filter`), luôn lấy bản ghi tại `report_date` mới nhất trong khoảng đó (kể cả khi giá trị là `NULL` $\to$ hiển thị `Chưa có số liệu phê duyệt (-)`).

---

### [TRAP-070] Bẫy Gộp 2 Đơn Vị Phụ Trách Khác `department_code` Trong `office_mission`, Cột `deleted_at` Của Bảng `office` & Rò Rỉ Đuôi Thời Gian Vào Tên Lĩnh Vực (`REQ-Q03` / `SC-3.1`)
- **Môi trường & Công nghệ:** `CanonicalSemanticNormalizer.compile_canonical_sql` / `DuckDBSemanticCatalog.extract_scope_from_query` / `WarehouseLangGraphAgent.node_synthesize_response`
- **Triệu chứng:**
  1. Khi hỏi `"lĩnh vực nông nghiệp hiện đang có những nhiệm vụ nào"`, cột `Đơn vị phụ trách` hiển thị 2 đơn vị `"Chi cục, Phòng nông nghiệp"` cho mỗi nhiệm vụ (`Diêm nghiệp`, `Phát triển nông thôn`).
  2. Khi nhiệm vụ trong kho dữ liệu chưa được gán đơn vị phụ trách (`NULL`, ví dụ `nhiệm vụ 2`, `nhiệm vụ 3`), cột `Đơn vị phụ trách` lại hiển thị `"Chưa phân công"` hoặc `"Cấp tỉnh"` thay vì `'-'`.
  3. Bảng `dwh_internal.office` không có cột `deleted_date` (chỉ có `deleted_at`), nên nếu viết `o.deleted_date IS NULL` sẽ văng lỗi PostgreSQL `column o.deleted_date does not exist`.
- **Nguyên nhân gốc rễ:**
  1. Trong bảng `dwh_internal.office_mission`, `Diêm nghiệp` và `Phát triển nông thôn` (`m.department_code = '68-1-01'`) bị gắn thêm dòng của `department_code = '68-2-01'` (`Phòng nông nghiệp`), trong khi `STRING_AGG(DISTINCT o.office_name, ', ')` không đối chiếu `om.department_code = m.department_code` hay ưu tiên đơn vị thực hiện trong `fact_report_criteria`.
  2. Danh sách `stop_tails` trong `extract_scope_from_query` trước đó thiếu các cụm từ chỉ thời gian (`" trong quý"`, `" trong nửa"`, `" từ đầu năm"`, `" từ tháng"`,...), khiến cụm thời gian ở cuối câu có thể bị dính vào tên lĩnh vực.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không dùng `STRING_AGG` gộp nhiều đơn vị khác `department_code` cho 1 nhiệm vụ; Không gọi `o.deleted_date` trên bảng `dwh_internal.office`; Không fallback đơn vị `NULL` thành `"Cấp tỉnh"` hay `"Chưa phân công"`.
  * ✅ **ALWAYS:**
    1. Xác định **01 đơn vị phụ trách duy nhất** cho mỗi nhiệm vụ theo thứ tự ưu tiên: bản ghi đã duyệt trong `fact_report_criteria` $\to$ bản ghi trong `office_mission` có `om.department_code = m.department_code` $\to$ fallback **`'-'`** khi `NULL`.
    2. Cắt sạch các cụm từ thời gian trong `extract_scope_from_query` và áp dụng `EXISTS (SELECT 1 FROM dwh_internal.fact_report_criteria ...)` cho mọi mốc thời gian (`nửa đầu/cuối năm`, `quý 1..4`, `từ đầu năm tới giờ`, `từ tháng A đến tháng B`, `tháng X`, `ngày cụ thể`).

---

### [TRAP-071] Bẫy Lệch Cận `[A, B]` Khi Dùng `LAG/LEAD`, Rò Rỉ `lval` Ngoài Kỳ Lọc Trong Tree Modal & Ghi Đè CQR Giữa `SC-2.4` $\leftrightarrow$ `SC-2.1`
- **Môi trường & Công nghệ:** `CanonicalSemanticNormalizer.compile_canonical_sql` / `DuckDBSemanticCatalog.build_criteria_tree_for_rows` / `WarehouseLangGraphAgent.node_parse_context`
- **Triệu chứng:**
  1. Nếu dùng `LAG(f.report_date) OVER (ORDER BY f.report_date)` và `LEAD(f.report_date)` trên bảng có nhiều bản ghi cùng `report_date` (khác `version`) hoặc khi `rn = 1` chọn cận trên $B$, giá trị `can_duoi_ngay` / `can_tren_ngay` tại dòng `rn = 1` bị lệch khỏi khoảng $[A, B]$ bao quanh ngày hỏi $a$.
  2. Khi người dùng lọc theo khoảng thời gian (`has_temporal_filter=True`) và mở Pop-up Tree Modal (`REQ-Q01` / `SC-4.1`), các chỉ tiêu con không phát sinh bản ghi trong kỳ lại lấy nhầm `latest_value` (`lval`) của cả năm từ `catalog_criteria_hierarchy`.
  3. Khi Lượt 1 hỏi chỉ tiêu cha (`SC-2.4`, ví dụ `"HTX nông nghiệp"`) và Lượt 2 gõ tự nhiên chỉ tiêu lá trùng tên (`"Thế còn chỉ tiêu Đang hoạt động thì sao?"`), bộ viết lại câu hỏi CQR có thể ghi đè chỉ tiêu mới bằng tên chỉ tiêu cha cũ hoặc đánh rơi ngữ cảnh cha khiến hệ thống trả về bảng 4 dòng `DUPLICATE_LEAF` (`SC-2.1`).
- **Nguyên nhân gốc rễ:**
  1. `LAG`/`LEAD` phụ thuộc vào dòng lân cận trực tiếp trong thứ tự sắp xếp thay vì so sánh trực tiếp với mốc `spec_d`.
  2. `build_criteria_tree_for_rows` fallback vô điều kiện về `lval` khi `cid not in val_by_cid`.
  3. Chưa truyền `inherited_parent_criterion` tách biệt với thực thể chỉ tiêu của lượt hiện tại vào `normalize_query` và `classify_criterion_hierarchy`.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không dùng `LAG`/`LEAD` để tìm 2 cận ngày báo cáo bao quanh `spec_d`; Không fallback về `lval` trong `build_criteria_tree_for_rows` khi `has_temporal_filter=True`; Không để CQR ghi đè tên chỉ tiêu lá ở Lượt 2 bằng tên chỉ tiêu cha của Lượt 1.
  * ✅ **ALWAYS:**
    1. Tính `can_duoi_ngay = MAX(CASE WHEN f.report_date::date <= spec_d THEN f.report_date END) OVER (PARTITION BY f.criteria_id, f.office_id)` và `can_tren_ngay = MIN(CASE WHEN f.report_date::date >= spec_d THEN f.report_date END) OVER (PARTITION BY f.criteria_id, f.office_id)`.
    2. Truyền `has_temporal_filter=True` vào `build_criteria_tree_for_rows` khi câu hỏi có bộ lọc thời gian để khóa `node_val = None` (`'-'`) cho các nhánh con không phát sinh dữ liệu trong kỳ.
    3. Duy trì `inherited_parent_criterion` trong `AgentState` / `history` và truyền `parent_context` vào `classify_criterion_hierarchy` để phân giải `DUPLICATE_LEAF` $\to$ `SINGLE_LEAF` đúng nhánh cha.

---

### [TRAP-072] Bẫy Ghi Đè Đa Bảng Markdown Trong `SmartTable.tsx` (`REQ-Q05`), Lệch Selector `drilldown-mission` & Rò Rỉ Tiền Tố `[tenant_code=...]` Lên Bong Bóng Chat
- **Môi trường & Công nghệ:** `SmartTable.tsx` / `MessageItem.tsx` / `ChatContainer.tsx` / `storage.ts`
- **Triệu chứng:**
  1. Khi phản hồi backend (`final_answer`, ví dụ `REQ-Q05` / `SC-5.1b`) chứa **3 bảng Markdown khác nhau** (Bảng 1: 9 dòng tổng hợp kỳ báo cáo; Bảng 2: 14 dòng chi tiết chỉ tiêu nháp; Bảng 3: 72 dòng đối chiếu Draft vs Approved), cả 3 bảng trên UI đều hiển thị y hệt Bảng 1 (9 dòng)!
  2. Nút drill-down nhiệm vụ trong `SmartTable.tsx` đặt `data-testid="drilldown-mission-${cleanVal}"` thay vì chỉ số dòng `rIdx`, làm gãy kịch bản kiểm thử tự động gọi `data-testid="drilldown-mission-0"` / `"drilldown-mission-1"`.
  3. Bong bóng chat của người dùng hiển thị nguyên chuỗi `[tenant_code=68, level=0] <câu hỏi>` trên giao diện.
- **Nguyên nhân gốc rễ:**
  1. `MessageItem.tsx` truyền cùng `tabularData={message.tabular_data}` (chứa dữ liệu của Bảng 1) vào mọi thẻ `<table>` do `ReactMarkdown` sinh ra, và `SmartTable.tsx` ưu tiên mù quáng `tabularData` mà không đối chiếu với `children` (`mdColumns`, `mdRows`). Đồng thời `parseTableFromChildren` dùng chỉ số `forEach` `idx` trên `thead` (bị lệch khi có text node `\n`) thay vì bộ đếm phần tử hợp lệ `hIdx`.
  2. `SmartTable.tsx` gắn `cleanVal` vào `data-testid` thay vì `rIdx`.
  3. `ChatContainer.tsx` gán trực tiếp `promptWithContext` vào `userMsg.content`.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không ưu tiên mù quáng `tabularData` trong `SmartTable.tsx` khi `children` có cấu trúc cột/dòng khác `tabularData`; Không dùng chỉ số `forEach` thô cho `col_${idx}` trong `thead`; Không gán chuỗi `[tenant_code=...]` vào `userMsg.content` hiển thị trên UI.
  * ✅ **ALWAYS:**
    1. Luôn phân tích `parseTableFromChildren(children)` (`mdColumns`, `mdRows`) trong `resolveSmartTableData` và chỉ áp dụng/làm giàu từ `tabularData` khi `(a)` `mdRows.length === 0`, hoặc `(b)` số cột, tên cột (`doHeadersMatch`) và số dòng khớp với `tabularData`.
    2. Đặt `data-testid={\`drilldown-mission-${rIdx}\`}` kèm `data-mission-name={cleanVal}` cho nút drill-down nhiệm vụ.
    3. Cắt bỏ tiền tố `/^\[tenant_code=[^\]]+\]\s*/i` khỏi `userMsg.content` trên UI (trong `ChatContainer.tsx`, `MessageItem.tsx`, `storage.ts`, `api.ts`), chỉ gửi `promptWithContext` xuống API backend.

---

### [TRAP-073] Bẫy Lách Luật AST (AST Evasion), Nhiễm Trọng Số Tiền Tố `jaro_winkler_similarity` Trên Chuỗi Giao Token (`sect`) & Lệch Alias `nguoi_tao` / Biểu Thức Số Học Ngoại Truy Vấn (`q3.val - q2.val`)
- **Môi trường & Công nghệ:** `DuckDBSemanticCatalog` / `CanonicalSemanticNormalizer` / `ClarificationEngine` / `WarehouseLangGraphAgent` / `ASTEnforcerService`
- **Triệu chứng:**
  1. Thay thế toán tử `in` / `re` bằng các hàm Python tự chế (`_lcs_length`, `_indel_ratio`, `_partial_indel_ratio`, `_token_set_similarity`, `_has_term`, `_has_any_term`, `text.find(kw) != -1`, `len(text.split(kw)) > 1`) vi phạm quy tắc chống lách luật AST (AST Evasion / Smuggling) và gây nghẽn CPU Python.
  2. Khi tính độ tương đồng tập từ (`_sql_token_set_similarity`) bằng cách ghép phần giao `sect` lên đầu (`s_ab = sect + ' ' + d1`, `s_ba = sect + ' ' + d2`) rồi đưa vào `GREATEST(..., jaro_winkler_similarity(s_ab, s_ba))`, trọng số Winkler ưu tiên tiền tố chung khiến mọi câu hỏi có chứa `"tỉnh Lâm Đồng"` khớp nhầm với tài khoản `"Admin Tỉnh Lâm Đồng"` ($\ge 85\%$) hoặc khớp nhầm chỉ tiêu chia sẻ từ đầu, đẩy câu hỏi KTXH sang `OFFICER_ASSIGNMENT`.
  3. Kịch bản `SC-1.3_REPORT_DRAFT_ONLY` biên dịch SQL với alias `report_id`, `report_status`, `nguoi_tao`, nhưng `warehouse_langgraph_agent.py` chỉ đọc `r.get("id")`, `r.get("status")`, `r.get("created_by")` dẫn đến hiển thị sai người tạo mặc định `"chicuc_ptnt"` thay vì `"Admin Tỉnh Lâm Đồng"`.
  4. Trong `ASTEnforcerService`, khi CTE chọn `SELECT value AS val` và truy vấn ngoài thực hiện phép trừ `q3.val - q2.val`, bộ kiểm tra AST chỉ dò tên cột gốc `value` trong biểu thức số học mà bỏ qua alias `val`, làm lọt cột `VARCHAR` chưa ép kiểu `NULLIF(TRIM(value), '')::DECIMAL`.
- **Nguyên nhân gốc rễ:**
  1. Chưa ủy thác toàn bộ phép đối sánh từ vựng và khoảng cách chuỗi xuống tầng C++ SQL của DuckDB (`semantic_lexicon`, `strpos`, `string_split_regex`, `levenshtein`, `jaro_winkler_similarity`).
  2. Áp dụng `jaro_winkler_similarity` trên hai chuỗi đã được tiền xử lý đặt phần giao `sect` lên đầu làm sai lệch bản chất đo khoảng cách chỉnh sửa (edit distance) trên phần hiệu `d1`, `d2`.
  3. Thiếu đồng bộ tên cột alias giữa `compile_canonical_sql` và `node_synthesize_response`, cùng với việc `ASTEnforcerService` chưa thu thập tập alias của cột `value` trước khi quét các nút `exp.Sub / exp.Add / exp.Mul / exp.Div`.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Tuyệt đối không viết hàm độ tương đồng chuỗi bằng vòng lặp Python hoặc lách luật AST bằng `.find() != -1` / `.split()`; Không đưa `jaro_winkler_similarity(s_ab, s_ba)` vào phép so sánh chuỗi đã ghép tiền tố `sect`; Không cho phép tài khoản quản trị hệ thống (`Admin Tỉnh...`, `Phường...`) khớp tự do trong `resolve_user_name` khi câu hỏi không có ngữ cảnh nhân sự.
  * ✅ **ALWAYS:**
    1. Thực thi 100% đối sánh từ điển ngữ nghĩa qua bảng DuckDB `semantic_lexicon(category, term, weight)` (`match_lexicon_categories`, `has_lexicon_category`) và các hàm SQL gốc của DuckDB (`sql_has_term`, `sql_has_any_term`, `sql_find_word_boundary_span`).
    2. Trong `_sql_token_set_similarity`, chỉ dùng khoảng cách chỉnh sửa chuẩn hóa (`1.0 - levenshtein(...) / GREATEST(length(...))`) khi đối chiếu các chuỗi tổ hợp `sect`, `s_ab`, `s_ba`.
    3. Hỗ trợ đầy đủ cả bộ khóa gốc và alias (`id`/`report_id`, `status`/`report_status`, `created_by`/`nguoi_tao`) tại tầng tổng hợp phản hồi `REQ-Q05`, và thu thập mọi alias của cột `value` trong `ASTEnforcerService` để bọc `CAST(NULLIF(TRIM(value), '') AS DECIMAL)` khi alias đó tham gia phép toán số học ở truy vấn cha.

---

### [TRAP-074] Bẫy Phình To Nhánh Ngoài Phạm Vi `output.md`, Bỏ Quên Bảng `criteria_group` Trong `ALLOWED_WAREHOUSE_TABLES` & Va Chạm Động Từ Đệm `"tổng hợp"` Với Chỉ Tiêu Lá `"Tổng hợp"` (`tong_hop4`)
- **Môi trường & Công nghệ:** `DuckDBSemanticCatalog.classify_criterion_hierarchy` / `CanonicalSemanticNormalizer` / `WarehouseLangGraphAgent` / PostgreSQL 16 (`vna_wom_dev`)
- **Triệu chứng:**
  1. Sự xuất hiện của các nhánh ngoài phạm vi `IPGov_Chatbot/docs/output.md` (`R2-DYN-**`, `ward_mission_scope`, `office_user_dept`, `fact_office_scope`, `fact_report_scope`, `criteria_fact_office_scope`, 6 nhánh kiểm toán tự chế `SC-1.1_REPORT_TOTAL_SUBMITTED`..`SC-4.3_MISSION_EMPTY_SUBDEPT`) kèm dữ liệu giả (`Chi cục Phát triển nông thôn`, `admin-lamdong`, 2 dòng `collection_form` giả) làm lệch hoàn toàn kết quả hiển thị của `REQ-Q01`..`REQ-Q05`.
  2. Câu hỏi `SC-5.2` truy vấn `dwh_internal.criteria_group` bị `execute_safe_sql` chặn thực thi và trả về 0 dòng vì `ALLOWED_WAREHOUSE_TABLES` thiếu `"criteria_group"`.
  3. Khi câu hỏi có từ đệm hành chính `"tổng hợp số lượng chỉ tiêu trang trại..."` (`Q02-B9 P1`), hàm `classify_criterion_hierarchy` khớp trực tiếp chuỗi có dấu `"tổng hợp"` với chỉ tiêu lá Cấp 3 `"Tổng hợp"` (`code = 'tong_hop4'`, thuộc nhóm Trang trại), làm trả về `SINGLE_LEAF` (`Tổng hợp`) thay vì `PARENT_GROUP` (`Trang trại`).
- **Nguyên nhân gốc rễ:**
  1. Không khóa chặt phạm vi thiết kế vào tài liệu chuẩn `IPGov_Chatbot/docs/output.md` và tự ý sửa dữ liệu gốc trong `vna_wom_dev`.
  2. Chưa khai báo bảng `"criteria_group"` trong tập `ALLOWED_WAREHOUSE_TABLES` của `warehouse_langgraph_agent.py`.
  3. Chốt chặn chống khớp nhầm `"tổng hợp"` trước đó chỉ đặt trong nhánh không dấu (`if not sp`) và chỉ kiểm tra `it["code"] == "tong_hop"` thay vì `it["name_low"] == "tổng hợp"` (`code = 'tong_hop4'`).
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không thêm các nhánh `target_table` hoặc `audit_sub_intent` ngoài phạm vi `IPGov_Chatbot/docs/output.md`; Không tự ý chèn bản ghi giả hoặc đổi tên đơn vị `'Chi cục'` thành `'Chi cục Phát triển nông thôn'`; Không cho phép `it["name_low"] == "tổng hợp"` khớp tự do khi người dùng dùng `"tổng hợp"` như động từ đệm.
  * ✅ **ALWAYS:**
    1. Chỉ duy trì đúng 5 nhóm câu hỏi `REQ-Q01`..`REQ-Q05` (với 3 `audit_sub_intent` chuẩn: `REPORT_SUBMISSION_STATUS`, `FORM_CRITERIA_GROUP`, `MISSION_ASSIGNMENT_MATRIX`) và bảo toàn nguyên trạng dữ liệu chuẩn trong `vna_wom_dev` (`office_name = 'Chi cục'`, `created_by = 'tzyalnh'`).
    2. Khai báo đầy đủ `"criteria_group"` trong `ALLOWED_WAREHOUSE_TABLES`.
    3. Trong `classify_criterion_hierarchy`, chặn khớp chỉ tiêu có `it["name_low"] == "tổng hợp"` trừ khi câu hỏi chứa ngữ cảnh tường minh `("chi tieu tong hop", "trang trai tong hop", "linh vuc tong hop")`.

---

### [TRAP-075] Bẫy Cướp Quyền Điều Hướng Do Nhánh Tra Cứu Danh Mục Sở/Phòng Ban (`office_or_department`) Thiếu Chốt Chặn `not has_specific_catalog_metric`
- **Môi trường & Công nghệ:** `CanonicalSemanticNormalizer._extract_stream_a_deterministic` / `DuckDBSemanticCatalog.is_dimension_query`
- **Triệu chứng:**
  Khi câu hỏi tra cứu một chỉ tiêu cụ thể nhưng có chứa từ "đơn vị" (ví dụ: *"Làm ơn cho tôi hỏi thăm một chút là chỉ tiêu số lượng đơn vị đang hoạt động trên hệ thống hiện nay ghi nhận như thế nào?"*), nhánh kiểm tra `is_dimension_query(raw_input, "office_or_department")` tại dòng 993 trong `canonical_normalizer.py` bị kích hoạt, chuyển hướng toàn bộ câu hỏi sang `DIMENSION_LISTING` (liệt kê danh mục phòng ban) thay vì trả về bảng đối chiếu `DUPLICATE_LEAF` (SC-2.1) của chỉ tiêu *"Đang hoạt động"*.
- **Nguyên nhân gốc rễ:**
  Nhánh 4 trong `_extract_stream_a_deterministic` thiếu điều kiện phòng vệ `not has_specific_catalog_metric and not is_fact_calc`, dẫn đến việc chỉ cần câu hỏi xuất hiện từ khóa phòng ban/đơn vị thì bị cướp quyền điều hướng ngay cả khi đã phát hiện ra chỉ tiêu số liệu cụ thể trong catalog.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Tuyệt đối không đặt các nhánh phân loại danh mục (Dimension Listing) trước khi kiểm tra hoặc bỏ qua điều kiện `not has_specific_catalog_metric and not is_fact_calc`.
  * ✅ **ALWAYS:**
    Bắt buộc thêm `if not has_specific_catalog_metric and not is_fact_calc and hasattr(self.catalog, "is_dimension_query") and self.catalog.is_dimension_query(raw_input, "office_or_department"):` để đảm bảo câu hỏi chứa chỉ tiêu cụ thể luôn được định tuyến đúng về Fact Plane (`METRIC_POINT_INQUIRY` / `DUPLICATE_LEAF`).

---

### [TRAP-076] Bẫy Rò Rỉ Ngữ Cảnh Nhóm Cha (Parent Context Leakage) Do Heuristic Đếm Độ Dài Từ Thay Vì Dấu Hiệu Tỉnh Lược Cấu Trúc
- **Môi trường & Công nghệ:** `WarehouseLangGraphAgent` / Quản trị Hội thoại Đa Lượt (Discourse State Tracking) / SC-2.1 & SC-2.4
- **Triệu chứng:**
  Sau khi hỏi một nhóm chỉ tiêu cha ở Turn 1 (ví dụ: *"Cho tôi xem số liệu chỉ tiêu Trang trại năm 2026?"*), ở Turn 2 người dùng hỏi một chỉ tiêu độc lập trùng tên ở nhiều nhánh nhưng không có từ hỏi dạng câu hỏi dài (ví dụ: *"Chỉ tiêu trồng trọt"* hoặc *"Trồng trọt năm 2026"*). Chatbot vô tình kế thừa lại ngữ cảnh `"Trang trại"` của Turn 1, khiến bảng đối chiếu 4 nhánh (`multi_parent_rows`) bị teo tóp về 1 nhánh duy nhất (giá trị 26) thay vì trả về cả 4 nhánh (HTX, LHHTX, THT, Trang trại).
- **Nguyên nhân gốc rễ:**
  Heuristic `is_contextual_query = has_connective or (len(norm_tokens) <= 5 and not has_standalone_metric_ask)` gán bừa mọi câu hỏi ngắn $\le 5$ từ không chứa từ nghi vấn ("bao nhiêu", "đạt bao nhiêu") thành câu hỏi phụ thuộc ngữ cảnh, bất kể người dùng không hề dùng các từ nối liên kết hay đại từ chỉ định.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Tuyệt đối không dùng heuristic đếm số từ `len(tokens) <= 5` để suy đoán ý định tỉnh lược (anaphora).
  * ✅ **ALWAYS:** Chỉ cho phép kế thừa `inherited_parent_ctx` khi câu hỏi chứa từ nối liên kết tường minh (`"còn"`, `"sao"`, `"thế"`, `"trong"`, `"nhánh"`, `"thuộc"`) hoặc đại từ chỉ định trỏ vào thực thể trước (`"nhóm đó"`, `"nhánh này"`, `"ở trên"`). Các câu hỏi tra cứu danh từ độc lập phải tự động giải phóng ngữ cảnh cha (`inherited_parent_ctx = None`) để trả về toàn diện các nhánh (`SC-2.1`).

---

### [TRAP-077] Bẫy ValidationError Kiểu Dữ Liệu Trong DialogueStateFrame Khi Trích Xuất Thực Thể Danh Sách (List Coercion Trap)
- **Môi trường & Công nghệ:** `DiscourseStateTracker` / `WarehouseLangGraphAgent` / Pydantic v2 `DialogueStateFrame`
- **Triệu chứng:**
  `pydantic_core._pydantic_core.ValidationError: Input should be a valid string [type=string_type, input_value=['HTX nông nghiệp', ...], input_type=list]` tại `discourse_state_tracker.py` khi chạy câu hỏi OOD dạng `"Liệt kê danh mục các nhiệm vụ thuộc khối ngành Nông nghiệp và Phát triển nông thôn?"`.
- **Nguyên nhân gốc rễ:**
  Hàm `extract_topic_entity` hoặc `planner_slots["topic_entity"]` trả về một `list` (do `catalog.find_criteria_by_name` trả về danh sách thực thể hoặc trường hợp đa thực thể). Giá trị này được gán trực tiếp vào trường `topic_entity: Optional[str]` và `keywords: List[str]` trong `DialogueStateFrame`, vi phạm ràng buộc kiểu dữ liệu nghiêm ngặt của Pydantic v2.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không truyền trực tiếp kết quả trích xuất thực thể hoặc slot vào `DialogueStateFrame` mà không kiểm tra và ép kiểu.
  * ✅ **ALWAYS:**
    Luôn kiểm tra `isinstance(topic, list)` và ép kiểu an toàn (`", ".join(str(x) for x in topic)` nếu là list, `str(topic)` nếu không rỗng) trước khi khởi tạo `DialogueStateFrame`, đồng thời làm phẳng (flatten) mảng `keywords` để đảm bảo 100% phần tử là `str`.

---

### [TRAP-078] Bẫy Rò Rỉ Ngữ Cảnh Do Đưa Giới Từ Thông Dụng Vào Tập Từ Nối Tỉnh Lược (Preposition Context Leakage Trap)
- **Môi trường & Công nghệ:** `DuckDBSemanticCatalog` (`DISCOURSE_CONNECTIVE` / `DISCOURSE_DEMONSTRATIVE`) / `WarehouseLangGraphAgent`
- **Triệu chứng:**
  Sau khi hỏi chỉ tiêu cha ở Turn 1 (ví dụ: *"Cho tôi xem số liệu chỉ tiêu Trang trại năm 2026?"*), ở Turn 2 người dùng hỏi một câu độc lập có chứa giới từ thông dụng như *"trong"* (*"Chỉ tiêu trồng trọt trong năm 2026 là bao nhiêu?"*) hoặc *"thuộc"* (*"Các chỉ tiêu thuộc nhiệm vụ Diêm nghiệp?"*). Chatbot nhận diện nhầm câu hỏi là hội thoại tỉnh lược (anaphora ellipsis continuation), tự động kích hoạt `inherited_parent_ctx = Trang trại`, làm teo tóp bảng so sánh 4 nhánh (`duplicate_leaf`) thành 1 nhánh hoặc cướp quyền điều hướng của nhiệm vụ mới.
- **Nguyên nhân gốc rễ:**
  Tập từ nối `DISCOURSE_CONNECTIVE` bị cấu hình thừa các giới từ quan hệ thông dụng (`"trong"`, `"thuộc"`, `"đối với"`), và `DISCOURSE_DEMONSTRATIVE` chứa các danh từ phân loại đơn lẻ (`"nhóm"`, `"nhánh"`). Bất kỳ câu hỏi chuẩn nào có giới từ thời gian (`"trong năm 2026"`) hoặc giới từ quan hệ (`"thuộc nhiệm vụ"`) đều bị dương tính giả (false positive).
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Tuyệt đối không đưa các giới từ độc lập (`"trong"`, `"thuộc"`, `"đối với"`) hoặc danh từ chung (`"nhóm"`, `"nhánh"`) vào `DISCOURSE_CONNECTIVE` / `DISCOURSE_DEMONSTRATIVE`.
  * ✅ **ALWAYS:**
    1. Chỉ định nghĩa `DISCOURSE_CONNECTIVE` với các cụm từ nối tỉnh lược thực sự: `{"thế còn", "vậy còn", "thế thì", "còn thì", "còn", "thì sao", "thế sao"}`.
    2. Chỉ định nghĩa `DISCOURSE_DEMONSTRATIVE` với các cụm đại từ chỉ định tường minh: `{"nhóm đó", "nhánh này", "nhóm này", "nhánh đó", "chỉ tiêu đó", "chỉ tiêu này", "ở trên", "vừa rồi"}`.
    3. Thêm chốt chặn nghiệp vụ trong agent router: Bỏ qua kế thừa ngữ cảnh cha nếu câu hỏi chứa nhiệm vụ tường minh (`has_explicit_mission`) hoặc câu hỏi tự định nghĩa một chỉ tiêu cha mới (`is_parent_in_query`).

---

### [TRAP-079] Bẫy Va Chạm Substring `INSTR` Trên Token Không Dấu Đơn Tiết ("con", "the", "sao") & Khiếm Khuyết Hợp Đồng `root_name` Trong `classify_criterion_hierarchy`
- **Môi trường & Công nghệ:** `DuckDBSemanticCatalog` (`DISCOURSE_CONNECTIVE`) / `WarehouseLangGraphAgent` / `semantic_lexicon`
- **Triệu chứng:**
  1. Khi người dùng hỏi Turn 1 về chỉ tiêu cha (ví dụ *"Cho tôi xem số liệu chỉ tiêu Trang trại năm 2026?"*), sang Turn 2 người dùng hỏi một câu độc lập có từ "con" (ví dụ *"Chỉ tiêu con trong năm 2026 là bao nhiêu?"*) hoặc "sao" (*"Tại sao..."*), hệ thống nhận diện nhầm "con" / "sao" là `DISCOURSE_CONNECTIVE`, vô tình kế thừa lại ngữ cảnh cha `Trang trại`.
  2. Kế thừa ngữ cảnh nhóm cha từ lịch sử hội thoại (`history`) hoàn toàn tê liệt vì `u_h.get("classification") in ("parent", "parent_group")` có phát hiện nhưng điều kiện `u_h.get("root_name")` luôn là `None` do `classify_criterion_hierarchy` trả về `name`, `parent_name` nhưng quên gán khóa `root_name` và `root_id` cho nút gốc.
- **Nguyên nhân gốc rễ:**
  1. Đưa các token không dấu 1 âm tiết (`"con"`, `"the"`, `"sao"`) vào bảng `semantic_lexicon` rồi dùng toán tử `INSTR(haystack, needle) > 0` không có ranh giới từ (word boundary) làm khớp bất kỳ từ tiếng Việt thông dụng nào chứa chuỗi con đó (`"chỉ tiêu con"` khớp `"con"`, `"tại sao"` khớp `"sao"`).
  2. Sự sai lệch hợp đồng dữ liệu giữa hàm phân loại phân cấp `classify_criterion_hierarchy` (bỏ quên `root_name`) và hàm router đa lượt `node_plan_route` của agent.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không bao giờ nạp token không dấu 1 âm tiết (`con`, `the`, `sao`) vào lexicon từ nối; Không dựa dẫm vào 1 khóa duy nhất `u_h.get("root_name")` mà không có fallback an toàn.
  * ✅ **ALWAYS:**
    1. Kiểm tra ranh giới từ (`' ' || needle || ' '`) đối với `DISCOURSE_CONNECTIVE` trong `has_lexicon_term` và chặn các token không dấu 1 âm tiết khi hydrate catalog.
    2. Trong `classify_criterion_hierarchy`, gán đầy đủ cả `root_id` và `root_name` cho các nút gốc (`category == 'PARENT_GROUP'`).
    3. Trong agent router, trích xuất linh hoạt `p_name = u_h.get("root_name") or u_h.get("name") or u_h.get("matched_name")`, và áp dụng chốt chặn `is_dup_leaf and not (has_connective or has_demonstrative)` để triệt tiêu mọi rò rỉ ngữ cảnh cha.








---

### [TRAP-080] Bẫy Dò Chuỗi Cứng (Probing) và Cắt Chuỗi Cứng (Slicing) Trong Router/Catalog Gây Gãy Tính Tổng Quát Hóa Framework
- **Môi trường & Công nghệ:** `CanonicalSemanticNormalizer` / `DuckDBSemanticCatalog` / `WarehouseLangGraphAgent` / AST Zero-Heuristic
- **Triệu chứng:**
  1. Dò chuỗi con cố định (ví dụ: `"lành" in frame.target_user_name`) để quyết định SELECT cột `u.position`, khiến các cán bộ khác bị mất chức danh hoặc sinh SQL không đồng nhất.
  2. Dùng `if frame.department_code == "68-1-07"` hardcode mã phòng ban liên kết trong code Python thay vì lưu trong metadata catalog.
  3. Sử dụng `[:]`, `removeprefix`, `removesuffix`, hoặc `.find()` cắt chuỗi thủ công trong Python (`u_search[len(pref):]`, `metric_name[len("chỉ tiêu "):]`, `extracted_mission[:pos]`) vi phạm nguyên tắc cấm cắt chuỗi cứng.
  4. CTE SQL sinh ra chứa cứng nhãn `"HTX nông nghiệp"` và năm `"2026"` thay vì lấy theo metric và năm động.
- **Nguyên nhân gốc rễ:**
  Lối mòn vá lỗi (patching) nhanh để giải quyết test case cục bộ thay vì tổng quát hóa schema metadata và ủy thác xử lý cho DuckDB SQL engine.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Tuyệt đối không dò chuỗi con của tên riêng thực thể (`"lành" in text`); Không hardcode mã liên kết phòng ban/sở ngành trong code Python; Không dùng `[:]` / `removeprefix` / `removesuffix` / `.find()` cắt chuỗi; Không hardcode nhãn phân loại hoặc năm trong CTE.
  * ✅ **ALWAYS:**
    1. Chiếu đồng nhất các cột nghiệp vụ cần thiết (`u.position`).
    2. Lưu cấu trúc quan hệ (`related_codes`) trong `catalog_seed_metadata.json` và bảng `catalog_departments` DuckDB, truy xuất qua `get_associated_department_codes(code)`.
    3. Ủy thác loại bỏ từ nhiễu/tiền tố/hậu tố qua `strip_query_noise` bằng DuckDB SQL với bảng `semantic_lexicon`.
    4. Trích xuất dynamic label `metric_lbl` và `{year}` cho mọi CTE và biểu thức truy vấn.

---

### [TRAP-081] Bẫy Va Chạm Tiền Tố Substring Không Ranh Giới Từ Trong strip_query_noise và has_lexicon_term (Word Boundary Prefix Collision Trap)
- **Môi trường & Công nghệ:** `DuckDBSemanticCatalog` (`strip_query_noise`, `has_lexicon_term`) / `CanonicalSemanticNormalizer`
- **Triệu chứng:**
  Khi người dùng hỏi câu hỏi bắt đầu bằng từ vựng có tiền tố trùng với một token nhiễu ngắn (ví dụ: *"Hiệu quả hoạt động của trang trại là bao nhiêu?"* chứa từ *"Hiệu quả"* bắt đầu bằng `"Hi"` trùng với greeting lead noise `"hi"`), hệ thống nhận diện nhầm câu hỏi có chứa lời chào hỏi và tự động cắt cụt tiền tố chuỗi (`"Hiệu quả..."` -> `"ệu quả..."`). Chuỗi truy vấn bị hỏng khiến tầng trích xuất thực thể không thể khớp được chỉ tiêu *"Hiệu quả hoạt động"*, dẫn đến rớt nhánh hoặc gán sai chỉ tiêu cha.
- **Nguyên nhân gốc rễ:**
  Hàm `strip_query_noise` và `has_lexicon_term` khi so khớp tiền tố (`LEAD` / `PREFIX`) dùng toán tử `LIKE term || '%'` hoặc `INSTR(text, term) > 0` không có điều kiện ranh giới từ (word boundary). Do đó, token 2 ký tự `"hi"` khớp vào 2 ký tự đầu của `"Hiệu quả"`.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Tuyệt đối không so khớp tiền tố chuỗi `LIKE term || '%'` hoặc `INSTR(text, term) > 0` đối với các từ nhiễu ngắn mà không kiểm tra ký tự ranh giới từ.
  * ✅ **ALWAYS:**
    Khi loại bỏ hoặc nhận diện tiền tố (`is_lead`), bắt buộc kiểm tra xem token đó có đứng độc lập hoặc theo sau bởi dấu cách / dấu phân cách hay không:
    `LOWER(text) = LOWER(term) OR LOWER(text) LIKE LOWER(term) || ' %' OR LOWER(text) LIKE LOWER(term) || ',%' OR LOWER(text) LIKE LOWER(term) || '!%' ...`

---

### [TRAP-082] Bẫy Cắt Chuỗi Tiền Tố [len(p):] Thủ Công Gây Rò Rỉ Kỹ Thuật và Bỏ Qua Lexicon Quản Trị Trung Tâm
- **Môi trường & Công nghệ:** `ClarificationEngine` / `WarehouseLangGraphAgent` / `DuckDBSemanticCatalog`
- **Triệu chứng:**
  Xuất hiện các hàm cục bộ lặp lại (`_stem_core_cand`, `_stem_core`) sử dụng vòng lặp `for p in ("số lượng ", ...): if n.startswith(p): return n[len(p):].strip()`. Khi cần bổ sung tiền tố mới (ví dụ: `"mức độ"`, `"tỷ lệ"`), kỹ sư buộc phải tìm và sửa nhiều nơi trong mã nguồn, dễ bỏ sót và vi phạm nguyên tắc Zero-Heuristics của hệ thống.
- **Nguyên nhân gốc rễ:**
  Viết logic cắt chuỗi tiện tay bằng Python thủ công thay vì ủy thác cho bảng `semantic_lexicon` (`METRIC_AGG_PREFIX_NOISE`) và hàm `strip_query_noise` trong DuckDB Catalog.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Tuyệt đối không viết vòng lặp `startswith` kết hợp `[len(p):]` để cắt tiền tố/hậu tố chuỗi trong Router hay Agent.
  * ✅ **ALWAYS:** Đăng ký các tiền tố/hậu tố vào `semantic_lexicon` và gọi `self.catalog.strip_query_noise(text, category)` để quản trị tập trung tại một nguồn chân lý duy nhất (SSOT).

---

### [TRAP-083] Bẫy Hardcode Fallback Danh Mục Nghiệp Vụ Gây Thiên Kiến Miền Dữ Liệu (Domain Bias Trap)
- **Môi trường & Công nghệ:** `WarehouseLangGraphAgent` / `DuckDBSemanticCatalog` / `build_criteria_tree_for_rows`
- **Triệu chứng:**
  Khi DuckDB Catalog gặp lỗi hoặc bảng danh mục chưa có bản ghi, hệ thống fallback về các giá trị cứng thuộc lĩnh vực nông nghiệp (`"Nông nghiệp"`, `"Diêm nghiệp"`, `"Phát triển nông thôn"`, `"Chi cục"`), hoặc hardcode thứ tự ưu tiên `m_order = 0 if nd["mission_name"] == "Diêm nghiệp" else 1`. Khi mở rộng sang các sở ngành khác (Y tế, Giáo dục, Xây dựng, Tài chính), hệ thống hiển thị gợi ý hoặc nhãn sở ngành không thuộc phạm vi người dùng hỏi.
- **Nguyên nhân gốc rễ:**
  Lối tư duy dùng dữ liệu mẫu cục bộ làm fallback cứu vớt kết quả thay vì trả về `[]` an toàn hoặc truy vấn động từ các bảng metadata `catalog_missions_detail` và `catalog_scopes`.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Tuyệt đối không hardcode chuỗi tên lĩnh vực/nhiệm vụ/phòng ban nghiệp vụ trong các mệnh đề `or [...]` hoặc biểu thức `if/else` sắp xếp thứ tự.
  * ✅ **ALWAYS:**
    1. Khi danh mục rỗng, trả về `[]` an toàn để kích hoạt nhánh xử lý từ chối chuẩn mực.
    2. Sắp xếp thứ tự nhiệm vụ/lĩnh vực động qua `ORDER BY name ASC` hoặc `mission_order_map` được build từ bảng metadata `catalog_missions_detail`.
    3. Tra cứu `def_mname` và `def_oname` động từ bản ghi hợp lệ đầu tiên trong metadata thay vì hardcode chuỗi tĩnh.

---

### [TRAP-084] Bẫy N+1 Query Lặp Truy Vấn Metadata Trong Vòng Lặp Phân Cấp Cây Chỉ Tiêu (N+1 Tree Hydration Query Trap)
- **Môi trường & Công nghệ:** `DuckDBSemanticCatalog.build_criteria_tree_for_rows`
- **Triệu chứng:**
  Khi dựng cây chỉ tiêu cho kết quả truy vấn gồm hàng trăm dòng (`hier_rows`), hệ thống thực thi câu lệnh SQL lặp đi lặp lại `SELECT has_approved_facts FROM catalog_missions_detail WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))` cho từng dòng bên trong vòng lặp `for r in hier_rows:`. Thao tác này gây nghẽn IO, tăng độ trễ tổng thể và dễ phát sinh deadlock/connection lock trên DuckDB RAM dưới tải đồng thời.
- **Nguyên nhân gốc rễ:**
  Truy vấn đơn lẻ bên trong vòng lặp (N+1 query anti-pattern) thay vì gom nhóm (batch fetch) siêu dữ liệu `catalog_missions_detail` thành một bảng tra cứu bộ nhớ (in-memory hash map) trước khi bắt đầu duyệt cây.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Tuyệt đối không gọi `self.conn.execute(...)` bên trong vòng lặp duyệt dòng cây phân cấp `hier_rows`.
  * ✅ **ALWAYS:**

---

### [TRAP-085] Bẫy Trả Về Trạng Thái Đối Thoại Cũ (Stale `curr_quest`) Trong Phân Nhánh Khám Phá Danh Mục (Stale Context Frame Trap in `CATALOG_DISCOVERY`)
- **Môi trường & Công nghệ:** `IntentRouter.route_query` / `HDFTDialogueTracker` / `CATALOG_DISCOVERY`
- **Triệu chứng:**
  Trong chuỗi hội thoại đa lượt, khi người dùng chuyển từ câu hỏi khám phá biểu mẫu chung (*"Năm 2026 có những biểu mẫu thu thập dữ liệu nào ?"*) sang câu hỏi lọc theo phòng ban (*"Biểu mẫu nào của Phòng Xây dựng sắp đến hạn nộp ?"*), dù `HDFTDialogueTracker.update_state` đã nhận diện chính xác phòng ban (*"Phòng Xây dựng"*) và nạp vào `active_quest.admin_entity`, đối tượng trả về `RouterOutputDTO` ở phân nhánh `CATALOG_DISCOVERY` vẫn mang `active_quest=curr_quest` (frame cũ từ lượt trước), làm mất hoàn toàn slot phòng ban vừa trích xuất được và khiến các lượt hội thoại tiếp theo không thể kế thừa ngữ cảnh.
- **Nguyên nhân gốc rễ:**
  Tại phân nhánh `if parsed.intent == "CATALOG_DISCOVERY"` trong `intent_router.py`, hàm khởi tạo `RouterOutputDTO` sử dụng biến `active_quest=curr_quest` (trạng thái trước khi cập nhật lượt mới) thay vì `active_quest=active_quest` (trạng thái đã được cập nhật bởi `self.hdft_tracker.update_state`).
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Tuyệt đối không gán `active_quest=curr_quest` trong các phân nhánh định tuyến nằm sau lệnh gọi `self.hdft_tracker.update_state`.
  * ✅ **ALWAYS:** Luôn gán `active_quest=active_quest`, `active_quest_preserved=True if active_quest else False`, và `active_quest_action=QuestActionEnum.INIT if not curr_quest else QuestActionEnum.PRESERVE` để bảo đảm cấu trúc trạng thái đối thoại trả về luôn phản ánh chính xác các slot vừa được cập nhật và làm giàu trong lượt hiện tại.

---

### [TRAP-086] Bẫy Coi Mọi Chỉ Tiêu Cha Là Rỗng (`SC-2.4a` vs `SC-2.4b`), Cướp Quyền `DIMENSION_LISTING` Khi Câu Hỏi Có Từ `"số lượng"` + Ngày Tháng Trên `DUPLICATE_LEAF`, Và Gọi Sớm Vector Embedding Trước `classify_criterion_hierarchy`
- **Môi trường & Công nghệ:** `DuckDBSemanticCatalog` / `CanonicalSemanticNormalizer` / `WarehouseLangGraphAgent` / `DiscourseStateTracker` / `DWHConnectionPool`
- **Triệu chứng:**
  1. Trong kho dữ liệu `vna_wom_dev`, có 5 chỉ tiêu cha (`is_leaf = FALSE`) thực sự có số liệu tổng hợp đã phê duyệt (`Tổng số lượng chủ thể sản phẩm OCOP trong năm` = `17`, `Tổng số lượng sản phẩm OCOP trong năm` = `32`, `Số lượng HTX phân theo lĩnh vực` = `138`, `Tổng diện tích sản xuất muối` = `0` / `1.520`, `Tổng sản lượng muối` = `0` / `27.000`). Nếu mặc định coi mọi chỉ tiêu cha đều không có số liệu, người dùng bị mất số liệu tổng hợp của chỉ tiêu cha.
  2. Khi người dùng hỏi `"số lượng chỉ tiêu trồng trọt ngày 30/4"`, `is_dimension_query` khớp từ `"số lượng"` + `"chỉ tiêu"` và phân loại nhầm sang `DIMENSION_LISTING` thay vì `METRIC_POINT_INQUIRY` (`SC-2.1` + `🎫 Ticket Thời Gian`), đồng thời nhánh `SC-2.1` chỉ chạy khi `len(rows) == 1` hoặc ghi đè bằng `br.get("latest_value")` không lọc theo ngày.
  3. Gọi `find_top_k_candidates` / `resolve_metric_id` trước khi kiểm tra `classify_criterion_hierarchy` trong DuckDB RAM làm kích hoạt nạp mô hình SentenceTransformers (`~22s`) không cần thiết.
- **Nguyên nhân gốc rễ:**
  1. Chưa tách bạch `SC-2.4a` (chỉ tiêu cha có số liệu $\to$ hiển thị Thẻ 5 Trường Chuẩn + bảng 1 dòng + các nút gợi ý chỉ tiêu con) và `SC-2.4b` (chỉ tiêu cha không có số liệu $\to$ giải thích nhóm cha + các nút gợi ý chỉ tiêu con).
  2. `is_dimension_query` chưa kiểm tra `classify_criterion_hierarchy` để loại trừ trường hợp câu hỏi đang nhắm tới một chỉ tiêu lá/cha cụ thể; `compile_canonical_sql` chưa đưa `lf.criteria_id` vào mệnh đề `SELECT` ngoài của `METRIC_POINT_INQUIRY`.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không mặc định mọi chỉ tiêu cha đều rỗng; Không để `is_dimension_query` trả về `True` khi `classify_criterion_hierarchy` khớp chỉ tiêu cụ thể (`single_leaf`, `duplicate_leaf`, `parent`, `parent_group`); Không fallback về `br.get("latest_value")` khi đang có bộ lọc thời gian (`has_temporal_point_or_range=True`).
  * ✅ **ALWAYS:**
    1. Kiểm tra `not _is_empty_or_dash(parent_val)` trong `SC-2.4` để hiển thị **Thẻ 5 Trường Chuẩn + Bảng 1 dòng + Nút gợi ý chỉ tiêu con** (`SC-2.4a`), và chỉ hiển thị thông báo nhóm cha rỗng khi `_is_empty_or_dash(parent_val)` (`SC-2.4b`).
    2. Bổ sung `lf.criteria_id` vào `SELECT` ngoài của `METRIC_POINT_INQUIRY` và đối chiếu `str(r.get("criteria_id")) == str(br.get("id"))` trong `SC-2.1` để hiển thị chính xác bảng 6 cột theo đúng mốc thời gian (`31/03/2026` cho ngày `30/04`).
    3. Ưu tiên kiểm tra `classify_criterion_hierarchy` trong DuckDB RAM trước khi gọi `find_top_k_candidates`, và tái sử dụng kết nối TCP đồng bộ (`_sync_conn`) trong `DWHConnectionPool.execute_sync_fallback`.

---

### [TRAP-087] Bẫy Bỏ Sót Bộ Lọc Nhiệm Vụ (`mis_filter_draft`) Trong Truy Vấn Đối Chiếu Chênh Lệch Bản Nháp (`SC-5.1b` `diff_sql`) Và Tiêm Nhãn Phân Cấp Cấu Trúc Vào Truy Vấn Drill-Down Ngăn Ghim Tham Chiếu (`PinnedReferenceDrawer`)
- **Môi trường & Công nghệ:** `WarehouseLangGraphAgent` (`SC-5.1b`) / `PinnedReferenceDrawer.tsx` / `SmartTable.tsx`
- **Triệu chứng:**
  1. Khi người dùng hỏi chi tiết các chỉ tiêu bản nháp và đối chiếu chênh lệch của một nhiệm vụ cụ thể (ví dụ: `"nhiệm vụ Diêm nghiệp năm 2026"` — `SC-5.1b`), bảng 1 (`draft_detail_sql`) lọc đúng `14` dòng của `Diêm nghiệp`, nhưng bảng 2 (`diff_sql` — đối chiếu chênh lệch giữa Bản nháp mới nhất và Bản đã phê duyệt) lại trả về `72` dòng của toàn bộ các nhiệm vụ (bao gồm cả `Phát triển nông thôn`) thay vì `6` dòng có chênh lệch của `Diêm nghiệp`.
  2. Trên giao diện `PinnedReferenceDrawer`, khi người dùng ghim bảng danh mục chỉ tiêu Cấp 1 (`SC-1.1a`) có cột `Loại chỉ tiêu / Phân nhóm cha` mang giá trị cấu trúc `"Nhóm chỉ tiêu (2 chỉ tiêu con)"` và bấm vào dòng `Tổng diện tích sản xuất muối` để đối chiếu số liệu Quý 2, hàm `handleRowDrilldown` ghép nguyên chuỗi `"Nhóm chỉ tiêu (2 chỉ tiêu con)"` vào câu hỏi gửi đi, làm hỏng truy vấn ngôn ngữ tự nhiên.
- **Nguyên nhân gốc rễ:**
  1. Trong `warehouse_langgraph_agent.py`, biến `mis_filter_draft` (`AND f.mission_name ILIKE '%...%'`) được đưa vào `draft_detail_sql` nhưng bị bỏ sót trong 2 CTE `latest_approved` và `latest_draft` của `diff_sql`.
  2. Trong `PinnedReferenceDrawer.tsx`, `handleRowDrilldown` chỉ loại trừ `'Chỉ tiêu gốc'` khỏi `parentCtx` mà chưa loại trừ các nhãn mô tả cấu trúc Cấp 1 như `'Nhóm chỉ tiêu'` hoặc `'Chỉ tiêu đơn'`.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không bao giờ áp dụng bộ lọc phạm vi (`target_mission`, `tenant_code`, `year_code`) ở một truy vấn con mà bỏ sót ở truy vấn đối chiếu đi kèm trong cùng một kịch bản; Không ghép các nhãn mô tả cấu trúc (`Nhóm chỉ tiêu (...)`, `Chỉ tiêu đơn`) làm ngữ cảnh tên nhóm cha trong câu hỏi drill-down.
  * ✅ **ALWAYS:**
    1. Truyền nhất quán `{mis_filter_draft}` vào cả `draft_detail_sql` lẫn hai CTE `latest_approved` và `latest_draft` của `diff_sql`.
    2. Kiểm tra loại trừ `!parentCtx.startsWith('Nhóm chỉ tiêu') && !parentCtx.startsWith('Chỉ tiêu đơn')` trước khi nối `parentCtx` vào câu hỏi drill-down trong `PinnedReferenceDrawer.tsx`.

---

### [TRAP-088] Bẫy Trùng Lặp Nút Gợi Ý Chỉ Tiêu Con Inline & Đứt Gãy Đồng Bộ State Thời Gian (Duplicate Inline Child Action Chips & Broken Reactive Timeline State Synchronization)
- **Môi trường & Công nghệ:** `SingleMetricSliderCard.tsx` / `MessageItem.tsx` / `warehouse_langgraph_agent.py` (`SC-2.4`, `REQ-Q02`)
- **Triệu chứng:**
  1. Người dùng nhìn thấy danh sách chỉ tiêu con xuất hiện 2 lần trong cùng một phản hồi: một lần dạng văn bản thô inline (`🔘 [Tên con 1]  🔘 [Tên con 2]...`) ở cuối đoạn văn bản markdown, và một lần dạng các nút bấm tương tác (`QuickActionChips`) ở đáy tin nhắn.
  2. Khi người dùng bấm chuyển đổi giữa các kỳ báo cáo (`31/03/2026`, `30/06/2026`, `30/09/2026` hoặc ngày tùy chỉnh) trên thẻ mốc thời gian, số liệu `Giá trị:` và `Thời điểm báo cáo:` trong đoạn văn bản 5 trường chi tiết bên dưới và huy hiệu số liệu xem trước (`preview_value`) trên các nút action chips con ở đáy không thay đổi, vẫn bị đóng băng ở kỳ báo cáo ban đầu dù thẻ thời gian đã chuyển sang kỳ mới.
- **Nguyên nhân gốc rễ:**
  1. Tại backend (`warehouse_langgraph_agent.py`), chuỗi `chip_md = "  ".join([c["label"] for c in chips])` được nối cứng vào văn bản `ans` trước khi trả về, trong khi frontend `MessageItem.tsx` lại tự động render `<QuickActionChips chips={message.quick_action_chips} />`.
  2. State mốc thời gian (`selectedIdx`, `activeSnapshot`) bị cô lập cục bộ bên trong `SingleMetricSliderCard.tsx`, không phát sự kiện đồng bộ lên component cha `MessageItem`, dẫn đến khối văn bản tĩnh markdown và component `QuickActionChips` không nhận được sự kiện thay đổi mốc thời gian để cập nhật lại số liệu.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Tuyệt đối không nối chuỗi markdown inline `🔘 [...]` vào câu trả lời khi DTO đã có trường `quick_action_chips`; Không giam giữ state thời gian cục bộ trong card con khi các thành phần khác trong tin nhắn cần phản ứng theo kỳ được chọn.
  * ✅ **ALWAYS:**
    1. Chỉ trả về danh sách nút con qua mảng DTO `quick_action_chips`, loại bỏ hoàn toàn việc ghép chuỗi `{chip_md}` vào markdown văn bản ở backend.
    2. Trong `MessageItem.tsx`, triển khai regex phòng vệ để lọc sạch mọi chuỗi text inline `🔘 [...]` còn sót lại, đảm bảo các nút gợi ý chỉ xuất hiện duy nhất 1 lần ở đáy tin nhắn.
    3. Nâng state mốc thời gian lên `MessageItemComponent` thông qua prop callback `onTimelineChange(snapshot, shiftNotice)`, sử dụng regex thay thế tức thì `0ms Client-side` cho 5 trường thông tin chi tiết và cập nhật `reactiveChips` đồng bộ số liệu trên toàn bộ preview badges.

---

### [TRAP-089] Bẫy So Khớp Token Mờ Khi Phân Giải Chỉ Tiêu Lũy Kế & Cấu Trúc Phân Cấp (Blurry Token Overlap vs Hierarchical Cumulative Scope)
- **Môi trường & Công nghệ:** `DuckDBSemanticCatalog` / `find_top_k_candidates` / `warehouse_langgraph_agent.py` (`SC-2.5`, `SC-2.6`, `R3`, `R4`)
- **Triệu chứng:**
  1. Khi người dùng hỏi chỉ tiêu tổng lũy kế (ví dụ: *"lũy kế tổng số lượng chủ thể sản phẩm..."* hoặc *"lũy kế tổng số lượng chủ thể sản phẩm OCOP..."*), thuật toán so khớp token mờ truyền thống xếp các nút lá con mang xếp hạng sao (`Số lượng chủ thể sản phẩm OCOP 5 sao`) hoặc nhóm hàng năm (`Tổng số lượng chủ thể sản phẩm OCOP trong năm`) lên vị trí Top 1 do có mật độ trùng lặp từ khóa (*"sản phẩm"*, *"OCOP"*) rất cao.
  2. Các chỉ tiêu có tên dài hoặc có khoảng trắng đôi trong CSDL (`"Lũy kế  tổng số lượng..."`) bị rớt khỏi Top-5 ứng viên thô ban đầu (`candidate_pool_size = top_k`), khiến chúng bị cắt tỉa sớm trước khi bộ reranker có cơ hội chấm điểm.
  3. Khi người dùng hỏi về cấu trúc phân cấp (ví dụ: *"số lĩnh vực của HTX"*, *"các mức đánh giá hiệu quả hoạt động của hợp tác xã"*, *"đang có các loại diện tích sản xuất muối gì?"*), hệ thống hiểu nhầm là truy vấn số đo tổng hợp đơn lẻ hoặc bị nuốt nhầm sang các nhánh thực thể khác có cùng tên nhóm con (như nhầm `'Hiệu quả hoạt động'` của HTX sang THT hoặc Trang trại).
- **Nguyên nhân gốc rễ:**
  1. Thiếu cơ chế phân biệt tính phân cực thời gian (Temporal Polarity: lũy kế vs trong năm) và không có điểm phạt cho các thuộc tính đặc thù hẹp (sao OCOP) khi người dùng không hỏi đích danh.
  2. Kích thước tập ứng viên ban đầu quá nhỏ (`limit = top_k`), gây nghẽn cổ chai cắt tỉa sớm (Early Truncation Trap).
  3. Thiếu cơ chế Neo Thực thể Gốc (Entity Root Anchoring) kết hợp chỉ dấu phân nhóm (aspect cues) để phân giải ngữ nghĩa câu hỏi đếm/liệt kê danh mục con.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không dựa thuần túy vào độ tương đồng token Jaccard/BM25 đối với các cụm chỉ tiêu có cấu trúc đa tầng OCOP; Không cố định kích thước candidate pool bằng `top_k`; Không phân loại câu hỏi cấu trúc danh mục con thành câu hỏi lấy số đo đơn lẻ.
  * ✅ **ALWAYS:**
    1. Mở rộng kích thước tập ứng viên: `candidate_pool_size = max(top_k * 5, 25)` trong `find_criteria_by_name`.
    2. Áp dụng cơ chế chấm điểm phân cực thời gian: $+25.0$ cho ứng viên lũy kế và $-30.0$ cho ứng viên hàng năm khi câu hỏi có tín hiệu lũy kế.
    3. Áp dụng điểm phạt tính đặc thù sao OCOP: $-25.0$ cho tất cả các nút lá mang xếp hạng sao khi người dùng không hỏi cụ thể 3 sao, 4 sao hay 5 sao.
    4. Áp dụng điểm phân cực đối tượng: $+15.0$ cho ứng viên chứa *chủ thể* khi câu hỏi hỏi về *chủ thể* mà không hỏi riêng *sản phẩm*.
    5. Xây dựng hàm `resolve_hierarchy_breakdown` neo đúng thực thể gốc DWH (`'HTX nông nghiệp'`, `'Diêm nghiệp'`...) và dùng aspect cues (*lĩnh vực*, *hiệu quả*, *diện tích*...) để xuất đúng số lượng, tên in đậm và bảng 6 cột chuẩn hóa.

---

### [TRAP-090] Bẫy `getattr(settings, ...)` Trả Về `None` & Lỗi `JSONDecodeError: Extra data` Khi Parse Output LLM
- **Môi trường & Công nghệ:** `canonical_normalizer.py` (`_parse_query_nlu_llm`), `duckdb_semantic_catalog.py` (`_llm_disambiguate`), Pydantic `Settings`
- **Triệu chứng:**
  1. Gọi `getattr(settings, "OPENROUTER_ROUTER_MODEL", "google/gemini-2.5-flash-lite")` trả về `None` khiến `ChatOpenAI(model=None)` định tuyến sang auto-router của OpenRouter mất 30–45 giây và làm timeout kết nối SSE.
  2. Hàm trích xuất JSON bằng `raw_text[raw_text.find("{"):raw_text.rfind("}")+1]` ném lỗi `JSONDecodeError: Extra data: line 2 column 2` khi LLM sinh ra 2 khối JSON liên tiếp.
- **Nguyên nhân gốc rễ:**
  1. Thuộc tính `OPENROUTER_ROUTER_MODEL: Optional[str] = None` đã tồn tại trên class `Settings` với giá trị `None`, nên `getattr` lấy giá trị `None` thay vì giá trị mặc định.
  2. Tìm `{` đầu tiên và `}` cuối cùng sẽ gộp cả 2 object JSON nếu LLM lặp lại câu trả lời.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không dùng `getattr(settings, "FIELD", "default")` đơn thuần cho các biến cấu hình `Optional[str] = None`; Không dùng `find("{")..rfind("}")` để cắt chuỗi JSON từ LLM.
  * ✅ **ALWAYS:**
    1. Dùng `getattr(settings, "OPENROUTER_ROUTER_MODEL", None) or "google/gemini-2.5-flash-lite"` kèm `timeout=5.0, max_retries=0`.
    2. Dùng `json.JSONDecoder(strict=False).raw_decode(raw_text[s_idx:])[0]` để bóc tách chính xác object JSON hợp lệ đầu tiên.

---

### [TRAP-091] Bẫy Kẹp Ngưỡng `max(score, floor)` Sau Phép Trừ Phạt Phân Cực Làm Mất Tác Dụng Của Penalty Deltas
- **Môi trường & Công nghệ:** `DuckDBSemanticCatalog._retrieve_candidate_metrics` / `_compute_candidate_score`
- **Triệu chứng:**
  Khi câu hỏi chứa từ khóa lũy kế (hoặc không hỏi về xếp hạng sao OCOP), các ứng viên hàng năm hoặc ứng viên lá con mang sao OCOP nhận điểm phạt âm lớn ($\Delta_{\text{temporal}} = -30.0$, $\Delta_{\text{star}} = -25.0$). Tuy nhiên, thuật toán chấm điểm kẹp `final_score = max(score, floor)` ở cuối cùng với `floor = 50.0`. Khi điểm ban đầu của ứng viên là `60.0` và bị trừ `-30.0` thành `30.0`, phép kẹp `max(30.0, 50.0)` đẩy điểm ngược trở lại `50.0`, làm vô hiệu hóa hoàn toàn độ chênh phạt (penalty delta) và khiến ứng viên bị phạt vẫn có điểm số xấp xỉ ứng viên đúng, dẫn đến việc chọn sai chỉ tiêu lá hoặc sai phân cực thời gian.
- **Nguyên nhân gốc rễ:**
  Áp dụng ngưỡng sàn `floor` sau khi đã tính toán toàn bộ các điều chỉnh phân cực và điểm cấu trúc, thay vì độc lập hóa ngưỡng sàn cơ sở ngay từ đầu.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Tuyệt đối không kẹp `max(score, floor)` ở bước cuối cùng sau khi đã áp dụng các hệ số phạt âm (`penalty deltas`).
  * ✅ **ALWAYS:**
    Tách rời ngưỡng sàn cơ sở: `base_floor = max(base_score, floor)` trước khi cộng điểm cấu trúc và trừ điểm phạt:
    `final_score = base_floor + structural_delta - penalty_delta`.

---

### [TRAP-092] Bẫy Khử Trùng Lặp Ứng Viên Bằng Tên Đơn Thuần (`name`) Làm Loại Bỏ Sớm Ứng Viên Đồng Âm Khác Nhánh Cha
- **Môi trường & Công nghệ:** `DuckDBSemanticCatalog._retrieve_candidate_metrics` / `find_top_k_candidates`
- **Triệu chứng:**
  Khi nhiều nhánh cha khác nhau trong CSDL chia sẻ cùng tên chỉ tiêu lá (như `'Chăn nuôi'`, `'Trồng trọt'`, `'Lâm nghiệp'` cùng xuất hiện dưới `HTX nông nghiệp`, `Liên hiệp HTX nông nghiệp`, `Tổ hợp tác nông nghiệp`, `Trang trại`), bước tiền xử lý khử trùng lặp sử dụng `set(name)` hoặc từ điển `seen[clean_name]`. Thao tác này chỉ giữ lại bản ghi đầu tiên bắt gặp và loại bỏ tất cả các bản ghi ở các nhánh cha còn lại. Khi người dùng hỏi chỉ tiêu kèm đích danh nhánh cha (ví dụ: *"cho tôi biết số liệu chăn nuôi của liên hiệp hợp tác xã"*), ứng viên `'Chăn nuôi'` của Liên hiệp HTX đã bị loại bỏ sớm từ vòng ngoài, khiến hệ thống không thể phân giải đúng nhánh hoặc rớt về fallback.
- **Nguyên nhân gốc rễ:**
  Khử trùng lặp chỉ dựa trên tên đơn thuần của chỉ tiêu (`clean_name`) mà bỏ qua khóa ngữ cảnh phân cấp gốc (`root_name`).
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Tuyệt đối không khử trùng lặp tập ứng viên chỉ bằng tên chỉ tiêu `clean_name` đối với các kho dữ liệu có chỉ tiêu đồng âm đa nhánh.
  * ✅ **ALWAYS:**
    Sử dụng khóa tổ hợp `(clean_name, root_name)` khi lưu và lọc trùng lặp tập ứng viên `candidate_metrics` trong `_retrieve_candidate_metrics`.

---

### [TRAP-093] Bẫy Fallback Quét Văn Bản Trên `fact_report_criteria` Gây Dương Tính Giả Cho Câu Hỏi Toán Học & Thủ Tục Hành Chính Ngoài Phạm Vi
- **Môi trường & Công nghệ:** `WarehouseLangGraphAgent` / `duckdb_semantic_catalog.py` / `canonical_normalizer.py`
- **Triệu chứng:**
  Khi người dùng nhập các câu hỏi toán học số học (ví dụ: `"3 mũ 2"`, `"tính 15 nhân 20"`) hoặc câu hỏi thủ tục hành chính công ngoài DWH (ví dụ: `"thủ tục làm sổ đỏ"`, `"hướng dẫn đăng ký kết hôn"`), catalog không tìm thấy ứng viên ngữ nghĩa tương ứng (`candidates == []`). Hệ thống kích hoạt cơ chế fallback quét text SQL `WHERE f.name ILIKE '%...%'` trên bảng `fact_report_criteria`. Do các từ như `"mũ"`, `"tính"`, `"thủ tục"`, `"kết"` có thể xuất hiện ngẫu nhiên trong các tên chỉ tiêu hoặc văn bản ghi chú báo cáo, câu lệnh SQL sinh ra khớp nhầm vào các bản ghi không liên quan và trả về số liệu sai, vi phạm tiêu chuẩn an toàn ngoài phạm vi (OOS).
- **Nguyên nhân gốc rễ:**
  Thiếu tầng phân loại và chặn sớm các câu hỏi ngoài phạm vi nghiệp vụ DWH (Early Out-of-Scope Guard) trước khi bước vào pipeline truy vấn fact data.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không bao giờ fallback về truy vấn LIKE/ILIKE văn bản trên bảng fact khi catalog rỗng mà chưa kiểm tra câu hỏi có thuộc phạm vi OOS hay không.
  * ✅ **ALWAYS:**
    Triển khai bộ phân loại sớm Regex Out-of-Scope (toán học số học, thủ tục hành chính ngoài DWH) ngay tại đầu pipeline normalizer/router. Khi phát hiện câu hỏi OOS, thiết lập ngay `is_out_of_scope = True`, `sql = None` và trả về thông báo từ chối an toàn (Polite Refusal), triệt tiêu hoàn toàn việc sinh SQL giả.

---

### [TRAP-094] Bẫy Suy Diễn Kiểu `any` Lan Truyền Qua `useMemo` (`TS7006`) Và Quét File Test Trong Next.js Production Build Trên Render
- **Môi trường & Công nghệ:** Next.js 14 (`next build`) / TypeScript Strict Mode / `SmartTable.tsx` / `tsconfig.json` / Render Cloud Build
- **Triệu chứng:**
  Khi deploy `ipgov-chatbot-frontend` lên Render (`npm install && npm run build`), bước `Checking validity of types ...` thất bại với lỗi `Type error: Parameter 'r' implicitly has an 'any' type` tại `SmartTable.tsx:1987` và các lỗi kiểm tra kiểu trên các file kiểm thử trong `src/components/chat/__tests__/`.
- **Nguyên nhân gốc rễ:**
  1. Trong `SmartTable.tsx`, biến `periodSnapshots = (tabularData as any)?.period_snapshots` có kiểu `any`. Khi `periodAdjustedRows = useMemo(() => { ... return periodSnapshots[activePeriod]; })` không khai báo kiểu trả về tường minh, TypeScript suy diễn kiểu của `periodAdjustedRows` thành `any` thay vì `Record<string, any>[]`, kéo theo toàn bộ các hàm `.filter((r) => ...)` phía sau bị mất kiểu của `r` và vi phạm `noImplicitAny`.
  2. `tsconfig.json` để `"include": ["**/*.ts", "**/*.tsx"]` mà chưa loại trừ `"**/__tests__/**"` và `"**/*.test.tsx"` khỏi quá trình build production của Next.js.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không để `useMemo` trả về giá trị truy cập từ biến `as any` mà không khai báo kiểu trả về tường minh; Không để `next build` quét các file unit test nội bộ.
  * ✅ **ALWAYS:**
    1. Khai báo kiểu trả về tường minh `useMemo((): Record<string, any>[] => ...)` cho các mảng dữ liệu bảng.
    2. Cập nhật đầy đủ các trường mở rộng (`tree_modal`, `trees_by_root_id`, `level1_rows`, `period_snapshots`) vào interface `TabularData` trong `src/types/chat.ts` và thêm `"**/__tests__/**"`, `"**/*.test.ts"`, `"**/*.test.tsx"` vào `exclude` của `tsconfig.json`.

---

### [TRAP-095] Bẫy Bỏ Quên Hydrate `timeline_values` / `period_values` Từ Backend Cho Các Dòng `SmartTable` Khi Chuyển Đổi Ticket Kỳ Báo Cáo 0ms Tại Chỗ
- **Môi trường & Công nghệ:** `SmartTable.tsx` (`periodAdjustedRows`) / `MessageItem.tsx` / `warehouse_langgraph_agent.py` (`resolve_hierarchy_breakdown`, `duplicate_leaf`, `l1_formatted`) / `duckdb_semantic_catalog.py` (`get_batch_period_values`)
- **Triệu chứng:**
  Khi người dùng hỏi các mức đánh giá hiệu quả hoạt động của HTX (nhánh R3 `resolve_hierarchy_breakdown` hoặc SC-2.1 `duplicate_leaf`), bảng `SmartTable` hiển thị số liệu năm 2026 (`56; 55; 16; 3`, giá trị cha `130`). Khi người dùng bấm vào các nút ticket kỳ báo cáo (`Quý 1`, `Quý 2`, `Quý 3`) trên thanh `smart-table-context-ticket-bar`, nút chuyển sang trạng thái active nhưng các con số trong bảng vẫn đứng yên ở `56; 55; 16; 3` thay vì đổi tại chỗ thành `57; 55; 16; 0` (Quý 2) hoặc `56; 50; 16; 0` (Quý 1).
- **Nguyên nhân gốc rễ:**
  `SmartTable.tsx` đã chuyển sang cơ chế lọc kỳ báo cáo tại chỗ 0ms client-side (`periodAdjustedRows`) dựa trên `r.timeline_values` hoặc `r.period_values` của từng dòng (và test unit chỉ mock sẵn `timeline_values` trong fixture). Tuy nhiên, `warehouse_langgraph_agent.py` khi đóng gói `table_rows` (R3), `multi_rows` (SC-2.1), và `l1_formatted` (REQ-Q01/Q04) chỉ gán `value` đơn lẻ của kỳ hiện tại mà chưa gọi truy vấn batch sang PostgreSQL `fact_report_criteria` để đính kèm `timeline_values` (`year`, `q1`, `q2`, `q3`, và ngày `YYYY-MM-DD`/`DD/MM/YYYY`) cho từng dòng và `parent_timeline_values` cho chỉ tiêu cha.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không bao giờ chỉ mock `timeline_values` trong unit test frontend mà quên bơm dữ liệu thật từ tầng `DuckDBSemanticCatalog` / `WarehouseLangGraphAgent` xuống payload `tabular_data.rows`.
  * ✅ **ALWAYS:**
    1. Bắt buộc gọi `self.catalog.get_batch_period_values(...)` để nạp đầy đủ `timeline_values` / `period_values` (`year`, `q1`, `q2`, `q3`, `YYYY-MM-DD`, `DD/MM/YYYY`) cho từng dòng trong `table_rows`, `multi_rows`, `l1_formatted` và `parent_timeline_values` cho `tabular_data`.
    2. Giữ tham chiếu hàm `onPeriodChange` ổn định bằng `React.useCallback(..., [])` trong `MessageItem.tsx` để `markdownComponents.table` không bị tạo lại mỗi lần bấm nút kỳ báo cáo (tránh làm React unmount và reset state `activePeriod` của `SmartTable`).

---

### [TRAP-096] Bẫy Ghi Đè Số Liệu Ngày Cụ Thể Bằng `pMap['year']` Khi Mount `SmartTable`, Lệch `query_text` Của `QuickActionChips`, Và Khởi Tạo Lặp `DuckDBSemanticCatalog` Khi Hydrate Lịch Sử
- **Môi trường & Công nghệ:** `SmartTable.tsx` (`initialTemporalInfo`, `periodAdjustedRows`, `handlePinTable`) / `MessageItem.tsx` (`reactiveChips`) / `ChatHistoryStore` (`_hydrate_legacy_timeline_values`) / `storage.ts` (`mergeSessions`)
- **Triệu chứng:**
  1. Khi người dùng hỏi phân rã chỉ tiêu kèm ngày cụ thể hoặc tháng/khoảng ngày (ví dụ: *"các mức đánh giá hiệu quả hoạt động của hợp tác xã ngày 31/03/2026"*), Backend tính đúng `- **Giá trị:** 122` và `rows = [56, 50, 16, 0]`, nhưng `temporal_scope.period_label` là `"tính đến 31/03/2026"` (không chứa chữ `"quý 1"`). Khi `SmartTable` mount, `initialTemporalPeriod` rơi về mặc định `'year'` và `periodAdjustedRows` lập tức ghi đè `[56, 50, 16, 0]` bằng `pMap['year']` (`[56, 55, 16, 3]`), gây mâu thuẫn giữa dòng tổng hợp phía trên (`122`) và bảng phía dưới (`130`).
  2. Khi chuyển kỳ báo cáo trên bảng sang `Quý 2` hoặc `Tùy chỉnh ngày`, `reactiveChips` trong `MessageItem.tsx` chỉ tra khớp chuỗi tuyệt đối `cMap[tablePeriod.customDate]` (bỏ sót chuẩn hóa `DD/MM/YYYY <-> YYYY-MM-DD` và mốc `<= isoCustom`), đồng thời giữ nguyên `chip.query_text` ở `"năm 2026"` thay vì cập nhật sang kỳ đang chọn, và nút `📌 Ghim` (`handlePinTable`) ghim mảng `rows` gốc thay vì `periodAdjustedRows`.
  3. Khi tự động làm giàu (`lazy hydration`) `timeline_values` cho các phiên hội thoại cũ trong `chat_history.sqlite3`, việc gọi `DuckDBSemanticCatalog()` bên trong vòng lặp tin nhắn gây khởi tạo lặp lại DuckDB hàng chục lần.
- **Nguyên nhân gốc rễ:**
  1. `initialTemporalPeriod` chỉ kiểm tra chuỗi `'quý 1'|'quý 2'|'quý 3'` mà bỏ qua `specific_date`, `month_filter`, `date_from`/`date_to` trong `temporal_scope`, đồng thời `periodAdjustedRows` ghi đè ngay cả khi người dùng chưa bấm đổi kỳ (`!hasUserChangedPeriod`).
  2. Thiếu hàm phân giải mốc thời gian thống nhất giữa `SmartTable` và `MessageItem.reactiveChips`, và thiếu cache singleton `self._catalog` trong `ChatHistoryStore`.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không để `periodAdjustedRows` tự ý ghi đè giá trị dòng bằng `pMap['year']` khi câu hỏi gốc có bộ lọc thời gian đặc thù và người dùng chưa bấm chuyển kỳ; Không khởi tạo `DuckDBSemanticCatalog()` bên trong vòng lặp duyệt tin nhắn lịch sử.
  * ✅ **ALWAYS:**
    1. Phân tích đầy đủ `specific_date`, `month_filter`, `date_from`, `date_to` trong `initialTemporalInfo` và giữ nguyên `rows` gốc khi `!hasUserChangedPeriod && hasCustomBackendRange`.
    2. Đồng bộ `periodAdjustedRows` vào `handlePinTable`, bộ đếm bộ lọc nhanh, `activeTreeNodes`, và đồng bộ cả `preview_value` lẫn `query_text` của `QuickActionChips` theo `tablePeriod`.
    3. Cache `self._catalog` trên instance `ChatHistoryStore` và ghi nhận kết quả hydrate vào SQLite để các lần đọc sau đạt độ trễ 0ms.

---

### [TRAP-097] Bẫy Rò Rỉ `position: absolute` Của `.sr-only` Ra Khỏi Thẻ Con Kết Hợp `scrollIntoView()` Cuộn Khung Cha `overflow-hidden` Làm Biến Mất Khung Chat
- **Môi trường & Công nghệ:** `SingleMetricSliderCard.tsx` / `MessageList.tsx` / `ChatContainer.tsx` / Tailwind CSS (`.sr-only`) / W3C CSSOM View (`Element.scrollIntoView`)
- **Triệu chứng:**
  Khi mở hoặc thực thi phiên hội thoại dài 5 lượt có chứa thẻ `SingleMetricSliderCard` ở cuối danh sách (ví dụ phiên 10 tin nhắn `"bạn hãy cho tôi biết lũy kế tổng số lượng..."` kết thúc bằng câu `"cho tôi biết số liệu chăn nuôi của liên hiệp hợp tác xã ngày 30/4"`), toàn bộ thanh `<header>` và vùng danh sách tin nhắn `<MessageList>` biến mất khỏi màn hình, chỉ còn thanh nhập liệu `<ChatInput>` bị đẩy nhảy lên sát mép trên cùng (`y = 24px`) kèm khoảng trắng rỗng 969px phía dưới.
- **Nguyên nhân gốc rễ:**
  1. Trong `SingleMetricSliderCard.tsx`, hai thẻ `<span className="sr-only">` (`slider-active-value` và `slider-delta-badge`) mang thuộc tính `position: absolute` với `top: auto; left: auto`. Do cả `SingleMetricSliderCard` lẫn `MessageList` đều không có `position: relative`, khối chứa định vị (containing block) của `.sr-only` bị rò rỉ ra tận khung cột phải `div.flex-1.flex.flex-col.h-full.bg-white.relative.overflow-hidden` trong `ChatContainer.tsx`. Ở tin nhắn thứ 10 (`y = 4083px`), thẻ `.sr-only` làm `scrollHeight` của khung cột phải phình từ `1080px` lên `4083px`.
  2. Ngay sau đó, `MessageList.tsx` gọi `bottomRef.current?.scrollIntoView({ behavior: 'smooth' })`. Theo đặc tả W3C CSSOM View, `scrollIntoView()` cuộn **mọi** khung chứa tổ tiên có nội dung tràn—kể cả phần tử có `overflow: hidden` (programmatic scroll container). Khung cột phải bị cuộn tới `scrollTop = 969px`, đẩy `<header>` (`y = -969px`) và `<MessageList>` (`y = -892px..+24px`) văng hoàn toàn lên phía trên mép màn hình.
  3. Ngoài ra, hai thẻ bọc flex dưới `<header>` trong `ChatContainer.tsx` dùng `h-full` (`height: 100%`) thay vì `min-h-0`, làm chiều cao tổng cộng vượt quá khung cha một khoảng đúng bằng chiều cao header (`77px`).
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Tuyệt đối không đặt phần tử `.sr-only` (`position: absolute`) bên trong component con mà không có `position: relative` trên thẻ gốc của component đó; Không dùng `bottomRef.current.scrollIntoView()` trong giao diện đa khung lồng nhau có `overflow-hidden`; Không dùng `flex-1 h-full` cho phần tử flex con nằm cùng cấp với `<header>`.
  * ✅ **ALWAYS:**
    1. Đặt `relative` trên thẻ gốc của `SingleMetricSliderCard` và thêm `top-0 left-0` cho mọi phần tử `.sr-only`.
    2. Trong `MessageList.tsx`, thêm `min-h-0 relative` vào container cuộn và chỉ cuộn trực tiếp `scrollContainerRef.current.scrollTo({ top: container.scrollHeight, behavior: 'smooth' })` thay vì `scrollIntoView()`.
    3. Trong `ChatContainer.tsx`, dùng `flex-1 flex overflow-hidden min-h-0 relative` cho các khung flex dưới `<header>`.

---

### [TRAP-098] Bẫy Toán Tử Nullish Coalescing `localShiftNotice ?? card.temporal_shift_notice` Giữ Kẹt Cảnh Báo Lệch Ngày Và Bẫy Đếm Lệch `11 tin nhắn` Do Lưu Thẻ `welcome-*` Vào `localStorage`
- **Môi trường & Công nghệ:** `SingleMetricSliderCard.tsx` / `MessageItem.tsx` / `ChatContainer.tsx` / `storage.ts`
- **Triệu chứng:**
  1. Ở câu hỏi tra cứu ngày lệch đợt chốt sổ (ví dụ: *"cho tôi biết số liệu chăn nuôi của liên hiệp hợp tác xã ngày 30/4"*), khi người dùng bấm chuyển sang nút kỳ báo cáo chính xác `Kỳ Q3 (30/09/2026)`, hộp cảnh báo màu vàng `"Ngày tra cứu 30/04/2026 không trùng đợt chốt sổ... đối chiếu mốc gần nhất ngày 31/03/2026"` trong `SingleMetricSliderCard` và câu dẫn `(ngày 31/03/2026):` bên dưới vẫn không biến mất, gây mâu thuẫn với dòng `- **Thời điểm báo cáo:** 30/09/2026`.
  2. Khi thực hiện phiên hội thoại mới 5 lượt (10 tin nhắn), thanh bên `ChatSidebar` hiển thị `11 tin nhắn` (do tính luôn thẻ chào mừng `welcome-*` ở đầu mảng `messages`), và khi nhấn vào xem lại phiên cũ (`12:08`), hàm `saveSession(target)` ghi đè `updatedAt = new Date().toISOString()` làm mốc thời gian của phiên cũ bị biến đổi thành giờ hiện tại.
- **Nguyên nhân gốc rễ:**
  1. `SingleMetricSliderCard.tsx` dùng biểu thức `const effectiveShiftNotice = localShiftNotice ?? card.temporal_shift_notice ?? null;`. Vì toán tử `??` trong JavaScript/TypeScript rơi về vế phải khi vế trái là `null` hoặc `undefined`, lệnh `setLocalShiftNotice(null)` khi bấm nút chọn kỳ báo cáo hoàn toàn vô tác dụng (vẫn trả về `card.temporal_shift_notice`).
  2. `persistSession` trong `ChatContainer.tsx` và `safeWriteSessions`/`mergeSessions` trong `storage.ts` chưa lọc bỏ phần tử `welcome-*` và phần tử chờ stream rỗng (`isStreaming && !content`), đồng thời `saveSession` luôn ép `updatedAt = new Date().toISOString()` ngay cả khi chỉ khôi phục lịch sử.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không dùng `localState ?? propValue` khi `null` là giá trị hợp lệ dùng để xóa trạng thái; Không lưu thẻ chào mừng `welcome-*` vào mảng `session.messages`; Không ghi đè `updatedAt` khi chỉ đọc/khôi phục phiên hội thoại cũ.
  * ✅ **ALWAYS:**
    1. Khởi tạo `localShiftNotice` trực tiếp từ `card.temporal_shift_notice ?? null` và gán `effectiveShiftNotice = localShiftNotice`, đồng thời cập nhật câu dẫn ngày trong `MessageItem.tsx` khi chuyển kỳ.
    2. Lọc bỏ `welcome-*` và `isStreaming && !content` qua `isPersistableMessage` trong `storage.ts` và `persistSession`, đồng thời truyền `{ preserveTimestamp: true }` vào `saveSession` khi khôi phục phiên từ SQLite.

---

### [TRAP-099] Bẫy Render Không Tự Deploy Khi `git push` Và Bẫy `self.graph.stream()` Đồng Bộ Chặn Event Loop Làm Chết Health Check 5s (`502 Bad Gateway`) Trên Render
- **Môi trường & Công nghệ:** Render Cloud (`ipgov-chatbot-backend` / `ipgov-chatbot-frontend`) / FastAPI Asyncio Event Loop / LangGraph `self.graph.stream()`
- **Triệu chứng:**
  1. Sau khi `git commit` và `git push` bản sửa lỗi `timeline_values` (`cd7d6cd`, `66e9fb5`) lên nhánh `main` của GitHub, kiểm thử trực tiếp trên Render (`https://ipgov-chatbot-frontend.onrender.com`) vẫn không thấy số liệu nhảy khi bấm các nút Ticket thời gian (`Quý 1`, `Quý 2`, `Quý 3`).
  2. Khi thực hiện hội thoại đa lượt liên tiếp trên Render, đến lượt thứ 2–3 thì máy chủ Backend bất ngờ trả về `502 Bad Gateway` và toàn bộ lịch sử phiên vừa tạo trong SQLite bị mất.
- **Nguyên nhân gốc rễ:**
  1. **Render Auto-Deploy Webhook Bị Bỏ Qua:** Mặc dù cấu hình dịch vụ trên Render để `autoDeploy: "yes"`, các lần `git push` lên GitHub không kích hoạt webhook tự động trên Render (toàn bộ lịch sử deploy trên Render đều có `"trigger": "api"` hoặc `"manual"`, không có `"new_commit"`). Do đó cả Backend lẫn Frontend trên Render vẫn chạy commit cũ trước khi sửa lỗi.
  2. **Blocking Event Loop Làm Timeout Health Check 5s Của Render:** Trong `warehouse_langgraph_agent.py` (`run_stream`) và `main.py` (`_run_startup_warmup`), vòng lặp `for event in self.graph.stream(...)` và `DuckDBSemanticCatalog()` chạy đồng bộ trực tiếp trên luồng `asyncio` chính của FastAPI. Vì các node gọi OpenRouter, HuggingFace Embedding Space và PostgreSQL qua I/O đồng bộ (`urllib.request`, `psycopg2`), luồng chính bị khóa 12–17 giây. Load balancer của Render gửi `GET /api/v1/health` mỗi 5 giây với ngưỡng timeout 5 giây; khi bị chặn quá 15 giây, Render đánh dấu `server_failed: HTTP health check failed (timed out after 5 seconds)`, gửi `SIGTERM` (`Shutting down`) khởi động lại container, gây lỗi `502 Bad Gateway` và xóa trắng SQLite trên đĩa tạm của container.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không giả định `git push` đã tự động cập nhật dịch vụ trên Render mà không kiểm tra `commit.id` đang `live` qua Render API; Không chạy generator đồng bộ `self.graph.stream()` hoặc khởi tạo `DuckDBSemanticCatalog()` trực tiếp trên luồng `asyncio` chính của FastAPI.
  * ✅ **ALWAYS:**
    1. Sau mỗi lần `git push`, chủ động gọi Render REST API (`POST /v1/services/{serviceId}/deploys`) cho cả Backend và Frontend và xác nhận trạng thái `status == "live"` đúng mã commit `HEAD`.
    2. Trong `warehouse_langgraph_agent.py` (`run_stream`), chạy `self.graph.stream()` trên worker thread qua `loop.run_in_executor` + `asyncio.Queue` (`loop.call_soon_threadsafe`) và bọc `_run_startup_warmup` trong `asyncio.to_thread` để luồng `asyncio` chính luôn phản hồi `GET /api/v1/health` trong `< 1ms`.

---

### [TRAP-100] Bẫy Đóng Băng Số Liệu Trong Pop-up Cây Phân Cấp (`InteractiveCriteriaTreeModal`) Khi Chuyển Kỳ Báo Cáo Và Bẫy Trùng Tên Chỉ Tiêu Lá (`Chăn nuôi`) Khi Hydrate `tabular_data.rows[0]`
- **Môi trường & Công nghệ:** `duckdb_semantic_catalog.py` (`build_criteria_tree_for_rows`) / `warehouse_langgraph_agent.py` / `chat_history_store.py` (`_hydrate_legacy_timeline_values`) / `SmartTable.tsx` (`InteractiveCriteriaTreeModal`)
- **Triệu chứng:**
  1. Ở câu hỏi `REQ-Q01`/`REQ-Q04` (*"Các chỉ tiêu Cấp 1 của nhiệm vụ Phát triển nông thôn năm 2026?"*), dù `SmartTable.tsx` đã có hàm `applyPeriodToNode` đọc `node.timeline_values || node.period_values`, khi người dùng bấm chọn `[Quý 1]` hoặc `[Quý 2]` rồi mở `🌳 - Xem chi tiết các chỉ tiêu con` (`InteractiveCriteriaTreeModal`), toàn bộ số liệu Cấp 1, Cấp 2, Cấp 3 bên trong modal vẫn đóng băng ở giá trị cả năm (`Lũy kế = 138`, `Thành lập mới = 3`, `Hiệu quả hoạt động = 130`, `Tốt/Trung bình/Kém/Chưa đủ ĐK = 56/55/16/3`) và trong modal cũng thiếu thanh chọn nhanh kỳ báo cáo.
  2. Ở câu hỏi `REQ-Q02` (*"cho tôi biết số liệu chăn nuôi của liên hiệp hợp tác xã ngày 30/4"*), `tabular_data.rows[0]` sau khi lưu vào SQLite và qua `_hydrate_legacy_timeline_values` bị gán nhầm `timeline_values = {"q1": "25", "q2": "25", "q3": "25", "year": "25"}` (số liệu của `HTX nông nghiệp > Chăn nuôi`) thay vì `{"q1": "1", "q2": "1", "q3": "0", "year": "0"}` (số liệu đúng của `Liên hiệp HTX > Chăn nuôi`, `criteria_id = 33714acb-cef0-447d-9a3b-d515da06889e`).
- **Nguyên nhân gốc rễ:**
  1. Hàm `build_criteria_tree_for_rows` trong `duckdb_semantic_catalog.py` dựng cây `nodes_by_id` từ bảng DuckDB `catalog_criteria_hierarchy` nhưng chưa gọi `self.get_batch_period_values(...)` để gắn `timeline_values` và `period_values` vào từng nút Cấp 1/2/3 của `tree_by_root_id` và `level1_summary_rows`. Do đó `node.timeline_values` luôn là `undefined` ở phía `SmartTable.tsx`.
  2. Trong `warehouse_langgraph_agent.py`, khi tạo `tabular_data.rows[0]` cho câu trả lời chỉ tiêu đơn (`single_metric_card`), dict dòng chỉ chứa `{"stt": 1, "item": ..., "value": ..., "unit": ...}` mà thiếu `criteria_id` và `timeline_values`. Khi `ChatHistoryStore._hydrate_legacy_timeline_values` chạy, nó tra cứu `period_map` thuần theo tên `item = "chăn nuôi"`, dẫn đến va chạm homonym với chỉ tiêu lá cùng tên thuộc nhóm cha khác.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không dựng cây `tree_modal` (`build_criteria_tree_for_rows`) mà bỏ trống `timeline_values` trên các nút con; Không tạo dòng `tabular_data.rows[0]` cho `single_metric_card` mà thiếu `criteria_id` và `timeline_values`.
  * ✅ **ALWAYS:**
    1. Trong `build_criteria_tree_for_rows` (`duckdb_semantic_catalog.py`), gọi `self.get_batch_period_values(list(nodes_by_id.values()), ...)` để đính kèm `timeline_values` và `period_values` cho toàn bộ nút Cấp 1/2/3 và `level1_summary_rows`, đồng thời hiển thị thanh chọn kỳ báo cáo 0ms ngay trong `InteractiveCriteriaTreeModal`.
    2. Trong `warehouse_langgraph_agent.py` và `ChatHistoryStore._hydrate_legacy_timeline_values`, luôn gắn `criteria_id` (lấy từ `single_metric_card.criteria_id` nếu `len(t_rows) == 1`) và `timeline_values` trích xuất từ `timeline_snaps` cho `tabular_data.rows[0]`, cũng như đệ quy hydrate `tree_modal` cho các phiên lịch sử cũ.

---

### [TRAP-101] Bẫy Biến Dạng Truy Vấn Độc Lập Đa Lượt Trong CQR (`state["user_query"] = cqr_res.rewritten_query`) Và Bẫy Cổng Từ Khóa Tĩnh `BREAKDOWN_TRIGGER` Khi Người Dùng Paraphrase Tên Chỉ Tiêu
- **Môi trường & Công nghệ:** `warehouse_langgraph_agent.py` (`node_parse_context`) / `discourse_state_tracker.py` (`classify_turn_transition`) / `neural_cqr_engine.py` / `duckdb_semantic_catalog.py` (`_resolve_paraphrased_criterion_from_kb`)
- **Triệu chứng:**
  1. Khi hỏi đơn lẻ `"cho tôi biết số lượng lĩnh vực của hợp tác xã nông nghiệp"`, hệ thống trả về đúng bảng 8 lĩnh vực của HTX. Nhưng nếu hỏi ngay sau câu `"cho tôi biết số lĩnh vực của HTX nông nghiệp"`, câu thứ hai lại bị biến dạng sang truy vấn liệt kê chỉ tiêu Cấp 1 toàn kho.
  2. Khi người dùng paraphrase tên chỉ tiêu theo ngữ nghĩa định nghĩa (ví dụ: `"Số lượng hợp tác xã nông nghiệp mới được cấp phép trong quý 1"` cho `'Thành lập mới'`, hoặc `"Tình hình liên kết sản xuất của hợp tác xã nông nghiệp ở quý 2"` cho `'Liên kết sản xuất'`), các cổng từ khóa tĩnh (`ALLOWED_SEMANTIC_LEXICON_SEED` / `BREAKDOWN_TRIGGER`) trượt khớp và rơi về danh sách Cấp 1 mặc định.
- **Nguyên nhân gốc rễ:**
  1. Trong `discourse_state_tracker.py`, câu thứ hai có độ tương đồng Jaccard cao với lượt 1 nên không nhảy vào `TOPIC_SHIFT`, rơi xuống nhánh nối ghép lịch sử (`SLOT_UPDATE`) dù bản thân câu thứ hai đã đầy đủ chủ ngữ/vị ngữ và không chứa đại từ quy chiếu. Nghiêm trọng hơn, `warehouse_langgraph_agent.py` ghi đè trực tiếp `state["user_query"] = cqr_res.rewritten_query` trước khi chạy `resolve_hierarchy_breakdown`.
  2. Hệ thống cũ dựa vào danh sách từ khóa tĩnh thay vì đối chiếu độ phủ IDF và ngữ cảnh phân cấp trên Kho Tri thức Định nghĩa Chỉ tiêu (`criterion_definitions_kb.json` / `catalog_definitions`).
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Tuyệt đối không dùng danh sách từ khóa tĩnh (`ALLOWED_SEMANTIC_LEXICON_SEED`, `BREAKDOWN_TRIGGER`, `seed_aliases`) để chặn cổng phân loại phân cấp; Không cho phép CQR nối ghép ngữ cảnh cũ vào câu hỏi đã tự chủ ngữ nghĩa (self-contained query without anaphora); Không ghi đè chuỗi gốc `raw_user_query` khi truyền vào `resolve_hierarchy_breakdown`.
  * ✅ **ALWAYS:**
    1. Kiểm tra tính tự chủ ngữ nghĩa (`is_self_contained and not has_anaphora`) trong `DiscourseStateTracker` và `NeuralCQREngine` để giữ nguyên câu hỏi độc lập (`rewritten_query = current_query`, `confidence = 0.0`).
    2. Bảo toàn `raw_user_query` trong `node_parse_context` và phân giải paraphrase thông qua bộ chấm điểm IDF động kết hợp khử nhiễu thực thể gốc (`parent_core_toks`) trên bảng DuckDB `catalog_definitions` (`155/155` định nghĩa chuẩn hóa).

---

### [TRAP-102] Bẫy Va Chạm Chuỗi Con `"cơ sở"` vs `"sở "` Trong `resolve_administrative_scope` Và Bẫy Mất Chữ Số Đơn (`3 sao`, `4 sao`, `5 sao`) Khi Lọc Token `len(w) >= 2`
- **Môi trường & Công nghệ:** `duckdb_semantic_catalog.py` (`resolve_administrative_scope`, `_resolve_paraphrased_criterion_from_kb`, `classify_criterion_hierarchy`)
- **Triệu chứng:**
  1. Khi câu hỏi chứa cụm từ `"Khảo sát số cơ sở đang duy trì hoạt động qua các định chế kinh tế vào quý 2"` (`Q26`), hàm `resolve_administrative_scope` gán nhầm `department_code = '68-1-06'`, khiến truy vấn liên nhánh `'Đang hoạt động'` trả về 0 bản ghi.
  2. Khi câu hỏi hỏi nhóm cha `"Phân hạng cấp độ sao của các sản phẩm OCOP được thẩm định trong năm 2026"` (`Q20`, không nêu số sao cụ thể), nếu bộ tách từ dùng điều kiện `len(w) >= 2`, các chữ số đơn `"3"`, `"4"`, `"5"` trong tên chỉ tiêu lá `'Sản phẩm OCOP 3 sao'` bị loại bỏ, làm biến mất token phân biệt giữa chỉ tiêu lá và nhóm cha `'Tổng số lượng sản phẩm OCOP trong năm'`.
- **Nguyên nhân gốc rễ:**
  1. Trong `resolve_administrative_scope`, biểu thức `has_dept_indicator` kiểm tra `"sở " in t_clean`. Từ ghép `"cơ sở "` kết thúc bằng `"sở "` nên kích hoạt nhầm cờ tìm kiếm Sở/Ngành cấp tỉnh.
  2. Bộ lọc độ dài token `len(w) >= 2` vô tình xóa các chữ số đơn (`"1"`..`"9"`) đóng vai trò định danh cấp/bậc/hạng sao của chỉ tiêu lá.
- **Quy tắc dứt điểm:**
  * ❌ **NEVER:** Không kiểm tra chuỗi con `"sở "` trước khi loại bỏ từ ghép `"cơ sở"` (`\b(cơ\s+sở|co\s+so)\b`); Không lọc bỏ chữ số đơn bằng `len(w) >= 2` đơn thuần trong bộ phân giải ngữ nghĩa chỉ tiêu.
  * ✅ **ALWAYS:**
    1. Trong `resolve_administrative_scope`, luôn xóa `\b(cơ\s+sở|co\s+so)\b` khỏi chuỗi kiểm tra `t_dept_check` trước khi xét `has_dept_indicator`.
    2. Trong `_resolve_paraphrased_criterion_from_kb`, luôn giữ lại chữ số bằng điều kiện `len(w) >= 2 or w.isdigit()` để bảo toàn token phân biệt cấp độ/hạng sao (`3`, `4`, `5`) giữa chỉ tiêu lá và nhóm chỉ tiêu cha.


