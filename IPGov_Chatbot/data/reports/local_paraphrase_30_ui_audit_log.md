# Nhật Ký Kiểm Thử Tương Tác Local UI — Bộ 30 Câu Hỏi Paraphrase Kèm Lọc Thời Gian

- **Tên đợt kiểm thử (Batch Name)**: `LOCAL_PARAPHRASE_30_BENCHMARK_V2`
- **Thời gian thực thi (Timestamp)**: `2026-10-27 10:25:30 — 10:43:18 +07:00`
- **Môi trường kiểm thử**: Local UI (`http://localhost:3000/`) kết nối trực tiếp Backend (`http://127.0.0.1:8000`) & CSDL PostgreSQL (`vna_wom_dev` @ `104.248.155.6:5432`)
- **Phiên hội thoại (Single Continuous Session ID)**: `session-1793071561993` (60 tin nhắn = 30 câu hỏi + 30 câu trả lời liên tục trong 1 phiên duy nhất, được giữ nguyên trên trình duyệt để kiểm tra)
- **Cấu hình hiển thị**: Zoom `80%`, đóng thanh lịch sử bên trái (Sidebar Collapsed), chờ hệ thống hoàn tất `thinking` 100% trước khi chụp
- **Bất biến Toán học Pairwise Jaccard (`C(30, 2) = 435` cặp)**: `Max Pairwise Jaccard = 0.2778 < 0.30` (27.78%), `Avg Pairwise Jaccard = 0.0322 < 0.10` (3.22%)
- **Kết quả tổng hợp**: **30 / 30 (100% Correct)** cho cả câu trả lời chính và kết quả sau khi bấm các nút ticket thời gian (`1–3` nút/câu).

---

## Bảng Tổng Hợp 30 Câu Hỏi Kiểm Thử (`Q01` – `Q30`)

