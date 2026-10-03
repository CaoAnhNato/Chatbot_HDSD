# ADR-002: Khử Nhập Nhằng Ngữ Nghĩa Thực Thể, Quản Trị Kỳ Báo Cáo DWH & Chuẩn Hóa Phản Hồi Trong IPGov_Chatbot

- **Trạng thái:** Accepted
- **Ngày phê duyệt:** 2026-10-02
- **Người đề xuất:** Antigravity AI Assistant & Kỹ sư Trưởng
- **Phạm vi:** `IPGov_Chatbot/` (Module 03 Router, Module 04 Catalog, Module 08 Response, Next.js Frontend)

---

## 1. Bối Cảnh (Context) & Bằng Chứng Thực Nghiệm Từ CSDL `vna_wom_dev`

Trong quá trình nghiệm thu thực tế hệ thống `IPGov_Chatbot` trên CSDL PostgreSQL công ty (`vna_wom_dev`), các kiểm thử viên và kỹ sư trưởng đã phát hiện 5 điểm nghẽn nghiêm trọng:

1. **Lộ tên bảng CSDL kỹ thuật thô trong lời chào:** Khi người dùng mở đầu phiên chat hoặc hỏi về năng lực của hệ thống, chatbot hiển thị các tên bảng CSDL nội bộ (`mission`, `office_mission`, `fact_report_criteria`, `collection_form`, `user_mission`, `user`) gây khó hiểu cho cán bộ, chuyên viên nghiệp vụ.
2. **Lặp lại câu hỏi nguyên văn của người dùng & Sai định dạng số:** 
   - Phản hồi của chatbot nhúng nguyên văn câu hỏi vào cấu trúc `"Theo số liệu báo cáo đã phê duyệt năm 2026 của tỉnh Lâm Đồng, {user_question} đạt: {val}."`.
   - Câu hỏi mốc thời gian bị trả lời thành `"đạt: 2.026"`. Năm lịch 4 chữ số bị format dấu phân cách.
   - Dấu phân cách số chưa thống nhất: Cần dấu phẩy `,` cho hàng nghìn (`1,320`) và dấu chấm `.` cho phần thập phân (`12.5`).
3. **Bẫy cộng dồn lũy kế các kỳ báo cáo (Cumulative Quarter Duplication):**
   - **Bằng chứng thực nghiệm từ CSDL `vna_wom_dev`:** Khi truy vấn bảng `fact_report_criteria` và `report`, đơn vị `department_code = '68-1-01'` có 3 báo cáo được duyệt trong năm 2026 cho chỉ tiêu *"Doanh thu bình quân trong năm của một Trang trại nông nghiệp"*:
     * Quý 1 (`report_date = 2026-03-31`): giá trị = `620` (version 2)
     * 6 Tháng (`report_date = 2026-06-30`): giá trị = `1450` (version 1)
     * 9 Tháng (`report_date = 2026-09-30`): giá trị = `2200` (version 1)
   - Phép tính `SUM(value)` ngây thơ trước đây đã cộng $620 + 1,450 + 2,200 = 4,270$. Đây là phép cộng sai lệch nghiêm trọng giữa các kỳ báo cáo của cùng 1 đơn vị!
4. **Nhập nhằng ngữ nghĩa chỉ tiêu (Semantic Misattribution) do `ILIKE '%...%'`:**
   - Do dùng `ILIKE '%trang trại%'`, câu SQL đã gom chỉ tiêu doanh thu vào số lượng trang trại, trong khi chỉ tiêu số lượng *"Trang trại"* thực tế đang có giá trị `NULL`.
5. **Cộng sai các chỉ tiêu Non-Additive (Tỷ lệ %, Suất đầu tư, Bình quân):**
   - Việc mặc định áp dụng hàm `SUM` đối với các chỉ tiêu dạng tỷ lệ hoặc bình quân gây sai lệch toán học (ví dụ: cộng tỷ lệ 60% ở 3 huyện thành 180%).

