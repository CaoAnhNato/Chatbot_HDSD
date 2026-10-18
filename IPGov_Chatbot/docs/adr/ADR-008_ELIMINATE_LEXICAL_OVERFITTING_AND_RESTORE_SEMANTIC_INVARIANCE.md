# ADR-008: BÃI BỎ HOÀN TOÀN REGEX Ở TẦNG NLU/ROUTER & THIẾT LẬP TẦNG NGỮ NGHĨA TỔNG QUÁT BẤT BIẾN (SEMANTIC INVARIANCE)

- **Trạng thái:** ACCEPTED (ĐÃ THỐNG NHẤT VỚI NGƯỜI DÙNG)
- **Ngày quyết định:** 2026-10-11
- **Người đề xuất:** Hội đồng Kiến trúc & Lead QA Auditor
- **Phạm vi tác động:** `IPGov_Chatbot/modules/mod03_router`, `IPGov_Chatbot/modules/mod04_catalog`, `IPGov_Chatbot/modules/mod08_response`
- **Tài liệu SSOT liên quan:**
  * `IPGov_Chatbot/blueprints/02_INTENT_ROUTING_VA_SLOT_EXTRACTION_SSOT.md`
  * `IPGov_Chatbot/blueprints/04_METADATA_CATALOG_VA_CAPABILITY_DISCOVERY_SSOT.md`
  * `IPGov_Chatbot/evaluations/golden_benchmark_fact_criteria_30.json`

---

## 1. BỐI CẢNH VẤN ĐỀ (CONTEXT & PROBLEM STATEMENT)

Trong quá trình vận hành và kiểm toán codebase, hệ thống phát hiện 11 vị trí mã nguồn mang tính "chắp vá" (bypass regex, rẽ nhánh từ khóa cứng, heuristic đếm số từ `len <= 3`, `len <= 4`, cắt chuỗi một chiều `index(kw)` và ép trọng số Steiner Tree `0.1`). 

Các kỹ thuật heuristic này tạo ra hiện tượng **Lexical Overfitting (Quá khớp từ vựng)**:
1. Hệ thống chỉ chạy đúng khi người dùng gõ chính xác các mẫu câu đã được hardcode trong test suite.
2. Hệ thống lập tức gãy đổ (Crash 500 hoặc rò rỉ dữ liệu) khi gặp các câu hỏi tương đương về mặt ngữ nghĩa nhưng khác biệt về hình thái từ vựng (phương ngữ, đảo ngữ, câu ghép có lời chào, từ đệm công vụ, hoán dụ thời gian).
3. Đánh mất hoàn toàn thuộc tính **Semantic Invariance (Bất biến ngữ nghĩa)** được định nghĩa trong nghiên cứu chuẩn mực *CheckList (Ribeiro et al., ACL 2020)* và *Dr.Spider (ICLR 2023)*.

---

## 2. CÁC QUYẾT ĐỊNH KIẾN TRÚC ĐÃ CHỐT (ARCHITECTURAL DECISIONS)

Sau phiên thẩm vấn kỹ thuật đối thoại trực tiếp (`/grill-with-docs`) và thống nhất cùng người dùng, hệ thống cưỡng chế 7 quyết định cốt lõi:

### Quyết định 1: Cấm tuyệt đối thư viện Regex ở tầng NLU / Router
- Nghiêm cấm hoàn toàn các thư viện `re`, `regex`, `google-re2`, `hyperscan` tại các module nhận diện ý định và chuẩn hóa câu hỏi (`canonical_normalizer.py`, `warehouse_langgraph_agent.py`, `clarification_engine.py`).
- Mọi logic nhận diện ý định chào hỏi (`GREETING_FAREWELL`), câu hỏi dữ liệu (`DWH_DATA_QUERY`), câu hỏi làm rõ (`AMBIGUOUS_QUERY`) bắt buộc phải đi qua **Structured Output của DeepSeek Cognitive Planner** (`deepseek/deepseek-v4.1-flash`).

### Quyết định 2: In-Context Temporal Grounding với Mốc Neo Thời Gian (Anchor Date)
- Loại bỏ toàn bộ chuỗi regex bậc thang phân giải quý/tháng/năm trong Stream B.
- Cognitive Planner nhận mốc neo thời gian hệ thống cố định: `anchor_date: '2026-10-11'`.
- Mô hình tự động suy luận và sinh dải ngày ISO:
  * *"Quý vừa qua"* $\to$ `date_from: '2026-07-01'`, `date_to: '2026-09-30'`.
  * *"Đầu năm nay"* $\to$ `date_from: '2026-01-01'`, `date_to: '2026-06-30'`.
- Tầng Python chỉ thực hiện thẩm định định dạng chuỗi ISO an toàn (`datetime.date.fromisoformat`).

### Quyết định 3: Phân rã bài toán con Scatter-Gather cho câu hỏi đa chỉ tiêu lai
- Khi người dùng hỏi ghép các chỉ tiêu khác bản chất (Ví dụ: 1 chỉ tiêu điểm snapshot và 1 chỉ tiêu cộng dồn Additive đa đơn vị):
  * Cognitive Planner phân tách thành $N$ truy vấn con độc lập (`CanonicalQueryFrame`).
  * Thực thi song song xuống kho DWH.
  * Module 08 (`ResponseSynthesizer`) chịu trách nhiệm tập hợp, tinh chỉnh văn phong và phản hồi nhất quán.

