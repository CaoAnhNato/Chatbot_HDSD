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

## 7. Quy Tắc Chuẩn Hóa Bản Vẽ Thiết Kế & An Toàn Kiến Trúc (Architecture Blueprints Standards)

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

## 8. Nguyên Tắc Ưu Tiên Tuyệt Đối Tính Chính Xác & Độ Linh Hoạt Nghiệp Vụ Trong Giai Đoạn MVP (Accuracy & Functional Flexibility First - Zero SLA Constraints)

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

## 9. Nguyên Tắc Chống Khớp Quá Mức Heuristic & Rò Rỉ Kiểm Thử (Anti-Heuristic Overfitting & Test Leakage Standards)

Để đảm bảo hệ thống có năng lực tổng quát hóa cao trong môi trường hành chính công vụ thực tế, loại bỏ hoàn toàn hiện tượng "Pass 100% test nhưng sập khi người dùng hỏi thật", mọi thành viên phát triển và Agent bắt buộc phải tuân thủ nghiêm ngặt 5 điều khoản cưỡng chế sau:

1. **Nghiêm Cấm Tuyệt Đối Phân Nhánh Bằng Từ Khóa Cứng (Strict Anti-Shortcut Rule)**:
   - **Tuyệt đối cấm** viết các câu lệnh điều kiện phân nhánh `if-else` hoặc Regex dựa trên từ khóa tĩnh của các câu hỏi mẫu trong test case (như hardcode tên đơn vị `"Phòng Kinh tế"`, `"Sở Xây dựng"`, tên chỉ tiêu `"khuyến công"`, hoặc năm `"2025"` vào logic code cốt lõi).
   - Mọi thao tác trích xuất và định tuyến bắt buộc phải đi qua **Tầng Ngữ Nghĩa Tổng Quát (General Semantic Layer)** thiết kế theo mẫu **Strategy Pattern**:
     * *Hợp đồng giao diện (Interface Contract):* Bắt buộc có cơ chế chấm điểm tương đồng định lượng và ngưỡng tin cậy (`score_cutoff` / `confidence_threshold`) để phân tách rõ ràng giữa: Khớp chắc chắn (Confident Match), Cần làm rõ (Ambiguous $\to$ Active Clarification), và Ngoài phạm vi (Out-of-Scope). Tuyệt đối không dựa vào so khớp chuỗi thô hay hardcode từ khóa.
     * *Chiến lược Khởi tạo (Default Baseline cho MVP):* Tra cứu thực thể qua DuckDB In-Memory Catalog bằng thuật toán BM25 kết hợp so khớp mờ Levenshtein (`RapidFuzz`) có `score_cutoff` nhằm đảm bảo tính gọn nhẹ, vận hành thuần trong bộ nhớ mà không phụ thuộc tài nguyên phần cứng lớn.
     * *Khả năng Mở rộng Thực nghiệm (Pluggable Semantic Strategies):* Cho phép và khuyến khích nâng cấp, thay thế hoặc kết hợp với các chiến lược tiên tiến hơn dựa trên kết quả đo lường thực nghiệm (như Dense Embeddings, Hybrid Retrieval RRF, Cross-Encoder Reranking, hoặc Knowledge Graph) miễn là thỏa mãn Hợp đồng giao diện.
   - Cấu trúc DTO trung gian phải sử dụng các kiểu dữ liệu trừu tượng (`UUID`, `department_code`, `metric_id`), tuyệt đối không dựa vào chuỗi văn bản tự do chưa qua chuẩn hóa.

2. **Cách Ly Tuyệt Đối Giữa Tập Kiểm Thử & Mã Nguồn (Hold-out Test Set Isolation)**:
   - **Cấm Test Leakage:** Tuyệt đối không được sao chép câu hỏi, dữ liệu hoặc cấu trúc của tập Golden Test Cases vào làm Few-Shot Prompt, System Prompt của Router hoặc bộ sinh SQL.
   - Few-Shot Prompts chỉ được phép sử dụng các **Khuôn Mẫu Tiêu Biểu Trừu Tượng (Canonical Prototypes)** được thiết kế độc lập, minh họa cấu trúc ngữ pháp thay vì chứa đựng dữ liệu thực tế của các ca kiểm thử nghiệm thu.

