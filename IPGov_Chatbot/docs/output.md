---
doc_id: "SRS-CHATBOT-QUERY-SPEC-V3"
title: "Danh Mục Các Loại Câu Hỏi Nghiệp Vụ Hệ Thống Xử Lý (SRS)"
role: "SPEC"
scope: "Hierarchical Criteria, Fact Report Criteria, Mission, Scope & Report/Form/Mission Audit Queries (REQ-Q01 to REQ-Q05)"
ssot_of: []
depends_on:
  - "IPGov_Chatbot/blueprints/00_TECH_STACK_VA_KIEN_TRUC_TONG_THE.md"
  - "IPGov_Chatbot/data/catalog_seed_metadata.json"
related_docs:
  - "IPGov_Chatbot/docs/BACKEND_RUN_GUIDE.md"
---

# DANH MỤC CÁC LOẠI CÂU HỎI NGHIỆP VỤ HỆ THỐNG XỬ LÝ

> [!IMPORTANT]
> **Tóm tắt nhanh (30s Overview):** Hệ thống `IPGov_Chatbot` xử lý **4 nhóm câu hỏi nghiệp vụ cốt lõi** trên Kho Dữ Liệu tỉnh Lâm Đồng, đồng thời hỗ trợ đính kèm **🎫 Ticket Thời Gian** (ngày cụ thể, tháng, quý, bán niên, lũy kế) trực tiếp vào từng câu hỏi gốc.

