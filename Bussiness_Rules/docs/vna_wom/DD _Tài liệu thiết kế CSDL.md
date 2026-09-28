**HỆ THỐNG QUẢN LÝ ĐIỀU HÀNH CẤP XÃ**

**TÀI LIỆU THIẾT KẾ CƠ SỞ DỮ LIỆU**

Phiên bản V2.0 — 13/09/2026

*Tài liệu song hành cùng: SRS \_Tài liệu đặc tả yêu cầu PM.docx*

# LỊCH SỬ THAY ĐỔI TÀI LIỆU

| **Ngày thay đổi** | **Phiên bản** | **Mô tả** | **Tác giả** |
|----|----|----|----|
| 19/09/2025 | V0.1 | Tạo mới (SRS) | Phan Thanh Tùng |
| 26/12/2025 | V1.0 | Thiết kế CSDL ban đầu | Vỹ Tào |
| 13/09/2026 | V2.0 | Chuẩn hoá cấu trúc tài liệu, đồng bộ theo hệ thống đang triển khai |  |

# MỤC LỤC

[LỊCH SỬ THAY ĐỔI TÀI LIỆU [2](#lịch-sử-thay-đổi-tài-liệu)](#lịch-sử-thay-đổi-tài-liệu)

[MỤC LỤC [3](#mục-lục)](#mục-lục)

[1. Giới thiệu [6](#giới-thiệu)](#giới-thiệu)

[1.1 Mục đích [6](#mục-đích)](#mục-đích)

[1.2 Phạm vi [6](#phạm-vi)](#phạm-vi)

[1.3 Tài liệu tham chiếu [6](#tài-liệu-tham-chiếu)](#tài-liệu-tham-chiếu)

[1.4 Thuật ngữ [6](#thuật-ngữ)](#thuật-ngữ)

[2. Quy ước thiết kế [7](#quy-ước-thiết-kế)](#quy-ước-thiết-kế)

[2.1 Hệ quản trị CSDL [7](#hệ-quản-trị-csdl)](#hệ-quản-trị-csdl)

[2.2 Quy ước đặt tên [7](#quy-ước-đặt-tên)](#quy-ước-đặt-tên)

[2.3 Khối cột hệ thống (audit) dùng chung [8](#khối-cột-hệ-thống-audit-dùng-chung)](#khối-cột-hệ-thống-audit-dùng-chung)

[2.4 Quy ước xoá dữ liệu [8](#quy-ước-xoá-dữ-liệu)](#quy-ước-xoá-dữ-liệu)

[2.5 Quy ước JSONB [9](#quy-ước-jsonb)](#quy-ước-jsonb)

[2.6 Quy ước mã tổ chức [9](#quy-ước-mã-tổ-chức)](#quy-ước-mã-tổ-chức)

[3. Tổng quan mô hình dữ liệu [9](#tổng-quan-mô-hình-dữ-liệu)](#tổng-quan-mô-hình-dữ-liệu)

[3.1 Ghi chú sơ đồ ERD [9](#ghi-chú-sơ-đồ-erd)](#ghi-chú-sơ-đồ-erd)

[3.2 Danh mục 27 thực thể theo chương [9](#danh-mục-27-thực-thể-theo-chương)](#danh-mục-27-thực-thể-theo-chương)

[3.3 Căn cứ xây dựng tài liệu [10](#căn-cứ-xây-dựng-tài-liệu)](#căn-cứ-xây-dựng-tài-liệu)

[4. Dữ liệu tổ chức (đồng bộ từ hệ thống ngoài) [11](#dữ-liệu-tổ-chức-đồng-bộ-từ-hệ-thống-ngoài)](#dữ-liệu-tổ-chức-đồng-bộ-từ-hệ-thống-ngoài)

[4.1 Bảng stage_province [11](#bảng-stage_province)](#bảng-stage_province)

[4.2 Bảng stage_ward [11](#bảng-stage_ward)](#bảng-stage_ward)

[4.3 Bảng stage_department [12](#bảng-stage_department)](#bảng-stage_department)

[4.4 Bảng stage_user [13](#bảng-stage_user)](#bảng-stage_user)

[5. Danh mục dùng chung [15](#danh-mục-dùng-chung)](#danh-mục-dùng-chung)

[5.1 Bảng year [15](#bảng-year)](#bảng-year)

[5.2 Bảng office [15](#bảng-office)](#bảng-office)

[5.3 Bảng scope [16](#bảng-scope)](#bảng-scope)

[5.4 Bảng mission [17](#bảng-mission)](#bảng-mission)

[5.5 Bảng office_mission [18](#bảng-office_mission)](#bảng-office_mission)

[5.6 Bảng office_user [19](#bảng-office_user)](#bảng-office_user)

[5.7 Bảng user_mission [19](#bảng-user_mission)](#bảng-user_mission)

[6. Tiêu chí đầu vào [21](#tiêu-chí-đầu-vào)](#tiêu-chí-đầu-vào)

[6.1 Bảng collection_criteria [21](#bảng-collection_criteria)](#bảng-collection_criteria)

[6.2 Bảng general_criteria [23](#bảng-general_criteria)](#bảng-general_criteria)

[6.3 Bảng criteria_group [24](#bảng-criteria_group)](#bảng-criteria_group)

[7. Đánh giá & duyệt [28](#đánh-giá-duyệt)](#đánh-giá-duyệt)

[7.1 Bảng evaluation_config [28](#bảng-evaluation_config)](#bảng-evaluation_config)

[7.2 Bảng report_record [30](#bảng-report_record)](#bảng-report_record)

[7.3 Bảng report_review_step [32](#bảng-report_review_step)](#bảng-report_review_step)

[7.4 Bảng report_record_history [33](#bảng-report_record_history)](#bảng-report_record_history)

[8. Phiếu rà soát [35](#phiếu-rà-soát)](#phiếu-rà-soát)

[8.1 Bảng collection_form [35](#bảng-collection_form)](#bảng-collection_form)

[8.2 Bảng collection_form_record [38](#bảng-collection_form_record)](#bảng-collection_form_record)

[9. Báo cáo tổng hợp [40](#báo-cáo-tổng-hợp)](#báo-cáo-tổng-hợp)

[9.1 Bảng report_summary [40](#bảng-report_summary)](#bảng-report_summary)

[10. Chatbot [43](#chatbot)](#chatbot)

[10.1 Bảng chat_message [43](#bảng-chat_message)](#bảng-chat_message)

[11. Cấu hình hiển thị [44](#cấu-hình-hiển-thị)](#cấu-hình-hiển-thị)

[11.1 Bảng visual_config [44](#bảng-visual_config)](#bảng-visual_config)

[11.2 Bảng chart [45](#bảng-chart)](#bảng-chart)

[11.3 Bảng kpi [46](#bảng-kpi)](#bảng-kpi)

[12. Cấu hình website [47](#cấu-hình-website)](#cấu-hình-website)

[12.1 Bảng website_config [47](#bảng-website_config)](#bảng-website_config)

[12.2 Bảng website_banner [47](#bảng-website_banner)](#bảng-website_banner)

[9.2 Luồng xử lý báo cáo tổng hợp [48](#luồng-xử-lý-báo-cáo-tổng-hợp)](#luồng-xử-lý-báo-cáo-tổng-hợp)

[Luồng I — Tạo mới / chỉnh sửa báo cáo (lưu cấu hình vào report_summary) [48](#luồng-i-tạo-mới-chỉnh-sửa-báo-cáo-lưu-cấu-hình-vào-report_summary)](#luồng-i-tạo-mới-chỉnh-sửa-báo-cáo-lưu-cấu-hình-vào-report_summary)

[Luồng II — Xem / tính toán báo cáo (tạo snapshot dữ liệu) [49](#luồng-ii-xem-tính-toán-báo-cáo-tạo-snapshot-dữ-liệu)](#luồng-ii-xem-tính-toán-báo-cáo-tạo-snapshot-dữ-liệu)

[11.4 Luồng cấu hình & hiển thị Dashboard/Landing page [49](#luồng-cấu-hình-hiển-thị-dashboardlanding-page)](#luồng-cấu-hình-hiển-thị-dashboardlanding-page)

[Luồng 1 — Cấu hình (thiết lập khung) [49](#luồng-1-cấu-hình-thiết-lập-khung)](#luồng-1-cấu-hình-thiết-lập-khung)

[Luồng 2 — Hiển thị (đổ dữ liệu lên UI) [49](#luồng-2-hiển-thị-đổ-dữ-liệu-lên-ui)](#luồng-2-hiển-thị-đổ-dữ-liệu-lên-ui)

[13. Phụ lục [50](#phụ-lục)](#phụ-lục)

[Phụ lục A — Tổng hợp cấu trúc JSONB [50](#phụ-lục-a-tổng-hợp-cấu-trúc-jsonb)](#phụ-lục-a-tổng-hợp-cấu-trúc-jsonb)

[Phụ lục B — Danh mục ENUM / giá trị chuẩn hoá [50](#phụ-lục-b-danh-mục-enum-giá-trị-chuẩn-hoá)](#phụ-lục-b-danh-mục-enum-giá-trị-chuẩn-hoá)

[Phụ lục C — Chỉ mục đề xuất [54](#phụ-lục-c-chỉ-mục-đề-xuất)](#phụ-lục-c-chỉ-mục-đề-xuất)

[Phụ lục D — Khuyến nghị mở rộng [54](#phụ-lục-d-khuyến-nghị-mở-rộng)](#phụ-lục-d-khuyến-nghị-mở-rộng)

[Phụ lục E — Ma trận phủ nghiệp vụ SRS [55](#phụ-lục-e-ma-trận-phủ-nghiệp-vụ-srs)](#phụ-lục-e-ma-trận-phủ-nghiệp-vụ-srs)

# 1. Giới thiệu

## 1.1 Mục đích

Tài liệu này mô tả thiết kế cơ sở dữ liệu (CSDL) của Hệ thống quản lý điều hành cấp xã, phục vụ đội phát triển tra cứu cấu trúc bảng, quan hệ, ràng buộc và cấu trúc dữ liệu JSONB khi lập trình, đồng thời làm căn cứ đối chiếu giữa yêu cầu nghiệp vụ (SRS) và hệ thống đang chạy thực tế (production).

## 1.2 Phạm vi

Tài liệu thiết kế đầy đủ cơ sở dữ liệu đáp ứng 16 nhóm chức năng nghiệp vụ mà SRS đã phân tích (mục 6.1-6.16), gồm 27 thực thể dữ liệu chia theo Chương 4-12. Mỗi bảng ghi rõ trạng thái: "Đã triển khai" (kiểm chứng được qua kho dữ liệu automation/vna_dwh_internal, gồm 16 bảng ở Chương 4-8) hoặc "Theo đặc tả SRS" (thiết kế đáp ứng yêu cầu nghiệp vụ, chưa nằm trong phạm vi đồng bộ của kho dữ liệu hiện có, gồm 11 bảng). Phụ lục E đối chiếu trực tiếp từng mục SRS 6.1-6.16 với bảng/cột đáp ứng.

## 1.3 Tài liệu tham chiếu

• SRS \_Tài liệu đặc tả yêu cầu PM.docx (v0.1, 19/09/2025)

• Kho dữ liệu automation/vna_dwh_internal (dbt project) và dữ liệu thật trong schema dwh_internal

• HD-PL NỀN TẢNG QUẢN LÝ CBCCVC 28.8.docx, PHỤ LỤC III.docx

## 1.4 Thuật ngữ

| **Thuật ngữ** | **Giải thích** |
|----|----|
| Tenant | Đơn vị cấp tỉnh/thành phố. Nhận dạng bằng mã tenantCode (varchar, 2 chữ số, vd "75", "96"). |
| Department | Cơ quan/đơn vị hành chính. Nhận dạng bằng mã departmentCode (varchar). Có cấu trúc phân cấp nhiều cấp (level trong production, SRS gọi là level 1-4) qua stage_department.parentId. |
| Office | Phòng ban trực thuộc 1 UBND Xã/Phường — đơn vị nghiệp vụ nhỏ nhất quản lý Lĩnh vực/Nhiệm vụ. |
| Scope (Lĩnh vực) | Lĩnh vực phụ trách của 1 phòng ban, gắn theo Năm làm việc. |
| Mission (Nhiệm vụ) | Nhiệm vụ cụ thể thuộc 1 Lĩnh vực. |
| Criteria (Tiêu chí) | Đơn vị dữ liệu nhỏ nhất cần thu thập/báo cáo, có thể phân cấp tối đa 3 cấp (level 1/2/3). |
| yearCode | Mã năm làm việc, varchar(4), ví dụ "2025", "2026". |
| tenantCode / departmentCode | Mã định danh tỉnh/cơ quan dạng chuỗi (KHÔNG phải UUID), đồng bộ từ hệ thống định danh hành chính ngoài (xem Chương 4). Gần như mọi bảng nghiệp vụ đều mang theo 2 mã này để lọc/phân quyền. |

# 2. Quy ước thiết kế

## 2.1 Hệ quản trị CSDL

PostgreSQL (theo yêu cầu hợp đồng, Phụ lục II). Sử dụng kiểu uuid, jsonb, timestamptz, mảng (array) và CREATE TYPE ... AS ENUM khi cần ràng buộc tập giá trị cố định.

## 2.2 Quy ước đặt tên

• Tên bảng nghiệp vụ (schema public của vna_wom_dev): snake_case, số ít (vd. collection_form, report_record).

• Tên bảng tổ chức đồng bộ (schema staging): cũng snake_case nhưng các CỘT bên trong lại là snake_case thuần (is_activated, province_code...) — khác hẳn quy ước camelCase của các bảng nghiệp vụ. Đây là 2 hệ thống khác nhau ghép lại, không phải lỗi.

• Tên cột của bảng nghiệp vụ: camelCase, đặt trong dấu ngoặc kép khi dùng trong PostgreSQL vì PostgreSQL hạ chữ thường tên không đặt ngoặc kép (vd. "createdDate", "tenantCode").

• Khoá chính: id kiểu uuid, DEFAULT uuid_generate_v4().

• Khoá ngoại: đặt tên \<bảng số ít\>\<Tên bảng tham chiếu\>Id, ví dụ missionId, officeId.

• Mọi bảng nghiệp vụ dùng chung khối cột audit chuẩn (xem bảng bên dưới) thay vì chỉ createdBy/updatedBy/createdAt/updatedAt như bản thiết kế trước — tuy nhiên KHÔNG PHẢI bảng nào cũng dùng đủ 11 cột; một số bảng (vd. scope, mission, office) chỉ dùng tập con — xem cột "Ghi chú" ở từng bảng.

• Enum khai báo bằng CREATE TYPE... AS ENUM, đặt tên \<bảng\>\_status_enum — nhưng KHÔNG PHẢI mọi trạng thái trong production đều được ràng buộc bằng ENUM thật; một số cột (report_record.status, office_user.role) chỉ là varchar tự do, xem Phụ lục B.

• tenantCode/departmentCode/yearCode luôn là varchar, không phải UUID hay FK cứng — đối soát với dữ liệu tổ chức đồng bộ ở Chương 4.

## 2.3 Khối cột hệ thống (audit) dùng chung

Hầu hết bảng nghiệp vụ dùng một tập con của 11 cột sau, xác nhận qua các model ETL trong kho dữ liệu. Không phải bảng nào cũng dùng đủ 11 cột — bảng thuộc tính của từng thực thể ở Chương 4-12 liệt kê đúng tập cột mà bảng đó thật sự có.

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| "createdDate" | timestamp |  | Thời điểm tạo bản ghi |
| "createdBy" | varchar(256) |  | Tên đăng nhập (username) người tạo — KHÔNG phải UUID |
| "createdUserId" | uuid |  | Định danh UUID người tạo |
| "creator" | varchar(256) |  | Tên hiển thị người tạo tại thời điểm tạo (snapshot) |
| "modifiedDate" | timestamp |  | Thời điểm sửa gần nhất |
| "modifiedBy" | varchar(256) |  | Tên đăng nhập người sửa gần nhất |
| "modifiedUserId" | uuid |  | Định danh UUID người sửa gần nhất |
| "modifier" | varchar(256) |  | Tên hiển thị người sửa gần nhất (snapshot) |
| "deletedAt" | timestamp |  | Thời điểm xoá (soft-delete); NULL = chưa xoá |
| "deletedBy" | varchar(256) |  | Tên đăng nhập người xoá |
| "usedIds" | uuid\[\] |  | Danh sách id bản ghi liên quan đã dùng/tham chiếu (phục vụ kiểm tra trước khi xoá) |
| "usedId" | varchar |  | Id đơn lẻ dùng gần nhất — dùng ở một số bảng thay cho usedIds |

## 2.4 Quy ước xoá dữ liệu

• **Soft-delete (mặc định):** Đặt cột deletedAt/deletedDate khác NULL. Áp dụng cho toàn bộ bảng có khối audit chuẩn (collection_criteria, criteria_group, collection_form, collection_form_record, report_record, office_mission, user_mission, office_user, mission, scope, office). Đây là hành vi thật của production (mọi bảng đều có deletedAt/deletedBy).

• **Hard-delete có điều kiện:** Chỉ áp dụng khi bản ghi CHƯA được bất kỳ bảng nào khác tham chiếu (kiểm tra qua usedIds/usedId), ví dụ tiêu chí chưa được thêm vào bộ thu thập nào. SRS mô tả nhiều màn hình dùng hard-delete cho trường hợp này — không mâu thuẫn với soft-delete, vì hard-delete chỉ xảy ra ở bước dọn dữ liệu nháp chưa từng được dùng.

• **year.isDeleted:** Ngoại lệ: bảng year giữ cột boolean isDeleted riêng (không dùng deletedAt) vì đây là bảng danh mục gốc, hiếm khi xoá và không cần mốc thời gian xoá.

## 2.5 Quy ước JSONB

Các cấu trúc dạng cây hoặc động (tiêu chí, câu hỏi phiếu rà soát, bước duyệt, dữ liệu báo cáo) được lưu bằng JSONB thay vì tách thành bảng quan hệ đầy đủ. Mỗi trường JSONB được đặc tả chi tiết kèm mẫu dữ liệu thực tế tại Phụ lục A.

## 2.6 Quy ước mã tổ chức

tenantCode (mã tỉnh/thành, 2 chữ số, vd "68") và departmentCode (mã cơ quan/đơn vị) là chuỗi văn bản, không phải khoá ngoại UUID — chúng tham chiếu tới bảng stage_department.code (Chương 4), đến từ hệ thống định danh hành chính ngoài, đồng bộ một chiều vào hệ thống này.

departmentCode theo định dạng \<tenantCode\>-\<cấp\>-\<số thứ tự\>, ví dụ "68-1-02" (tỉnh 68, cấp 1, đơn vị số 02) hoặc "68-2-01" (tỉnh 68, cấp 2, đơn vị số 01). Cấp 0 dùng chính tenantCode làm departmentCode.

# 3. Tổng quan mô hình dữ liệu

## 3.1 Ghi chú sơ đồ ERD

Sơ đồ ERD tổng thể (image/ERD.png) mô tả quan hệ giữa các bảng. Khuyến nghị dựng lại ERD theo đúng tên bảng/cột đã chuẩn hoá trong tài liệu này sau khi DDL chính thức được chốt.

## 3.2 Danh mục 27 thực thể theo chương

| **Tên bảng** | **Chương** | **Trạng thái** |
|----|----|----|
| stage_province | Chương 4 — Dữ liệu tổ chức (đồng bộ từ hệ thống ngoài) | Đã triển khai |
| stage_ward | Chương 4 — Dữ liệu tổ chức (đồng bộ từ hệ thống ngoài) | Đã triển khai |
| stage_department | Chương 4 — Dữ liệu tổ chức (đồng bộ từ hệ thống ngoài) | Đã triển khai |
| stage_user | Chương 4 — Dữ liệu tổ chức (đồng bộ từ hệ thống ngoài) | Đã triển khai |
| year | Chương 5 — Danh mục dùng chung | Theo SRS |
| office | Chương 5 — Danh mục dùng chung | Đã triển khai |
| scope | Chương 5 — Danh mục dùng chung | Đã triển khai |
| mission | Chương 5 — Danh mục dùng chung | Đã triển khai |
| office_mission | Chương 5 — Danh mục dùng chung | Đã triển khai |
| office_user | Chương 5 — Danh mục dùng chung | Đã triển khai |
| user_mission | Chương 5 — Danh mục dùng chung | Đã triển khai |
| collection_criteria | Chương 6 — Tiêu chí đầu vào | Đã triển khai |
| general_criteria | Chương 6 — Tiêu chí đầu vào | Theo SRS |
| criteria_group | Chương 6 — Tiêu chí đầu vào | Đã triển khai |
| evaluation_config | Chương 7 — Đánh giá & duyệt | Theo SRS |
| report_record | Chương 7 — Đánh giá & duyệt | Đã triển khai |
| report_review_step | Chương 7 — Đánh giá & duyệt | Theo SRS |
| report_record_history | Chương 7 — Đánh giá & duyệt | Đã triển khai |
| collection_form | Chương 8 — Phiếu rà soát | Đã triển khai |
| collection_form_record | Chương 8 — Phiếu rà soát | Đã triển khai |
| report_summary | Chương 9 — Báo cáo tổng hợp | Theo SRS |
| chat_message | Chương 10 — Chatbot | Theo SRS |
| visual_config | Chương 11 — Cấu hình hiển thị | Theo SRS |
| chart | Chương 11 — Cấu hình hiển thị | Theo SRS |
| kpi | Chương 11 — Cấu hình hiển thị | Theo SRS |
| website_config | Chương 12 — Cấu hình website | Theo SRS |
| website_banner | Chương 12 — Cấu hình website | Theo SRS |

## 3.3 Căn cứ xây dựng tài liệu

Cấu trúc mỗi bảng bám sát yêu cầu dữ liệu mà SRS đã đặc tả cho từng chức năng (mục 6.1-6.16). Với các bảng đã triển khai, cấu trúc được đối chiếu thêm với hệ thống đang chạy: pipeline ETL của kho dữ liệu automation/vna_dwh_internal, cấu trúc JSONB do chính ứng dụng tạo ra (snapshot tiêu chí trong reportData/config), và dữ liệu thật truy vấn được. Phụ lục E tổng hợp đối chiếu giữa từng mục SRS và bảng/cột đáp ứng.

# 4. Dữ liệu tổ chức (đồng bộ từ hệ thống ngoài)

### 4.1 Bảng stage_province

*Trạng thái:* **Đã triển khai**

Danh mục tỉnh/thành phố, đồng bộ từ hệ thống định danh hành chính ngoài (không phải do nghiệp vụ ứng dụng này tạo/sửa).

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK | Định danh tỉnh/thành |
| code | varchar(10) | UNIQUE | Mã tỉnh/thành, ví dụ "01" |
| name | text | NOT NULL | Tên tỉnh/thành |
| is_activated | boolean |  | Đang áp dụng hay đã ngừng (sáp nhập, đổi tên) |
| editable | boolean |  | Cho phép chỉnh sửa từ ứng dụng hay chỉ đọc (đồng bộ 1 chiều) |
| deletable | boolean |  | Cho phép xoá hay không |

**Quan hệ**

• stage_ward.province_code → stage_province.code

• stage_department.province_code, stage_user.province_code tham chiếu tới đây

*Tham chiếu SRS: Không có mục SRS riêng — hạ tầng tổ chức dùng chung toàn hệ thống*

### 4.2 Bảng stage_ward

*Trạng thái:* **Đã triển khai**

Danh mục xã/phường, đồng bộ từ hệ thống định danh hành chính ngoài. Lưu cả mã cũ để đối chiếu khi có sáp nhập địa giới.

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK | Định danh xã/phường |
| code | text |  | Mã xã/phường hiện hành |
| name | text |  | Tên xã/phường |
| province_code | text | FK → stage_province.code | Tỉnh/thành quản lý |
| province_name | text |  | Tên tỉnh (denormalize để hiển thị nhanh) |
| old_codes | jsonb |  | Danh sách mã cũ trước khi sáp nhập địa giới (mảng chuỗi) |
| is_activated | boolean |  | Còn hiệu lực hay đã sáp nhập/giải thể |
| editable | boolean |  |  |
| deletable | boolean |  |  |

**Quan hệ**

• province_code → stage_province.code

• stage_department.ward_code, stage_user.ward_code tham chiếu tới đây

**Cấu trúc JSONB**

• **old_codes:** Mảng chuỗi mã cũ, ví dụ \["27310", "27313"\] — phục vụ tra cứu lịch sử khi địa giới hành chính thay đổi.

*Tham chiếu SRS: Không có mục SRS riêng*

### 4.3 Bảng stage_department

*Trạng thái:* **Đã triển khai**

Danh mục cơ quan/đơn vị, đồng bộ từ hệ thống định danh hành chính ngoài. Chứa 2 cấp cao nhất của cây tổ chức: cấp tỉnh/thành (level 0) và cơ quan trực thuộc cấp tỉnh (level 1).

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK | Định danh cơ quan/đơn vị |
| parent_id | uuid | FK → stage_department.id (tự tham chiếu) | Đơn vị cha trực tiếp |
| tenant_code | text |  | Mã tỉnh/thành chủ quản |
| code | text |  | Mã đơn vị — level 0 dùng chính mã tỉnh (vd "68"); level 1 theo định dạng \<tenantCode\>-1-\<số thứ tự\> (vd "68-1-02") |
| name | text |  | Tên đơn vị |
| level | integer |  | 0 (cấp tỉnh/thành, 34 đơn vị, không có parent) hoặc 1 (cơ quan trực thuộc cấp tỉnh, 6 đơn vị, có parent) |
| department_code_lv1 | text |  | Mã đơn vị cấp 1 (denormalize) |
| province_code / province_name | text |  | Tỉnh/thành quản lý (denormalize) |
| district_code / district_name | text |  | Huyện/quận quản lý (denormalize) |
| ward_code / ward_name | text |  | Xã/phường quản lý (denormalize) |
| is_activated | boolean |  | Đơn vị còn hoạt động |
| editable | boolean |  |  |
| deletable | boolean |  |  |

**Quan hệ**

• parent_id → id (tự tham chiếu)

• code là giá trị mà các bảng nghiệp vụ khác gọi là departmentCode; tenant_code là tenantCode. Các đơn vị cấp 2 trở xuống mà nghiệp vụ đang dùng (vd "68-2-01", "79-2-03") theo cùng quy tắc đặt mã \<tenantCode\>-\<cấp\>-\<số thứ tự\> nhưng chưa có mặt trong bảng đồng bộ này.

*Tham chiếu SRS: 6.4 Quản lý phòng ban; 6.13 (Trong cơ quan/Đơn vị cấp dưới)*

### 4.4 Bảng stage_user

*Trạng thái:* **Đã triển khai**

Danh mục tài khoản người dùng, đồng bộ từ hệ thống định danh/nhân sự ngoài — KHÔNG phải bảng người dùng nội bộ của ứng dụng (đăng nhập/mật khẩu nằm ở service khác).

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK | Định danh người dùng — được các bảng nghiệp vụ tham chiếu qua createdUserId/modifiedUserId/userId |
| tenant_code | text |  | Tỉnh/thành công tác |
| department_code | text | FK → stage_department.code | Đơn vị công tác |
| department_name | text |  | Tên đơn vị (denormalize) |
| username | text |  | Tên đăng nhập — là giá trị mà các bảng nghiệp vụ lưu ở cột createdBy/modifiedBy |
| name | text |  | Họ và tên hiển thị |
| position | text |  | Chức vụ |
| province_code / district_code / ward_code | text |  | Nơi công tác (denormalize) |
| is_activated | boolean |  | Tài khoản đang hoạt động |
| is_vna | boolean |  | Đánh dấu tài khoản nội bộ đội ngũ triển khai (VNA) hay tài khoản thật của cán bộ — cần loại các dòng is_vna=true khi thống kê nghiệp vụ thật |
| deleted_at | timestamp |  | Thời điểm vô hiệu hoá/xoá |
| editable / deletable | boolean |  |  |

**Quan hệ**

• department_code → stage_department.code

• id được office_user.userId, user_mission.userId tham chiếu

• username là giá trị xuất hiện ở cột "createdBy"/"modifiedBy" (varchar) của mọi bảng nghiệp vụ khác

*Tham chiếu SRS: 6.4, 6.5 Quản lý người dùng vào phòng ban*

# 5. Danh mục dùng chung

### 5.1 Bảng year

*Trạng thái:* **Theo đặc tả SRS**

Năm làm việc — đơn vị thời gian gốc mà hầu hết dữ liệu nghiệp vụ (scope, mission, criteria, report...) đều gắn theo qua yearCode.

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK, DEFAULT uuid_generate_v4() | Định danh duy nhất |
| yearCode | varchar(4) | NOT NULL | Giá trị năm, ví dụ "2025" — khớp yearCode dùng ở mọi bảng khác |
| displayName | varchar(50) | NOT NULL | Tên hiển thị, ví dụ "Năm ngân sách 2025". |
| tenantCode | varchar(64) |  | Năm làm việc theo từng tỉnh/thành |
| status | boolean | DEFAULT true | Hoạt động / Không hoạt động |
| isDeleted | boolean | DEFAULT false | Soft-delete — ngoại lệ duy nhất dùng cờ boolean thay vì deletedAt (xem §2.5 Quy ước xoá) |

**Quan hệ**

• yearCode được tham chiếu (dạng chuỗi, không FK cứng) bởi scope, mission, office, criteria_group, collection_form, report_record, collection_form_record

• UNIQUE (tenantCode, yearCode) — mỗi năm chỉ tạo 1 lần trong tenant (SRS 6.1, dòng 113-114)

*Tham chiếu SRS: 6.1 Quản lý năm làm việc*

### 5.2 Bảng office

*Trạng thái:* **Đã triển khai**

Phòng ban trực thuộc 1 UBND Xã/Phường.

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK | Định danh phòng ban |
| name | varchar(100) | NOT NULL | Tên phòng ban |
| note | text |  | Mô tả phòng ban — cột tồn tại trên bảng nguồn nhưng chưa được đưa vào dữ liệu phân tích ở kho dữ liệu |
| yearCode | varchar(4) |  | Năm áp dụng |
| tenantCode | varchar(64) |  | Tỉnh/thành quản lý |
| departmentCode | varchar(64) |  | Cơ quan chủ quản (tham chiếu stage_department.code) |
| "createdDate" | timestamp |  | Thời điểm tạo |
| "createdBy" | varchar(256) |  | Người tạo (username) |
| createdUserId | uuid |  | Người tạo (UUID) — tồn tại trên bảng nguồn, chưa được đưa vào dữ liệu phân tích |
| creator | varchar(256) |  | Tên hiển thị người tạo (snapshot) — tồn tại trên bảng nguồn, chưa được đưa vào dữ liệu phân tích |
| "modifiedDate" | timestamp |  | Thời điểm sửa gần nhất |
| "modifiedBy" | varchar(256) |  | Người sửa gần nhất (username) |
| modifiedUserId | uuid |  | Người sửa gần nhất (UUID) — tồn tại trên bảng nguồn, chưa được đưa vào dữ liệu phân tích |
| modifier | varchar(256) |  | Tên hiển thị người sửa gần nhất (snapshot) — tồn tại trên bảng nguồn, chưa được đưa vào dữ liệu phân tích |
| "deletedBy" | varchar(256) |  | Người xoá |
| "deletedAt" | timestamp |  | Thời điểm xoá (soft-delete) |
| usedIds | uuid\[\] |  | Tồn tại trên bảng nguồn, chưa được đưa vào dữ liệu phân tích |
| usedId | varchar |  | Tồn tại trên bảng nguồn, chưa được đưa vào dữ liệu phân tích |

**Quan hệ**

• departmentCode → stage_department.code

• office_mission.officeId → office.id

• office_user.officeId → office.id

*Tham chiếu SRS: 6.4 Quản lý phòng ban*

### 5.3 Bảng scope

*Trạng thái:* **Đã triển khai**

Lĩnh vực phụ trách của 1 phòng ban, theo năm làm việc.

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK | Định danh lĩnh vực |
| code | varchar(64) |  | Mã lĩnh vực |
| name | varchar(64) | NOT NULL | Tên lĩnh vực |
| status | boolean | DEFAULT true | Hoạt động / Không hoạt động |
| synchronized | boolean | DEFAULT false | Đồng bộ Lĩnh vực này xuống các cơ quan cấp dưới (level 2/3/4) hay không (SRS 6.2, dòng 386, 549 — mặc định "Không") |
| "yearCode" | varchar(4) |  | Năm áp dụng |
| "departmentCode" | varchar(64) |  | Cơ quan chủ quản |
| "tenantCode" | varchar(64) |  | Tỉnh/thành |
| "createdBy" | varchar(256) |  | Người tạo (username) |
| "modifiedBy" | varchar(256) |  | Người sửa (username) |
| "createdDate" | timestamp |  | Thời điểm tạo |
| "modifiedDate" | timestamp |  | Thời điểm sửa |
| "deletedAt" | timestamp |  | Thời điểm xoá (soft-delete) |

**Quan hệ**

• mission.scopeId → scope.id

• UNIQUE (tenantCode, yearCode, code) — mã lĩnh vực duy nhất trong tenant (SRS 6.2, dòng 564)

*Tham chiếu SRS: 6.2 Quản lý lĩnh vực*

### 5.4 Bảng mission

*Trạng thái:* **Đã triển khai**

Nhiệm vụ cụ thể thuộc 1 Lĩnh vực.

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK | Định danh nhiệm vụ |
| "yearCode" | varchar(4) | lấy qua scope.yearCode | Năm áp dụng (denormalize từ scope) |
| code | varchar(100) | NOT NULL | Mã nhiệm vụ |
| name | varchar(255) | NOT NULL | Tên nhiệm vụ |
| status | boolean | DEFAULT true | Hoạt động / Không hoạt động |
| "scopeId" | uuid | FK → scope.id | Lĩnh vực chứa nhiệm vụ |
| "departmentCode" | varchar(64) |  | Cơ quan chủ quản |
| "tenantCode" | varchar(64) |  | Tỉnh/thành |
| "createdBy" | varchar(256) |  | Người tạo (username) |
| "modifiedBy" | varchar(256) |  | Người sửa (username) |
| "createdDate" | timestamp |  | Thời điểm tạo |
| "modifiedDate" | timestamp |  | Thời điểm sửa |
| "deletedAt" | timestamp |  | Thời điểm xoá (soft-delete) |

**Quan hệ**

• scopeId → scope.id

• office_mission.missionId → mission.id

• collection_criteria.missionId → mission.id

• UNIQUE (tenantCode, yearCode, code) — mã nhiệm vụ duy nhất trong tenant (SRS 6.3, dòng 862)

*Tham chiếu SRS: 6.3 Quản lý nhiệm vụ*

### 5.5 Bảng office_mission

*Trạng thái:* **Đã triển khai**

Gán Nhiệm vụ cho Phòng ban phụ trách.

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK | Định danh bản ghi gán |
| "officeId" | uuid | FK → office.id | Phòng ban phụ trách |
| "missionId" | uuid | FK → mission.id | Nhiệm vụ được gán — mỗi nhiệm vụ gán cho đúng 1 phòng ban (SRS 6.4.2 BR4) |
| "tenantCode" | varchar(64) |  | denormalize từ office |
| "departmentCode" | varchar(64) |  | denormalize từ office |
| "createdBy" | varchar(256) |  | Người tạo (username) |
| "modifiedBy" | varchar(256) |  | Người sửa (username) |
| "createdDate" | timestamp |  |  |
| "modifiedDate" | timestamp |  |  |
| "deletedAt" | timestamp |  | Thời điểm xoá (soft-delete) |

**Quan hệ**

• officeId → office.id

• missionId → mission.id

*Tham chiếu SRS: 6.4.2 Gán nhiệm vụ cho phòng ban*

### 5.6 Bảng office_user

*Trạng thái:* **Đã triển khai**

Gán người dùng vào phòng ban, kèm vai trò.

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK | Định danh bản ghi gán |
| "userId" | uuid | FK → stage_user.id | Người dùng |
| "officeId" | uuid | FK → office.id | Phòng ban |
| role | varchar(50) |  | Vai trò trong phòng ban: LEADER (Lãnh đạo) / STAFF (Chuyên viên) |
| "isActive" | boolean |  | Trạng thái kích hoạt mapping |
| "createdDate" | timestamp | → assigned_date | Thời điểm gán |
| "modifiedDate" | timestamp |  | Thời điểm sửa |
| "deletedAt" | timestamp |  | Thời điểm xoá — ETL office_user.sql chỉ lấy dòng deletedAt IS NULL |

**Quan hệ**

• officeId → office.id

• userId → stage_user.id

*Tham chiếu SRS: 6.4.3, 6.5 Quản lý người dùng vào phòng ban*

### 5.7 Bảng user_mission

*Trạng thái:* **Đã triển khai**

Gán người dùng phụ trách 1 Nhiệm vụ cụ thể (trong phạm vi phòng ban do office_mission xác định).

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK | Định danh bản ghi gán |
| "userId" | uuid | FK → stage_user.id | Người phụ trách |
| "missionId" | uuid | FK → mission.id | Nhiệm vụ được phụ trách — mỗi nhiệm vụ do đúng 1 người phụ trách (SRS 6.5.2 BR3) |
| "tenantCode" | varchar(64) |  | denormalize |
| "departmentCode" | varchar(64) |  | denormalize |
| "createdBy"/"modifiedBy"/"deletedBy" | varchar(256) hoặc uuid |  | Lưu tên đăng nhập ở phần lớn bản ghi; một số bản ghi lưu thẳng UUID — pipeline xử lý dữ liệu phải nhận diện định dạng UUID trước khi ép kiểu |
| "createdDate" | timestamp |  |  |
| "modifiedDate" | timestamp |  |  |
| "deletedAt" | timestamp |  |  |

**Quan hệ**

• missionId → mission.id

• userId → stage_user.id

• officeId không phải cột của bảng này — xác định qua JOIN office_mission.missionId = user_mission.missionId

*Tham chiếu SRS: 6.5.2 Phân công lĩnh vực & nhiệm vụ cho thành viên*

# 6. Tiêu chí đầu vào

### 6.1 Bảng collection_criteria

*Trạng thái:* **Đã triển khai**

Tiêu chí đầu vào thu thập theo Nhiệm vụ, có phân cấp 3 cấp (level 1/2/3) qua parentId.

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK | Định danh tiêu chí |
| code | varchar |  | Mã tiêu chí |
| name | varchar | NOT NULL | Tên tiêu chí |
| level | integer |  | Cấp của tiêu chí trong cây: 1, 2 hoặc 3 |
| "parentId" | uuid | FK → collection_criteria.id (tự tham chiếu) | Tiêu chí cha — dựng cây L1/L2/L3 |
| "missionId" | uuid | FK → mission.id | Nhiệm vụ chứa tiêu chí (có thể NULL với tiêu chí chung) |
| dataType | data_type_enum |  | information / collected |
| role | varchar |  | Vai trò tiêu chí: group (Nhóm) / measure (Đo lường) / aggregate (Tổng hợp) |
| inputMethod | varchar |  | number / text / textarea / boolean / date / select / multiselect |
| guide | text |  | Hướng dẫn nhập |
| placeholder | text |  | Hint hiển thị |
| minLength | integer |  | Validation — số ký tự hoặc giá trị tối thiểu tuỳ inputMethod |
| maxLength | integer |  | Validation — số ký tự hoặc giá trị tối đa tuỳ inputMethod |
| options | jsonb |  | Danh sách lựa chọn cho select/multiselect — \[{"value","display"}\] |
| sumToParent | boolean |  | Có tính tổng giá trị lên tiêu chí cha hay không |
| aggregateFn | varchar |  | Phép tổng hợp khi sumToParent = true — giá trị quan sát: sum |
| shareData | boolean |  | Chia sẻ tiêu chí này ra ngoài phạm vi nhiệm vụ gốc |
| usedInGroups | boolean |  | Đã được thêm vào ít nhất 1 bộ thu thập (criteria_group) hay chưa |
| status | collection_criteria_status_enum |  | Xem Phụ lục B |
| "yearCode" | varchar(4) |  | Năm áp dụng |
| "tenantCode" | varchar(64) |  | Tỉnh/thành |
| "creatorId" | uuid |  | Người tạo (UUID) |
| "creator"/"modifier" | varchar(256) |  | Tên hiển thị người tạo / người sửa gần nhất (snapshot) |
| "createdDate"/"modifiedDate" | timestamp |  | Thời điểm tạo / sửa gần nhất |
| "deletedAt"/"deletedBy" | timestamp / varchar(256) |  | Thời điểm và người xoá (soft-delete) |

**Quan hệ**

• missionId → mission.id

• parentId → collection_criteria.id (self)

• Toàn bộ tiêu chí (kèm giá trị đã nhập) được snapshot vào report_record.reportData tại thời điểm báo cáo, và vào criteria_group.config khi thêm vào bộ thu thập — xem Phụ lục A

• UNIQUE (tenantCode, yearCode, code) — mã tiêu chí duy nhất trong tenant (SRS 6.6, dòng 1717, 2083)

*Tham chiếu SRS: 6.6 Quản lý tiêu chí đầu vào*

### 6.2 Bảng general_criteria

*Trạng thái:* **Theo đặc tả SRS**

Tiêu chí chung, tái sử dụng giữa các phiếu rà soát (họ tên, CCCD, ngày sinh...), không phụ thuộc Nhiệm vụ.

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK, DEFAULT uuid_generate_v4() | Định danh tiêu chí chung |
| dataType | data_type_enum | NOT NULL | information / collected |
| name | varchar(64) | NOT NULL | Tên hiển thị |
| code | varchar(64) | NOT NULL, UNIQUE | Mã tiêu chí (duy nhất toàn hệ thống) |
| inputMethod | varchar | NOT NULL | text/number/date/select/... — xem mẫu thật generalCriteria trong collection_form.config, Phụ lục A |
| placeholder | text |  | Hint hiển thị |
| guide | varchar(100) |  | Hướng dẫn nhập |
| minValue | integer |  | Giá trị tối thiểu — áp dụng khi inputMethod = number (SRS 6.6.2.1) |
| maxValue | integer |  | Giá trị tối đa — áp dụng khi inputMethod = number (SRS 6.6.2.1) |
| minLength | integer |  | Số ký tự tối thiểu — áp dụng khi inputMethod = text/textarea (SRS 6.6.2.1) |
| maxLength | integer |  | Số ký tự tối đa — áp dụng khi inputMethod = text/textarea (SRS 6.6.2.1) |
| options | jsonb |  | Tập tuỳ chọn cho select/multiselect — xem Phụ lục A |
| status | varchar | DEFAULT 'public' | Trạng thái tiêu chí chung |
| yearCode | varchar(4) |  | Năm áp dụng (SRS 6.6.1, dòng 1527, 1551) |
| tenantCode | varchar(64) |  | Tỉnh/thành |
| departmentCode | varchar(64) |  | Cơ quan sở hữu tiêu chí |
| createdBy/updatedBy/createdAt/updatedAt | — |  | Theo khối audit chuẩn §2.4 |

**Quan hệ**

• Được tham chiếu (theo qid/dataKeys) từ collection_form.config → generalCriteria

**Cấu trúc JSONB**

• **options:** \[{"value": "lao_dong_that_nghiep", "display": "Lao động thất nghiệp"}, ...\]

*Tham chiếu SRS: 6.6.1, 6.10.3 (nhóm câu hỏi Thông tin chung)*

### 6.3 Bảng criteria_group

*Trạng thái:* **Đã triển khai**

Bộ thu thập — tập hợp tiêu chí (dạng cây snapshot) dùng để gắn vào form/đánh giá.

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK | Định danh bộ thu thập |
| name | varchar(120) | NOT NULL | Tên bộ thu thập |
| description | varchar(500) |  | Mô tả |
| status | criteria_group_status_enum | DEFAULT 'draft' | Xem Phụ lục B |
| "config" | jsonb |  | Danh sách cấu hình các tiêu chí trong bộ — CÂY snapshot đầy đủ thuộc tính tiêu chí. Xem Phụ lục A |
| "yearCode" | varchar(4) | NOT NULL | Năm áp dụng |
| "missionIds" | uuid\[\] |  | Các nhiệm vụ liên quan |
| "scopeIds" | uuid\[\] |  | Các lĩnh vực liên quan |
| "tenantCode" | varchar(64) |  | Tỉnh/thành |
| "departmentCode" | varchar(64) |  | Cơ quan chủ quản |
| "createdDate"/"createdBy"/"createdUserId"/"creator" | — |  | Khối audit đầy đủ (theo §2.4) |
| "modifiedDate"/"modifiedBy"/"modifiedUserId"/"modifier" | — |  |  |
| "deletedAt"/"deletedBy" | — |  |  |
| "usedIds"/"usedId" | uuid\[\] / varchar |  | Đánh dấu đã được dùng ở form/đánh giá nào — phục vụ kiểm tra trước khi cho phép sửa cấu trúc (khớp SRS 6.7 BR6: khoá cấu trúc khi Đang sử dụng) |

**Quan hệ**

• missionIds/scopeIds tham chiếu mission.id/scope.id dạng mảng, không FK cứng

• collection_form.config tham chiếu tới các bộ thu thập qua scopeId (khoá của scopeCriteria)

**Cấu trúc JSONB**

• **config:** Mảng cây tiêu chí (mỗi phần tử có thể có children lồng nhau). Các khoá quan sát được trong dữ liệu thật: id, code, name, role, guide, level, status, creator, children, dataType, modifier, parentId, creatorId, maxLength, minLength, missionId, shareData, aggregateFn, createdDate, inputMethod, placeholder, sumToParent, modifiedDate, usedInGroups, hidden, required. hidden/required là cờ ghi đè theo từng bộ thu thập (SRS 6.7.2.2: nút Ẩn/hiện và switch Bắt buộc áp dụng riêng cho form). Mẫu thực tế: {"id":"f0d5...", "code":"test_level_1", "name":"Test level 1", "role":"aggregate", "guide":null, "level":1, "status":"local", "creator":"admin-lamdong", "children":\[\], "dataType":"collected", "modifier":"admin-lamdong", "parentId":null, "creatorId":"270c...", "maxLength":null, "minLength":null, "missionId":"59d3...", "shareData":false, "aggregateFn":"sum", "createdDate":"2026-03-13T08:30:53.435Z", "inputMethod":null, "placeholder":null, "sumToParent":false, "modifiedDate":"2026-03-23T06:59:04.478Z", "usedInGroups":false}

*Tham chiếu SRS: 6.7 Quản lý bộ thu thập*

# 7. Đánh giá & duyệt

### 7.1 Bảng evaluation_config

*Trạng thái:* **Theo đặc tả SRS**

Cấu hình luồng duyệt nhiều cấp cho một Bộ thu thập theo Năm làm việc. Cơ chế phiên bản cấu hình đang vận hành trong hệ thống: report_record.evaluationVersionId có giá trị ở 167/182 bản ghi thật, với 58 phiên bản khác nhau đang được tham chiếu.

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK, DEFAULT uuid_generate_v4() | Định danh cấu hình |
| criteriaGroupId | uuid | FK → criteria_group.id | Bộ thu thập áp dụng cấu hình |
| scopeId | uuid | FK → scope.id, optional | Lĩnh vực |
| missionId | uuid | FK → mission.id, optional | Nhiệm vụ |
| yearCode | varchar(4) | NOT NULL | Năm làm việc |
| departmentCode | varchar(64) |  | Cơ quan tạo cấu hình — dùng để giới hạn phạm vi xem/sửa/xoá (SRS 6.8.1 dòng 3004, 3289, 3296) |
| tenantCode | varchar(64) |  | Tỉnh/thành |
| version | integer |  | Số phiên bản hiện hành của cấu hình |
| status | evaluation_config_status_enum |  | Lưu nháp / Đang sử dụng / Lưu trữ — thuộc phiên bản hiện hành (xem cấu trúc JSONB steps) |
| steps | jsonb |  | Mảng bước duyệt của phiên bản đang áp dụng — xem Phụ lục A |
| createdBy/updatedBy/createdAt/updatedAt | — |  | Khối audit chuẩn §2.4 |
| deletedAt/deletedBy | — |  | Soft-delete (SRS 6.8.2 mục 3, BR3) |

**Quan hệ**

• criteriaGroupId → criteria_group.id

• scopeId → scope.id

• missionId → mission.id

• report_record.evaluationVersionId → phiên bản trong steps (xem JSONB)

• Ràng buộc: mỗi (yearCode, criteriaGroupId) chỉ có 1 phiên bản ở trạng thái Đang sử dụng tại một thời điểm (SRS E5, mục 6.8.2)

**Cấu trúc JSONB**

• **version / steps:** version: INT — số phiên bản hiện hành của cấu hình. steps: JSONB — mảng bước duyệt của phiên bản đang áp dụng, mỗi phần tử dạng {"stepOrder": 1, "officeId": "uuid", "approverUserId": "uuid", "allowReturnPreviousStep": true, "activatedAt": "2026-01-01T00:00:00Z"}. allowReturnPreviousStep áp dụng cho toàn phiên bản (SRS 6.8.2); activatedAt quyết định phiên bản chỉ áp dụng cho phiếu có Thời gian đánh giá ≥ thời điểm này (SRS BR6, mục 6.8.2).

*Tham chiếu SRS: 6.8 Quản lý cấu hình đánh giá*

### 7.2 Bảng report_record

*Trạng thái:* **Đã triển khai**

Bản ghi thu thập/báo cáo — dữ liệu cốt lõi nhất của toàn hệ thống. Mỗi bản ghi ứng với 1 kỳ báo cáo của 1 bộ thu thập, mang theo TOÀN BỘ cây tiêu chí (snapshot) trong reportData.

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK | Định danh bản ghi báo cáo |
| "reportDate" | timestamptz |  | Thời gian báo cáo — mặc định hôm nay, không cho ngày tương lai (SRS 6.9) |
| "yearCode" | varchar(4) |  | Năm áp dụng |
| "departmentCode" | varchar(64) |  | Cơ quan lập báo cáo |
| "tenantCode" | varchar(64) |  | Tỉnh/thành |
| status | varchar |  | draft / pending / approved / rejected — xem Phụ lục B |
| "evaluationVersionId" | uuid | FK → evaluation_config (phiên bản) | Phiên bản cấu hình đánh giá áp dụng cho bản ghi này — snapshot tại thời điểm tạo, không đổi khi cấu hình có phiên bản mới |
| "criteriaGroupId" | uuid | FK → criteria_group.id | Bộ thu thập áp dụng |
| "createdBy" | varchar(256) |  | Người lập báo cáo (username) |
| "modifiedBy" | varchar(256) |  |  |
| "createdDate" | timestamp |  |  |
| "modifiedDate" | timestamp |  | Thời điểm lưu nháp gần nhất (SRS 6.9.1, dòng 3428) |
| "submittedAt" | timestamptz |  | Thời điểm gửi duyệt gần nhất (SRS 6.9.1, dòng 3429) |
| approvedAt | timestamptz |  | Thời điểm duyệt của cấp cuối cùng — cập nhật khi report_review_step ghi nhận hành động Duyệt ở bước cuối (SRS 6.9.1, dòng 3430) |
| "deletedAt" | timestamp |  | Thời điểm xoá (soft-delete) |
| "reportData" | jsonb |  | Cây tiêu chí đầy đủ (snapshot), bao gồm cả giá trị đã nhập — xem Phụ lục A |

**Quan hệ**

• criteriaGroupId → criteria_group.id

• Không có cột officeId trực tiếp — để xác định đơn vị phụ trách, JOIN qua mission.id (bên trong reportData) → office_mission.missionId → office_mission.officeId

• report_record_history.reportRecordId → report_record.id

**Cấu trúc JSONB**

• **reportData:** Mảng cây đệ quy — mỗi phần tử là 1 tiêu chí, chứa children lồng nhau. Đầy đủ khoá quan sát được trong dữ liệu thật: id, code, name, level, parentId, missionId, scopeId, parentName, status, role, dataType, inputMethod, guide, placeholder, minLength, maxLength, options, sumToParent, aggregateFn, shareData, usedInGroups, hidden, required, value, creatorId, creator, modifier, createdDate, modifiedDate, children. Mẫu thực tế: \[{"id":"a34a...", "code":"tong_so_don_vi_bao_cao_1", "name":"Tổng số đơn vị báo cáo", "role":"aggregate", "guide":null, "level":1, "value":356, "status":"public", "creator":"long", "children":\[{"id":"bc16...", "code":"loai_hinh_khac_2", "name":"Loại hình khác", "role":"measure", "guide":null, "level":2, "value":8, "status":"public", "creator":"long", "children":\[\], "dataType":"collected", "modifier":"long", "parentId":"a34a...", "maxLength":999, "minLength":0, "missionId":"7fb5...", "aggregateFn":null, "createdDate":"2026-01-14T04:30:56.698Z", "inputMethod":"number", "placeholder":null, "sumToParent":true, "modifiedDate":"2026-01-14T06:05:32.840Z"}\]}\]. Trường value ở node cấp cha (role=aggregate) là kết quả tính tổng từ children có sumToParent=true (SRS 6.9 BR5: L1 = Σ(L2), L2 = Σ(L3)). hidden/required là giá trị ghi đè theo từng bộ thu thập (tương ứng SRS 6.7.2.2 — Ẩn/hiện và Bắt buộc theo form).

*Tham chiếu SRS: 6.9 Thu thập dữ liệu; 6.12 Duyệt dữ liệu thu thập*

### 7.3 Bảng report_review_step

*Trạng thái:* **Theo đặc tả SRS**

Lịch sử từng bước xử lý duyệt của một report_record (tab "Tiến độ xử lý", SRS 6.9.2/6.12.2).

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK, DEFAULT uuid_generate_v4() | Định danh bước xử lý |
| yearCode | varchar(4) | NOT NULL | Năm áp dụng |
| reportRecordId | uuid | FK → report_record.id | Bản ghi báo cáo |
| criteriaGroupId | uuid | FK → criteria_group.id | Bộ thu thập |
| stepOrder | integer |  | Thứ tự bước duyệt |
| status | review_step_status_enum |  | Lưu nháp / Đã gửi / Chờ duyệt / Đã duyệt / Từ chối |
| action | review_action_enum |  | Gửi dữ liệu / Duyệt dữ liệu / Từ chối / Trả về bước trước — hành động cuối chỉ khả dụng khi phiên bản cấu hình có allowReturnPreviousStep = true |
| description | varchar(1000) |  | Ý kiến người duyệt/từ chối |
| actorUserId | uuid |  | Người thực hiện (duyệt/từ chối) — SRS yêu cầu ghi rõ nhưng bảng UI 6.9.2/6.12.2 không có cột này, đã bổ sung theo yêu cầu BR |
| createdBy/createdAt | — |  | Người xử lý, thời gian xử lý |

**Quan hệ**

• reportRecordId → report_record.id

• criteriaGroupId → criteria_group.id

*Tham chiếu SRS: 6.9.2 Tab tiến độ xử lý; 6.12.2 Luồng duyệt/từ chối*

### 7.4 Bảng report_record_history

*Trạng thái:* **Đã triển khai**

Lưu từng phiên bản snapshot dữ liệu của report_record theo thời gian — phục vụ màn hình "Lịch sử chỉnh sửa" (SRS 6.9.3): xem tại một mốc lưu, dữ liệu tiêu chí nào đã đổi.

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK | Định danh phiên bản lịch sử |
| "reportRecordId" | uuid | FK → report_record.id | Bản ghi báo cáo mà phiên bản này thuộc về |
| version | integer |  | Số phiên bản, tăng dần theo thời gian (1, 2, 3...) — phiên bản có số lớn nhất là bản mới nhất. Khi report_record chưa có phiên bản lịch sử nào, chính report_record được coi là phiên bản 0 |
| "reportDataSnapshot" | jsonb |  | Toàn bộ nội dung reportData tại thời điểm lưu phiên bản — CÙNG CẤU TRÚC CÂY như report_record.reportData (xem Phụ lục A) |
| "createdBy" | varchar(256) |  | Người thực hiện (username) |
| "createdUserId" | uuid |  | Người thực hiện (UUID) |
| "creator" | varchar(256) |  | Tên hiển thị người thực hiện (snapshot) |
| "modifiedBy"/"modifiedUserId"/"modifier" | — |  | Tương tự, cho lần sửa gần nhất |
| "deletedBy" | varchar(256) |  |  |
| "createdDate" | timestamp |  | Mốc thời gian hiển thị trong Timeline |
| "modifiedDate" | timestamp |  |  |
| "deletedAt" | timestamp |  |  |

**Quan hệ**

• reportRecordId → report_record.id

**Cấu trúc JSONB**

• **reportDataSnapshot:** Giống hệt cấu trúc cây của report_record.reportData — xem Phụ lục A.

*Tham chiếu SRS: 6.9.3 Lịch sử chỉnh sửa*

# 8. Phiếu rà soát

### 8.1 Bảng collection_form

*Trạng thái:* **Đã triển khai**

Phiếu rà soát — mẫu biểu thu thập dữ liệu công khai cho người dân điền, với câu hỏi động và rule hiển thị có điều kiện.

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK | Định danh mẫu phiếu |
| code | varchar(100) | NOT NULL, UNIQUE | Mã phiếu rà soát |
| name | varchar(120) | NOT NULL | Tên phiếu |
| description | text |  | Mô tả phiếu |
| "tenantCode" | varchar(64) |  | Tỉnh/thành |
| "departmentCode" | varchar(64) |  | Cơ quan chủ quản |
| "yearCode" | varchar(4) |  | Năm áp dụng |
| "startDate" | timestamptz |  | Ngày bắt đầu hiệu lực |
| "endDate" | timestamptz |  | Ngày kết thúc hiệu lực |
| "isDisabled" | boolean |  | Cờ tắt thủ công — dùng để xác định trạng thái "Đã tắt" (SRS 6.10.1) |
| status | collection_form_status_enum | DEFAULT 'new' | Xem Phụ lục B |
| criteriaGroupIds | uuid\[\] | NOT NULL | Danh sách Bộ thu thập được chọn cho phiếu, ≥1 phần tử — khoá không đổi được sau khi tạo (SRS 6.10.3, dòng 3816, 3872, 3935) |
| publicToken | varchar(64) | UNIQUE | Token bí mật gắn kèm link chia sẻ công khai |
| tokenExpiredAt | timestamptz |  | Hạn dùng của token — không vượt quá endDate (SRS 6.10.2 BR4, 6.11 BR1, dòng 3766, 4022) |
| "config" | jsonb |  | Cấu hình câu hỏi động của phiếu — generalCriteria + scopeCriteria + ocr. Xem Phụ lục A |
| "createdDate"/"createdBy"/"createdUserId"/"creator" | — |  | Khối audit đầy đủ |
| "modifiedDate"/"modifiedBy"/"modifiedUserId"/"modifier" | — |  |  |
| "deletedAt"/"deletedBy" | — |  | Soft-delete — SRS 6.10.1 yêu cầu thêm khôi phục trong 30 ngày (xử lý ở tầng ứng dụng, không cần cột riêng) |
| "usedIds"/"usedId" | — |  | Đánh dấu đã có lượt khai báo hay chưa — quyết định được phép xoá/sửa cấu trúc hay không (SRS 6.10.1, 6.10.3 BR8) |

**Quan hệ**

• criteriaGroupIds → criteria_group.id (mảng, N-N)

• Liên kết tới Lĩnh vực qua config → scopeCriteria (khoá của object chính là scopeId)

**Cấu trúc JSONB**

• **config:** 3 khoá gốc: generalCriteria (mảng câu hỏi thông tin chung, sourceLevel = 0), scopeCriteria (object khoá theo scopeId, mỗi giá trị là mảng câu hỏi nghiệp vụ với sourceLevel = 1/2/3 tương ứng cấp tiêu chí), và ocr. Mỗi câu hỏi gồm: qid, order, title, required, sourceLevel, displayMode (always/when), condition ({questionId, values}), options (\[{value, display}\]), dataKeys, displayValue (mảng nhãn hiển thị khi điều kiện thoả), inputMethod, minLength, maxLength. Mẫu thực tế: {"generalCriteria": \[{"qid":"d0b7...", "order":1, "title":"Họ và tên", "options":false, "dataKeys":\["full_name"\], "required":true, "condition":null, "maxLength":100, "minLength":1, "displayMode":"always", "inputMethod":"text", "sourceLevel":0}\], "scopeCriteria": {"\<scopeId\>": \[{"qid":"f8b6...", "order":1, "title":"Tình trạng tham gia HĐKT", "options":\[{"value":"lao_dong_that_nghiep","display":"Lao động thất nghiệp"},...\], "dataKeys":\["lao_dong_that_nghiep",...\], "required":true, "condition":null, "displayMode":"always", "sourceLevel":1}, {"qid":"53d6...", "order":2, "title":"Nhóm HĐLĐ", "options":\[...\], "dataKeys":\[...\], "required":false, "condition":{"questionId":"f8b6...","values":\["nguoi_ld_co_viec_lam"\]}, "displayValue":\["Có việc làm","Không có việc làm"\], "displayMode":"when", "sourceLevel":2}\]}, "ocr": "cccd"}. condition/displayMode hiện thực đúng rule hiển thị có điều kiện của SRS 6.10.3 ("Luôn hiển thị" = always, "Theo câu hỏi trước" = when, chỉ tham chiếu câu hỏi đứng trước). ocr (giá trị quan sát: "cccd") là tính năng OCR quét giấy tờ tuỳ thân để tự động điền phiếu, nằm ngoài phạm vi đặc tả của SRS.

*Tham chiếu SRS: 6.10 Cấu hình phiếu rà soát*

### 8.2 Bảng collection_form_record

*Trạng thái:* **Đã triển khai**

Một lượt người dân khai báo/rà soát dữ liệu theo 1 phiếu rà soát.

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK | Định danh lượt khai báo |
| "formId" | uuid | FK → collection_form.id | Thuộc phiếu rà soát nào |
| "yearCode" | varchar(4) |  | Năm áp dụng |
| "reportDate" | date |  | Ngày rà soát |
| status | varchar(32) |  | Trạng thái xử lý (dữ liệu thật quan sát: submitted) |
| "submittedAt" | timestamptz |  | Thời điểm người dân gửi phiếu |
| "lastSavedAt" | timestamptz |  | Thời điểm lưu nháp gần nhất (nếu cho lưu nháp) |
| "formData" | jsonb |  | Dữ liệu người dân đã điền. Xem Phụ lục A |
| "tenantCode"/"departmentCode" | varchar(64) |  | Tỉnh/thành, cơ quan |
| "createdDate"/"createdBy"/"createdUserId"/"creator" | — |  | Khối audit |
| "modifiedDate"/"modifiedBy"/"modifiedUserId"/"modifier" | — |  |  |
| "deletedAt"/"deletedBy" | — |  |  |
| "usedIds"/"usedId" | — |  |  |

**Quan hệ**

• formId → collection_form.id

**Cấu trúc JSONB**

• **formData:** Mẫu THẬT (đã có dữ liệu): {"generalCriteria": \[\], "collectionCriteria": \[{"id":"6a28...", "code":"nguoi_co_viec_lam", "name":"Người có việc làm trước tết 2026", "value":"Người có việc làm"}\]}

*Tham chiếu SRS: 6.10.4, 6.11 Rà soát dữ liệu*

# 9. Báo cáo tổng hợp

### 9.1 Bảng report_summary

*Trạng thái:* **Theo đặc tả SRS**

Cấu hình báo cáo động do người dùng tự tạo (SRS 6.13): chọn tiêu chí, phạm vi, khoảng thời gian, kiểu hiển thị; khi xem báo cáo hệ thống tính toán và lưu snapshot vào summaryData.

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK | Định danh bản ghi cấu hình báo cáo |
| name | varchar(150) | NOT NULL | Tên báo cáo |
| description | varchar(500) |  | Mô tả — dùng làm điều kiện tìm kiếm (SRS 6.13.1) |
| yearCode | varchar(4) | NOT NULL | Năm làm việc áp dụng |
| departmentCode | varchar(64) |  | Cơ quan đơn vị |
| officeId | uuid | FK → office.id | Phòng ban sở hữu báo cáo — quyết định phạm vi khi shareStatus = department (SRS 6.13.1, dòng 4314, 4327, 4334: chia sẻ mức Phòng ban khác với cơ quan) |
| tenantCode | varchar(64) |  | Tỉnh |
| scopeIds | uuid\[\] |  | Các lĩnh vực |
| missionIds | uuid\[\] |  | Các nhiệm vụ |
| criteriasConfig | jsonb |  | Cấu hình bố cục tiêu chí báo cáo — xem Phụ lục A |
| dateFrom / dateTo | timestamptz |  | Khoảng thời gian báo cáo; SRS giới hạn khoảng ≤ 365 ngày |
| displayType | report_summary_display_type_enum |  | latest (Mới nhất) / list (Liệt kê) |
| shareStatus | report_summary_share_status_enum |  | private (Cá nhân) / department (Phòng ban) |
| unitScopeType | report_summary_unit_scope_enum |  | self (Trong cơ quan) / subordinate (Đơn vị cấp dưới) |
| departmentCodes | jsonb |  | Danh sách mã đơn vị cấp dưới đã chọn khi unitScopeType = subordinate (tối đa 50 đơn vị/lần chạy). Ví dụ: \["27310", "27313"\] |
| summaryData | jsonb | NOT NULL | Dữ liệu tổng hợp đã tính toán (snapshot) — xem Phụ lục A |
| createdBy/updatedBy/createdAt/updatedAt | — |  | Khối audit chuẩn |

**Quan hệ**

• officeId → office.id

• scopeIds/missionIds tham chiếu scope.id/mission.id dạng mảng

• Khi tính toán, lọc report_record theo yearCode + dateFrom/dateTo + scopeIds/missionIds, rồi join qua office_mission để xác định phạm vi đơn vị (self/subordinate)

**Cấu trúc JSONB**

• **criteriasConfig:** \[{"criteriaId":"uuid","order":0,"level":1,"parentId":null,"dataType":"number"}, ...\] — thứ tự chỉ đổi được trong phạm vi đồng cấp (SRS 6.13.2).

• **summaryData:** Snapshot kết quả tính toán theo tiêu chí/đơn vị/thời gian, cấu trúc phụ thuộc displayType (latest: 1 giá trị/tiêu chí; list: mảng theo mốc thời gian).

*Tham chiếu SRS: 6.13 Tổng hợp dữ liệu*

# 10. Chatbot

### 10.1 Bảng chat_message

*Trạng thái:* **Theo đặc tả SRS**

Lưu hội thoại giữa người dùng và chatbot hỗ trợ trên hệ thống.

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----------------|------------------|---------------|---------------------|
| id             | uuid             | PK            | Định danh tin nhắn  |
| userId         | uuid             |               | Người nhắn          |
| senderType     | sender_type_enum | NOT NULL      | user / bot          |
| messageContent | text             | NOT NULL      | Nội dung tin nhắn   |
| createdAt      | timestamptz      | DEFAULT now() | Thời điểm gửi       |

**Quan hệ**

• Hội thoại được xác định duy nhất bằng userId — mọi tin nhắn giữa 1 người dùng và bot nằm trên cùng 1 dòng thời gian liên tục, không tách theo phiên/thread riêng

*Tham chiếu SRS: 6.15 Chatbot (SRS không có đặc tả, mô tả lấy từ tài liệu rời)*

# 11. Cấu hình hiển thị

### 11.1 Bảng visual_config

*Trạng thái:* **Theo đặc tả SRS**

Cấu hình chung cho Dashboard/Landing page/Website theo Lĩnh vực, Năm, Đơn vị.

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK | Định danh cấu hình |
| type | visual_config_type_enum | NOT NULL | dashboard / landingPage / website |
| scopeId | uuid |  | Liên kết Lĩnh vực |
| yearCode | varchar(4) |  | Năm áp dụng |
| departmentCode | varchar(64) |  | Cơ quan đơn vị |
| tenantCode | varchar(64) |  | Tỉnh/thành |
| displayOrder | integer |  | Thứ tự hiển thị Lĩnh vực trên dashboard (SRS 6.16) |
| isPublished | boolean |  | Đã publish cho năm làm việc hay chưa (SRS E3, mục 6.16) |
| status | boolean | DEFAULT true | Bật/tắt toàn bộ khối hiển thị của Lĩnh vực này |
| createdBy/updatedBy/createdAt/updatedAt | — |  | Khối audit chuẩn |

**Quan hệ**

• scopeId → scope.id

• chart.configId / kpi.configId → visual_config.id

*Tham chiếu SRS: 6.14 Dashboard; 6.15 Landing page; 6.16 Cấu hình Dashboard*

### 11.2 Bảng chart

*Trạng thái:* **Theo đặc tả SRS**

Biểu đồ hiển thị trên Dashboard/Landing page, thuộc 1 Lĩnh vực.

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK | Định danh biểu đồ |
| configId | uuid | FK → visual_config.id | Liên kết cấu hình hiển thị |
| yearCode | varchar(4) | NOT NULL | Năm tạo |
| departmentCode / tenantCode | varchar(64) |  | Cơ quan, tỉnh |
| chartName | varchar(80) |  | Tên biểu đồ |
| chartType | chart_type_enum | NOT NULL | number/line/area/bar/pie/table — xem Phụ lục B |
| criteriaIds | jsonb |  | Danh sách tiêu chí dùng để lọc dữ liệu — TỐI ĐA 8 chỉ tiêu theo SRS 6.16, cùng cấp |
| displayOrder | integer |  | Thứ tự hiển thị trong Lĩnh vực |
| status | varchar | DEFAULT 'active' | active / inactive |
| createdBy/updatedBy/createdAt/updatedAt | — |  | Khối audit chuẩn |

**Quan hệ**

• configId → visual_config.id

**Cấu trúc JSONB**

• **criteriaIds:** \["uuid1", "uuid2",...\] — tối đa 8 phần tử, phải cùng cấp tiêu chí (SRS 6.16.1).

*Tham chiếu SRS: 6.14 Dashboard; 6.16 Cấu hình Dashboard*

### 11.3 Bảng kpi

*Trạng thái:* **Theo đặc tả SRS**

Thẻ chỉ số KPI hiển thị trên Dashboard/Landing page, thuộc 1 Lĩnh vực (tối đa 6 thẻ/lĩnh vực).

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK | Định danh thẻ KPI |
| configId | uuid | FK → visual_config.id |  |
| departmentCode / tenantCode | varchar(64) |  | Cơ quan, tỉnh |
| yearCode | varchar(4) |  | Năm tạo |
| name | varchar(80) | NOT NULL | Tên hiển thị trên thẻ KPI |
| aggregateType | aggregate_type_enum |  | SUM/AVG/COUNT/LATEST |
| criteriaId | uuid | FK, NOT NULL | Tiêu chí lấy dữ liệu |
| color | varchar(10) |  | Mã màu viền thẻ (hex) |
| iconUrl | text |  | Đường dẫn ảnh/icon |
| displayOrder | integer |  | Thứ tự hiển thị |
| status | varchar |  | active / inactive |
| createdBy/updatedBy/createdAt/updatedAt | — |  | Khối audit chuẩn |

**Quan hệ**

• configId → visual_config.id

• criteriaId → collection_criteria.id

*Tham chiếu SRS: 6.14 Dashboard; 6.16 Cấu hình Dashboard*

# 12. Cấu hình website

### 12.1 Bảng website_config

*Trạng thái:* **Theo đặc tả SRS**

Cấu hình chung cho website công khai của 1 tỉnh/cơ quan.

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK | Định danh cấu hình website |
| tenantCode | varchar(64) | NOT NULL | Tỉnh/Tenant |
| departmentCode | varchar(64) |  | Cơ quan chủ quản (nếu có) |
| yearCode | varchar(4) | NOT NULL | Năm áp dụng |
| siteName | varchar(100) | NOT NULL | Tên hệ thống/tiêu đề website |
| favicon | varchar(255) |  | Đường dẫn favicon |
| footerContent | text |  | Nội dung footer |
| createdBy/updatedBy/createdAt/updatedAt | — |  | Khối audit chuẩn |

**Quan hệ**

• websiteBanner.websiteConfigId → website_config.id

*Tham chiếu SRS: 6.16 (dropdown "Cấu hình website" — SRS không đặc tả chi tiết, nội dung lấy từ tài liệu rời)*

### 12.2 Bảng website_banner

*Trạng thái:* **Theo đặc tả SRS**

Banner hiển thị trên trang chủ website.

**Cấu trúc thuộc tính**

| **Thuộc tính** | **Kiểu dữ liệu** | **Ràng buộc** | **Mô tả / Ý nghĩa** |
|----|----|----|----|
| id | uuid | PK | Định danh banner |
| websiteConfigId | uuid | NOT NULL, FK → website_config.id | Liên kết cấu hình website |
| tenantCode / departmentCode | varchar(64) |  | Tỉnh, cơ quan (nếu có) |
| yearCode | varchar(4) |  | Năm áp dụng banner |
| title | varchar(100) |  | Tiêu đề banner |
| imageUrl | varchar(500) |  | Đường dẫn ảnh banner |
| linkUrl | varchar(500) |  | Link khi click banner |
| displayOrder | integer |  | Thứ tự hiển thị |
| isActive | boolean | DEFAULT true | Trạng thái hiển thị |
| createdBy/updatedBy/createdAt/updatedAt | — |  | Khối audit chuẩn |

**Quan hệ**

• websiteConfigId → website_config.id

*Tham chiếu SRS: 6.16 Cấu hình website*

## 9.2 Luồng xử lý báo cáo tổng hợp

### Luồng I — Tạo mới / chỉnh sửa báo cáo (lưu cấu hình vào report_summary)

• Bước 1. Người dùng nhập tên báo cáo, chọn năm làm việc, chọn danh sách Lĩnh vực/Nhiệm vụ, chọn khoảng thời gian (dateFrom → dateTo, tối đa 365 ngày) → lưu vào name, yearCode, scopeIds, missionIds, dateFrom, dateTo.

• Bước 2. Chọn phạm vi đơn vị: Trong cơ quan (self) hoặc Đơn vị cấp dưới (subordinate) → lưu vào unitScopeType.

• Bước 3. Nếu subordinate: chọn danh sách đơn vị cấp dưới (tối đa 50) → lưu vào departmentCodes (jsonb).

• Bước 4. Thiết kế bố cục báo cáo: kéo thả tiêu chí, sắp xếp thứ tự (chỉ trong phạm vi đồng cấp), loại bỏ trùng lặp → lưu vào criteriasConfig (jsonb).

• Bước 5. Chọn kiểu hiển thị: latest (Mới nhất) / list (Liệt kê) → lưu vào displayType.

• Bước 6. Chọn chế độ chia sẻ: private (Cá nhân) / department (Phòng ban) → lưu vào shareStatus.

• Bước 7. Lưu cấu hình: hệ thống tạo mới hoặc cập nhật bản ghi report_summary; summaryData ban đầu rỗng, sẽ được tính khi người dùng nhấn Xem báo cáo.

### Luồng II — Xem / tính toán báo cáo (tạo snapshot dữ liệu)

• Bước 1. Tải cấu hình từ report_summary theo id; dựng điều kiện lọc report_record theo yearCode, dateFrom/dateTo (so với submittedAt), scopeIds/missionIds (thông qua criteria_group liên kết Mission/Scope).

• Bước 2. Áp dụng phạm vi đơn vị: nếu unitScopeType = subordinate → lọc theo report_record có departmentCode nằm trong departmentCodes đã chọn (join qua office_mission → office.departmentCode); nếu = self → lọc theo các phòng ban nội bộ của cơ quan tạo báo cáo.

• Bước 3. Xử lý theo displayType: list → lấy toàn bộ bản ghi report_record thoả điều kiện, mỗi bản ghi là một dòng; latest → với mỗi tiêu chí/đơn vị chỉ lấy bản ghi có submittedAt mới nhất ≤ dateTo.

• Bước 4. Tổng hợp dữ liệu, lưu vào summaryData (jsonb); trả bảng dữ liệu ra giao diện (có phân trang); kích hoạt nút Xuất Excel (định dạng XLSX).

## 11.4 Luồng cấu hình & hiển thị Dashboard/Landing page

### Luồng 1 — Cấu hình (thiết lập khung)

Mỗi Lĩnh vực có 1 bản ghi visual_config riêng gắn với Năm và Đơn vị. Dựa trên bản ghi này, các bảng kpi và chart lưu danh sách mã tiêu chí cần hiển thị — tạo ra một "bản đồ" để hệ thống biết cần truy vấn tiêu chí nào từ CSDL cho Lĩnh vực đó.

### Luồng 2 — Hiển thị (đổ dữ liệu lên UI)

• Bước 1: Người dùng chọn Lĩnh vực và khoảng thời gian trên giao diện.

• Bước 2: Backend đọc visual_config của Lĩnh vực đó để lấy danh sách mã tiêu chí đã thiết lập.

• Bước 3: Backend truy vấn report_record, lọc đồng thời: đúng Lĩnh vực đã chọn, trạng thái = approved (Đã duyệt), thời gian ghi nhận nằm trong khoảng đã lọc.

• Bước 4: Bóc tách dữ liệu từ reportData (jsonb) của các bản ghi thoả điều kiện, tính toán (cộng dồn/gom nhóm theo mốc thời gian) cho từng tiêu chí.

• Bước 5: Trả dữ liệu đã tính toán về giao diện; hiển thị theo loại (Thẻ số hay Biểu đồ).

# 13. Phụ lục

## Phụ lục A — Tổng hợp cấu trúc JSONB

Xem chi tiết từng trường JSONB tại phần "Cấu trúc JSONB" của mỗi bảng tương ứng ở Chương 4-12. Danh sách các trường JSONB đã đặc tả trong tài liệu này:

| **Trường JSONB** | **Vị trí đặc tả chi tiết** |
|----|----|
| stage_ward.old_codes | Xem Chương tương ứng — mục "stage_ward" |
| general_criteria.options | Xem Chương tương ứng — mục "general_criteria" |
| criteria_group.config | Xem Chương tương ứng — mục "criteria_group" |
| evaluation_config.version / steps | Xem Chương tương ứng — mục "evaluation_config" |
| report_record.reportData | Xem Chương tương ứng — mục "report_record" |
| report_record_history.reportDataSnapshot | Xem Chương tương ứng — mục "report_record_history" |
| collection_form.config | Xem Chương tương ứng — mục "collection_form" |
| collection_form_record.formData | Xem Chương tương ứng — mục "collection_form_record" |
| report_summary.criteriasConfig | Xem Chương tương ứng — mục "report_summary" |
| report_summary.summaryData | Xem Chương tương ứng — mục "report_summary" |
| chart.criteriaIds | Xem Chương tương ứng — mục "chart" |

## Phụ lục B — Danh mục ENUM / giá trị chuẩn hoá

**collection_criteria_status_enum**

• **Giá trị:** new, pending, rejected, public, active, archived, draft, local

• **Dùng ở:** collection_criteria.status

• **Tần suất trong dữ liệu thật:** new (1.743), public (371), local (19)

• **Nhãn hiển thị:** Mới, Chờ duyệt, Từ chối, Công khai, Hoạt động, Lưu trữ, Nháp, Cục bộ

**criteria_group_status_enum**

• **Giá trị:** draft, active, archived, new

• **Dùng ở:** criteria_group.status

• **Tần suất trong dữ liệu thật:** new (87), active (26), draft (3), archived (1)

• **Nhãn hiển thị:** Lưu nháp, Đang sử dụng, Lưu trữ, Mới

**collection_form_status_enum**

• **Giá trị:** draft, active, archived, new

• **Dùng ở:** collection_form.status

• **Tần suất trong dữ liệu thật:** active (7), archived (15), draft (4), new (14)

• **Nhãn hiển thị:** Lưu nháp, Đang sử dụng, Lưu trữ, Mới

**data_type_enum**

• **Giá trị:** information, collected

• **Dùng ở:** collection_criteria.dataType, general_criteria.dataType

• **Tần suất trong dữ liệu thật:** collected (100% dữ liệu mẫu)

• **Nhãn hiển thị:** Thông tin chung, Thu thập

**input_method**

• **Giá trị:** number, text, textarea, boolean, date, select, multiselect

• **Dùng ở:** collection_criteria.inputMethod

• **Tần suất trong dữ liệu thật:** number (1.222), text (8), textarea (8), boolean (2), date (2), select (2), multiselect (2)

• **Nhãn hiển thị:** Số, Trả lời ngắn, Trả lời đoạn, Đúng/Sai, Ngày, Danh sách lựa chọn, Nhập liệu từ danh sách

**criteria_role**

• **Giá trị:** group, measure, aggregate

• **Dùng ở:** collection_criteria.role

• **Tần suất trong dữ liệu thật:** measure (1.246), aggregate (270), group (149)

• **Nhãn hiển thị:** Nhóm, Đo lường, Tổng hợp

**aggregate_fn**

• **Giá trị:** sum

• **Dùng ở:** collection_criteria.aggregateFn — áp dụng khi sumToParent = true

• **Tần suất trong dữ liệu thật:** sum (270 bản ghi có sumToParent = true)

• **Nhãn hiển thị:** Phép tổng hợp cho tiêu chí vai trò Tổng hợp

**office_user_role**

• **Giá trị:** LEADER, STAFF

• **Dùng ở:** office_user.role

• **Tần suất trong dữ liệu thật:** STAFF (44), LEADER (34)

• **Nhãn hiển thị:** Lãnh đạo, Chuyên viên

**report_record_status**

• **Giá trị:** draft, pending, approved, rejected

• **Dùng ở:** report_record.status

• **Tần suất trong dữ liệu thật:** pending (52), approved (77), draft (37), rejected (16)

• **Nhãn hiển thị:** Lưu nháp, Chờ duyệt, Đã duyệt, Từ chối

**collection_form_record_status**

• **Giá trị:** submitted

• **Dùng ở:** collection_form_record.status

• **Tần suất trong dữ liệu thật:** submitted (50)

• **Nhãn hiển thị:** Đã gửi

**evaluation_config_status**

• **Giá trị:** draft, active, archived

• **Dùng ở:** evaluation_config (theo từng phiên bản)

• **Nhãn hiển thị:** Lưu nháp, Đang sử dụng, Lưu trữ

**review_step_status**

• **Giá trị:** draft, sent, pending, approved, rejected

• **Dùng ở:** report_review_step.status

• **Nhãn hiển thị:** Lưu nháp, Đã gửi, Chờ duyệt, Đã duyệt, Từ chối

**review_action**

• **Giá trị:** send, approve, reject, return

• **Dùng ở:** report_review_step.action

• **Nhãn hiển thị:** Gửi dữ liệu, Duyệt dữ liệu, Từ chối, Trả về bước trước

**report_summary_display_type**

• **Giá trị:** latest, list

• **Dùng ở:** report_summary.displayType

• **Nhãn hiển thị:** Mới nhất, Liệt kê

**report_summary_share_status**

• **Giá trị:** private, department

• **Dùng ở:** report_summary.shareStatus

• **Nhãn hiển thị:** Cá nhân, Phòng ban

**report_summary_unit_scope**

• **Giá trị:** self, subordinate

• **Dùng ở:** report_summary.unitScopeType

• **Nhãn hiển thị:** Trong cơ quan, Đơn vị cấp dưới

**chart_type**

• **Giá trị:** number, line, area, bar, pie, table

• **Dùng ở:** chart.chartType

• **Nhãn hiển thị:** Số, Đường, Vùng, Cột, Tròn, Bảng

**aggregate_type**

• **Giá trị:** SUM, AVG, COUNT, LATEST

• **Dùng ở:** kpi.aggregateType

• **Nhãn hiển thị:** Tổng, Trung bình, Đếm, Mới nhất

**visual_config_type**

• **Giá trị:** dashboard, landingPage, website

• **Dùng ở:** visual_config.type

• **Nhãn hiển thị:** Dashboard, Landing page, Website

**sender_type**

• **Giá trị:** user, bot

• **Dùng ở:** chat_message.senderType

• **Nhãn hiển thị:** Người dùng, Bot

## Phụ lục C — Chỉ mục đề xuất

• Mọi cột khoá ngoại (parentId, scopeId, missionId, criteriaGroupId, formId, reportRecordId, officeId, userId...) nên có index B-tree để tối ưu truy vấn cây và JOIN.

• report_record: index composite (yearCode, tenantCode, departmentCode, status, reportDate) — phục vụ lọc Dashboard và Báo cáo tổng hợp theo đúng mẫu truy vấn ở Chương 9, 11.

• GIN index trên các cột jsonb được truy vấn thường xuyên (reportData, config) nếu tầng ứng dụng cần lọc/tìm kiếm theo khoá bên trong JSONB thay vì chỉ đọc nguyên khối.

## Phụ lục D — Khuyến nghị mở rộng

Các nội dung dưới đây nằm ngoài phạm vi 27 bảng của tài liệu này, nhưng cần được đội phát triển xem xét bổ sung để đáp ứng đầy đủ yêu cầu nghiệp vụ trong SRS:

• 11 bảng trong tài liệu này (year, general_criteria, evaluation_config, report_review_step, report_summary, chat_message, visual_config, chart, kpi, website_config, website_banner) được mô tả theo đặc tả SRS vì chưa nằm trong phạm vi đồng bộ của kho dữ liệu hiện có.

• 4 bảng tổ chức (stage_province/ward/department/user) đến từ một hệ thống định danh hành chính khác, đồng bộ một chiều và chỉ đọc đối với ứng dụng nghiệp vụ — cần biết cấu trúc để join đúng khi truy vấn theo tổ chức, nhưng không thuộc phạm vi CSDL của ứng dụng.

• evaluation_config hiện lưu version/steps của DUY NHẤT phiên bản đang áp dụng trong 1 dòng — SRS 6.8.2 (dòng 3140-3363) mô tả mỗi cấu hình có NHIỀU phiên bản (Lưu nháp/Đang sử dụng/Lưu trữ), tạo phiên bản mới bằng cách nhân bản phiên bản hiện hành mà không ảnh hưởng các phiên bản trước. Muốn lưu đủ lịch sử nhiều phiên bản cần tách version/steps thành cấu trúc riêng cho từng phiên bản.

• Không có nơi lưu bền vững lựa chọn giao diện của từng người dùng (bộ thu thập chọn gần nhất theo năm, thứ tự/ẩn-hiện cột, số dòng/trang, bộ lọc, trạng thái mở rộng cây) — SRS yêu cầu ở nhiều màn hình (6.1.3, 6.2.3, 6.3.3, 6.6.1, 6.6.3, 6.7.1, 6.8.1, 6.9.1, 6.12.1).

• SRS 6.5.2 yêu cầu khi chuyển phân công (reassign) một nhiệm vụ sang người khác phải giữ lại lịch sử phân công cũ thay vì ghi đè. Thiết kế hiện tại (office_mission, user_mission) chỉ lưu bản ghi đang hiệu lực; muốn giữ lịch sử đầy đủ theo yêu cầu này cần thêm mốc hiệu lực (validFrom/validTo) hoặc một bảng lịch sử phân công riêng.

• Không có bảng audit log riêng cho thao tác nghiệp vụ (ai duyệt/từ chối, ai gán nhiệm vụ, khi nào) mà SRS 6.4.2 BR5, 6.5.2 BR4, 6.9 BR7, 6.16 E4 đều yêu cầu — hiện chỉ có vệt audit cấp bản ghi (createdBy/modifiedBy), không có log cấp hành động.

• Không có bảng notification — SRS 6.12 BR4 yêu cầu gửi thông báo cho cấp duyệt tiếp theo.

• collection_criteria dùng chung một cặp minLength/maxLength cho cả 2 ngữ nghĩa khác nhau: giới hạn giá trị số (khi inputMethod = number) và giới hạn số ký tự (khi inputMethod = text/textarea) — SRS 6.6.2 mô tả đây là 2 khái niệm riêng (giá trị tối thiểu/tối đa và số ký tự tối thiểu/tối đa). Cấu trúc JSONB thật (reportData, criteria_group.config) xác nhận chỉ có 1 cặp — cần tách thành 2 cặp cột riêng nếu sửa.

• collection_criteria không có cột xác định đơn vị sở hữu (departmentCode) — SRS BR2 (6.6.3, dòng 1880) yêu cầu tiêu chí ở trạng thái Mới/Cục bộ/Chờ duyệt/Từ chối chỉ hiển thị trong cơ quan đã tạo ra nó. Hiện chỉ suy ra gián tiếp qua creatorId → stage_user.department_code, sẽ sai lệch khi người tạo chuyển đơn vị.

• website_config chỉ có favicon, không có trường logo, màu chủ đạo hay thông tin liên hệ/SEO; footerContent là một khối văn bản tự do duy nhất — SRS không đặc tả các trường này.

• stage_user (bảng đồng bộ người dùng) không có ngày sinh và giới tính — hai trường mà SRS 6.4.3 yêu cầu khi lọc danh sách thêm người dùng vào phòng ban. Hai trường này cần được lưu ở một bảng/service khác ngoài phạm vi đồng bộ hiện tại.

## Phụ lục E — Ma trận phủ nghiệp vụ SRS

Đối chiếu trực tiếp 17 mục chức năng SRS 6.1-6.16 (mục 6.15 gồm 2 chức năng: Chatbot và Landing page) với bảng/cột đáp ứng trong tài liệu này:

| **Mục SRS** | **Bảng đáp ứng** |
|----|----|
| 6.1 Quản lý năm làm việc | year |
| 6.2 Quản lý lĩnh vực | scope |
| 6.3 Quản lý nhiệm vụ | mission |
| 6.4 Quản lý phòng ban | office, office_mission, office_user |
| 6.5 Quản lý người dùng vào phòng ban | office_user, user_mission |
| 6.6 Quản lý tiêu chí đầu vào | collection_criteria, general_criteria |
| 6.7 Quản lý bộ thu thập | criteria_group |
| 6.8 Quản lý cấu hình đánh giá | evaluation_config |
| 6.9 Thu thập dữ liệu | report_record, report_record_history |
| 6.10 Cấu hình phiếu rà soát | collection_form |
| 6.11 Rà soát dữ liệu | collection_form_record |
| 6.12 Duyệt dữ liệu thu thập | report_review_step |
| 6.13 Tổng hợp dữ liệu | report_summary |
| 6.14 Dashboard | visual_config, chart, kpi |
| 6.15 Chatbot | chat_message |
| 6.15 Landing page | visual_config (type = landingPage), chart, kpi, website_config, website_banner |
| 6.16 Cấu hình Dashboard/Landing page/Website | visual_config, chart, kpi, website_config, website_banner |