3. **Cưỡng Chế Kiểm Thử Hành Vi Bền Vững (CheckList Invariance & Directional Testing - ACL 2020)**:
   Mọi chức năng phân tích ngôn ngữ (Router, Guardrail, Intent Classifier) khi được đưa vào bộ kiểm thử phải thỏa mãn các nguyên lý kiểm thử hành vi:
   - **Kiểm thử Bất biến (Invariance Test - INV):**
     * *Hoán vị thực thể (Entity Swapping):* Thay thế tên phòng ban A bằng phòng ban B, năm X bằng năm Y trong câu hỏi $\to$ Luồng định tuyến (`intent`) và cấu trúc AST của câu lệnh SQL bắt buộc phải giữ nguyên không đổi.
     * *Hoán vị cấu trúc câu (Syntactic Paraphrasing):* Thêm từ đệm công vụ (*"Kính gửi chatbot"*, *"Vui lòng cho tôi biết"*, *"Hãy thống kê giúp"*), đảo ngữ $\to$ Không được làm sai lệch Intent hay rơi vào Out-of-Scope.
     * *Khả năng chịu lỗi gõ (Robustness to Noise):* Viết hoa, viết thường, hoặc lỗi khoảng trắng không được làm gãy quá trình trích xuất Slot.
   - **Kiểm thử Kỳ vọng Đổi hướng (Directional Expectation Test - DIR):**
     * Khi câu hỏi bổ sung thêm điều kiện lọc (ví dụ: *"và chỉ lấy số liệu đã duyệt năm 2025"*), câu lệnh SQL sinh ra bắt buộc phải được bổ sung mệnh đề `AND` tương ứng, không được giữ nguyên kết quả cũ.

4. **Bắt Buộc Đánh Giá Trên Tập Phân Phối Mở Rộng (Out-of-Distribution - OOD Testing)**:
   - Trong bộ kiểm thử tổng thể, bắt buộc duy trì tối thiểu **$15\%$ các Test Cases thuộc nhóm Out-of-Distribution**: Bao gồm các chỉ tiêu ít gặp, các đơn vị hành chính cấp xã/phường mới hoặc dữ liệu giả định hợp lệ chưa từng xuất hiện trong quá trình code.
   - Hệ thống chỉ được xem là đạt chuẩn tổng quát khi vượt qua tập OOD này với độ chính xác tương đương tập In-Distribution.

5. **Kiểm Thử Bằng Thực Thi CSDL Thực Tế Thay Vì Blind Mocking (Live Database Assertion)**:
   - Đối với các module sinh và thực thi SQL (MOD-05, MOD-06, MOD-07): **Nghiêm cấm việc chỉ assert chuỗi ký tự tĩnh (`assert sql == "..."`)**.
   - Toàn bộ câu lệnh SQL được sinh ra bắt buộc phải được thực thi trực tiếp trên CSDL PostgreSQL Docker `vna_wom_dev`:
     * Xác nhận câu truy vấn chạy thành công trên PostgreSQL 16 (không văng cú pháp hoặc lỗi kiểu dữ liệu).
     * Xác nhận kết quả trả về (`QueryResultDTO`) có số dòng (`row_count`) và giá trị các chỉ tiêu khớp hoàn toàn với Ground Truth.

---

## 10. Nguyên Tắc Quản Trị Mô Hình & API Tập Trung (SSOT Model & Configuration Governance)

Để loại trừ triệt để tình trạng phân mảnh cấu hình (Configuration Drift), bùng nổ mô hình không kiểm soát (Model Proliferation) và bảo đảm an toàn bảo mật API keys, toàn bộ thành viên và Agent bắt buộc tuân thủ 4 điều khoản sau:

1. **Điểm Tụ Cấu Hình Duy Nhất (Single Source of Truth - SSOT)**:
   - Mọi định danh mô hình ngôn ngữ (LLM models), mô hình nhúng (Embedding models), API keys và các thông số kết nối dịch vụ ngoài (DWH PostgreSQL, Supabase, ChromaDB, Langfuse) bắt buộc phải được khai báo và quản lý tập trung tại `backend/config.py`.
   - File `IPGov_Chatbot/config.py` đóng vai trò là tầng Re-export/Adapter, nhập khẩu trực tiếp các thuộc tính từ `backend/config.py`. Tuyệt đối không tự ý khai báo độc lập các trường trùng lặp gây xung đột.

2. **Cưỡng Chế Thứ Tự Ưu Tiên Các Mô Hình Đã Cấu Hình Sẵn (Pre-configured Models First)**:
   Mọi module xử lý ngôn ngữ và suy luận trong hệ sinh thái `IPGov_Chatbot` bắt buộc phải ưu tiên lựa chọn các mô hình đã được định cấu hình sẵn trong `settings`:
   - **Tác vụ Định tuyến Ý định, Lập luận Nhanh & Tool Calling (Router & Reasoning):** Ưu tiên `gemini-2.5-flash` (`settings.GEMINI_MODEL_NAME`).
   - **Tác vụ Sinh SQL Cấu Trúc Phức Tạp (DIN-SQL / MAC-SQL Generator):** Ưu tiên `gpt-4o-mini` (`settings.OPENAI_MODEL_NAME`) hoặc `gemini-2.5-flash`.
   - **Tác vụ Trả lời Hỏi Đáp Tri Thức & Fallback Chitchat:** Ưu tiên `qwen3.7-flash` (`settings.QWEN_MODEL_NAME`).
   - **Tác vụ Nhúng Ngữ Nghĩa (Semantic Embedding):** Ưu tiên mô hình tiếng Việt chuyên dụng `AITeamVN/Vietnamese_Embedding_v2` (`settings.EMBEDDING_MODEL_NAME`).

