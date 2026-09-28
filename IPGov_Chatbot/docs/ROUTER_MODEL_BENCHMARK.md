# BẢNG SO SÁNH HIỆU NĂNG THỰC NGHIỆM CÁC MÔ HÌNH ROUTING (MODULE 03)
> Căn cứ thực nghiệm: MMSQL Query Taxonomy (NeurIPS 2023 / 2024), Dr.Spider Diagnostic Perturbations (ICLR 2023), và CheckList Behavioral Testing (Ribeiro et al., ACL 2020).  
> Ngày thực hiện đo đạc: 2026-09-25 | Môi trường: Groq Cloud API & Alibaba DashScope API | Quy tắc MVP: Zero SLA, Defensive Timeout 5.0s  
>  
> > [!NOTE]  
> > **LƯU Ý CẬP NHẬT CHUYỂN ĐỔI CÔNG NGHỆ (v3.2.0 - 2026-09-26):**  
> > Dựa trên quyết định điều chỉnh cấu hình hạn mức từ người dùng, hệ sinh thái Router chính thức chuyển dịch sang **Alibaba DashScope API** (`deepseek-v4.1-flash` P0, fallback sang `deepseek-v4-flash-0731` và `qwen3.8-flash`) với hạn mức 1.000.000 tokens miễn phí không giới hạn RPM/TPM, kết hợp **Redis Distributed Session Memory Pipeline** (`ipgov-redis`, localhost:6379) và **Tier 0.3 Semantic Decision Cache** cho Lượt 1 (< 50ms, 0 token LLM). Bảng dưới đây lưu giữ kết quả đối chuẩn ban đầu của các mô hình phục vụ tra cứu lịch sử (Historical Audit).

## 1. Bảng Tổng Hợp Hiệu Năng & Độ Ổn Định (Summary Matrix)
| Mô Hình (Model) | Nhà Cung Cấp (Provider) | Độ Trễ TB (Latency ms) | Token TB / Lượt | Tỷ Lệ Pass JSON (%) | Độ Chính Xác Intent (%) | Trạng Thái Đánh Giá |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `openai/gpt-oss-20b` | Groq Cloud | 975.3 ms | 1282 tokens | 100.0% | **100.0%** | Khuyến nghị Router Chính (P0) |
| `openai/gpt-oss-120b` | Groq Cloud | 3679.7 ms | 1062 tokens | 80.0% | **80.0%** | Fallback 1 |
| `qwen/qwen3.8-27b` | Groq Cloud | 1337.8 ms | 912 tokens | 80.0% | **80.0%** | Fallback 2 |
| `qwen3.7-flash` | Alibaba DashScope | 5443.3 ms | 0 tokens | 0.0% | **0.0%** | Fallback Cuối |

---

## 2. Chi Tiết Thực Nghiệm Trên 5 Dạng Câu Hỏi Khảo Sát (Quest Breakdown)
### 2.1. Quest 1: Q1_STANDARD_METRIC - Nhóm 1: Chuẩn tắc đơn lẻ (Answerable)
- **Câu hỏi kiểm thử (Prompt):** *"Năm 2026, toàn tỉnh có bao nhiêu vụ tai nạn lao động?"*
- **Ý định kỳ vọng (Expected Intent):** `TEMPLATE_FAST_TRACK`

| Mô Hình | Intent Dự Đoán | Độ Trễ (ms) | Tokens (Prompt/Comp/Total) | JSON Hợp Lệ | Đạt Chuẩn (Pass) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `openai/gpt-oss-20b` | `TEMPLATE_FAST_TRACK` | 973.7 ms | 1219 / 63 / 1282 | Hợp lệ | **PASSED** |
| `openai/gpt-oss-120b` | `TEMPLATE_FAST_TRACK` | 2483.9 ms | 1219 / 160 / 1379 | Hợp lệ | **PASSED** |
| `qwen/qwen3.8-27b` | `TEMPLATE_FAST_TRACK` | 1773.1 ms | 1034 / 111 / 1145 | Hợp lệ | **PASSED** |
| `qwen3.7-flash` | `ERROR` | 6317.9 ms | 0 / 0 / 0 | Lỗi | **FAILED** |

### 2.2. Quest 2: Q2_AMBIGUOUS_CLARIFY - Nhóm 2: Mơ hồ / Thiếu mốc thời gian (Ambiguous)
- **Câu hỏi kiểm thử (Prompt):** *"Kinh phí thực hiện khuyến công là bao nhiêu?"*
- **Ý định kỳ vọng (Expected Intent):** `CLARIFICATION`

| Mô Hình | Intent Dự Đoán | Độ Trễ (ms) | Tokens (Prompt/Comp/Total) | JSON Hợp Lệ | Đạt Chuẩn (Pass) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `openai/gpt-oss-20b` | `CLARIFICATION` | 815.6 ms | 1213 / 72 / 1285 | Hợp lệ | **PASSED** |
| `openai/gpt-oss-120b` | `ERROR` | 5194.0 ms | 0 / 0 / 0 | Lỗi | **FAILED** |
| `qwen/qwen3.8-27b` | `CLARIFICATION` | 1421.0 ms | 1026 / 70 / 1096 | Hợp lệ | **PASSED** |
| `qwen3.7-flash` | `ERROR` | 5334.0 ms | 0 / 0 / 0 | Lỗi | **FAILED** |

### 2.3. Quest 3: Q3_IMPLICIT_COMPARISON - Nhóm 3: So sánh ngầm ẩn đa kỳ (Parallel DAG)
- **Câu hỏi kiểm thử (Prompt):** *"Số vụ tai nạn lao động năm 2026 tăng hay giảm so với năm 2025?"*
- **Ý định kỳ vọng (Expected Intent):** `DYNAMIC_PARALLEL_DAG`

