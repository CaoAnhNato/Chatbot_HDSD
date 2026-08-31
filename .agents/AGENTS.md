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
