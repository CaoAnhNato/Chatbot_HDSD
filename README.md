# Multimodal HDSD Chatbot Assistant 🤖📚

> **Tài Liệu Hướng Dẫn Cài Đặt & Vận Hành Toàn Diện Từ Con Số 0 (Client Handover Manual)**  
> *Dành cho khách hàng thiết lập trên máy mới hoàn toàn (Clean Machine) — Hướng dẫn chi tiết từng câu lệnh từ chuẩn bị môi trường, nạp dữ liệu Word (.docx), đến khởi chạy Backend & Frontend.*

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14.2%20App%20Router-black?logo=next.js)](https://nextjs.org/)
[![Vector Store](https://img.shields.io/badge/Vector%20Store-ChromaDB-red)](https://www.trychroma.com/)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

---

## 📑 Mục Lục
1. [Giới Thiệu Tổng Quan](#1-giới-thiệu-tổng-quan)
2. [Cài Đặt Các Công Cụ Nền Tảng (Prerequisites)](#2-cài-đặt-các-công-cụ-nền-tảng-prerequisites)
3. [Bước 1: Tải Mã Nguồn Dự Án (Git Clone)](#bước-1-tải-mã-nguồn-dự-án-git-clone)
4. [Bước 2: Cài Đặt Môi Trường Backend & Thư Viện Python](#bước-2-cài-đặt-môi-trường-backend--thư-viện-python)
5. [Bước 3: Cấu Hình Biến Môi Trường Backend (.env)](#bước-3-cấu-hình-biến-môi-trường-backend-env)
6. [Bước 4: Đặt File Word & Chạy Nạp Dữ Liệu (Data Ingestion - BẮT BUỘC)](#bước-4-đặt-file-word--chạy-nạp-dữ-liệu-data-ingestion---bắt-buộc)
7. [Bước 5: Cài Đặt Giao Diện Người Dùng Frontend (Next.js 14)](#bước-5-cài-đặt-giao-diện-người-dùng-frontend-nextjs-14)
8. [Bước 6: Khởi Chạy Toàn Bộ Hệ Thống](#bước-6-khởi-chạy-toàn-bộ-hệ-thống)
9. [Kiểm Thử & Đánh Giá Chất Lượng Phản Hồi](#kiểm-thử--đánh-giá-chất-lượng-phản-hồi)
10. [Xử Lý Lỗi Thường Gặp Khi Cài Đặt (Troubleshooting)](#xử-lý-lỗi-thường-gặp-khi-cài-đặt-troubleshooting)

---

## 1. Giới Thiệu Tổng Quan

**Multimodal HDSD Chatbot Assistant** là hệ thống trợ lý AI hỗ trợ tra cứu quy trình, hướng dẫn thao tác phần mềm dựa trên tài liệu Word (DOCX):
* **Hỗ trợ 2 phân hệ độc lập:**
  * 🏛️ **Cán bộ Phường / Xã:** Tra cứu quy trình tiếp nhận, quản lý thông tin an toàn lao động cơ sở.
  * 🏢 **Doanh nghiệp:** Tra cứu thủ tục khai báo, nộp báo cáo tai nạn lao động.
* **Đa phương tiện (Multimodal):** Tự động bóc tách ảnh chụp màn hình UI từ file Word gốc và hiển thị chính xác tại từng bước hướng dẫn thao tác, phóng to bằng Lightbox.
* **Truy xuất lai siêu tốc (Hybrid RAG):** Kết hợp tìm kiếm vector ngữ nghĩa (Dense Vector) và tìm kiếm từ khóa BM25 cho tốc độ phản hồi tức thì.

---

## 2. Cài Đặt Các Công Cụ Nền Tảng (Prerequisites)

> 💡 **Khách hàng bắt đầu từ máy tính mới cần cài đặt đủ 3 phần mềm dưới đây trước khi thực hiện các bước tiếp theo:**

### 2.1. Cài đặt Git (Quản lý mã nguồn)
* **Tải về:** Truy cập [https://git-scm.com/download/win](https://git-scm.com/download/win) tải bản cài đặt Windows 64-bit và nhấn **Next** đến khi hoàn tất.
* **Kiểm tra sau khi cài:** Mở Terminal (PowerShell hoặc Command Prompt) gõ:
  ```powershell
  git --version
  # Kết quả hợp lệ ví dụ: git version 2.45.x
  ```

### 2.2. Cài đặt Python 3.11 hoặc Python 3.12 (RẤT QUAN TRỌNG)
* **Tải về:** Khuyến nghị tải phiên bản **Python 3.12.x** tại: [https://www.python.org/downloads/release/python-3128/](https://www.python.org/downloads/release/python-3128/) (kéo xuống mục Files, chọn *Windows installer (64-bit)*).
* ⚠️ **LƯU Ý BẮT BUỘC TRONG LÚC CÀI ĐẶT:**
  * Ngay tại màn hình đầu tiên của trình cài đặt Python, **TÍCH CHỌN VÀO Ô: `Add python.exe to PATH`** ở dưới cùng trước khi bấm *Install Now*.
* ⚠️ **Tại sao không dùng Python 3.13 hoặc 3.14?**
  * Các gói AI chuyên biệt (`chromadb`, `sentence-transformers`, `torch`) chưa phát hành bản nhị phân dựng sẵn cho Python 3.13/3.14 trên Windows. Nếu dùng 3.13+, quá trình cài đặt sẽ bị lỗi yêu cầu cài bộ công cụ Visual Studio C++ nặng hơn 5GB.
* **Kiểm tra sau khi cài:**
  ```powershell
  python --version
  # Kết quả hợp lệ: Python 3.11.x hoặc Python 3.12.x
  ```

### 2.3. Cài đặt Node.js & npm (Chạy Giao diện Frontend)
* **Tải về:** Truy cập [https://nodejs.org/](https://nodejs.org/) và tải bản **LTS (Long Term Support)** (ví dụ: Node.js v20.x hoặc v22.x LTS).
* **Kiểm tra sau khi cài:**
  ```powershell
  node -v
  npm -v
  # Kết quả hợp lệ: node v20.x.x / npm 10.x.x
  ```

---

## Bước 1: Tải Mã Nguồn Dự Án (Git Clone)

Mở **PowerShell** (hoặc CMD), di chuyển đến thư mục bạn muốn lưu dự án (ví dụ `D:\Projects` hoặc `C:\Users\<Tên_bạn>`), sau đó chạy:

```powershell
# 1. Tải toàn bộ repository về máy
git clone https://github.com/CaoAnhNato/Chatbot_HDSD.git

# 2. Di chuyển vào thư mục gốc của dự án
cd Chatbot_HDSD
```

---

## Bước 2: Cài Đặt Môi Trường Backend & Thư Viện Python

### 2.1. Cấp quyền thực thi script cho PowerShell (chỉ cần chạy 1 lần nếu gặp lỗi)
Mở PowerShell tại thư mục dự án và chạy:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 2.2. Tạo môi trường ảo Python độc lập (.venv)
Tại thư mục `Chatbot_HDSD`, chạy lệnh sau để tạo môi trường cách ly:
```powershell
python -m venv .venv
```

### 2.3. Kích hoạt môi trường ảo
* **Trên Windows PowerShell:**
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
* **Trên Windows Command Prompt (CMD):**
  ```cmd
  .\.venv\Scripts\activate.bat
  ```
* **Trên Linux / macOS:**
  ```bash
  source .venv/bin/activate
  ```
> *Khi kích hoạt thành công, dòng lệnh sẽ xuất hiện tiền tố `(.venv)` ở đầu.*

### 2.4. Nâng cấp pip và cài đặt toàn bộ thư viện Backend
Chạy lệnh cài đặt các gói cần thiết từ file `requirements.txt`:
```powershell
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```
*(Quá trình tải và cài đặt các thư viện `fastapi`, `uvicorn`, `chromadb`, `sentence-transformers`... sẽ mất khoảng 1 - 3 phút).*

---

## Bước 3: Cấu Hình Biến Môi Trường Backend (.env)

Hệ thống cần file cấu hình để nhận diện API Key của mô hình AI và các thiết lập cục bộ.

### 3.1. Tạo file `.env` từ file mẫu:
* **Trên Windows PowerShell:**
  ```powershell
  Copy-Item backend\.env.example backend\.env
  ```
* **Trên Windows CMD:**
  ```cmd
  copy backend\.env.example backend\.env
  ```

### 3.2. Chỉnh sửa nội dung file `backend/.env`:
Mở file `backend/.env` bằng Notepad hoặc VS Code. Bạn chỉ cần lưu ý các mục sau:

```dotenv
# ==============================================================================
# 1. CẤU HÌNH API KEY (CHỌN 1 TRONG CÁC NHÀ CUNG CẤP DƯỚI ĐÂY)
# ==============================================================================

# Cách 1 (Mặc định): Sử dụng Qwen API từ Alibaba Cloud DashScope
QWEN_API_KEY="sk-your-qwen-dashscope-api-key"
QWEN_BASE_URL="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
QWEN_MODEL_NAME="qwen3.7-flash"

# Cách 2: Sử dụng OpenRouter API (Khuyên dùng - Hỗ trợ Gemini, DeepSeek, Qwen...)
ACTIVE_LLM_PROVIDER="openrouter"
OPENROUTER_API_KEY="sk-or-v1-your-openrouter-api-key"
QWEN_BASE_URL="https://openrouter.ai/api/v1"
QWEN_MODEL_NAME="google/gemini-2.5-flash-lite"

# Cách 3: Sử dụng Google Gemini API
GOOGLE_API_KEY="AIzaSy-your-google-api-key"

# ==============================================================================
# 2. CẤU HÌNH CHẠY LOCAL (GIỮ NGUYÊN)
# ==============================================================================
PROJECT_NAME="Multimodal HDSD Chatbot Assistant"
PORT=8000
HOST="127.0.0.1"

# BẮT BUỘC ĐỂ false NẾU MÁY BẠN CHƯA CÀI REDIS SERVER
REDIS_ENABLED=false

# Cấu hình lưu trữ Vector DB và Ảnh bóc tách nội bộ
VECTOR_DB_TYPE="chroma"
CHROMA_PERSIST_DIRECTORY="./chroma_data"
IMAGE_STORAGE_PATH="./data/extracted_images"
BASE_IMAGE_CDN_URL="http://localhost:8000/static/images"

# Danh sách domain Frontend được phép kết nối API (CORS)
CORS_ORIGINS='["http://localhost:3000", "http://127.0.0.1:3000", "https://chatbot-hdsd.vercel.app"]'
```

---

## Bước 4: Đặt File Word & Chạy Nạp Dữ Liệu (Data Ingestion - BẮT BUỘC)

> ❗ **Máy mới của khách hàng chưa có cơ sở dữ liệu Vector và chưa có ảnh trích xuất.**  
> Bạn cần đặt file Word tài liệu hướng dẫn sử dụng vào thư mục chỉ định và chạy lệnh nạp dữ liệu để hệ thống tự động xử lý.

### 4.1. Thư mục đích đặt tài liệu Word
Khách hàng đặt các file tài liệu hướng dẫn sử dụng (`.docx`) vào đúng thư mục sau:
📁 **`Bussiness_Rules/docs/`**

| Phân hệ nghiệp vụ | Tên file Word được hệ thống tự động nhận diện |
| :--- | :--- |
| **Phân hệ Phường / Xã** | `HDSD WOM v1.0.docx` *(hoặc `HDSD ATLĐ (Phường).docx`)* |
| **Phân hệ Doanh nghiệp** | `_AI_HDSD_ATLĐ (DN).v1_HCM_2026 (1).docx` *(hoặc `HDSD_DN.docx`)* |

> *(Trong mã nguồn tải về từ repository đã có sẵn file mẫu `HDSD WOM v1.0.docx` trong thư mục `Bussiness_Rules/docs/` để bạn có thể chạy thử nghiệm ngay).*

### 4.2. Chạy lệnh nạp dữ liệu vào ChromaDB Vector Store
Đảm bảo môi trường ảo `(.venv)` đang được kích hoạt tại thư mục gốc `Chatbot_HDSD`, chọn chạy lệnh tương ứng:

* **Tùy chọn A: Nạp phân hệ Phường / Xã:**
  ```powershell
  python backend/scripts/ingest_docs.py --mode phuong
  ```
  *(hoặc chạy script chuyên biệt: `python backend/scripts/ingest_phuong_docs.py`)*

* **Tùy chọn B: Nạp phân hệ Doanh nghiệp:**
  ```powershell
  python backend/scripts/ingest_docs.py --mode dn
  ```

* **Tùy chọn C: Nạp đồng thời cả 2 phân hệ cùng lúc:**
  ```powershell
  python backend/scripts/ingest_docs.py --mode all
  ```

### 4.3. Quá trình Ingestion tự động thực hiện những việc gì?
1. 📖 Đọc và bóc tách cây cấu trúc tài liệu Word (Heading 1, 2, 3, bảng biểu, danh sách thao tác).
2. 🖼️ **Tự động trích xuất toàn bộ ảnh UI chụp màn hình** có trong file Word và lưu ra thư mục `backend/data/extracted_images/` để phục vụ hiển thị lên giao diện chat.
3. 🏷️ Gắn nhãn phân hệ, trích xuất từ khóa tìm kiếm và các bước nghiệp vụ.
4. 🧠 Tính toán vector embedding và lưu trữ chỉ mục vào ChromaDB tại thư mục `backend/chroma_data/`.
5. 🎉 Khi màn hình thông báo: `NẠP THÀNH CÔNG COLLECTION ... (xxx chunks)!` là dữ liệu đã sẵn sàng phục vụ.

---

## Bước 5: Cài Đặt Giao Diện Người Dùng Frontend (Next.js 14)

Mở một **cửa sổ Terminal mới**, di chuyển vào thư mục `frontend`:

```powershell
cd "D:\Projects\Chatbot_HDSD\frontend"   # (Thay đường dẫn tới thư mục dự án của bạn)
```

### 5.1. Tạo file cấu hình kết nối API (`.env.local`)
Tạo file `.env.local` bên trong thư mục `frontend/` để chỉ định Frontend kết nối với máy chủ Backend cục bộ của bạn:

* **Trên Windows PowerShell:**
  ```powershell
  Set-Content -Path .env.local -Value 'NEXT_PUBLIC_API_URL="http://localhost:8000/api/v1"'
  ```
* **Hoặc tạo file `.env.local` bằng tay trong thư mục `frontend/` với nội dung duy nhất:**
  ```dotenv
  NEXT_PUBLIC_API_URL="http://localhost:8000/api/v1"
  ```

### 5.2. Cài đặt các gói phụ thuộc Node.js
Chạy lệnh cài đặt:
```powershell
npm install
```
*(Chờ quá trình tải và cài đặt các thư viện React, Next.js, TailwindCSS hoàn tất).*

---

## Bước 6: Khởi Chạy Toàn Bộ Hệ Thống

Để hệ thống hoạt động đầy đủ, bạn cần **chạy song song 2 cửa sổ Terminal**:

### 🟢 Cửa Sổ Terminal 1: Khởi Chạy Backend (FastAPI Engine)
Đứng tại thư mục gốc của dự án (`Chatbot_HDSD`):

```powershell
# 1. Kích hoạt môi trường ảo
.\.venv\Scripts\Activate.ps1

# 2. Khởi chạy máy chủ FastAPI tại cổng 8000
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

* **Trang tài liệu Swagger API:** Mở trình duyệt truy cập: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **Kiểm tra trạng thái máy chủ:** [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health) (trả về `{"status":"healthy"}`).

---

### 🟢 Cửa Sổ Terminal 2: Khởi Chạy Frontend (Next.js 14)
Di chuyển vào thư mục `frontend`:

```powershell
cd frontend
npm run dev
```

* **Truy cập ứng dụng Chatbot:** Mở trình duyệt web và truy cập địa chỉ:
  👉 **[http://localhost:3000](http://localhost:3000)**

---

## Kiểm Thử & Đánh Giá Chất Lượng Phản Hồi

Sau khi đã nạp dữ liệu và khởi động hệ thống, bạn có thể thực hiện kiểm thử:

### 1. Thử nghiệm trên giao diện Web (`http://localhost:3000`)
* Chuyển tab sang **[🏛️ Phường / Xã]** và đặt các câu hỏi:
  * *"Làm sao để đổi mật khẩu tài khoản đang đăng nhập?"* $\rightarrow$ Hệ thống sẽ hướng dẫn từng bước và đính kèm ảnh chụp màn hình UI.
  * *"Quy trình khai báo tai nạn lao động khi vừa xảy ra trên địa bàn"*
  * *"Số điện thoại hỗ trợ kỹ thuật của hệ thống là gì?"* $\rightarrow$ Hệ thống xuất hiện Thẻ liên hệ hotline màu vàng (`028 3535 2524`).

### 2. Chạy kịch bản kiểm thử tự động Backend (Automated Tests)
Mở cửa sổ Terminal tại thư mục `Chatbot_HDSD` (đã kích hoạt `.venv`):
```powershell
# Kiểm thử toàn diện 10 phân hệ nghiệp vụ Phường/Xã
python backend/tests/test_phuong_rag.py

# Chạy đo lường Benchmark 18 test cases và thời gian phản hồi (TTFT)
python backend/tests/run_benchmark.py
```

---

## Xử Lý Lỗi Thường Gặp Khi Cài Đặt (Troubleshooting)

### 1. Lỗi PowerShell: `File ... Activate.ps1 cannot be loaded because running scripts is disabled`
* **Nguyên nhân:** Windows mặc định chặn chạy script ngoài PowerShell.
* **Cách sửa:** Mở PowerShell và chạy lệnh sau để cấp quyền cho phiên làm việc hiện tại:
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  ```
  Sau đó kích hoạt lại: `.\.venv\Scripts\Activate.ps1`.

### 2. Lỗi `Microsoft Visual C++ 14.0 or greater is required` khi chạy `pip install`
* **Nguyên nhân:** Bạn đang sử dụng Python 3.13 hoặc 3.14 nên pip phải tự biên dịch mã nguồn C++.
* **Cách sửa:**
  1. Gỡ cài đặt Python 3.13/3.14.
  2. Tải và cài đặt **Python 3.11** hoặc **Python 3.12** từ [python.org](https://www.python.org/downloads/). (Nhớ tích chọn *Add python.exe to PATH*).
  3. Xóa thư mục `.venv` cũ (`Remove-Item -Recurse -Force .venv`) và tạo lại từ Bước 2.2.

### 3. Lỗi `ModuleNotFoundError: No module named 'app'` khi khởi động Backend
* **Nguyên nhân:** Thiếu tham số `--app-dir backend` khiến Python tìm thư mục `app` ở sai vị trí.
* **Cách sửa:** Chạy đúng cú pháp lệnh:
  ```powershell
  python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
  ```

### 4. Lỗi kết nối Redis: `ConnectionRefusedError: [Errno 111] Connection refused`
* **Nguyên nhân:** Máy tính cá nhân chưa cài đặt dịch vụ Redis Server.
* **Cách sửa:** Mở file `backend/.env`, tìm dòng `REDIS_ENABLED` và đổi thành:
  ```dotenv
  REDIS_ENABLED=false
  ```

### 5. Chatbot trả lời báo lỗi chưa có API Key
* **Nguyên nhân:** Chưa cấu hình khóa AI hoặc khóa không hợp lệ trong file `backend/.env`.
* **Cách sửa:** Mở `backend/.env` và điền key vào biến `QWEN_API_KEY` hoặc `OPENROUTER_API_KEY`.

### 6. Khi chạy Ingestion báo `Không tìm thấy file: ...`
* **Nguyên nhân:** File tài liệu Word chưa được đặt đúng thư mục `Bussiness_Rules/docs/` hoặc bị sai tên.
* **Cách sửa:** Kiểm tra thư mục `Bussiness_Rules/docs/` xem đã có file `HDSD WOM v1.0.docx` (cho Phường) hoặc `HDSD_DN.docx` (cho Doanh nghiệp) chưa.

### 7. Lỗi xung đột cổng: `[Errno 10048] Address already in use (port 8000 hoặc 3000)`
* **Nguyên nhân:** Có một tiến trình Python hoặc Node.js cũ đang chạy ngầm chiếm cổng.
* **Cách sửa:** Chạy lệnh PowerShell sau để giải phóng cổng:
  ```powershell
  # Giải phóng cổng 8000:
  Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess -ErrorAction SilentlyContinue | Stop-Process -Force

  # Giải phóng cổng 3000:
  Get-Process -Id (Get-NetTCPConnection -LocalPort 3000).OwningProcess -ErrorAction SilentlyContinue | Stop-Process -Force
  ```

---

## 📂 Cấu Trúc Thư Mục Dự Án

```
Chatbot_HDSD/
├── Bussiness_Rules/                       # Tài liệu nghiệp vụ & Chứa file Word đầu vào
│   └── docs/                              # 👉 ĐẶT FILE WORD (.DOCX) TẠI ĐÂY ĐỂ NẠP DỮ LIỆU
│       └── HDSD WOM v1.0.docx             # File tài liệu hướng dẫn sử dụng mẫu
├── backend/                               # Máy chủ Python FastAPI & AI RAG Engine
│   ├── app/
│   │   ├── api/v1/                        # Các REST API Endpoints (/chat, /health, /ingest)
│   │   ├── core/                          # Cấu hình tập trung (config.py), Guardrails
│   │   ├── models/                        # Pydantic Schemas (ChatRequest, Response)
│   │   ├── services/                      # RAG Service, Qwen Service, Intent Routing
│   │   ├── ingestion/                     # Module bóc tách OpenXML Docx & Trích xuất ảnh UI
│   │   └── vectorstore/                   # ChromaDB Store & BM25 Sparse Index
│   ├── scripts/
│   │   ├── ingest_docs.py                 # Script nạp dữ liệu chính (hỗ trợ --mode all/dn/phuong)
│   │   └── ingest_phuong_docs.py          # Script nạp dữ liệu phân hệ Phường/Xã
│   ├── tests/                             # Bộ kiểm thử tự động & Benchmark đo lường hiệu năng
│   ├── data/
│   │   ├── extracted_images/              # 🖼️ Nơi chứa ảnh chụp UI trích xuất tự động từ Word
│   │   └── catalogs/                      # Domain Catalog JSON sinh tự động sau khi nạp
│   ├── chroma_data/                       # 🗄️ Cơ sở dữ liệu Vector ChromaDB lưu trữ cục bộ
│   ├── .env.example                       # Mẫu cấu hình biến môi trường Backend
│   └── requirements.txt                   # Danh sách thư viện Python cần cài đặt
├── frontend/                              # Giao diện người dùng Web Next.js 14
│   ├── src/
│   │   ├── app/                           # App Router (page.tsx, layout.tsx)
│   │   ├── components/chat/               # UI Chat, Lightbox zoom ảnh, nhúng video
│   │   └── lib/                           # Xử lý API Client & giải mã luồng SSE Streaming
│   ├── .env.example                       # Mẫu cấu hình biến môi trường Frontend
│   └── package.json                       # Danh sách gói thư viện Node.js
└── README.md                              # Tài liệu hướng dẫn sử dụng (Tệp này)
```

---
*Multimodal HDSD Chatbot Assistant — Bộ tài liệu chuẩn bị sẵn sàng cho khách hàng cài đặt và vận hành.*