| Mã | Nhóm truy vấn | Câu hỏi Paraphrase (kèm lọc thời gian) | Kết quả ban đầu | Kết quả sau bấm nút | Đánh giá |
| :---: | :--- | :--- | :--- | :--- | :---: |
| **Q01** | `SINGLE_CRITERION` | cho tôi biết Số lượng hợp tác xã nông nghiệp đạt hiệu quả tốt trong quý 1 | Giá trị: 56 | Bảng cập nhật tại chỗ (in-place): Kỳ 30/09/2026 hiển thị Giá trị = 56; chuyển sang Kỳ 30/06/2026 hiển thị Giá trị = 57 (biến động +1 so với Quý 1) | **Correct** |
| **Q02** | `SINGLE_CRITERION` | cho biết Số lượng hợp tác xã nông nghiệp mới được cấp phép trong quý 1 | Giá trị: 2 | Bảng cập nhật tại chỗ: Kỳ 30/09/2026 hiển thị Giá trị = 3; Kỳ 30/06/2026 hiển thị Giá trị = 5 (biến động +3 so với Quý 1) | **Correct** |
| **Q03** | `SINGLE_CRITERION` | Số lượng các thành viên tham gia vào hợp tác xã nông nghiệp trong quý 2 | Giá trị: 5,208 (5.208) | Bảng cập nhật tại chỗ: Kỳ 30/09/2026 hiển thị 5.200; Kỳ 31/03/2026 hiển thị 5.198 (giảm 10 thành viên so với Quý 2) | **Correct** |
| **Q04** | `SINGLE_CRITERION` | Diện tích đồng muối canh tác theo phương thức công nghiệp vào tháng 6 năm 2026 | Giá trị: 520 | Bảng cập nhật tại chỗ: Kỳ 31/03/2026 = 520; Kỳ 31/07/2026 = 0 (biến động -520) | **Correct** |
| **Q05** | `SINGLE_CRITERION` | Quy mô ruộng muối kết tinh bằng phương pháp truyền thống thủ công ngày 15/06/2026 | Giá trị: 1,000 (1.000) | Bảng cập nhật tại chỗ: Kỳ 31/03/2026 = 1.000; Kỳ 31/07/2026 = 0 (biến động -1.000) | **Correct** |
| **Q06** | `SINGLE_CRITERION` | Khối lượng hạt muối thu hoạch từ dây chuyền công nghiệp hiện đại trong quý 2 | Giá trị: 5,500 (5.500) | Bảng cập nhật tại chỗ: Kỳ 31/03/2026 = 5.500; Kỳ 31/07/2026 = 0 (biến động -5.500) | **Correct** |
| **Q07** | `SINGLE_CRITERION` | Các tổ hợp tác nông thôn được cấp đăng ký mới tại quý 1 năm 2026 | Giá trị: 15 | Bảng cập nhật tại chỗ: Kỳ 30/06/2026 = 15; Kỳ 30/09/2026 = 15 | **Correct** |
| **Q08** | `SINGLE_CRITERION` | Mức thu nhập doanh số bình quân của mỗi chủ trang trại trong năm 2026 | Giá trị: 2,200 (2.200) | Bảng cập nhật tại chỗ: Kỳ 31/03/2026 = 620; Kỳ 30/06/2026 = 1.450 (tăng +830 so với Quý 1) | **Correct** |
| **Q09** | `SINGLE_CRITERION` | Tổng số hộ diêm dân bám nghề làm muối tính đến quý 3 năm 2026 | Giá trị: 0 | Bảng cập nhật tại chỗ: Kỳ 30/06/2026 = 660; Kỳ 31/03/2026 = 660 | **Correct** |
| **Q10** | `SINGLE_CRITERION` | Chủ thể sở hữu sản phẩm đạt chuẩn 4 sao chương trình mỗi xã một sản phẩm lũy kế đến quý 2 | Giá trị: 26 | Bảng cập nhật tại chỗ qua các kỳ: 31/03/2026 = 23, 30/09/2026 = 27, và 12/10/2026 = 2 | **Correct** |
| **Q11** | `PARENT_CHILDREN_BREAKDOWN` | Tình hình liên kết sản xuất của hợp tác xã nông nghiệp ở quý 2 | 2 chỉ tiêu con theo đúng canonical_order: (1) Số HTX nông nghiệp có liên kết sản xuất ổn định = 120; (2) Số HTX nông nghiệp có liên kết không ổn định, thường xuyên = 10 | Bảng 2 chỉ tiêu con cập nhật tại chỗ: Quý 1 = [125; 5]; Quý 3 = [130; 8] | **Correct** |
| **Q12** | `PARENT_CHILDREN_BREAKDOWN` | Phân loại các lĩnh vực hoạt động của khu vực HTX trong quý 1 | 8 chỉ tiêu con đúng thứ tự chuẩn: Trồng trọt (25), Chăn nuôi (25), Lâm nghiệp (15), Thủy sản (15), Diêm nghiệp (7), Chế biến nông sản (15), Nước sạch NT (15), Khác (tổng hợp, dịch vụ,...) (13) | Bảng 8 chỉ tiêu con cập nhật tại chỗ: Quý 2 (Tổng 135) = [25; 25; 15; 15; 7; 15; 15; 18]; Quý 3 (Tổng 138) = [25; 25; 15; 15; 10; 15; 15; 18] | **Correct** |
| **Q13** | `PARENT_CHILDREN_BREAKDOWN` | Xếp hạng các bậc đánh giá hiệu quả vận hành của khối HTX vào quý 2 năm 2026 | 4 chỉ tiêu con đúng thứ tự chuẩn: Tốt (57), Trung bình/Khá (55), Kém hiệu quả (16), Chưa đủ điều kiện đánh giá (0) | Bảng 4 chỉ tiêu con cập nhật tại chỗ: Quý 1 (Tổng 122) = [56; 50; 16; 0]; Quý 3 (Tổng 130) = [56; 55; 16; 3] | **Correct** |
| **Q14** | `PARENT_CHILDREN_BREAKDOWN` | Cơ cấu các loại hình ruộng cấu thành tổng diện tích sản xuất muối đến tháng 6/2026 | 2 chỉ tiêu con: Diện tích muối sản xuất thủ công (1.000), Diện tích muối sản xuất công nghiệp (520) | Bảng 2 chỉ tiêu con cập nhật tại chỗ: Quý 1 (Tổng 1.520) = [1.000; 520]; Quý 3 (Tổng 0) = [0; 0] | **Correct** |
| **Q15** | `PARENT_CHILDREN_BREAKDOWN` | Phân bổ các lĩnh vực canh tác bên khối tổ hợp tác trong quý 1 | 8 chỉ tiêu con: Trồng trọt (168), Chăn nuôi (135), Lâm nghiệp (44), Thủy sản (67), Diêm nghiệp (26), Chế biến nông sản (43), Nước sạch NT (22), Khác (10) | Bảng 8 chỉ tiêu con cập nhật tại chỗ: Quý 2 (Tổng 530) = [173; 140; 45; 69; 26; 45; 22; 10]; Quý 3 (Tổng 545) = [178; 144; 46; 71; 26; 47; 23; 10] | **Correct** |
| **Q16** | `PARENT_CHILDREN_BREAKDOWN` | Các mảng lĩnh vực chuyên ngành thuộc liên hiệp hợp tác xã tại quý 2 | 8 chỉ tiêu con: Trồng trọt (1), Chăn nuôi (1), Lâm nghiệp (0), Thủy sản (1), Diêm nghiệp (0), Chế biến nông sản (1), Nước sạch NT (0), Khác (0) | Bảng 8 chỉ tiêu con cập nhật tại chỗ: Quý 1 (Tổng 3) = [1; 1; 0; 1; 0; 0; 0; 0]; Quý 3 (Tổng 3) = [1; 0; 1; 0; 1; 0; 0; 0] | **Correct** |
| **Q17** | `PARENT_CHILDREN_BREAKDOWN` | Cơ cấu tổng đàn vật nuôi gia súc trên địa bàn tỉnh trong quý 1 năm 2026 | Tại Quý 1/2026: Số lượng trâu = Chưa có số liệu (-), Số lượng bò = Chưa có số liệu (-) (do dữ liệu gia súc chỉ phát sinh vào Quý 4 ngày 15-16/10/2026) | Bảng cập nhật tại chỗ: Khi bấm [Năm 2026 (Mới nhất)], hiển thị đầy đủ Số lượng trâu = 170 (15/10/2026) và Số lượng bò = 256 (15/10/2026), Tổng = 426 | **Correct** |
| **Q18** | `PARENT_CHILDREN_BREAKDOWN` | Phân nhóm các chuyên ngành sản xuất thuộc kinh tế trang trại vào quý 2 | 7 chỉ tiêu con: Trồng trọt (25), Chăn nuôi (61), Lâm nghiệp (2), Nuôi trồng thủy sản (14), Sản xuất muối (3), Chế biến nông sản (3), Khác (2) | Bảng 7 chỉ tiêu con cập nhật tại chỗ: Quý 1 (Tổng 105) = [24; 58; 2; 13; 3; 3; 2]; Quý 3 (Tổng 115) = [26; 64; 2; 15; 3; 3; 2] | **Correct** |
| **Q19** | `PARENT_CHILDREN_BREAKDOWN` | Tỷ trọng tổng sản lượng muối thu hoạch theo từng phương pháp ngày 30/04/2026 | 2 chỉ tiêu con: Sản lượng muối sản xuất thủ công (21.500), Sản lượng muối sản xuất công nghiệp (5.500) | Bảng 2 chỉ tiêu con cập nhật tại chỗ: Quý 2 (Tổng 27.000) = [21.500; 5.500]; Quý 3 (Tổng 0) = [0; 0] | **Correct** |
| **Q20** | `PARENT_CHILDREN_BREAKDOWN` | Phân hạng cấp độ sao của các sản phẩm OCOP được thẩm định trong năm 2026 | 3 chỉ tiêu con: Sản phẩm OCOP 3 sao (12), Sản phẩm OCOP 4 sao (2), Sản phẩm OCOP 5 sao (2) | Bảng 3 chỉ tiêu con cập nhật tại chỗ: Quý 1 (Tổng 8) = [6; 2; 0]; Quý 2 (Tổng 26) = [20; 6; 0]; Quý 3 (Tổng 32) = [24; 8; 0] | **Correct** |
| **Q21** | `CROSS_BRANCH_COMPARISON` | Đối chiếu số đơn vị mới thành lập giữa các mô hình kinh tế tập thể trong năm 2026 | Bảng đối chiếu liên nhánh 'Thành lập mới' (Năm 2026 - kỳ mới nhất 30/09/2026) gồm 4 nhánh: HTX nông nghiệp (3), Liên hiệp HTX nông nghiệp (0), Tổ hợp tác nông nghiệp (15), Trang trại (5) | Bảng 4 nhánh cập nhật tại chỗ: Quý 1 = [2; 0; 15; 3]; Quý 2 = [5; 1; 15; 5] | **Correct** |
| **Q22** | `CROSS_BRANCH_COMPARISON` | So sánh quy mô mảng chăn nuôi giữa các loại hình tổ chức nông nghiệp ngày 30/04/2026 | Bảng đối chiếu liên nhánh 'Chăn nuôi' (Mốc 30/04/2026 ➔ đối chiếu kỳ chốt sổ gần nhất 31/03/2026) gồm 4 nhánh: HTX nông nghiệp (25), Liên hiệp HTX nông nghiệp (1), Tổ hợp tác nông nghiệp (135), Trang trại (58) | Bảng 4 nhánh cập nhật tại chỗ: Quý 2 = [25; 1; 140; 61]; Quý 3 = [25; 0; 144; 64] | **Correct** |
| **Q23** | `CROSS_BRANCH_COMPARISON` | Thống kê chuyên ngành trồng trọt qua từng loại hình đơn vị kinh doanh ở quý 1 | Bảng đối chiếu liên nhánh 'Trồng trọt' (Quý 1/2026 - 31/03/2026) gồm 4 nhánh: HTX nông nghiệp (25), Liên hiệp HTX nông nghiệp (1), Tổ hợp tác nông nghiệp (168), Trang trại (24) | Bảng 4 nhánh cập nhật tại chỗ: Quý 2 = [25; 1; 173; 25]; Quý 3 = [25; 1; 178; 26] | **Correct** |
| **Q24** | `CROSS_BRANCH_COMPARISON` | Tổng hợp lực lượng thành viên góp vốn giữa các khối kinh tế hợp tác tại quý 2 | Bảng đối chiếu liên nhánh 'Thành viên' (Quý 2/2026 - 30/06/2026) gồm 4 nhánh: HTX nông nghiệp (5.208), Liên hiệp HTX nông nghiệp (28), Tổ hợp tác nông nghiệp (1.350), Trang trại (550) | Bảng 4 nhánh cập nhật tại chỗ: Quý 1 = [5.198; 22; 1.300; 525]; Quý 3 = [5.200; 30; 1.400; 575] | **Correct** |
| **Q25** | `CROSS_BRANCH_COMPARISON` | Đặt lên bàn cân mảng thủy sản ở các mô hình tổ chức trong quý 1 | Bảng đối chiếu liên nhánh 'Thủy sản' (Quý 1/2026 - 31/03/2026) gồm 3 nhánh: HTX nông nghiệp (15), Liên hiệp HTX nông nghiệp (1), Tổ hợp tác nông nghiệp (67) | Bảng 3 nhánh cập nhật tại chỗ: Quý 2 = [15; 1; 69]; Quý 3 = [15; 0; 71] | **Correct** |
| **Q26** | `CROSS_BRANCH_COMPARISON` | Khảo sát số cơ sở đang duy trì hoạt động qua các định chế kinh tế vào quý 2 | Bảng đối chiếu liên nhánh 'Đang hoạt động' (Quý 2/2026 - 30/06/2026) gồm 4 nhánh: HTX nông nghiệp (128), Liên hiệp HTX nông nghiệp (4), Tổ hợp tác nông nghiệp (500), Trang trại (105) | Bảng 4 nhánh cập nhật tại chỗ: Quý 1 = [122; 3; 485; 100]; Quý 3 = [130; 4; 515; 110] | **Correct** |
| **Q27** | `CROSS_BRANCH_COMPARISON` | Đối sánh lĩnh vực lâm nghiệp giữa các khối tổ chức nông thôn trong quý 1 năm 2026 | Bảng đối chiếu liên nhánh 'Lâm nghiệp' (Quý 1/2026 - 31/03/2026) gồm 4 nhánh: HTX nông nghiệp (15), Liên hiệp HTX nông nghiệp (0), Tổ hợp tác nông nghiệp (44), Trang trại (2) | Bảng 4 nhánh cập nhật tại chỗ: Quý 2 = [15; 0; 45; 2]; Quý 3 = [15; 1; 46; 2] | **Correct** |
| **Q28** | `CROSS_BRANCH_COMPARISON` | Rà soát mảng chế biến nông sản qua từng hệ thống đơn vị tập thể ở quý 2 | Bảng đối chiếu liên nhánh 'Chế biến nông sản' (Quý 2/2026 - 30/06/2026) gồm 4 nhánh: HTX nông nghiệp (15), Liên hiệp HTX nông nghiệp (1), Tổ hợp tác nông nghiệp (45), Trang trại (3) | Bảng 4 nhánh cập nhật tại chỗ: Quý 1 = [15; 0; 43; 3]; Quý 3 = [15; 0; 47; 3] | **Correct** |
| **Q29** | `CROSS_BRANCH_COMPARISON` | So chiếu mảng cung cấp nước sạch NT giữa các nhóm chủ thể quản lý tại quý 1 | Bảng đối chiếu liên nhánh 'Nước sạch NT' (Quý 1/2026 - 31/03/2026) gồm 3 nhánh: HTX nông nghiệp (15), Liên hiệp HTX nông nghiệp (0), Tổ hợp tác nông nghiệp (22) | Bảng 3 nhánh cập nhật tại chỗ: Quý 2 = [15; 0; 22]; Quý 3 = [15; 0; 23] | **Correct** |
| **Q30** | `CROSS_BRANCH_COMPARISON` | Bức tranh nghề truyền thống được công nhận giữa số phát sinh và lũy kế trong quý 2 | Bảng đối chiếu liên nhánh 'Nghề truyền thống' (Quý 2/2026 - 30/06/2026) gồm 2 nhánh: Tổng số làng nghề, làng nghề truyền thống, nghề truyền thống được công nhận trong năm (0), Lũy kế Số làng nghề, làng nghề truyền thống, nghề truyền thống được công nhận (4) | Bảng 2 nhánh cập nhật tại chỗ: Quý 1 = [0; 4]; Quý 3 = [0; 4] | **Correct** |

