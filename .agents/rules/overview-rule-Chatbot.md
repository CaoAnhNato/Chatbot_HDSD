---
trigger: always_on
description: Mandatory rules for deep technical research, web search with detailed reading, NotebookLM solution exploration with trade-off analysis, ArXiv paper research via ArXiv MCP for bottleneck analysis, official framework documentation verification, software architecture principles, strict venv/uv environment execution, and anti-patching standards.
---

# MANDATORY WORKSPACE RULES FOR TECH STACK, ENVIRONMENT EXECUTION & REQUIREMENTS

> [!IMPORTANT]
> **CÁC QUY TẮC THỰC THI BẮT BUỘC TRONG WORKSPACE DỰ ÁN**

---

## 1. Quy Tắc Bắt Buộc Web Search & Đọc Chi Tiết Nội Dung Khi Nghiên Cứu, Cải Tiến & Debugging

1. **Bắt Buộc Tìm Kiếm & Đọc Chi Tiết (Deep Web Reading)**:
   - Khi người dùng đặt vấn đề, yêu cầu cải tiến hệ thống, hoặc khi Agent gặp lỗi (bug) trong quá trình phát triển/debug:
     - **Không dừng lại ở thông tin tóm tắt / snippet overview** từ kết quả tìm kiếm thông thường.
     - **Bắt buộc sử dụng các công cụ chuyên sâu như `fetch`, `firecrawl`...** để truy cập và đọc toàn bộ nội dung chi tiết của từng bài viết (Technical Blogs, Stack Overflow questions & accepted/top answers/comments, GitHub Issues/Discussions, diễn đàn kỹ thuật uy tín).
     - Phân tích kỹ bối cảnh xảy ra lỗi, cơ chế hoạt động thực tế và các giải pháp đã được cộng đồng xác minh trước khi áp dụng.

2. **Tư Vấn & Đề Xuất Kỹ Thuật Up-to-Date**:
   - Khi đề xuất công nghệ, model, thư viện, framework hay kiến trúc SOTA:
     - Bắt buộc gọi tool tìm kiếm trước để cập nhật tài liệu mới nhất.
     - Phân biệt rõ ràng giữa bản phát hành chính thức (Official Releases/Stable) và các bản thử nghiệm/bài báo cộng đồng.

---

## 2. Quy Tắc Tra Cứu Giải Pháp Qua NotebookLM MCP & Đọc Tài Liệu Gốc (Root Source & Trade-off Analysis)

1. **Tra Cứu Giải Pháp Qua NotebookLM MCP**:
   - Khi cần xác định giải pháp, phương pháp tiếp cận hoặc kiến trúc tối ưu cho bài toán của hệ thống, Agent **bắt buộc sử dụng `notebooklm` MCP tool** để rà soát kho tài liệu nghiên cứu và tri thức chuyên ngành đã lưu trữ.

2. **Đọc Chi Tiết Tài Liệu Gốc & Phân Tích Đa Chiều (In-Depth Source Analysis)**:
   - Khi xác định được nguồn tài liệu chứa giải pháp, Agent **bắt buộc đọc trực tiếp và chi tiết tài liệu gốc của source đó** để nắm vững:
     - **Cách triển khai thực tế**: Hiểu rõ từng bước cài đặt, thuật toán và luồng vận hành theo đúng thiết kế tác giả đề ra.
     - **Điều kiện phát huy hiệu quả (Boundary/Operational Conditions)**: Xác định rõ giải pháp này tối ưu trong hoàn cảnh nào (ví dụ: kích thước dữ liệu, độ trễ cho phép, môi trường tài nguyên, ràng buộc phần cứng).
     - **Phân tích Đánh Đổi (Trade-offs)**: Bắt buộc chỉ rõ và cân nhắc các mặt được/mất khi áp dụng giải pháp (độ trễ xử lý vs. độ chính xác, tài nguyên bộ nhớ/CPU/GPU vs. tốc độ phản hồi, độ phức tạp của code vs. khả năng bảo trì và mở rộng).

---

## 3. Quy Tắc Tra Cứu & Nghiên Cứu Paper Khoa Học Qua ArXiv MCP Khi Phân Tích Bottleneck & Đề Xuất Giải Pháp

1. **Bắt Buộc Tra Cứu Bài Báo Khoa Học (Academic Papers) Qua ArXiv MCP Tool**:
   - Khi người dùng yêu cầu **phân tích điểm nghẽn (bottleneck)** của hệ thống (ví dụ: độ trễ/latency, throughput, suy giảm độ chính xác precision/recall, hiện tượng hallucination trong RAG, nghẽn pipeline, memory footprint, cold-start...):
     - Agent **BẮT BUỘC SỬ DỤNG MCP TOOL `arxiv`** (như `search_papers`, `download_paper`, `read_paper`, `get_abstract`,...) để tìm kiếm các bài báo khoa học, preprint và nghiên cứu mới nhất/uy tín liên quan trực tiếp đến vấn đề bottleneck đang gặp.

