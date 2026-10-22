---
trigger: always_on
description: Mandatory rules for deep technical research (Web Search & ArXiv MCP), official framework documentation verification, software architecture principles, strict venv/uv environment execution, and anti-pattern/anti-heuristic standards.
---

# MANDATORY WORKSPACE RULES FOR TECH STACK, ENVIRONMENT EXECUTION & REQUIREMENTS

> [!IMPORTANT]
> **CÁC QUY TẮC THỰC THI BẮT BUỘC TRONG WORKSPACE DỰ ÁN**

---

## 1. Quy Tắc Bắt Buộc Nghiên Cứu Chuyên Sâu (Deep Web Reading & ArXiv Academic Grounding)

1. **Tìm Kiếm & Đọc Chi Tiết Nội Dung (Deep Web Reading)**:
   - Khi nghiên cứu, cải tiến hệ thống, đề xuất công nghệ/SOTA hoặc xử lý bug, **không dừng lại ở snippet tóm tắt**.
   - Bắt buộc dùng công cụ chuyên sâu (`fetch`, `firecrawl`...) đọc toàn bộ nội dung bài viết (Technical Blogs, Stack Overflow answers/comments, GitHub Issues, Official Release Docs) để nắm rõ bối cảnh và giải pháp đã kiểm chứng.

2. **Tra Cứu Paper Khoa Học Qua ArXiv MCP Khi Phân Tích Điểm Nghẽn (Bottleneck Analysis)**:
   - Khi phân tích bottleneck (latency, throughput, precision/recall, hallucination, nghẽn pipeline...), bắt buộc dùng MCP tool `arxiv` (`search_papers`, `read_paper`, `get_abstract`...) để tìm kiếm và đối chiếu các nghiên cứu uy tín.
   - Mọi đề xuất giải quyết bottleneck phải dẫn chứng rõ tên paper, ArXiv ID/Link, cơ chế thuật toán và đánh giá tính khả thi/đánh đổi (trade-offs) khi tích hợp vào kiến trúc dự án.

---

## 2. Quy Tắc Tra Cứu Official Documentation & Chuẩn Mực Kiến Trúc Hệ Thống (Architecture & Anti-Patching Standards)

1. **Tra Cứu Official Framework Docs Theo Đúng Version**:
   - Khi làm việc với bất kỳ framework/thư viện nào (FastAPI, LangChain, LlamaIndex, Pydantic, PyTorch, v.v.):
     - Bắt buộc kiểm tra và đọc tài liệu chính thức (Official Documentation) **tương ứng đúng với phiên bản hiện tại** đang cài đặt trong môi trường dự án.
     - Nắm vững chữ ký hàm (function signatures), kiểu dữ liệu các tham số (params), giá trị trả về, cơ chế lifecycle và luồng xử lý ngoại lệ theo chuẩn khuyến nghị của tác giả framework.

2. **Tuân Thủ Các Nguyên Lý & Mẫu Thiết Kế Hệ Thống (System Design Principles)**:
   - Mọi mã nguồn được thiết kế và triển khai trong dự án **bắt buộc phải tuân thủ nghiêm ngặt các nguyên lý kiến trúc phần mềm**, bao gồm:
     - **Reusability & Modularity**: Đảm bảo khả năng tái sử dụng giữa các class, module, function; tránh viết code trùng lặp (DRY).
     - **Pipe-and-Filter Architecture**: Thiết kế pipeline dữ liệu rành mạch, các bộ lọc/bước xử lý độc lập và có thể thay thế hoặc ghép nối linh hoạt.
     - **Strategy Pattern & Router Logic**: Tách biệt rõ ràng các chiến lược xử lý (ví dụ: intent routing, fallback strategies, model dispatching), cho phép mở rộng chiến lược mới mà không làm thay đổi luồng điều khiển cốt lõi (Open/Closed Principle).
     - **Dependency Injection (DI)**: Giảm thiểu sự phụ thuộc cứng giữa các thành phần, giúp mã nguồn dễ mở rộng, dễ mock và dễ viết unit/integration tests.
     - **Observability Layer**: Tích hợp tầng quan sát chuẩn hóa (Structured Logging, Tracking, Metrics, Context Tracing) để theo dõi luồng thực thi và hỗ trợ debug hiệu quả.

