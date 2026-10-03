# 🚀 BÁO CÁO CẬP NHẬT CÁC NĂNG LỰC HIỆN TẠI CỦA HỆ THỐNG CHATBOT

> **Đơn vị quản lý:** Dự án Chatbot Tra Cứu Số Liệu Điều Hành Chính Quyền Tỉnh (IPGov_Chatbot)  
> **Phiên bản hệ thống:** `v1.2.0` (Chuẩn hóa giao diện người dùng, Tối ưu hóa truy vấn kho dữ liệu & Bộ kiểm thử 30 ca thực tế)  
> **Quy chuẩn theo dõi:** Mỗi năng lực của Chatbot được tổng hợp rõ ràng qua 5 mục thông tin:
> 1. **Đang phát triển**
> 2. **Đang thử nghiệm**
> 3. **Hoàn Thiện**
> 4. **Đang fix Bug/update**
> 5. **Version**

---

## Sơ Đồ Danh Mục Các Năng Lực Cốt Lõi Của Chatbot

```mermaid
flowchart TD
    ROOT["HỆ THỐNG NĂNG LỰC CHATBOT"]
    
    ROOT --> C1["1. Tra cứu chỉ số cụ thể"]
    ROOT --> C2["2. Phân tích cơ cấu và thành phần"]
    ROOT --> C3["3. So sánh biến động theo thời gian"]
    ROOT --> C4["4. Xếp hạng chỉ số"]
    ROOT --> C5["5. Kiểm tra dữ liệu sẵn sàng & hỏi lại"]
    ROOT --> C6["6. Tra cứu báo cáo và phân công nhiệm vụ"]
    ROOT --> C7["7. Bảo vệ an toàn và bảo mật kho dữ liệu"]
    ROOT --> C8["8. Trả lời thông minh, Giao diện UI & Câu lệnh minh bạch"]
```

---

### 1. Năng Lực Tra Cứu Chỉ Số Cụ Thể

* **Đang phát triển:**
  - Tự động nhận diện đơn vị tính (hecta, tấn, triệu đồng, sản phẩm) ngay cả khi người dùng không đề cập trong câu hỏi.
* **Đang thử nghiệm:**
  - Truy vấn đồng thời đa ứng viên (Single-Query Multi-Candidate Retrieval): Lấy cả 5 ứng viên chỉ tiêu trong 1 câu SQL để vừa truy xuất số liệu chính vừa có sẵn dữ liệu gợi ý tức thì.
* **Hoàn Thiện:**
  - Tự động nhận diện mốc thời gian năm 2026 và phạm vi tỉnh Lâm Đồng khi người dùng tra cứu nhanh.
  - Phân biệt chính xác giữa **chỉ tiêu cộng dồn** (Additive: áp dụng `SUM(value)` như *Hộ sản xuất muối: 1,320*) và **chỉ tiêu bình quân/không cộng dồn** (Non-additive: lấy báo cáo mới nhất).
  - So khớp an toàn tuyệt đối: Dùng `TRIM(f.name) ILIKE TRIM('<Candidate Name>')` (không dùng `%` hai đầu) để triệt tiêu lỗi nuốt chuỗi con hoặc gom nhầm chỉ tiêu khác.
* **Đang fix Bug/update:**
  - Đã khắc phục triệt để lỗi gom nhầm `%trang trại%` (từ con số sai 4,270 về đúng bản chất: số lượng trang trại là NULL, doanh thu bình quân trang trại là 2,200).
* **Version:** `v1.2.0`

---

### 2. Năng Lực Phân Tích Cơ Cấu Và Thành Phần

* **Đang phát triển:**
  - Tự động tính toán tỷ trọng phần trăm đóng góp của từng thành phần so với tổng thể toàn ngành.
* **Đang thử nghiệm:**
  - Hiển thị bảng phân rã chi tiết (Breakdown Table) theo từng đơn vị cho các chỉ tiêu không cộng dồn (suất đầu tư, tỷ lệ hoàn thành).
