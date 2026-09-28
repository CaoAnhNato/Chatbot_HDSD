# MANDATORY CODING RULES & ARCHITECTURE STANDARDS FOR IPGOV CHATBOT

> **Phạm vi áp dụng:** Toàn bộ mã nguồn thuộc dự án Trợ lý ảo Tra cứu DWH Chính phủ điện tử (`IPGov_Chatbot`).  
> **Cơ sở tham chiếu:** `IPGov_Chatbot/PLAN_KIEN_TRUC_CAY_THU_MUC_VA_QUY_TAC_CODE.md` và 11 Blueprints kiến trúc.  
> **Chuẩn mực tuân thủ:** Arc42, IEEE Std 1016-2009, Spider 2.0 / BIRD-SQL Benchmark, và Triết lý Tinh Giản Ponytail Lean.

---

## 1. 4 NGUYÊN TẮC KIẾN TRÚC CỐT LÕI (CORE ARCHITECTURAL PRINCIPLES)

1. **Kiến Trúc In-Process Modular Monolith:**
   - Tuyệt đối không xé nhỏ hệ thống thành các microservices qua HTTP/gRPC nội bộ nhằm giữ kiến trúc tinh gọn, tập trung xử lý in-process và giảm thiểu độ phức tạp giao tiếp mạng.
   - Toàn bộ 8 modules kỹ thuật chạy chung tiến trình bộ nhớ trong FastAPI Backend, giao tiếp bằng hàm bất đồng bộ (asyncio) và Pydantic v2 DTOs.

2. **Cơ Chế Lean 2-Stage Retrieval Trong RAM (Không Dùng Vector DB Ngoại Vi):**
   - **Giai đoạn 1:** Dùng DuckDB Native FTS (BM25) kết hợp RapidFuzz lọc thô bảng/cột trong RAM.
   - **Giai đoạn 2:** Dùng NetworkX Minimal Steiner Tree trên đồ thị khóa ngoại DWH để tự động bù đắp các bảng cầu nối trung gian (Bridge Tables), ngăn chặn $100\%$ lỗi gãy quan hệ JOIN.
   - Nghiêm cấm cài đặt các cụm Vector Database ngoại vi gây nợ kỹ thuật và hiện tượng Schema Topological Blindness.

3. **Cưỡng Chế Đẩy Tính Toán Xuống CSDL (Database-First Push-Down):**
   - Toàn bộ các phép toán thống kê tập hợp (Tăng trưởng YoY/MoM, Xếp hạng Top-K `DENSE_RANK()`, Tỷ trọng đóng góp `SUM() OVER ()`, Phân vị Median/Percentile) bắt buộc phải được thực thi trực tiếp bằng SQL Window Functions trong PostgreSQL và DuckDB.
   - **Tuyệt đối cấm LLM tự tính toán hoặc làm tròn số** để triệt tiêu $100\%$ ảo giác toán học (Mathematical Hallucination). Python chỉ đóng vai trò đường ống dẫn dữ liệu (piping) từ CSDL sang Jinja2.

4. **Biên Giới Bảo Mật AST Tất Định (Deterministic AST Guardrails):**
   - Mọi chuỗi SQL sinh ra từ LLM được xem là **Untrusted String** (Chuỗi ký tự chưa xác thực).
   - Cấm gửi trực tiếp Untrusted SQL vào driver kết nối CSDL. Bắt buộc phải đi qua 5 tầng duyệt AST của SQLGlot (`app/modules/mod06_ast_enforcer`):
     - Kiểm tra dialect PostgreSQL 16.
     - Chặn tuyệt đối DDL/DML (DROP, DELETE, UPDATE, INSERT, ALTER...).
     - Whitelist bảng cho phép, cấm `pg_catalog` và `information_schema`.
     - Thuật toán Recursive Scope Visitor tiêm vị từ phân quyền HBAC vào đúng scope CTE / Subquery.
     - Tiêm giới hạn `LIMIT 500`.

