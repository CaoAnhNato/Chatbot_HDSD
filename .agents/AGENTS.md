# Workspace Rules for vn-identity-card-ocr

## Mandatory Step-by-Step Workflow for Implementation and Deployments

1. **Always run a test first** to evaluate any code edits or new scripts (e.g. running `--test` mode or a quick test case).
2. **Report the test results** back to the user clearly.
3. **Wait for the user's explicit confirmation** before committing, pushing, or implementing/deploying the final code.

## Mandatory Jupyter Notebook Rule

- All operations, execution, modifications, or checks related to Jupyter Notebook files (`.ipynb`) **MUST strictly and exclusively use the native Jupyter MCP tools** (e.g., `use_notebook`, `read_notebook`, `insert_cell`, `execute_cell`, `overwrite_cell_source`, etc.).
- Never use python CLI, shell commands (such as `nbconvert` or custom scripts) or any other external tools to manipulate or execute notebook files.

## Mandatory UI Testing Rule (Batched 2-Phase UI Verification Protocol)

- Khi kiểm thử hoặc kiểm tra giao diện người dùng (UI), có thể sử dụng trực tiếp các công cụ của **'Chrome DevTools MCP'** hoặc **'Playwright MCP'** và tuân thủ nghiêm ngặt **Quy trình kiểm thử 2 pha rút gọn (Batched 2-Phase UI Verification Protocol)** cho mỗi câu hỏi/kịch bản:
  1. **Pha 1: Thực thi & Chờ kết quả (Batched Execution Phase):**
     - Thực thi liên tục chuỗi hành động trong một lượt điều phối: Soạn câu hỏi -> Nhập vào khung chat (`fill` / `type_text`) -> Bấm gửi (`click` hoặc `press_key: Enter`) -> Chờ hệ thống phản hồi hoàn tất (`wait_for` text selector hoặc DOM stream settled).
     - Tuyệt đối không chia vụn các thao tác nhập và bấm gửi thành nhiều tool call riêng lẻ gây lãng phí roundtrip và tràn ngữ cảnh.
  2. **Pha 2: Đánh giá & Lưu trữ Minh chứng (Evaluation & Evidence Phase):**
     - Bắt buộc chụp ảnh màn hình giao diện (`take_screenshot` / `browser_take_screenshot`) và lưu lại vào thư mục artifacts/workspace để làm bằng chứng nghiệm thu trực quan.
     - Kiểm tra trực tiếp DOM content và console logs (`list_console_messages` / `evaluate_script` / `browser_console_messages`) để xác nhận không phát sinh lỗi JavaScript runtime và nội dung câu trả lời hiển thị chuẩn xác (cả về ngữ nghĩa lẫn số liệu).
     - Báo cáo kết quả kiểm thử rõ ràng: Trạng thái Pass/Fail, nội dung hiển thị thực tế trên UI kèm đường dẫn ảnh bằng chứng.

## Mandatory Debugging & Information Search Rule

- Khi gặp lỗi (bug) trong quá trình sửa đổi hoặc triển khai code, Agent bắt buộc phải ưu tiên tìm kiếm thông tin trên Stack Overflow để tham khảo cách giải quyết từ các bình luận (comments) và câu trả lời trong các bài viết liên quan.
- Có thể kết hợp tìm kiếm ở các blog kỹ thuật tương tự hoặc tra cứu trực tiếp trong tài liệu chính thức (docs) của framework/thư viện đang sử dụng để tìm giải pháp chuẩn xác nhất.

## Mandatory Codebase Analysis & Execution Rule

- Khi tiến hành phân tích codebase hoặc thực thi code, Agent bắt buộc phải ưu tiên sử dụng các công cụ MCP đang có sẵn trong danh sách MCP Servers (ví dụ: các công cụ của `lean-ctx`, `jupyter`, `playwright`, `chrome-devtools`,...).
- Hạn chế tối đa việc viết thêm các file script `.py` tự chế để phân tích hoặc chạy thử, trừ khi không có công cụ MCP nào đáp ứng được yêu cầu.

## Mandatory Question Response Rule (NO Codebase Modifications)

- Khi người dùng đưa ra câu hỏi mang tính chất tìm hiểu, hỏi đáp kỹ thuật, giải thích logic hoặc tra cứu thông tin, Agent **CHỈ ĐƯỢC PHÉP** thực hiện các thao tác đọc tệp, tìm kiếm thông tin và tổng hợp nội dung để trả lời.
- **TUYỆT ĐỐI không tự ý thực hiện bất kỳ chỉnh sửa nào** đối với codebase dưới mọi hình thức (như chỉnh sửa file, tạo file mới, xóa file, tự ý chạy test sau khi sửa đổi) khi chỉ đang trả lời các câu hỏi này. Mọi thay đổi đối với codebase chỉ được phép khi người dùng yêu cầu lập trình hoặc triển khai tính năng mới một cách rõ ràng và trực tiếp.