* **Hoàn Thiện:**
  - Tổng hợp số liệu theo nhóm chỉ tiêu rành mạch, hiển thị bảng dữ liệu trực quan (`STT | Chỉ tiêu / Mục | Giá trị`).
  - Khử trùng lặp lũy kế qua các kỳ báo cáo bằng CTE Window Function (`ROW_NUMBER() OVER (...) AS rn WHERE rn = 1`) sắp xếp theo ngày nộp và phiên bản mới nhất.
* **Đang fix Bug/update:**
  - Chuẩn hóa tên cột hiển thị, không tự ý gán nhãn tên chỉ tiêu thành tên cơ quan hay đơn vị.
* **Version:** `v1.2.0`

---

### 3. Năng Lực So Sánh Biến Động Theo Thời Gian

* **Đang phát triển:**
  - Phân tích xu hướng tăng giảm liên tục qua các quý trong năm hoặc nhiều năm liên tiếp.
* **Đang thử nghiệm:**
  - Tự động đối chiếu số liệu giữa các kỳ báo cáo khi kho dữ liệu được bổ sung các năm trước.
* **Hoàn Thiện:**
  - Trả lời trực diện và tự nhiên đối với câu hỏi về mốc thời gian điều hành: *"Hiện tại kho dữ liệu điều hành (IPGov DWH) của tỉnh Lâm Đồng đang phục vụ và tổng hợp số liệu báo cáo đã phê duyệt của năm **2026**"*.
  - Định dạng số chuẩn Tiếng Việt: Dấu phẩy `,` phân cách hàng nghìn (ví dụ: `1,320`, `54,000`), dấu chấm `.` phân cách thập phân (ví dụ: `12.5`), giữ nguyên năm 4 chữ số (`2026`).
* **Đang fix Bug/update:**
  - Xóa bỏ hoàn toàn hiện tượng trả lời ngớ ngẩn coi năm là số liệu đo lường (như `"đạt: 2.026"` hoặc `"đạt: 2,026"`).
* **Version:** `v1.2.0`

---

### 4. Năng Lực Xếp Hạng Chỉ Số

* **Đang phát triển:**
  - Tùy biến xếp hạng theo nhiều tiêu chí nghiệp vụ linh hoạt (theo quy mô, tiến độ, số lượng).
* **Đang thử nghiệm:**
  - Đo lường và làm nổi bật biên độ chênh lệch giữa đơn vị dẫn đầu và đơn vị đứng cuối.
* **Hoàn Thiện:**
  - Trình bày bảng xếp hạng rõ ràng, làm nổi bật mục dẫn đầu.
  - Chỉ kích hoạt bảng xếp hạng khi người dùng thực sự có yêu cầu so sánh hơn kém (từ khóa "top", "cao nhất", "thấp nhất").
* **Đang fix Bug/update:**
  - Đảm bảo trật tự sắp xếp luôn theo thứ tự giảm dần (`ORDER BY ... DESC`) chính xác.
* **Version:** `v1.2.0`

---

### 5. Năng Lực Kiểm Tra Độ Sẵn Sàng Của Dữ Liệu & Gợi Ý Làm Rõ

* **Đang phát triển:**
  - Mở rộng thuật toán tìm kiếm kết hợp Hybrid RRF (Dense Embedding + RapidFuzz) trên DuckDB Catalog trong RAM.
* **Đang thử nghiệm:**
  - Tự động quyết định giữa: Chọn thẳng chỉ tiêu Top 1 (khi vượt trội `Score_Delta >= 0.10`) hoặc kích hoạt nút bấm làm rõ (Active Clarification Chips khi câu hỏi quá ngắn hoặc điểm số xấp xỉ).
* **Hoàn Thiện:**
  - **Xử lý số liệu NULL trung thực & Gợi ý có thật:** Khi chỉ tiêu người dùng hỏi tồn tại nhưng chưa có số liệu (`value IS NULL`, ví dụ: 'Trang trại'), chatbot giải thích rõ ràng và tự động lấy chỉ tiêu liên quan có số liệu thực tế từ danh sách ứng viên (ví dụ: 'Doanh thu bình quân...') để gợi ý.
  - **Bộ kiểm thử 30 ca kho dữ liệu thực tế:** Vượt qua 30/30 ca kiểm thử (tỷ lệ đạt 100%) trực tiếp trên CSDL PostgreSQL công ty, lưu vết nhật ký tại `tests/logs/warehouse_30_cases_run.jsonl`.