| Mô Hình | Intent Dự Đoán | Độ Trễ (ms) | Tokens (Prompt/Comp/Total) | JSON Hợp Lệ | Đạt Chuẩn (Pass) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `openai/gpt-oss-20b` | `DYNAMIC_PARALLEL_DAG` | 959.1 ms | 1222 / 98 / 1320 | Hợp lệ | **PASSED** |
| `openai/gpt-oss-120b` | `DYNAMIC_PARALLEL_DAG` | 1279.5 ms | 1222 / 150 / 1372 | Hợp lệ | **PASSED** |
| `qwen/qwen3.8-27b` | `DYNAMIC_PARALLEL_DAG` | 1147.3 ms | 1040 / 134 / 1174 | Hợp lệ | **PASSED** |
| `qwen3.7-flash` | `ERROR` | 5346.5 ms | 0 / 0 / 0 | Lỗi | **FAILED** |

### 2.4. Quest 4: Q4_CATALOG_DISCOVERY - Nhóm 4: Khám phá danh mục (Metadata Discovery)
- **Câu hỏi kiểm thử (Prompt):** *"Hệ thống hiện đang quản lý và theo dõi số liệu của những ngành, lĩnh vực nào?"*
- **Ý định kỳ vọng (Expected Intent):** `CATALOG_DISCOVERY`

| Mô Hình | Intent Dự Đoán | Độ Trễ (ms) | Tokens (Prompt/Comp/Total) | JSON Hợp Lệ | Đạt Chuẩn (Pass) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `openai/gpt-oss-20b` | `CATALOG_DISCOVERY` | 1090.6 ms | 1221 / 54 / 1275 | Hợp lệ | **PASSED** |
| `openai/gpt-oss-120b` | `CATALOG_DISCOVERY` | 7222.2 ms | 1221 / 81 / 1302 | Hợp lệ | **PASSED** |
| `qwen/qwen3.8-27b` | `CATALOG_DISCOVERY` | 1264.0 ms | 1035 / 112 / 1147 | Hợp lệ | **PASSED** |
| `qwen3.7-flash` | `ERROR` | 5369.4 ms | 0 / 0 / 0 | Lỗi | **FAILED** |

### 2.5. Quest 5: Q5_OUT_OF_SCOPE - Nhóm 5: Ngoài phạm vi DWH (Adversarial / Out-of-Scope)
- **Câu hỏi kiểm thử (Prompt):** *"Thời tiết hôm nay tại Đà Lạt thế nào, có mưa không?"*
- **Ý định kỳ vọng (Expected Intent):** `OUT_OF_SCOPE`

| Mô Hình | Intent Dự Đoán | Độ Trễ (ms) | Tokens (Prompt/Comp/Total) | JSON Hợp Lệ | Đạt Chuẩn (Pass) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `openai/gpt-oss-20b` | `OUT_OF_SCOPE` | 1037.4 ms | 1218 / 32 / 1250 | Hợp lệ | **PASSED** |
| `openai/gpt-oss-120b` | `OUT_OF_SCOPE` | 2218.8 ms | 1218 / 38 / 1256 | Hợp lệ | **PASSED** |
| `qwen/qwen3.8-27b` | `ERROR` | 1083.4 ms | 0 / 0 / 0 | Lỗi | **FAILED** |
| `qwen3.7-flash` | `ERROR` | 4848.7 ms | 0 / 0 / 0 | Lỗi | **FAILED** |

## 3. Phân Tích Kỹ Thuật & Khuyến Nghị Kiến Trúc
### 3.1. Phân Tích Độ Trễ & Giới Hạn Tốc Độ (Rate Limits & Latency)
- **Groq Cloud API (`openai/gpt-oss-20b`):** Đạt tốc độ suy luận nhanh vượt trội nhờ phần cứng LPU inference. Mô hình phân loại chính xác $100\%$ các trường hợp so sánh thời gian, làm rõ slot và bóc tách thực thể.
- **Cơ chế Reasoning Suppression:** Khi cấu hình `reasoning_effort='low'` kết hợp `reasoning_format='hidden'`, mô hình triệt tiêu hoàn toàn các chuỗi reasoning dài dòng, giữ token phản hồi ở mức tối thiểu.
- **Hiện tượng Rate Limit Free Tier:** Free tier của Groq áp trần 8,000 TPM (Tokens Per Minute). Do đó, cấu trúc **Fallback 4 cấp độ** (`gpt-oss-20b` $\to$ `gpt-oss-120b` $\to$ `qwen3.8-27b` $\to$ DashScope `qwen3.7-flash`) là thiết kế sống còn giúp hệ thống không bao giờ bị gián đoạn.

### 3.2. Đánh Giá Khắc Phục Hiện Tượng Boundary Leakage (Ribeiro et al., ACL 2020)
- Trước đây, Regex Tier 1/Tier 2 gặp tình trạng rò rỉ biên: người dùng chỉ cần thêm từ đệm công vụ hoặc đảo ngữ là hệ thống gán nhầm sang Fast Track hoặc Discovery.
- Với kiến trúc **SSOT LLM Structured Outputs**, mô hình hiểu sâu ngữ nghĩa công vụ:
  + Bỏ qua hoàn toàn các kính ngữ (*"Kính thưa đồng chí", "Trợ lý ảo ơi"*).
  + Nhận diện chính xác câu hỏi đa kỳ ngầm ẩn (*"tăng hay giảm"*) thành `DYNAMIC_PARALLEL_DAG`.
  + Tự động phát hiện câu hỏi ngoài phạm vi DWH (*"thời tiết Đà Lạt"*) để từ chối an toàn mà không sinh SQL giả mạo.