---

## Chi Tiết Nhật Ký Kiểm Thử & Ảnh Minh Chứng (`Q01` – `Q30`)

### Q01 (SINGLE_CRITERION): "cho tôi biết Số lượng hợp tác xã nông nghiệp đạt hiệu quả tốt trong quý 1"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'đạt hiệu quả tốt' + 'hợp tác xã nông nghiệp' ➔ Chỉ tiêu lá 'Số HTX nông nghiệp hoạt động hiệu quả tốt' (Cấp 3, thuộc nhóm 'Hiệu quả hoạt động' > 'HTX nông nghiệp')
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Chỉ tiêu: Số HTX nông nghiệp hoạt động hiệu quả tốt | Giá trị: 56 | Kỳ báo cáo: 31/03/2026 (Quý 1/2026) | Đơn vị: Chi cục | Nhiệm vụ: Phát triển nông thôn
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (code='so_htx_nong_nghiep_hoat_dong_hieu_qua_tot'): 31/03/2026 = 56; 30/06/2026 = 57; 30/09/2026 = 56 (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian trong box 'Kỳ báo cáo đối chiếu': [Quý 3 · 30/09/2026: 56] ➔ [Quý 2 · 30/06/2026: 57]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng cập nhật tại chỗ (in-place): Kỳ 30/09/2026 hiển thị Giá trị = 56; chuyển sang Kỳ 30/06/2026 hiển thị Giá trị = 57 (biến động +1 so với Quý 1)
- **Nhận xét & Kết luận**: **Correct — Hệ thống phân giải chính xác câu hỏi paraphrase 'Số lượng hợp tác xã nông nghiệp đạt hiệu quả tốt trong quý 1' về đúng chỉ tiêu lá 'Số HTX nông nghiệp hoạt động hiệu quả tốt' tại mốc 31/03/2026 với giá trị 56. Khi bấm các nút ticket Quý 3 (30/09/2026) và Quý 2 (30/06/2026), bảng cập nhật tức thì tại chỗ sang giá trị 56 và 57, khớp tuyệt đối 100% với CSDL PostgreSQL vna_wom_dev và nội dung hình ảnh minh chứng.**

#### Minh chứng hình ảnh Q01
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q01_initial.png`)**:
  ![Q01 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q01_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q01_after_buttons.png`)**:
  ![Q01 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q01_after_buttons.png)

---

### Q02 (SINGLE_CRITERION): "cho biết Số lượng hợp tác xã nông nghiệp mới được cấp phép trong quý 1"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'mới được cấp phép' + 'hợp tác xã nông nghiệp' ➔ Chỉ tiêu lá 'Thành lập mới' (Cấp 2, thuộc nhánh 'HTX nông nghiệp')
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Chỉ tiêu: Thành lập mới (Thuộc nhóm: HTX nông nghiệp - Cấp 2) | Giá trị: 2 | Kỳ báo cáo: 31/03/2026 (Quý 1/2026)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (code='thanh_lap_moi', parent='HTX nông nghiệp'): 31/03/2026 = 2; 30/06/2026 = 5; 30/09/2026 = 3 (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 3 · 30/09/2026: 3] ➔ [Quý 2 · 30/06/2026: 5]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng cập nhật tại chỗ: Kỳ 30/09/2026 hiển thị Giá trị = 3; Kỳ 30/06/2026 hiển thị Giá trị = 5 (biến động +3 so với Quý 1)
- **Nhận xét & Kết luận**: **Correct — Hệ thống ánh xạ chuẩn xác cụm paraphrase 'mới được cấp phép' sang chỉ tiêu 'Thành lập mới' thuộc nhánh cha 'HTX nông nghiệp' tại ngày 31/03/2026 (Quý 1) với giá trị 2. Sau khi bấm nút ticket Quý 3 và Quý 2, số liệu trên bảng chuyển đổi chính xác sang 3 và 5, khớp 100% với dữ liệu kho vna_wom_dev.**

#### Minh chứng hình ảnh Q02
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q02_initial.png`)**:
  ![Q02 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q02_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q02_after_buttons.png`)**:
  ![Q02 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q02_after_buttons.png)

---

### Q03 (SINGLE_CRITERION): "Số lượng các thành viên tham gia vào hợp tác xã nông nghiệp trong quý 2"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'các thành viên tham gia vào hợp tác xã nông nghiệp' ➔ Chỉ tiêu lá 'Thành viên' (Cấp 2, thuộc nhánh 'HTX nông nghiệp')
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Chỉ tiêu: Thành viên (Thuộc nhóm: HTX nông nghiệp - Cấp 2) | Giá trị: 5,208 (5.208) | Kỳ báo cáo: 30/06/2026 (Quý 2/2026)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (code='thanh_vien', parent='HTX nông nghiệp'): 31/03/2026 = 5,198; 30/06/2026 = 5,208; 30/09/2026 = 5,200 (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 3 · 30/09/2026: 5.200] ➔ [Quý 1 · 31/03/2026: 5.198]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng cập nhật tại chỗ: Kỳ 30/09/2026 hiển thị 5.200; Kỳ 31/03/2026 hiển thị 5.198 (giảm 10 thành viên so với Quý 2)
- **Nhận xét & Kết luận**: **Correct — Hệ thống nhận diện chính xác chỉ tiêu 'Thành viên' thuộc nhánh 'HTX nông nghiệp' ở Quý 2 (30/06/2026) với số liệu 5,208. Thao tác bấm nút ticket Quý 3 (30/09/2026) và Quý 1 (31/03/2026) cập nhật bảng tại chỗ về đúng 5.200 và 5.198, khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q03
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q03_initial.png`)**:
  ![Q03 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q03_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q03_after_buttons.png`)**:
  ![Q03 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q03_after_buttons.png)

---

### Q04 (SINGLE_CRITERION): "Diện tích đồng muối canh tác theo phương thức công nghiệp vào tháng 6 năm 2026"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'Diện tích đồng muối canh tác theo phương thức công nghiệp' ➔ Chỉ tiêu lá 'Diện tích muối sản xuất công nghiệp' (Cấp 2, thuộc 'Tổng diện tích sản xuất muối')
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Chỉ tiêu: Diện tích muối sản xuất công nghiệp | Giá trị: 520 | Kỳ báo cáo: 30/06/2026 (Tháng 6/2026)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (code='dien_tich_muoi_san_xuat_cong_nghiep'): 31/03/2026 = 520; 30/06/2026 = 520; 31/07/2026 = 0 (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 1 · 31/03/2026: 520] ➔ [Quý 3 · 31/07/2026: 0]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng cập nhật tại chỗ: Kỳ 31/03/2026 = 520; Kỳ 31/07/2026 = 0 (biến động -520)
- **Nhận xét & Kết luận**: **Correct — Hệ thống phân giải đúng cụm paraphrase 'Diện tích đồng muối canh tác theo phương thức công nghiệp' về chỉ tiêu 'Diện tích muối sản xuất công nghiệp' kỳ 30/06/2026 với giá trị 520. Khi bấm sang ticket Quý 1 (31/03/2026) và Quý 3 (31/07/2026), bảng hiển thị chính xác 520 và 0, khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q04
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q04_initial.png`)**:
  ![Q04 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q04_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q04_after_buttons.png`)**:
  ![Q04 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q04_after_buttons.png)

---

### Q05 (SINGLE_CRITERION): "Quy mô ruộng muối kết tinh bằng phương pháp truyền thống thủ công ngày 15/06/2026"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'Quy mô ruộng muối kết tinh bằng phương pháp truyền thống thủ công' ➔ Chỉ tiêu lá 'Diện tích muối sản xuất thủ công' (Cấp 2, thuộc 'Tổng diện tích sản xuất muối')
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Chỉ tiêu: Diện tích muối sản xuất thủ công | Giá trị: 1,000 (1.000) | Kỳ báo cáo đối chiếu gần nhất: 30/06/2026 (cho mốc tra cứu 15/06/2026)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (code='dien_tich_muoi_san_xuat_thu_cong'): 31/03/2026 = 1,000; 30/06/2026 = 1,000; 31/07/2026 = 0 (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 1 · 31/03/2026: 1.000] ➔ [Quý 3 · 31/07/2026: 0]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng cập nhật tại chỗ: Kỳ 31/03/2026 = 1.000; Kỳ 31/07/2026 = 0 (biến động -1.000)
- **Nhận xét & Kết luận**: **Correct — Hệ thống giải nghĩa chính xác cụm 'Quy mô ruộng muối kết tinh bằng phương pháp truyền thống thủ công' về chỉ tiêu 'Diện tích muối sản xuất thủ công', tự động đối chiếu mốc chốt sổ gần nhất 30/06/2026 (cho ngày 15/06/2026) với giá trị 1,000. Bấm nút ticket Quý 1 và Quý 3 trả về đúng 1.000 và 0, khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q05
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q05_initial.png`)**:
  ![Q05 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q05_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q05_after_buttons.png`)**:
  ![Q05 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q05_after_buttons.png)

