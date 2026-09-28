# BẢNG RÀ SOÁT & DUYỆT BỘ TEST CASE KHÁM PHÁ NĂNG LỰC & HỘI THOẠI ĐA LƯỢT (MULTI-TURN & DISCOVERY TEST CASES)

> **Mục đích**: Cổng kiểm soát **Human-in-the-Loop (HITL) Gate** cho các test cases còn thiếu trong hệ thống:
>
> 1. **Nhóm 1 (Discovery & Capability Exploration)**: 10 câu hỏi đơn giản/khám phá chức năng, phạm vi dữ liệu, mốc thời gian, quyền hạn HBAC, quy trình duyệt.
> 2. **Nhóm 2 (Multi-turn Conversational Threads - H-DFT)**: 05 chuỗi hội thoại đa lượt liên hoàn (16 turns) kiểm tra khả năng lưu trữ ngữ cảnh hội thoại, đại từ thay thế (Anaphora/Co-reference), xử lý câu hỏi mơ hồ/hỏi làm rõ (Clarification/Slot-filling), đào sâu phân cấp (Drill-down) và chuyển đổi chủ đề (Topic Shift).
>
> **Ràng buộc tuân thủ**: Bảng này **CHỈ DỪNG Ở NỘI DUNG CÂU HỎI, NGỮ CẢNH HỘI THOẠI VÀ ĐÁNH GIÁ AUDIT**, tuyệt đối không chứa mã SQL.

---

## 1. TỔNG QUAN CÁC NĂNG LỰC ĐÀM THOẠI ĐƯỢC KIỂM THỬ


| Nhóm Kiểm Thử                                                  |         Số lượng Case         | Năng Lực Cốt Lõi Được Kiểm Tra                                                                                                                                                                                                                                                                                                                                                       | Cơ Chế Kỹ Thuật Đánh Giá                                                                  |
| :------------------------------------------------------------------ | :---------------------------------: | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------- |
| **Phần I: Khám Phá Năng Lực (Discovery)**                    |           10 câu hỏi           | Tự giới thiệu chức năng, tra cứu 8 lĩnh vực, phạm vi mốc năm dữ liệu, định nghĩa chỉ tiêu, phân quyền HBAC, trạng thái báo cáo, mốc tươi mới ETL, hướng dẫn cán bộ mới.                                                                                                                                                                                    | In-memory Metadata Catalog trên DuckDB RAM, Capability Router Bypass (<50ms).                   |
| **Phần II: Chuỗi Đàm Thoại Đa Lượt (Multi-turn Threads)** | 5 chuỗi (16 lượt đàm thoại) | • Giải quyết đại từ thay thế (Anaphora Resolution):*"Số lượng này"*, *"ở huyện đó"*, *"báo cáo này"*.• Nhận diện thiếu tham số & Hỏi làm rõ (Slot-filling & Ambiguity Clarification).• Đào sâu phân cấp hành chính (Drill-down: Tỉnh $\to$ Huyện $\to$ Phòng).• Chuyển đổi chủ đề & Dọn sạch ngữ cảnh cũ (Topic Shift & Context Isolation). | Khung hội thoại H-DFT, Bộ nhớ phiên Session State, Lineage Badges, AST Security Guardrails. |

---

## 2. PHẦN I: 10 TEST CASE CÂU HỎI ĐƠN GIẢN & KHÁM PHÁ NĂNG LỰC HỆ THỐNG

### **DISC_01** | `DISCOVERY` | `CAPABILITY_CORE`

- **Mục tiêu kiểm thử**: Kiểm tra khả năng tự giới thiệu tổng quan vai trò, chức năng cốt lõi và các tiện ích phục vụ công vụ của Chatbot.
- **Câu hỏi hiện tại**: *"Hệ thống này có chức năng gì?"*
- **Biến thể khẩu ngữ bổ trợ**: *"Hệ thống này có chức năng gì vậy em?"* (kiểm tra bộ lọc từ đệm stopword)
- **Hành vi kỳ vọng của Chatbot**: Giới thiệu ngắn gọn vai trò trợ lý khai thác kho dữ liệu công vụ; liệt kê 4 tiện ích chính (Tra cứu thống kê, So sánh biến động, Theo dõi tiến độ duyệt báo cáo, Xuất số liệu); gợi ý các câu lệnh mẫu để người dùng bắt đầu.
- **Nhận xét đánh giá Audit**: [PASS] Đạt 5/5 tiêu chí.
- **Đánh giá của Bạn**:
  - [X]  **ĐẠT** (Giữ câu hiện tại)
  - [ ]  **ĐỒNG Ý VỚI GỢI Ý VIẾT LẠI**
  - [ ]  **YÊU CẦU SỬA KHÁC**: __________________________________________________

