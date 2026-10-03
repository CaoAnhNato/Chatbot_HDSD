# 🏛️ KIẾN TRÚC QUYẾT ĐỊNH (ADR-001): AGENT TỰ HÀNH ĐIỀU PHỐI TOÀN TRÌNH VỚI LANGGRAPH

> **Mã định danh:** `ADR-001`  
> **Trạng thái:** `ACCEPTED` (Đã thông qua thẩm định kỹ thuật qua `/grill-with-docs`)  
> **Ngày phê duyệt:** 2026-10-01  
> **Người đề xuất:** Antigravity AI Assistant & Project Lead  
> **Tài liệu liên quan:** [implementation_plan.md](file:///C:/Users/Admin/.gemini/antigravity/brain/0df7a20d-bb31-4d0c-bf72-febcf1006960/implementation_plan.md), [update.md](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/docs/update.md), [bug_chatbot.md](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/IPGov_Chatbot/docs/bug_chatbot.md)

---

## 1. Ngữ Cảnh Kỹ Thuật (Context)

Hệ thống `IPGov_Chatbot` chuyển đổi hạ tầng kết nối sang kho dữ liệu tập trung của công ty tại địa chỉ `104.248.155.6:5432/vna_wom_dev`. Qua quá trình kiểm toán thực tế:
1. Kho dữ liệu bao gồm 8+ bảng nghiệp vụ cốt lõi: `fact_report_criteria`, `criteria`, `report`, `collection_form`, `user_mission`, `"user"`, `office_mission`, `mission`, `office`.
2. Bảng hạ tầng kỹ thuật `pipeline_logs` không thuộc phạm vi phục vụ hỏi đáp của người dùng cuối.
3. Các cơ chế lọc chuỗi cứng (Regex, cắt 2 từ cuối `name_parts[-2:]`, heuristic đếm dòng `2 <= len <= 50 -> TOP_K`) phát sinh lỗi nghiêm trọng (`BUG-001`, `BUG-002`) gây lệch lạc ngữ nghĩa công vụ.
4. Người dùng yêu cầu hệ thống có năng lực tự chủ cao: Tự khám phá kho dữ liệu, tự động làm rõ ý định khi thiếu thông tin, minh bạch hóa câu lệnh truy vấn bằng khối thu gọn `<details>`, và hiển thị trạng thái xử lý theo thời gian thực (Live Loading States).

---

## 2. Quyết Định Thiết Kế (Architectural Decisions)

Hệ thống thống nhất thực hiện 7 quyết định kiến trúc then chốt:

### Quyết định 1: Nhạc Trưởng Toàn Trình Bằng LangGraph (End-to-End StateGraph)
* Áp dụng nguyên tắc **"Đứng trên vai người khổng lồ"**: Tận dụng thư viện `langgraph 1.2.11` và `langchain 1.3.16` có sẵn trong môi trường ảo.
* Xây dựng một `StateGraph` duy nhất tích hợp liền mạch toàn bộ chu trình xử lý:
  `Parse & Inherit Context` $\to$ `Active Clarification Check` $\to$ `Explore Warehouse Schema` $\to$ `Dynamic SQL Generation` $\to$ `AST Security Guardrail` $\to$ `DWH Execution` $\to$ `Response Synthesis`.
* Không chia nhỏ rời rạc qua các đường ống tuần tự cũ để tối ưu hóa độ trễ (< 50ms) và dễ dàng kiểm soát vòng lặp tự sửa sai (Self-correction Loop).

### Quyết định 2: Bộ Công Cụ SQL Động Kèm AST Guardrail (Dynamic SQL Tooling)
* Agent được trang bị 2 tool cốt lõi:
  1. `describe_tables(table_names: List[str])`: Khám phá chi tiết schema, tên cột, kiểu dữ liệu từ DuckDB Catalog.
  2. `execute_safe_sql(query: str)`: Tiếp nhận câu lệnh SQL do Agent viết ra, tự động đưa qua chốt chặn AST Guardrail (SQLGlot) để kiểm tra an toàn (chặn DROP, DELETE, ALTER, chèn tenant_code tự động) rồi thực thi trên PostgreSQL.
* Đảm bảo tính linh hoạt tối đa, trả lời được mọi câu hỏi tra cứu phức tạp hay liên kết đa bảng trên toàn bộ 8 bảng CSDL.

### Quyết định 3: Lưu Trữ Bộ Nhớ Ngữ Cảnh Bền Vững Với SQLite (SqliteSaver)
* Sử dụng `SqliteSaver` lưu trữ checkpoint của phiên chat vào tệp cục bộ `data/agent_memory.db`.
* Không phụ thuộc dịch vụ ngoài (Redis/Docker), đảm bảo lịch sử hội thoại và ngữ cảnh không bị mất khi khởi động lại server.

### Quyết định 4: Kế Thừa Ngữ Cảnh Thông Minh Chống Hỏi Lặp (Context Inheritance)
* Agent **CHỈ** hỏi làm rõ khi thông tin bắt buộc bị thiếu trong **CẢ** câu hỏi hiện tại **LẪN** lịch sử phiên chat trong `Session Working Memory`.
* Nếu người dùng ở lượt trước đã xác định ngữ cảnh (`tenant_code = '68'`, `year_code = '2026'`), câu hỏi tiếp nối sẽ tự động tái sử dụng các tham số này mà không hỏi lại.

### Quyết định 5: Bậc Thang Mô Hình Theo Tác Vụ (Task-based Model Cascade)
* Không đặt tên API Key theo tên model. Đặt tên theo nhiệm vụ:
  - `AGENT_DECISION_LLM_API_KEY`: Điều phối lập luận và gọi công cụ.
  - `SQL_GENERATION_LLM_API_KEY`: Sinh câu lệnh SQL.
  - `RESPONSE_SYNTHESIS_LLM_API_KEY`: Tổng hợp câu trả lời tự nhiên.
* Bậc thang ưu tiên: `gemini-2.5-flash-lite` (Ưu tiên 1) $\to$ `gemini-3.5-flash-lite` (Fallback 1) $\to$ `deepseek/deepseek-v4.1-flash` (Fallback 2).

### Quyết định 6: Minh Bạch Hóa Câu Lệnh Truy Vấn (Transparent Collapsible SQL)
* Mọi phản hồi có truy vấn dữ liệu thành công đều tự động đính kèm khối thu gọn:
  ```html
  <details>
  <summary>🔍 Xem câu lệnh truy vấn (SQL Query)</summary>

  ```sql
  SELECT ...
  ```
  </details>
  ```

### Quyết định 7: Trạng Thái Xử Lý Thời Gian Thực (Live Loading States)
* Phát sự kiện tiến trình qua SSE Streaming (`THINKING` $\to$ `EXPLORING_WAREHOUSE` $\to$ `GENERATING_SQL` $\to$ `EXECUTING_DWH` $\to$ `SYNTHESIZING`) giúp giao diện Test Bench UI cập nhật sinh động cho người dùng.

---

## 3. Hệ Quả Kỹ Thuật (Consequences)

### Tích cực:
* **Tối giản sửa đổi mã nguồn:** Tận dụng 100% các package chuẩn có sẵn trong môi trường ảo, không cần cài thêm thư viện lạ.
* **Bền bỉ & Tin cậy:** Loại bỏ triệt để các bẫy regex/heuristic dễ vỡ, thay thế bằng LLM Agent có AST Guardrail bảo vệ.
* **Trải nghiệm người dùng vượt trội:** Kế thừa ngữ cảnh thông minh, quan sát được tiến trình loading thời gian thực và kiểm tra được câu lệnh SQL thực tế chạy xuống kho.

### Hạn chế & Giảm thiểu:
* **Chi phí gọi LLM:** Do chuyển đổi từ rule tĩnh sang LLM Decision Agent, token LLM sẽ tăng nhẹ.
  - *Giải pháp giảm thiểu:* Sử dụng mô hình chi phí siêu rẻ và tốc độ cao `gemini-2.5-flash-lite` làm mặc định, kết hợp cache schema trong DuckDB RAM để tối thiểu hóa token đầu vào.