---

### Q06 (SINGLE_CRITERION): "Khối lượng hạt muối thu hoạch từ dây chuyền công nghiệp hiện đại trong quý 2"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'Khối lượng hạt muối thu hoạch từ dây chuyền công nghiệp hiện đại' ➔ Chỉ tiêu lá 'Sản lượng muối sản xuất công nghiệp' (Cấp 2, thuộc 'Tổng sản lượng muối edit 1')
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Chỉ tiêu: Sản lượng muối sản xuất công nghiệp | Giá trị: 5,500 (5.500) | Kỳ báo cáo: 30/06/2026 (Quý 2/2026)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (code='san_luong_muoi_san_xuat_cong_nghiep'): 31/03/2026 = 5,500; 30/06/2026 = 5,500; 31/07/2026 = 0 (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 1 · 31/03/2026: 5.500] ➔ [Quý 3 · 31/07/2026: 0]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng cập nhật tại chỗ: Kỳ 31/03/2026 = 5.500; Kỳ 31/07/2026 = 0 (biến động -5.500)
- **Nhận xét & Kết luận**: **Correct — Hệ thống phân biệt chính xác giữa 'Khối lượng hạt muối thu hoạch' (Sản lượng) và 'Diện tích', trả về đúng chỉ tiêu 'Sản lượng muối sản xuất công nghiệp' ở Quý 2 (30/06/2026) với giá trị 5,500. Bấm ticket Quý 1 và Quý 3 cập nhật bảng sang 5.500 và 0, khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q06
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q06_initial.png`)**:
  ![Q06 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q06_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q06_after_buttons.png`)**:
  ![Q06 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q06_after_buttons.png)

---

### Q07 (SINGLE_CRITERION): "Các tổ hợp tác nông thôn được cấp đăng ký mới tại quý 1 năm 2026"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'Các tổ hợp tác nông thôn được cấp đăng ký mới' ➔ Chỉ tiêu lá 'Thành lập mới' (Cấp 2, thuộc nhánh 'Tổ hợp tác nông nghiệp')
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Chỉ tiêu: Thành lập mới (Thuộc nhóm: Tổ hợp tác nông nghiệp - Cấp 2) | Giá trị: 15 | Kỳ báo cáo: 31/03/2026 (Quý 1/2026)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (code='thanh_lap_moi_3', parent='Tổ hợp tác nông nghiệp'): 31/03/2026 = 15; 30/06/2026 = 15; 30/09/2026 = 15 (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 2 · 30/06/2026: 15] ➔ [Quý 3 · 30/09/2026: 15]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng cập nhật tại chỗ: Kỳ 30/06/2026 = 15; Kỳ 30/09/2026 = 15
- **Nhận xét & Kết luận**: **Correct — Hệ thống định tuyến đúng nhánh 'Tổ hợp tác nông nghiệp' > 'Thành lập mới' tại Quý 1 (31/03/2026) với giá trị 15 (không bị lẫn với HTX nông nghiệp hay Trang trại). Bấm ticket Quý 2 và Quý 3 hiển thị đúng giá trị 15, khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q07
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q07_initial.png`)**:
  ![Q07 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q07_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q07_after_buttons.png`)**:
  ![Q07 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q07_after_buttons.png)

---

### Q08 (SINGLE_CRITERION): "Mức thu nhập doanh số bình quân của mỗi chủ trang trại trong năm 2026"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'Mức thu nhập doanh số bình quân của mỗi chủ trang trại' ➔ Chỉ tiêu lá 'Doanh thu bình quân trong năm của một Trang trại nông nghiệp' (Cấp 2, thuộc 'Trang trại')
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Chỉ tiêu: Doanh thu bình quân trong năm của một Trang trại nông nghiệp | Giá trị: 2,200 (2.200) | Kỳ báo cáo mới nhất năm 2026: 30/09/2026
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (code='doanh_thu_binh_quan_trong_nam_cua_mot_trang_trai_nong_nghiep'): 31/03/2026 = 620; 30/06/2026 = 1,450; 30/09/2026 = 2,200 (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 1 · 31/03/2026: 620] ➔ [Quý 2 · 30/06/2026: 1.450]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng cập nhật tại chỗ: Kỳ 31/03/2026 = 620; Kỳ 30/06/2026 = 1.450 (tăng +830 so với Quý 1)
- **Nhận xét & Kết luận**: **Correct — Hệ thống ánh xạ chính xác cụm paraphrase 'Mức thu nhập doanh số bình quân của mỗi chủ trang trại' về chỉ tiêu 'Doanh thu bình quân trong năm của một Trang trại nông nghiệp' với giá trị năm 2026 (kỳ 30/09/2026) là 2,200. Khi bấm ticket Quý 1 và Quý 2, số liệu đổi sang 620 và 1.450, khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q08
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q08_initial.png`)**:
  ![Q08 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q08_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q08_after_buttons.png`)**:
  ![Q08 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q08_after_buttons.png)

---

### Q09 (SINGLE_CRITERION): "Tổng số hộ diêm dân bám nghề làm muối tính đến quý 3 năm 2026"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'Tổng số hộ diêm dân bám nghề làm muối' ➔ Chỉ tiêu lá Cấp 1 'Tổng hộ sản xuất muối'
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Chỉ tiêu: Tổng hộ sản xuất muối (Chỉ tiêu gốc - Cấp 1) | Giá trị: 0 | Kỳ báo cáo Quý 3: 31/07/2026
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (code='tong_ho_san_xuat_muoi'): 31/03/2026 = 660; 30/06/2026 = 660; 31/07/2026 = 0 (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 2 · 30/06/2026: 660] ➔ [Quý 1 · 31/03/2026: 660]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng cập nhật tại chỗ: Kỳ 30/06/2026 = 660; Kỳ 31/03/2026 = 660
- **Nhận xét & Kết luận**: **Correct — Hệ thống nhận diện chính xác cụm paraphrase 'hộ diêm dân bám nghề làm muối' về chỉ tiêu 'Tổng hộ sản xuất muối' tại Quý 3 (31/07/2026) với giá trị 0. Khi bấm sang ticket Quý 2 (30/06/2026) và Quý 1 (31/03/2026), bảng hiển thị đúng 660 hộ, khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q09
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q09_initial.png`)**:
  ![Q09 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q09_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q09_after_buttons.png`)**:
  ![Q09 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q09_after_buttons.png)

---

### Q10 (SINGLE_CRITERION): "Chủ thể sở hữu sản phẩm đạt chuẩn 4 sao chương trình mỗi xã một sản phẩm lũy kế đến quý 2"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'Chủ thể sở hữu sản phẩm đạt chuẩn 4 sao chương trình mỗi xã một sản phẩm lũy kế' ➔ Chỉ tiêu lá 'Số lượng chủ thể sản phẩm OCOP 4 sao' (Cấp 3, thuộc 'Lũy kế tổng số lượng chủ thể đến thời điểm báo cáo')
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Chỉ tiêu: Số lượng chủ thể sản phẩm OCOP 4 sao (Thuộc nhóm: Lũy kế tổng số lượng chủ thể đến thời điểm báo cáo - Cấp 3) | Giá trị: 26 | Kỳ báo cáo: 30/06/2026
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (code='so_luong_chu_the_san_pham_ocop_4_sao'): 31/03/2026 = 23; 30/06/2026 = 26; 30/09/2026 = 27; 08/10/2026 = 12; 12/10/2026 = 2 (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 3 nút ticket thời gian: [Quý 1 · 31/03/2026: 23] ➔ [Quý 3 · 30/09/2026: 27] ➔ [Quý 4 · 12/10/2026: 2]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng cập nhật tại chỗ qua các kỳ: 31/03/2026 = 23, 30/09/2026 = 27, và 12/10/2026 = 2
- **Nhận xét & Kết luận**: **Correct — Hệ thống phân biệt chính xác nhánh 'Lũy kế' so với 'Trong năm' và cấp độ '4 sao', trả về đúng chỉ tiêu 'Số lượng chủ thể sản phẩm OCOP 4 sao' kỳ Quý 2 (30/06/2026) với giá trị 26. Bấm 3 nút ticket thời gian (Quý 1, Quý 3, Quý 4) cập nhật bảng chính xác sang 23, 27 và 2, khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q10
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q10_initial.png`)**:
  ![Q10 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q10_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q10_after_buttons.png`)**:
  ![Q10 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q10_after_buttons.png)

---