### **DISC_02** | `DISCOVERY` | `SCOPE_DISCOVERY`

- **Mục tiêu kiểm thử**: Kiểm tra khả năng tra cứu danh mục lĩnh vực quản lý nhà nước từ Catalog DuckDB RAM mà không cần quét bảng Fact.
- **Câu hỏi hiện tại**: *"Hệ thống đang theo dõi số liệu của những ngành, lĩnh vực nào?"*
- **Hành vi kỳ vọng của Chatbot**: Liệt kê 8 lĩnh vực quản lý nhà nước có dữ liệu trong kho: Nội vụ & Lao động, Xây dựng, Công thương, Y tế, Giáo dục & Đào tạo, Văn hóa - Xã hội, Nông nghiệp & PTNT, Tài nguyên & Môi trường; kèm các nút Action Chips để người dùng bấm chọn nhanh.
- **Nhận xét đánh giá Audit**: [PASS] Đạt 5/5 tiêu chí. Văn phong chuẩn mực hành chính.
- **Đánh giá của Bạn**:
  - [X]  **ĐẠT** (Giữ câu hiện tại)
  - [ ]  **ĐỒNG Ý VỚI GỢI Ý VIẾT LẠI**
  - [ ]  **YÊU CẦU SỬA KHÁC**: __________________________________________________

### **DISC_03** | `DISCOVERY` | `TEMPORAL_WINDOW`

- **Mục tiêu kiểm thử**: Kiểm tra năng lực xác định chính xác phạm vi mốc thời gian và chu kỳ dữ liệu có trong DWH.
- **Câu hỏi hiện tại**: *"Số liệu báo cáo trong hệ thống có từ năm nào đến năm nào?"*
- **Hành vi kỳ vọng của Chatbot**: Thông báo rõ ràng: Hệ thống lưu trữ dữ liệu báo cáo chính thức của năm 2025 và năm 2026 với các chu kỳ tháng, quý, 6 tháng và năm. Đồng thời nêu rõ các năm trước 2025 chưa được số hóa lên kho tập trung để tránh người dùng hiểu nhầm.
- **Nhận xét đánh giá Audit**: [PASS] Đạt 5/5 tiêu chí. Rất thực tế cho công tác lập kế hoạch.
- **Đánh giá của Bạn**:
  - [X]  **ĐẠT** (Giữ câu hiện tại)
  - [ ]  **ĐỒNG Ý VỚI GỢI Ý VIẾT LẠI**
  - [ ]  **YÊU CẦU SỬA KHÁC**: __________________________________________________

### **DISC_04** | `DISCOVERY` | `METRIC_DEFINITION`

- **Mục tiêu kiểm thử**: Kiểm tra từ điển chỉ tiêu công vụ (Semantic Glossary) để giải thích định nghĩa, công thức toán học và đơn vị tính của một chỉ tiêu hành chính.
- **Câu hỏi hiện tại**: *"Chỉ tiêu tỷ lệ giải ngân kinh phí khuyến công được tính như thế nào?"*
- **Hành vi kỳ vọng của Chatbot**: Giải thích rõ công thức: Tỷ lệ giải ngân (%) = (Kinh phí khuyến công đã thực tế giải ngân / Tổng dự toán kinh phí được phê duyệt giao trong kỳ) * 100%. Nêu rõ đơn vị tính là %, áp dụng cho đề án khuyến công địa phương/quốc gia căn cứ từ báo cáo đã duyệt chính thức.
- **Nhận xét đánh giá Audit**: [PASS] Đạt 5/5 tiêu chí. Đúng nghiệp vụ tài chính công.
- **Đánh giá của Bạn**:
  - [X]  **ĐẠT** (Giữ câu hiện tại)
  - [ ]  **ĐỒNG Ý VỚI GỢI Ý VIẾT LẠI**
  - [ ]  **YÊU CẦU SỬA KHÁC**: __________________________________________________

### **DISC_05** | `DISCOVERY` | `FORM_CATALOG`

