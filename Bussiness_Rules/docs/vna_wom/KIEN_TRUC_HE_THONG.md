# Kiến trúc hệ thống hiện tại — vna_dwh_pipline

Tài liệu này mô tả kiến trúc vận hành **hiện tại** của repo `vna_dwh_pipline`: đây là bước xây dựng
Data Warehouse (DWH) trong toàn bộ hệ thống VNA, chịu trách nhiệm điều phối (orchestration) việc
đưa dữ liệu từ CSDL nghiệp vụ (`vna_wom_dev`) và các hệ thống định danh ngoài vào hai schema kho dữ
liệu: `dwh_internal` (đầy đủ) và `dwh_public` (rút gọn, đã lọc quyền riêng tư).

## 1. Sơ đồ tổng thể

```
                        ┌─────────────────────────────────────────┐
                        │        Hệ thống định danh ngoài          │
                        │  core-tenant-dev.vnaapi.com (tỉnh/thành, │
                        │  phường xã, phòng ban)                   │
                        │  core-user-dev.vnaapi.com (người dùng)   │
                        └───────────────────┬───────────────────────┘
                                            │ REST API (Bearer token)
                                            ▼
┌───────────────────────────────────────────────────────────────────────┐
│                     Airflow (Astronomer, LocalExecutor)                │
│                                                                         │
│  DAG: sync_core_tenant  (0 2 * * * — 2h sáng hằng ngày)                │
│    load_province ─┬─▶ load_ward ────────┐                              │
│                    └─▶ load_department ──┤                             │
│    get_user_ids ──▶ load_user ───────────┤                             │
│                                          ▼                             │
│                                trigger_dbt_dwh_internal                │
│                                          │                             │
│                                          ▼                             │
│  DAG: vna_dwh_internal  (trigger-only, không lịch cố định)             │
│    dbt run — project vna_dwh_internal ──▶ schema dwh_internal          │
│                                                                         │
│  DAG: vna_dwh_public  (*/5 * * * * — mỗi 5 phút, độc lập)              │
│    dbt run — project vna_dwh_public ────▶ schema dwh_public            │
│    (⚠ profile hiện khai schema="dwh_internal" — xem mục 5)             │
└───────────────────────────────────────────────────────────────────────┘
                     │                                   │
                     ▼                                   ▼
         staging.stage_province/ward/          Postgres: vna_wom_dev
         department/user  (Postgres,           ├─ public.*        (CSDL nghiệp vụ, nguồn của dbt)
         TRUNCATE + INSERT toàn bộ mỗi lần)     ├─ dwh_internal.*  (16-17 bảng, đầy đủ)
                                                └─ dwh_public.*     (7 bảng, denormalized, đã lọc)
```

## 2. Hai lớp trong hệ thống

| Lớp | Vị trí | Vai trò |
|---|---|---|
| **Điều phối (orchestration)** | repo `vna_dwh_pipline` (Airflow + Cosmos) | Quyết định *khi nào* và *theo lịch nào* việc đồng bộ/biến đổi dữ liệu chạy; không chứa logic SQL biến đổi dữ liệu. |
| **Biến đổi dữ liệu (transformation)** | 2 dbt project `vna_dwh_internal` / `vna_dwh_public`, nhúng dưới `dags/dbt/` | Chứa toàn bộ logic SQL: chọn cột, join, tính fact, áp incremental/soft-delete. Workspace phát triển gốc là `automation/vna_dwh_internal` — bản nhúng trong `dags/dbt/` cần được đồng bộ lại định kỳ (xem mục 5). |

dbt chạy trong virtualenv riêng (`dbt_venv`, cài `dbt-redshift` dù profile thực tế là Postgres),
tách khỏi virtualenv chính của Airflow — do `Dockerfile` dựng khi build image.

## 3. Ba DAG chính

| DAG (`dag_id`) | Lịch chạy | Vai trò |
|---|---|---|
| `sync_core_tenant` | `0 2 * * *` (2h sáng, hằng ngày) | Gọi REST API bên ngoài để đồng bộ tỉnh/thành, phường xã, phòng ban, người dùng vào schema `staging`; sau khi xong, trigger `vna_dwh_internal`. |
| `vna_dwh_internal` | Không có lịch cố định (`schedule_interval=None`) — chỉ chạy khi được trigger | Chạy toàn bộ dbt project `vna_dwh_internal`, build/refresh schema `dwh_internal`. |
| `vna_dwh_public` | `*/5 * * * *` (mỗi 5 phút) | Chạy dbt project `vna_dwh_public` độc lập, không phụ thuộc lịch của 2 DAG trên. |

## 4. Cơ chế đồng bộ dữ liệu tổ chức (external API sync)

Khác với các bảng nghiệp vụ (`report`, `criteria`, `mission`...) được dbt đọc trực tiếp từ CSDL nguồn
`vna_wom_dev`, nhóm dữ liệu tổ chức (tỉnh/thành, phường xã, phòng ban, người dùng) được đồng bộ theo
cơ chế riêng — **không qua dbt**, mà qua các Airflow `PythonOperator` trong `plugins/core_tenant/`:

- **Nguồn dữ liệu**: `core-tenant-dev.vnaapi.com` (tỉnh/thành `/province/all`, phường xã
  `/ward/all/{provinceCode}`, phòng ban `/department/current/{provinceCode}`) và
  `core-user-dev.vnaapi.com` (`/user/{userId}`).