### Q11 (PARENT_CHILDREN_BREAKDOWN): "Tình hình liên kết sản xuất của hợp tác xã nông nghiệp ở quý 2"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'Tình hình liên kết sản xuất của hợp tác xã nông nghiệp' ➔ Nhóm cha 'Liên kết sản xuất' (Cấp 2, thuộc 'HTX nông nghiệp') gồm 2 chỉ tiêu con
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Nhóm cha: Liên kết sản xuất (Kỳ Quý 2/2026 - 30/06/2026) | 2 chỉ tiêu con theo đúng canonical_order: (1) Số HTX nông nghiệp có liên kết sản xuất ổn định = 120; (2) Số HTX nông nghiệp có liên kết không ổn định, thường xuyên = 10
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (parent='Liên kết sản xuất'): Q1 (31/03/2026) = [125; 5]; Q2 (30/06/2026) = [120; 10]; Q3 (30/09/2026) = [130; 8] (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 1] ➔ [Quý 3]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng 2 chỉ tiêu con cập nhật tại chỗ: Quý 1 = [125; 5]; Quý 3 = [130; 8]
- **Nhận xét & Kết luận**: **Correct — Hệ thống giải quyết trọn vẹn ví dụ Q4 của người dùng: tự động phân rã nhóm cha 'HTX nông nghiệp > Liên kết sản xuất' tại Quý 2 (30/06/2026) thành 2 chỉ tiêu con 'Số HTX nông nghiệp có liên kết sản xuất ổn định' (120) và 'Số HTX nông nghiệp có liên kết không ổn định, thường xuyên' (10). Bấm nút Quý 1 và Quý 3 cập nhật bảng thành [125; 5] và [130; 8], khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q11
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q11_initial.png`)**:
  ![Q11 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q11_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q11_after_buttons.png`)**:
  ![Q11 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q11_after_buttons.png)

---

### Q12 (PARENT_CHILDREN_BREAKDOWN): "Phân loại các lĩnh vực hoạt động của khu vực HTX trong quý 1"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'các lĩnh vực hoạt động của khu vực HTX' ➔ Nhóm cha 'Số lượng HTX phân theo lĩnh vực' (Cấp 2, thuộc 'HTX nông nghiệp') gồm 8 chỉ tiêu con
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Nhóm cha: Số lượng HTX phân theo lĩnh vực (Quý 1/2026, Tổng = 130) | 8 chỉ tiêu con đúng thứ tự chuẩn: Trồng trọt (25), Chăn nuôi (25), Lâm nghiệp (15), Thủy sản (15), Diêm nghiệp (7), Chế biến nông sản (15), Nước sạch NT (15), Khác (tổng hợp, dịch vụ,...) (13)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (parent='Số lượng HTX phân theo lĩnh vực'): Q1 = [25, 25, 15, 15, 7, 15, 15, 13] (Tổng 130); Q2 = [25, 25, 15, 15, 7, 15, 15, 18] (Tổng 135); Q3 = [25, 25, 15, 15, 10, 15, 15, 18] (Tổng 138) (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 2] ➔ [Quý 3]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng 8 chỉ tiêu con cập nhật tại chỗ: Quý 2 (Tổng 135) = [25; 25; 15; 15; 7; 15; 15; 18]; Quý 3 (Tổng 138) = [25; 25; 15; 15; 10; 15; 15; 18]
- **Nhận xét & Kết luận**: **Correct — Hệ thống phân rã chính xác 8 chỉ tiêu con của nhóm 'Số lượng HTX phân theo lĩnh vực' tại Quý 1 theo đúng thứ tự chuẩn trong kho dữ liệu. Khi bấm nút Quý 2 và Quý 3, toàn bộ 8 dòng và tổng nhóm cha cập nhật tức thì sang bộ số liệu Quý 2 (135) và Quý 3 (138), khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q12
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q12_initial.png`)**:
  ![Q12 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q12_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q12_after_buttons.png`)**:
  ![Q12 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q12_after_buttons.png)

---

### Q13 (PARENT_CHILDREN_BREAKDOWN): "Xếp hạng các bậc đánh giá hiệu quả vận hành của khối HTX vào quý 2 năm 2026"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'các bậc đánh giá hiệu quả vận hành của khối HTX' ➔ Nhóm cha 'Hiệu quả hoạt động' (Cấp 2, thuộc 'HTX nông nghiệp') gồm 4 chỉ tiêu con
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Nhóm cha: Hiệu quả hoạt động (Quý 2/2026, Tổng = 128) | 4 chỉ tiêu con đúng thứ tự chuẩn: Tốt (57), Trung bình/Khá (55), Kém hiệu quả (16), Chưa đủ điều kiện đánh giá (0)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (parent='Hiệu quả hoạt động'): Q1 = [56, 50, 16, 0] (Tổng 122); Q2 = [57, 55, 16, 0] (Tổng 128); Q3 = [56, 55, 16, 3] (Tổng 130) (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 1] ➔ [Quý 3]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng 4 chỉ tiêu con cập nhật tại chỗ: Quý 1 (Tổng 122) = [56; 50; 16; 0]; Quý 3 (Tổng 130) = [56; 55; 16; 3]
- **Nhận xét & Kết luận**: **Correct — Hệ thống nhận diện đúng nhóm cha 'Hiệu quả hoạt động' từ câu hỏi paraphrase 'Xếp hạng các bậc đánh giá hiệu quả vận hành của khối HTX vào quý 2 năm 2026', hiển thị đúng bộ số liệu Quý 2 [57; 55; 16; 0] theo đúng thứ tự chuẩn. Bấm ticket Quý 1 và Quý 3 cập nhật bảng sang [56; 50; 16; 0] và [56; 55; 16; 3], khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q13
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q13_initial.png`)**:
  ![Q13 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q13_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q13_after_buttons.png`)**:
  ![Q13 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q13_after_buttons.png)

---

### Q14 (PARENT_CHILDREN_BREAKDOWN): "Cơ cấu các loại hình ruộng cấu thành tổng diện tích sản xuất muối đến tháng 6/2026"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'các loại hình ruộng cấu thành tổng diện tích sản xuất muối' ➔ Nhóm cha 'Tổng diện tích sản xuất muối' (Cấp 1) gồm 2 chỉ tiêu con
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Nhóm cha: Tổng diện tích sản xuất muối (Kỳ Quý 2 / Tháng 6/2026, Tổng = 1,520) | 2 chỉ tiêu con: Diện tích muối sản xuất thủ công (1.000), Diện tích muối sản xuất công nghiệp (520)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (parent='Tổng diện tích sản xuất muối'): Q1 = [1.000; 520]; Q2 = [1.000; 520]; Q3 = [0; 0] (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 1] ➔ [Quý 3]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng 2 chỉ tiêu con cập nhật tại chỗ: Quý 1 (Tổng 1.520) = [1.000; 520]; Quý 3 (Tổng 0) = [0; 0]
- **Nhận xét & Kết luận**: **Correct — Hệ thống phân rã chính xác nhóm cha 'Tổng diện tích sản xuất muối' tại tháng 6/2026 thành 2 chỉ tiêu con 'Diện tích muối sản xuất thủ công' (1.000) và 'Diện tích muối sản xuất công nghiệp' (520). Bấm ticket Quý 1 và Quý 3 cập nhật bảng chính xác sang [1.000; 520] và [0; 0], khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q14
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q14_initial.png`)**:
  ![Q14 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q14_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q14_after_buttons.png`)**:
  ![Q14 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q14_after_buttons.png)

---

### Q15 (PARENT_CHILDREN_BREAKDOWN): "Phân bổ các lĩnh vực canh tác bên khối tổ hợp tác trong quý 1"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'các lĩnh vực canh tác bên khối tổ hợp tác' ➔ Nhóm cha 'Tổng số THT phân theo lĩnh vực' (Cấp 2, thuộc 'Tổ hợp tác nông nghiệp') gồm 8 chỉ tiêu con
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Nhóm cha: Tổng số THT phân theo lĩnh vực (Quý 1/2026, Tổng = 515) | 8 chỉ tiêu con: Trồng trọt (168), Chăn nuôi (135), Lâm nghiệp (44), Thủy sản (67), Diêm nghiệp (26), Chế biến nông sản (43), Nước sạch NT (22), Khác (10)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (parent='Tổng số THT phân theo lĩnh vực'): Q1 = [168, 135, 44, 67, 26, 43, 22, 10] (515); Q2 = [173, 140, 45, 69, 26, 45, 22, 10] (530); Q3 = [178, 144, 46, 71, 26, 47, 23, 10] (545) (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 2] ➔ [Quý 3]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng 8 chỉ tiêu con cập nhật tại chỗ: Quý 2 (Tổng 530) = [173; 140; 45; 69; 26; 45; 22; 10]; Quý 3 (Tổng 545) = [178; 144; 46; 71; 26; 47; 23; 10]
- **Nhận xét & Kết luận**: **Correct — Hệ thống phân giải đúng nhóm cha 'Tổng số THT phân theo lĩnh vực' ở Quý 1 (tổng 515, 8 lĩnh vực con). Bấm ticket Quý 2 và Quý 3 cập nhật bảng tức thì sang bộ số liệu Quý 2 (tổng 530) và Quý 3 (tổng 545), khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q15
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q15_initial.png`)**:
  ![Q15 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q15_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q15_after_buttons.png`)**:
  ![Q15 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q15_after_buttons.png)