- **Mục tiêu kiểm thử**: Kiểm tra khả năng truy vấn danh mục các biểu mẫu thu thập số liệu đang áp dụng từ bộ nhớ RAM.
- **Câu hỏi hiện tại**: *"Hệ thống hiện có những loại biểu mẫu báo cáo nào đang áp dụng?"*
- **Hành vi kỳ vọng của Chatbot**: Liệt kê các nhóm biểu mẫu thu thập dữ liệu đang có hiệu lực trong năm (Biểu mẫu ATVSLĐ, Biểu mẫu khuyến công, Biểu mẫu trật tự xây dựng, Biểu mẫu giảm nghèo...) kèm thông tin cơ quan chủ trì ban hành và kỳ báo cáo áp dụng.
- **Nhận xét đánh giá Audit**: [PASS] Đạt 5/5 tiêu chí.
- **Đánh giá của Bạn**:
  - [X]  **ĐẠT** (Giữ câu hiện tại)
  - [ ]  **ĐỒNG Ý VỚI GỢI Ý VIẾT LẠI**
  - [ ]  **YÊU CẦU SỬA KHÁC**: __________________________________________________

### **DISC_06** | `DISCOVERY` | `HBAC_DISCOVERY`

- **Mục tiêu kiểm thử**: Kiểm tra năng lực giải thích cơ chế phân quyền phân cấp hình cây (Tree-based HBAC) và xác định minh bạch ranh giới dữ liệu được phép truy cập theo từng tài khoản.
- **Câu hỏi hiện tại**: *"Tài khoản chuyên viên cấp phòng thì tôi tra cứu được những dữ liệu nào?"*
- **Hành vi kỳ vọng của Chatbot**: Giải thích rõ: Tài khoản cấp phòng được toàn quyền tra cứu mọi số liệu và trạng thái báo cáo (đã duyệt, chờ duyệt, nháp) thuộc nội bộ phòng ban mình phụ trách, đồng thời xem được số liệu tổng hợp công khai của tỉnh; không thể xem số liệu nội bộ của các phòng ban khác hoặc sở ngành khác.
- **Nhận xét đánh giá Audit**: [PASS] Đạt 5/5 tiêu chí. Rất thiết thực cho người dùng cơ sở.
- **Đánh giá của Bạn**:
  - [X]  **ĐẠT** (Giữ câu hiện tại)
  - [ ]  **ĐỒNG Ý VỚI GỢI Ý VIẾT LẠI**
  - [ ]  **YÊU CẦU SỬA KHÁC**: __________________________________________________

### **DISC_07** | `DISCOVERY` | `EXPORT_CAPABILITY`

- **Mục tiêu kiểm thử**: Kiểm tra phản hồi về các định dạng xuất dữ liệu (Export Capability) và hướng dẫn cán bộ tải kết quả.
- **Câu hỏi hiện tại**: *"Chatbot có hỗ trợ xuất dữ liệu ra bảng Excel hoặc file PDF không?"*
- **Hành vi kỳ vọng của Chatbot**: Xác nhận có hỗ trợ và nêu rõ: Xuất bảng tính Excel (.xlsx) cho bảng số liệu chi tiết, xuất dự thảo báo cáo Word (.docx), xem trực quan và in PDF; hướng dẫn chỉ cần gõ "Xuất bảng này ra Excel" sau khi nhận kết quả.
- **Nhận xét đánh giá Audit**: [PASS] Đạt 5/5 tiêu chí.
- **Đánh giá của Bạn**:
  - [X]  **ĐẠT** (Giữ câu hiện tại)
  - [ ]  **ĐỒNG Ý VỚI GỢI Ý VIẾT LẠI**
  - [ ]  **YÊU CẦU SỬA KHÁC**: __________________________________________________

### **DISC_08** | `DISCOVERY` | `REPORT_STATUS_POLICY`

- **Mục tiêu kiểm thử**: Kiểm tra khả năng định nghĩa 4 trạng thái vòng đời báo cáo và khẳng định nguyên tắc chỉ sử dụng số liệu hợp thức (Approved) cho phân tích thống kê.
- **Câu hỏi hiện tại**: *"Báo cáo có những trạng thái duyệt nào và trạng thái nào là số liệu chính thức?"*
- **Hành vi kỳ vọng của Chatbot**: Giải thích rõ 4 trạng thái: (1) Đã phê duyệt (Approved) - Số liệu chính thức có giá trị pháp lý; (2) Đang chờ duyệt (Pending) - Chỉ mang tính tham khảo nội bộ; (3) Bản nháp (Draft) - Lưu tạm; (4) Bị từ chối (Rejected) - Bị trả về. Khẳng định mặc định mọi thống kê chính thức đều lấy từ trạng thái Đã phê duyệt.
- **Nhận xét đánh giá Audit**: [PASS] Đạt 5/5 tiêu chí. Đảm bảo tính pháp lý số liệu.
- **Đánh giá của Bạn**:
  - [X]  **ĐẠT** (Giữ câu hiện tại)
  - [ ]  **ĐỒNG Ý VỚI GỢI Ý VIẾT LẠI**
  - [ ]  **YÊU CẦU SỬA KHÁC**: __________________________________________________

