# 🐛 BÁO CÁO CÁC CA LỖI (BUG CASES) PHÁT SINH TRONG QUÁ TRÌNH KIỂM THỬ & VẬN HÀNH CHATBOT

> **Đơn vị quản trị:** Dự án Chatbot Tra Cứu Kho Dữ Liệu Điều Hành Chính Quyền Tỉnh (`IPGov_Chatbot`)  
> **Phiên bản tài liệu:** v1.0.0 (Cập nhật sau đợt chuyển đổi Warehouse Công ty `104.248.155.6`)  
> **Tài liệu đối chiếu:** [FAILED_TEST_CASES_LOG.md](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/docs/FAILED_TEST_CASES_LOG.md), [TRAPS.md](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/TRAPS.md)

---

## 1. Tổng Quan Về Các Nhóm Lỗi (Bug Classification Overview)

Tài liệu này ghi nhận và phân loại toàn diện các lỗi (bugs, defects, runtime failures, semantic errors) phát sinh trong suốt vòng đời kiểm thử tự động, thử nghiệm nội bộ và kiểm toán cơ sở dữ liệu của Chatbot. Toàn bộ các lỗi được quy chuẩn theo 5 mức độ nghiêm trọng:

| Mã Bug | Tên Ca Lỗi | Module Bị Ảnh Hưởng | Mức Độ | Trạng Thái Hiện Tại |
| :--- | :--- | :---: | :---: | :---: |
| **BUG-001** | Lỗi hiển thị Top-K ngây thơ & Sai lệch thứ tự giá trị | MOD-08 (Synthesizer) | 🔴 Cao | ✅ Đã khắc phục (Chuyển sang COMPONENT_LIST khi không có ý định ranking) |
| **BUG-002** | Bẫy cắt đuôi từ khóa phái sinh (`name_parts[-2:]`) quét lan man | MOD-05 (Track A Compiler) | 🔴 Cao | ✅ Đã khắc phục (Loại bỏ cắt đuôi thô, áp dụng Dynamic SQL Agent) |
| **BUG-003** | Lỗi vỡ truy vấn do Schema Drift (`year` $\to$ `year_code`) | MOD-04, MOD-05, MOD-06 | 🔴 Cao | ✅ Đã khắc phục trên Remote DWH |
| **BUG-004** | Bẫy tập rỗng do phép `JOIN` bảng `deparment` (0 dòng) | MOD-05, MOD-04 | 🔴 Cao | ✅ Đã khắc phục (Chính sách Zero-JOIN) |
| **BUG-005** | Lỗi gọi cột ảo `row_count` trên bảng `pipeline_logs` (`[TRAP-012]`) | MOD-05, MOD-08 | 🟡 Trung bình | ✅ Đã khắc phục |
| **BUG-006** | Lỗi chia cho 0 và hiệu ứng cơ số nhỏ (Small Base Effect) khi tính % tăng trưởng | MOD-08 (Jinja Engine) | 🟡 Trung bình | ✅ Đã khắc phục (`safe_percentage`) |
| **BUG-007** | Bẫy ghi đè cache Catalog khi DB rỗng (`[TRAP-008]`) | MOD-04 (DuckDB Catalog) | 🟡 Trung bình | ✅ Đã khắc phục |
| **BUG-008** | Lỗi khoảng trống dữ liệu khi hỏi ngoài Nông nghiệp 2026 trên DWH mới | MOD-03 (Router) | 🟡 Trung bình | ✅ Đã khắc phục (Kích hoạt Data Availability Guard & Active Clarification) |
| **BUG-009** | Lỗi hỏi năng lực chatbot ("bạn giúp được gì") tự động dump dữ liệu Fact 342 dòng | MOD-03 (Agent Router) | 🔴 Cao | ✅ Đã khắc phục (Định tuyến trực tiếp sang bộ tổng hợp năng lực DWH kèm Quick Action Chips) |
| **BUG-010** | Khối câu lệnh SQL thu gọn (`<details>`) bị hiển thị thô trên giao diện người dùng | Frontend (MessageItem) | 🟡 Trung bình | ✅ Đã khắc phục (Đồng bộ CollapsibleSqlBlock trên cả 2 cây frontend, regex chuẩn hóa) |
| **BUG-011** | Lỗi thực thi truy vấn diêm nghiệp (`dict is not a sequence`) do bẫy tham số rỗng với `%` | MOD-07 (Connection Pool) | 🔴 Cao | ✅ Đã khắc phục (`[TRAP-031]`: Phân nhánh `if parameters:` trước khi gọi `cur.execute()`) |
| **BUG-012** | Lỗi lặp lại câu hỏi khi DWH rỗng & Rơi mất nút gợi ý (Quick Action Chips) trên Frontend | MOD-03 (Agent Router) & Frontend (api.ts / ChatContainer) | 🔴 Cao | ✅ Đã khắc phục (Chuẩn hóa prefix thông báo, ánh xạ '68-1-01', chuyển tiếp đầy đủ quick_action_chips qua SSE Stream) |

