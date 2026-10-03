---
title: "Đặc tả Kỹ thuật Module 08: Response Synthesizer & Lineage Badge"
module_id: "MOD-08"
stage: 8
layer: "Response Synthesis & Lineage Verification"
architecture_pattern: "Dual-Engine (Deterministic Fast-Path & Generative LLM with BLUF Enforcement)"
compliance:
  - "Arc42 & IEEE Std 1016-2009"
  - "BLUF Standard (Bottom Line Up Front)"
  - "Zero Hallucination & Zero-Cost Fast-Path (Jinja2 in RAM < 0.05ms)"
  - "Safety Buffer Ceiling (max_tokens = 2048, prompt-controlled brevity)"
linked_blueprints:
  - "IPGov_Chatbot/blueprints/06_OBSERVABILITY_TRACING_DLQ_VA_EVALUATION.md"
  - "IPGov_Chatbot/blueprints/08_BO_TEST_CASE_KIEM_THU_TOAN_DIEN_VA_5_DIEM_MU_DWH.md"
related_traps:
  - "[TRAP-006] Lỗi Pydantic v2 Strict Mode (extra='forbid') Khi Ánh Xạ DTO LLM"
created_date: "2026-09-29"
status: "APPROVED_AND_IMPLEMENTED"
---

# ĐẶC TẢ KỸ THUẬT MODULE 08: RESPONSE SYNTHESIZER & LINEAGE BADGE

> [!IMPORTANT]
> **ĐỘNG CƠ TỔNG HỢP KÉP & CHỨNG THỰC NGUỒN GỐC DỮ LIỆU (DUAL-ENGINE BLUF SYNTHESIS)**
> 
> Module 08 là chặng cuối cùng của pipeline xử lý Text-to-SQL trong hệ thống `IPGov_Chatbot`, chịu trách nhiệm chuyển hóa tập dữ liệu thô từ Module 07 thành câu trả lời ngôn ngữ tự nhiên chuẩn công vụ, súc tích (BLUF - Bottom Line Up Front) kèm theo Thẻ Nguồn Gốc Dữ Liệu (`LineageBadgeDTO`) có mã băm xác thực SHA-256 bất biến.
> 
> Hệ thống áp dụng triết lý thiết kế tối ưu chi phí và độ tin cậy:
> 1. **Tầng Mẫu Tiền Biên Dịch (JinjaSlotEngine):** Khớp các mẫu câu hỏi phổ biến trong bộ nhớ RAM, đạt tốc độ $< 0.05\text{ms}$ và tiêu tốn **0 token LLM** cho toàn bộ các dạng câu hỏi chuẩn tắc.
> 2. **Tầng Sinh Ngôn Ngữ Tự Nhiên (LLMSynthesizer):** Sử dụng `google/gemini-2.5-flash-lite` với cơ chế Safety Buffer Ceiling (`max_tokens = 2048`) ngăn ngừa cắt cụt bảng Markdown, đồng thời siết chặt độ súc tích qua System Prompt (Negative Constraints).
> 3. **Phòng Vệ 2 Tầng (Defensive Dual-Gate):** Tập kết quả rỗng trả về thông báo tất định với 0 lượt gọi LLM; mẫu số bằng 0 hoặc cơ số nhỏ ($< 5$) được chuyển sang chênh lệch tuyệt đối để triệt tiêu `ZeroDivisionError` và hiệu ứng cơ số nhỏ (Small Base Effect).
> 4. **Trực Quan Hóa 8 Giai Đoạn (Web Test Bench UI):** Giao diện `/bench` hiển thị live tiến trình thực thi 8 bước qua SSE stream với ngăn kéo thanh tra chi tiết (Payload Inspector Drawer).

---

## 1. Kiến Trúc Luồng Vận Hành

