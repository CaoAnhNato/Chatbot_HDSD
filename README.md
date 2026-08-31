# Multimodal HDSD Chatbot Assistant 🤖📚

> Trợ lý AI Đa phương tiện Hướng dẫn Sử dụng Hệ thống Quản lý Điều hành Cấp Xã dựa trên **Qwen-3.7-Flash API** & **Multimodal RAG**.

---

## 🌟 Tính Năng Nổi Bật

- **Multimodal Response:** Hướng dẫn từng bước (Text) kèm **Ảnh chụp màn hình UI** và **Link Video YouTube (Timestamp cụ thể)**.
- **Tự Động Warm-Up (FastAPI Lifespan):** Khởi động sẵn Vector Embedding, BM25 Index và HTTP/2 Session Pooling để đạt TTFT < 1s ngay từ câu hỏi đầu tiên.
- **Qwen-3.7-Flash AI Engine:** Tận dụng năng lực hiểu tiếng Việt sâu sắc và suy luận chính xác từ ngữ cảnh tài liệu HDSD.
- **Hybrid Retrieval (Dense + Sparse BM25 + RRF):** Tối ưu hóa việc tìm đúng phân đoạn và ảnh/video liên quan.
- **Edge Cases & Graceful Degradation:**
  - Tự động gợi ý làm rõ câu hỏi mơ hồ (Quick Action Chips).
  - Xuất card **Thông tin liên hệ hỗ trợ kỹ thuật (Hotline/Zalo)** khi phát hiện sự cố phần mềm.
  - Bộ lọc **Security Guardrails** chống Prompt Injection & SQL Injection.
- **Hiển thị trực quan:** Giao diện Next.js 14 với chế độ phóng to ảnh (Lightbox) và phát video YouTube trực tiếp.

> 📖 **Xem hướng dẫn chi tiết:** [Bussiness_Rules/docs/SYSTEM_RUN_GUIDE.md](file:///c:/Users/Admin/HUIT - Học Tập/Năm 4/Chatbot_Project/Bussiness_Rules/docs/SYSTEM_RUN_GUIDE.md)

---

## 🏗️ Cấu Trúc Dự Án

```
Chatbot_Project/
├── .venv/                         # Python Virtual Environment
├── docs/                          # Tài liệu kiến trúc & thiết kế hệ thống
│   └── PROJECT_CANVAS_ARCHITECTURE.md # Toàn bộ đặc tả kiến trúc hệ thống
├── docker-compose.yml             # Khởi chạy toàn bộ hệ thống bằng Docker
├── references/                    # Thư viện tham chiếu (multi-modal-RAG)
├── Bussiness_Rules/               # Tài liệu nghiệp vụ & file Word HDSD gốc
│   └── docs/_AI_HDSD_ATLD (DN)... # File hướng dẫn sử dụng nguồn
├── backend/                       # Python FastAPI Backend & RAG Engine
│   ├── app/
│   │   ├── api/v1/                # REST API Endpoints (/chat, /ingest, /health)
│   │   ├── core/                  # Config, Guardrails, Logger, Audit Logger
│   │   ├── models/                # Pydantic Data Models
│   │   ├── services/              # Qwen Service, RAG Engine, Intent Classifier
│   │   ├── ingestion/             # Docx Parser, Media Extractor, Chunker
│   │   ├── vectorstore/           # Qdrant & ChromaDB Managers
│   │   └── utils/                 # Prompts, Fallback Contact Info
│   ├── data/                      # Lưu trữ tài liệu, chunks, logs và ảnh UI
│   │   ├── logs/                  # File log chat_audit.jsonl & chat_errors.jsonl
│   │   └── extracted_images/      # Ảnh chụp màn hình bóc tách từ Docx
│   └── requirements.txt           # Thư viện Backend
└── frontend/                      # Next.js 14 App Router Web App
    ├── src/
    │   ├── app/                   # Next.js Pages & Layouts
    │   ├── components/chat/       # Chat UI, MediaViewer, YouTubeEmbed, ContactCard
    │   ├── hooks/                 # Chat Hooks
    │   └── lib/                   # API Client & Utils
    └── package.json               # Frontend Dependencies
```

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Nhanh

### 1. Kích hoạt Môi trường ảo Python (Backend)

```bash
# Kích hoạt venv (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Cài đặt thư viện backend
cd backend
pip install -r requirements.txt

# Tạo file cấu hình môi trường
cp .env.example .env
# Điền QWEN_API_KEY / DASHSCOPE_API_KEY vào .env

# Chạy Backend server
uvicorn app.main:app --reload --port 8000
```

### 2. Chạy Giao diện Người dùng (Frontend)

```bash
cd frontend
npm install
cp .env.example .env.local

# Chạy ứng dụng Next.js
npm run dev
# Truy cập tại: http://localhost:3000
```

---

## 📑 Tài liệu tham khảo kiến trúc
Xem chi tiết tại: [`docs/PROJECT_CANVAS_ARCHITECTURE.md`](./docs/PROJECT_CANVAS_ARCHITECTURE.md)
