---
doc_id: "DOC-RENDER-AUTOMATION-GUIDE"
title: "Hướng Dẫn Quy Trình Automation Test Theo Mốc Thời Gian Với Hệ Thống Deploy Trên Render"
role: "GUIDE"
scope: "Scheduled Automation (/automation), Browser UI 10-Quest Single-Session Verification (/browser), Backend 20-Quest Suite & Warehouse Ground-Truth Cross-Check"
ssot_of: []
depends_on:
  - "IPGov_Chatbot/docs/output.md"
  - "render.yaml"
related_docs:
  - "IPGov_Chatbot/docs/BACKEND_RUN_GUIDE.md"
---

# HƯỚNG DẪN QUY TRÌNH AUTOMATION TEST THEO MỐC THỜI GIAN TRÊN RENDER

Tài liệu quy định chi tiết quy trình kiểm thử tự động theo lịch (`07:30`, `12:30`, `17:30`, `23:30` giờ Việt Nam) đối với hệ thống **IPGov Chatbot đã deploy trên Cloud Render**:
- **Frontend Render:** `https://ipgov-chatbot-frontend.onrender.com/`
- **Backend Render:** `https://ipgov-chatbot-backend.onrender.com`

---

## 1. Các Giới Hạn & Quy Tắc Bất Biến Khi Chạy Test

1. **Giới hạn cứng số lượng câu hỏi:**
   - **Backend Test:** Tối đa **20 quest** / đợt (`IPGov_Chatbot/tests/render_automation/backend_20_quests_runner.py`).
   - **UI Test (`/browser`):** Đúng **10 quest** / đợt (`IPGov_Chatbot/tests/render_automation/ui_10_quests_spec.json`).
   - **Nguồn câu hỏi:** Chỉ lấy từ `IPGov_Chatbot/docs/output.md`, 2 đợt feedback + phiên hiện tại, và `IPGov_Chatbot/tests/`.
2. **Quy tắc 1 Session Duy Nhất & Thiết lập Giao diện `/browser`:**
   - Khi mới truy cập `https://ipgov-chatbot-frontend.onrender.com/`, bắt buộc đợi **1–2 phút** để dịch vụ Render Free Tier khởi động hoàn tất.
   - Chỉnh **Zoom 80%** (`document.body.style.zoom = '0.8'`).
   - **Đóng tab lịch sử bên trái** (collapse sidebar lịch sử chat).
   - Toàn bộ **10 quest UI** phải được thực hiện liên tiếp trong **1 session duy nhất**.
3. **Quy trình 9 bước cho mỗi Prompt trên UI:**
   - **Bước 1:** Nhập prompt và gửi. Nếu hệ thống đang `thinking` (`ĐANG XỬ LÝ`) và chưa hiện xong đáp án thì chờ hệ thống output hoàn tất rồi mới chụp.
   - **Bước 2:** Chụp ảnh màn hình đáp án chính từ hệ thống.
   - **Bước 3:** Đọc toàn bộ nội dung đáp án trên UI.
   - **Bước 4:** Dò lại trực tiếp trong **Warehouse (`vna_wom_dev`)** xem đáp án có khớp 100% không.
   - **Bước 5:** Bấm thử **1–3 button** ngay trong đáp án (ticket thời gian `Quý 1`, `Quý 2`, `Quý 3`, `Năm 2026`, `31/03/2026`, `30/06/2026`, nút mở cây chỉ tiêu con `- (Xem chi tiết con)` hoặc nút gợi ý chỉ tiêu con).
   - **Bước 6:** Chụp lại ảnh đáp án sau khi bấm các button này (chờ hết thinking/loading mới chụp).
   - **Bước 7:** So sánh kết quả sau khi bấm button với dữ liệu đang có trong Warehouse.
   - **Bước 8:** Viết nhận xét cho prompt chính + đáp án sau khi bấm các button, **bắt buộc mở đầu bằng `'Correct'` hoặc `'Wrong'`**, ghi vào file nhật ký kèm **Tên đợt test + Thời gian test**.
   - **Bước 9:** Lặp lại tuần tự cho đến khi hết 10 câu trong danh sách.

---

## 2. Lệnh Chạy & Vị Trí File Nhật Ký Báo Cáo

### 🔹 Chạy trích xuất Ground Truth từ Warehouse & 20 Quests Backend:
```powershell
.\.venv\Scripts\python.exe -m IPGov_Chatbot.tests.render_automation.warehouse_ground_truth_checker
.\.venv\Scripts\python.exe -m IPGov_Chatbot.tests.render_automation.backend_20_quests_runner
```

### 🔹 Vị trí File Nhật Ký & Báo Cáo để Kiểm Tra:
- **File Nhật ký Kiểm toán Tổng hợp:** `IPGov_Chatbot/data/reports/render_automation/render_automation_audit_log.md`
- **File Snapshot Ground Truth từ Warehouse:** `IPGov_Chatbot/data/reports/render_automation/warehouse_ground_truth_snapshot.json`
- **Thư mục Ảnh chụp màn hình `/browser`:** `IPGov_Chatbot/data/reports/render_automation/screenshots/`
