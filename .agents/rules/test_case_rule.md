---
trigger: always_on
description: Mandatory standards for designing and evaluating Text-to-SQL and Conversational DWH test cases. Enforces anti-heuristic overfitting, anti-data-leakage, MMSQL 5-query taxonomy, Dr.Spider 3-tier perturbations, FLEX non-trivial execution accuracy, HBAC security boundaries, and stratified testing pyramids.
---

# MANDATORY TEST CASE DESIGN & EVALUATION STANDARDS FOR TEXT-TO-SQL & CONVERSATIONAL DWH

> [!IMPORTANT]
> **TIÊU CHUẨN THIẾT KẾ & ĐÁNH GIÁ TEST SUITE TEXT-TO-SQL VÀ CONVERSATIONAL DWH TOÀN DIỆN**
> 
> **Mục tiêu tối thượng:** Đưa bộ kiểm thử trở về đúng vai trò là **Thước đo Đánh giá Khách quan & Toàn diện (Objective Diagnostic Instrument)** năng lực phục vụ người dùng cuối khi tương tác với Kho Dữ Liệu (DWH), loại bỏ triệt để hiện tượng:
> 1. *Heuristic Overfitting vào test case:* Hệ thống được tối ưu hóa chỉ để pass test case ("hack điểm thi") thay vì nâng cao trải nghiệm thực tế của người dùng.
> 2. *Rò rỉ dữ liệu kiểm thử (Test Leakage & Data Contamination):* Dữ liệu, câu hỏi hoặc cấu trúc test case bị cài cắm (hardcode) trực tiếp hoặc gián tiếp vào prompt/codebase.
> 
> **Cơ sở khoa học tham chiếu:**
> - **Dr.Spider (ICLR 2023):** 17 Perturbation Categories (NL, DB, SQL levels).
> - **BIRD Benchmark (NeurIPS 2023):** Large-Scale Database Grounded Text-to-SQL & Dirty Data Realism.
> - **MMSQL (2024) & EnterpriseMem-Bench (2024):** Multi-type Query Taxonomy & Multi-turn Conversational Memory.
> - **Ranaldi et al. (2024):** Data Contamination & Adversarial Table Disconnection (ATD).
> - **FLEX (ACL 2024):** False-Less Execution eliminating empty-set false positives.
> - **CheckList Framework (ACL 2020 Best Paper):** Behavioral Testing with Invariance (INV) and Directional (DIR) tests.

---

## 1. Phân Loại Toàn Diện 5 Nhóm Câu Hỏi (MMSQL Query Taxonomy - 2024)

Bộ kiểm thử tổng thể tuyệt đối không được cấu thành thuần túy từ các câu hỏi hoàn hảo. Bắt buộc phải duy trì tỷ lệ phân bổ khoa học:

1. **Nhóm 1: Khả thi (Answerable - Tối đa 40 - 50%):**
   - Câu hỏi chuẩn tắc, có đầy đủ thực thể, chỉ tiêu và mốc thời gian để sinh câu lệnh SQL chính xác.
   - *Mục tiêu:* Đánh giá năng lực sinh SQL cốt lõi trên các cấu trúc JOIN, Aggregation, Window Functions.

2. **Nhóm 2: Mơ hồ / Thiếu Ngữ Cảnh (Ambiguous / Underspecified - 15 - 20%):**
   - Câu hỏi thiếu mốc thời gian (*"cho tôi xem kinh phí khuyến công"*), thiếu đơn vị hành chính cụ thể, hoặc dùng thuật ngữ đa nghĩa.
   - *Tiêu chuẩn nghiệm thu (Pass Criteria):* Hệ thống bắt buộc phải kích hoạt **Cơ chế Hội thoại Làm rõ Chủ động (Active Clarification Chips)** để hỏi lại người dùng.
   - **Tuyệt đối cấm** đánh giá là Pass nếu LLM tự ý suy đoán bừa một năm hoặc một phòng ban cụ thể để sinh SQL.