### **DISC_09** | `DISCOVERY` | `DATA_FRESHNESS`

- **Mục tiêu kiểm thử**: Kiểm tra năng lực xác minh mốc tươi mới của dữ liệu (Data Freshness / Sync Status).
- **Câu hỏi hiện tại (bản ban đầu)**: *"Dữ liệu báo cáo hôm nay đã được cập nhật từ phần mềm tác nghiệp về kho DWH chưa?"*
- **Nhận xét điểm phi logic / gượng gạo**: Vi phạm C5: Cụm từ "kho DWH" là tiếng lóng IT kỹ thuật của lập trình viên, cán bộ hành chính không sử dụng từ này.
- **Gợi ý viết lại chuẩn thực tế**: **"Dữ liệu báo cáo hôm nay đã được cập nhật từ phần mềm tác nghiệp về kho dữ liệu tổng hợp chưa?"**
- **Hành vi kỳ vọng của Chatbot**: Cung cấp mốc thời gian đồng bộ thành công gần nhất (ví dụ: hoàn tất lúc 00:00 sáng nay); xác nhận hệ thống vận hành ổn định và dữ liệu hiện tra cứu phản ánh đầy đủ báo cáo đã duyệt tính đến thời điểm đó.
- **Đánh giá của Bạn**:
  - [ ]  **ĐẠT** (Giữ câu hiện tại)
  - [X]  **ĐỒNG Ý VỚI GỢI Ý VIẾT LẠI**
  - [ ]  **YÊU CẦU SỬA KHÁC**: __________________________________________________

### **DISC_10** | `DISCOVERY` | `USER_ONBOARDING`

- **Mục tiêu kiểm thử**: Kiểm tra khả năng chào đón, hướng dẫn quy trình tương tác ban đầu cho cán bộ mới tiếp cận hệ thống.
- **Câu hỏi hiện tại**: *"Xin chào, tôi là cán bộ mới thì nên bắt đầu tra cứu số liệu như thế nào?"*
- **Hành vi kỳ vọng của Chatbot**: Chào đón thân thiện, hướng dẫn 3 bước đơn giản (Đặt câu hỏi tiếng Việt nêu rõ chỉ tiêu, đơn vị, năm; bấm các nút gợi ý Action Chips; cung cấp 3 câu hỏi mẫu thực tế để thử ngay).
- **Nhận xét đánh giá Audit**: [PASS] Đạt 5/5 tiêu chí.
- **Đánh giá của Bạn**:
  - [X]  **ĐẠT** (Giữ câu hiện tại)
  - [ ]  **ĐỒNG Ý VỚI GỢI Ý VIẾT LẠI**
  - [ ]  **YÊU CẦU SỬA KHÁC**: __________________________________________________

---

## 3. PHẦN II: 05 CHUỖI ĐÀM THOẠI ĐA LƯỢT HOÀN CHỈNH (MULTI-TURN CONVERSATION THREADS)

---

### **THREAD_01** | `MULTI_TURN` | `CAPABILITY_TO_METRIC_YOY_DRILLDOWN`

> **Chủ đề**: Lao động - Thương binh và Xã hội (An toàn vệ sinh lao động)
> **Mục tiêu**: Kiểm tra chuỗi hội thoại thực tế đúng như bạn đã nêu: Khám phá chức năng $\to$ Tra cứu chỉ tiêu gần đây $\to$ So sánh xu hướng tăng/giảm bằng đại từ thay thế $\to$ Đào sâu tìm đơn vị trọng điểm.
> **Bẫy kỹ thuật**: Bẫy mốc thời gian ngầm định ("gần đây" phải map về năm 2025 đã phê duyệt chính thức thay vì 2026 đang dở dang) và đại từ thay thế *"Số lượng này"*, *"Ở những đơn vị nào"* phải kế thừa đúng chỉ tiêu tai nạn lao động.

* **Lượt 1 (Turn 1)**:

  - **Người dùng hỏi**: *"Hệ thống này có chức năng gì ?"*
  - **Trạng thái ngữ cảnh (Context State)**: Khởi tạo phiên hội thoại mới; chưa có bộ lọc nào được kích hoạt.
  - **Hành vi kỳ vọng**: Giới thiệu chức năng trợ lý số liệu công vụ; hiển thị 8 lĩnh vực và nút bấm gợi ý *"📊 Số vụ tai nạn lao động gần đây"*.
