# IPGov Chatbot — Trợ Lý Ảo Tra Cứu Kho Dữ Liệu Hành Chính Công (DWH)

> **Mục tiêu:** Hệ thống trợ lý ảo tra cứu chỉ tiêu, báo cáo, biểu mẫu và dữ liệu tổng hợp từ Kho DWH Chính phủ điện tử (PostgreSQL `vna_wom_dev`), đảm bảo tính chính xác số liệu tuyệt đối, tuân thủ Nghị định 13/2023/NĐ-CP và cơ chế phân quyền phân cấp HBAC (Hierarchical Role-Based Access Control).

---

## 🏛️ Cấu Trúc Dự Án (Clean Directory Structure)

Mọi tệp tin trong hệ sinh thái `IPGov_Chatbot` được tổ chức ngăn nắp, tuân thủ nguyên tắc **"Đúng Nơi Đúng Chỗ"** và **Triết lý Tinh Giản Ponytail (Lean Zero-Slop)**:

```
IPGov_Chatbot/
├── main.py                     # Entry point chính của ứng dụng FastAPI Backend
├── run_server.py               # CLI Runner khởi chạy máy chủ linh hoạt qua terminal
├── config.py                   # Cấu hình tập trung IPGovSettings (Pydantic v2)
├── README.md                   # Tài liệu tổng quan dự án
│
├── modules/                    # 8 Phân hệ nghiệp vụ cốt lõi (In-Process Modular Monolith)
│   ├── mod01_gateway/          # Module 1: API Gateway, JWT RFC 7519, SSE Stream Ingress
│   ├── mod02_guardrails/       # Module 2: Pre-Router Guardrails (PII NĐ 13/2023, DDL/DML, Scope)
│   └── mod03_router/           # Module 3: SSOT DashScope LLM Router & Redis Session Memory (deepseek-v4.1-flash, H-DFT, Sliding Window LTRIM, Decision Cache)
│
├── schemas/                    # Pydantic v2 DTOs dùng chung giữa các modules
│   ├── user_context.py         # UserSecurityContextDTO (tenant, dept, office, role_level)
│   ├── guardrail_dto.py        # SanitizedQuestDTO, GuardrailResultDTO, ViolationTypeEnum
│   ├── router_dto.py           # RouterOutputDTO, ActiveQuestFrameDTO, SessionEpisodicMemoryDTO
│   ├── structured_router_schema.py # LLMRouterStructuredOutput (Pydantic v2 extra="forbid")
│   └── sse_events.py           # SSEEvent DTOs định dạng MIME text/event-stream
│
├── frontend/                   # Giao diện kiểm thử và component tích hợp
│   ├── role_selector_bench.html# Test Bench độc lập (HTML5/Tailwind/JS) chạy ngay trên trình duyệt
│   └── components/
│       └── RoleSelector.tsx    # React/Next.js component chọn nhanh vai trò HBAC
│
├── tests/                      # Hạ tầng kiểm thử tự động & Baseline Snapshots (Pass 100%)
│   ├── conftest.py             # Fixtures môi trường test
│   ├── test_backend_app.py     # Integration test toàn diện cho FastAPI Backend
│   ├── test_ci_sec_guardrails.py # 7 ca kiểm thử an ninh HITL (CI-SEC-GUARDRAILS)
│   ├── test_enterprise_modules_suites.py # 81 ca kiểm thử Gateway & Guardrails
│   ├── test_mod01_gateway.py   # Unit test Module 1
│   ├── test_mod02_guardrails.py# Unit test Module 2
│   ├── test_redis_session_manager.py # 6 ca kiểm thử Redis Session Manager (ActiveQuest, LTRIM, Cache)
│   ├── test_mod03_groq_structured_router.py # 10 ca kiểm thử SSOT Structured Router & Adversarial Quests
│   ├── test_mod03_chitchat.py  # 12 ca kiểm thử Chitchat Fast Bypass & Decoupling
│   ├── test_mod03_hdft_multiturn.py # 16 ca kiểm thử đa lượt H-DFT & Discovery
│   ├── test_mod03_router_all_tracks.py # 3 ca kiểm thử all tracks & snapshot stage 3
│   └── snapshots/              # Lưu trữ Baseline Snapshots Stage 1, Stage 2 & Stage 3
│       ├── stage_1_gateway/
│       ├── stage_2_prerouter/
│       └── stage_3_router_hdft/
│
├── docs/                       # Tài liệu kỹ thuật chuyên sâu & Kế hoạch tổng thể
│   ├── MASTER_PLAN_AND_PROGRESS_TRACKING.md # Kế hoạch tổng thể & Bảng theo dõi tiến độ 8 modules
│   ├── BACKEND_RUN_GUIDE.md    # Hướng dẫn chi tiết khởi chạy Backend qua terminal
│   ├── MODULE_01_GATEWAY_SPEC.md # Đặc tả kỹ thuật Module 1 (Liên kết Blueprints 00, 07)
│   ├── MODULE_02_GUARDRAILS_SPEC.md # Đặc tả kỹ thuật Module 2 (Liên kết Blueprints 02, 04)
│   ├── MODULE_03_ROUTER_SPEC.md # Đặc tả kỹ thuật Module 3 (v3.2 SSOT DashScope & Redis Pipeline)
│   └── ROUTER_MODEL_BENCHMARK.md # Báo cáo đo đạc thực nghiệm các mô hình Router và ghi chú v3.2
│
├── data/                       # Dữ liệu kiểm chuẩn & Bộ test case HITL
│   └── golden_full_suite.json  # 113 Test Cases HITL đã được thẩm định
│
├── evaluations/                # Công cụ đánh giá chất lượng Text-to-SQL và RAG
│   └── ...
│
└── blueprints/                 # 11 Hồ sơ thiết kế kiến trúc hệ thống
    └── README.md
```