3. **Nghiêm Cấm Anti-Pattern Vá Code Tạm Bợ (Strict Anti-Patching Rule)**:
   - **TUYỆT ĐỐI KHÔNG** viết code theo kiểu các hàm rời rạc, chắp vá không có cấu trúc.
   - **TUYỆT ĐỐI KHÔNG** giải quyết lỗi hoặc edge cases bằng cách "đè thêm một đống điều kiện `if-else` / rule chắp vá" trực tiếp vào hàm hiện tại nhằm qua mắt bug tạm thời.
   - Khi phát hiện bug hoặc case chưa hỗ trợ, **bắt buộc phải xem xét lại toàn diện thiết kế kiến trúc**, tìm ra nguyên nhân gốc rễ (Root Cause) và tái cấu trúc (refactor/extend) logic một cách bài bản, đúng chuẩn mẫu thiết kế đã định hình.

---

## 3. Quy Tắc Môi Trường Python (`venv`), Công Cụ `uv` & Quản Lý Phụ Thuộc (`requirements.txt`)

1. **Chỉ Thực Thi Code & Quản Lý Package Trên Môi Trường `venv`**:
   - Mọi thao tác thực thi code Python, chạy script, kiểm thử, hoặc quản lý gói (thêm mới `install`, cập nhật `update`, gỡ bỏ `uninstall` package/library) **CHỈ ĐƯỢC PHÉP THỰC THI QUA MÔI TRƯỜNG `venv`** (đường dẫn: `.\venv\Scripts\python.exe` hoặc `venv\Scripts\pip`).
   - Nghiêm cấm chạy code hoặc cài đặt thư viện vào Python hệ thống toàn cục (Global Python) ngoài `venv`.

2. **Ưu Tiên Tải & Cài Đặt Package Bằng `uv` Để Đạt Tốc Độ Tối Đa**:
   - Bất kỳ khi nào thực hiện cài đặt hoặc cập nhật package/thư viện Python, Agent **BẮT BUỘC ƯU TIÊN SỬ DỤNG LỆNH `uv`** (ví dụ: `uv pip install --python .\venv\Scripts\python.exe <package>` hoặc `uv pip install ...` chỉ định môi trường `venv`) để tối ưu hóa tốc độ tải và cài đặt ở mức cao nhất.

3. **Cập Nhật Tự Động `requirements.txt` Khi Thay Đổi Thư Viện**:
   - Bất kỳ khi nào thực hiện cài đặt (`install`) hoặc cập nhật (`update`) bất kỳ package/thư viện Python nào vào môi trường `venv`, Agent **BẮT BUỘC PHẢI BỔ SUNG/CẬP NHẬT NGAY THÔNG TIN THƯ VIỆN ĐÓ VÀO FILE `requirements.txt`** của dự án để đảm bảo tính đồng bộ môi trường.

---

## 4. Quy Tắc Chuẩn Hóa Bản Vẽ Thiết Kế & An Toàn Kiến Trúc (Architecture Blueprints Standards)

1. **Chuẩn Mực Thiết Kế Quốc Tế**:
   - Mọi tài liệu thiết kế hệ thống (Blueprints / SDD) bắt buộc phải tuân theo các khung chuẩn mực: Arc42, IEEE Std 1016-2009, C4 Model, và O'Reilly Agentic Architectural Patterns.
   - Tài liệu phải thể hiện trạng thái mục tiêu thống nhất (Single Target Architecture), nghiêm cấm cách trình bày rời rạc theo dạng changelog / commit log / v1-v2.

2. **100% Sử Dụng Sơ Đồ Chuẩn Mermaid Hoặc Draw.io (Tuyệt Đối Cấm ASCII Art)**:
   - Toàn bộ sơ đồ kiến trúc, luồng xử lý, phân cấp, ERD bắt buộc phải được viết bằng mã Mermaid chuẩn (`flowchart TD`, `graph TD`, `sequenceDiagram`, `erDiagram`) hoặc xuất từ drawio.
   - Tuyệt đối không sử dụng ký tự vẽ hộp ASCII art trong các file markdown để tránh lỗi hiển thị và vỡ bố cục.

