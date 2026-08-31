# 🚀 BẢNG HƯỚNG DẪN THIẾT KẾ & TRIỂN KHAI TOÀN DIỆN HỆ THỐNG HDSD CHATBOT
### (Vercel + Railway + Supabase PostgreSQL/pgvector + HuggingFace Space)

> **Mục tiêu:** Cung cấp tài liệu thiết kế kiến trúc phân tán (Decoupled Cloud Architecture) và lộ trình triển khai từng bước chi tiết giúp hệ thống sẵn sàng phục vụ nhiều người dùng thử nghiệm đồng thời, tự động lưu trữ lịch sử hội thoại trên Cloud, và tự động đồng bộ (CI/CD) mỗi khi push code lên Git.
>
> 📌 **Thông tin cấu hình trọng tâm:**
> * **Embedding Model:** `AITeamVN/Vietnamese_Embedding_v2` (567.8M params, xlm-roberta base, embedding dimension 1024, chuyên biệt hóa cho tiếng Việt).
> * **GitHub Repository:** [`https://github.com/CaoAnhNato/Chatbot_HDSD.git`](https://github.com/CaoAnhNato/Chatbot_HDSD.git)
> * **HuggingFace Space Automation Skill:** `curl https://huggingface.co/new-space/agents.md and build me a Space with a demo for <a model, paper, or local folder>`

---

## 📑 MỤC LỤC
1. [Phân Tích Kiến Trúc & Đề Xuất Vector Database](#1-phân-tích-kiến-trúc--đề-xuất-vector-database)
2. [Sơ Đồ Luồng Dữ Liệu Toàn Hệ Thống (System Dataflow)](#2-sơ-đồ-luồng-dữ-liệu-toàn-hệ-thống-system-dataflow)
3. [Thiết Kế Cơ Sở Dữ Liệu Supabase (Schema & Migrations)](#3-thiết-kế-cơ-sở-dữ-liệu-supabase-schema--migrations)
4. [Thiết Kế Model Microservice Trên HuggingFace Space](#4-thiết-kế-model-microservice-trên-huggingface-space)
5. [Hướng Dẫn Triển Khai Từng Bước (Step-by-Step Deployment)](#5-hướng-dẫn-triển-khai-từng-bước-step-by-step-deployment)
6. [Cơ Chế CI/CD & Tự Động Đồng Bộ Khi Push Code](#6-cơ-chế-cicd--tự-động-đồng-bộ-khi-push-code)
7. [Bảng Ma Trận Biến Môi Trường (Environment Variables Matrix)](#7-bảng-ma-trận-biến-môi-trường-environment-variables-matrix)
8. [Checklist Vận Hành & Xử Lý Sự Cố (Troubleshooting & Security)](#8-checklist-vận-hành--xử-lý-sự-cố-troubleshooting--security)

---

## 1. Phân Tích Kiến Trúc & Đề Xuất Vector Database

### 1.1. Phân tích & Đánh giá Stack công nghệ đã chọn:
* **Frontend (Vercel):** Lựa chọn chuẩn mực cho Next.js 14 App Router. Tận dụng mạng lưới Edge CDN toàn cầu, zero-downtime deployment, tích hợp sẵn HTTPS và preview link cho từng pull request.
* **Backend (Railway.app):** Cung cấp môi trường Docker container chạy 24/7. Hỗ trợ toàn diện cho cơ chế `lifespan warm-up` của FastAPI, streaming response (SSE) không bị ngắt quãng, và quản lý persistent volume nếu cần.
* **Cloud Database (Supabase PostgreSQL):** Database quan hệ chuẩn công nghiệp, hỗ trợ pooling kết nối (PgBouncer), API REST/GraphQL tức thì, và hệ thống phân quyền Row-Level Security (RLS).
* **Model Server (HuggingFace Space):** Chạy microservice API độc lập cho Embedding Model `AITeamVN/Vietnamese_Embedding_v2` (tương thích SentenceTransformers, hỗ trợ đa dạng task sentence-similarity tiếng Việt).
* **LLM Engine:** Alibaba Cloud DashScope `Qwen-3.7-Flash` API.

---

### 1.2. Phân tích & Đề xuất Lựa chọn Vector Database

Dưới góc nhìn tối ưu chi phí và độ phức tạp hệ thống:

| Tiêu chí | Phương án 1: Supabase `pgvector` ⭐ *(Khuyên dùng)* | Phương án 2: Qdrant Cloud Free Tier |
| :--- | :--- | :--- |
| **Số lượng dịch vụ** | **1 dịch vụ duy nhất** (Gộp chung với PostgreSQL của Supabase) | 2 dịch vụ riêng biệt (Supabase + Qdrant Cloud) |
| **Chi phí** | **Miễn phí** (Tích hợp sẵn trong Free Tier của Supabase) | Miễn phí 1 cluster (Giới hạn 1GB RAM / 0.5 CPU) |
| **Khả năng truy vấn Hybrid** | Kết hợp trực tiếp Full-text Search (`tsvector`/`pg_trgm`) + Vector Cosine (`<=>`) trong **1 câu lệnh SQL duy nhất** | Hỗ trợ Sparse + Dense qua API Qdrant |
| **Độ trễ mạng (Latency)** | Rất thấp (Không tốn network round-trip giữa 2 cloud databases) | Tốn thêm 1 chặng mạng từ Railway sang Qdrant Cloud |
| **Khả năng mở rộng** | Phù hợp tối đa cho ~50.000 chunks tài liệu HDSD | Phù hợp nếu mở rộng quy mô >1 triệu chunks |

> 🎯 **ĐỀ XUẤT CHÍNH THỨC:** Sử dụng **Supabase `pgvector`**.
> * **Lý do:** Bạn đã chọn Supabase làm Cloud Database lưu lịch sử chat. Kích hoạt thêm extension `vector` của Postgres sẽ giúp bạn quản lý toàn bộ dữ liệu (Chat Sessions, Chat Messages, Document Chunks và Vector Embeddings) trên một cơ sở dữ liệu duy nhất, giúp bảo toàn tính toàn vẹn dữ liệu (ACID), đơn giản hóa mã nguồn kết nối và giảm thiểu tối đa chi phí quản trị.

---

## 2. Sơ Đồ Luồng Dữ Liệu Toàn Hệ Thống (System Dataflow)

```mermaid
flowchart TD
    subgraph Client_Layer ["1. CLIENT LAYER (End-Users)"]
        UserBrowser["🌐 Người dùng / Cán bộ Phường / Doanh nghiệp"]
    end

    subgraph Frontend_Layer ["2. FRONTEND (Vercel Edge Network)"]
        VercelApp["⚡ Next.js 14 App Router (hdsd-chatbot.vercel.app)<br/>• Chat UI Components<br/>• SSE Streaming Consumer<br/>• MediaViewer & Lightbox"]
    end

    subgraph Backend_Layer ["3. BACKEND CORE (Railway.app Container)"]
        FastAPI["🚀 FastAPI Core Service (api.railway.app)<br/>• Intent Classifier (Procedural vs Targeted)<br/>• Hybrid RAG Coordinator<br/>• Session & History Controller<br/>• Security Guardrails & Audit Logger"]
    end

    subgraph AI_Inference_Layer ["4. AI INFERENCE LAYER"]
        HFSpace["🤗 HuggingFace Space API<br/>(Model: AITeamVN/Vietnamese_Embedding_v2)"]
        QwenLLM["🧠 Qwen-3.7-Flash API (DashScope / Alibaba Cloud)<br/>(Contextual Reasoning & SOP Markdown Generation)"]
    end

    subgraph Storage_Layer ["5. PERSISTENT STORAGE (Supabase Cloud)"]
        subgraph SupabaseDB ["🐘 Supabase PostgreSQL (Port 5432 / 6543)"]
            T_Sessions[("📋 chat_sessions<br/>(id, user_id, role, title)")]
            T_Messages[("💬 chat_messages<br/>(id, session_id, role, content, metadata)")]
            T_Chunks[("📚 document_chunks (pgvector)<br/>(id, role, content, embedding vector[1024])")]
        end
    end

    %% Luồng tương tác
    UserBrowser <-->|HTTPS / WSS / SSE| VercelApp
    VercelApp <-->|REST API + Server-Sent Events| FastAPI
    FastAPI -->|1. Vectorize Query| HFSpace
    HFSpace -->|1024-dim Vector Array| FastAPI
    FastAPI <-->|2. Hybrid Search & Save History| SupabaseDB
    FastAPI -->|3. Augmented Prompt with Chunks| QwenLLM
    QwenLLM -->|Stream Tokens| FastAPI
```

---

## 3. Thiết Kế Cơ Sở Dữ Liệu Supabase (Schema & Migrations)

Truy cập **Supabase Dashboard** > **SQL Editor** và thực thi đoạn script SQL sau để khởi tạo cấu trúc dữ liệu hoàn chỉnh:

```sql
-- 1. Bật extension pgvector để hỗ trợ vector embeddings
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Bảng quản lý phiên hội thoại (Chat Sessions)
CREATE TABLE IF NOT EXISTS public.chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_identifier VARCHAR(100) NOT NULL DEFAULT 'anonymous',
    role VARCHAR(20) NOT NULL DEFAULT 'phuong', -- 'phuong' hoặc 'dn'
    title VARCHAR(255) NOT NULL DEFAULT 'Cuộc hội thoại mới',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. Bảng lưu trữ chi tiết tin nhắn hội thoại (Chat Messages)
CREATE TABLE IF NOT EXISTS public.chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES public.chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    intent VARCHAR(50),
    source_chunks JSONB DEFAULT '[]'::jsonb,
    images JSONB DEFAULT '[]'::jsonb,
    youtube_links JSONB DEFAULT '[]'::jsonb,
    quick_action_chips JSONB DEFAULT '[]'::jsonb,
    contact_support JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 4. Bảng lưu trữ kho tri thức RAG (Document Chunks & Embeddings)
-- Khớp kích thước vector 1024 của model AITeamVN/Vietnamese_Embedding_v2
CREATE TABLE IF NOT EXISTS public.document_chunks (
    id VARCHAR(100) PRIMARY KEY,
    document_title VARCHAR(255) NOT NULL,
    target_role VARCHAR(20) NOT NULL DEFAULT 'all', -- 'phuong', 'dn', 'all'
    heading_hierarchy TEXT[],
    content TEXT NOT NULL,
    extracted_images JSONB DEFAULT '[]'::jsonb,
    youtube_ref JSONB,
    step_keywords TEXT[],
    -- Model AITeamVN/Vietnamese_Embedding_v2 xuất vector dimension = 1024
    embedding vector(1024),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 5. Tạo Index tối ưu hóa truy vấn
-- Index tìm kiếm vector theo thuật toán HNSW (Hierarchical Navigable Small World)
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding 
ON public.document_chunks USING hnsw (embedding vector_cosine_ops);

-- Index Full-Text Search tiếng Việt cho Hybrid Search
CREATE INDEX IF NOT EXISTS idx_document_chunks_fts 
ON public.document_chunks USING gin (to_tsvector('simple', content));

-- Index tăng tốc truy xuất lịch sử chat theo session
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id 
ON public.chat_messages (session_id, created_at ASC);

-- 6. Tạo Hàm SQL Thực Thi Hybrid Retrieval (Vector + Full-Text Search)
CREATE OR REPLACE FUNCTION match_document_chunks (
    query_embedding vector(1024),
    match_threshold float,
    match_count int,
    filter_role varchar
)
RETURNS TABLE (
    id varchar,
    content text,
    extracted_images jsonb,
    youtube_ref jsonb,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id,
        dc.content,
        dc.extracted_images,
        dc.youtube_ref,
        1 - (dc.embedding <=> query_embedding) AS similarity
    FROM public.document_chunks dc
    WHERE (dc.target_role = filter_role OR dc.target_role = 'all' OR filter_role IS NULL)
      AND 1 - (dc.embedding <=> query_embedding) > match_threshold
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
```

---

## 4. Thiết Kế Model Microservice Trên HuggingFace Space

Tận dụng HuggingFace Space để chạy model `AITeamVN/Vietnamese_Embedding_v2`. Dưới đây là kiến trúc và cấu hình chi tiết theo chuẩn **HuggingFace Spaces Skill**:

### 4.1. Quy trình khởi tạo Space qua HuggingFace CLI & Skill:
1. **Kiểm tra và đăng nhập:**
   ```bash
   pip install -U huggingface_hub
   hf auth whoami
   ```
2. **Khởi tạo Space:**
   ```bash
   hf repos create Nato1306/vietnamese-embedding-api --type space --space-sdk gradio --flavor zero-a10g --public --exist-ok
   ```
   *(Hoặc sử dụng Docker SDK nếu muốn chạy trực tiếp FastAPI container)*.

### 4.2. Cấu trúc mã nguồn triển khai Space (`Gradio / FastAPI API`):

#### File `app.py`:
```python
import gradio as gr
from sentence_transformers import SentenceTransformer
import torch
import numpy as np

MODEL_ID = "AITeamVN/Vietnamese_Embedding_v2"
device = "cuda" if torch.cuda.is_available() else "cpu"

print(f"Loading {MODEL_ID} on {device}...")
model = SentenceTransformer(MODEL_ID, device=device)

def get_embedding(text: str):
    """API endpoint trích xuất vector embedding 1024 chiều"""
    if not text.strip():
        return {"error": "Empty text"}
    embedding = model.encode(text, normalize_embeddings=True)
    return {
        "model": MODEL_ID,
        "dim": len(embedding),
        "embedding": embedding.tolist()
    }

def batch_embedding(texts_joined: str):
    """Trích xuất embedding cho nhiều đoạn văn bản phân tách bởi dấu xuống dòng"""
    lines = [t.strip() for t in texts_joined.split("\n") if t.strip()]
    if not lines:
        return {"error": "No texts provided"}
    embeddings = model.encode(lines, normalize_embeddings=True)
    return {
        "model": MODEL_ID,
        "count": len(lines),
        "dim": embeddings.shape[1],
        "embeddings": embeddings.tolist()
    }

with gr.Blocks(title="Vietnamese Embedding v2 API") as demo:
    gr.Markdown(f"# 🇻🇳 {MODEL_ID} Inference Microservice")
    gr.Markdown("Dịch vụ tạo Embedding 1024-dim phục vụ RAG cho Hệ thống Chatbot HDSD.")
    
    with gr.Tab("Single Text Embedding"):
        txt_in = gr.Textbox(label="Văn bản tiếng Việt", placeholder="Nhập văn bản cần tạo vector...")
        btn_run = gr.Button("Trích xuất Vector", variant="primary")
        json_out = gr.JSON(label="Vector Embedding (1024 chiều)")
        btn_run.click(fn=get_embedding, inputs=txt_in, outputs=json_out, api_name="embed")
        
    with gr.Tab("Batch Embedding"):
        batch_in = gr.Textbox(label="Danh sách văn bản (mỗi dòng một câu)", lines=5)
        btn_batch = gr.Button("Trích xuất Batch", variant="primary")
        json_batch_out = gr.JSON(label="Danh sách Embeddings")
        btn_batch.click(fn=batch_embedding, inputs=batch_in, outputs=json_batch_out, api_name="batch_embed")

demo.launch()
```

#### File `requirements.txt`:
```txt
sentence-transformers>=3.0.0
torch
gradio>=4.0.0
numpy
accelerate
```

> [!WARNING]
> **Cơ chế Sleep trên Free HuggingFace Space & Keep-Alive:**
> Free Space trên HuggingFace sẽ chuyển sang trạng thái "Sleeping" sau 48 giờ không có lượt truy cập.
> * **Giải pháp khắc phục:** Thiết lập một tác vụ Cron Job (qua dịch vụ miễn phí như `cron-job.org` hoặc `UptimeRobot`) để ping vào endpoint của Space mỗi 15 phút một lần để giữ cho Space luôn thức (Keep-alive).

---

## 5. Hướng Dẫn Triển Khai Từng Bước (Step-by-Step Deployment)

### BƯỚC 1: Cấu hình Cơ sở dữ liệu Supabase
1. Đăng ký tài khoản tại [supabase.com](https://supabase.com) và tạo một New Project (đặt tên ví dụ: `hdsd-chatbot-db`).
2. Vào mục **Project Settings** > **Database**:
   * Sao chép chuỗi kết nối **Connection String (URI)** (chọn tab *Transaction Pooler* port `6543` để tối ưu kết nối serverless).
   * Lưu lại mật khẩu database (`SUPABASE_DB_PASSWORD`).
3. Mở **SQL Editor** và dán toàn bộ đoạn code SQL ở **Mục 3** để khởi tạo bảng và index `pgvector`.

---

### BƯỚC 2: Triển khai Model Microservice lên HuggingFace Space
1. Khởi tạo Space tại `https://huggingface.co/spaces/Nato1306/vietnamese-embedding-api`.
2. Đẩy file `app.py` và `requirements.txt` lên Space.
3. Nhận Public API URL dạng:
   `https://nato1306-vietnamese-embedding-api.hf.space`

---

### BƯỚC 3: Triển khai Backend FastAPI lên Railway.app
1. Đăng nhập [railway.app](https://railway.app) bằng tài khoản GitHub.
2. Chọn **"New Project"** > **"Deploy from GitHub repo"** > Chọn repository `CaoAnhNato/Chatbot_HDSD`.
3. Trong phần cấu hình Service:
   * **Root Directory:** Đặt là `/backend`
   * **Builder:** Chọn `Dockerfile` (Railway sẽ tự động đọc [backend/Dockerfile](file:///c:/Users/Admin/HUIT%20-%20H%E1%BB%8Dc%20T%E1%BA%ADp/N%C4%83m%204/Chatbot_Project/backend/Dockerfile)).
4. Vào tab **Variables** của Service trên Railway và nhập các biến môi trường:
   ```env
   PORT=8000
   QWEN_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
   DATABASE_URL=postgresql://postgres.xxx:[PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
   HF_EMBEDDING_API_URL=https://nato1306-vietnamese-embedding-api.hf.space
   EMBEDDING_MODEL_NAME=AITeamVN/Vietnamese_Embedding_v2
   VECTOR_DB_TYPE=pgvector
   CORS_ORIGINS=https://chatbot-hdsd.vercel.app,http://localhost:3000
   ```
5. Vào tab **Settings** > **Networking** > Chọn **Generate Domain** để nhận Public HTTPS Domain (ví dụ: `https://chatbot-hdsd-backend.up.railway.app`).

---

### BƯỚC 4: Triển khai Frontend Next.js lên Vercel
1. Đăng nhập [vercel.com](https://vercel.com) > Chọn **"Add New Project"**.
2. Chọn repository `CaoAnhNato/Chatbot_HDSD`.
3. Trong giao diện cấu hình:
   * **Root Directory:** Chọn `frontend`
   * **Framework Preset:** `Next.js`
   * **Build Command:** `npm run build`
   * **Output Directory:** `.next`
4. Mở rộng phần **Environment Variables** và cấu hình:
   ```env
   NEXT_PUBLIC_API_URL=https://chatbot-hdsd-backend.up.railway.app/api/v1
   ```
5. Nhấn **Deploy**. Sau khi build hoàn tất, bạn nhận được domain chính thức (ví dụ: `https://chatbot-hdsd.vercel.app`).

---

## 6. Cơ Chế CI/CD & Tự Động Đồng Bộ Khi Push Code

Hệ thống được thiết kế theo chuẩn **GitOps** gắn với repository chính thức:
👉 **`https://github.com/CaoAnhNato/Chatbot_HDSD.git`**

```
[Developer Máy Cục Bộ] 
       │ 
       ▼ (1) git add . && git commit -m "update prompt/feature"
       ▼ (2) git push origin main
[GitHub: CaoAnhNato/Chatbot_HDSD]
       ├──▶ Webhook 1 ──▶ [Vercel]: Tự động build lại Next.js UI trong ~60s (Zero-Downtime)
       └──▶ Webhook 2 ──▶ [Railway]: Tự động build lại Docker FastAPI & chạy Lifespan Warmup
```

### 💡 Các tình huống cập nhật thực tế:
1. **Cập nhật giao diện / Logic Frontend:**
   * Sửa file trong thư mục `frontend/`.
   * Chạy `git push origin main`.
   * Vercel tự build và cập nhật giao diện mới cho toàn bộ người dùng đang truy cập mà không cần khởi động lại Backend.
2. **Cập nhật Prompt / RAG Logic / API Endpoint Backend:**
   * Sửa file trong thư mục `backend/`.
   * Chạy `git push origin main`.
   * Railway tự kích hoạt quy trình build Docker container mới, kiểm tra healthcheck thành công rồi mới chuyển traffic sang container mới.
3. **Cập nhật Tài liệu HDSD mới (Document Ingestion):**
   * Khi có file tài liệu Word mới, chạy script nạp dữ liệu một lần lên Supabase:
     ```bash
     python backend/scripts/ingest_to_supabase.py --file "Bussiness_Rules/docs/HDSD_Moi.docx"
     ```
   * Dữ liệu vector mới sẽ xuất hiện ngay lập tức trong bảng `document_chunks` của Supabase mà không cần redeploy code.

---

## 7. Bảng Ma Trận Biến Môi Trường (Environment Variables Matrix)

| Vị trí | Tên Biến Môi Trường | Giá trị Mẫu | Mô tả |
| :--- | :--- | :--- | :--- |
| **Vercel (Frontend)** | `NEXT_PUBLIC_API_URL` | `https://chatbot-hdsd-backend.up.railway.app/api/v1` | URL trỏ tới API Backend trên Railway |
| **Railway (Backend)** | `PORT` | `8000` | Cổng lắng nghe của container |
| **Railway (Backend)** | `QWEN_API_KEY` | `sk-dashscope-xxxxxxxx` | API Key Alibaba DashScope Qwen |
| **Railway (Backend)** | `DATABASE_URL` | `postgresql://postgres:[PASS]@[HOST]:6543/postgres` | Chuỗi kết nối Supabase PostgreSQL |
| **Railway (Backend)** | `HF_EMBEDDING_API_URL` | `https://nato1306-vietnamese-embedding-api.hf.space` | URL gọi inference model embedding |
| **Railway (Backend)** | `EMBEDDING_MODEL_NAME` | `AITeamVN/Vietnamese_Embedding_v2` | Tên embedding model |
| **Railway (Backend)** | `VECTOR_DB_TYPE` | `pgvector` | Định danh driver vector store |
| **Railway (Backend)** | `CORS_ORIGINS` | `https://chatbot-hdsd.vercel.app` | Whitelist domain frontend gọi API |

---

## 8. Checklist Vận Hành & Xử Lý Sự Cố (Troubleshooting & Security)

### ✅ Checklist An toàn trước khi mở cho nhiều người test:
- [ ] **Khắc phục lỗi Mixed Content:** Đảm bảo `NEXT_PUBLIC_API_URL` bắt đầu bằng `https://`, không dùng `http://`.
- [ ] **Kiểm tra CORS Header:** Mở DevTools Network trên trình duyệt khi chat, kiểm tra xem response header có trả về `Access-Control-Allow-Origin: https://chatbot-hdsd.vercel.app` hay không.
- [ ] **Kiểm tra Streaming SSE:** Xác minh câu trả lời của Bot gõ từng từ mượt mà (chế độ SSE không bị buffer hoặc timeout giữa chừng).
- [ ] **Kiểm tra lưu lịch sử chat:** Sau khi chat thử vài câu, vào Supabase Table Editor kiểm tra xem dữ liệu đã được ghi vào bảng `chat_sessions` và `chat_messages` chưa.
- [ ] **Keep-alive HuggingFace Space:** Cấu hình cronjob ping `https://nato1306-vietnamese-embedding-api.hf.space` mỗi 15 phút.
- [ ] **Bảo mật API Key:** Tuyệt đối không commit file `.env` chứa `QWEN_API_KEY` hay `DATABASE_URL` lên GitHub public. Luôn sử dụng tab Environment Variables của Vercel/Railway.

---
*Tài liệu được biên soạn phục vụ công tác triển khai thử nghiệm hệ thống Chatbot HDSD 2026.*