```mermaid
flowchart TD
    M07["Module 07<br/>QueryResultDTO"] --> Facade["ResponseSynthesizerService"]
    Facade --> CheckEmpty{"Kiểm tra Rỗng / Lỗi CSDL"}
    CheckEmpty -->|CSDL Lỗi| ErrNotif["Thông báo Lỗi CSDL<br/>(RenderMode: ERROR_NOTIFICATION)"]
    CheckEmpty -->|Tập kết quả Rỗng| EmptyNotif["Jinja EMPTY_RESULT<br/>(0ms, 0 Token LLM)"]
    CheckEmpty -->|Có dữ liệu| JinjaCheck{"Khớp mẫu Jinja2?<br/>(Direct, Ranking, YoY, Part-to-Whole...)"}
    
    JinjaCheck -->|Khớp mẫu (100% Golden Cases)| JinjaEngine["JinjaSlotEngine (RAM)<br/>RenderMode: DETERMINISTIC_TEMPLATE"]
    JinjaCheck -->|Không khớp| LLMGen["LLMSynthesizer<br/>Gemini-2.5-flash-lite (Buffer 2048)<br/>RenderMode: LLM_SYNTHESIS"]
    
    JinjaEngine --> BadgeBuild["LineageBadgeBuilder<br/>Tạo SHA-256 + Thẩm quyền HBAC"]
    LLMGen --> BadgeBuild
    EmptyNotif --> BadgeBuild
    
    BadgeBuild --> Out["SynthesizerOutputDTO"]
    ErrNotif --> Out
    Out --> SSE["Gateway SSE Stream<br/>(event: content_chunk & lineage_resolved)"]
    SSE --> UI["Web Test Bench (/bench)<br/>8-Stage Stepper & Inspector Drawer"]
```

---

## 2. Các Thành Phần Nòng Cốt

### 2.1. `JinjaSlotEngine` (`modules/mod08_response/jinja_slot_engine.py`)
- Môi trường Jinja2 tiền biên dịch chạy thuần trong RAM (`DictLoader`).
- Hỗ trợ 11 khuôn mẫu BLUF tiêu chuẩn công vụ:
  1. `DIRECT_METRIC`: Chỉ tiêu đơn lẻ (Single fact metric).
  2. `RANKING_TOP_K`: Xếp hạng Top-K đơn vị có biên độ chênh lệch.
  3. `TEMPORAL_COMPARISON`: So sánh chuỗi thời gian YoY/MoM (hỗ trợ cả kết quả 1 dòng dùng hàm cửa sổ LAG và 2 dòng độc lập).
  4. `PART_TO_WHOLE`: Tỷ trọng cơ cấu bộ phận so với toàn thể.
  5. `REPORT_STATUS`: Trạng thái thẩm định 1 biểu mẫu báo cáo.
  6. `REPORT_STATUS_LIST`: Danh sách trạng thái báo cáo của các đơn vị.
  7. `COLLECTION_FORM`: Danh mục biểu mẫu thu thập dữ liệu đang kích hoạt.
  8. `DATA_ANOMALY`: Kiểm toán bất thường dữ liệu và cảnh báo rà soát.
  9. `USER_MISSION`: Phân công nhiệm vụ và chỉ tiêu cho cán bộ.
  10. `ETL_FRESHNESS`: Mốc thời gian đồng bộ dữ liệu kho DWH gần nhất.
  11. `EMPTY_RESULT`: Thông báo an toàn khi không tìm thấy số liệu đã duyệt.
- Bộ lọc tùy chỉnh:
  - `vn_format_num`: Định dạng số chuẩn Việt Nam (chấm hàng nghìn, phẩy thập phân).
  - `vn_status_translate`: Việt hóa trạng thái công vụ (`approved` $\to$ `Đã phê duyệt`...).
  - `safe_percentage`: Phòng vệ cơ số nhỏ và mẫu số 0.

### 2.2. `LLMSynthesizer` (`modules/mod08_response/llm_synthesizer.py`)
- Mô hình: `google/gemini-2.5-flash-lite`.
- Tham số kỹ thuật:
  - `temperature = 0.0` (tất định, triệt tiêu ảo giác).
  - `max_tokens = 2048` (ngưỡng an toàn chống rách Markdown table).
- Quy chuẩn Prompt:
  - Sử dụng `BLUF_SYSTEM_PROMPT` với các Negative Constraints nghiêm ngặt: không chào hỏi xã giao, không lặp lại câu hỏi người dùng, chỉ nêu 1 gạch đầu dòng xu hướng ngắn gọn ($\le 30$ từ).
- Cơ chế Phục hồi Suy thoái (Graceful Fallback):
  - Khi ngoại lệ mạng hoặc không có API Key, tự động chuyển đổi sang hàm `_render_offline_fallback` tạo bảng Markdown trực tiếp từ DWH rows mà không làm crash ứng dụng.