3. **Kiểm Tra Tính Khả Dụng Thực Tế Trước Khi Thực Thi (Runtime API Availability Guard)**:
   - Trước khi khởi tạo client gọi LLM hoặc chuyển giao task, mã nguồn bắt buộc phải kiểm tra sự tồn tại của API Key hợp lệ thông qua `settings.effective_llm_api_key` hoặc danh sách `settings.allowed_llm_providers`.
   - Nếu API Key của nhà cung cấp chính chưa được cấp trong `.env`, hệ thống phải tự động fallback sang nhà cung cấp phụ có sẵn trong danh sách hoặc trả về thông báo graceful degradation, tuyệt đối không để crash ứng dụng với lỗi `AuthenticationError`.

4. **Giao Thức Đề Xuất Mô Hình Mới (Model Escalation Protocol)**:
   - Agent và lập trình viên **CHỈ ĐƯỢC PHÉP** đề xuất bổ sung thêm model/provider mới khi thỏa mãn một trong các điều kiện định lượng sau:
     * Model có sẵn không hỗ trợ tính năng kỹ thuật bắt buộc (ví dụ: thiếu Native Structured Output / JSON Schema mode, không hỗ trợ Context Caching dài hạn).
     * Thực nghiệm đo lường trên tập Golden Dataset chứng minh Execution Accuracy của model có sẵn thấp hơn ngưỡng chấp nhận (< 80%) và không thể cải thiện qua Prompt Engineering / In-Context Learning.
     * Vấn đề giới hạn cửa sổ ngữ cảnh (Context Window) hoặc chi phí token vượt quá ngân sách cho phép.
   - Mọi đề xuất model mới bắt buộc phải trình bày rõ: Tên model, cơ sở khoa học/benchmark, lý do model hiện có không đáp ứng được, ước tính chi phí token và phương án nạp API Key vào `backend/config.py`.

---

## 11. Tiêu Chuẩn Thiết Kế & Đánh Giá Test Suite Text-to-SQL Toàn Diện

> [!NOTE]
> Toàn bộ quy chuẩn chi tiết về thiết kế test case, phân loại 5 nhóm câu hỏi MMSQL, 3 tầng nhiễu Dr.Spider, tiêu chuẩn FLEX Execution Accuracy, và phân quyền HBAC đã được tách riêng sang tệp quy tắc chuyên biệt:
> 📄 [test_case_rule.md](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/.agents/rules/test_case_rule.md).
> Mọi thành viên và Agent bắt buộc phải tuân thủ nghiêm ngặt các điều khoản trong tệp trên khi thiết kế hoặc đánh giá bất kỳ ca kiểm thử nào.

---

## 12. Quy Tắc Bắt Buộc Cập Nhật Hướng Dẫn Kiểm Thử UI (UI Test Documentation & Verification Standard)

1. **Đồng Bộ Tài Liệu Hướng Dẫn Kiểm Thử UI Khi Cải Tiến Bất Kỳ Module Nào**:
   - Mỗi khi cải tiến, tái cấu trúc, hoặc phát triển tính năng mới cho bất kỳ module nào trong hệ thống (`mod01` đến `mod08`), Agent và lập trình viên **BẮT BUỘC PHẢI CẬP NHẬT NGAY** tệp tài liệu:
     `IPGov_Chatbot/docs/BACKEND_RUN_GUIDE.md`.

2. **Nội Dung Bắt Buộc Phải Bổ Sung Vào `BACKEND_RUN_GUIDE.md` Bao Gồm**:
   - **Danh mục câu hỏi kiểm thử mẫu (Test Prompts Showcase)**: Cung cấp ít nhất 3-5 câu hỏi điển hình phản ánh trực tiếp logic/tính năng mới vừa được nâng cấp (ví dụ: các câu hỏi Fast Track, Dynamic DAG, Clarification Chips, Chitchat Bypass...).
   - **Kết quả kỳ vọng trên giao diện (Expected UI Output)**: Mô tả rõ ràng thẻ trạng thái, route trả về, intent nhận diện và hành vi hiển thị của chatbot (chế độ người dùng vs chế độ debug).
   - **Hướng dẫn thao tác kiểm thử trực quan trên Web GUI**: Các bước click, chọn vai trò HBAC, bật/tắt chế độ debug và cách sử dụng nút báo lỗi & note (HITL Feedback).
   - **Lưu ý khởi động lại dịch vụ**: Nhắc nhở rõ ràng việc tắt tiến trình server cũ và khởi chạy lại máy chủ để nạp mã nguồn mới nhất.

3. **Cổng Kiểm Thử Nghiệm Thu (Acceptance Gate)**:
   - Bất kỳ PR hoặc nhiệm vụ hoàn thiện module nào cũng bị coi là **CHƯA HOÀN THÀNH** nếu chưa cập nhật phần kiểm thử UI tương ứng trong `BACKEND_RUN_GUIDE.md` và chưa kiểm chứng trực tiếp trên giao diện Test Bench `/bench`.

---