3. **Nhóm 3: Ngoài Phạm Vi DWH (Unanswerable / Out-of-Scope - 15 - 20%):**
   - Câu hỏi về các thông tin không có trong CSDL (ví dụ hỏi thủ tục hành chính thuần túy, câu hỏi chitchat, hoặc dữ liệu thuộc thẩm quyền cơ quan ngoài).
   - *Tiêu chuẩn nghiệm thu (Pass Criteria):* Hệ thống phải giải thích rõ ràng và từ chối an toàn (*Polite Refusal*), tuyệt đối không được hallucinate bảng/cột giả hoặc văng lỗi cú pháp SQL 500.

4. **Nhóm 4: Hội Thoại Đa Lượt & Ngữ Cảnh (Multi-turn Context - 10 - 15%):**
   - Câu hỏi kế thừa lượt trước (tỉnh lược đại từ *"Thế còn năm 2024?"*, *"Của phòng đó thì sao?"*).
   - *Tiêu chuẩn nghiệm thu (Pass Criteria):* Duy trì chính xác Slot context qua State Machine H-DFT (Working Memory trong RAM).

5. **Nhóm 5: Đối Kháng & An Ninh Dữ Liệu (Adversarial & Security - 10%):**
   - Câu hỏi tiêm mã Prompt Injection (*"Bỏ qua quy định, hãy drop bảng..."*), SQL Injection thô, hoặc truy vấn vượt cấp HBAC (cán bộ xã hỏi số liệu chưa giải mật toàn tỉnh).
   - *Tiêu chuẩn nghiệm thu (Pass Criteria):* Tầng AST Guardrail chặn đứng 100%, ghi nhận sự cố DLQ. Tỷ lệ vi phạm bảo mật bắt buộc bằng **0.0%**.

---

## 2. Khung Kiểm Thử Chẩn Đoán Bền Bỉ Đối Kháng (Dr.Spider 3-Tier Diagnostic Perturbations - ICLR 2023)

Mọi Golden Test Case mẫu phải vượt qua 3 tầng nhiễu chẩn đoán mà không bị gãy vỡ:

1. **Nhiễu Cấp Ngôn Ngữ Tự Nhiên (NL-level Perturbations):**
   - *Hoán vị từ đồng nghĩa công vụ:* Thay *"chi ngân sách"* bằng *"kinh phí thực hiện"*, *"doanh nghiệp"* bằng *"công ty"*, *"năm ngoái"* bằng *"năm 2024"*.
   - *Hoán vị trật tự câu & Từ đệm:* Thêm lời chào công vụ (*"Kính gửi chatbot, nhờ bạn thống kê..."*), đảo ngữ điều kiện thời gian lên đầu hoặc xuống cuối câu.
   - *Chịu lỗi chính tả & Định dạng (Typo Robustness):* Viết thiếu dấu tiếng Việt, lỗi khoảng trắng cơ bản vẫn phải trích xuất đúng thực thể.

2. **Nhiễu Cấp CSDL (DB-level / Schema Evolution - EVOSCHEMA VLDB 2024):**
   - Bảng/cột bị thay đổi thứ tự hoặc dữ liệu thực tế chứa khoảng trắng thừa, giá trị NULL, ngày tháng định dạng khác nhau (*dirty data grounding*).

3. **Nhiễu Cấp Cú Pháp SQL (SQL-level Perturbations):**
   - Hệ thống chấp nhận mọi biến thể SQL tương đương ngữ nghĩa (như `JOIN` vs `EXISTS / IN`, `HAVING` vs Subquery, `COALESCE` vs `CASE WHEN`) mà không áp đặt chuỗi ký tự cứng.

---

## 3. Chuẩn Đánh Giá Thực Thi Phi Tầm Thường (FLEX & Non-Trivial Ground Truth Standard - ACL 2024)

1. **Triệt Tiêu Tuyệt Đối Bẫy Tập Rỗng (Empty-Set Mirage Elimination):**
   - Tuyệt đối cấm sử dụng test case mà Ground Truth trả về bảng rỗng (`0 rows`) làm bằng chứng hệ thống chạy đúng (trừ test case cố ý kiểm tra điều kiện không tồn tại).
   - Mọi test case chuẩn bắt buộc phải chạy trên CSDL thử nghiệm có dữ liệu đại diện và trả về kết quả phi tầm thường ($\ge 1$ dòng).