3. **Tính Khách Quan & Loại Bỏ Hoàn Toàn Ngôn Từ Quảng Cáo**:
   - Nghiêm cấm sử dụng các từ ngữ phóng đại, cảm tính như "100% chính xác", "đột phá", "siêu việt", "hoàn hảo".
   - Mọi đánh giá chất lượng phải được định lượng bằng chỉ số kỹ thuật: Execution Accuracy (EX), Valid SQL Rate (VA), và Error Budget.

4. **Bảo Toàn Toàn Vẹn Tài Liệu (Strict No-Deletion Rule)**:
   - Tuyệt đối không tự ý xóa, đổi tên hoặc gộp bỏ bất kỳ file tài liệu `.md` nào trong thư mục thiết kế nếu chưa có sự đồng ý rõ ràng của người dùng.

5. **Đối Chiếu Dữ Liệu Thực Tế CSDL PostgreSQL (Grounded Truth)**:
   - Mọi giả định về schema, tên bảng, kiểu dữ liệu, quan hệ khóa ngoại bắt buộc phải được kiểm chứng bằng truy vấn trực tiếp trên Docker CSDL `vna_wom_dev` trước khi đưa vào tài liệu.

6. **Cưỡng Chế Phân Quyền Tất Định Tầng AST (Deterministic Guardrails)**:
   - Phân quyền phân cấp HBAC và bộ lọc trạng thái bắt buộc phải được tiêm tự động ở tầng AST (SQLGlot), tuyệt đối không để LLM tự quyết định việc áp dụng phân quyền.

---

## 5. Nguyên Tắc Ưu Tiên Tuyệt Đối Tính Chính Xác & Độ Linh Hoạt Nghiệp Vụ Trong Giai Đoạn MVP (Accuracy & Functional Flexibility First - Zero SLA Constraints)

1. **Xóa Bỏ Hoàn Toàn Ràng Buộc SLA & Độ Trễ Trong Giai Đoạn MVP**:
   - **Tuyệt đối không áp đặt bất kỳ ngưỡng thời gian (SLA), micro-SLAs hay cam kết độ trễ nào** làm điều kiện nghiệm thu, cổng chặn (acceptance gates) hay tiêu chí đánh giá cho hệ thống hoặc từng module riêng lẻ.
   - Giai đoạn MVP tập trung tối đa nguồn lực vào **tính chính xác, tính đầy đủ và khả năng xử lý linh hoạt mọi yêu cầu phức tạp** của người dùng cuối. Hệ thống được toàn quyền sử dụng thời gian cần thiết (Multi-step DAG, CoT reasoning, self-correction, LLM calls) để đảm bảo sinh câu trả lời và câu lệnh SQL chuẩn xác nhất.
   - Toàn bộ nguồn lực kiểm thử và thiết kế phải tập trung cho **Tính Hợp Lệ Cú Pháp (Valid SQL Rate $\ge 98\%$)**, **Độ Chính Xác Thực Thi (Execution Accuracy $\ge 85 - 90\%$)** và **Bảo Mật Phân Quyền Tuyệt Đối (Security Violation Rate = 0.0%)**.
   - *Lưu ý về An toàn Hạ tầng:* Chỉ duy trì các ngưỡng Timeout kỹ thuật phòng vệ (ví dụ: Timeout kết nối CSDL, Timeout gọi API mạng) nhằm ngăn chặn bế tắc tiến trình (Deadlock / Resource Exhaustion) hoặc vòng lặp vô tận, tuyệt đối không dùng làm chỉ số SLA đo lường hiệu năng.

