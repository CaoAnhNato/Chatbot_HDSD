# BẢNG THUẬT NGỮ NGHIỆP VỤ & KHO DỮ LIỆU (IPGov DWH GLOSSARY)

Tài liệu chuẩn hóa định nghĩa, thuật ngữ kỹ thuật và quy chuẩn hiển thị trong hệ thống `IPGov_Chatbot`.

| Thuật ngữ / Khái niệm | Ý nghĩa Nghiệp vụ & Kỹ thuật trong Hệ thống | Quy chuẩn Hiển thị / Hành vi Hệ thống |
| :--- | :--- | :--- |
| **Chỉ tiêu (Criteria)** | Đại lượng thống kê hoặc chỉ số đo lường kinh tế - xã hội (ví dụ: sản lượng muối, diện tích diêm nghiệp, số sản phẩm OCOP...). | Được lưu tại bảng `criteria` và `fact_report_criteria`. Khi hiển thị, phải dùng tên tiếng Việt đầy đủ kèm đơn vị tính (`unit`). |
| **Báo cáo (Report)** | Đợt nộp và tổng hợp số liệu của một cơ quan/đơn vị theo kỳ quy định (tháng, quý, năm). | Lưu tại bảng `report`. Chỉ số liệu từ các báo cáo có trạng thái `approved` mới được đưa vào tính toán thống kê. |
| **Phiên bản Báo cáo (Report Version)** | Số thứ tự lần hiệu chỉnh của một báo cáo (ví dụ: `version = 1`, `version = 2`). | Hệ thống áp dụng quy tắc Deduplication: Chỉ trích xuất số liệu của phiên bản cao nhất (`MAX(version)`) cho mỗi chỉ tiêu trên từng báo cáo đã duyệt. |
| **Biểu mẫu Thu thập (Collection Form)** | Mẫu tờ khai thu thập dữ liệu định kỳ do UBND tỉnh hoặc các sở ngành ban hành. | Lưu tại bảng `collection_form`. Trạng thái hoạt động là `active` hoặc `deprecated`. |
| **Nhiệm vụ / Đề án (Mission)** | Chương trình, kế hoạch hoặc đề án công tác trọng tâm được giao cho cơ quan, phòng ban hoặc cán bộ. | Lưu tại bảng `mission`, `office_mission`, `user_mission`. |
| **Cán bộ / Chuyên viên (User)** | Tài khoản cán bộ, công chức, chuyên viên tham gia xử lý số liệu trên hệ thống điều hành. | Bảng `user` trong PostgreSQL (tên bảng có dấu nháy kép `"user"` do trùng từ khóa). Không có cột `is_admin`. |
| **Ứng viên Chỉ tiêu (Candidate Criteria)** | Danh sách các chỉ tiêu có độ tương đồng ngữ nghĩa cao nhất với câu hỏi người dùng được trích xuất từ DuckDB Catalog trong RAM. | Cố định `TOP_K = 5` ứng viên, xếp hạng bằng thuật toán Hybrid RRF, lọc với ngưỡng `Score >= 60.0`. |
| **Khớp Tự Động Tin Cậy (Confident Match)** | Tình huống hệ thống tự động xác định được chỉ tiêu chính xác mà không cần hỏi lại người dùng. | Điều kiện: Ứng viên Top 1 khớp tuyệt đối HOẶC độ chênh lệch điểm $\Delta_{\text{score}} \ge 0.10$. |
| **Làm Rõ Chủ Động (Active Clarification)** | Tình huống câu hỏi người dùng quá ngắn hoặc có nhiều chỉ tiêu tương đương về điểm số cần xác nhận lại. | Hiển thị câu hỏi làm rõ kèm các nút bấm gợi ý (Chips) để người dùng chọn trực tiếp. |
| **Chỉ tiêu Rỗng (NULL Metric Value)** | Chỉ tiêu đã được ban hành trong danh mục biểu mẫu 2026 nhưng hiện tại chưa có cơ quan nào nộp số liệu thực tế (`value IS NULL`). | Chatbot giải thích rõ ràng trạng thái danh mục và dữ liệu, đồng thời tự động gợi ý chỉ tiêu liên quan có dữ liệu trong kho DWH. |
| **Quy chuẩn Định dạng Số (Number Formatting)** | Định dạng số liệu hiển thị trong toàn bộ phản hồi của chatbot. | Hàng nghìn dùng dấu phẩy `,` (`1,320`); thập phân dùng dấu chấm `.` (`12.5`); năm lịch 4 số (`2026`) giữ nguyên, không thêm dấu phân cách. |