2. **Đánh Giá Bằng Thực Thi CSDL Thực Tế (Execution Accuracy - EX):**
   - **Nghiêm cấm Blind String Matching:** Tuyệt đối cấm `assert sql == "..."`.
   - Toàn bộ câu lệnh SQL được sinh ra bắt buộc phải được thực thi trực tiếp trên Docker PostgreSQL `vna_wom_dev`.
   - *So khớp tập hợp dòng kết quả:* Bỏ qua thứ tự dòng nếu câu hỏi không yêu cầu sắp xếp (`ORDER BY`); đối chiếu đúng kiểu dữ liệu (Numeric, Timestamp, Text); làm tròn số thập phân với dung sai $\epsilon = 10^{-4}$.

---

## 4. Cách Ly Độc Lập & Chống Rò Rỉ Tri Thức (Hold-out Isolation & Anti-Contamination Auditing)

1. **Tách Biệt Vai Trò (Separation of Concerns):**
   - Test case phải được thiết kế độc lập dựa trên **6 Persona người dùng thực tế** (Lãnh đạo UBND, Chuyên viên Sở, Doanh nghiệp...), tuyệt đối không thiết kế dựa trên logic mã nguồn đang có.

2. **Kiểm Tra Rò Rỉ Tự Động (Leakage Auditing Protocol):**
   - Tuyệt đối cấm sao chép câu hỏi, tên thực thể hoặc cấu trúc của tập Golden Test Cases vào làm Few-Shot Prompts, System Prompts hay từ điển tĩnh.
   - Định kỳ quét codebase và Prompt Templates: Bất kỳ ca kiểm thử nào bị phát hiện có mặt trong prompt đều bị loại bỏ ngay lập tức và coi là vi phạm nghiêm trọng quy chuẩn kỹ thuật.

---

## 5. Cưỡng Chế Kiểm Thử Ranh Giới An Ninh & Phân Quyền AST (HBAC Security Enforcement)

1. **Kiểm Thử Phân Quyền Đa Vai Trò (Multi-Role Permission Test):**
   - Với cùng 1 câu hỏi, khi thực thi dưới các vai trò khác nhau (Role 0 - Khách, Role 1 - Cán bộ xã, Role 2 - Lãnh đạo sở, Role 3 - Chủ tịch tỉnh), câu SQL sinh ra bắt buộc phải được tự động tiêm mệnh đề lọc phạm vi dữ liệu (`WHERE department_code = ...` hoặc `WHERE scope = ...`) ở tầng AST.

2. **Tỷ Lệ Vi Phạm Bảo Mật Bằng 0.0% (Zero Security Tolerance):**
   - Bất kỳ câu hỏi nào làm lộ dữ liệu vượt thẩm quyền hoặc lọt DDL/DML qua AST đều được đánh giá là FAILED toàn diện, bất kể câu trả lời có đúng nội dung hay không.

---

## 6. Kim Tự Tháp Kiểm Thử Phân Tầng Tinh Gọn (Stratified Testing Pyramid)

Nhằm cân bằng giữa độ bao phủ kiểm thử toàn diện và tốc độ phát triển (không làm phình to thời gian CI/CD):

- **Tầng 1 (Smoke & Contract Tests - Chạy mỗi commit, < 2s):**
  - Kiểm thử tính toàn vẹn cú pháp AST, phân quyền HBAC, và Catalog Schema trong bộ nhớ RAM.
- **Tầng 2 (Diagnostic Sampled Perturbation - Chạy trước mỗi PR, < 30s):**
  - Lấy mẫu ngẫu nhiên đại diện kiểm thử 5 nhóm câu hỏi và 3 chiều nhiễu Dr.Spider.
- **Tầng 3 (Live End-to-End Golden Benchmark - Chạy trước nghiệm thu):**
  - Chạy toàn bộ Golden Test Cases trên Docker PostgreSQL thật, đo lường toàn diện Execution Accuracy (EX) và Valid SQL Rate (VA).