---

## 2. Quyết Định Kiến Trúc (Decisions)

### 2.1. Chuẩn Hóa Lời Chào & Khả Năng Theo 4 Trụ Cột Nghiệp Vụ Công Vụ
- Bỏ 100% các tên bảng CSDL kỹ thuật khỏi câu trả lời chào hỏi và năng lực.
- Phân nhóm năng lực theo 4 trụ cột nghiệp vụ hành chính tỉnh Lâm Đồng:
  1. *Chỉ tiêu Kinh tế - Xã hội & Nông nghiệp*
  2. *Tiến độ Báo cáo & Tổng hợp Điều hành*
  3. *Danh mục Biểu mẫu Thu thập*
  4. *Chương trình, Đề án & Phân công Công tác*

### 2.2. Trích Xuất Ứng Viên Top-5 Bằng Hybrid RRF Trong RAM
- Thiết lập cố định **`TOP_K = 5`** candidates.
- Thuật toán xếp hạng: **Hybrid Reciprocal Rank Fusion (RRF)** kết hợp Dense Semantic Search (`AITeamVN/Vietnamese_Embedding_v2`) và Sparse Fuzzy Matching (`RapidFuzz` `token_set_ratio`).
- Ngưỡng cắt tin cậy: **`Score >= 60.0`**.

### 2.3. Quy Tắc Phân Định Tự Động Chọn vs Kích Hoạt Hỏi Lại (Confident Match vs Clarification)
- **Tự động chọn (Confident Match):** Khi Top 1 vượt trội với **`Score_Delta >= 0.10`** (giữa Top 1 và Top 2) hoặc Top 1 khớp chính xác tên 100%.
- **Hỏi lại (Active Clarification Chips):** Khi câu hỏi quá vắn tắt ($< 2$ từ, ví dụ chỉ gõ *"trang trại"*, *"muối"*) HOẶC **`Score_Delta < 0.10`** (mơ hồ ngữ nghĩa giữa số lượng và doanh thu).

### 2.4. Khử Trùng Lặp Kỳ Báo Cáo Bằng CTE Window Function Theo Thời Gian
- Để chỉ lấy số liệu của **kỳ báo cáo mới nhất** của từng đơn vị trong năm 2026, câu lệnh SQL bắt buộc sử dụng CTE Window Function:
  ```sql
  WITH ranked_facts AS (
      SELECT f.*,
             ROW_NUMBER() OVER (
                 PARTITION BY f.department_code, f.name 
                 ORDER BY f.report_date DESC, f.version DESC
             ) as rn
      FROM dwh_internal.fact_report_criteria f
      WHERE f.tenant_code = '68' 
        AND f.year_code = '2026' 
        AND f.report_status = 'approved'
  )
  ```
- Lọc `WHERE rn = 1`: Đảm bảo với đơn vị `68-1-01`, hệ thống lấy đúng số liệu Quý 3 mới nhất (`2,200`), loại bỏ việc cộng dồn Quý 1 (`620`) và Quý 2 (`1,450`).

### 2.5. Phòng Chống Trượt Dữ Liệu Bẩn Bằng Unicode NFC & `TRIM(...) ILIKE TRIM(...)`
- *Tầng Python:* Chuẩn hóa chuỗi ứng viên sang Unicode chuẩn dựng sẵn NFC trước khi truyền vào SQL: `unicodedata.normalize('NFC', name.strip())`.
- *Tầng SQL:* Sử dụng `TRIM(f.name) ILIKE TRIM('<Candidate Name>')` (**tuyệt đối không có dấu `%` ở 2 đầu**). Bỏ qua khác biệt chữ hoa/thường, loại trừ khoảng trắng thừa, và không nuốt chuỗi con khác.