* **Lượt 2 (Turn 2)**:

  - **Người dùng hỏi**: *"Số vụ tai nạn lao động gần đây là bao nhiêu ?"*
  - **Trạng thái ngữ cảnh (Context State)**: Phân giải "gần đây" $\to$ `year = 2025` (năm đã chốt duyệt); gắn thực thể `code = 'TNLD_SO_VU'`; cấp phạm vi `Level 0 (Toàn tỉnh)`.
  - **Hành vi kỳ vọng**: Báo cáo tổng số vụ tai nạn lao động toàn tỉnh năm 2025 (ví dụ: 142 vụ). Đính kèm Lineage Badge từ Báo cáo ATVSLĐ đã duyệt của UBND tỉnh; hiển thị nút gợi ý *"📈 Xu hướng tăng/giảm so với 2024"*.
* **Lượt 3 (Turn 3)**:

  - **Người dùng hỏi**: *"Số lượng này đang tăng hay giảm ?"*
  - **Trạng thái ngữ cảnh (Context State)**: **Giải quyết đại từ thay thế (Anaphora Resolution)**: *"Số lượng này"* = *Số vụ tai nạn lao động* (`TNLD_SO_VU`); kích hoạt so sánh tăng trưởng cùng kỳ (YoY: 2025 vs 2024).
  - **Hành vi kỳ vọng**: Tính toán đối chuẩn giữa 2025 (142 vụ) và 2024 (160 vụ); kết luận rõ: Số vụ tai nạn lao động năm 2025 GIẢM 18 vụ (tương đương giảm 11.25% so với năm 2024).
* **Lượt 4 (Turn 4)**:

  - **Người dùng hỏi**: *"Ở những đơn vị nào xảy ra nhiều nhất ?"*
  - **Trạng thái ngữ cảnh (Context State)**: Kế thừa chỉ tiêu tai nạn lao động năm 2025; thực hiện **Drill-down** hạ độ mịn từ Level 0 (Toàn tỉnh) xuống Level 2 (Phòng ban/Cơ quan cơ sở); sắp xếp giảm dần `LIMIT 5`.
  - **Hành vi kỳ vọng**: Hiển thị bảng Top 5 đơn vị có số vụ tai nạn lao động nhiều nhất năm 2025 kèm khuyến nghị tăng cường thanh tra giám sát liên ngành tại các đơn vị này.

- **Đánh giá Audit**: [PASS] Đạt 5/5 tiêu chí. Dòng hội thoại mẫu mực, giải quyết triệt để vấn đề lưu ngữ cảnh.
- **Đánh giá của Bạn**:
  - [X]  **ĐẠT** (Giữ trọn chuỗi kịch bản)
  - [ ]  **YÊU CẦU SỬA**: __________________________________________________

---

### **THREAD_02** | `MULTI_TURN` | `HIERARCHICAL_DRILL_DOWN`

> **Chủ đề**: Y tế (Cơ sở vật chất y tế xã đạt chuẩn quốc gia)
> **Persona bắt buộc**: `LÃNH ĐẠO CẤP TỈNH (Role Level 0)` (bắt buộc để có thẩm quyền xem dữ liệu liên huyện).
> **Mục tiêu**: Kiểm tra khả năng điều hướng phân cấp hành chính 3 tầng (Tỉnh $\to$ Huyện $\to$ Xã), chuyển đổi toán tử từ đếm tổng hợp sang tìm cực trị (Min) và lọc số lượng chưa đạt.
> **Bẫy kỹ thuật & Điều chỉnh của Auditor**: Bảng fact_report_criteria trong DWH lưu số lượng tổng hợp tại cấp đơn vị. Để tránh bẫy ảo giác độ mịn, Turn 3 được điều chỉnh truy vấn số trạm chưa đạt và tỷ lệ đạt chuẩn.

* **Lượt 1 (Turn 1)**:

  - **Người dùng hỏi**: *"Toàn tỉnh năm 2025 có bao nhiêu trạm y tế đạt chuẩn quốc gia ?"*
  - **Trạng thái ngữ cảnh (Context State)**: Chỉ tiêu `YTE_TRAM_DAT_CHUAN`, năm `2025`, phạm vi `Toàn tỉnh (Level 0)`.
  - **Hành vi kỳ vọng**: Trả về tổng số: Năm 2025 toàn tỉnh có 124/142 trạm y tế xã/phường đạt chuẩn (đạt tỷ lệ 87.32%, tăng 6 trạm so với năm 2024).