* **Đang fix Bug/update:**
  - Không còn hiện tượng tự suy đoán số liệu bừa bãi khi dữ liệu trong kho là NULL hoặc chưa được phê duyệt.
* **Version:** `v1.2.0`

---

### 6. Năng Lực Tra Cứu Báo Cáo Và Phân Công Nhiệm Vụ

* **Đang phát triển:**
  - Tra cứu liên kết chuyên sâu giữa danh mục biểu mẫu nộp dữ liệu và phân công người dùng phụ trách.
* **Đang thử nghiệm:**
  - Tự động nhận diện mã định danh cơ quan (ví dụ: Sở Nông nghiệp `68-1-01`) để tiêm điều kiện lọc thẩm quyền chính xác.
* **Hoàn Thiện:**
  - **Tra cứu thông suốt 4 trụ cột nghiệp vụ trong kho:**
    1. *Chỉ tiêu KTXH & Nông nghiệp:* `fact_report_criteria` + `criteria` (Hộ sản xuất muối: 1,320, diện tích: 3,040, HTX: 138).
    2. *Tình hình Báo cáo & Tổng hợp:* `report` (Thống kê 9 đợt nộp: 6 đã duyệt, 3 bản nháp; đếm tổng số báo cáo đã phê duyệt: 6).
    3. *Biểu mẫu Thu thập Số liệu:* `collection_form` (Phản hồi trung thực, lịch sự khi bảng rỗng, kèm gợi ý các vùng dữ liệu sẵn có).
    4. *Nhiệm vụ, Đề án & Cán bộ:* `mission` + `user_mission` + `"user"` (Truy xuất danh mục 5 nhiệm vụ trọng tâm; danh sách cán bộ phụ trách nhiệm vụ Diêm nghiệp: Nguyễn Thị Thúy Lành - Chi cục, Phường Bắc Gia Nghĩa - Phòng nông nghiệp).
  - **Bảng Hiển Thị Chuyên Biệt Theo Từng Miền Dữ Liệu:**
    * Cán bộ phân công: `| STT | Họ và tên | Chức vụ | Phòng ban / Đơn vị | Nhiệm vụ phụ trách |`
    * Đợt nộp báo cáo: `| STT | Đợt nộp báo cáo | Đơn vị nộp | Trạng thái phê duyệt |`
    * Danh mục nhiệm vụ: `| STT | Tên nhiệm vụ / Đề án | Trạng thái thực hiện |`
  - **Việt Hóa Toàn Diện Trạng Thái:** Chuyển đổi mã kỹ thuật sang ngôn ngữ hành chính chuẩn (`approved` $\to$ **Đã phê duyệt**, `draft` $\to$ **Bản nháp**, `true` $\to$ **Đang triển khai**).
* **Đang fix Bug/update:**
  - Đã khắc phục `TRAP-036`: Ép kiểu boolean chuẩn cho `m.mission_status` (loại bỏ lỗi runtime `'active'`).
  - Đã khắc phục `TRAP-037`: Loại bỏ ảo giác cột `um.mission_code` trên bảng `user_mission`.
  - Đã khắc phục `TRAP-038`: Hỗ trợ đầy đủ alias `user_name`, `user_position` trong bộ trích xuất thông tin cán bộ.
* **Version:** `v1.2.0`

---

### 7. Năng Lực Bảo Vệ An Toàn & Bảo Mật Kho Dữ Liệu

* **Đang phát triển:**
  - Phân tích độ phức tạp của câu hỏi để tự động phân bổ tài nguyên xử lý tối ưu.
* **Đang thử nghiệm:**
  - Mở rộng phạm vi tra cứu toàn tỉnh cho cán bộ điều hành trong giai đoạn thử nghiệm.