---

### Q16 (PARENT_CHILDREN_BREAKDOWN): "Các mảng lĩnh vực chuyên ngành thuộc liên hiệp hợp tác xã tại quý 2"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'Các mảng lĩnh vực chuyên ngành thuộc liên hiệp hợp tác xã' ➔ Nhóm cha 'Tổng số LHHTX phân theo lĩnh vực' (Cấp 2, thuộc 'Liên hiệp HTX nông nghiệp') gồm 8 chỉ tiêu con
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Nhóm cha: Tổng số LHHTX phân theo lĩnh vực (Quý 2/2026, Tổng = 4) | 8 chỉ tiêu con: Trồng trọt (1), Chăn nuôi (1), Lâm nghiệp (0), Thủy sản (1), Diêm nghiệp (0), Chế biến nông sản (1), Nước sạch NT (0), Khác (0)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (parent='Tổng số LHHTX phân theo lĩnh vực'): Q1 = [1, 1, 0, 1, 0, 0, 0, 0] (3); Q2 = [1, 1, 0, 1, 0, 1, 0, 0] (4); Q3 = [1, 0, 1, 0, 1, 0, 0, 0] (3) (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 1] ➔ [Quý 3]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng 8 chỉ tiêu con cập nhật tại chỗ: Quý 1 (Tổng 3) = [1; 1; 0; 1; 0; 0; 0; 0]; Quý 3 (Tổng 3) = [1; 0; 1; 0; 1; 0; 0; 0]
- **Nhận xét & Kết luận**: **Correct — Hệ thống nhận diện đúng nhánh gốc 'Liên hiệp HTX nông nghiệp' từ cụm viết đầy đủ 'liên hiệp hợp tác xã' và phân rã chính xác 8 chỉ tiêu con của 'Tổng số LHHTX phân theo lĩnh vực' tại Quý 2 (tổng 4). Bấm ticket Quý 1 và Quý 3 cập nhật đúng số liệu từng ngành, khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q16
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q16_initial.png`)**:
  ![Q16 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q16_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q16_after_buttons.png`)**:
  ![Q16 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q16_after_buttons.png)

---

### Q17 (PARENT_CHILDREN_BREAKDOWN): "Cơ cấu tổng đàn vật nuôi gia súc trên địa bàn tỉnh trong quý 1 năm 2026"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'Cơ cấu tổng đàn vật nuôi gia súc' ➔ Nhóm cha 'Số lượng gia súc' (Cấp 1) gồm 2 chỉ tiêu con: 'Số lượng trâu', 'Số lượng bò'
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Nhóm cha: Số lượng gia súc (Tổng năm = 426) | Tại Quý 1/2026: Số lượng trâu = Chưa có số liệu (-), Số lượng bò = Chưa có số liệu (-) (do dữ liệu gia súc chỉ phát sinh vào Quý 4 ngày 15-16/10/2026)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (parent='Số lượng gia súc'): Q1/Q2/Q3 = Chưa phát sinh; Năm 2026 (15-16/10/2026) = [Số lượng trâu: 170, Số lượng bò: 256, Tổng: 426] (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 2] ➔ [Năm 2026 (Mới nhất)]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng cập nhật tại chỗ: Khi bấm [Năm 2026 (Mới nhất)], hiển thị đầy đủ Số lượng trâu = 170 (15/10/2026) và Số lượng bò = 256 (15/10/2026), Tổng = 426
- **Nhận xét & Kết luận**: **Correct — Hệ thống phân giải chính xác cụm paraphrase 'tổng đàn vật nuôi gia súc' về nhóm cha 'Số lượng gia súc' gồm 2 chỉ tiêu con ('Số lượng trâu', 'Số lượng bò'), phản ánh trung thực trạng thái chưa phát sinh số liệu ở Quý 1/Quý 2 và hiển thị chính xác [170; 256] (tổng 426) khi bấm nút 'Năm 2026 (Mới nhất)', khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q17
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q17_initial.png`)**:
  ![Q17 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q17_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q17_after_buttons.png`)**:
  ![Q17 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q17_after_buttons.png)

---

### Q18 (PARENT_CHILDREN_BREAKDOWN): "Phân nhóm các chuyên ngành sản xuất thuộc kinh tế trang trại vào quý 2"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'các chuyên ngành sản xuất thuộc kinh tế trang trại' ➔ Nhóm cha 'Tổng số lượng TT phân theo lĩnh vực' (Cấp 2, thuộc 'Trang trại') gồm 7 chỉ tiêu con
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Nhóm cha: Tổng số lượng TT phân theo lĩnh vực (Quý 2/2026, Tổng = 110) | 7 chỉ tiêu con: Trồng trọt (25), Chăn nuôi (61), Lâm nghiệp (2), Nuôi trồng thủy sản (14), Sản xuất muối (3), Chế biến nông sản (3), Khác (2)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (parent='Tổng số lượng TT phân theo lĩnh vực'): Q1 = [24, 58, 2, 13, 3, 3, 2] (105); Q2 = [25, 61, 2, 14, 3, 3, 2] (110); Q3 = [26, 64, 2, 15, 3, 3, 2] (115) (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 1] ➔ [Quý 3]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng 7 chỉ tiêu con cập nhật tại chỗ: Quý 1 (Tổng 105) = [24; 58; 2; 13; 3; 3; 2]; Quý 3 (Tổng 115) = [26; 64; 2; 15; 3; 3; 2]
- **Nhận xét & Kết luận**: **Correct — Hệ thống ánh xạ chuẩn xác 'các chuyên ngành sản xuất thuộc kinh tế trang trại' về nhóm cha 'Tổng số lượng TT phân theo lĩnh vực' (7 chỉ tiêu con, tổng 110 ở Quý 2). Bấm ticket Quý 1 và Quý 3 cập nhật bảng sang bộ số liệu Quý 1 (105) và Quý 3 (115), khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q18
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q18_initial.png`)**:
  ![Q18 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q18_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q18_after_buttons.png`)**:
  ![Q18 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q18_after_buttons.png)

---

### Q19 (PARENT_CHILDREN_BREAKDOWN): "Tỷ trọng tổng sản lượng muối thu hoạch theo từng phương pháp ngày 30/04/2026"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'tổng sản lượng muối thu hoạch theo từng phương pháp' ➔ Nhóm cha 'Tổng sản lượng muối edit 1' (Cấp 1) gồm 2 chỉ tiêu con
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Nhóm cha: Tổng sản lượng muối edit 1 (Mốc tra cứu 30/04/2026 ➔ đối chiếu kỳ chốt sổ gần nhất 31/03/2026, Tổng = 27,000) | 2 chỉ tiêu con: Sản lượng muối sản xuất thủ công (21.500), Sản lượng muối sản xuất công nghiệp (5.500)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (parent='Tổng sản lượng muối edit 1'): 31/03/2026 = [21.500; 5.500] (27.000); 30/06/2026 = [21.500; 5.500] (27.000); 31/07/2026 = [0; 0] (0) (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 2] ➔ [Quý 3]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng 2 chỉ tiêu con cập nhật tại chỗ: Quý 2 (Tổng 27.000) = [21.500; 5.500]; Quý 3 (Tổng 0) = [0; 0]
- **Nhận xét & Kết luận**: **Correct — Hệ thống phân rã chính xác nhóm cha 'Tổng sản lượng muối edit 1' tại mốc 30/04/2026 (đối chiếu kỳ 31/03/2026) thành 2 chỉ tiêu con [21.500; 5.500]. Khi bấm ticket Quý 2 và Quý 3, bảng cập nhật tức thì sang [21.500; 5.500] và [0; 0], khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q19
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q19_initial.png`)**:
  ![Q19 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q19_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q19_after_buttons.png`)**:
  ![Q19 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q19_after_buttons.png)

---

