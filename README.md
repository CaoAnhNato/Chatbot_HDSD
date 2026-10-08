# Multimodal HDSD Chatbot Assistant 🤖📚

> **Trợ lý AI Đa phương tiện Hướng dẫn Sử dụng Hệ thống Quản lý Điều hành & Báo cáo An toàn Lao động**  
> Kiến trúc **Multi-Role RAG**, kết hợp **Dense Vietnamese Embedding** và **Hybrid Extractive-Generative Retrieval**, tích hợp **Qwen-3.7-Flash API**.

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14.2%20App%20Router-black?logo=next.js)](https://nextjs.org/)
[![Qwen](https://img.shields.io/badge/AI%20Engine-Qwen--3.7--Flash-orange)](https://help.aliyun.com/document_detail/271257.html)
[![ChromaDB](https://img.shields.io/badge/Vector%20Store-ChromaDB%20%2F%20Qdrant-red)](https://www.trychroma.com/)
[![Deployment](https://img.shields.io/badge/Live%20Deploy-Vercel%20%26%20Railway-brightgreen)](https://chatbot-hdsd.vercel.app)

---

## 🌐 Hệ Thống Trực Tuyến (Live Demo & Endpoints)

Dự án được triển khai trên môi trường Production Cloud:

| Phân hệ / Dịch vụ | Nền tảng | Đường dẫn truy cập | Chức năng |
| :--- | :---: | :--- | :--- |
| **Giao diện Chat Web (Frontend)** | **Vercel** | [https://chatbot-hdsd.vercel.app](https://chatbot-hdsd.vercel.app) | Ứng dụng Next.js 14, hiển thị luồng SSE streaming, xem ảnh UI qua Lightbox và nhúng video YouTube. |
| **Máy chủ API AI (Backend)** | **Railway** | [https://chatbothdsd-production.up.railway.app](https://chatbothdsd-production.up.railway.app) | FastAPI Async Server, xử lý Hybrid RAG, Ingestion pipeline và kết nối Qwen LLM. |
| **Tài liệu API (Swagger UI)** | **Railway** | [https://chatbothdsd-production.up.railway.app/docs](https://chatbothdsd-production.up.railway.app/docs) | Giao diện Swagger / OpenAPI để kiểm thử trực tiếp các endpoints `/chat`, `/health`, `/ingest`. |
| **Embedding Microservice** | **Hugging Face** | [https://nato1306-vietnamese-embedding-api.hf.space](https://nato1306-vietnamese-embedding-api.hf.space) | Dịch vụ vector embedding tiếng Việt (`AITeamVN/Vietnamese_Embedding_v2`). |

---

## ⚙️ Các Phân Hệ & Cơ Chế Xử Lý Cốt Lõi

### 1. Phản Hồi Đa Phương Tiện (Multimodal Response)
- Hướng dẫn các bước thao tác định dạng Markdown (`**Bước 1:**`, `**Bước 2:**`).
- Đính kèm ảnh giao diện UI tương ứng theo vị trí thẻ `[IMAGE_N]` (hỗ trợ xem chi tiết qua Lightbox).
- Nhúng video hướng dẫn YouTube phát đúng mốc thời gian (timestamp) của thao tác.

### 2. Phân Tách Không Gian Tri Thức Theo Vai Trò (Multi-Role RAG)
- Phân hệ **Doanh nghiệp (`DN`)**: Tra cứu quy trình đăng ký, nộp báo cáo định kỳ TNLĐ, báo cáo ATVSLĐ (Collection: `hdsd_chunks`).
- Phân hệ **Cán bộ Phường (`Phường`)**: Tra cứu nghiệp vụ quản lý doanh nghiệp, tiếp nhận và thẩm định báo cáo (Collection: `hdsd_phuong_chunks`).
- Bộ định tuyến `Dynamic Catalog Router` tự động phân loại đối tượng để truy xuất đúng collection.

### 3. Cơ Chế Truy Xuất Kết Hợp (Hybrid Retrieval)
- Kết hợp tìm kiếm ngữ nghĩa Dense Vector (`AITeamVN/Vietnamese_Embedding_v2` 1024 chiều) và tìm kiếm từ khóa Sparse BM25.
- Áp dụng công thức Reciprocal Rank Fusion (RRF) kết hợp Intent Action Boost để xếp hạng chunk thuộc phân hệ nghiệp vụ mục tiêu lên vị trí ưu tiên.

### 4. Điều Phối Phản Hồi Theo Nhóm Câu Hỏi (Tri-Modal Dispatcher)
- **Mode A (Procedural Extractive):** Đối với câu hỏi quy trình thao tác, hệ thống trích xuất trực tiếp nội dung Rich Markdown từ chunk tài liệu nguồn nhằm giữ nguyên văn bản gốc và giảm thời gian chờ.
- **Mode B (Targeted Generative QA):** Đối với câu hỏi ngách (hỏi về điều kiện, thời hạn, trách nhiệm), gửi ngữ cảnh liên quan tới mô hình `qwen3.7-flash` để tổng hợp câu trả lời ngắn gọn trong 1–3 câu.
- **Mode C (Contact Support Card):** Tự động xuất trình thẻ thông tin Hotline, Zalo khi phát hiện người dùng phản ánh sự cố kỹ thuật.

### 5. Khởi Tạo Tài Nguyên Trước (FastAPI Lifespan)
- Nạp sẵn Vector Embedding model và chỉ mục BM25 vào bộ nhớ khi server khởi động, giúp câu hỏi đầu tiên không bị trễ thời gian tải thư viện.

### 6. Kiểm Soát Đầu Vào (Security Guardrails)
- Bộ lọc regex kiểm tra và từ chối các câu lệnh vi phạm (Prompt Injection, SQL Injection) trước khi xử lý nghiệp vụ.

---

## 🏗️ Cấu Trúc Thư Mục Dự Án

```
Chatbot_Project/
├── Bussiness_Rules/                       # Tài liệu nghiệp vụ & Đặc tả kiến trúc
│   └── docs/                              # Toàn bộ hệ thống tài liệu kỹ thuật
│       ├── PROJECT_CANVAS_ARCHITECTURE.md # 📑 Tài liệu đặc tả kiến trúc kỹ thuật
│       ├── SYSTEM_RUN_GUIDE.md            # 🚀 Hướng dẫn cài đặt & vận hành hệ thống
│       ├── RAG_EVALUATION_REPORT.md       # 📊 Báo cáo đánh giá RAGAS
│       ├── modules/                       # 📂 Bộ 7 đặc tả kỹ thuật chi tiết
│       │   ├── MODULE_01_INGESTION_PARSER.md
│       │   ├── MODULE_02_VECTORSTORE_RETRIEVAL.md
│       │   ├── MODULE_03_SECURITY_GUARDRAILS.md
│       │   ├── MODULE_04_INTENT_CLASSIFICATION.md
│       │   ├── MODULE_05_STRATEGY_ROUTER.md
│       │   ├── MODULE_06_RAG_SYNTHESIS_LLM.md
│       │   └── MODULE_07_FRONTEND_PRESENTATION.md
│       └── markdown/                      # Nội dung HDSD đã chuyển đổi dạng Markdown
├── backend/                               # Máy chủ Python FastAPI & AI Engine
│   ├── app/
│   │   ├── api/v1/                        # REST API Endpoints (/chat, /ingest, /health)
│   │   ├── core/                          # Config, Guardrails, Logger, Audit Logger
│   │   ├── models/                        # Pydantic Data Models (ChatRequest, Response)
│   │   ├── services/                      # RAG Service, Qwen Service, Intent Service
│   │   ├── ingestion/                     # Docx OpenXML Parser, Media Extractor, Chunker
│   │   ├── vectorstore/                   # ChromaDB, Qdrant & Hybrid Retriever
│   │   └── utils/                         # Prompts, Fallback Contact Card
│   ├── scripts/                           # Script nạp dữ liệu (Ingestion scripts)
│   │   ├── ingest_docs.py                 # Nạp dữ liệu Doanh nghiệp vào ChromaDB
│   │   ├── ingest_phuong_docs.py          # Nạp dữ liệu Cán bộ Phường vào ChromaDB
│   │   └── ingest_all_to_supabase_and_chroma.py
│   ├── tests/                             # Bộ kịch bản kiểm thử tự động & Benchmark
│   │   ├── run_benchmark.py               # Benchmark bộ 18 test cases
│   │   ├── run_ragas_evaluation.py        # Đo lường các chỉ số RAGAS
│   │   ├── test_phuong_rag.py             # Kiểm thử phân hệ Cán bộ Phường
│   │   └── test_conversational_cqr.py     # Kiểm thử Contextual Query Rewriting
│   ├── data/                              # Dữ liệu ảnh bóc tách (extracted_images) & logs
│   ├── chroma_data/                       # Cơ sở dữ liệu Vector ChromaDB cục bộ
│   ├── Dockerfile                         # Đóng gói Docker Backend
│   └── requirements.txt                   # Danh sách thư viện Python
├── frontend/                              # Giao diện người dùng Next.js 14 Web App
│   ├── src/
│   │   ├── app/                           # App Router (page.tsx, layout.tsx)
│   │   ├── components/chat/               # Chat UI, Lightbox, YouTubeEmbed, ActionChips
│   │   ├── hooks/                         # useChat hook xử lý SSE streaming
│   │   ├── lib/                           # API Client & SSE Stream Parser
│   │   └── types/                         # TypeScript interfaces
│   ├── Dockerfile                         # Đóng gói Docker Frontend
│   └── package.json                       # Thư viện Frontend
├── docker-compose.yml                     # Khởi chạy toàn bộ hệ thống bằng Docker
└── README.md                              # Tài liệu tổng quan dự án (Tệp này)
```

---

## 💻 Bảng Tổng Hợp Tech Stack

| Phân tầng | Công nghệ | Vai trò trong hệ thống |
| :--- | :--- | :--- |
| **Frontend UI** | Next.js 14, React 18, TailwindCSS, Lucide Icons | Giao diện Chatbot hiển thị luồng SSE token thời gian thực, Image Lightbox, nhúng YouTube player. |
| **Backend Core** | Python 3.11+, FastAPI, Uvicorn, AsyncIO | Máy chủ API RESTful bất đồng bộ, điều phối luồng RAG và SSE Streaming. |
| **AI LLM Engine** | **Qwen-3.7-Flash API** (Alibaba Cloud DashScope) | Xử lý ngôn ngữ tiếng Việt và tổng hợp câu trả lời cho các câu hỏi ngách. |
| **Embedding Engine** | `AITeamVN/Vietnamese_Embedding_v2` (1024 dim) | Vector Embedding tiếng Việt; hỗ trợ cả on-premise ONNX và HF Spaces Microservice. |
| **Vector Database** | **ChromaDB** & **Qdrant** | Lưu trữ và tìm kiếm vector Cosine Similarity phân tách theo role collection. |
| **Sparse Index** | **Rank-BM25** (`rank_bm25`) | Tìm kiếm từ khóa theo tần suất từ và nghịch đảo văn bản. |
| **Data Ingestion** | `python-docx` (XML Run-level Parser) | Bóc tách cấu trúc tài liệu Word, bảo toàn định dạng in đậm, in nghiêng và vị trí ảnh UI. |
| **Cloud Persistence** | **Supabase** (PostgreSQL / pgvector) | Lưu trữ phiên hội thoại, lịch sử tin nhắn và persistence trên đám mây. |
| **Hosting & CI/CD** | **Vercel** (Frontend) & **Railway** (Backend) | Hạ tầng đám mây phân tán, tự động build và deploy theo Git commit. |

---

## 📊 Kết Quả Đo Lường Thực Nghiệm & Đánh Giá RAGAS

Hệ thống được kiểm thử tự động trên bộ **18 kịch bản truy vấn thực tế**:

### 1. Bảng So Sánh Hiệu Năng Thực Nghiệm

| Chỉ số kỹ thuật | RAG Truyền thống (LLM Generation) | Cơ chế Hybrid (Extractive + Generative) | Ghi chú kỹ thuật |
| :--- | :---: | :---: | :--- |
| **Thời gian nhận token đầu (TTFT)** | ~10.000 ms - 15.000 ms | **~210 ms** | Rút ngắn nhờ luồng trích xuất trực tiếp |
| **Tổng thời gian phản hồi** | ~12.000 ms - 18.000 ms | **~725 ms** | Giảm thiểu việc sinh lại văn bản dài của LLM |
| **Độ chính xác Top-1 (Precision@1)** | 66.7% | **100.0%** | Kết hợp Dense + Sparse BM25 và Action Boost |
| **Định vị ảnh UI theo bước** | Dễ bị lệch do xử lý ngẫu nhiên | **Khớp đúng bước** | Cơ chế gán vị trí cố định `[IMAGE_N]` |
| **Bảo toàn định dạng văn bản gốc** | Thường bị mất khi LLM tóm tắt | **Giữ nguyên 100%** | Trích xuất trực tiếp từ cấu trúc OpenXML |

### 2. Điểm Số Theo Chuẩn RAGAS
- **Answer Relevancy:** **$100.0\%$** (Câu trả lời bám sát câu hỏi của người dùng).
- **Context Recall:** **$67.6\%$** (Bao phủ các bước thực hiện và lưu ý nghiệp vụ).
- **Faithfulness:** **$63.1\%$** (Đạt 100% trên nhóm câu hỏi quy trình nhờ cơ chế trích xuất nguyên bản).

---

## 🚀 Hướng Dẫn Cài Đặt & Khởi Chạy Máy Cục Bộ (Local Setup Guide)

### Bước 1: Clone Kho Mã Nguồn & Cấu Hình Môi Trường

```bash
# 1. Clone repository từ GitHub
git clone https://github.com/CaoAnhNato/Chatbot_HDSD.git
cd Chatbot_HDSD

# 2. Cấu hình biến môi trường cho Backend
cp backend/.env.example backend/.env
# Mở backend/.env và điền DASHSCOPE_API_KEY hoặc QWEN_API_KEY

# 3. Cấu hình biến môi trường cho Frontend
cp frontend/.env.example frontend/.env.local
```

### Bước 2: Khởi Chạy Backend (FastAPI Server)

```bash
# Kích hoạt môi trường ảo Python (Windows PowerShell)
.\.venv\Scripts\Activate.ps1
# Hoặc trên Linux/macOS: source .venv/bin/activate

# Cài đặt thư viện (khuyến nghị dùng uv để cài đặt nhanh)
uv pip install -r backend/requirements.txt
# Hoặc dùng pip:
# pip install -r backend/requirements.txt

# (Tùy chọn) Chạy nạp dữ liệu vào Vector DB nếu cần tạo mới
python backend/scripts/ingest_docs.py

# Khởi chạy Backend server tại port 8000
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
```

*Backend sẵn sàng tại: `http://localhost:8000` (Swagger Docs tại `http://localhost:8000/docs`).*

### Bước 3: Khởi Chạy Frontend (Next.js Web App)

Mở một cửa sổ Terminal mới:

```bash
cd frontend

# Cài đặt các gói phụ thuộc Node.js
npm install

# Khởi chạy máy chủ phát triển
npm run dev
```

*Giao diện Chatbot sẵn sàng tại: `http://localhost:3000`.*

### Bước 4: Chạy Kịch Bản Kiểm Thử Tự Động (Benchmark Suite)

Để kiểm chứng 18 kịch bản nghiệp vụ và đo lường độ trễ:

```bash
python backend/tests/run_benchmark.py
```

---

## 📑 Tài Liệu Kỹ Thuật Tham Chiếu

1. 📑 **Đặc tả Kiến trúc Kỹ thuật Hệ thống:** [`Bussiness_Rules/docs/PROJECT_CANVAS_ARCHITECTURE.md`](./Bussiness_Rules/docs/PROJECT_CANVAS_ARCHITECTURE.md)
2. 🚀 **Hướng dẫn Vận hành & Cài đặt:** [`Bussiness_Rules/docs/SYSTEM_RUN_GUIDE.md`](./Bussiness_Rules/docs/SYSTEM_RUN_GUIDE.md)
3. 📊 **Báo cáo Đánh giá RAGAS:** [`Bussiness_Rules/docs/RAG_EVALUATION_REPORT.md`](./Bussiness_Rules/docs/RAG_EVALUATION_REPORT.md)
4. 📂 **Bộ 7 Tài liệu Đặc tả Từng Module:** [`Bussiness_Rules/docs/modules/`](./Bussiness_Rules/docs/modules/)

---
*Multimodal HDSD Chatbot Assistant.*
#   C h a t b o t - H D S D - W O M  
 