2. **Chống Ảo Tưởng "Đúng 100% Mọi Trường Hợp" (The 100% Accuracy Fallacy)**:
   - Nghiêm cấm đặt ra mục tiêu cảm tính "100% tất cả các case có thể xảy ra", bởi vì trong Xử lý Ngôn ngữ Tự nhiên (NLP) và Cơ sở Dữ liệu Thực tế luôn tồn tại sự bất đối xứng thông tin và nhập nhằng ngữ nghĩa (Semantic Ambiguity).
   - Thay vào đó, hệ thống bắt buộc phải quản trị bằng:
     - **Mục tiêu thực nghiệm cao nhất có thể:** $\text{VA} \ge 98\%$, $\text{EX} \ge 85 - 90\%$.
     - **Ngân sách lỗi (Error Budget $\le 15\%$):** Dành cho các câu hỏi thiếu ngữ cảnh hoặc vượt phạm vi dữ liệu.
     - **Cơ chế Hội thoại Làm rõ Chủ động (Active Clarification Chips):** Khi câu hỏi mơ hồ, hệ thống chủ động hỏi lại thay vì suy đoán gây ảo giác (Hallucination).
     - **Cơ chế Phục Hồi Suy Thoái An Toàn (Graceful Fallback):** Tuyệt đối không để xảy ra lỗi 500 khi gặp câu hỏi bất thường.

---

## 6. Nguyên Tắc Chống Anti-Pattern Heuristic, Cấm Rò Rỉ Kiểm Thử & Điều Phối Hướng Ngữ Nghĩa

1. **Cấm Sử Dụng Anti-Pattern So Khớp Chuỗi / Từ Khóa Cứng (No Regex/Keyword Shortcuts)**:
   - **Tuyệt đối không** dùng `if-else` từ khóa tĩnh hoặc so khớp chuỗi (`regex`) để phân loại ý định (ví dụ: xác định intent ở `mod03`), chọn bảng dữ liệu, trích xuất thực thể, hay ép câu trả lời theo mẫu (hardcoded template).
   - Không ép buộc cố định một thuật toán cụ thể trong rule; hệ thống phải xử lý qua tầng ngữ nghĩa/mô hình tổng quát có ngưỡng tin cậy rõ ràng (phân biệt khớp chắc chắn, mơ hồ cần làm rõ, và ngoài phạm vi).

2. **Cấm Rò Rỉ Dữ Liệu Kiểm Thử & Blind Mocking (No Test Leakage & Live DB Verification)**:
   - **Cấm Test Leakage:** Không đưa câu hỏi hoặc dữ liệu cụ thể từ tập Golden Test Cases vào Prompt hay code logic.
   - **Kiểm thử thực thi thực tế:** Đánh giá kết quả sinh SQL bằng cách thực thi trực tiếp trên CSDL thực tế và kiểm tra tính bất biến hành vi (thay đổi tên thực thể, đảo cấu trúc câu hoặc thêm điều kiện lọc vẫn giữ đúng logic), tuyệt đối không chỉ so khớp chuỗi SQL tĩnh (`assert sql == "..."`).

---

## 7. Tiêu Chuẩn Thiết Kế & Đánh Giá Test Suite Text-to-SQL Toàn Diện

> [!NOTE]
> Toàn bộ quy chuẩn chi tiết về thiết kế test case, phân loại 5 nhóm câu hỏi MMSQL, 3 tầng nhiễu Dr.Spider, tiêu chuẩn FLEX Execution Accuracy, và phân quyền HBAC đã được tách riêng sang tệp quy tắc chuyên biệt:
> 📄 [test_case_rule.md](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/.agents/rules/test_case_rule.md).
> Mọi thành viên và Agent bắt buộc phải tuân thủ nghiêm ngặt các điều khoản trong tệp trên khi thiết kế hoặc đánh giá bất kỳ ca kiểm thử nào.

---

## 8. Quy Tắc Bắt Buộc Cập Nhật Các Tài Liệu Liên Quan Khi Cải Tiến Hệ Thống

1. **Đồng Bộ Tài Liệu Liên Quan Theo Phạm Vi Thay Đổi**:
   - Mỗi khi cải tiến, tái cấu trúc, hoặc phát triển tính năng mới cho bất kỳ module nào trong hệ thống, Agent và lập trình viên **BẮT BUỘC PHẢI CẬP NHẬT CÁC TÀI LIỆU LIÊN QUAN** (như hướng dẫn vận hành, tài liệu đặc tả module, danh mục câu hỏi kiểm thử mẫu, kết quả kỳ vọng và hướng dẫn kiểm thử trên UI).
   - Bất kỳ nhiệm vụ nâng cấp module nào cũng bị coi là **CHƯA HOÀN THÀNH** nếu chưa đồng bộ các tài liệu liên quan và kiểm chứng thực tế.

---