---

## 2. Chi Tiết Các Ca Lỗi Điển Hình

### BUG-001: Lỗi Hiển Thị Top-K Ngây Thơ & Sai Lệch Thứ Tự Giá Trị
* **Ngữ cảnh phát hiện:** Người dùng hỏi câu đơn giản: `"[tenant_code=68, level=0] số tai nạn lao động 2026"`.
* **Hiện tượng lỗi (Bug Symptom):**
  - Hệ thống trả về câu tiêu đề: *"Top 31 đơn vị có tai nạn lao động cao nhất năm 2026, dẫn đầu là Hợp đồng lao động không xác định thời hạn (56):"*.
  - Bảng số liệu:
    * Hạng 1: *Hợp đồng lao động không xác định thời hạn* | Giá trị: 56
    * Hạng 2: *Hợp đồng lao động xác định thời hạn* | Giá trị: 62
* **Nguyên nhân gốc rễ (Root Cause):**
  1. Tại [`jinja_slot_engine.py`](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/modules/mod08_response/jinja_slot_engine.py#L445), hệ thống có điều kiện phân nhánh: `if 2 <= len(rows) <= 50:` thì tự động trả về template `RANKING_TOP_K` mà không kiểm tra xem câu hỏi có mang ý định xếp hạng (`RANKING`) hay không.
  2. Template `RANKING_TOP_K` hardcode chữ *"đơn vị"*, trong khi cột trả về từ SQL là `ten_chi_tieu` (Tên chỉ tiêu) chứ không phải tên sở ngành/phòng ban.
  3. Câu SQL do Compiler sinh ra chỉ sắp xếp `ORDER BY f.year ASC` chứ không hề sắp xếp giảm dần theo giá trị (`ORDER BY value DESC`), dẫn đến việc dòng có giá trị 56 đứng trước dòng có giá trị 62 nhưng vẫn bị gán nhãn là "Hạng 1 dẫn đầu".
* **Giải pháp khắc phục:**
  - Cưỡng chế điều kiện chọn template: Chỉ chọn `RANKING_TOP_K` khi `router_output.dag_archetype == 'RANKING_TOP_K'`.
  - Nếu kết quả nhiều dòng là các chỉ tiêu thành phần, sử dụng mẫu phân rã `BREAKDOWN_LIST` với tiêu đề bảng `STT | Tên chỉ tiêu | Giá trị`.

---

### BUG-002: Bẫy Cắt Đuôi Từ Khóa Phái Sinh (`name_parts[-2:]`) Quét Lan Man
* **Ngữ cảnh phát hiện:** Khi biên dịch câu hỏi tra cứu chỉ số đơn lẻ tại Track A Compiler.
* **Hiện tượng lỗi (Bug Symptom):** Câu hỏi chỉ hỏi một chỉ tiêu cụ thể ("tai nạn lao động"), nhưng câu SQL sinh ra lại trả về danh sách 31 chỉ tiêu hoàn toàn không liên quan (như *"Lao động thất nghiệp"*, *"Lao động là người cao tuổi"*, *"Hợp đồng lao động..."*).
* **Nguyên nhân gốc rễ (Root Cause):**
  - Tại [`track_a_compiler.py`](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/modules/mod05_sql_compiler/track_a_compiler.py#L238-L243), code tự động lấy 2 từ cuối của tên chỉ tiêu:
    ```python
    name_parts = clean_name.split()
    if len(name_parts) >= 2:
        core_phrase = " ".join(name_parts[-2:])  # -> "lao động"
        crit_conds.append(f"lc.name ILIKE '%{core_phrase}%'")
        crit_conds.append(f"f.name ILIKE '%{core_phrase}%'")
    ```
  - Khi `clean_name` là "Số vụ tai nạn lao động", `name_parts[-2:]` trở thành `"lao động"`.
  - Mệnh đề SQL bị gắn thêm `OR f.name ILIKE '%lao động%'`, quét trúng tất cả 31 chỉ tiêu có chữ "lao động" trong kho dữ liệu.
* **Giải pháp khắc phục:**
  - Xóa bỏ hoàn toàn cơ chế cắt 2 từ cuối thô sơ.
  - Sử dụng tra cứu chính xác theo `criteria.code` kết hợp tìm kiếm ngữ nghĩa toàn bộ cụm từ qua DuckDB Catalog.

---

### BUG-003: Lỗi Vỡ Truy Vấn Do Schema Drift (`year` $\to$ `year_code`)
* **Ngữ cảnh phát hiện:** Khi kết nối hệ thống Chatbot với máy chủ Warehouse công ty (`104.248.155.6:5432/vna_wom_dev`).
* **Hiện tượng lỗi (Bug Symptom):** PostgreSQL báo lỗi `psycopg2.errors.UndefinedColumn: column f.year does not exist` khi thực thi câu truy vấn.
* **Nguyên nhân gốc rễ (Root Cause):**
  - CSDL trên máy chủ công ty đã được chuẩn hóa lại tên cột thời gian: Cột lưu trữ năm trên các bảng `fact_report_criteria`, `report`, `mission`, `scope` được đặt tên là `year_code` thay vì `year`.
  - Mã nguồn Compiler và AST Enforcer cũ vẫn hardcode `f.year = '2026'`.
* **Giải pháp khắc phục:**
  - Đồng bộ toàn diện `year` $\to$ `year_code` trong `track_a_compiler.py`, `archetype_patterns.py`, `prompt_templates.py`, `ast_hbac_guard.py` và `catalog_seed_metadata.json`.

---

### BUG-004: Bẫy Tập Rỗng Do Phép `JOIN` Bảng `deparment` (0 Dòng)
* **Ngữ cảnh phát hiện:** Các câu lệnh Text-to-SQL thực hiện `JOIN dwh_internal.deparment d ON f.department_code = d.code`.
* **Hiện tượng lỗi (Bug Symptom):** Câu truy vấn SQL cú pháp hoàn toàn hợp lệ, trong bảng Fact có dữ liệu, nhưng kết quả trả về luôn là `0 rows` (Empty-Set Mirage).
* **Nguyên nhân gốc rễ (Root Cause):**
  - Sau đợt reset dữ liệu trên máy chủ công ty, bảng Dimension `deparment` hiện có đúng **0 dòng**.
  - Bất kỳ phép `INNER JOIN` nào tới bảng `deparment` đều biến tập kết quả thành rỗng.
* **Giải pháp khắc phục:**
  - Áp dụng nguyên tắc **Zero-JOIN deparment**: Tận dụng cột Degenerate Dimension `department_code` có sẵn trong bảng Fact (`fact_report_criteria.department_code`).
  - Phân giải tên đơn vị sang mã qua DuckDB In-Memory Catalog Seed thay vì JOIN trực tiếp trong PostgreSQL.

---

### BUG-005: Lỗi Truy Vấn Cột Ảo `row_count` Trên Bảng `pipeline_logs` (`[TRAP-012]`)
* **Ngữ cảnh phát hiện:** Khi người dùng hỏi về tính tươi mới của kho dữ liệu (ETL Freshness): *"Kho dữ liệu được đồng bộ khi nào?"*.
* **Hiện tượng lỗi (Bug Symptom):** Bị văng lỗi cột không tồn tại khi SQL cố gắng `SELECT row_count FROM dwh_internal.pipeline_logs`.
* **Nguyên nhân gốc rễ (Root Cause):** Bảng `pipeline_logs` thực tế chỉ có 3 cột: `model_name`, `last_run_at`, `status`.
* **Giải pháp khắc phục:** Cập nhật mẫu SQL của archetype `ETL_FRESHNESS` chỉ truy vấn `MAX(last_run_at)` và `status`.

---

### BUG-006: Lỗi Chia Cho 0 & Hiệu Ứng Cơ Số Nhỏ (Small Base Effect) Khi So Sánh %
* **Ngữ cảnh phát hiện:** Khi người dùng so sánh biến động số liệu giữa 2 năm (Temporal YoY Comparison).
* **Hiện tượng lỗi (Bug Symptom):**
  - Văng lỗi `ZeroDivisionError` khi năm trước ghi nhận giá trị bằng 0.
  - Báo tăng trưởng đột biến (ví dụ tăng 300% từ 1 lên 4) gây sai lệch nhận định quản trị.
* **Nguyên nhân gốc rễ (Root Cause):** Thiếu cơ chế kiểm soát biên toán học trước khi tính phần trăm biến động.
* **Giải pháp khắc phục:** Xây dựng hàm `safe_percentage(val_2, val_1)` trả về ghi chú cảnh báo khi cơ số nhỏ ($0 < val_1 < 5$) và chỉ tính chênh lệch tuyệt đối khi $val_1 = 0$.

---

### BUG-007: Bẫy Ghi Đè Cache Catalog Khi DB Rỗng (`[TRAP-008]`)
* **Ngữ cảnh phát hiện:** Khi khởi động hệ thống và nạp dữ liệu từ Live DB vào DuckDB In-Memory Catalog.
* **Hiện tượng lỗi (Bug Symptom):** Khi một bảng trên DB bị rỗng (như `deparment`), tiến trình hydrate tự động `TRUNCATE` và nạp 0 dòng, xóa sạch dữ liệu seed đang có trong RAM.
* **Nguyên nhân gốc rễ (Root Cause):** Thiếu chốt chặn kiểm tra số lượng bản ghi trả về trước khi ghi đè cache RAM.
* **Giải pháp khắc phục:** Bổ sung điều kiện phòng vệ: Chỉ ghi đè khi số dòng fetch được từ DB > 0. Nếu DB trả về 0 dòng, giữ nguyên bộ seed metadata ban đầu.

---

### BUG-008: Lỗi Khoảng Trống Dữ Liệu Khi Hỏi Ngoài Nông Nghiệp 2026 Trên DWH Mới
* **Ngữ cảnh phát hiện:** Người dùng hỏi các chỉ tiêu về an toàn lao động, giao thông, y tế trên DWH công ty mới.
* **Hiện tượng lỗi (Bug Symptom):** DWH công ty hiện tại chỉ có 463 dòng Fact thuộc năm 2026 của Sở Nông nghiệp & PTNT. Các câu hỏi ngoài phạm vi này sinh ra SQL hợp lệ nhưng trả về 0 dòng, gây hiểu lầm là hệ thống bị hỏng.
* **Giải pháp khắc phục:** Kích hoạt **Data Availability Guard** ở tầng Router: Phát hiện câu hỏi ngoài phạm vi Nông nghiệp 2026 và đưa ra phản hồi lịch sự kèm gợi ý các chỉ tiêu OCOP, HTX, sản xuất muối đang sẵn sàng.

---

### BUG-009: Lỗi Hỏi Năng Lực Chatbot Trả Về Dữ Liệu Fact Không Liên Quan
* **Ngữ cảnh phát hiện:** Người dùng hỏi các câu hỏi chung về khả năng của hệ thống như *"bạn giúp được gì cho tôi"*, *"khả năng của chatbot"*, *"bạn là ai"*.
* **Hiện tượng lỗi (Bug Symptom):** Hệ thống không trả lời giới thiệu bản thân mà tự động sinh câu truy vấn `SELECT ... FROM dwh_internal.fact_report_criteria` quét 342 dòng dữ liệu nông nghiệp và trả về toàn bộ danh mục chỉ tiêu không liên quan.
* **Nguyên nhân gốc rễ (Root Cause):**
  - Trong `warehouse_langgraph_agent.py`, tầng phân tích ngữ cảnh (`node_parse_context`) chưa phân biệt được câu hỏi giới thiệu năng lực (Capability / Greeting Query) với câu hỏi tra cứu dữ liệu (Data Query).
  - Kết quả là câu hỏi bị đưa vào luồng `generate_sql` mặc định, tự động gán tenant/năm mặc định và truy vấn bảng Fact.
* **Giải pháp khắc phục:**
  - Bổ sung cờ `is_capability_query` và bộ nhận diện từ khóa năng lực (`"giúp được gì"`, `"làm được gì"`, `"khả năng"`, `"chức năng"`, `"bạn là ai"`).
  - Khi phát hiện `is_capability_query = True`, luồng LangGraph định tuyến rẽ nhánh trực tiếp sang `synthesize_response` (`route_after_parse`), trả về lời giới thiệu chuẩn mực về kho dữ liệu DWH kèm danh sách các Quick Action Chips gợi ý câu hỏi mẫu, hoàn toàn không sinh SQL hay truy vấn bảng Fact.

---

### BUG-010: Khối Câu Lệnh SQL Thu Gọn Hiển Thị Dạng Text Thô Trên Giao Diện Người Dùng
* **Ngữ cảnh phát hiện:** Khi người dùng gửi câu hỏi trên giao diện web (`npm run dev`), phản hồi chứa thẻ HTML `<details><summary>🔍 Xem câu lệnh truy vấn...</summary>...</details>` bị hiển thị lộ toàn bộ dưới dạng chuỗi văn bản thô chưa parse.
* **Hiện tượng lỗi (Bug Symptom):** Người dùng chưa nhấn vào xem mà câu lệnh SQL đã tự động lộ ra, hoặc thẻ `<details>` bị render thành plain text xấu xí, không có nút mũi tên gập/mở hay nút sao chép (Copy).
* **Nguyên nhân gốc rễ (Root Cause):**
  - Dự án tồn tại 2 cây thư mục frontend độc lập: `frontend/` và `IPGov_Chatbot/frontend/` (`[TRAP-032]`).
  - Lập trình viên cập nhật `CollapsibleSqlBlock` tại `frontend/src/components/chat/MessageItem.tsx`, nhưng người dùng khởi chạy giao diện từ thư mục `IPGov_Chatbot/frontend/`.
  - File `IPGov_Chatbot/frontend/src/components/chat/MessageItem.tsx` cũ chưa có logic tách regex `<details>` và component `CollapsibleSqlBlock`.
* **Giải pháp khắc phục:**
  - Đồng bộ toàn diện mã nguồn `MessageItem.tsx`, `MessageList.tsx`, `ChatContainer.tsx` sang cả hai cây frontend (`frontend/` và `IPGov_Chatbot/frontend/`).
  - Nâng cấp biểu thức chính quy Regex tách khối linh hoạt: `/<details[^>]*>[\s\r\n]*<summary[^>]*>([\s\S]*?)<\/summary>([\s\S]*?)<\/details>/gi` để hỗ trợ bắt chuẩn xác các biến thể xuống dòng của markdown.

---

### BUG-011: Lỗi Thực Thi Truy Vấn Diêm Nghiệp (`dict is not a sequence`)
* **Ngữ cảnh phát hiện:** Người dùng hỏi: *"tống các hộ sản xuất muối hiện tại là bao nhiêu ?"*.
* **Hiện tượng lỗi (Bug Symptom):** Chatbot báo lỗi: `Lỗi thực thi PostgreSQL: dict is not a sequence` và không trả về số liệu.
* **Nguyên nhân gốc rễ (Root Cause):**
  - Tại [`connection_pool.py`](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/modules/mod07_dwh_exec/connection_pool.py#L134), code gọi `cur.execute(sql, parameters or {})`.
  - Mặc dù `parameters` là `{}` (dict rỗng), thư viện `psycopg2` (C-extension) khi nhận đối số thứ 2 là `dict` sẽ kích hoạt bộ phân giải tham số `%s`/`%(name)s`.
  - Khi câu lệnh SQL chứa các ký tự wildcard như `ILIKE '%muối%'`, `psycopg2` hiểu nhầm `%m` là một specifier định dạng tham số nhưng không tìm thấy key `m` trong dict, dẫn đến văng lỗi nội bộ `TypeError: dict is not a sequence` (`[TRAP-031]`).
* **Giải pháp khắc phục:**
  - Phân nhánh rõ ràng trước khi gọi execute:
    ```python
    if parameters:
        cur.execute(sql, parameters)
    else:
        cur.execute(sql)
    ```
  - Khi `parameters` rỗng hoặc `None`, chỉ gọi `cur.execute(sql)` thuần túy, loại bỏ triệt để xung đột giữa `psycopg2` và ký tự `%` của SQL `ILIKE`.

---

### BUG-012: Lỗi Lặp Lại Câu Hỏi Khi DWH Rỗng & Rơi Mất Nút Gợi Ý (Quick Action Chips) Trên Giao Diện Frontend
* **Ngữ cảnh phát hiện:** Người dùng test câu hỏi trên giao diện Web UI: `"[tenant_code=68, level=0] Trạng thái các đợt nộp báo cáo của Sở Nông nghiệp hiện nay thế nào?"`.
* **Hiện tượng lỗi (Bug Symptom):**
  1. Chatbot lặp lại nguyên văn câu hỏi người dùng thành tên chỉ tiêu:  
     *"Chỉ tiêu **Trạng thái các đợt nộp báo cáo của Sở Nông nghiệp hiện nay thế nào?** hiện chưa có bản ghi số liệu được phê duyệt trong kho DWH năm 2026."*
  2. Bị rơi mất toàn bộ nút bấm gợi ý (Quick Action Chips) bên dưới, mặc dù câu trả lời có ghi *"Đồng chí có thể chọn một trong các câu hỏi gợi ý bên dưới"*.
  3. Truy vấn trả về 0 dòng (tập rỗng) do LLM tự suy đoán mã phòng ban thành `'NN'` trong câu lệnh SQL `WHERE r.department_code = 'NN'`.
* **Nguyên nhân gốc rễ (Root Cause):**
  1. *Lỗi lặp câu hỏi:* Tại [`warehouse_langgraph_agent.py`](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/modules/mod03_router/warehouse_langgraph_agent.py), khi `rows` rỗng và `selected_cand` là `None`, biến `target_metric_label` bị gán fallback bằng `clean_prompt` (toàn bộ câu hỏi người dùng) và đưa vào chuỗi `f"Chỉ tiêu **{target_metric_label}** hiện chưa có bản ghi số liệu..."`.
  2. *Lỗi rơi mất nút gợi ý:*
     - Tại `api.ts` (`frontend/src/lib/api.ts` và `IPGov_Chatbot/frontend/src/lib/api.ts`), khi nhận SSE event `done`, object chuyển tiếp vào `handlers.onDone` chỉ bóc tách `{ full_answer, contact_support, metrics }` và bỏ rơi hoàn toàn trường `data.quick_action_chips`.
     - Tại `ChatContainer.tsx`, hàm `onDone` chỉ cập nhật `content` và `contact_support`, không gán `quick_action_chips: doneData.quick_action_chips`.
  3. *Lỗi truy vấn trả về 0 dòng:* Tại `node_parse_context`, bộ trích xuất phòng ban chỉ ánh xạ từ khóa `"công thương"` sang `'68-1-01'`, thiếu từ khóa `"nông nghiệp"`, dẫn đến `target_dept` bị `None`. LLM không được chỉ dẫn mã phòng ban của Sở Nông nghiệp trong CSDL nên tự bịa mã `'NN'`.
* **Giải pháp khắc phục:**
  1. *Ánh xạ đơn vị chuẩn:* Bổ sung các từ khóa `"nông nghiệp"`, `"sở nông nghiệp"`, `"ptnt"`, `"diêm nghiệp"` trỏ về mã phòng ban thực tế `'68-1-01'` trong `node_parse_context`, đồng thời đưa chỉ dẫn vào System Prompt của bộ sinh SQL: *"Mã đơn vị của Sở Nông nghiệp và PTNT / Chi cục Nông nghiệp trong kho là '68-1-01'. TUYỆT ĐỐI KHÔNG tự bịa mã phòng ban như 'NN'"*.
  2. *Chuẩn hóa thông báo rỗng:* Khi không có `selected_cand`, sử dụng tiền tố trung tính: `Yêu cầu tra cứu hiện **chưa có bản ghi số liệu được phê duyệt**...`, tuyệt đối không ghép nguyên văn câu hỏi vào sau từ *"Chỉ tiêu"*.
  3. *Chuyển tiếp đầy đủ Quick Action Chips:* Bổ sung `quick_action_chips` vào `StreamDonePayload` trong `api.ts`, chuyển qua `onDone` trong `ChatContainer.tsx` và render trực quan qua `QuickActionChips` trên `MessageItem.tsx` ở cả 2 cây frontend.
* **Kết quả kiểm chứng:**
  - Câu hỏi *"Trạng thái các đợt nộp báo cáo của Sở Nông nghiệp hiện nay thế nào?"* sinh câu SQL chính xác `WHERE r.department_code = '68-1-01'` và trả về đầy đủ 9 đợt báo cáo (6 approved, 3 draft) dạng bảng chi tiết.
  - Các ca kiểm thử rỗng hiển thị thông điệp tự nhiên không lặp lại câu hỏi.
  - Các nút bấm gợi ý hành động nhanh (Quick Action Chips) hiển thị đầy đủ bên dưới tin nhắn bot.
  - Toàn bộ 30/30 ca kiểm thử kho dữ liệu đều đạt chuẩn **100% PASSED**.

---

## 3. Các Ca Lỗi Hệ Thống Theo PLAN-REMEDIATION-v1.4.0 (Đã Khắc Phục Toàn Diện)

Đợt cập nhật `v1.4.0` giải quyết dứt điểm 10 mẫu lỗi hệ thống ghi nhận trong tập dữ liệu thực nghiệm `fail_quest_v1-2-0.json`, được xác minh bằng 15 ca kiểm thử đối kháng (`test_remediation_suite.py`) và 30 ca Golden Benchmark (`test_warehouse_30_cases.py`):

| Mã Bug Remediation | Mô Tả & Mẫu Lỗi | Cơ Chế Khắc Phục | Trạng Thái |
| :--- | :--- | :--- | :---: |
| **BUG-CLARIF-agr-T01** | Lượt 1 thiếu mốc thời gian -> Kích hoạt Active Clarification Chips thay vì suy đoán cứng 2026 | Bổ sung `is_broad_inquiry` gate trong `node_parse_context`, trả về gợi ý làm rõ năm 2026/2025 | ✅ Đã khắc phục (100% Pass) |
| **BUG-ELLIP-agr-T02** | Kế thừa tỉnh lược đại từ: "vậy có bao nhiêu hộ" | Quản trị ngữ cảnh hội thoại qua `DiscourseStateTracker` (Level 1 Pivot) kế thừa topic `sản xuất muối` và năm `2026` | ✅ Đã khắc phục (100% Pass) |
| **BUG-PIVOT-agr-T03** | Chuyển dịch chỉ tiêu liên hoàn: Diện tích -> Sản lượng -> Số hộ | `HierarchicalFocusStack` (HFS) duy trì Top Frame, Schema Compatibility Gate đảm bảo chỉ tiêu cùng nhóm KTXH | ✅ Đã khắc phục (100% Pass) |
| **BUG-REVIVE-salt-T04** | Hồi sinh chủ đề (Topic Revival): Muối -> Nhiệm vụ -> Quay lại Muối | Triển khai Level 2 Interleaved Topic Return (`find_frame_by_topic`), hồi sinh `temporal_slot` và `department_slot` từ quá khứ | ✅ Đã khắc phục (100% Pass) |
| **BUG-NONADD-i_01-T09** | Chỉ tiêu non-additive Doanh thu bình quân trang trại bị cộng dồn `SUM` | Bổ sung cờ `is_non_additive`, ép buộc sinh CTE Window Function `ROW_NUMBER() OVER (...) AS rn WHERE rn = 1` hoặc `AVG` | ✅ Đã khắc phục (100% Pass) |
| **BUG-DIRTY-l_02-T02** | Dữ liệu bẩn: Tài khoản test mang tên đơn vị hành chính (`Phường Bắc Gia Nghĩa`) | Tự động phát hiện và gắn nhãn tag `*(TK Quản trị)*`, loại bỏ hardcode fallback `"Diêm nghiệp"` | ✅ Đã khắc phục (100% Pass) |
| **BUG-FALLBACK-pers-T03** | Hỏi về tài khoản test bị ép gán nhiệm vụ "Diêm nghiệp" | Thanh trừng toàn bộ hardcoded fallbacks `or "Diêm nghiệp"`, `or "Sở NN&PTNT"` trong `node_synthesize_response` | ✅ Đã khắc phục (100% Pass) |
| **BUG-PROMPT-pers-T04** | Lọc cán bộ theo chức vụ QTV bị hallucinate nhiệm vụ Diêm nghiệp | Bổ sung System Prompt phân tách rõ giữa chức vụ QTV và phân công nhiệm vụ, trích xuất chính xác theo `user.position` | ✅ Đã khắc phục (100% Pass) |
| **BUG-FILTER-pers-T09** | Lọc định hướng phủ định ("thuộc chi cục, không lấy cấp phòng") | Tự động chuẩn hóa câu hỏi và ánh xạ lọc vào `um.office_name NOT ILIKE '%phòng%'` và `um.office_name ILIKE '%chi cục%'` | ✅ Đã khắc phục (100% Pass) |
| **BUG-OUTSCOPE-gen-T10** | Câu hỏi ngoài phạm vi DWH (CCCD, thời tiết, lãnh đạo chính trị, sáng tác/đánh giá chủ quan) | Tích hợp `ScopePrechecker` tại `chat.py` và `node_parse_context`, từ chối lịch sự an toàn, chặn đứng lỗi 500 và crash `COUNT(f.id)` | ✅ Đã khắc phục (100% Pass) |
| **BUG-013** | Nuốt mất event SSE `thought_progress` (`guardrails_passed`) khi stream qua Agent | Phát đầy đủ `event: thought_progress` với `step="guardrails_passed"` trước khi ủy quyền Agent (`[TRAP-042]`) | ✅ Đã khắc phục (9/9 Pass) |
| **BUG-014** | Hardcode thời gian `year = '2026'` và `comp_years = ['2025', '2026']` trong Track A & Archetype Patterns | Tham số hóa thời gian động, xóa bỏ mọi gán cứng năm, tôn trọng filters của spec và router | ✅ Đã khắc phục (20/20 Pass) |
| **BUG-015** | Không Warm-up đầy đủ model khi chạy khởi động backend -> First request bị lag 51 giây | Triển khai Non-blocking Lifespan Hydration trong `main.py`, nạp sẵn `ModelRegistry` và DuckDB vector cache | ✅ Đã khắc phục (v1.5.0) |
| **BUG-016** | F5 ở UI kích hoạt Uvicorn WatchFiles restart ngầm và xóa sạch state model | Cấu hình Scoped Directory Watcher (`reload_dirs` + `reload_excludes`) và Process-Level `ModelRegistry` Singleton | ✅ Đã khắc phục (v1.5.0) |

---

### BUG-015 & BUG-016: Lỗi Không Warm-up Đầy Đủ & Mất State Model Khi F5 UI

* **Ngữ cảnh phát hiện:** Người dùng gửi câu hỏi đầu tiên sau khi khởi động backend phải chờ hơn 50 giây; và cứ mỗi khi bấm **F5** trên trình duyệt Web UI thì hệ thống lại bắt đầu tải lại weights từ đầu (`Loading weights: 0%| ... 100%| 391/391`).
* **Hiện tượng lỗi (Bug Symptom):**
  1. *First-Request Cold-Start Lag:* Thời gian phản hồi câu hỏi đầu tiên của người dùng lên tới 51 giây do phải import `sentence_transformers` (47s) + nạp 391 tensor weights (2.5s) + tính toán embedding.
  2. *F5 UI State Loss:* Trình duyệt refresh trang Next.js (`localhost:3000`), sau đó gửi câu hỏi kế tiếp thì terminal backend lại hiện thanh tải `Loading weights: 391/391`.
* **Nguyên nhân gốc rễ (Root Cause):**
  1. *Thiếu Startup Lifespan Hydration:* `IPGov_Chatbot/main.py` chỉ `yield` ngay trong hàm `lifespan` mà không nạp trước mô hình `SentenceTransformer`, vector cache của DuckDB hay khởi tạo pool CSDL. Mọi thứ bị hoãn lại (lazy-loading) đến đúng thời điểm người dùng gửi câu hỏi đầu tiên.
  2. *Uvicorn Spurious Watcher Reload:* Uvicorn chạy với `reload=True` quét toàn bộ thư mục root. Khi bấm F5, Next.js dev server ghi tệp cache vào `frontend/.next/`, đồng thời SQLite ghi vào `data/agent_memory.db-wal`. Thư viện `watchfiles` của Uvicorn phát hiện file thay đổi nên tự động **kill tiến trình Python backend và restart lại**. Khi process bị restart, toàn bộ RAM chứa weights bị hủy, buộc lượt hỏi tiếp theo phải nạp lại từ đầu.
* **Giải pháp khắc phục:**
  1. *Xây dựng `ModelRegistry` Singleton (`IPGov_Chatbot/core/model_registry.py`):* Lưu giữ mô hình embedding vĩnh viễn ở cấp độ tiến trình Python, sử dụng khóa tái nhập `threading.RLock()` và `local_files_only=True` nạp trực tiếp từ cache đĩa.
  2. *Non-blocking Lifespan Hydration (`IPGov_Chatbot/main.py`):* Khởi chạy worker nền `_run_startup_warmup()` ngay khi khởi động. Mở cổng HTTP trong < 300ms (`readiness: warming_up`) và hoàn tất nạp 5/5 tài nguyên trong ~3.3 giây (`readiness: ready`).
  3. *Uvicorn Scoped Watcher Filter (`run_server.py`, `main.py`, `backend/app/main.py`):* Cấu hình tường minh `reload_dirs` chỉ theo dõi thư mục code backend, thiết lập `reload_excludes` loại trừ toàn diện `.next/*`, `node_modules/*`, `data/*`, `*.db`, `*.parquet`, `*.log`.
* **Kết quả đo lường thực nghiệm:**
  - Thời gian truy xuất mô hình embedding sau nạp: **0.01 ms**.
  - Thời gian truy xuất chỉ tiêu DuckDB Semantic Catalog: **0.1 ms** (từ 51s $\to$ 0.1ms).
  - Tốc độ hoàn tất truy vấn DWH thực tế: **3.0 giây** (bao gồm toàn trình sinh SQL và query PostgreSQL).
  - F5 tại UI: Terminal backend hoàn toàn im lặng, không restart, không bao giờ load lại weights.



