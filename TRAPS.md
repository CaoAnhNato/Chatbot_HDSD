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