* **Hoàn Thiện:**
  - Màng chắn AST Guardrail ngăn chặn 100% các câu hỏi hoặc câu lệnh mang tính chất phá hủy, chỉnh sửa CSDL (DDL/DML injection: DROP, DELETE, ALTER).
  - Tỷ lệ vi phạm bảo mật đo lường đạt **0.0%**.
* **Đang fix Bug/update:**
  - Tự động tiêm điều kiện lọc tenant `68` và trạng thái phê duyệt `report_status = 'approved'` ở tầng AST.
* **Version:** `v1.2.0`

---

### 8. Năng Lực Trả Lời Thông Minh, Giao Diện UI & Câu Lệnh Minh Bạch

* **Đang phát triển:**
  - Bổ sung biểu đồ trực quan hóa dữ liệu tự động (Chart Widget) đối với các câu hỏi thống kê phân bố hoặc so sánh.
* **Đang thử nghiệm:**
  - Cơ chế nhận diện ngữ cảnh đàm thoại đa lượt (Multi-turn Context) ghi nhớ chỉ tiêu và đơn vị của lượt hỏi trước.
* **Hoàn Thiện:**
  - **Nút Mở Rộng Xem Câu Lệnh SQL (Expandable SQL Toggle Button):**
    * Trên giao diện web (`frontend/src/components/chat/MessageItem.tsx`), khối câu lệnh SQL được đóng gói bên trong thẻ `<details>` có nút bấm thu gọn/mở rộng `🔍 Xem câu lệnh truy vấn (SQL Query)`.
    * **Mặc định luôn thu gọn (`isOpen: false`)**: Tránh choán toàn bộ màn hình của người dùng.
    * Khi người dùng có nhu cầu kiểm tra tính minh bạch, chỉ cần nhấn vào nút để **mở rộng (expand)** khối SQL, đi kèm tính năng sao chép (Copy) và tô màu cú pháp.
  - **Thanh Tiến Trình Trạng Thái Động (Dynamic Real-time Stage Loading Bar):**
    * Hiển thị trực quan từng bước xử lý theo thời gian thực (*Nhận diện ý định $\to$ Tìm kiếm chỉ tiêu $\to$ Sinh câu lệnh SQL $\to$ Truy vấn kho dữ liệu $\to$ Tổng hợp phản hồi*).
  - **Banner Khởi Động Nhận Diện Dự Án Độc Lập:**
    * Cập nhật lệnh khởi động Backend (`IPGov_Chatbot.run_server`) và Frontend: Hiển thị thông báo nhận diện nổi bật `🚀 ĐANG KÍCH HOẠT IPGov_Chatbot (CỔNG: <port>)` trên màn hình terminal, giúp người dùng phân biệt rành mạch, không bị nhầm lẫn sang các module ngoài của chatbot khác.
  - **Chuẩn Hóa Văn Phong Công Vụ & Bỏ Lặp Lại Câu Hỏi:**
    * Trả lời trực diện kết quả của chỉ tiêu, loại bỏ 100% việc nhúng lặp lại câu hỏi của người dùng.
    * Lời chào mở đầu chuyên nghiệp theo 4 trụ cột nghiệp vụ hành chính, loại bỏ hoàn toàn các tên bảng kỹ thuật CSDL thô (`fact_report_criteria`, `mission`...).
* **Đang fix Bug/update:**
  - Khắc phục triệt để lỗi giao diện tự động phình to khối SQL khi vừa tải xong tin nhắn.
* **Version:** `v1.2.0`

---

### 9. Năng Lực Quản Trị Ngữ Cảnh Hội Thoại Đa Lượt & Hòa Mạng Thần Kinh (PLAN-REMEDIATION-v1.4.0)

