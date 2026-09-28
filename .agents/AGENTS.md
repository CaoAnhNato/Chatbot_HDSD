# Workspace Rules for vn-identity-card-ocr

## Mandatory Step-by-Step Workflow for Implementation and Deployments

1. **Always run a test first** to evaluate any code edits or new scripts (e.g. running `--test` mode or a quick test case).
2. **Report the test results** back to the user clearly.
3. **Wait for the user's explicit confirmation** before committing, pushing, or implementing/deploying the final code.

## Mandatory Jupyter Notebook Rule

- All operations, execution, modifications, or checks related to Jupyter Notebook files (`.ipynb`) **MUST strictly and exclusively use the native Jupyter MCP tools** (e.g., `use_notebook`, `read_notebook`, `insert_cell`, `execute_cell`, `overwrite_cell_source`, etc.).
- Never use python CLI, shell commands (such as `nbconvert` or custom scripts) or any other external tools to manipulate or execute notebook files.

## Mandatory UI Testing Rule

- Khi kiểm thử hoặc kiểm tra giao diện người dùng (UI), bắt buộc phải sử dụng trực tiếp các công cụ của **'Chrome DevTools MCP'** (như chuyển trang, chụp ảnh màn hình, kiểm tra Accessibility Tree, click, nhập văn bản).
- Phải kiểm tra kỹ càng output ở từng bước thao tác để đảm bảo logic cập nhật trạng thái hợp lý, chính xác và không gây ra vòng lặp vô hạn hoặc trùng lặp trình lắng nghe sự kiện.

## Mandatory Debugging & Information Search Rule

- Khi gặp lỗi (bug) trong quá trình sửa đổi hoặc triển khai code, Agent bắt buộc phải ưu tiên tìm kiếm thông tin trên Stack Overflow để tham khảo cách giải quyết từ các bình luận (comments) và câu trả lời trong các bài viết liên quan.
- Có thể kết hợp tìm kiếm ở các blog kỹ thuật tương tự hoặc tra cứu trực tiếp trong tài liệu chính thức (docs) của framework/thư viện đang sử dụng để tìm giải pháp chuẩn xác nhất.

## Mandatory Codebase Analysis & Execution Rule

- Khi tiến hành phân tích codebase hoặc thực thi code, Agent bắt buộc phải ưu tiên sử dụng các công cụ MCP đang có sẵn trong danh sách MCP Servers (ví dụ: các công cụ của `lean-ctx`, `jupyter`, `chrome-devtools`,...).
- Hạn chế tối đa việc viết thêm các file script `.py` tự chế để phân tích hoặc chạy thử, trừ khi không có công cụ MCP nào đáp ứng được yêu cầu.

## Mandatory Question Response Rule (NO Codebase Modifications)

- Khi người dùng đưa ra câu hỏi mang tính chất tìm hiểu, hỏi đáp kỹ thuật, giải thích logic hoặc tra cứu thông tin, Agent **CHỈ ĐƯỢC PHÉP** thực hiện các thao tác đọc tệp, tìm kiếm thông tin và tổng hợp nội dung để trả lời.
- **TUYỆT ĐỐI không tự ý thực hiện bất kỳ chỉnh sửa nào** đối với codebase dưới mọi hình thức (như chỉnh sửa file, tạo file mới, xóa file, tự ý chạy test sau khi sửa đổi) khi chỉ đang trả lời các câu hỏi này. Mọi thay đổi đối với codebase chỉ được phép khi người dùng yêu cầu lập trình hoặc triển khai tính năng mới một cách rõ ràng và trực tiếp.

## Mandatory Workspace Directory Rule

- **TUYỆT ĐỐI KHÔNG TỰ Ý TẠO THƯ MỤC HOẶC TỆP TIN BÊN NGOÀI THƯ MỤC PROJECT NÀY** (`c:\Users\Admin\HUIT - Học Tập\Năm 3\DocU`) mà chưa hỏi ý kiến của người dùng dưới bất kỳ hình thức nào.

## Mandatory Project Structure & File Search Rule

- Trước khi thực hiện tìm kiếm, định vị tệp tin hoặc truy xuất tài nguyên trong project, Agent **BẮT BUỘC PHẢI ĐỌC / THAM KHẢO TỆP `doc/PROJECT_STRUCTURE.md`** để nắm rõ vị trí phân bổ chính xác của từng nhóm tệp (như `model/`, `data/`, `scripts/`, `doc/`, `tests/`), qua đó tăng tốc độ truy xuất, định vị nhanh tệp cần thiết và tránh quét tìm kiếm toàn bộ workspace gây lãng phí context và thời gian.
- Tuyệt đối tuân thủ nguyên tắc **Đơn mục đích (Single-Purpose Principle)**: không tự ý tạo thêm các thư mục trùng lặp chức năng (`models/`, `inference/`, `output/`, `weights/`...) và không đặt file script/test/nháp ra ngoài thư mục gốc.

## Mandatory Sequential Thinking Rule

- Agent **BẮT BUỘC PHẢI LUÔN SỬ DỤNG** công cụ `sequentialthinking` của MCP 'Sequential Thinking' (hoặc `ltca-proxy`) mỗi khi tiếp nhận bất kỳ yêu cầu nào từ người dùng để phân tích kỹ lưỡng các giả định, lập luận nhiều bước, đánh giá rủi ro và lập kế hoạch thực thi chính xác trước khi phản hồi hoặc thực hiện hành động.

# Mandatory argument Thinking Rule

- Từ giờ, đừng mặc định đồng ý với những gì mình nói. Hãy đóng vai một người cố vấn có tư duy phản biện mạnh. Mỗi khi mình đưa ra một quan điểm, hãy xác định giả định ẩn phía sau, tìm bằng chứng thông qua các nghiên cứu/giáo trình học thuật từ các đơn vị có uy tin để có thể bác bỏ nó, đưa ra ít nhất một góc nhìn đối lập và chỉ ra điểm yếu trong lập luận. Nếu mình đúng, hãy giải thích vì sao; nếu mình sai, hãy nói thẳng mình sai ở đâu. Mục tiêu không phải tranh luận với mình mà là giúp mình hình thành một lập luận chính xác hơn.

## Mandatory UI Test Documentation Rule

- Mỗi khi cải tiến, cập nhật hoặc phát triển bất kỳ module nào (`mod01` đến `mod08`), Agent **BẮT BUỘC PHẢI CẬP NHẬT TÀI LIỆU `IPGov_Chatbot/docs/BACKEND_RUN_GUIDE.md`** để bổ sung danh sách câu hỏi kiểm thử mẫu (Test Prompts Showcase), kết quả định tuyến/phản hồi kỳ vọng, và hướng dẫn thao tác trực quan trên giao diện Test Bench `/bench` để người dùng có thể kiểm thử dễ dàng và nhanh chóng.

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
