# MANDATORY WORKSPACE RULES FOR PROJECT MEMORY & TRAPS MANAGEMENT

> [!IMPORTANT]
> **QUY TẮC CƯỠNG CHẾ QUẢN TRỊ BỘ NHỚ DỰ ÁN VÀ PHÒNG NGỪA BẪY MÃ NGUỒN**
> 
> Mọi tương tác, phân tích, đề xuất kỹ thuật, sửa đổi mã nguồn hoặc điều phối sub-agent trong workspace bắt buộc phải tuân thủ nghiêm ngặt 5 điều khoản dưới đây.

---

## 1. Cơ Chế Nạp Ngữ Cảnh 2 Tầng (2-Tier Memory Grounding)
1. **Tầng 1 (Chỉ đạo cốt lõi & Ràng buộc Bất biến - Core Invariants):**
   - Mọi lượt xử lý của Agent phải luôn duy trì nhận thức về các chỉ đạo nền tảng được định nghĩa tại phần đầu của tệp [`.agents/PROJECT_MEMORY.md`](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/.agents/PROJECT_MEMORY.md).
2. **Tầng 2 (Truy xuất có định hướng theo tác vụ - Task-Scoped Retrieval):**
   - Khi nhận lệnh liên quan đến một phân hệ cụ thể (ví dụ: Text-to-SQL, HBAC, API Gateway, Docker DWH, Test Runner), Agent phải trích xuất và tham chiếu đúng section liên quan trong `.agents/PROJECT_MEMORY.md`, bảo đảm không bỏ sót các lưu ý chuyên biệt mà không làm tràn bão hòa ngữ cảnh token.

---

## 2. Tự Động Ghi Nhận Lưu Ý & Sửa Đổi Của Người Dùng (Auto-Ingestion Protocol)
1. Khi người dùng đưa ra các phát ngôn mang tính điều chỉnh, ràng buộc hoặc lưu ý công vụ (chứa các cụm từ: *"từ giờ..."*, *"lưu ý là..."*, *"phải..."*, *"không được..."*, *"nhớ rằng..."*, *"chỉnh lại thành..."*) hoặc các lệnh ghi nhớ tường minh:
   - Agent **BẮT BUỘC CHỦ ĐỘNG** cập nhật ngay nội dung này vào đúng mục tương ứng trong [`.agents/PROJECT_MEMORY.md`](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/.agents/PROJECT_MEMORY.md).
   - Phản hồi xác nhận ngắn gọn với người dùng: *"✅ Đã ghi nhận lưu ý vào Project Memory."*
2. Nghiêm cấm việc "vâng lời suông" trong câu trả lời mà không cập nhật tệp `.agents/PROJECT_MEMORY.md`.

---

## 3. Rà Soát Bẫy Trước Khi Thực Thi Mã (Pre-flight Trap Check)
1. Trước khi viết code, chỉnh sửa code hoặc chạy bất kỳ lệnh terminal/PowerShell nào thuộc về các công nghệ đặc thù (Python, PowerShell Windows, PostgreSQL DWH, Pytest, v.v.):
   - Agent **BẮT BUỘC** phải rà soát các bẫy liên quan đã được lưu trong [`TRAPS.md`](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/TRAPS.md).
   - Nếu phương án dự kiến vi phạm bất kỳ bẫy nào trong `TRAPS.md`, Agent phải lập tức thay đổi giải pháp kỹ thuật trước khi gõ lệnh.

---

## 4. Tự Động Ghi Nhận Bẫy Sau Khi Khắc Phục Lỗi (Post-Fix Trap Logging)
1. Khi gặp lỗi runtime, lỗi cú pháp shell, test fail, hoặc phát hiện một anti-pattern tiềm ẩn:
   - Sau khi tìm ra giải pháp và khắc phục thành công (vượt qua kiểm thử), Agent **BẮT BUỘC CHỦ ĐỘNG** ghi nhận lỗi đó vào cuối tệp [`TRAPS.md`](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/TRAPS.md) theo cấu trúc chuẩn:
     * Định danh bẫy `[TRAP-xxx]`.
     * Triệu chứng / Bối cảnh xuất hiện lỗi.
     * Nguyên nhân gốc rễ (Root Cause).
     * Quy tắc phòng ngừa dứt điểm (Never Do / Always Do).
2. Tuyệt đối không chờ người dùng nhắc nhở mới ghi chép bẫy.

---

## 5. Truyền Tải Ngữ Cảnh Cho Sub-Agents (Sub-Agent Inheritance Protocol)
1. Khi Agent chính điều phối tác vụ qua `invoke_subagent`:
   - Agent chính **BẮT BUỘC** trích xuất các Core Invariants từ [`.agents/PROJECT_MEMORY.md`](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/.agents/PROJECT_MEMORY.md) và các TRAPS liên quan trực tiếp đến phạm vi nhiệm vụ của Sub-Agent để tiêm vào Prompt khởi tạo.
   - Chỉ thị cho Sub-Agent: Tuân thủ nghiêm ngặt [`TRAPS.md`](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/TRAPS.md) và báo cáo ngược lại mọi bẫy lỗi mới phát hiện trong quá trình chạy nhiệm vụ để Agent chính ghi nhận vào `TRAPS.md`.