- **Xác thực**: `core_tenant.api.get_session()` đăng nhập qua `POST {host}/auth/login` với
  `username/password/department/project` lấy từ Airflow Connection **`core_user_api`**, nhận về
  Bearer token dùng cho các lệnh gọi tiếp theo (province/ward/department). Riêng bước
  `load_user` hiện gọi `core-user-dev.vnaapi.com/user/{id}` bằng một `requests.Session()` **không**
  gắn token — khác với 3 bước còn lại, cần xác nhận với đội API xem endpoint này có bắt buộc xác
  thực hay không.
- **Ghi dữ liệu**: mỗi lần chạy đều `TRUNCATE` rồi `INSERT` lại toàn bộ (`execute_values`, không
  phải incremental) vào `staging.stage_province` / `stage_ward` / `stage_department` / `stage_user`
  trong cùng Postgres `vna_wom_dev`.
- **Phạm vi đồng bộ user**: danh sách `userId` cần lấy hồ sơ chi tiết được truy vấn từ chính
  `public.office_user` (bảng ứng dụng đang vận hành) — hệ thống chỉ đồng bộ user đã tồn tại trong
  ứng dụng, không kéo toàn bộ user của hệ thống định danh ngoài.
- Việc gọi API dùng `ThreadPoolExecutor` với `MAX_WORKERS = 6` để tăng tốc khi có nhiều tỉnh/thành
  hoặc nhiều user.

## 5. `dwh_internal` và `dwh_public` — quan hệ và cơ chế lọc quyền riêng tư

`vna_dwh_public` là bản kho dữ liệu rút gọn phục vụ khai thác công khai: bỏ các bảng User/Office chi
tiết, tập trung vào một bảng fact denormalized (`fact_report_criteria`) để BI tool không cần join
nhiều bảng.

**Cơ chế kiểm soát công khai (privacy filter) — đã xác nhận trong SQL**: model
`vna_dwh_public/models/fact/fact_report_criteria.sql` join tới `criteria` và chỉ giữ giá trị
`value` khi `criteria.share_data IS TRUE`; ngược lại `value` được trả về `NULL`. Đây là **cơ chế
duy nhất** quyết định một chỉ tiêu có được công khai hay không — không có tầng lọc nào khác ở phía
DAG hay ứng dụng đọc dữ liệu Public.

**⚠ Lưu ý kỹ thuật cần xác minh**: `dags/vna_dwh_public.py` hiện khai `profile_args["schema"] =
"dwh_internal"` — giống hệt cấu hình của DAG `vna_dwh_internal`, nhiều khả năng là sao chép nhầm.
Cần xác minh dbt project `vna_dwh_public` có đang thực sự build đúng vào schema `dwh_public` hay
đang ghi đè lên schema `dwh_internal`.

## 6. Khác biệt giữa tài liệu vật lý (`code_dwh.sql`) và hệ thống đang chạy thực tế

Các file `docs/internal/code_dwh.sql` và `docs/public/code_dwh.sql` là DDL xuất tay/qua ERD tool
(pgAdmin) tại một thời điểm, hiện đã lệch so với schema đang chạy:

- `code_dwh.sql` (internal) **chưa khai báo** 2 bảng `deparment` và `ward` — 2 bảng này đã tồn tại
  thực tế trong schema `dwh_internal` đang vận hành.
- Bộ giá trị enum khai trong `code_dwh.sql` (dạng chữ hoa, ví dụ `DRAFT/PUBLISHED/CLOSED/ARCHIVED`)
  không khớp với giá trị enum thực tế đang chạy trên CSDL (dạng chữ thường, ví dụ
  `draft/active/archived/new`) — chỉ nên dùng để tham khảo cấu trúc bảng, không dùng làm nguồn xác
  nhận enum.
- Bảng `user_scope` tồn tại vật lý trong schema nhưng model dbt tương ứng (`dim/user_scope.sql`)
  đang ở trạng thái `enabled = false` — bảng này hiện không còn được dbt cập nhật dữ liệu mới.
- dbt project nhúng tại `dags/dbt/vna_dwh_internal` là **bản sao** của workspace phát triển
  `automation/vna_dwh_internal`, hiện lệch 4 file (`criteria.sql`, `mission.sql`, `office.sql`,
  `scope.sql` — do đổi tên cột `yearCode` → `year` ở workspace gốc mà chưa đồng bộ lại bản nhúng).
  Cần một bước đồng bộ thủ công hoặc CI mỗi khi workspace gốc thay đổi.

## 7. Tài liệu liên quan

- [`docs/internal/tai_lieu.docx`](internal/tai_lieu.docx) — chi tiết từng bảng schema `dwh_internal`.
- [`docs/public/tai_lieu.docx`](public/tai_lieu.docx) — chi tiết từng bảng schema `dwh_public`.
- [`docs/internal/code_dwh.sql`](internal/code_dwh.sql), [`docs/public/code_dwh.sql`](public/code_dwh.sql) — DDL tham khảo (xem lưu ý mục 6 ở trên).
- [`docs/internal/ERD_dwh_internal.png`](internal/ERD_dwh_internal.png), [`docs/public/dwh_public.png`](public/dwh_public.png) — sơ đồ ERD.