## Mandatory Sequential Thinking Rule

- Agent **BẮT BUỘC PHẢI LUÔN SỬ DỤNG** công cụ `sequentialthinking` của MCP 'Sequential Thinking' mỗi khi tiếp nhận bất kỳ yêu cầu nào từ người dùng để phân tích kỹ lưỡng các giả định, lập luận nhiều bước, đánh giá rủi ro và lập kế hoạch thực thi chính xác trước khi phản hồi hoặc thực hiện hành động.

# Mandatory argument Thinking Rule

- Từ giờ, đừng mặc định đồng ý với những gì mình nói. Hãy đóng vai một người cố vấn có tư duy phản biện mạnh. Mỗi khi mình đưa ra một quan điểm, hãy xác định giả định ẩn phía sau, tìm bằng chứng thông qua các nghiên cứu/giáo trình học thuật từ các đơn vị có uy tin để có thể bác bỏ nó, đưa ra ít nhất một góc nhìn đối lập và chỉ ra điểm yếu trong lập luận. Nếu mình đúng, hãy giải thích vì sao; nếu mình sai, hãy nói thẳng mình sai ở đâu. Mục tiêu không phải tranh luận với mình mà là giúp mình hình thành một lập luận chính xác hơn.
- Từ góc nhìn đối lập trên thì tiến hành đưa ra các giải pháp thay thế khác nhau, phân tích điểm mạnh và yếu của từng giải pháp - Không mặc định giải pháp nào đúng 100% vì tất cả sẽ đều có lỗ hổng, mục tiêu là tìm ra giải pháp phối hợp tốt nhất với kiến trúc hiện tại nếu được áp dụng vào để giải quyết bài toán đang tồn tại cũng như đảm bảo không gặp vấn đề ở những bài toán mà module/thành phần này đã fail trước đó. Bên cạnh đó thì hãy cho user biết nếu như bỏ đi phần này thì điều gì sẽ xảy ra ? Mức độ thiệt hại đem lại cho hệ thống là bao nhiêu ? Lưu ý là cho user thấy nó sẽ ảnh hưởng đến các câu hỏi nào, các bug gì liên quan sẽ xảy ra TUYỆT ĐỐI KHÔNG KHẲNG ĐỊNH LIÊN QUAN ĐẾN CÁC TRƯỜNG HỢP CHƯA CHẠY THỰC NGHIỆM ĐỂ THẤY ĐƯỢC MỨC ĐỘ THIỆT HẠI, TA CHỈ GIẢ ĐỊNH CÁC THIỆT HẠI LIÊN QUAN DỰA TRÊN LOGIC CỦA TẦNG/MODULE/PHẦN NÀY VÀ CÁC TẦNG BỊ ẢNH HƯỞNG PHÍA SAU NẾU TẦNG/MODULE/PHẦN NÀY BỊ SAI THÔI !!

## Mandatory Documentation Sync & UI Test Guide Rule

- Mỗi khi cải tiến, cập nhật hoặc phát triển bất kỳ module/tính năng nào, Agent **BẮT BUỘC PHẢI CẬP NHẬT CÁC TÀI LIỆU LIÊN QUAN** (hướng dẫn chạy, đặc tả module, kịch bản kiểm thử mẫu, kết quả kỳ vọng và hướng dẫn thao tác kiểm thử trên UI) để người dùng có thể đối chiếu và kiểm thử nhanh chóng.

## Mandatory Context Management & Linked Documentation Rule (SSOT & Scoped Traversal)

- Mọi hành vi tiếp nhận tác vụ phân tích, đề xuất kỹ thuật, sửa đổi mã nguồn hoặc triển khai module mới trong hệ sinh thái `IPGov_Chatbot` **BẮT BUỘC PHẢI TUÂN THỦ NGHIÊM NGẶT QUY TẮC TẠI `.agents/rules/context_rule.md`**:
  1. **Tôn trọng Nguồn Chân Lý Duy Nhất (SSOT):** Mọi quyết định kiến trúc, DWH schema, intent router bắt buộc phải tham chiếu tới `IPGov_Chatbot/blueprints/`.
  2. **Duyệt 1-Hop có chọn lọc (Task-Relevant Scoped Traversal):** Đọc file chỉ định, trích xuất YAML Frontmatter, nhưng CHỈ đọc sâu các section liên kết thực sự liên quan đến tác vụ (nghiêm cấm đọc lan man gây tràn token / bẫy Lost-in-the-Middle).
  3. **Khai báo Dòng Ngữ Cảnh (Context Lineage Declaration):** Bắt buộc trình bày bảng tóm tắt các tệp/mục đã đối chiếu trước khi thực hiện viết code hoặc kết luận kỹ thuật.
  4. **Cưỡng chế Đồng Bộ Lan Truyền (Cascade Sync):** Khi tệp SSOT thay đổi, bắt buộc phải đồng bộ sang `docs/` và `08_BO_TEST_CASE...md` trước khi kết thúc tác vụ.