* **Lượt 2 (Turn 2)**:

  - **Người dùng hỏi**: *"Huyện nào có số lượng thấp nhất ?"*
  - **Trạng thái ngữ cảnh (Context State)**: Kế thừa chỉ tiêu và năm 2025; hạ độ mịn xuống cấp Huyện (Level 1); kích hoạt hàm cực trị `MIN/ASC LIMIT 1`.
  - **Hành vi kỳ vọng**: Xác định chính xác: Huyện Đam Rông có số lượng trạm y tế đạt chuẩn thấp nhất tỉnh năm 2025 với 4/8 trạm (tỷ lệ 50.0%); lưu thực thể `Huyện Đam Rông` vào bộ nhớ ngắn hạn.
* **Lượt 3 (Turn 3 - Đã được Auditor chuẩn hóa tránh bẫy độ mịn)**:

  - **Người dùng hỏi**: *"Cụ thể huyện đó có bao nhiêu trạm chưa đạt và tỷ lệ đạt chuẩn là bao nhiêu %?"*
  - **Trạng thái ngữ cảnh (Context State)**: Đại từ *"huyện đó"* = *Huyện Đam Rông*; đảo logic sang đếm số trạm chưa đạt (8 - 4 = 4 trạm chưa đạt, chiếm tỷ lệ 50%).
  - **Hành vi kỳ vọng**: Nêu rõ 4 trạm chưa đạt chuẩn tại huyện Đam Rông, kèm giải trình nguyên nhân chính (thiếu thiết bị chẩn đoán hình ảnh và thiếu biên chế bác sĩ đa khoa cơ hữu).

- **Đánh giá Audit**: [PASS SAU KHI AUDIT TINH CHỈNH] Đạt 5/5 tiêu chí.
- **Đánh giá của Bạn**:
  - [X]  **ĐẠT** (Giữ trọn chuỗi kịch bản)
  - [ ]  **YÊU CẦU SỬA**: __________________________________________________

---

### **THREAD_03** | `MULTI_TURN` | `AMBIGUITY_CLARIFICATION_SLOT_FILLING`

> **Chủ đề**: Công thương (Kinh phí giải ngân khuyến công)
> **Mục tiêu**: Kiểm thử năng lực phát hiện câu hỏi mơ hồ thiếu tham số (Temporal slot & Admin entity slot). Chatbot không được đoán mò mà phải dừng lại hỏi làm rõ (Clarification), tiếp nhận câu trả lời bổ sung (Slot-filling) và mở rộng so sánh liên kỳ.
> **Bẫy kỹ thuật**: Bẫy suy đoán ngầm định (Silent Assumption Trap). Khi user hỏi thiếu năm, chatbot phải hỏi làm rõ. Ở Turn 2 khi user chỉ nói cụt *"Năm 2025 toàn tỉnh"*, hệ thống phải nạp đồng thời cả 2 slot và kích hoạt truy vấn ngay.

* **Lượt 1 (Turn 1)**:

  - **Người dùng hỏi**: *"Cho tôi xem số liệu giải ngân kinh phí khuyến công."*
  - **Trạng thái ngữ cảnh (Context State)**: Phát hiện khuyết cả 2 tham số: `year` và `admin_scope`. Chuyển sang trạng thái `CLARIFICATION`.
  - **Hành vi kỳ vọng**: Dừng chạy SQL trên Fact; phản hồi lịch sự hỏi làm rõ: *"Bạn muốn xem kinh phí giải ngân khuyến công của năm nào và phạm vi nào? Hiện hệ thống có số liệu quyết toán 2024, năm 2025 đã phê duyệt và 2026 đang thực hiện"* kèm các nút Action Chips.
* **Lượt 2 (Turn 2)**:

  - **Người dùng trả lời ngắn gọn**: *"Năm 2025 toàn tỉnh."*
  - **Trạng thái ngữ cảnh (Context State)**: Khớp nối slot: `year = 2025`, `admin_scope = 'toan_tinh'`; giải tỏa trạng thái Clarification, thực thi truy vấn.
  - **Hành vi kỳ vọng**: Trả về kết quả chính xác: Năm 2025 tổng kinh phí khuyến công đã giải ngân toàn tỉnh đạt 4.850 triệu đồng (đạt 97.0% kế hoạch giao đầu năm).
