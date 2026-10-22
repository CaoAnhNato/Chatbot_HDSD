---
doc_id: "DOC-RUN-GUIDE"
title: "Hướng Dẫn Khởi Chạy Local & Kiểm Thử Nhanh IPGov Chatbot"
role: "GUIDE"
scope: "Backend CLI, Web Frontend UI, Test Bench & Quick Test Prompts"
ssot_of: []
depends_on:
  - "IPGov_Chatbot/blueprints/00_TECH_STACK_VA_KIEN_TRUC_TONG_THE.md"
related_docs:
  - "IPGov_Chatbot/docs/update.md"
---

# HƯỚNG DẪN KHỞI CHẠY LOCAL & KIỂM THỬ NHANH IPGOV CHATBOT

Tài liệu hướng dẫn vận hành tối giản phục vụ trực tiếp quá trình phát triển và kiểm thử nội bộ hệ thống **IPGov Chatbot**.

---

## 1. Khởi Chạy Nhanh Toàn Bộ Hệ Thống (Local Quick Start)

Mở 2 cửa sổ Terminal (PowerShell):

### 🔹 Bước 1: Khởi động Backend (Port 8000)
```powershell
.\.venv\Scripts\python.exe -m IPGov_Chatbot.run_server
```
* **Mặc định:** Tự động nạp mô hình Embedding `SentenceTransformer` từ cache RAM cục bộ (Offline 100%, tốc độ < 1ms, 0 cuộc gọi mạng ngoài).
* **Tùy chọn cờ lệnh (CLI Options):**
  * `--local-embedding`: Cưỡng chế chạy Local RAM (khuyên dùng trên máy trạm dev).
  * `--remote-embedding`: Cưỡng chế kết nối Remote Hugging Face Space ZeroGPU (dành cho Cloud Render 512MB RAM).

### 🔹 Bước 2: Khởi động Frontend Web (Port 3000)
```powershell
cd IPGov_Chatbot/frontend
npm run dev
```

---

## 2. Đường Dẫn Truy Cập Trực Quan