* **Hoàn Thiện:**
  - **Kiến trúc Ngữ cảnh Hội thoại 3 Cấp Độ (`DiscourseStateTracker` + `HierarchicalFocusStack` HFS-DSF):**
    * **Level 1 (Contiguous Attribute Pivoting):** Chuyển dịch thuộc tính liên hoàn giữa các lượt hỏi (Diện tích $\to$ Sản lượng $\to$ Số hộ) trên cùng một chủ đề mà không bị rớt mốc thời gian hoặc phạm vi hành chính.
    * **Level 2 (Interleaved Topic Return / Topic Revival):** Hồi sinh chính xác chủ đề cũ trong ngăn xếp khi người dùng hỏi xen kẽ nhiều chủ đề (ví dụ: *Muối $\to$ Nhiệm vụ $\to$ Quay lại Muối*), tự động hồi phục các slot `temporal_slot` (2026) và `department_slot` (68-1-01).
    * **Level 3 (Long-jump Discourse Resumption):** Tái kích hoạt chủ đề nhảy cóc dựa trên độ tương đồng ngữ nghĩa đối tượng khung (Frame-Aware D-SAS).
  - **Động Cơ Hòa Mạng Câu Hỏi Thần Kinh Không Regex (`NeuralCQREngine`):**
    * Sử dụng mô hình ngôn ngữ `gemini-2.5-flash-lite` với Pydantic Structured Output `CQRReformulationResult` để tái kiến tạo câu hỏi độc lập (Standalone Query), loại bỏ hoàn toàn bẫy Regex nối chuỗi thô.
  - **Cổng Kiểm Định Tương Thích Lược Đồ (Schema Compatibility Gate):**
    * Ngăn chặn việc gán ghép thuộc tính sai đối tượng (như hỏi chức vụ cán bộ trên chỉ tiêu muối hoặc hỏi sản lượng trên nhiệm vụ).
  - **Màng Lọc Phạm Vi An Toàn (`ScopePrechecker`):**
    * Tiền kiểm và từ chối an toàn ngay tại API `chat.py` và Router đối với 5 danh mục ngoài phạm vi DWH: Thủ tục CCCD/hành chính công, thời tiết đời sống, nhân sự cấp ủy/chính trị, sáng tác văn bản, và đánh giá định tính chủ quan.
  - **Thanh Trừng Toàn Diện Các Poisonous Hardcoded Fallbacks:**
    * Loại bỏ triệt để các fallback gây bẩn dữ liệu: `or "Diêm nghiệp"`, `or "Sở NN&PTNT"`, `or "2026"`, `or "chỉ tiêu"`, `"công thương" -> "68-1-05"`.
    * Tự động phát hiện và gắn tag `*(TK Quản trị)*` cho các tài khoản test mang tên đơn vị hành chính (`Phường Bắc Gia Nghĩa`).
    * **Tham số hóa thời gian Track A & Archetype Patterns:** Xóa bỏ hoàn toàn gán cứng `year = "2026"` và `comp_years = ["2025", "2026"]` trong `track_a_compiler.py` và `archetype_patterns.py`, thực hiện phân tích động theo thời gian câu hỏi.
    * **Khắc phục chuẩn luồng SSE Handshake:** Phát đầy đủ `event: thought_progress` với `step="guardrails_passed"` tại `gateway_endpoint.py`, khôi phục 100% tính tương thích hợp đồng API Gateway (`[TRAP-042]`).
  - **Bảo Vệ Khóa Chính & Khử Ảo Giác Mã Đơn Vị Ở Tầng AST Sanitizer:**
    * Giới hạn phạm vi thay thế `id -> fact_sk` strictly vào `fact_aliases`, bảo toàn tuyệt đối `r.id` của bảng báo cáo (`[TRAP-039]`).
    * Khử ảo giác mã tenant `68` và mã đơn vị không tồn tại `68-0-00` trên các câu hỏi nhiệm vụ và nhân sự (`[TRAP-040]`).
    * Khử ảo giác cột `year_code` trên các bảng không có cột năm `user_mission` và `user` (`[TRAP-041]`).
* **Kết Quả Đo Lường Thực Nghiệm:**
  - **15/15 Ca Kiểm Thử Đối Kháng (`test_remediation_suite.py`):** **100% PASSED** (Execution Accuracy EX: 100%, Valid SQL Rate VA: 100%).
  - **30/30 Ca Golden Benchmark DWH (`test_warehouse_30_cases.py`):** **100% PASSED** (Zero Regression).
  - **9/9 Ca Kiểm Thử Tích Hợp Gateway (`test_backend_app.py`):** **100% PASSED**.
  - **20/20 Ca Kiểm Thử Compiler (`test_mod05_phase1_track_a.py` & `test_mod05_phase2_track_b.py`):** **100% PASSED**.