| Mã loại | Nhóm câu hỏi nghiệp vụ hệ thống xử lý | Nhánh con & Ticket đính kèm | Định dạng đầu ra |
| :---: | :--- | :--- | :--- |
| **[`REQ-Q01`](#1-loại-1-req-q01-liệt-kê-danh-sách-các-chỉ-tiêu)** | **Liệt Kê Danh Sách Các Chỉ Tiêu** | • **Nhánh 1.1 (`REQ-Q04`):** Chỉ tiêu Cấp 1 của Nhiệm vụ<br/>• **🎫 Ticket Thời Gian:** Lọc theo Tháng / Quý / Bán niên / Khoảng tháng<br/>• **`SC-1.2` / `SC-4.2`:** Kỳ hoặc nhiệm vụ chưa có dữ liệu duyệt | Bảng 7 cột Cấp 1 + Pop-up Cây chỉ tiêu |
| **[`REQ-Q02`](#2-loại-2-req-q02-tra-cứu-thông-tin-của-một-chỉ-tiêu)** | **Tra Cứu Thông Tin Của Một Chỉ Tiêu** | • **Mặc định:** Chỉ tiêu lá đơn lẻ (có số liệu hoặc chưa có số liệu `'-'`)<br/>• **`SC-2.1`:** Chỉ tiêu lá nằm ở nhiều nhánh cha<br/>• **`SC-2.4`:** Chỉ tiêu cha (có số liệu hoặc rỗng) + Gợi ý chỉ tiêu con kèm số liệu xem trước<br/>• **🎫 Ticket Thời Gian (`slider-time`):** Áp dụng cho cả 3 dạng trên (hỗ trợ hỏi bằng ngôn ngữ tự nhiên & điều chỉnh trực tiếp qua thanh trượt/bộ chọn mốc thời gian trên UI) | Thẻ 5 trường + Thanh `slider-time` / Bảng 6 cột / Nút gợi ý chỉ tiêu con |
| **[`REQ-Q03`](#3-loại-3-req-q03-liệt-kê-các-nhiệm-vụ-trong-một-lĩnh-vực)** | **Liệt Kê Các Nhiệm Vụ Trong Một Lĩnh Vực** | • **🎫 Ticket Thời Gian:** Lọc nhiệm vụ có báo cáo trong kỳ<br/>• **`SC-3.2`:** Lĩnh vực không tồn tại | Bảng 5 cột + Nút chuyển tiếp xem chỉ tiêu Cấp 1 |
| **[`REQ-Q05`](#4-loại-4-req-q05-kiểm-toán-báo-cáo-biểu-mẫu--phân-công-nhiệm-vụ)** | **Kiểm Toán Báo Cáo, Biểu Mẫu & Phân Công Nhiệm Vụ** | • **`SC-5.1`:** Tiến độ kỳ báo cáo & Đối chiếu bản nháp<br/>• **`SC-5.2`:** Biểu mẫu & Bộ thu thập chỉ tiêu<br/>• **`SC-5.3`:** Ma trận phân công Phòng ban & Cá nhân | Bảng 9 kỳ báo cáo / Bảng 5 bộ thu thập / Ma trận 8 nhiệm vụ |

---

## 1. LOẠI 1 (`REQ-Q01`): Liệt Kê Danh Sách Các Chỉ Tiêu

### A. Câu hỏi mẫu & Tệp chứa Quest
> [!TIP]
> **🎯 Sample Prompts (`REQ-Q01` — Liệt kê danh sách các chỉ tiêu toàn cục / theo đơn vị):**
> - <mark>**"Hệ thống hiện đang thu thập những chỉ tiêu nào trong năm 2026?"**</mark>
> - <mark>**"Liệt kê số lượng các chỉ tiêu từ tháng 2 đến tháng 8 năm nay?"**</mark>
> - <mark>**"Liệt kê số lượng các chỉ tiêu trong tháng 9?"**</mark>
> - <mark>**"Liệt kê danh sách chỉ tiêu của Phòng nông nghiệp trong quý 2 và quý 3?"**</mark>
>
> 📂 **File chứa quest:** [test_output_md_110_perturbations.py (L23-L81)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_output_md_110_perturbations.py#L23-L81) · [test_req_q01_to_q04_full_spec.py (L11-L56, L285-L307, L455-L490)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_req_q01_to_q04_full_spec.py#L11-L56) · [test_audit_fixes_subagent2.py (L102-L186)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_audit_fixes_subagent2.py#L102-L186)

### B. Logic hoạt động
- Truy xuất các bản ghi báo cáo đã phê duyệt và gom về đầu mục chỉ tiêu gốc Cấp 1 trên **Bảng 7 cột**.
- Tách bạch 2 cột độc lập:
  1. **`Giá trị mới nhất`**: Hiển thị giá trị thực tế của chính chỉ tiêu Cấp 1 đó (hoặc `Chưa có số liệu phê duyệt (-)` nếu chỉ tiêu Cấp 1 không có số liệu riêng).
  2. **`Chỉ tiêu con`**: Hiển thị nút **`- (Xem chi tiết con)`** nếu có nhánh con Cấp 2, Cấp 3 hoặc **`Không có`** nếu là chỉ tiêu đơn.

### C. Định dạng câu trả lời (Output mẫu — Bảng 7 Cột)

| STT | Tên chỉ tiêu Cấp 1 | Loại cấu trúc | Giá trị mới nhất | Chỉ tiêu con | Đơn vị thực hiện | Nhiệm vụ trọng tâm |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| 1 | **Tổng hộ sản xuất muối** | Chỉ tiêu đơn *(Cấp 1)* | **660** | Không có | Chi cục | Diêm nghiệp |
| 2 | **Tổng diện tích sản xuất muối** | Nhóm chỉ tiêu *(2 chỉ tiêu con)* | **1.520** | **`- (Xem chi tiết con)`** | Chi cục | Diêm nghiệp |
| 3 | **Liên hiệp HTX nông nghiệp** | Nhóm chỉ tiêu *(8 chỉ tiêu con)* | **Chưa có số liệu phê duyệt (-)** | **`- (Xem chi tiết con)`** | Chi cục | Phát triển nông thôn |
| 4 | **HTX nông nghiệp** | Nhóm chỉ tiêu *(12 chỉ tiêu con)* | **Chưa có số liệu phê duyệt (-)** | **`- (Xem chi tiết con)`** | Chi cục | Phát triển nông thôn |
| 5 | **Trang trại** | Nhóm chỉ tiêu *(9 chỉ tiêu con)* | **Chưa có số liệu phê duyệt (-)** | **`- (Xem chi tiết con)`** | Chi cục | Phát triển nông thôn |

- **Tương tác khi bấm `- (Xem chi tiết con)`:** Mở **Cửa sổ Pop-up** vẽ sơ đồ cây phân cấp từ Cấp 1 $\to$ Cấp 2 $\to$ Cấp 3 kèm số liệu mới nhất trong kỳ:

```mermaid
flowchart LR
    subgraph POPUP_TREE["🪟 CỬA SỔ POP-UP CÂY CHỈ TIÊU (Cấp 1 -> Cấp 2 -> Cấp 3)"]
        direction LR
        P1["<b>Liên hiệp HTX nông nghiệp</b><br/><i>(Chỉ tiêu cha - Cấp 1)</i>"]
        C2_1["<b>Lũy kế đến thời điểm báo cáo</b>: <b>6</b>"]
        C2_2["<b>Thành lập mới</b>: <b>1</b>"]
        C2_3["<b>Đang hoạt động</b>: <b>4</b>"]
        C2_4["<b>Thành viên</b>: <b>35</b>"]
        C2_5["<b>Tổng số LHHTX phân theo lĩnh vực</b><br/><i>(Nhóm trung gian - Cấp 2)</i>"]
        C3_1["<b>Trồng trọt</b>: <b>3</b>"]
        C3_2["<b>Chăn nuôi</b>: <b>0</b>"]
        C3_3["<b>Lâm nghiệp</b>: <b>0</b>"]

        P1 --> C2_1 & C2_2 & C2_3 & C2_4 & C2_5
        C2_5 --> C3_1 & C3_2 & C3_3
    end
```

### D. Các nhánh con & Ticket thời gian của Loại 1

#### 🔹 Nhánh 1.1 (`REQ-Q04`): Hiển thị các chỉ tiêu Cấp 1 của Nhiệm vụ
> [!TIP]
> **🎯 Sample Prompts (`REQ-Q04` — Chỉ tiêu Cấp 1 theo nhiệm vụ):**
> - <mark>**"Hiển thị các chỉ tiêu cấp 1 của nhiệm vụ Phát triển nông thôn?"**</mark>
> - <mark>**"Nhiệm vụ Diêm nghiệp có những chỉ tiêu cấp 1 nào?"**</mark>
> - <mark>**"Danh sách các chỉ tiêu cấp đầu hiện có trong nhiệm vụ phát triển nông thôn là gì?"**</mark>
> - <mark>**"Liệt kê các chỉ tiêu cấp 1 của các nhiệm vụ trọng tâm hiện nay?"**</mark>
>
> 📂 **File chứa quest:** [test_output_md_110_perturbations.py (L250-L303)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_output_md_110_perturbations.py#L250-L303) · [test_req_q01_to_q04_full_spec.py (L167-L248, L805-L882)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_req_q01_to_q04_full_spec.py#L167-L248)

- **Output mẫu (Bảng 7 cột theo Nhiệm vụ):**

| STT | Nhiệm vụ | Tên chỉ tiêu Cấp 1 | Loại cấu trúc Cấp 1 | Giá trị mới nhất | Chỉ tiêu con | Đơn vị thực hiện |
| :---: | :--- | :--- | :--- | :---: | :---: | :--- |
| 1 | Diêm nghiệp | **Tổng hộ sản xuất muối** | Chỉ tiêu đơn *(Nút lá Cấp 1)* | **660** | Không có | Chi cục |
| 2 | Diêm nghiệp | **Tổng diện tích sản xuất muối** | Nhóm chỉ tiêu *(2 chỉ tiêu con)* | **1.520** | **`- (Xem chi tiết con)`** | Chi cục |
| 3 | Diêm nghiệp | **Tổng sản lượng muối** | Nhóm chỉ tiêu *(2 chỉ tiêu con)* | **27.000** | **`- (Xem chi tiết con)`** | Chi cục |

#### 🎫 Ticket Thời Gian (`Ticket-Time` cho `REQ-Q01` & `REQ-Q04`): Liệt kê danh sách chỉ tiêu theo khoảng thời gian
> [!TIP]
> **🎫 Sample Prompts khi gắn Ticket Thời Gian vào `REQ-Q01` / `REQ-Q04`:**
> - <mark>**"Từ tháng 4 đến tháng 9 có các chỉ tiêu nào?"**</mark> *(Khoảng tháng)*
> - <mark>**"Trong quý 2 năm nay có những chỉ tiêu nào được thu thập?"**</mark> *(Quý)*
> - <mark>**"Liệt kê số lượng các chỉ tiêu trong nửa đầu năm 2026?"**</mark> *(Bán niên)*
> - <mark>**"Trong quý 3, nhiệm vụ Diêm nghiệp có những chỉ tiêu cấp 1 nào được báo cáo?"**</mark> *(Nhiệm vụ + Quý)*
>
> 📂 **File chứa quest:** [test_output_md_110_perturbations.py (L52-L81, L277-L290)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_output_md_110_perturbations.py#L52-L81) · [test_req_q01_to_q04_full_spec.py (L11-L56, L805-L863)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_req_q01_to_q04_full_spec.py#L805-L863)

- **Cơ chế Ticket Thời Gian:**
  - Khi câu hỏi đính kèm mốc/khoảng thời gian (*tháng lẻ*, *từ tháng X đến tháng Y*, *quý 1..4*, *nửa đầu năm*, *nửa cuối năm*, *lũy kế từ đầu năm*), hệ thống lọc các bản ghi đã phê duyệt đúng trong khoảng ngày bắt đầu – kết thúc của kỳ (áp dụng cho cả **Bảng 7 cột** lẫn cây chỉ tiêu trong **Pop-up**).
  - **Trường hợp kỳ hoặc nhiệm vụ chưa phát sinh dữ liệu duyệt (`SC-1.2` / `SC-4.2`):**
    - VD kỳ trống (<mark>*"Các chỉ tiêu thu thập trong tháng 1 năm 2024 là gì?"*</mark>): *"Hiện tại chưa ghi nhận bản ghi chỉ tiêu nào được phê duyệt trong kỳ tháng 01/2024. Đồng chí có thể tra cứu dữ liệu kỳ năm 2026."*
    - VD nhiệm vụ chưa có báo cáo duyệt (<mark>*"Nhiệm vụ Cải cách hành chính năm 2026 có các chỉ tiêu nào?"*</mark>): *"Nhiệm vụ **'Cải cách hành chính'** (do **Phòng kinh tế** phụ trách) hiện đã có trong danh mục nhiệm vụ năm 2026, nhưng **chưa phát sinh bản ghi chỉ tiêu báo cáo nào được phê duyệt** trong hệ thống."*

---

## 2. LOẠI 2 (`REQ-Q02`): Tra Cứu Thông Tin Của Một Chỉ Tiêu

### A. Câu hỏi mẫu & Tệp chứa Quest
> [!TIP]
> **🎯 Sample Prompts (`REQ-Q02` — Chỉ tiêu lá đơn lẻ):**
> - <mark>**"Cho tôi biết tổng hộ sản xuất muối năm 2026 là bao nhiêu?"**</mark>
> - <mark>**"Số lượng sản phẩm OCOP 3 sao đã được công nhận là bao nhiêu?"**</mark>
> - <mark>**"Doanh thu bình quân trong năm của một hợp tác xã nông nghiệp là bao nhiêu?"**</mark>
> - <mark>**"Chỉ tiêu liên kết sản xuất của Tổ hợp tác năm 2026 là bao nhiêu?"**</mark>
>
> 📂 **File chứa quest:** [test_output_md_110_perturbations.py (L85-L119, L169-L185)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_output_md_110_perturbations.py#L85-L119) · [test_req_q01_to_q04_full_spec.py (L58-L71, L107-L117, L368-L398)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_req_q01_to_q04_full_spec.py#L58-L71)

### B. Logic hoạt động
- Đối chiếu tên chỉ tiêu trong danh mục:
  1. **Chỉ tiêu lá đơn lẻ:** Lấy bản ghi phê duyệt mới nhất và hiển thị **Thẻ 5 Trường Chuẩn** (nếu giá trị trong kho đang trống hoặc `'-'` thì hiển thị `Chưa có số liệu phê duyệt (-)`).
  2. **Chỉ tiêu lá nằm ở nhiều nhánh cha (`SC-2.1`):** Hiển thị **Bảng 6 cột** đối chiếu toàn bộ các nhánh cha.
  3. **Chỉ tiêu cha (`SC-2.4`):** Nếu chỉ tiêu cha **có số liệu** thì hiển thị **Thẻ 5 Trường Chuẩn** kèm các **Button gợi ý chỉ tiêu con**; nếu chỉ tiêu cha **không có số liệu** thì hiển thị thông báo kèm các **Button gợi ý chỉ tiêu con**.

### C. Định dạng câu trả lời (Output mẫu — Thẻ 5 Trường Chuẩn)

- **Mẫu 1 — Khi chỉ tiêu có số liệu phê duyệt:**
  ```markdown
  Thông tin số liệu mới nhất của chỉ tiêu đồng chí tra cứu:
  - **Chỉ tiêu:** Tổng hộ sản xuất muối *(Chỉ tiêu gốc - Cấp 1)*
  - **Giá trị:** **660**
  - **Đơn vị thực hiện:** Chi cục
  - **Nhiệm vụ trọng tâm:** Diêm nghiệp
  - **Thời điểm báo cáo:** 30/09/2026
  ```
- **Mẫu 2 — Khi chỉ tiêu có trong danh mục nhưng chưa có số liệu trong kỳ (`'-'`):**
  ```markdown
  Thông tin số liệu mới nhất của chỉ tiêu đồng chí tra cứu:
  - **Chỉ tiêu:** Liên kết sản xuất *(Thuộc nhóm: Tổ hợp tác - Cấp 2)*
  - **Giá trị:** Chưa có số liệu phê duyệt (-)
  - **Đơn vị thực hiện:** Chi cục
  - **Nhiệm vụ trọng tâm:** Phát triển nông thôn
  - **Thời điểm báo cáo:** 30/09/2026
  ```

### D. Các nhánh con & Ticket thời gian của Loại 2

#### 🔹 `SC-2.1`: Chỉ tiêu lá nằm ở nhiều nhánh chỉ tiêu cha khác nhau
> [!TIP]
> **🎯 Sample Prompts (`SC-2.1` — Các chỉ tiêu lá xuất hiện ở nhiều nhánh cha *HTX*, *LHHTX*, *Tổ hợp tác*, *Trang trại*):**
> - <mark>**"Chỉ tiêu thành lập mới hiện tại là bao nhiêu?"**</mark>
> - <mark>**"Cho tôi xem số liệu chỉ tiêu đang hoạt động?"**</mark>
> - <mark>**"Chỉ tiêu trồng trọt hiện đạt bao nhiêu?"**</mark>
> - <mark>**"Số lượng chỉ tiêu trồng trọt ngày 30/4?"**</mark> *(Kết hợp `🎫 Ticket thời gian`)*
>
> 📂 **File chứa quest:** [test_output_md_110_perturbations.py (L120-L138)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_output_md_110_perturbations.py#L120-L138) · [test_req_q01_to_q04_full_spec.py (L73-L89, L341-L366)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_req_q01_to_q04_full_spec.py#L341-L366)

- **Output mẫu (Bảng 6 cột đối chiếu toàn bộ các nhánh cha):**

| STT | Tên chỉ tiêu | Nhóm chỉ tiêu (Cấp) | Giá trị mới nhất | Đơn vị thực hiện | Nhiệm vụ trọng tâm |
| :---: | :--- | :--- | :---: | :--- | :--- |
| 1 | Trồng trọt | HTX nông nghiệp > Số lượng HTX phân theo lĩnh vực *(Cấp 2)* | **26** | Chi cục | Phát triển nông thôn |
| 2 | Trồng trọt | Liên hiệp HTX nông nghiệp > Tổng số LHHTX phân theo lĩnh vực *(Cấp 2)* | **3** | Chi cục | Phát triển nông thôn |
| 3 | Trồng trọt | Tổ hợp tác nông nghiệp > Tổng số THT phân theo lĩnh vực *(Cấp 2)* | **12** | Chi cục | Phát triển nông thôn |
| 4 | Trồng trọt | Trang trại > Tổng số trang trại *(Cấp 2)* | **16** | Chi cục | Phát triển nông thôn |

#### 🔹 `SC-2.4`: Hỏi vào tên một chỉ tiêu cha (có các chỉ tiêu con bên dưới)
> [!TIP]
> **🎯 Sample Prompts (`SC-2.4`):**
> - <mark>**"Tổng số lượng chủ thể sản phẩm OCOP trong năm là bao nhiêu?"**</mark> *(Chỉ tiêu cha **có số liệu**)*
> - <mark>**"Cho tôi biết số liệu chỉ tiêu Liên hiệp HTX nông nghiệp?"**</mark> *(Chỉ tiêu cha **không có số liệu**)*
> - <mark>**"Thông tin số liệu Chương trình OCOP hiện tại là bao nhiêu?"**</mark> *(Chỉ tiêu cha **không có số liệu**)*
> - <mark>**"Số liệu chỉ tiêu trang trại ngày 23/4 là bao nhiêu?"**</mark> *(Chỉ tiêu cha kết hợp `🎫 Ticket thời gian`)*
>
> 📂 **File chứa quest:** [test_output_md_110_perturbations.py (L140-L167, L187-L198)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_output_md_110_perturbations.py#L187-L198) · [test_req_q01_to_q04_full_spec.py (L119-L136, L308-L339)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_req_q01_to_q04_full_spec.py#L308-L339) · [test_srs_v3_upgrades.py (L145-L191)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_srs_v3_upgrades.py#L145-L191)

- **Trường hợp 1 (`SC-2.4a`) — Chỉ tiêu cha CÓ số liệu tổng hợp (VD: `'Tổng số lượng chủ thể sản phẩm OCOP trong năm'` có giá trị `17` tại kỳ `30/09/2026`):**
  - Hiển thị **Thẻ 5 Trường Chuẩn** của chỉ tiêu cha kèm các **Button gợi ý các chỉ tiêu con** ngay bên dưới:
  ```markdown
  Thông tin số liệu mới nhất của chỉ tiêu đồng chí tra cứu:
  - **Chỉ tiêu:** Tổng số lượng chủ thể sản phẩm OCOP trong năm *(Thuộc nhóm: Chương trình OCOP - Cấp 2)*
  - **Giá trị:** **17**
  - **Đơn vị thực hiện:** Chi cục
  - **Nhiệm vụ trọng tâm:** Phát triển nông thôn
  - **Thời điểm báo cáo:** 30/09/2026

  Đồng chí có thể bấm chọn một trong các **chỉ tiêu con trực thuộc** ở bên dưới để xem chi tiết:
  ```
  > 🔘 `[Số lượng chủ thể là HTX]` &nbsp; 🔘 `[Số lượng chủ thể là Doanh nghiệp]` &nbsp; 🔘 `[Số lượng chủ thể là Cơ sở sản xuất/Hộ kinh doanh]` &nbsp; 🔘 `[Số lượng chủ thể là Tổ hợp tác]`

- **Trường hợp 2 (`SC-2.4b`) — Chỉ tiêu cha KHÔNG có số liệu tổng hợp (VD: `'Liên hiệp HTX nông nghiệp'`):**
  > *"Chỉ tiêu **'Liên hiệp HTX nông nghiệp'** là một **chỉ tiêu cha (nhóm chỉ tiêu)** nên không có số liệu tổng hợp riêng lẻ. Đồng chí vui lòng bấm chọn một trong các **chỉ tiêu con đang có số liệu** trực thuộc nhóm này ở bên dưới để xem chi tiết:"*
  >
  > 🔘 `[Lũy kế đến thời điểm báo cáo]` &nbsp; 🔘 `[Thành lập mới]` &nbsp; 🔘 `[Đang hoạt động]` &nbsp; 🔘 `[Thành viên]` &nbsp; 🔘 `[Tổng số LHHTX phân theo lĩnh vực]`

#### 🎫 Ticket Thời Gian (`slider-time` / `Ticket-Time` cho toàn bộ `REQ-Q02`): Lọc số liệu theo ngày cụ thể, khoảng thời gian hoặc trượt chọn mốc thời gian trực tiếp
> [!TIP]
> **🎫 Sample Prompts khi gắn Ticket Thời Gian (`slider-time`) vào Chỉ tiêu lá đơn lẻ / Chỉ tiêu lá đa nhánh (`SC-2.1`) / Chỉ tiêu cha (`SC-2.4`):**
> - <mark>**"Cho tôi biết số liệu chỉ tiêu tổng hộ sản xuất muối vào ngày 30/9?"**</mark> *(Chỉ tiêu lá đơn lẻ + Ngày)*
> - <mark>**"Chỉ tiêu sản lượng muối công nghiệp trong quý 2 năm 2026 là bao nhiêu?"**</mark> *(Chỉ tiêu lá đơn lẻ + Quý)*
> - <mark>**"Số lượng chỉ tiêu trồng trọt ngày 30/4?"**</mark> *(Chỉ tiêu lá đa nhánh `SC-2.1` + Ngày)*
> - <mark>**"Số liệu chỉ tiêu trang trại ngày 23/4 là bao nhiêu?"**</mark> *(Chỉ tiêu cha `SC-2.4` + Ngày)*
> - <mark>**"Tổng diện tích sản xuất muối trong nửa đầu năm 2026 là bao nhiêu?"**</mark> *(Chỉ tiêu cha `SC-2.4` + Khoảng thời gian)*
>
> 📂 **File chứa quest:** [test_output_md_110_perturbations.py (L140-L167)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_output_md_110_perturbations.py#L140-L167) · [test_req_q01_to_q04_full_spec.py (L91-L105, L684-L722)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_req_q01_to_q04_full_spec.py#L684-L722) · [test_srs_v3_upgrades.py (L80-L140)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_srs_v3_upgrades.py#L80-L140)

- **Cơ chế Ticket Thời Gian (`slider-time`) trên `REQ-Q02` (Áp dụng đồng nhất cho cả Chỉ tiêu lá đơn lẻ, `SC-2.1` và `SC-2.4`):**
  1. **Khi gắn mốc ngày cụ thể $a$ (trên dãy mốc báo cáo $D = [A, B, C, \dots]$):** Xác định khoảng $[A, B]$ chứa $a$, so sánh khoảng cách $\Delta_A = a - A$ và $\Delta_B = B - a$ để chọn kỳ báo cáo gần nhất (nếu $\Delta_A = \Delta_B$ thì ưu tiên cận trên $B$). *Ví dụ:* các mốc `[31/03, 30/06, 30/09]`, hỏi ngày `30/04` hoặc `23/04` $\to$ đối chiếu về kỳ báo cáo gần nhất ngày **`31/03/2026`** và thông báo rõ ngày đối chiếu.
  2. **Khi gắn khoảng thời gian (tháng, quý, nửa đầu năm, lũy kế...):** Lấy bản ghi tại kỳ báo cáo mới nhất nằm trong khoảng thời gian đó.
  3. **Tương tác Thanh trượt / Bộ chọn Thời gian trực tiếp (`slider-time` trên UI):** Ngay trên **Thẻ 5 Trường Chuẩn** của chỉ tiêu đơn lẻ (cũng như Bảng 6 cột `SC-2.1` và Khối chỉ tiêu cha `SC-2.4`), hệ thống hiển thị thanh điều khiển **`🎫 slider-time`** cho phép người dùng trượt hoặc bấm chuyển đổi trực tiếp giữa các mốc báo cáo trong năm (`31/03/2026`, `30/06/2026`, `30/09/2026`, hoặc theo `Quý 1..4` / `Bán niên` / `Cả năm 2026`) để đối chiếu biến động số liệu của chỉ tiêu đó qua từng kỳ mà không cần gõ lại câu hỏi mới.

---

## 3. LOẠI 3 (`REQ-Q03`): Liệt Kê Các Nhiệm Vụ Trong Một Lĩnh Vực

### A. Câu hỏi mẫu & Tệp chứa Quest
> [!TIP]
> **🎯 Sample Prompts (`REQ-Q03` — Liệt kê nhiệm vụ theo lĩnh vực):**
> - <mark>**"Liệt kê các nhiệm vụ trong lĩnh vực Nông nghiệp?"**</mark>
> - <mark>**"Lĩnh vực Nông nghiệp hiện có những nhiệm vụ trọng tâm nào?"**</mark>
> - <mark>**"Cho tôi danh sách tên các nhiệm vụ thuộc lĩnh vực 1?"**</mark>
>
> 📂 **File chứa quest:** [test_output_md_110_perturbations.py (L202-L246)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_output_md_110_perturbations.py#L202-L246) · [test_req_q01_to_q04_full_spec.py (L138-L165, L248-L267, L732-L803)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_req_q01_to_q04_full_spec.py#L732-L803)

### B. Logic hoạt động & Định dạng câu trả lời (Bảng 5 Cột)
- Lọc các nhiệm vụ thuộc lĩnh vực được hỏi kèm đơn vị phụ trách và hỗ trợ nút **`🔍 Xem chỉ tiêu Cấp 1`** trên từng dòng để chuyển tiếp sang Nhánh 1.1 (`REQ-Q04`).

| STT | Mã nhiệm vụ | Tên nhiệm vụ | Lĩnh vực | Đơn vị phụ trách |
| :---: | :--- | :--- | :--- | :--- |
| 1 | `NV_DN_01` | **Diêm nghiệp** | Nông nghiệp | Chi cục |
| 2 | `NV_PTNT_02` | **Phát triển nông thôn** | Nông nghiệp | Chi cục |

### C. Ticket Thời Gian & Trường hợp đặc biệt của Loại 3

- **🎫 Ticket Thời Gian (`SC-3.1` — Lọc nhiệm vụ thuộc lĩnh vực theo khoảng thời gian):**
  - **Sample Prompts:** <mark>**"Lĩnh vực Nông nghiệp trong nửa đầu năm có những nhiệm vụ nào?"**</mark>, <mark>**"Từ tháng 2 đến tháng 9 lĩnh vực Nông nghiệp có những nhiệm vụ nào?"**</mark>
  - **Logic:** Chỉ liệt kê các nhiệm vụ thuộc lĩnh vực có phát sinh báo cáo phê duyệt trong khoảng thời gian được hỏi và bảo toàn ngữ cảnh thời gian khi chuyển tiếp sang xem chỉ tiêu Cấp 1.
- **🔹 `SC-3.2` — Tên lĩnh vực không tồn tại trong hệ thống:**
  - **Sample Prompts:** <mark>**"Liệt kê các nhiệm vụ thuộc lĩnh vực Hàng không vũ trụ?"**</mark>
  - **Output mẫu:**
    > *"Hiện tại trong kho dữ liệu tỉnh Lâm Đồng **không có lĩnh vực 'Hàng không vũ trụ'**. Đồng chí có thể tra cứu các nhiệm vụ thuộc các lĩnh vực hiện có sau đây:"*
    >
    > 🔘 `[Lĩnh vực: Nông nghiệp]` &nbsp; 🔘 `[Lĩnh vực: Lĩnh vực 1]`

---

## 4. LOẠI 4 (`REQ-Q05`): Kiểm Toán Báo Cáo, Biểu Mẫu & Phân Công Nhiệm Vụ

### 🔹 `SC-5.1`: Kiểm toán tiến độ kỳ báo cáo & Đối chiếu số liệu bản nháp (`SC-5.1a` & `SC-5.1b`)
> [!TIP]
> **🎯 Sample Prompts (`SC-5.1`):**
> - <mark>**"Liệt kê trạng thái các kỳ báo cáo năm 2026, ngày nộp và những báo cáo nào đang ở trạng thái nháp chưa nộp?"**</mark> *(`SC-5.1a`)*
> - <mark>**"Cho biết chi tiết các chỉ tiêu trong các kỳ báo cáo nháp của nhiệm vụ Diêm nghiệp năm 2026 và đối chiếu chênh lệch với bản đã phê duyệt?"**</mark> *(`SC-5.1b`)*
>
> 📂 **File chứa quest:** [test_output_md_110_perturbations.py (L308-L334)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_output_md_110_perturbations.py#L308-L334) · [test_req_q05_report_form_mission_audit.py (L46-L83)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_req_q05_report_form_mission_audit.py#L46-L83)

- **Output mẫu `SC-5.1a` (Bảng 9 kỳ báo cáo năm 2026 — câu dẫn ngắn gọn, thuần Việt):**
  > *"Tổng hợp tiến độ 9 kỳ báo cáo năm 2026 của tỉnh Lâm Đồng (6 kỳ đã phê duyệt, 3 kỳ bản nháp chưa nộp):"*

| STT | Kỳ báo cáo | Ngày nộp | Trạng thái | Người tạo | Đơn vị thực hiện | Nhiệm vụ báo cáo | Tổng chỉ tiêu | Chỉ tiêu đã có số liệu |
| :---: | :---: | :---: | :--- | :---: | :--- | :--- | :---: | :---: |
| 1 | **2026-09-30** | `2026-03-26` | Đã phê duyệt | `tzyalnh` | Chi cục | Phát triển nông thôn | 107 | **37** |
| 2 | **2026-09-20** | `2026-03-26` | Đã phê duyệt | `tzyalnh` | Chi cục | Diêm nghiệp | 7 | **6** |
| 3 | **2026-06-30** | `2026-03-26` | Đã phê duyệt | `tzyalnh` | Chi cục | Diêm nghiệp | 7 | **4** |
| 4 | **2026-06-30** | `2026-03-26` | Đã phê duyệt | `tzyalnh` | Chi cục | Phát triển nông thôn | 107 | **21** |
| 5 | **2026-03-31** | `2026-03-26` | Đã phê duyệt | `tzyalnh` | Chi cục | Diêm nghiệp | 7 | **7** |
| 6 | **2026-03-31** | `2026-03-26` | Đã phê duyệt | `tzyalnh` | Chi cục | Phát triển nông thôn | 107 | **46** |
| 7 | **2026-09-22** | `Chưa nộp (-)` | Bản nháp | `tzyalnh` | Chi cục | Diêm nghiệp | 7 | **4** |
| 8 | **2026-09-21** | `Chưa nộp (-)` | Bản nháp | `tzyalnh` | Chi cục | Phát triển nông thôn | 107 | **37** |
| 9 | **2026-08-31** | `Chưa nộp (-)` | Bản nháp | `tzyalnh` | Chi cục | Diêm nghiệp | 7 | **7** |

- **Output mẫu `SC-5.1b` (Chi tiết 2 kỳ báo cáo nháp của nhiệm vụ `Diêm nghiệp`):**
  - **Kỳ nháp `2026-09-22` (7 dòng):** `Tổng diện tích sản xuất muối` = **`52`**, `Diện tích muối sản xuất công nghiệp` = **`12`**, `Diện tích muối sản xuất thủ công` = **`64`**, `Tổng sản lượng muối` = **`0`**, 3 chỉ tiêu còn lại chưa có số liệu (**`Chưa nhập (-)`**).
  - **Kỳ nháp `2026-08-31` (7 dòng):** `Tổng diện tích sản xuất muối` = **`1.800`**, `Diện tích muối sản xuất công nghiệp` = **`500`**, `Diện tích muối sản xuất thủ công` = **`700`**, `Tổng sản lượng muối` = **`2.500`**, `Sản lượng muối công nghiệp` = **`550`**, `Sản lượng muối thủ công` = **`420`**, `Tổng hộ sản xuất muối` = **`50`**.

---

### 🔹 `SC-5.2`: Kiểm toán biểu mẫu thu thập & Bộ thu thập chỉ tiêu (`SC-5.2a` & `SC-5.2b`)
> [!TIP]
> **🎯 Sample Prompts (`SC-5.2`):**
> - <mark>**"Hệ thống hiện có những biểu mẫu thu thập hoặc bộ thu thập chỉ tiêu nào đang áp dụng năm 2026?"**</mark>
> - <mark>**"Năm 2026 đang áp dụng những biểu mẫu thu thập hoặc bộ thu thập chỉ tiêu nào trên hệ thống?"**</mark>
>
> 📂 **File chứa quest:** [test_output_md_110_perturbations.py (L336-L348)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_output_md_110_perturbations.py#L336-L348) · [test_req_q05_report_form_mission_audit.py (L84-L102)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_req_q05_report_form_mission_audit.py#L84-L102)

- **Output mẫu (Bảng 5 bộ thu thập chỉ tiêu năm 2026):**
  > *"Hệ thống hiện ghi nhận 0 biểu mẫu thu thập độc lập và 5 bộ thu thập chỉ tiêu năm 2026 (3 bộ đang kích hoạt, 2 bộ bản nháp):"*

| STT | Tên bộ thu thập | Trạng thái | Người tạo | Nhiệm vụ liên kết | Lĩnh vực | Số chỉ tiêu gốc (Cấp 1) | Tổng chỉ tiêu ánh xạ |
| :---: | :--- | :---: | :---: | :--- | :--- | :---: | :---: |
| 1 | **Bộ thu thập cải cách** | Đang kích hoạt | `admin-lamdong` | Cải cách hành chính | Lĩnh vực 1 | **0** | 0 |
| 2 | **Bộ thu thập Diêm nghiệp** | Đang kích hoạt | `admin-lamdong` | Diêm nghiệp | Nông nghiệp | **3** | 7 |
| 3 | **Bộ thu thập Phát triển nông thôn** | Đang kích hoạt | `admin-lamdong` | Phát triển nông thôn | Nông nghiệp | **6** | 107 |
| 4 | **Thu Thập** | Bản nháp | `tzyalnh` | Diêm nghiệp | Nông nghiệp | **3** | 7 |
| 5 | **tt** | Bản nháp | `tuong` | Cải cách hành chính, nhiệm vụ 1 | Lĩnh vực 1, Nông nghiệp | **0** | 0 |

---

### 🔹 `SC-5.3`: Ma trận phân công nhiệm vụ theo Phòng ban & Cá nhân phụ trách (`SC-5.3a` & `SC-5.3b`)
> [!TIP]
> **🎯 Sample Prompts (`SC-5.3`):**
> - <mark>**"Nhiệm vụ Diêm nghiệp được phân công cho những phòng ban nào và cán bộ nào phụ trách?"**</mark>
> - <mark>**"Hiển thị ma trận phân công nhiệm vụ năm 2026 giữa các phòng ban và cá nhân phụ trách?"**</mark>
>
> 📂 **File chứa quest:** [test_output_md_110_perturbations.py (L350-L362)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_output_md_110_perturbations.py#L350-L362) · [test_req_q05_report_form_mission_audit.py (L104-L120)](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/tests/test_req_q05_report_form_mission_audit.py#L104-L120)

- **Output mẫu (Ma trận đối soát phân công 8 nhiệm vụ năm 2026):**
  > *"Bảng đối soát phân công phòng ban và cán bộ phụ trách 8 nhiệm vụ năm 2026 của tỉnh Lâm Đồng:"*

| STT | Mã nhiệm vụ | Tên nhiệm vụ | Lĩnh vực | Phòng ban được giao | Cán bộ phụ trách & Vai trò |
| :---: | :--- | :--- | :--- | :--- | :--- |
| 1 | `cai_cach_hanh_chinh` | **Cải cách hành chính** | Lĩnh vực 1 | Phòng kinh tế | Vũ Đặng Thanh Tường (tuong - Chức vụ: dev - Vai trò: LEADER) — Phòng kinh tế |
| 2 | `cai_cach_hanh_chinh_2` | **Cải cách hành chính** | Nông nghiệp | Chưa phân công phòng ban | Chưa phân công cán bộ |
| 3 | `diem_nghiep` | **Diêm nghiệp** | Nông nghiệp | Chi cục, Phòng nông nghiệp | Tăng Thị Mỹ Lành (tzyalnh - Chức vụ: BA - Vai trò: LEADER) — Chi cục |
| 4 | `nhiem_vu_1` | **nhiệm vụ 1** | Nông nghiệp | Phòng kinh tế, Phòng nông nghiệp | Chưa phân công cán bộ |
| 5 | `nhiem_vu_2` | **nhiệm vụ 2** | Nông nghiệp | Chưa phân công phòng ban | Chưa phân công cán bộ |
| 6 | `nhiem_vu_2_2` | **nhiệm vụ 2** | Lĩnh vực 1 | Chưa phân công phòng ban | Chưa phân công cán bộ |
| 7 | `nhiem_vu_3` | **nhiệm vụ 3** | Nông nghiệp | Chưa phân công phòng ban | Chưa phân công cán bộ |
| 8 | `phat_trien_nong_thon` | **Phát triển nông thôn** | Nông nghiệp | Chi cục, Phòng nông nghiệp | Tăng Thị Mỹ Lành (tzyalnh - Chức vụ: BA - Vai trò: LEADER) — Chi cục |

---

## 5. KIẾN TRÚC GENERATIVE UI / HYBRID CHAT-GUI (5 TÍNH NĂNG NÂNG CẤP TRẢI NGHIỆM ĐIỀU HÀNH)

Hệ thống tích hợp **5 tính năng Generative UI / Hybrid Chat-GUI** giúp chuyển đổi kết quả tra cứu từ văn bản tĩnh sang giao diện tương tác trực tiếp (`0ms Client-side` cho các thao tác lọc, đối chiếu và trượt thời gian):

| STT | Mã Tính Năng | Tên Tính Năng Generative UI | Thành Phần Backend & Frontend | Cơ Chế Vận Hành & Tương Tác (`data-testid`) |
| :---: | :---: | :--- | :--- | :--- |
| 1 | **`GP 1.3`** | **Adaptive Criteria Tree Modal** *(Sơ đồ cây thích ứng)* | `SmartTable.tsx` (`InteractiveCriteriaTreeModal`, `InteractiveCriteriaTreeCanvas`) | • **Sticky Root (`data-testid="tree-sticky-root-column"`):** Cột gốc Cấp 1 ghim cố định `sticky top-4` khi cuộn dọc.<br/>• **Sub-Grid 2 cột Cấp 3:** Tự động thu gọn nhánh Cấp 3 khi tổng con $> 7$; khi mở rộng sẽ gom Cấp 3 vào khung lưới 2 cột nối bằng 1 đường cong SVG Cubic Bezier.<br/>• **Tìm kiếm giữ nhánh cha (`data-testid="tree-search-input"`):** Hỗ trợ gõ tiếng Việt không dấu, tô vàng từ khóa khớp (`data-testid="tree-search-highlight"`) và nút đặt lại (`data-testid="tree-empty-reset-button"`).<br/>• **Bộ lọc trạng thái (`data-testid="tree-status-filter"`):** `[Tất cả]`, `[⚡ Đã có số liệu]`, `[Chưa có số liệu (-)]`.<br/>• **Chuyển chế độ xem (`data-testid="tree-view-switcher"`):** `[🌳 Sơ đồ cây \| 📋 Bảng thu gọn]`. |
| 2 | **`GP 2.3` + `Đề xuất 3`** | **Kiến Trúc 2 Tầng Chống Ping-Pong** *(In-Modal Comparison Tray + Split-Screen Pinned Drawer)* | `SmartTable.tsx`, `PinnedReferenceDrawer.tsx`, `ChatContainer.tsx` | • **Tầng 1 — Khay Đối Chiếu Tại Chỗ (`data-testid="tree-comparison-tray"`, `0ms`, `0 request`):** Bấm chọn 1–4 chỉ tiêu con để dựng 1–4 Thẻ 5 Trường Chuẩn kèm thanh **Sparkbar** so sánh tỷ lệ ngay dưới đáy Modal; tự động thay thế FIFO khi chọn thẻ thứ 5; nút `💬 Đẩy bảng đối chiếu ra luồng Chat` (`data-testid="push-comparison-to-chat"`).<br/>• **Tầng 2 — Khay Ghim Tham Chiếu Bên Phải (`data-testid="pinned-reference-drawer"`, tối đa 3 Tab):** Nút `📌 Ghim` (`data-testid="pin-item-button"`) trên Bảng / Cây / Thẻ chỉ tiêu giúp ghim cố định sang cột phải màn hình, hỗ trợ tìm kiếm nhanh trong khay (`data-testid="pinned-drawer-search-input"`) và drill-down bảo toàn `temporal_scope.query_suffix` (`data-testid="pinned-table-drilldown-0"`). |
| 3 | **`Đề xuất 4`** | **Value-Preview Action Chips** *(Chip gợi ý kèm số liệu xem trước cho `SC-2.4`)* | `warehouse_langgraph_agent.py`, `QuickActionChips.tsx` | • Làm giàu `quick_action_chips` của `SC-2.4a` và `SC-2.4b` với `preview_value`, `child_count`, `is_parent_group`.<br/>• Hiển thị huy hiệu số liệu (`data-testid="chip-preview-badge"`), huy hiệu nhóm con (`data-testid="chip-group-badge"`) hoặc trạng thái (`data-testid="chip-status-badge"`), tôn trọng bộ lọc thời gian đang áp dụng và giữ nguyên nhóm cha trung gian (`Tổng số LHHTX phân theo lĩnh vực · 🌳 3 chỉ tiêu con`). |
| 4 | **`Đề xuất 5 Mở rộng`** | **Ticket `slider-time` & Context Ticket Bar** *(Thanh trượt kỳ báo cáo `0ms` & Khung ngữ cảnh bảng)* | `duckdb_semantic_catalog.py` (`get_criterion_timeline_snapshots`), `SingleMetricSliderCard.tsx`, `SmartTable.tsx` | • **Thẻ Đơn Chỉ Tiêu (`REQ-Q02`, `SC-2.4a`):** Đính kèm `single_metric_card` chứa `timeline_snapshots` (sắp xếp tăng dần kèm `delta_prev`, `delta_pct`), cảnh báo trượt thời gian (`data-testid="slider-temporal-shift-notice"`), kéo thanh trượt `0ms` (`data-testid="metric-timeline-range"`) hoặc chọn ngày tùy chỉnh theo thuật toán Dual-Bound Snapshot (`data-testid="slider-custom-date-input"` + `data-testid="slider-custom-date-apply"`).<br/>• **Context Ticket Bar trên Bảng (`SC-2.1`, `REQ-Q01`, `REQ-Q03`, `REQ-Q04`):** Hiển thị thanh vé ngữ cảnh (`data-testid="smart-table-context-ticket-bar"`) với các nút chuyển kỳ `[Năm 2026 (Mới nhất)]`, `[Quý 1]`, `[Quý 2]`, `[Quý 3]` và chọn ngày tùy chỉnh (`data-testid="context-ticket-date-input"`). |
| 5 | **`Đề xuất 6`** | **1-Click Quick Filter Toggle Pills** *(Bộ lọc 1 chạm trên `SmartTable`)* | `SmartTable.tsx` (`data-testid="smart-table-quick-filters"`) | • **Bảng Chỉ tiêu (`REQ-Q01`, `REQ-Q04`):** `[Tất cả]`, `[⚡ Đã có số liệu]`, `[🌳 Có chỉ tiêu con]`.<br/>• **Bảng Kiểm toán (`REQ-Q05` / `SC-5.1`, `SC-5.2`):** `[Tất cả]`, `[⚡ Chỉ hiện dòng có chênh lệch]`, `[⚠️ Bản nháp chưa nộp]`. |