### 2.6. Giải Quyết Bài Toán "Chicken-and-Egg" Bằng Truy Vấn Đồng Thời Đa Ứng Viên (Single-Query Multi-Candidate Retrieval)
- Trong 1 lần thực thi SQL duy nhất, truy vấn đồng thời cả 5 ứng viên trong Top-K:
  ```sql
  WHERE rn = 1 
    AND TRIM(f.name) ILIKE ANY(ARRAY['Trang trại', 'Doanh thu bình quân trong năm của một Trang trại nông nghiệp', ...])
  ```
- **Lợi ích:** 0ms round-trip phụ. PostgreSQL trả về kết quả của cả chỉ tiêu chính (`Trang trại` $\to$ `NULL`) và chỉ tiêu liên quan (`Doanh thu bình quân...` $\to$ `2,200`). Synthesizer báo rõ chỉ tiêu chính bị NULL và lấy ngay chỉ tiêu liên quan có dữ liệu NOT NULL làm gợi ý, đảm bảo 100% gợi ý là số liệu có thật.

### 2.7. Phân Giải Phạm Vi Hành Chính Đa Cấp
- Gọi `duckdb_semantic_catalog.resolve_administrative_scope(query)`:
  - Nếu câu hỏi chỉ định đơn vị cụ thể (Sở, Chi cục): Tiêm `AND f.department_code = '{dept_code}'`.
  - Nếu là câu hỏi toàn tỉnh: Giữ `f.tenant_code = '68'`.
- Phản hồi ghi rõ xuất xứ số liệu: *"Theo báo cáo của [Tên Đơn Vị]..."* hoặc *"Số liệu toàn tỉnh Lâm Đồng..."*.

### 2.8. Xử Lý Chuyên Biệt Cho Chỉ Tiêu Non-Additive (Tỷ Lệ %, Bình Quân, Suất Đầu Tư)
- Nếu tên hoặc đơn vị chứa `"tỷ lệ"`, `"bình quân"`, `"suất"`, `"%"`, `"triệu đồng / người"`:
  - **Tuyệt đối cấm dùng `SUM`**.
  - Nếu có nhiều đơn vị báo cáo: Hiển thị Bảng phân rã (Breakdown Table) theo từng đơn vị kèm `AVG` tham khảo (chú thích rõ "Trung bình cộng các đơn vị").
  - Nếu chỉ có 1 đơn vị: Hiển thị trực tiếp giá trị của đơn vị đó.

### 2.9. Quy Chuẩn Định Dạng Số & Năm Lịch
- Hàng nghìn dùng dấu phẩy `,` (`1,320`).
- Thập phân dùng dấu chấm `.` (`12.5`).
- Năm lịch 4 chữ số (`2026`) giữ nguyên, không thêm dấu phân cách.
- Câu hỏi về năm: Trả lời tự nhiên rõ ràng: *"Số liệu báo cáo và chỉ tiêu điều hành hiện tại của hệ thống đang được ghi nhận cho **năm 2026**."*

### 2.10. Giao Diện Khối SQL Next.js
- Thẻ `<details>` mặc định đóng (`open = false`), chỉ mở rộng khi người dùng click vào thanh tiêu đề *"🔍 Câu lệnh SQL truy xuất DWH (Nhấn để xem)"*.

---

## 3. Hệ Quả & Lợi Ích (Consequences)

- **Độ chính xác nghiệp vụ (EX):** Loại bỏ 100% việc cộng dồn sai lệch giữa các kỳ báo cáo trong năm (chỉ lấy kỳ mới nhất) và không cộng dồn các chỉ tiêu tỷ lệ/bình quân.
- **Tốc độ phản hồi:** Áp dụng truy vấn đồng thời đa ứng viên, tiết kiệm 100% round-trip phụ khi xử lý chỉ tiêu NULL.
- **Trải nghiệm người dùng:** Giao diện gọn gàng, định dạng số chuẩn xác, văn phong hành chính tự nhiên.