* **Lượt 3 (Turn 3)**:

  - **Người dùng hỏi tiếp**: *"So với năm 2024 thì sao ?"*
  - **Trạng thái ngữ cảnh (Context State)**: Kế thừa toàn bộ slot chỉ tiêu giải ngân khuyến công toàn tỉnh; chỉ thay đổi slot đối chuẩn so sánh `comparison_year = 2024`.
  - **Hành vi kỳ vọng**: Khởi tạo truy vấn song song năm 2024 (4.200 triệu đồng) và 2025 (4.850 triệu đồng); kết luận: Năm 2025 TĂNG 650 triệu đồng (+15.48% so với năm 2024).

- **Đánh giá Audit**: [PASS] Đạt 5/5 tiêu chí. Cơ chế hỏi làm rõ cực kỳ thông minh và chuẩn mực công vụ.
- **Đánh giá của Bạn**:
  - [X]  **ĐẠT** (Giữ trọn chuỗi kịch bản)
  - [ ]  **YÊU CẦU SỬA**: __________________________________________________

---

### **THREAD_04** | `MULTI_TURN` | `FORM_DISCOVERY_DEADLINE_STATUS`

> **Chủ đề**: Xây dựng (Biểu mẫu thu thập số liệu & Giám sát tiến độ báo cáo tác nghiệp)
> **Mục tiêu**: Kiểm tra khả năng phân định giữa truy vấn danh mục cấu hình biểu mẫu (In-Memory Catalog) với truy vấn giám sát quy trình báo cáo công vụ (Report Workflow Audit trên DB); giải quyết đại từ thay thế *"Báo cáo này"* kết hợp đơn vị phòng ban.
> **Bẫy kỹ thuật**: Bẫy quét nhầm bảng Fact cho câu hỏi danh mục biểu mẫu. Ở Turn 3, *"Báo cáo này của phòng"* phải ánh xạ chính xác mã biểu mẫu 01/KT-XD vừa tìm được và phòng ban gán tương ứng (Phòng Xây dựng) để kiểm tra tiến độ trong bảng report.

* **Lượt 1 (Turn 1)**:

  - **Người dùng hỏi**: *"Năm 2026 có những biểu mẫu thu thập dữ liệu nào ?"*
  - **Trạng thái ngữ cảnh (Context State)**: Truy vấn danh mục biểu mẫu năm 2026 (`collection_form`).
  - **Hành vi kỳ vọng**: Liệt kê danh sách biểu mẫu có hiệu lực trong năm 2026 (Biểu mẫu 01/KT-XD trật tự xây dựng, Biểu mẫu 02/LĐ-TBXH an toàn lao động, Biểu mẫu 05/CT-KC khuyến công...) kèm nút gợi ý *"🏗️ Biểu mẫu của Phòng Xây dựng sắp đến hạn nộp"*.
* **Lượt 2 (Turn 2)**:

  - **Người dùng hỏi**: *"Biểu mẫu nào của Phòng Xây dựng sắp đến hạn nộp ?"*
  - **Trạng thái ngữ cảnh (Context State)**: Kế thừa danh mục biểu mẫu 2026, lọc theo đơn vị `Phòng Xây dựng`, sắp xếp theo hạn nộp gần nhất (`deadline_date ASC LIMIT 1`).
  - **Hành vi kỳ vọng**: Xác định rõ: Biểu mẫu số 01/KT-XD ("Báo cáo giám sát trật tự xây dựng Quý 3/2026") của Phòng Xây dựng sắp đến hạn nhất; hạn chót: 25/09/2026 (còn 4 ngày), đính kèm cảnh báo thời hạn SLA Alert.
* **Lượt 3 (Turn 3)**:

  - **Người dùng hỏi**: *"Báo cáo này của phòng đã nộp và duyệt chưa ?"*
  - **Trạng thái ngữ cảnh (Context State)**: Đại từ *"Báo cáo này"* = *Biểu mẫu 01/KT-XD Q3/2026*; *"của phòng"* = *Phòng Xây dựng*; chuyển hướng sang kiểm tra trạng thái quy trình phê duyệt trong bảng `report`.
  - **Hành vi kỳ vọng**: Báo cáo tiến độ: Báo cáo đã được nộp ngày 20/09/2026, hiện đang ở trạng thái ĐÃ NỘP (submitted) và ĐANG CHỜ PHÊ DUYỆT (pending) tại Văn phòng Sở Xây dựng; kèm cảnh báo số liệu chưa duyệt chỉ dùng tham khảo nội bộ.