### Q20 (PARENT_CHILDREN_BREAKDOWN): "Phân hạng cấp độ sao của các sản phẩm OCOP được thẩm định trong năm 2026"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'Phân hạng cấp độ sao của các sản phẩm OCOP được thẩm định trong năm' ➔ Nhóm cha 'Tổng số lượng sản phẩm OCOP trong năm' (Cấp 2, thuộc 'Chương trình OCOP') gồm 3 chỉ tiêu con (3 sao, 4 sao, 5 sao)
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Nhóm cha: Tổng số lượng sản phẩm OCOP trong năm (Năm 2026, Tổng = 16) | 3 chỉ tiêu con: Sản phẩm OCOP 3 sao (12), Sản phẩm OCOP 4 sao (2), Sản phẩm OCOP 5 sao (2)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (parent='Tổng số lượng sản phẩm OCOP trong năm'): Năm 2026 (12/10/2026) = [12, 2, 2] (16); Q1 = [6, 2, 0] (8); Q2 = [20, 6, 0] (26); Q3 = [24, 8, 0] (32) (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 3 nút ticket thời gian: [Quý 1] ➔ [Quý 2] ➔ [Quý 3]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng 3 chỉ tiêu con cập nhật tại chỗ: Quý 1 (Tổng 8) = [6; 2; 0]; Quý 2 (Tổng 26) = [20; 6; 0]; Quý 3 (Tổng 32) = [24; 8; 0]
- **Nhận xét & Kết luận**: **Correct — Hệ thống nhận diện chính xác nhóm cha 'Tổng số lượng sản phẩm OCOP trong năm' (không bị cướp quyền bởi chỉ tiêu lá 3 sao/4 sao/5 sao khi câu hỏi không nêu số sao cụ thể) và liệt kê đủ 3 hạng sao [12; 2; 2]. Bấm 3 nút Quý 1, Quý 2, Quý 3 cập nhật bảng chính xác sang [6; 2; 0], [20; 6; 0] và [24; 8; 0], khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q20
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q20_initial.png`)**:
  ![Q20 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q20_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q20_after_buttons.png`)**:
  ![Q20 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q20_after_buttons.png)

---

### Q21 (CROSS_BRANCH_COMPARISON): "Đối chiếu số đơn vị mới thành lập giữa các mô hình kinh tế tập thể trong năm 2026"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'số đơn vị mới thành lập giữa các mô hình kinh tế tập thể' ➔ Chỉ tiêu đồng danh liên nhánh 'Thành lập mới' trên 4 nhánh cha
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Bảng đối chiếu liên nhánh 'Thành lập mới' (Năm 2026 - kỳ mới nhất 30/09/2026) gồm 4 nhánh: HTX nông nghiệp (3), Liên hiệp HTX nông nghiệp (0), Tổ hợp tác nông nghiệp (15), Trang trại (5)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (name='Thành lập mới'): Năm 2026/Q3 = [3, 0, 15, 5]; Q1 = [2, 0, 15, 3]; Q2 = [5, 1, 15, 5] (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 1] ➔ [Quý 2]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng 4 nhánh cập nhật tại chỗ: Quý 1 = [2; 0; 15; 3]; Quý 2 = [5; 1; 15; 5]
- **Nhận xét & Kết luận**: **Correct — Hệ thống đối chiếu chính xác chỉ tiêu đồng danh 'Thành lập mới' qua cả 4 nhánh kinh tế tập thể trong năm 2026 [3; 0; 15; 5]. Khi bấm nút ticket Quý 1 và Quý 2, cả 4 dòng cập nhật tức thì sang [2; 0; 15; 3] và [5; 1; 15; 5], khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q21
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q21_initial.png`)**:
  ![Q21 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q21_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q21_after_buttons.png`)**:
  ![Q21 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q21_after_buttons.png)

---

### Q22 (CROSS_BRANCH_COMPARISON): "So sánh quy mô mảng chăn nuôi giữa các loại hình tổ chức nông nghiệp ngày 30/04/2026"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'quy mô mảng chăn nuôi giữa các loại hình tổ chức nông nghiệp' ➔ Chỉ tiêu đồng danh liên nhánh 'Chăn nuôi' trên 4 nhánh cha
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Bảng đối chiếu liên nhánh 'Chăn nuôi' (Mốc 30/04/2026 ➔ đối chiếu kỳ chốt sổ gần nhất 31/03/2026) gồm 4 nhánh: HTX nông nghiệp (25), Liên hiệp HTX nông nghiệp (1), Tổ hợp tác nông nghiệp (135), Trang trại (58)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (name='Chăn nuôi'): 31/03/2026 = [25, 1, 135, 58]; Q2 (30/06/2026) = [25, 1, 140, 61]; Q3 (30/09/2026) = [25, 0, 144, 64] (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 2] ➔ [Quý 3]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng 4 nhánh cập nhật tại chỗ: Quý 2 = [25; 1; 140; 61]; Quý 3 = [25; 0; 144; 64]
- **Nhận xét & Kết luận**: **Correct — Hệ thống đối chiếu chính xác chỉ tiêu 'Chăn nuôi' trên 4 nhánh tại mốc 30/04/2026 (đối chiếu 31/03/2026: [25; 1; 135; 58]) và không sinh đoạn văn bản thừa phía dưới bảng. Bấm ticket Quý 2 và Quý 3 cập nhật bảng sang [25; 1; 140; 61] và [25; 0; 144; 64], khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q22
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q22_initial.png`)**:
  ![Q22 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q22_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q22_after_buttons.png`)**:
  ![Q22 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q22_after_buttons.png)

---

### Q23 (CROSS_BRANCH_COMPARISON): "Thống kê chuyên ngành trồng trọt qua từng loại hình đơn vị kinh doanh ở quý 1"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'chuyên ngành trồng trọt qua từng loại hình đơn vị kinh doanh' ➔ Chỉ tiêu đồng danh liên nhánh 'Trồng trọt' trên 4 nhánh cha
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Bảng đối chiếu liên nhánh 'Trồng trọt' (Quý 1/2026 - 31/03/2026) gồm 4 nhánh: HTX nông nghiệp (25), Liên hiệp HTX nông nghiệp (1), Tổ hợp tác nông nghiệp (168), Trang trại (24)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (name='Trồng trọt'): Q1 = [25, 1, 168, 24]; Q2 = [25, 1, 173, 25]; Q3 = [25, 1, 178, 26] (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 2] ➔ [Quý 3]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng 4 nhánh cập nhật tại chỗ: Quý 2 = [25; 1; 173; 25]; Quý 3 = [25; 1; 178; 26]
- **Nhận xét & Kết luận**: **Correct — Hệ thống liệt kê đầy đủ 4 nhánh của chỉ tiêu đồng danh 'Trồng trọt' ở Quý 1 [25; 1; 168; 24]. Bấm ticket Quý 2 và Quý 3 cập nhật bảng sang [25; 1; 173; 25] và [25; 1; 178; 26], khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q23
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q23_initial.png`)**:
  ![Q23 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q23_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q23_after_buttons.png`)**:
  ![Q23 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q23_after_buttons.png)

---

### Q24 (CROSS_BRANCH_COMPARISON): "Tổng hợp lực lượng thành viên góp vốn giữa các khối kinh tế hợp tác tại quý 2"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'lực lượng thành viên góp vốn giữa các khối kinh tế hợp tác' ➔ Chỉ tiêu đồng danh liên nhánh 'Thành viên' trên 4 nhánh cha
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Bảng đối chiếu liên nhánh 'Thành viên' (Quý 2/2026 - 30/06/2026) gồm 4 nhánh: HTX nông nghiệp (5.208), Liên hiệp HTX nông nghiệp (28), Tổ hợp tác nông nghiệp (1.350), Trang trại (550)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (name='Thành viên'): Q1 = [5.198, 22, 1.300, 525]; Q2 = [5.208, 28, 1.350, 550]; Q3 = [5.200, 30, 1.400, 575] (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 1] ➔ [Quý 3]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng 4 nhánh cập nhật tại chỗ: Quý 1 = [5.198; 22; 1.300; 525]; Quý 3 = [5.200; 30; 1.400; 575]
- **Nhận xét & Kết luận**: **Correct — Hệ thống nhận diện chính xác chỉ tiêu đồng danh 'Thành viên' qua 4 nhánh ở Quý 2 [5.208; 28; 1.350; 550]. Khi bấm nút ticket Quý 1 và Quý 3, bảng cập nhật sang [5.198; 22; 1.300; 525] và [5.200; 30; 1.400; 575], khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q24
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q24_initial.png`)**:
  ![Q24 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q24_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q24_after_buttons.png`)**:
  ![Q24 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q24_after_buttons.png)

---

### Q25 (CROSS_BRANCH_COMPARISON): "Đặt lên bàn cân mảng thủy sản ở các mô hình tổ chức trong quý 1"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'mảng thủy sản ở các mô hình tổ chức' ➔ Chỉ tiêu đồng danh liên nhánh 'Thủy sản' trên 3 nhánh cha (HTX, LHHTX, THT)
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Bảng đối chiếu liên nhánh 'Thủy sản' (Quý 1/2026 - 31/03/2026) gồm 3 nhánh: HTX nông nghiệp (15), Liên hiệp HTX nông nghiệp (1), Tổ hợp tác nông nghiệp (67)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (name='Thủy sản'): Q1 = [15, 1, 67]; Q2 = [15, 1, 69]; Q3 = [15, 0, 71] (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 2] ➔ [Quý 3]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng 3 nhánh cập nhật tại chỗ: Quý 2 = [15; 1; 69]; Quý 3 = [15; 0; 71]
- **Nhận xét & Kết luận**: **Correct — Hệ thống đối chiếu chính xác chỉ tiêu đồng danh 'Thủy sản' trên 3 nhánh ở Quý 1 [15; 1; 67]. Bấm ticket Quý 2 và Quý 3 cập nhật bảng sang [15; 1; 69] và [15; 0; 71], khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q25
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q25_initial.png`)**:
  ![Q25 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q25_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q25_after_buttons.png`)**:
  ![Q25 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q25_after_buttons.png)