### 2.3. `LineageBadgeBuilder` (`modules/mod08_response/lineage_badge_builder.py`)
- Tạo đối tượng `LineageBadgeDTO` gắn kèm mọi câu trả lời có dữ liệu:
  - `highest_authority`: Xác định cấp thẩm quyền phê duyệt cao nhất (`UBND Tỉnh`, `Giám đốc Sở`, `Trưởng phòng`, `Cán bộ cơ sở`).
  - `fact_row_count`: Số lượng dòng Fact thực tế đã truy vấn từ PostgreSQL.
  - `verification_hash`: Mã băm SHA-256 bất biến tính toán từ `executed_sql` và `fact_row_count`.
  - `issued_at`: Mốc thời gian phát hành chứng thực (ISO-8601 UTC).
  - `dwh_model`: Tên mô hình dữ liệu (`dwh_internal.fact_report_criteria`).
  - `active_role`: Tên vai trò bảo mật của người dùng yêu cầu tra cứu.

### 2.4. `ResponseSynthesizerService` (`modules/mod08_response/response_synthesizer_service.py`)
- Đóng vai trò Facade Service thống nhất:
  - `synthesize_async(...)`: Sử dụng trong luồng xử lý SSE Stream thời gian thực của Gateway.
  - `synthesize_sync(...)`: Sử dụng trong các bài test chạy hàng loạt và Benchmark Snapshots.

---

## 3. Nâng Cấp Giao Diện Web Test Bench (`role_selector_bench.html`)

Giao diện kiểm thử trực quan tại `/bench` được nâng cấp toàn diện:
1. **8-Stage Execution Stepper:**
   - 8 giai đoạn trực quan: Gateway $\to$ Pre-Router $\to$ H-DFT Router $\to$ Catalog $\to$ SQL Compiler $\to$ AST Enforcer $\to$ DWH Execution $\to$ Response Synthesizer.
   - Trạng thái chuyển đổi động: `Pending` (Xám) $\to$ `Running` (Xanh dương nhấp nháy) $\to$ `Completed` (Xanh lá) / `Blocked` (Đỏ) / `Skipped` (Cam).
2. **Payload Inspector Drawer:**
   - Ngăn kéo mở rộng cho từng stage cho phép lập trình viên và kiểm thử viên kiểm tra payload trung gian (Router classification, Raw SQL, Sanitized SQL, DB row count, Thẻ Lineage Badge).
3. **Thư viện Marked.js:**
   - Render định dạng Markdown mượt mà, hỗ trợ định dạng bảng dữ liệu kẻ ô sắc nét, thẻ in đậm số liệu BLUF.
4. **Lineage Badge Widget:**
   - Hộp thông tin chứng thực nguồn gốc dữ liệu đính kèm nút copy nhanh mã băm SHA-256.

---

## 4. Kết Quả Kiểm Thử Thực Nghiệm (Empirical Test Results)

### 4.1. Unit Tests (Tier 1 Bonsai Ladder)
- Tệp: `IPGov_Chatbot/tests/test_mod08_response.py`
- Kết quả: **16/16 Passed** (0.23s).
- Độ bao phủ: Kiểm thử định dạng số Việt Nam, xử lý chia cho 0, cơ số nhỏ, render 10 mẫu Jinja, đóng gói Thẻ Lineage Badge, và các cổng phòng vệ rỗng/lỗi.

### 4.2. Stream Pipeline Integration Test (Tier 2)
- Tệp: `IPGov_Chatbot/tests/test_stream_pipeline_integration.py`
- Kết quả: **1/1 Passed** (4.51s).
- Khẳng định chuỗi sự kiện SSE: `connected` $\to$ `router_routed` $\to$ `sql_generated` $\to$ `ast_sanitized` $\to$ `db_executed` $\to$ `content_chunk` $\to$ `lineage_resolved` $\to$ `done`.

### 4.3. Chained Snapshot Benchmark Toàn Bộ 8 Stages (Tier 3)
- Tệp: `IPGov_Chatbot/tests/test_chained_snapshots_all_8_stages.py`
- Kết quả: **106/106 Passed** (2.62s).
- Chỉ số đạt được:
  - **Tỷ lệ Tổng hợp Thành công:** **100.0%** (Tiêu chuẩn $\ge 98.0\%$).
  - **Tỷ lệ Tiết kiệm Chi phí qua Jinja Template:** **100.0%** (Tiêu chuẩn $\ge 80.0\%$).
  - **Độ phủ Thẻ Nguồn Gốc Lineage Badge:** **100.0%** (Tiêu chuẩn $100.0\%$).
  - **Tốc độ Xử lý Stage 8 Trung bình:** $< 0.05\text{ms}$ / câu truy vấn.
  - **Nhật ký Kiểm thử Có Cấu Trúc:** `IPGov_Chatbot/tests/logs/test_run_stage8_chained.jsonl`.
  - **Baseline Snapshot:** `IPGov_Chatbot/tests/snapshots/stage_8_synthesizer/snapshot_baseline.json`.