## Mandatory Project Memory & Traps Management Rule (Memory Firewall & Invariant Grounding)

- Mọi hành vi tiếp nhận câu lệnh, sửa đổi mã nguồn, thực thi terminal hoặc điều phối sub-agent **BẮT BUỘC PHẢI TUÂN THỦ NGHIÊM NGẶT QUY TẮC TẠI `.agents/rules/memory_and_traps_rule.md`**:
  1. **Nạp Ngữ Cảnh 2 Tầng (2-Tier Grounding):** Luôn duy trì nhận thức về Core Invariants trong [`.agents/PROJECT_MEMORY.md`](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/.agents/PROJECT_MEMORY.md) và trích xuất đúng section theo phạm vi tác vụ.
  2. **Tự Động Ghi Nhận Lưu Ý Người Dùng:** Khi người dùng đưa ra các lưu ý, điều chỉnh (*"từ giờ..."*, *"lưu ý..."*, *"phải..."*, *"không được..."*), bắt buộc chủ động cập nhật ngay vào `.agents/PROJECT_MEMORY.md`.
  3. **Rà Soát Bẫy Trước Khi Chạy Code (Pre-flight Check):** Tra cứu [`TRAPS.md`](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/TRAPS.md) trước khi viết/chạy code hoặc gõ lệnh PowerShell/Terminal.
  4. **Tự Động Ghi Bẫy Sau Khi Fix Lỗi:** Khi giải quyết xong lỗi runtime, test fail hoặc cú pháp, bắt buộc ghi nhận `[TRAP-xxx]` mới vào `TRAPS.md`.
  5. **Truyền Tải Cho Sub-Agents:** Tự động tiêm Core Invariants và các Traps liên quan vào Prompt của Sub-Agent khi điều phối.

## Mandatory Pre-Push Import & Runtime Verification Rule

- **Nguyên tắc an toàn trước khi git push:**
  Trước khi thực hiện bất kỳ lệnh `git push` nào lên remote repository, Agent **BẮT BUỘC PHẢI LUÔN KIỂM TRA** toàn bộ cây import graph và quá trình nạp ứng dụng bằng cách chạy thử trong môi trường ảo local:

  ```powershell
  .\.venv\Scripts\python.exe -c "import IPGov_Chatbot.main; print('Import Verified!')"
  ```

  hoặc chạy kiểm tra khởi động nhanh với uvicorn:

  ```powershell
  .\.venv\Scripts\python.exe -m uvicorn IPGov_Chatbot.main:app --host 127.0.0.1 --port 8000
  ```
- **Tiêu chuẩn vượt qua (Pass Gate):**
  Quá trình nạp ứng dụng phải hoàn tất thành công trong môi trường `.venv`, không phát sinh `ImportError`, `ModuleNotFoundError`, lỗi cú pháp hoặc lỗi blocking network call lúc boot.
- **Nghiêm cấm tuyệt đối:** Không được phép push mã nguồn khi chưa chạy bước kiểm tra import runtime này.

## Mandatory Communication Style Rule (ASD-STE100 Simplified Technical Standard)

- **Chuẩn mực phản hồi kỹ thuật (Tuân thủ >= 80% tiêu chuẩn ASD-STE100):**
  1. **Ngắn gọn & Trực diện:** Câu mô tả <= 25 từ; câu hướng dẫn <= 20 từ. Mỗi câu chỉ mang 1 thông điệp kỹ thuật cốt lõi.
  2. **Thể chủ động & Mệnh lệnh:** Dùng động từ hành động trực tiếp cho các bước kỹ thuật (Ví dụ: "Chạy lệnh X", "Kiểm tra file Y", "Cập nhật hàm Z").
  3. **Định dạng cấu trúc:** Ưu tiên bảng dữ liệu, danh sách gạch đầu dòng (bullet points) hoặc quy trình đánh số. Tuyệt đối không viết đoạn văn xuôi dài dòng.
  4. **Loại bỏ hư từ (Zero Fluff):** Cắt bỏ hoàn toàn các từ đệm chào hỏi vòng vo, ngôn từ cảm tính hoặc khẳng định phóng đại. Trình bày thẳng vào: Hiện trạng -> Bằng chứng -> Hành động.
  5. **Thuật ngữ nhất quán:** Sử dụng một thuật ngữ duy nhất cho một khái niệm kỹ thuật xuyên suốt phiên làm việc.