---

### Q26 (CROSS_BRANCH_COMPARISON): "Khảo sát số cơ sở đang duy trì hoạt động qua các định chế kinh tế vào quý 2"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'số cơ sở đang duy trì hoạt động qua các định chế kinh tế' ➔ Chỉ tiêu đồng danh liên nhánh 'Đang hoạt động' trên 4 nhánh cha
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Bảng đối chiếu liên nhánh 'Đang hoạt động' (Quý 2/2026 - 30/06/2026) gồm 4 nhánh: HTX nông nghiệp (128), Liên hiệp HTX nông nghiệp (4), Tổ hợp tác nông nghiệp (500), Trang trại (105)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (name='Đang hoạt động'): Q1 = [122, 3, 485, 100]; Q2 = [128, 4, 500, 105]; Q3 = [130, 4, 515, 110] (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 1] ➔ [Quý 3]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng 4 nhánh cập nhật tại chỗ: Quý 1 = [122; 3; 485; 100]; Quý 3 = [130; 4; 515; 110]
- **Nhận xét & Kết luận**: **Correct — Hệ thống xử lý chuẩn xác cụm 'số cơ sở đang duy trì hoạt động' (không nhận diện nhầm 'cơ sở' thành 'Sở' cấp 1) và trả về đúng 4 nhánh của chỉ tiêu 'Đang hoạt động' ở Quý 2 [128; 4; 500; 105]. Bấm ticket Quý 1 và Quý 3 cập nhật bảng sang [122; 3; 485; 100] và [130; 4; 515; 110], khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q26
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q26_initial.png`)**:
  ![Q26 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q26_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q26_after_buttons.png`)**:
  ![Q26 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q26_after_buttons.png)

---

### Q27 (CROSS_BRANCH_COMPARISON): "Đối sánh lĩnh vực lâm nghiệp giữa các khối tổ chức nông thôn trong quý 1 năm 2026"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'lĩnh vực lâm nghiệp giữa các khối tổ chức nông thôn' ➔ Chỉ tiêu đồng danh liên nhánh 'Lâm nghiệp' trên 4 nhánh cha
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Bảng đối chiếu liên nhánh 'Lâm nghiệp' (Quý 1/2026 - 31/03/2026) gồm 4 nhánh: HTX nông nghiệp (15), Liên hiệp HTX nông nghiệp (0), Tổ hợp tác nông nghiệp (44), Trang trại (2)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (name='Lâm nghiệp'): Q1 = [15, 0, 44, 2]; Q2 = [15, 0, 45, 2]; Q3 = [15, 1, 46, 2] (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 2] ➔ [Quý 3]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng 4 nhánh cập nhật tại chỗ: Quý 2 = [15; 0; 45; 2]; Quý 3 = [15; 1; 46; 2]
- **Nhận xét & Kết luận**: **Correct — Hệ thống đối sánh chính xác chỉ tiêu đồng danh 'Lâm nghiệp' trên 4 nhánh ở Quý 1 [15; 0; 44; 2]. Bấm ticket Quý 2 và Quý 3 cập nhật bảng sang [15; 0; 45; 2] và [15; 1; 46; 2], khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q27
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q27_initial.png`)**:
  ![Q27 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q27_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q27_after_buttons.png`)**:
  ![Q27 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q27_after_buttons.png)

---

### Q28 (CROSS_BRANCH_COMPARISON): "Rà soát mảng chế biến nông sản qua từng hệ thống đơn vị tập thể ở quý 2"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'mảng chế biến nông sản qua từng hệ thống đơn vị tập thể' ➔ Chỉ tiêu đồng danh liên nhánh 'Chế biến nông sản' trên 4 nhánh cha
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Bảng đối chiếu liên nhánh 'Chế biến nông sản' (Quý 2/2026 - 30/06/2026) gồm 4 nhánh: HTX nông nghiệp (15), Liên hiệp HTX nông nghiệp (1), Tổ hợp tác nông nghiệp (45), Trang trại (3)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (name='Chế biến nông sản'): Q1 = [15, 0, 43, 3]; Q2 = [15, 1, 45, 3]; Q3 = [15, 0, 47, 3] (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 1] ➔ [Quý 3]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng 4 nhánh cập nhật tại chỗ: Quý 1 = [15; 0; 43; 3]; Quý 3 = [15; 0; 47; 3]
- **Nhận xét & Kết luận**: **Correct — Hệ thống phân bổ chính xác chỉ tiêu đồng danh 'Chế biến nông sản' qua 4 nhánh ở Quý 2 [15; 1; 45; 3]. Bấm ticket Quý 1 và Quý 3 cập nhật bảng sang [15; 0; 43; 3] và [15; 0; 47; 3], khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q28
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q28_initial.png`)**:
  ![Q28 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q28_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q28_after_buttons.png`)**:
  ![Q28 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q28_after_buttons.png)

---

### Q29 (CROSS_BRANCH_COMPARISON): "So chiếu mảng cung cấp nước sạch NT giữa các nhóm chủ thể quản lý tại quý 1"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'mảng cung cấp nước sạch NT giữa các nhóm chủ thể quản lý' ➔ Chỉ tiêu đồng danh liên nhánh 'Nước sạch NT' trên 3 nhánh cha (HTX, LHHTX, THT)
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Bảng đối chiếu liên nhánh 'Nước sạch NT' (Quý 1/2026 - 31/03/2026) gồm 3 nhánh: HTX nông nghiệp (15), Liên hiệp HTX nông nghiệp (0), Tổ hợp tác nông nghiệp (22)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (name='Nước sạch NT'): Q1 = [15, 0, 22]; Q2 = [15, 0, 22]; Q3 = [15, 0, 23] (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 2] ➔ [Quý 3]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng 3 nhánh cập nhật tại chỗ: Quý 2 = [15; 0; 22]; Quý 3 = [15; 0; 23]
- **Nhận xét & Kết luận**: **Correct — Hệ thống đối chiếu chính xác chỉ tiêu đồng danh 'Nước sạch NT' trên 3 nhánh ở Quý 1 [15; 0; 22]. Bấm ticket Quý 2 và Quý 3 cập nhật bảng sang [15; 0; 22] và [15; 0; 23], khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q29
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q29_initial.png`)**:
  ![Q29 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q29_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q29_after_buttons.png`)**:
  ![Q29 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q29_after_buttons.png)

---

### Q30 (CROSS_BRANCH_COMPARISON): "Bức tranh nghề truyền thống được công nhận giữa số phát sinh và lũy kế trong quý 2"

- **Ánh xạ Ngữ nghĩa Paraphrase (KB-Grounded)**: 'nghề truyền thống được công nhận giữa số phát sinh và lũy kế' ➔ Chỉ tiêu đồng danh liên nhánh 'Nghề truyền thống' trên 2 nhánh cha ('...được công nhận trong năm' và 'Lũy kế...')
- **Đáp án đọc từ UI (Trước khi bấm nút)**: Bảng đối chiếu liên nhánh 'Nghề truyền thống' (Quý 2/2026 - 30/06/2026) gồm 2 nhánh: Tổng số làng nghề, làng nghề truyền thống, nghề truyền thống được công nhận trong năm (0), Lũy kế Số làng nghề, làng nghề truyền thống, nghề truyền thống được công nhận (4)
- **Đối chiếu Kho dữ liệu (`vna_wom_dev`)**: fact_report_criteria (name='Nghề truyền thống'): Q1 = [0, 4]; Q2 = [0, 4]; Q3 = [0, 4] (Khớp 100%)
- **Thao tác kiểm thử nút (1–5 buttons)**: Bấm 2 nút ticket thời gian: [Quý 1] ➔ [Quý 3]
- **Đáp án đọc từ UI (Sau khi bấm nút)**: Bảng 2 nhánh cập nhật tại chỗ: Quý 1 = [0; 4]; Quý 3 = [0; 4]
- **Nhận xét & Kết luận**: **Correct — Hệ thống nhận diện chính xác ý định so sánh liên nhánh giữa 'phát sinh' (trong năm) và 'lũy kế' cho chỉ tiêu đồng danh 'Nghề truyền thống' ở Quý 2, hiển thị đầy đủ cả 2 nhánh [0; 4]. Bấm ticket Quý 1 và Quý 3 cập nhật bảng sang [0; 4] và [0; 4], khớp 100% với Warehouse.**

#### Minh chứng hình ảnh Q30
- **Ảnh 1 — Đáp án ban đầu (`PARAPHRASE_UI_Q30_initial.png`)**:
  ![Q30 Initial](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q30_initial.png)
- **Ảnh 2 — Đáp án sau khi bấm nút ticket thời gian (`PARAPHRASE_UI_Q30_after_buttons.png`)**:
  ![Q30 After Buttons](file:///C:/Users/Admin/.gemini/antigravity/brain/0787715a-fc9d-4947-a0e6-01af53c1fb1f/PARAPHRASE_UI_Q30_after_buttons.png)

---