* **Version:** `v1.4.0`

---

### 10. Năng Lực Khởi Động Siêu Tốc & Bảo Toàn State Mô Hình (PLAN-WARMUP-RELOAD-v1.5.0)

* **Hoàn Thiện:**
  - **Process-Level Model Registry Singleton (`IPGov_Chatbot/core/model_registry.py`):**
    * Quản lý tập trung mô hình nhúng `SentenceTransformer` (`AITeamVN/Vietnamese_Embedding_v2`) trong bộ nhớ RAM cấp độ tiến trình Python.
    * Sử dụng cơ chế khóa tái nhập `threading.RLock()` bảo đảm an toàn đa luồng và triệt tiêu 100% nguy cơ deadlock khi khởi tạo lồng nhau.
    * Tích hợp đường truyền tải nhanh `local_files_only=True`: Nạp trực tiếp 391 trọng số từ cache đĩa trong **2.5s**, loại bỏ hoàn toàn việc gửi yêu cầu mạng HTTPS kiểm tra phiên bản tới HuggingFace Hub.
    * Tốc độ truy xuất sau nạp: **0.01 ms** (tương đương truy xuất biến bộ nhớ trực tiếp).
  - **Khởi Động Nền Không Phong Tỏa Mạng (Non-blocking Lifespan Hydration):**
    * Trong `IPGov_Chatbot/main.py`: Mở cổng HTTP/8000 và phản hồi Healthcheck ngay tức khắc trong **< 300ms** (`readiness: warming_up`).
    * Một tác vụ nền (`_run_startup_warmup()`) chạy song song thực hiện 5 bước khởi tạo hoàn chỉnh:
      1. Khởi tạo `DWHConnectionPool` (PostgreSQL asyncpg pool) và ping kiểm tra kết nối `SELECT 1` (kèm timeout phòng vệ 4.0s).
      2. Nạp và chạy Warm-up Dummy Forward-Pass cho `ModelRegistry` để cấp phát bộ nhớ tensor cache.
      3. Tự động nạp trước 125 vector embeddings của DuckDB Semantic Catalog từ đĩa vào RAM.
      4. Pre-warm LangGraph Autonomous Warehouse Agent & SQLite Checkpointer.
      5. Pre-warm phiên làm việc SSL của LLM Gateway.
    * Sau khi hoàn tất (chỉ mất ~3.3 giây), hệ thống tự động chuyển cờ `readiness: ready`.
    * **Hiệu quả thực nghiệm:** Thời gian phản hồi First Request của người dùng giảm từ **51 giây xuống còn 0.1 ms đối với catalog retrieval và ~3.0 giây cho toàn trình SQL** (cải thiện hơn 15 lần).
  - **Triệt Tiêu Hiện Tượng Mất State Khi F5 Giao Diện (Uvicorn Scoped Watcher Filter):**
    * Cấu hình tường minh `reload_dirs` chỉ theo dõi thư mục mã nguồn backend (`IPGov_Chatbot/`).
    * Thiết lập `reload_excludes` toàn diện loại trừ mọi thư mục và tệp biến động: `.next/*`, `node_modules/*`, `data/*`, `*.db`, `*.parquet`, `*.log`, `tests/logs/*`.
    * **Kết quả:** Người dùng thoải mái bấm F5 hoặc làm mới trình duyệt, Uvicorn hoàn toàn im lặng, không bị kích hoạt restart ngầm và không bao giờ phải nạp lại trọng số 391/391.
* **Kết Quả Đo Lường:**
  - `ModelRegistry.warmup_embedding_model()`: **14.5s** (bao gồm nạp và dummy encode).
  - `ModelRegistry.get_embedding_model()`: **0.01 ms**.
  - `DuckDBSemanticCatalog.find_criteria_by_name()`: **0.1 ms**.
  - `HTTP Health Readiness`: Chuyển từ `warming_up` sang `ready` sau **1.0 - 3.3s**.
* **Version:** `v1.5.0`