- **Đánh giá Audit**: [PASS] Đạt 5/5 tiêu chí. Mô phỏng xuất sắc quy trình tác nghiệp của chuyên viên.
- **Đánh giá của Bạn**:
  - [X]  **ĐẠT** (Giữ trọn chuỗi kịch bản)
  - [ ]  **YÊU CẦU SỬA**: __________________________________________________

---

### **THREAD_05** | `MULTI_TURN` | `ANOMALY_ACCOUNTABILITY_TOPIC_SHIFT`

> **Chủ đề**: Giám sát Chất lượng Dữ liệu & Đổi Chủ đề (Y tế $\to$ Giảm nghèo / Xã hội)
> **Mục tiêu**: Kiểm tra 2 cơ chế nâng cao của H-DFT: (1) Phát hiện bất thường dữ liệu và truy vết trách nhiệm công vụ qua bảng liên kết `user_mission`; (2) Chuyển đổi chủ đề triệt để (Topic Shift & Context Isolation) ở Turn 3, xóa sạch toàn bộ điều kiện lọc Y tế cũ để thực thi truy vấn độc lập mảng Giảm nghèo.
> **Bẫy kỹ thuật**: Bẫy ô nhiễm ngữ cảnh (Context Contamination Trap). Ở Turn 3 người dùng đổi chủ đề sang mảng Giảm nghèo, nếu không có cơ chế Purge Context thì hệ thống sẽ giữ lại điều kiện lọc "bị để trống hoặc bằng 0" của Y tế, dẫn tới sinh SQL sai lệch. Hệ thống phải dọn sạch ngữ cảnh cũ để chạy độc lập.

* **Lượt 1 (Turn 1)**:

  - **Người dùng hỏi**: *"Có chỉ tiêu nào của lĩnh vực y tế năm 2025 bị để trống hoặc bằng 0 bất thường không ?"*
  - **Trạng thái ngữ cảnh (Context State)**: Kiểm tra dị thường dữ liệu (`f.value IS NULL OR f.value = 0`), lĩnh vực `Y tế`, năm `2025`.
  - **Hành vi kỳ vọng**: Phát hiện và cảnh báo 2 chỉ tiêu bất thường: Chỉ tiêu suy dinh dưỡng thấp còi trẻ em (NULL) tại TTYT Huyện X và Số lượt khám chữa bệnh BHYT (0) tại Trạm Y tế Xã Y. Gắn cờ cảnh báo chất lượng dữ liệu và lưu 2 mã chỉ tiêu vào bộ nhớ.
* **Lượt 2 (Turn 2)**:

  - **Người dùng hỏi**: *"Cán bộ nào phụ trách những chỉ tiêu đó ?"*
  - **Trạng thái ngữ cảnh (Context State)**: Đại từ *"những chỉ tiêu đó"* = 2 chỉ tiêu y tế bất thường ở Turn 1; thực hiện Multi-hop Join sang bảng `user_mission` và `user` để truy vết cán bộ.
  - **Hành vi kỳ vọng**: Trình bày họ tên công vụ, đơn vị và chức vụ của 2 cán bộ phụ trách theo dõi chỉ tiêu; tuân thủ nghiêm ngặt bảo vệ PII (không hiển thị SĐT, CCCD).
* **Lượt 3 (Turn 3)**:

  - **Người dùng bất ngờ đổi chủ đề**: *"Thế còn bên mảng giảm nghèo năm 2025 toàn tỉnh đạt bao nhiêu % ?"*
  - **Trạng thái ngữ cảnh (Context State)**: **Phát hiện Topic Shift**: Kích hoạt cơ chế **Xóa sạch và cô lập ngữ cảnh (Purge & Isolate Context)**. Xóa bỏ hoàn toàn điều kiện lọc dị thường null/zero và miền Y tế; khởi tạo phiên độc lập cho chỉ tiêu Tỷ lệ hộ nghèo năm 2025 toàn tỉnh.
  - **Hành vi kỳ vọng**: Truy vấn độc lập thành công số liệu chính thức: Toàn tỉnh năm 2025 tỷ lệ hộ nghèo đa chiều đạt 1.82% (giảm 0.65% so với năm 2024, hoàn thành vượt mức mục tiêu HĐND giao).

- **Đánh giá Audit**: [PASS - ĐÁNH GIÁ XUẤT SẮC] Đạt 5/5 tiêu chí. Test case hoàn hảo để kiểm tra khả năng chống ô nhiễm ngữ cảnh (Context Contamination).
- **Đánh giá của Bạn**:
  - [X]  **ĐẠT** (Giữ trọn chuỗi kịch bản)
  - [ ]  **YÊU CẦU SỬA**: __________________________________________________
