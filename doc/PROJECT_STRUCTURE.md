# CẤU TRÚC DỰ ÁN IPGOV CHATBOT (PROJECT STRUCTURE)

> [!NOTE]
> Tài liệu định vị tài nguyên và phân bổ thư mục chính thức của hệ thống `IPGov_Chatbot`.
> Tuân thủ nguyên tắc Đơn mục đích (Single-Purpose Principle).

---

## 1. Bản Đồ Phân Bổ Thư Mục Cốt Lõi

```
Chatbot_Project/
├── .agents/                          # Bộ quy tắc quản trị agent, context & memory rules
├── backend/                          # Backend gốc (Config SSOT, FastAPI core)
├── data/                             # Dữ liệu nguồn, golden datasets & vector store
│   └── logs/                         # File log sự cố DLQ fallback
├── IPGov_Chatbot/                    # Hệ thống Monolith IPGov Chatbot 8 Modules
│   ├── blueprints/                   # Nguồn chân lý duy nhất (SSOT Blueprints 00 - 10)
│   ├── docs/                         # Tài liệu đặc tả kỹ thuật, hướng dẫn & master plan
│   │   ├── MODULE_01_GATEWAY_SPEC.md
│   │   ├── MODULE_02_GUARDRAILS_SPEC.md
│   │   ├── MODULE_03_ROUTER_SPEC.md
│   │   ├── MODULE_04_CATALOG_SPEC.md
│   │   ├── MODULE_05_SQL_COMPILER_SPEC.md
│   │   ├── MODULE_06_AST_ENFORCER_SPEC.md
│   │   ├── MODULE_07_DWH_EXEC_SPEC.md
│   │   ├── MODULE_08_RESPONSE_SYNTHESIZER_SPEC.md
│   │   ├── BACKEND_RUN_GUIDE.md
│   │   ├── MASTER_PLAN_AND_PROGRESS_TRACKING.md
│   │   └── TEST_CASES_GENEALOGY_AND_MAPPING_GUIDE.md
│   ├── modules/                      # Mã nguồn 8 Modules chuyên biệt
│   │   ├── mod01_gateway/            # Module 01: JWT, Context Extraction, SSE Stream
│   │   ├── mod02_guardrails/         # Module 02: Pre-router PII, DDL/DML, Scope check
│   │   ├── mod03_router/             # Module 03: Intent Router & H-DFT State Machine
│   │   ├── mod04_catalog/            # Module 04: In-Memory Catalog FTS & Steiner Tree
│   │   ├── mod05_sql_compiler/       # Module 05: Track A/B Adaptive SQL Compiler
│   │   ├── mod06_ast_enforcer/       # Module 06: Security Guardrails & AST Enforcer
│   │   │   ├── ast_enforcer_service.py
│   │   │   └── scope_visitor.py
│   │   ├── mod07_dwh_exec/           # Module 07: DWH Execution Engine (Docker PostgreSQL)
│   │   │   ├── connection_pool.py
│   │   │   ├── dlq_incident_logger.py
│   │   │   └── dwh_exec_service.py
│   │   └── mod08_response/           # Module 08: Response Synthesizer & Lineage Badge
│   │       ├── jinja_slot_engine.py
│   │       ├── llm_synthesizer.py
│   │       ├── lineage_badge_builder.py
│   │       └── response_synthesizer_service.py
│   ├── schemas/                      # Khế ước dữ liệu DTO Pydantic v2
│   │   ├── response_synthesizer_dto.py # DTO Module 08
│   │   ├── ast_enforcer_dto.py       # DTO Module 06
│   │   ├── dwh_exec_dto.py           # DTO Module 07
│   │   ├── sql_compiler_schema.py    # DTO Module 05
│   │   ├── catalog_dto.py            # DTO Module 04
│   │   ├── router_dto.py             # DTO Module 03
│   │   └── user_context.py           # DTO Module 01
│   ├── tests/                        # Hệ thống kiểm thử phân tầng (Tier 1, 2, 3)
│   │   ├── snapshots/                # Baselines lưu vết Stage 1 -> Stage 7
│   │   │   ├── stage_1_gateway/
│   │   │   ├── stage_2_prerouter/
│   │   │   ├── stage_3_router_hdft/
│   │   │   ├── stage_4_catalog/
│   │   │   ├── stage_5_sql_gen/
│   │   │   ├── stage_6_ast_enforcer/
│   │   │   ├── stage_7_dwh_exec/
│   │   │   └── stage_8_synthesizer/
│   │   ├── test_mod06_ast_enforcer.py
│   │   ├── test_mod07_dwh_exec.py
│   │   ├── test_mod08_response.py
│   │   ├── test_chained_snapshots_mod06_07.py
│   │   ├── test_chained_snapshots_all_8_stages.py
│   │   └── test_stream_pipeline_integration.py
│   └── main.py                       # Điểm khởi chạy ứng dụng FastAPI & Lifespan
└── frontend/                         # Giao diện người dùng Next.js / React
```