### Quyết định 4: Nhận diện mơ hồ theo Khoảng cách biên phân phối (REAR Margin Gap)
- Xóa bỏ hoàn toàn regex lột tiền tố hành động và điều kiện đếm từ `len(query.split()) <= 4`.
- Áp dụng khung REAR (ACL 2024): Kích hoạt Suggestion Chips khi khoảng cách điểm giữa Top 1 và Top 2 trên DuckDB Catalog nhỏ hơn ngưỡng phân phối biên ($\Delta_{\text{margin}} < \sigma_{\text{threshold}}$).

### Quyết định 5: Đỉnh đầu cuối bắt buộc (Required Terminals) trong Steiner Tree
- Xóa bỏ việc ép trọng số cạnh nhân tạo `weight = 0.1` cho bảng `office`.
- Sử dụng trọng số tự nhiên của đồ thị khóa ngoại DWH. Đưa bảng `office` vào danh sách bắt buộc (Terminals) khi câu hỏi yêu cầu thuộc tính cấp đơn vị thực hiện.

### Quyết định 6: Cổng kiểm chuẩn Full Pipeline Golden Benchmark FC-30
- Đánh giá năng lực toàn diện qua 30 câu hỏi của [`golden_benchmark_fact_criteria_30.json`](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/evaluations/golden_benchmark_fact_criteria_30.json).
- Kênh thực thi: Trực tiếp qua HTTP Endpoint `:8000/api/v1/chat` kết nối Live PostgreSQL DB `vna_wom_dev`.
- Ngưỡng đạt chuẩn: Execution Accuracy (EX) $\ge 85 - 90\%$, Valid SQL Rate (VA) $\ge 98\%$, Security Violation Rate = 0.0%.

### Quyết định 7: Xử lý chỉ tiêu cha có giá trị rỗng/dash
- Đối với các câu hỏi chạm vào chỉ tiêu cha có `value = '-'` hoặc `NULL` (ví dụ `FC_001` Trang trại):
  * Hệ thống ưu tiên truy xuất và hiển thị giá trị thực tế phi rỗng từ chỉ tiêu con tương ứng (ví dụ: `330`).
  * Kèm câu chú thích minh bạch cho người dùng về mối quan hệ giữa chỉ tiêu cha và các phân nhánh con.

### Quyết định 8: Thứ Tự Ưu Tiên Tối Thượng & Phân Tầng Mô Hình Thích Ứng (Adaptive Tiering)
- **Thứ tự ưu tiên tối thượng:** Độ chính xác (Accuracy #1) > Thời gian/Độ trễ (Latency #2) > Chi phí tài nguyên (Cost #3).
- **Ranh giới Whitelist OpenRouter:** Chỉ cho phép 4 dòng mô hình (`gemini-3.1-flash-lite`, `gemini-2.5-flash-lite`, `gemini-3.5-flash-lite`, `deepseek/deepseek-v4.1-flash`). Cấm tuyệt đối dòng mô hình Qwen và cấm các API ngoài OpenRouter.
- **Phân tầng thích ứng:** Mặc định Router/NLU chạy `gemini-3.1-flash-lite`; chỉ kích hoạt `deepseek-v4.1-flash` hoặc `gemini-3.5-flash-lite` cho phân rã đa chỉ tiêu hoặc khi độ tự tin thấp.
- **Thực thi song song:** Triển khai `asyncio.gather` cho $N$ truy vấn con Scatter-Gather để giữ độ trễ thấp mà không giảm độ chính xác.

---

## 3. HỆ QUẢ VÀ ĐÁNH ĐỔI KỸ THUẬT (CONSEQUENCES & TRADE-OFFS)

### Điểm tích cực (Pros):
1. **Triệt tiêu 100% Lexical Overfitting:** Không còn phụ thuộc vào việc người dùng dùng từ vựng gì, trật tự câu ra sao.
2. **Khôi phục Semantic Invariance:** Bền bỉ trước các biến thể nhiễu ngôn ngữ (Dr.Spider 17 perturbations).
3. **Mã nguồn sạch & Chuẩn IEEE/Arc42:** Loại bỏ toàn bộ magic numbers, regex chắp vá và điều kiện `if-else` cơ học.

### Điểm đánh đổi (Cons / Trade-offs):
1. **Phụ thuộc vào chất lượng LLM Planner:** Tầng NLU phụ thuộc vào sự suy luận của `deepseek/deepseek-v4.1-flash`. Nếu mạng chập chờn, tầng fallback phải dựa vào DuckDB RAM FTS thay vì regex cứng.
2. **Thời gian suy luận (Latency):** Tăng nhẹ độ trễ khi phân tách câu hỏi lai phức tạp thành $N$ bài toán con, nhưng đổi lại độ chính xác nghiệp vụ đạt mức tối đa.