| Giao Diện / Dịch Vụ | Đường Dẫn URL | Mục Đích Sử Dụng |
| :--- | :--- | :--- |
| 💻 **Web Chat Frontend** | [http://localhost:3000](http://localhost:3000) | Giao diện trò chuyện chính thức: Tra cứu số liệu, kế thừa hội thoại đa lượt, xem khối SQL thu gọn `<details>`, Action Chips gợi ý. |
| 🧪 **Web Test Bench GUI** | [http://127.0.0.1:8000/bench](http://127.0.0.1:8000/bench) | Giao diện kiểm thử kỹ thuật: Chọn nhanh 6 vai trò HBAC, test an ninh, theo dõi 8-Stage Execution Stepper và gắn ghi chú báo lỗi `📝 Báo lỗi & Note`. |
| 📖 **Swagger OpenAPI** | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) | Tra cứu và test trực tiếp các REST API endpoints. |
| 🩺 **Kiểm tra Sức khỏe** | [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health) | Kiểm tra trạng thái `readiness` (`warming_up` -> `ready`) và 5 thành phần core. |

> [!WARNING]
> Trên Windows, **bắt buộc truy cập** bằng `http://localhost:3000` hoặc `http://127.0.0.1:8000/bench`. **Không click vào đường dẫn `http://0.0.0.0:8000`** vì hệ điều hành Windows và Chromium sẽ chặn địa chỉ `0.0.0.0` với lỗi `ERR_ADDRESS_INVALID`.

---

## 3. Danh Sách Câu Hỏi Kiểm Thử Nhanh (Demo Showcase 4 Lĩnh Vực DWH Lâm Đồng 2026)

Dùng các câu hỏi mẫu dưới đây để copy-paste trực tiếp lên giao diện Web Chat (`http://localhost:3000`) hoặc Test Bench (`/bench`):

| Lĩnh Vực Nghiệp Vụ | Mã | Câu Hỏi Kiểm Thử (Prompt Test) | Kết Quả Kỳ Vọng (Ground Truth) | Hành Vi Hiển Thị UI |
| :--- | :---: | :--- | :--- | :--- |
| **1. Chỉ tiêu KTXH & Nông nghiệp** | `KT-01` | `Tổng các hộ sản xuất muối năm 2026 của tỉnh là bao nhiêu?` | **1,320** hộ (`report_status='approved'`) | Trả lời trực diện, định dạng số chuẩn `1,320`, khối `<details>` SQL thu gọn, chips gợi ý. |
| **1. Chỉ tiêu KTXH & Nông nghiệp** | `KT-02` | `Kinh phí thực hiện khuyến công năm 2026 là bao nhiêu?` | **643,212** ngàn đồng (3 chỉ tiêu con) | Bảng Markdown tổng hợp 3 dòng số liệu, khối `<details>` SQL thu gọn. |
| **1. Hội thoại Đa lượt (Multi-turn)** | `MT-01` | *Turn 1:* `Tổng các hộ sản xuất muối năm 2026`<br>*Turn 2:* `Thế còn diện tích sản xuất muối?` | Tự động kế thừa `year_code='2026'`, `tenant_code='68'` ở Turn 2. | Không hỏi lại năm/tỉnh ở Turn 2, trả về đúng diện tích muối (105 ha). |
| **2. Tình hình Báo cáo & Tổng hợp** | `BC-01` | `Trạng thái các đợt nộp báo cáo của Sở Nông nghiệp hiện nay thế nào?` | 9 đợt nộp (6 đợt `approved`, 3 đợt `draft`) | Bảng Markdown 4 cột, trạng thái Việt hóa (**Đã phê duyệt** / **Bản nháp**). |
| **2. Tình hình Báo cáo & Tổng hợp** | `BC-02` | `Hiện có bao nhiêu báo cáo đã được phê duyệt trong năm 2026?` | Tổng số: **6** báo cáo đã duyệt | Phản hồi trực diện số lượng báo cáo đã phê duyệt của tỉnh. |
| **3. Biểu mẫu Thu thập Số liệu** | `BM-01` | `Hiện tại có những biểu mẫu thu thập thông tin nào đang kích hoạt?` | 0 bản ghi kỳ 2026 (CSDL chưa nạp form kỳ này) | Thông báo trung thực (Zero Hallucination) kỳ 2026 chưa có biểu mẫu, gợi ý tra cứu chỉ tiêu. |
| **4. Nhiệm vụ & Đề án Trọng tâm** | `NV-01` | `Danh mục các nhiệm vụ trọng tâm năm 2026 của tỉnh Lâm Đồng?` | 5 nhiệm vụ đang triển khai | Bảng Markdown danh sách nhiệm vụ, trạng thái **Đang triển khai**. |
| **4. Cán bộ Phụ trách Nhiệm vụ** | `CB-01` | `Cán bộ nào phụ trách nhiệm vụ diêm nghiệp năm 2026?` | Nguyễn Thị Thúy Lành (BA) & Phường Bắc Gia Nghĩa (QTV) | Bảng Markdown thông tin cán bộ, chức vụ, đơn vị và nhiệm vụ phụ trách. |
| **5. Chặn Đối Kháng & An Ninh AST** | `SEC-01` | `DROP TABLE fact_report_criteria; --` | Chặn đứng tại AST Guardrail | Thông báo vi phạm an toàn, từ chối an toàn, không gửi tới CSDL. |
| **6. Câu hỏi Ngoài Phạm Vi DWH** | `OOD-01` | `Thủ tục cấp đổi thẻ Căn cước công dân gắn chip làm như thế nào?` | Bị chặn bởi `ScopePrechecker` | Từ chối lịch sự, giải thích rõ DWH chỉ phục vụ số liệu chỉ tiêu/nhiệm vụ tỉnh. |
| **7. Kiểm Thử Bất Biến Ngôn Ngữ (INV)** | `INV-01` | `Kính gửi trợ lý, vui lòng thống kê giúp sản lượng muối tỉnh 68 năm 2026.` | Cùng 1 SQL và số liệu như câu chuẩn: **643,212** kg | Chuẩn hóa về CanonicalQueryFrameDTO, khối `<details>` SQL đồng nhất 100%. |
| **8. Phân Giải Chỉ Tiêu Đa Nghĩa** | `ROB-01` | `Cho tôi xem tình hình HTX nông nghiệp năm 2026.` | Phát hiện cả Hợp tác xã và Liên hiệp HTX | Dừng sinh SQL, kích hoạt Clarification Chips với 2 options cụ thể. |
| **9. Chống Bẫy Viết Tắt Đa Nghĩa** | `ROB-02` | `Số LĐ nông thôn được tạo việc làm năm 2026?` | Phân định *"LĐ"* là *"Lao động"*, không nhầm Lâm Đồng | Truy vấn chỉ tiêu lao động theo tenant '68', không gán sai mã tỉnh. |
| **10. Chuyển Đổi Địa Bàn Động** | `ROB-03` | *Turn 1:* `Lâm Đồng có bao nhiêu HTX?`<br>*Turn 2:* `Thế còn TP.HCM?` | Tra cứu động bảng `catalog_tenants` ra tenant `'79'` | Không dùng regex cứng, cập nhật mượt mà State đa lượt giữa các tỉnh. |
| **11. Danh Mục Tỉnh & Loại Trừ Địa Bàn** | `DIM-01` | `Ngoài tỉnh Lâm Đồng ra thì còn tỉnh nào khác không?` | 33 tỉnh/thành phố khác (`dwh_internal.province` loại trừ Lâm Đồng) | Định tuyến sang Dimension Plane `province`, bảng Markdown 33 tỉnh kèm lưu ý số liệu DWH đang phục vụ tỉnh Lâm Đồng. |
| **11. Khám Phá Danh Mục Toàn Bộ Tỉnh** | `DIM-02` | `Hệ thống hiện có những tỉnh nào?` | Toàn bộ 34 tỉnh/thành phố (`dwh_internal.province`) | Bảng Markdown 34 tỉnh/thành phố kích hoạt trong DWH. |
| **12. Khám Phá Danh Mục Chỉ Tiêu** | `DIM-03` | `Kho dữ liệu có những chỉ tiêu nào?` | Danh mục chỉ tiêu (`dwh_internal.criteria`) | Định tuyến sang `METADATA_EXPLORATION`, hiển thị bảng chỉ tiêu thay vì rơi vào Fact search rỗng. |
| **13. Loại Trừ Nhiều Tỉnh Thành (Liên Từ)** | `DIM-04` | `Ngoài tỉnh Lâm Đồng và Bình Thuận ra thì còn tỉnh nào?` | 32 tỉnh/thành phố khác | Tự động phân tách liên từ `và`, sinh `NOT ILIKE` cho cả 2 tỉnh, loại bỏ hoàn toàn khỏi kết quả. |
| **14. Hỏi Địa Bàn Hành Chính & Đếm Tỉnh** | `DIM-05` | `Hiện tại hệ thống đang có bao nhiêu tỉnh thành?` | Tổng số 34 tỉnh thành | Trả lời trực diện số lượng và danh mục địa bàn, không bị ngộ nhận sang Fact numeric aggregation. |
| **15. Câu Hỏi Toán Học / Ngoài DWH** | `MATH-01` | `3 mũ 2 là nhiêu ?` | Kết quả: **9** (OUT_OF_SCOPE) | Trả lời trực tiếp phép tính lũy thừa, không sinh lỗi SQL, không gán nhãn chỉ tiêu DWH ảo. |
| **16. Tra Cứu Đơn Vị Qua User/Office** | `DEPT-01` | `chỉ tiêu liên kết sản xuất đang do đơn vị nào thực hiện ?` | **UBND Tỉnh Lâm Đồng** / **Chi cục** | Phân giải qua `dwh_internal.user` và `dwh_internal.office` (mã 68-1-01), không phụ thuộc bảng deparment (0 dòng). |
| **17. Chỉ Tiêu Chưa Phát Sinh Số Liệu** | `CRIT-01` | `dữ liệu cải cách 1 đang do tỉnh nào thực hiện ?` | Chỉ tiêu trong danh mục nhưng chưa có số liệu | Nhận diện đúng thuộc tính, giải thích rõ chưa phát sinh số liệu, tuyệt đối không dump 34 tỉnh. |
| **18. Khám Phá Quan Hệ Tỉnh - Xã Phường** | `WARD-01` | `tỉnh Lâm Đồng có bao nhiêu xã phường` | **124** xã, phường, thị trấn | Truy vấn trực tiếp `dwh_internal.ward` theo `province_code = '68'`, bảng danh mục 124 đơn vị. |
| **19. Khám Phá Quan Hệ Đơn Vị - Nhiệm Vụ** | `OFF-01` | `Chi cục phụ trách những nhiệm vụ nào ?` | Diêm nghiệp & Phát triển nông thôn | Truy vấn `dwh_internal.office_mission` và `dwh_internal.office`, liệt kê nhiệm vụ phụ trách. |
| **20. Khắc Phục Lỗi Synthesizer NULL** | `NULL-01` | `Số liệu chỉ tiêu liên kết sản xuất năm 2026 là bao nhiêu ?` | Giá trị `NULL` (chưa có số liệu) | Thông báo chính xác chỉ tiêu chưa có số liệu được duyệt, không ghi đè bằng tên chỉ tiêu. |

---

## 4. Xử Lý Sự Cố Nhanh Thường Gặp

### ⚠️ Lỗi xung đột cổng 8000 (`WinError 10048` - Socket already in use)
Có tiến trình Python/Uvicorn cũ chưa thoát:
```powershell
# Tìm PID tiến trình chiếm cổng 8000
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object LocalPort, OwningProcess

# Tắt tiến trình theo PID tìm được
Stop-Process -Id <PID> -Force
```

### ⚠️ Lệnh chạy kiểm thử nhanh bộ 15 Test Cases đại diện
```powershell
.\.venv\Scripts\python.exe -m pytest IPGov_Chatbot/tests/test_warehouse_agent_e2e.py -v
```

---

## 5. Bộ Kiểm Thử Đa Bảng & Chống Bẫy Template (Multi-Hop & Robustness Showcase)

Tệp dữ liệu benchmark chính thức: `IPGov_Chatbot/evaluations/golden_benchmark_multihop_and_robustness.json` (60 Golden Quests).

### 5.1. Phân Hệ A: Multi-Table JOINs (35 Quests)
- **Mục tiêu:** Liên kết 11 bảng chiều (`criteria`, `mission`, `office`, `scope`, `user`, `ward`...) cùng bảng Fact/Report.
- **Quy tắc thực thi:** `department_name` tra cứu từ bảng `dwh_internal."user"`, lĩnh vực nghiệp vụ tra cứu từ `dwh_internal.scope`.
- **Câu hỏi mẫu:**
  1. `Văn phòng nông nghiệp đang phụ trách những nhiệm vụ nào và thuộc lĩnh vực gì?`
  2. `Chỉ tiêu tổng sản lượng muối do văn phòng nào thu thập và thuộc lĩnh vực quản lý nhà nước nào?`
  3. `Huyện nào có nhiều xã/phường nhất và tổng số xã/phường là bao nhiêu?`

### 5.2. Phân Hệ B: Anti-Template Fast-Track Hijacking (15 Quests)
- **Mục tiêu:** Ngăn chặn bẫy tự động bung danh mục 34 tỉnh thành khi câu hỏi có từ khóa "tỉnh" nhưng hỏi về vị từ thực thể/chỉ tiêu cụ thể.
- **Câu hỏi mẫu:**
  1. `Dữ liệu cải cách 1 đang do tỉnh nào thực hiện?` (Kỳ vọng: Hỏi làm rõ / không bung danh mục 34 tỉnh)
  2. `Chỉ tiêu an toàn lao động năm 2026 đang do sở ban ngành nào thu thập?`
  3. `Tỉnh nào có sản lượng muối trên 20.000 tấn trong năm 2026?`

### 5.3. Phân Hệ C: Anti-Out-of-Scope Math Traps (10 Quests)
- **Mục tiêu:** Chặn đứng câu hỏi toán học phổ thông, câu hỏi thường thức ngoài kho dữ liệu DWH, tránh quét bảng Fact sinh chỉ tiêu ảo.
- **Câu hỏi mẫu:**
  1. `3 mũ 2 là nhiều?` (Kỳ vọng: Chặn ngoài phạm vi, hỗ trợ tính toán $3^2 = 9$)
  2. `Tính giúp tôi căn bậc hai của 144 bằng bao nhiêu?` (Kỳ vọng: Chặn ngoài phạm vi, kết quả 12)
  3. `Thời tiết ngày mai tại Đà Lạt như thế nào?` (Kỳ vọng: Từ chối lịch sự ngoài phạm vi DWH)

### 5.4. Lệnh Chạy Kiểm Định Độc Lập 3 Cổng Nghiệm Thu
```powershell
.\.venv\Scripts\python.exe -m IPGov_Chatbot.scripts.verify_multihop_robustness
```

---

## 6. Danh Mục 6 Nhóm Câu Hỏi Kiểm Thử Mẫu (Fact Report Criteria & Abstract Patterns Showcase)

Căn cứ: Kế hoạch triển khai [plan_update_fact_report_criteria_logic.md](file:///c:/Users/Admin/.gemini/antigravity/brain/19b9ffbb-0559-4d64-8089-d369d59d3636/plan_update_fact_report_criteria_logic.md).

| Mã Pattern | Tên Pattern Trừu Tượng | Câu Hỏi Kiểm Thử Mẫu (Test Prompt) | Ý Định Phân Loại | Kết Quả Định Tuyến & Phản Hồi Kỳ Vọng |
| :--- | :--- | :--- | :--- | :--- |
| **P-01** | `MONTHLY_COLLECTION_METRIC_LISTING` | `Cho tôi các chỉ tiêu thu thập được trong tháng 9 năm nay` | `DIMENSION_LISTING` | Lọc `EXTRACT(MONTH FROM report_date) = 9` & `year_code = '2026'`, `report_status = 'approved'`, CTE `rn = 1`. Trả về Bảng Markdown 5 cột: `STT \| Tên chỉ tiêu \| Giá trị mới nhất \| Đơn vị thực hiện \| Nhiệm vụ trọng tâm`. |
| **P-02** | `DATE_RANGE_CUMULATIVE_METRIC_DISCOVERY` | `Từ tháng 3 đến hiện tại thì đã thu thập được các chỉ tiêu nào ?` | `DIMENSION_LISTING` | Lọc `report_date >= '2026-03-01'`, `report_status = 'approved'`, lấy snapshot mới nhất từng chỉ tiêu. Bảng Markdown 5 cột. |
| **P-03** | `SYSTEM_WIDE_CRITERIA_INVENTORY` | `Hiện tại hệ thống đang có các chỉ tiêu nào ?` | `METADATA_EXPLORATION` | Trả về `DISTINCT` toàn bộ danh mục chỉ tiêu đang có trong kho dữ liệu với snapshot mới nhất (`rn = 1`), `report_status = 'approved'`, kèm đơn vị và nhiệm vụ. |
| **P-04** | `SINGLE_METRIC_LATEST_SNAPSHOT` | `Chỉ tiêu chăn nuôi hiện tại là bao nhiêu ?` | `METRIC_POINT_INQUIRY` | Ánh xạ chỉ tiêu `chan_nuoi4` (trang trại). Loại trừ bản dự thảo 21/09/2026 (`draft`, giá trị 67). Trả về chính xác giá trị **64**, `Đơn vị thực hiện : Chi cục`, `Nhiệm vụ trọng tâm : Phát triển nông thôn`, Ngày báo cáo: `30/09/2026`. |
| **P-05** | `AMBIGUOUS_TOPIC_CLARIFICATION_HTX` | `Chỉ tiêu hợp tác xã` | `METRIC_POINT_INQUIRY` | Router phát hiện đa nghĩa (`ambiguity_status = 'AMBIGUOUS'`). Sinh Clarification Chips: `["HTX nông nghiệp", "Liên hiệp HTX nông nghiệp", "Số HTX nông nghiệp hoạt động hiệu quả tốt"]`. |
| **P-06** | `AMBIGUOUS_TOPIC_CLARIFICATION_OCOP` | `Chỉ tiêu OCOP` | `METRIC_POINT_INQUIRY` | Router phát hiện đa nghĩa (`ambiguity_status = 'AMBIGUOUS'`). Sinh Clarification Chips: `["Chủ thể sản phẩm OCOP 3 sao", "Chủ thể sản phẩm OCOP 4 sao", "Tổng số sản phẩm OCOP"]`. |

### 6.1. Hướng Dẫn Thao Tác Trực Quan Trên Test Bench `/bench`
1. Khởi động backend: `.\.venv\Scripts\python.exe -m uvicorn IPGov_Chatbot.main:app --host 127.0.0.1 --port 8000`
2. Truy cập trình duyệt: `http://127.0.0.1:8000/bench`
3. Nhập lần lượt các câu hỏi mẫu P-01 đến P-06 vào khung chat và xác nhận phản hồi giao diện.

### 6.2. Lệnh Chạy Bộ Kiểm Thử Tự Động 6 Mẫu Hình
```powershell
.\.venv\Scripts\python.exe -m pytest IPGov_Chatbot/tests/test_fact_report_criteria_logic.py -v
```

---

## 7. Bộ Kiểm Thử Bất Biến Ngôn Ngữ, Mở Rộng Thời Gian & Phân Giải Chỉ Tiêu Đồng Âm (Perturbation Cascade Showcase - 41 Quests - Plan V4)

Căn cứ: Kế hoạch triển khai [plan_deduplicate_and_disambiguate_criteria.md](file:///c:/Users/Admin/.gemini/antigravity/brain/0ae5dc71-4d22-4843-9164-4d658d8881e7/plan_deduplicate_and_disambiguate_criteria.md) (Bản cập nhật V4).

| Nhóm Kiểm Thử | Mã Mẫu | Câu Hỏi Đối Kháng Tiêu Biểu | Dải Thời Gian / Chủ Đề | Kết Quả Định Tuyến & Hành Vi UI Kỳ Vọng |
| :--- | :---: | :--- | :--- | :--- |
| **Dải T1 – T7** | `T-EXT-01` | `chỉ tiêu thu thập từ tháng 1 đến 7` *(bỏ "các", bỏ "năm nay")* | `2026-01-01` $\to$ `2026-07-31` | `DIMENSION_LISTING`, Bảng 6 cột chuẩn gồm 114 bản ghi DWH, khối `<details>` SQL `WITH ranked_facts AS (...)`. |
| **Nửa đầu năm** | `T-EXT-02` | `nửa đầu năm có những chỉ tiêu nào` *(đảo thời gian lên đầu)* | `2026-01-01` $\to$ `2026-06-30` | `DIMENSION_LISTING`, Bảng 6 cột chuẩn gồm 114 bản ghi đã duyệt, đồng nhất giữa mọi biến thể ngữ pháp. |
| **Quý 2** | `T-EXT-03` | `trong quý hai có những chỉ tiêu nào` *(chữ số thành chữ viết)* | `2026-04-01` $\to$ `2026-06-30` | `DIMENSION_LISTING`, Bảng 6 cột chuẩn gồm 114 bản ghi đã duyệt, Stream B phân giải chữ "quý hai" chuẩn xác. |
| **T9 đến hết năm**| `T-EXT-04` | `tháng 9 đến cuối năm chỉ tiêu` *(rút gọn tối đa)* | `2026-09-01` $\to$ `2026-12-31` | `DIMENSION_LISTING`, Bảng 6 cột chuẩn gồm 107 bản ghi đã duyệt trong quý 3-4/2026. |
| **T4 đến T9 (Mới)**| `T-EXT-05` | `từ tháng 4 đến tháng 9 có các chỉ tiêu nào ?` *(Prompt người dùng)* | `2026-04-01` $\to$ `2026-09-30` | `DIMENSION_LISTING`, Bảng 6 cột chuẩn gồm 114 bản ghi DWH, 17 nhóm chỉ tiêu đồng âm (Chăn nuôi, Đang hoạt động...) được phân định rõ ràng bằng cột `Nhóm chỉ tiêu`. |
| **Tập rỗng (Empty)**| `P-EMPTY-01`| `Các chỉ tiêu thu thập trong tháng 1 năm 2024` | Kỳ rỗng số liệu (`0` dòng) | Thông báo trung thực không có dữ liệu đã duyệt trong kỳ, 0 hallucination, 0 lỗi 500. |
| **Đơn chỉ tiêu lá**| `P-INV-01` | `năm nay chỉ tiêu chăn nuôi` *(hoán vị trật tự từ)* | `chan_nuoi4` (trang trại) | `METRIC_POINT_INQUIRY`, Đủ 5 trường chuẩn, Giá trị: **64**, Chi cục PTNT, Ngày: 30/09/2026. |
| **Làm rõ đa nghĩa** | `P-INV-02` | `HTX có những chỉ tiêu nào` *(viết tắt chuyên môn)* | Từ viết tắt `HTX` | `ClarificationEngine` kích hoạt Active Action Chips với 3 chỉ tiêu HTX nông nghiệp. |

### 7.1. Cấu Trúc Bảng 6 Cột Chuẩn Hóa
```markdown
| STT | Tên chỉ tiêu | Nhóm chỉ tiêu | Giá trị mới nhất | Đơn vị thực hiện | Nhiệm vụ trọng tâm |
| :---: | :--- | :--- | :---: | :--- | :--- |
| 1 | Chăn nuôi | Số lượng HTX phân theo lĩnh vực | **25** | Chi cục | Phát triển nông thôn |
| 2 | Chăn nuôi | Tổng số LHHTX phân theo lĩnh vực | **0** | Chi cục | Phát triển nông thôn |
| 3 | Chăn nuôi | Tổng số lượng TT phân theo lĩnh vực | **64** | Chi cục | Phát triển nông thôn |
| 4 | Chăn nuôi | Tổng số THT phân theo lĩnh vực | **144** | Chi cục | Phát triển nông thôn |
```

### 7.2. Lệnh Chạy Bộ Kiểm Thử Tự Động & Thẩm Định Độc Lập
```powershell
# 1. Kiểm định ma trận 17 nhóm chỉ tiêu đồng âm (41 bản ghi DWH):
.\.venv\Scripts\python.exe IPGov_Chatbot/scripts/verify_multicategory_disambiguation.py

# 2. Chạy bộ test hồi quy toàn diện:
.\.venv\Scripts\python.exe -m pytest IPGov_Chatbot/tests/test_audit_fixes_subagent2.py IPGov_Chatbot/tests/test_fact_report_criteria_logic.py -v

# 3. Kiểm tra an toàn import:
.\.venv\Scripts\python.exe -c "import IPGov_Chatbot.main; print('Import Verified!')"
```

---

## 8. Bộ Kiểm Thử Thời Gian Lũy Kế Đầu Năm (YTD), Gỡ Bỏ LIMIT Ngầm & Hiển Thị Tức Thì 0ms (Unbounded & Instant Warehouse Output Showcase)

Căn cứ: Kế hoạch triển khai [plan_temporal_ytd_and_unbounded_instant_warehouse_output.md](file:///C:/Users/Admin/.gemini/antigravity/brain/0ae5dc71-4d22-4843-9164-4d658d8881e7/plan_temporal_ytd_and_unbounded_instant_warehouse_output.md).

| Mã Ca Kiểm Thử | Câu Hỏi Kiểm Thử Mẫu (Test Prompt) | Bộ Lọc Thời Gian Chuẩn Hóa | Kết Quả Định Tuyến & Hành Vi UI Kỳ Vọng |
| :---: | :--- | :--- | :--- |
| **YTD-01** | `Số lượng chỉ tiêu thu thập được từ đầu năm tới nay` | `date_from = '2026-01-01'`, `date_to = '2026-12-31'` | `DIMENSION_LISTING`, SQL không có `LIMIT 50`, trả về đầy đủ **114 bản ghi** trên bảng 6 cột chuẩn, hiển thị tức thì (`0ms`). |
| **YTD-02** | `Các chỉ tiêu thu thập từ đầu năm đến tháng 6` | `date_from = '2026-01-01'`, `date_to = '2026-06-30'` | `DIMENSION_LISTING`, trả về đầy đủ **114 bản ghi** phát sinh trong 6 tháng đầu năm 2026, không cắt trang 5 dòng. |
| **RNG-01** | `Các chỉ tiêu thu thập trong giai đoạn 3/2026 - 06/2026` | `date_from = '2026-03-01'`, `date_to = '2026-06-30'` | `DIMENSION_LISTING`, trả về đầy đủ **114 bản ghi** đồng nhất với `YTD-01`, hiển thị tức thì (`0ms`) trong khung cuộn dọc `SmartTable`. |
| **UNB-01** | `Danh sách các phường xã thuộc tỉnh Lâm Đồng` | Không giới hạn (`limit = None`) | `METADATA_EXPLORATION` (`ward`), trả về toàn bộ **> 50 đơn vị hành chính cấp xã/phường** không bị cắt ở 50 dòng. |

### 8.1. Lệnh Chạy Kiểm Thử Tự Động YTD & Unbounded Output
```powershell
.\.venv\Scripts\python.exe -m pytest IPGov_Chatbot/tests/test_temporal_ytd_and_unbounded.py -v -s
```

---

## 9. Bộ Kiểm Thử Toàn Diện Đặc Tả Nghiệp Vụ `REQ-Q01` đến `REQ-Q04` (`SC-1.1` $\to$ `SC-4.2`) & Cửa Sổ Pop-up Sơ Đồ Cây Phân Cấp (`docs/output.md`)

Căn cứ: Đặc tả nghiệp vụ và phân cấp dữ liệu [output.md](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/docs/output.md).

| Mã Yêu Cầu / Kịch Bản | Câu Hỏi Kiểm Thử Mẫu (Test Prompt) | Kết Quả Định Tuyến & Hành Vi UI Kỳ Vọng |
| :---: | :--- | :--- |
| **REQ-Q01 / SC-1.1** | `Số lượng chỉ tiêu thu thập được trong nửa đầu năm 2026 là bao nhiêu?` | `DIMENSION_LISTING`, `date_from='2026-01-01'`, `date_to='2026-06-30'`. Hiển thị **duy nhất 1 bảng Cấp 1 (9 dòng)** với đúng 6 cột chuẩn (`STT \| Tên chỉ tiêu Cấp 1 \| Loại cấu trúc \| Giá trị mới nhất \| Đơn vị thực hiện \| Nhiệm vụ trọng tâm`), các nhóm cha hiển thị nút **`- (Xem chi tiết con)`** mở Pop-up Tree Modal. |
| **SC-1.2** | `Các chỉ tiêu thu thập trong tháng 2 năm 2026 là gì?` | `DIMENSION_LISTING` (`month_filter=2`). Phản hồi trung thực chưa phát sinh bản ghi phê duyệt trong kỳ tháng 02/2026, gợi ý tra cứu năm **2026**. |
| **REQ-Q02 (Đơn lá)** | `Cho tôi xem số liệu chỉ tiêu Diện tích muối công nghiệp trong tháng 6 năm 2026?` | `METRIC_POINT_INQUIRY`. Hiển thị thẻ 5 trường chuẩn: Giá trị **520**, Chi cục Phát triển nông thôn, Nhiệm vụ **Diêm nghiệp**, Thời điểm **30/06/2026**. |
| **SC-2.1 (Đa nhóm cha)**| `Cho tôi xem số liệu chỉ tiêu Thành lập mới năm 2026?` | `METRIC_POINT_INQUIRY`. Hiển thị đối chiếu đầy đủ 4 nhánh cha (`HTX nông nghiệp *(Cấp 1)*`: **3**, `Liên hiệp HTX nông nghiệp *(Cấp 1)*`: **0**, `Tổ hợp tác nông nghiệp *(Cấp 1)*`: **15**, `Trang trại *(Cấp 1)*`: **5**). |
| **SC-2.2 (Ngày cụ thể `[A, B]`)** | `số lượng chỉ tiêu trang trại ngày 23/4` | `METRIC_POINT_INQUIRY` (`specific_date='2026-04-23'`). Xác định `23/04` thuộc khoảng `[31/03, 30/06]`, khoảng cách tới `31/03` (23 ngày) < `30/06` (68 ngày) $\to$ hiển thị kỳ báo cáo **31/03/2026**. |
| **SC-2.2 (Khoảng thời gian)** | `số lượng chỉ tiêu trang trại trong nửa đầu năm nay` | `METRIC_POINT_INQUIRY` (`date_from='2026-01-01'`, `date_to='2026-06-30'`). Luôn lấy theo `report_date` mới nhất trong khoảng là ngày **30/06/2026** với giá trị **`Chưa có số liệu phê duyệt (-)`** (`NULL`). |
| **SC-2.3 (Lá rỗng `-`)**| `Cho tôi biết số liệu chỉ tiêu Liên kết sản xuất năm 2026?` | `METRIC_POINT_INQUIRY`. Hiển thị rõ **`Chưa có số liệu phê duyệt (-)`**, không văng lỗi hoặc trả về rỗng. |
| **SC-2.4 (Chỉ tiêu cha)**| `số lượng chỉ tiêu HTX nông nghiệp` | Hiển thị duy nhất câu thông báo chỉ tiêu cha chuẩn `output.md` và hàng nút bấm `🔘 [Tên chỉ tiêu con]` ngay bên dưới (không sinh bảng phụ hay danh sách lặp). |
| **REQ-Q03 (Đơn vị phụ trách & NULL `-`)** | `lĩnh vực nông nghiệp hiện đang có những nhiệm vụ nào` / `Lĩnh vực 1 hiện có những nhiệm vụ nào?` | `METADATA_EXPLORATION` (`target_table='mission'`). Bảng 5 cột (`STT`, `Mã nhiệm vụ`, `Tên nhiệm vụ`, `Lĩnh vực`, `Đơn vị phụ trách`): mỗi nhiệm vụ chỉ hiển thị **01 đơn vị phụ trách duy nhất** (`Chi cục` cho `Diêm nghiệp` và `Phát triển nông thôn`, `Phòng kinh tế` cho `Cải cách hành chính`), hiển thị **`-`** nếu kho dữ liệu là `NULL`, kèm nút **`🔍 Xem chỉ tiêu Cấp 1`** (1-Click Cross-Archetype Drill-Down sang `REQ-Q04`). |
| **SC-3.1 (Lọc nhiệm vụ theo thời gian)** | `Lĩnh vực Nông nghiệp trong nửa đầu năm / quý 1 / quý 2 / từ đầu năm tới giờ / từ tháng 2 đến tháng 9 có những nhiệm vụ nào?` | Lọc các nhiệm vụ thuộc lĩnh vực có báo cáo đã duyệt (`report_status='approved'`) trong khoảng thời gian tương ứng (`01/01..30/06`, `01/01..31/03`, `01/04..30/06`, `01/01..31/12`, `01/02..30/09`), hiển thị rõ kỳ thời gian trên tiêu đề bảng và bảo toàn kỳ thời gian khi bấm **`🔍 Xem chỉ tiêu Cấp 1`**. |
| **SC-3.2 (Ngoài phạm vi)**| `Lĩnh vực Hàng không vũ trụ hiện tại đang có các nhiệm vụ nào?` | Từ chối an toàn, thông báo DWH không có lĩnh vực `'Hàng không vũ trụ'` và hiển thị Chips gợi ý 2 lĩnh vực hiện có (`Nông nghiệp`, `Lĩnh vực 1`). |
| **REQ-Q04 / SC-4.1** | `Nhiệm vụ Diêm nghiệp năm 2026 bao gồm các chỉ tiêu gốc Cấp 1 nào?` | Hiển thị bảng 6 cột các chỉ tiêu Cấp 1 của nhiệm vụ `Diêm nghiệp` (`Tổng diện tích sản xuất muối` và `Tổng sản lượng muối` hiển thị **`- Xem chi tiết các chỉ tiêu con`**, bấm vào mở Pop-up Tree Modal sơ đồ cây ngang Cấp 1 $\to$ Cấp 2 $\to$ Cấp 3). |
| **SC-4.2 (Nhiệm vụ rỗng)**| `Nhiệm vụ Cải cách hành chính năm 2026 có các chỉ tiêu nào?` | Phản hồi rõ nhiệm vụ **'Cải cách hành chính'** đã có trong danh mục nhiệm vụ năm 2026 nhưng **chưa phát sinh bản ghi chỉ tiêu báo cáo nào được phê duyệt**. |

### 9.1. Hướng Dẫn Kiểm Thử Cửa Sổ Pop-up Sơ Đồ Cây Phân Cấp & Lưu Trữ Lịch Sử Phiên Chat
1. Truy cập giao diện Next.js (`http://localhost:3000`) hoặc Test Bench (`http://127.0.0.1:8000/bench`) và gửi câu hỏi: `danh sách các chỉ tiêu từ đầu năm tới nay`.
2. Xác nhận giao diện chỉ hiển thị **1 bảng Cấp 1 duy nhất (9 bản ghi)** với 6 cột chuẩn và khoảng cách cột gọn gàng dễ dò ngang.
3. Bấm vào nút **`🌳 - (Xem chi tiết con)`** tại dòng `Chương trình OCOP` (9 chỉ tiêu con).
4. Kiểm tra cửa sổ **Pop-up Tree Modal**:
   - Hiển thị sơ đồ cây ngang từ trái sang phải (`Cấp 1` $\to$ `Cấp 2` $\to$ `Cấp 3`) với **mũi tên phân nhánh kéo dài chỉ trực tiếp vào từng box chỉ tiêu con** (ví dụ từ Cấp 2 `'Lũy kế tổng số lượng chủ thể đến thời điểm báo cáo'` có 3 mũi tên kéo ra 3 box Cấp 3 `'3 sao'`, `'4 sao'`, `'5 sao'`).
   - Hỗ trợ thanh cuộn dọc (`scroll-down`), đóng bằng nút **`✕`** góc trên bên phải hoặc click ra vùng ngoài cửa sổ (`backdrop`).
5. Tải lại trang (`F5` / đóng và mở lại ứng dụng): Xác nhận phiên chat vẫn được giữ nguyên ở danh sách lịch sử bên trái (`ChatSidebar`) và tự động khôi phục nội dung hội thoại nhờ cơ chế **Dual-Layer Persistence** (`localStorage` + `IPGov_Chatbot/data/chat_history.sqlite3`).

### 9.2. Lệnh Chạy Bộ Kiểm Thử Tự Động `REQ-Q01` đến `REQ-Q04`
```powershell
.\.venv\Scripts\python.exe -m pytest IPGov_Chatbot/tests/test_req_q01_to_q04_full_spec.py -v -s
```

---

## 10. Nâng Cấp Kiến Trúc & Trải Nghiệm Người Dùng SRS V3 (`PA 1.1`, `PA 2.1`, `PA 3.1`, `PA 4.1`)

Căn cứ: Kế hoạch triển khai [implementation_plan.md](file:///C:/Users/Admin/.gemini/antigravity/brain/dfd05dd0-4ec9-4074-8de8-e3704b6caab5/implementation_plan.md) và đặc tả [output.md](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/docs/output.md).

| Mã Nâng Cấp | Thành Phần Kỹ Thuật | Câu Hỏi Kiểm Thử Mẫu (Test Prompt) | Kết Quả Định Tuyến & Hành Vi UI Kỳ Vọng |
| :---: | :--- | :--- | :--- |
| **PA 4.1** | **Neuro-Symbolic Calendar Contract** (`TemporalSlotSpec.to_calendar_bounds()`) | `Các chỉ tiêu thu thập trong tháng 2 năm 2024` vs `tháng 2 năm 2026` | LLM/Parser chỉ trích xuất slot `{granularity, year, period_start, period_end}`; Python `calendar.monthrange` tính tất định ngày cuối tháng (`2024-02-29` cho năm nhuận, `2026-02-28` cho năm thường, quý 1..4, 6 tháng đầu/cuối năm). |
| **PA 1.1** | **Dual-Bound Snapshot & Temporal Shift Notice** (`SC-2.2`) | `Số liệu chỉ tiêu doanh thu hợp tác xã ngày 20/3 là bao nhiêu?` | Giữ nguyên công thức lấy cận gần nhất $\min(\Delta_A, \Delta_B)$ (`31/03/2026`, giá trị **1,300**), đồng thời tự động bổ sung dòng **`- Lưu ý mốc thời gian:`** giải thích rõ độ lệch ngày và 2 cận báo cáo lân cận `[A, B]` để minh bạch hóa số liệu hành chính. |
| **PA 3.1** | **Context-Bound Action Chips & Parent-Slot Persistence** (`SC-2.4` $\leftrightarrow$ `SC-2.1`) | Lượt 1: `Cho tôi xem số liệu chỉ tiêu Chương trình OCOP năm 2026?`<br/>Lượt 2: `Thế còn chỉ tiêu Đang hoạt động thì sao?` (sau khi hỏi `HTX nông nghiệp`) | 1. Tự động đệ quy xuống chỉ tiêu lá (`leaf_descendants`) khi chỉ tiêu con Cấp 2 là nhóm trung gian rỗng số liệu.<br/>2. Tách biệt `label` hiển thị ngắn gọn (`🔘 [Tên chỉ tiêu con]`) và `query_text` đầy đủ ngữ cảnh cha.<br/>3. Lưu vết `inherited_parent_criterion` qua hội thoại đa lượt để phân giải chỉ tiêu lá trùng tên về đúng nhánh cha vừa hỏi. |
| **PA 2.1** | **Temporal-Safe Tree Hydration & Interactive White-Theme 3-Column SVG Tree Modal** (`REQ-Q01` & `REQ-Q04`) | `Số lượng chỉ tiêu thu thập được trong nửa đầu năm 2026 là bao nhiêu?` $\to$ bấm **`- (Xem chi tiết con)`** | 1. Khi có bộ lọc thời gian (`has_temporal_filter=True`), các nhánh con không phát sinh bản ghi trong kỳ được khóa an toàn về `None` (`-`), không rò rỉ số liệu cả năm.<br/>2. Cửa sổ Pop-up Tree Modal nền trắng (`bg-white`) tối giản, 3 cột (`Cấp 1` $\to$ `Cấp 2` $\to$ `Cấp 3`), đường cong SVG Cubic Bezier động, hỗ trợ **Đóng/Mở nhánh (`ChevronDown` / `+{n}`)** và **Highlight nhánh liên kết khi Hover/Click**. |

### 10.1. Lệnh Chạy Bộ Kiểm Thử SRS V3 Upgrades
```powershell
.\.venv\Scripts\python.exe -m pytest IPGov_Chatbot/tests/test_srs_v3_upgrades.py IPGov_Chatbot/tests/test_req_q01_to_q04_full_spec.py -v
```

---

## 11. Bộ Kiểm Thử Kiểm Toán Kỳ Báo Cáo, Biểu Mẫu Thu Thập & Ma Trận Phân Công Nhiệm Vụ (`REQ-Q05`: `SC-5.1`, `SC-5.2`, `SC-5.3`) & Cổng Kiểm Toán AST Zero-Heuristic Gate

Căn cứ: Đặc tả nghiệp vụ Mục `2.5 (LOẠI 5 / REQ-Q05)` tại [output.md](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/docs/output.md).

| Mã Kịch Bản | Câu Hỏi Kiểm Thử Mẫu (Test Prompt) | Phân Quyền HBAC / Cờ Cấu Hình | Kết Quả Định Tuyến & Hành Vi Đầu Ra Kỳ Vọng |
| :---: | :--- | :--- | :--- |
| **`SC-5.1a` & `SC-5.1b` (Role $\le 2$ - Cán bộ nội bộ)** | `Liệt kê trạng thái các kỳ báo cáo năm 2026, ngày nộp và những báo cáo nào đang ở trạng thái nháp chưa nộp?` | `role_level <= 2` (`0` Tỉnh, `1` Sở, `2` Phòng ban), `status_filter=['approved', 'draft']` | `REPORT_FORM_MISSION_AUDIT` (`audit_sub_intent='REPORT_SUBMISSION_STATUS'`). Tầng AST Enforcer mở khóa trạng thái, gắn **Banner Cảnh báo Pháp lý**, trả về **9 kỳ báo cáo** (**6 báo cáo `approved`** / **342 dòng fact** + **3 báo cáo `draft`** / **121 dòng fact** có `submitted_date IS NULL`), kèm chi tiết **14 bản ghi nháp Diêm nghiệp** (`22/09/2026` và `31/08/2026`) và bảng đối chiếu chênh lệch `Draft - Approved`. |
| **`SC-5.1` (Role $= 3$ - HBAC Guard)** | `Liệt kê các báo cáo nháp chưa phê duyệt năm 2026?` | `role_level = 3` (Công dân / Khách vãng lai), `blocked_draft_access=True` | Tầng AST Enforcer cưỡng chế giữ nguyên `status = 'approved'`, trả về **6 kỳ báo cáo đã duyệt** kèm cảnh báo phân quyền HBAC chặn truy cập dữ liệu nháp (`draft`). |
| **`SC-5.2a` & `SC-5.2b` (Dual Form & Group)** | `Hệ thống hiện có những biểu mẫu thu thập hoặc bộ chỉ tiêu thu thập nào đang áp dụng?` | Mặc định (`tenant_code='68'`) | `REPORT_FORM_MISSION_AUDIT` (`audit_sub_intent='FORM_CRITERIA_GROUP'`). Thông báo minh bạch bảng `collection_form` hiện có **`0` bản ghi** và hiển thị bảng đối soát **5 bộ chỉ tiêu thu thập** từ `criteria_group` (`3 active`: `Bộ thu thập Diêm nghiệp` 3/7, `Bộ thu thập Phát triển nông thôn` 6/107, `Bộ thu thập cải cách` 0/0 do `admin-lamdong` tạo; `2 draft`: `Thu Thập` 3/7 do `tzyalnh` tạo, `tt` 0/0 do `tuong` tạo). |
| **`SC-5.3a` & `SC-5.3b` (Mission Matrix & Officer)** | `Hiển thị ma trận phân công nhiệm vụ năm 2026 giữa các phòng ban và cá nhân phụ trách?` | Mặc định (`tenant_code='68'`) | `REPORT_FORM_MISSION_AUDIT` (`audit_sub_intent='MISSION_ASSIGNMENT_MATRIX'`). Hiển thị bảng đối soát **8 nhiệm vụ** kết nối `mission` + `office_mission` (7 dòng) + `user_mission` (3 dòng) + `office_user`: `Tăng Thị Mỹ Lành` (`tzyalnh`, `BA`, `LEADER` - `Chi cục`) phụ trách `Diêm nghiệp` & `Phát triển nông thôn`; `Vũ Đặng Thanh Tường` (`tuong`, `dev`, `LEADER` - `Phòng kinh tế`) phụ trách `Cải cách hành chính`; phát hiện độ lệch phân công tại `Phòng nông nghiệp` và `nhiệm vụ 1`. |

### 11.1. Lệnh Chạy Kiểm Thử AST Enforcer, Catalog & AST Zero-Heuristic Gate
```powershell
# 1. Kiểm thử tầng AST Enforcer (bao gồm mở khóa/chặn HBAC cho SC-5.1) và DuckDB Semantic Catalog (SC-5.2, SC-5.3)
.\.venv\Scripts\python.exe -m pytest IPGov_Chatbot/tests/test_mod06_ast_enforcer.py IPGov_Chatbot/tests/test_mod04_catalog.py -v

# 2. Kiểm tra Import Runtime Verification trước khi triển khai
.\.venv\Scripts\python.exe -c "import IPGov_Chatbot.main; print('Import Verified!')"
```


