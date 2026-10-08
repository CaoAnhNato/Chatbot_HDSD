# 🚀 HƯỚNG DẪN KHỞI CHẠY VÀ VẬN HÀNH HỆ THỐNG HDSD CHATBOT AI ASSISTANT (V1 & V2)

> **Tài liệu Hướng dẫn Khởi chạy & Vận hành (Run Guide)**
> *Dành riêng cho việc khởi động nhanh toàn bộ hệ thống hỗ trợ cả 2 phân hệ: Phường/Xã (v2) và Doanh nghiệp (v1).*

---

## ⚡ 1. Khởi Chạy Nhanh Toàn Bộ Hệ Thống (Quick Start)

Mở **2 cửa sổ Terminal** riêng biệt tại thư mục gốc của dự án (`Chatbot_Project`):

### 🟢 Terminal 1: Khởi chạy Backend Server (FastAPI Engine)

```powershell
# Kích hoạt môi trường ảo (nếu chưa kích hoạt)
.\.venv\Scripts\Activate.ps1

# Khởi chạy Backend FastAPI với cờ --app-dir backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

* **Swagger API Docs:** `http://127.0.0.1:8000/docs`
* **API Health Check:** `http://127.0.0.1:8000/api/v1/health`
* **Cơ chế tự động:** Hệ thống tự động kích hoạt **Warm-up** nạp trước cả 2 Vector Collection (`hdsd_phuong_chunks` & `hdsd_chunks`), bộ từ khóa tìm kiếm, BM25 tokenizer và kết nối HTTP/2 Persistent Pool tới mô hình Qwen LLM.

---

### 🟢 Terminal 2: Khởi chạy Frontend Web UI (Next.js 14)

```powershell
# Di chuyển vào thư mục frontend và chạy Next.js dev server
cd frontend
npm run dev
```

* **Địa chỉ truy cập Web Chat:** `http://localhost:3000`
* **Giao diện đa phân hệ (Tab Switcher):**
  * `[🏛️ Phường / Xã]`: Tra cứu 10 phân hệ nghiệp vụ Phường/Xã, trích xuất ảnh giao diện trực quan, Card vàng liên hệ hỗ trợ kỹ thuật (`028 3535 2524`).
  * `[🏢 Doanh nghiệp]`: Tra cứu quy trình Doanh nghiệp kèm Video YouTube nhúng trực tiếp và ảnh minh họa.

---

## 🛠️ 2. Các Lệnh Vận Hành & Nạp Dữ Liệu (Data Ingestion)

### 2.1. Nạp Dữ Liệu Phân Hệ Phường/Xã (Vector DB v2 - `hdsd_phuong_chunks`)

```powershell
# Nạp trực tiếp tài liệu HDSD Phường/Xã
.\.venv\Scripts\python.exe backend/scripts/ingest_phuong_docs.py

# Hoặc dùng script tổng với cờ --mode phuong
.\.venv\Scripts\python.exe backend/scripts/ingest_docs.py --mode phuong
```

### 2.2. Nạp Dữ Liệu Phân Hệ Doanh Nghiệp (Vector DB v1 - `hdsd_chunks`)

```powershell
.\.venv\Scripts\python.exe backend/scripts/ingest_docs.py --mode dn
```

### 2.3. Nạp Toàn Bộ Cả 2 Phân Hệ Cùng Lúc

```powershell
.\.venv\Scripts\python.exe backend/scripts/ingest_docs.py --mode all
```

---

## 🧪 3. Kiểm Thử Tự Động (Automated Testing)

### 3.1. Kiểm Thử Toàn Diện Phân Hệ Phường/Xã (v2)

Kiểm tra 10 phân hệ nghiệp vụ, độ nhạy từ khóa tìm kiếm, Card vàng hotline hỗ trợ, Factoid Rejection:

```powershell
.\.venv\Scripts\python.exe backend/tests/test_phuong_rag.py
```

### 3.2. Chạy Bộ Đánh Giá & Benchmark RAGAS Cho Doanh Nghiệp (v1)

```powershell
.\.venv\Scripts\python.exe backend/tests/run_ragas_evaluation.py
```

* Báo cáo đánh giá chi tiết được lưu tự động tại: [`Bussiness_Rules/docs/RAG_EVALUATION_REPORT.md`](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/Bussiness_Rules/docs/RAG_EVALUATION_REPORT.md).

---

## 📊 4. Giám Sát & Nhật Ký Hệ Thống (Logs)

Toàn bộ phiên hỏi đáp và cảnh báo bảo mật được ghi nhận thời gian thực tại:

* **File Nhật ký tương tác (Audit Log):** `backend/data/logs/chat_audit.jsonl`
* **File Nhật ký sự cố & lỗi (Error Log):** `backend/data/logs/chat_errors.jsonl`