---

## 2. THANG BẬC TINH GIẢN PONYTAIL 7 BẬC (THE PONYTAIL LEAN LADDER)

Mọi kỹ sư và Agent khi phát triển hoặc tái cấu trúc mã nguồn BẮT BUỘC phải leo qua 7 bậc thang này và dừng lại ở bậc đầu tiên giải quyết được bài toán:

* **Bậc 1 (YAGNI - You Aren't Gonna Need It):**  
  - Không tạo Interface khi chỉ có đúng 1 Class hiện thực.
  - Không tạo Abstract Factory khi chỉ sinh một loại đối tượng.
  - Không viết code "để dành cho tương lai", chỉ viết những gì yêu cầu hiện tại đòi hỏi.
* **Bậc 2 (Reuse First):**  
  - Kiểm tra thư mục `app/schemas/` và `app/core/` trước khi định nghĩa thêm kiểu dữ liệu hoặc hàm tiện ích mới.
* **Bậc 3 (Stdlib First):**  
  - Ưu tiên tối đa thư viện chuẩn của Python: `enum.Enum`, `typing.Annotated`, `dataclasses`, `asyncio.gather`, `operator.ior` (gom dictionary trong RAM), `string.Template`.
* **Bậc 4 (Native Platform / Database-First):**  
  - Sử dụng SQL Window Functions cho thống kê; dùng `WITH RECURSIVE` hoặc `NOT EXISTS` cho duyệt cây phân cấp và lọc nút lá thay vì đệ quy trong Python.
* **Bậc 5 (Already-installed Libs):**  
  - Dùng `Jinja2` render template trong $< 0.05\text{ms}$; tuyệt đối không tự chế regex `re.sub`. Dùng DuckDB RAM thay vì cài thêm dịch vụ ngoài.
* **Bậc 6 (One Line):**  
  - Ưu tiên biểu thức ngắn gọn, trực diện, dễ đọc hơn là chia nhỏ thành nhiều hàm phụ trợ rườm rà.
* **Bậc 7 (Minimum Code with Safety):**  
  - Code tối thiểu nhưng **không được cắt giảm các chốt chặn an toàn tại ranh giới bảo mật** (JWT validation, AST sanitizer, DLQ logging).

---

## 3. QUY CHUẨN HỢP ĐỒNG INPUT / OUTPUT (STRICT FUNCTION I/O CONTRACTS)

1. **100% Type Hints Bắt Buộc:**
   - Mọi tham số đầu vào và giá trị trả về của hàm phải được khai báo kiểu dữ liệu tường minh (sử dụng cú pháp Python 3.10+ như `int | None`, `list[str]`, `dict[str, Any]`).
2. **Cấm Trả Về Kiểu `Any` Hoặc `dict` Vô Danh Ở Ranh Giới Module:**
   - Mọi dữ liệu truyền qua biên giới giữa 8 modules kỹ thuật bắt buộc phải được đóng gói bằng **Pydantic v2 BaseModel (DTO)** khai báo trong `app/schemas/`.
3. **Docstrings Chuẩn Google Style:**
   - Mỗi hàm public/module boundary phải có docstring rõ ràng gồm:
     - `Args`: Tên tham số, kiểu, ý nghĩa nghiệp vụ và ràng buộc giá trị.
     - `Returns`: Cấu trúc và ý nghĩa của đối tượng trả về.
     - `Raises`: Danh sách các ngoại lệ thuộc cây phân cấp `IPGovBaseException`.
     - `Tracing Context`: Tên OpenTelemetry Span và các thuộc tính gắn kèm.
4. **Mô Hình Xử Lý Lỗi Phân Cấp (Exception Hierarchy):**
   - Mọi lỗi nghiệp vụ phải kế thừa từ `IPGovBaseException` (trong `app/core/exceptions.py`), mang theo `error_code`, `status_code`, và `context_payload` để tự động đẩy vào bảng Dead-Letter-Queue khi có sự cố.

---

## 4. QUY CHUẨN GỠ LỖI (DEBUG) & QUAN SÁT (OBSERVABILITY CỤC BỘ)

1. **Lan Truyền Trace ID (Trace Context Propagation):**
   - Mọi request tại Gateway bắt buộc phải sinh một `trace_id` (UUIDv4) và truyền xuyên suốt qua tất cả các hàm của 8 modules.
   - Mọi log ghi ra (Structured JSON Logging) bắt buộc phải đính kèm `trace_id`.
2. **Hàng Đợi Sự Cố Dead-Letter-Queue (DLQ):**
   - Khi phát hiện lỗi cú pháp SQL, chặn bảo mật AST, hoặc quá thời gian chờ ($> 5000\text{ms}$), hệ thống bắt buộc phải ghi 1 bản ghi vào bảng `public.chatbot_dlq_incidents` (PostgreSQL) để phục vụ debug độc lập offline mà không làm gián đoạn người dùng.
3. **Triển Khai Tracing Cục Bộ (Local / Docker):**
   - Sử dụng OpenTelemetry SDK cục bộ, xuất metrics và traces/spans về Docker collector/log file nội bộ; sẵn sàng chuyển tiếp Langfuse khi cần.

---

## 5. QUY CHUẨN KIỂM THỬ DÂY CHUYỀN SNAPSHOT (CHAINED SNAPSHOT HARNESS)

1. **Nguyên Tắc Kiểm Thử Cách Ly Từng Module (Isolated Verification):**
   - Mỗi module $k$ trong 8 modules được kiểm thử độc lập bằng cách đọc trực tiếp file snapshot đầu vào từ `tests/fixtures/snapshots/stage_{k-1}/`.
   - Cấm viết test module $k$ mà phụ thuộc vào việc phải chạy lại toàn bộ từ module $1$.
2. **Cưỡng Chế Assertion Gates:**
   - Không được phép ghi đè snapshot baseline nếu chưa vượt qua toàn bộ Assertion Gates của giai đoạn đó.
3. **Lệnh Thực Thi Kiểm Thử Bắt Buộc Sử Dụng Môi Trường `venv`:**
   - Chạy test qua: `.\.venv\Scripts\python.exe -m pytest tests/chained/ -v`.

---

## 6. QUY TẮC QUẢN LÝ TỆP TIN, CẤU TRÚC THƯ MỤC VÀ VỆ SINH WORKSPACE THEO PONYTAIL (PONYTAIL LEAN FILE & DIRECTORY HYGIENE)

1. **Nguyên Tắc "Đúng Nơi Đúng Chỗ" (Strict Directory Placement):**
   - Mọi tệp tin sinh ra trong phạm vi `IPGov_Chatbot` bắt buộc phải được đặt vào đúng thư mục nghiệp vụ/chức năng phù hợp trong dự án (ví dụ: mã nguồn đặt trong `app/`, tài liệu thiết kế trong `blueprints/`, dữ liệu benchmark trong `data/`, đánh giá trong `evaluations/`, kiểm thử trong `tests/`).
   - Tuyệt đối cấm đặt các tệp tin script nháp, file test tạm thời, hoặc dump dữ liệu trực tiếp ở thư mục gốc `IPGov_Chatbot/` hoặc vứt rải rác ngoài thư mục quy định.

2. **Bộ 3 Câu Hỏi Vàng Ponytail Trước Khi Tạo Folder Mới (The 3-Question Folder Gate):**
   Trước khi có ý định tạo thêm bất kỳ một folder mới nào để lưu file, Agent và kỹ sư BẮT BUỘC phải tự chất vấn 3 câu hỏi sau:
   - **Câu hỏi 1 (Tốc độ tìm kiếm):** *Việc tạo folder mới để lưu file có thực sự giúp quá trình định vị và tìm kiếm tệp tin nhanh hơn không?* Hay chỉ làm tăng độ sâu cây thư mục và gây mệt mỏi khi duyệt file (Directory Nesting Fatigue)?
   - **Câu hỏi 2 (Vòng đời & Tái sử dụng):** *Folder này có được tận dụng cho nhiều lần sau để lưu trữ dữ liệu lâu dài không? Hay tạo ra rồi chỉ lưu những file dùng 1 lần duy nhất rồi bỏ quên?* Nếu chỉ dùng 1 lần, tuyệt đối không tạo folder mới; ưu tiên xử lý in-memory hoặc dùng thư mục tạm thời hệ thống.
   - **Câu hỏi 3 (Chống trùng lặp & Dồn thư mục):** *Có folder nào đang tồn tại tương tự trong `IPGov_Chatbot` hay không (ví dụ: `test` và `tests`, `model` và `models`, `doc` và `docs`, `script` và `scripts`)?* Nếu có, bắt buộc phải gom dồn vào folder đã có trước đó hoặc tạo thêm folder con (sub-folder) bên trong folder đó nếu thật sự cần thiết để quản lý, tuyệt đối không tạo thêm folder song song gây phân mảnh.

3. **Quy Chuẩn Chống Rác Thải Dữ Liệu & Vệ Sinh Workspace (Zero-Slop & Anti-Pollution):**
   - Tránh tuyệt đối trường hợp để các file rác (`temp_*.py`, `test_tmp.json`, `output.txt`, các file log trung gian không sử dụng) tràn lan trong folder làm "dơ" workspace rất nhiều, gây mất thời gian khi tìm kiếm file cần thiết và làm loãng ngữ cảnh làm việc của Agent.
   - Toàn bộ các file snapshot phục vụ kiểm thử chuỗi dây chuyền bắt buộc phải được đặt ngăn nắp trong `tests/fixtures/snapshots/stage_{k}_{module_name}/`.
   - Toàn bộ báo cáo tóm tắt thực thi kiểm thử bắt buộc phải lưu trong `tests/reports/`.
   - Luôn chủ động dọn dẹp sạch sẽ các tệp trung gian không còn giá trị sau khi hoàn thành nhiệm vụ.

---

## 7. QUY TẮC ĐỒNG BỘ LAN TRUYỀN TÀI LIỆU KHI CẬP NHẬT BLUEPRINTS (MANDATORY BLUEPRINT CASCADE SYNC)

1. **Ràng Buộc Đồng Bộ Bắt Buộc (The Cascade Sync Invariant):**
   - Bộ tài liệu `IPGov_Chatbot/blueprints/` là Nguồn Chân Lý Duy Nhất (Single Source of Truth - SSOT) của kiến trúc.
   - Mỗi khi thực hiện cập nhật hoặc bổ sung nội dung bất kỳ trong `blueprints/`, Agent **BẮT BUỘC PHẢI TỰ ĐỘNG** tìm kiếm toàn bộ các tệp `.md` liên quan trong `IPGov_Chatbot` (như `docs/MASTER_PLAN_AND_PROGRESS_TRACKING.md`, các đặc tả module trong `docs/`, `blueprints/08...`, `evaluations/`) và tiến hành đồng bộ nội dung tương ứng.
   - Tuyệt đối không dừng lại ở việc chỉ cập nhật file blueprint đơn lẻ khiến tài liệu thi công và kiểm thử bị lệch pha (Documentation Drift).
2. **Kích Hoạt Kỹ Năng Bắt Buộc:**
   - Sử dụng quy chuẩn quy định tại skill [`blueprint-cascade-sync`](../skills/blueprint-cascade-sync/SKILL.md).
   - Áp dụng nguyên tắc `/verification-before-completion`: Kiểm chứng bằng chứng thực tế trước khi tuyên bố hoàn tất.