---

## 🚀 Khởi Động Nhanh (Quick Start)

Mọi thao tác thực thi phải sử dụng môi trường Python ảo `.venv`:

```powershell
# 1. Khởi động máy chủ Backend (FastAPI + Uvicorn Auto-reload)
.\.venv\Scripts\python.exe -m IPGov_Chatbot.run_server

# 2. Truy cập trực tiếp các dịch vụ:
#    - Test Bench UI:     http://127.0.0.1:8000/bench
#    - Swagger Docs:      http://127.0.0.1:8000/docs
#    - Sức khỏe hệ thống: http://127.0.0.1:8000/api/v1/health
```

---

## 🧪 Chạy Kiểm Thử Tự Động (Test Suites)

```powershell
# Chạy toàn bộ 175 test cases tích hợp của IPGov Chatbot (100% PASS):
.\.venv\Scripts\python.exe -m pytest IPGov_Chatbot/tests/ -v
```

---

## 📚 Tài Liệu Tham Chiếu

- **Kế hoạch tổng thể & Bảng tiến độ:** [`docs/MASTER_PLAN_AND_PROGRESS_TRACKING.md`](docs/MASTER_PLAN_AND_PROGRESS_TRACKING.md)
- **Hướng dẫn khởi chạy Backend & Test Bench:** [`docs/BACKEND_RUN_GUIDE.md`](docs/BACKEND_RUN_GUIDE.md)
- **Đặc tả Module 1 (API Gateway):** [`docs/MODULE_01_GATEWAY_SPEC.md`](docs/MODULE_01_GATEWAY_SPEC.md)
- **Đặc tả Module 2 (Security Guardrails):** [`docs/MODULE_02_GUARDRAILS_SPEC.md`](docs/MODULE_02_GUARDRAILS_SPEC.md)
- **Đặc tả Module 3 (SSOT Groq Router & H-DFT):** [`docs/MODULE_03_ROUTER_SPEC.md`](docs/MODULE_03_ROUTER_SPEC.md)
- **Báo cáo benchmark thực nghiệm Router Models:** [`docs/ROUTER_MODEL_BENCHMARK.md`](docs/ROUTER_MODEL_BENCHMARK.md)
- **Quy chuẩn lập trình bắt buộc:** [`.agents/rules/ipgov-coding-rules.md`](../.agents/rules/ipgov-coding-rules.md)
- **Hồ sơ thiết kế kiến trúc Blueprints:** [`blueprints/README.md`](blueprints/README.md)