2. **Nghiên Cứu Sâu & Đề Xuất Giải Pháp Dựa Trên Paper (Paper-Grounded Solutions)**:
   - Đọc, phân tích và trích xuất phương pháp, thuật toán, kỹ thuật hoặc kiến trúc đã được chứng minh hiệu quả thực nghiệm trong các paper tìm được.
   - Khi đề xuất giải pháp kỹ thuật giải quyết bottleneck cho người dùng:
     - **Bắt buộc dẫn chứng rõ ràng**: Nêu tên paper, tác giả, ArXiv ID/Link.
     - **Giải trình cơ sở khoa học**: Trình bày rõ cơ chế/thuật toán của paper giúp giải quyết bottleneck như thế nào.
     - **Đánh giá tính khả thi & Đánh đổi**: Phân tích sự phù hợp khi đưa giải pháp từ paper vào bối cảnh kiến trúc thực tế của hệ thống dự án.

---

## 4. Quy Tắc Tra Cứu Official Documentation & Chuẩn Mực Kiến Trúc Hệ Thống (Architecture & Anti-Patching Standards)

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

## 5. Quy Tắc Môi Trường Python (`venv`), Công Cụ `uv` & Quản Lý Phụ Thuộc (`requirements.txt`)

1. **Chỉ Thực Thi Code & Quản Lý Package Trên Môi Trường `venv`**:
   - Mọi thao tác thực thi code Python, chạy script, kiểm thử, hoặc quản lý gói (thêm mới `install`, cập nhật `update`, gỡ bỏ `uninstall` package/library) **CHỈ ĐƯỢC PHÉP THỰC THI QUA MÔI TRƯỜNG `venv`** (đường dẫn: `.\venv\Scripts\python.exe` hoặc `venv\Scripts\pip`).
   - Nghiêm cấm chạy code hoặc cài đặt thư viện vào Python hệ thống toàn cục (Global Python) ngoài `venv`.

2. **Ưu Tiên Tải & Cài Đặt Package Bằng `uv` Để Đạt Tốc Độ Tối Đa**:
   - Bất kỳ khi nào thực hiện cài đặt hoặc cập nhật package/thư viện Python, Agent **BẮT BUỘC ƯU TIÊN SỬ DỤNG LỆNH `uv`** (ví dụ: `uv pip install --python .\venv\Scripts\python.exe <package>` hoặc `uv pip install ...` chỉ định môi trường `venv`) để tối ưu hóa tốc độ tải và cài đặt ở mức cao nhất.

3. **Cập Nhật Tự Động `requirements.txt` Khi Thay Đổi Thư Viện**:
   - Bất kỳ khi nào thực hiện cài đặt (`install`) hoặc cập nhật (`update`) bất kỳ package/thư viện Python nào vào môi trường `venv`, Agent **BẮT BUỘC PHẢI BỔ SUNG/CẬP NHẬT NGAY THÔNG TIN THƯ VIỆN ĐÓ VÀO FILE `requirements.txt`** của dự án để đảm bảo tính đồng bộ môi trường.

---

## 6. Quy Tắc Phản Hồi Câu Hỏi (TUYỆT ĐỐI Không Tự Ý Sửa Codebase)

1. **Chỉ Đọc/Tra Cứu/Tổng Hợp Thông Tin Khi Trả Lời Câu Hỏi**:
   - Khi người dùng đưa ra câu hỏi mang tính chất tìm hiểu, thắc mắc, hỏi đáp kỹ thuật, giải thích logic hoặc tra cứu thông tin, Agent **CHỈ ĐƯỢC PHÉP** thực hiện các thao tác đọc tệp, tìm kiếm thông tin và tổng hợp nội dung để trả lời.
2. **TUYỆT ĐỐI Không Tự Ý Chỉnh Sửa Codebase**:
   - Nghiêm cấm tự ý thực hiện bất kỳ chỉnh sửa mã nguồn nào (sửa đổi file, tạo file mới, xóa file, chạy kiểm thử tự động sửa đổi) dưới mọi hình thức khi phản hồi câu hỏi.
   - Mọi thay đổi đối với codebase chỉ được phép thực hiện khi người dùng đưa ra yêu cầu sửa đổi, lập trình, hoặc triển khai tính năng mới một cách trực tiếp và rõ ràng.

---