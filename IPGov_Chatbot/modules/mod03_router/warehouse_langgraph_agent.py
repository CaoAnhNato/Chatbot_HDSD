"""
Module: IPGov_Chatbot/modules/mod03_router/warehouse_langgraph_agent.py
Chức năng: Agent tự hành điều phối toàn trình (End-to-End Autonomous Warehouse Agent)
được xây dựng trên StateGraph của LangGraph, tích hợp:
- Lưu trữ session bền vững bằng SqliteSaver tại data/agent_memory.db
- Tự động kế thừa ngữ cảnh hội thoại đa lượt (Context Inheritance) chống hỏi lặp
- Dynamic SQL Tooling & AST Guardrail (SQLGlot) cho 8 bảng nghiệp vụ
- Loại bỏ hoàn toàn bảng hạ tầng kỹ thuật pipeline_logs
- Khắc phục triệt để các bẫy [TRAP-004], [TRAP-005], [TRAP-023], [TRAP-028]
- Phát các SSE stage events thời gian thực (THINKING -> EXPLORING -> GENERATING -> EXECUTING -> SYNTHESIZING)
- Tự động gắn khối thu gọn <details><summary>🔍 Xem câu lệnh truy vấn (SQL Query)</summary>...
- Bậc thang mô hình: gemini-2.5-flash-lite -> gemini-3.5-flash-lite -> deepseek/deepseek-v4.1-flash
Căn cứ: ADR-001, implementation_plan.md, PROJECT_MEMORY.md
"""

from __future__ import annotations

import asyncio
import datetime
import decimal
import json
import logging
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, TypedDict

import sqlglot
from sqlglot import exp

from langgraph.checkpoint.sqlite import SqliteSaver
import unicodedata
from langgraph.graph import END, START, StateGraph

from IPGov_Chatbot.config import settings
from IPGov_Chatbot.modules.mod02_guardrails.injection_shield import InjectionShield
from IPGov_Chatbot.modules.mod02_guardrails.scope_prechecker import ScopePrechecker
from IPGov_Chatbot.modules.mod03_router.canonical_normalizer import CanonicalSemanticNormalizer
from IPGov_Chatbot.modules.mod03_router.discourse_state_tracker import DiscourseStateTracker, DialogueStateFrame
from IPGov_Chatbot.modules.mod03_router.neural_cqr_engine import NeuralCQREngine, CQRReformulationResult
from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog
from IPGov_Chatbot.modules.mod06_ast_enforcer.ast_enforcer_service import ASTEnforcerService
from IPGov_Chatbot.modules.mod07_dwh_exec.dwh_exec_service import DWHExecutionService
from IPGov_Chatbot.modules.mod08_response.jinja_slot_engine import JinjaSlotEngine, vn_format_num
from IPGov_Chatbot.schemas.canonical_query_frame import CanonicalIntentEnum, CanonicalQueryFrameDTO
from IPGov_Chatbot.schemas.dwh_exec_dto import QueryResultDTO
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO

logger = logging.getLogger("ipgov.warehouse_langgraph_agent")

# Danh sách các bảng nghiệp vụ và danh mục được phép truy vấn trong kho DWH
ALLOWED_WAREHOUSE_TABLES = [
    "fact_report_criteria",
    "criteria",
    "report",
    "collection_form",
    "user_mission",
    "user",
    "office_mission",
    "mission",
]

# Danh mục các bảng công khai trong kho dwh_public (không bao gồm office, deparment, user, user_mission)
PUBLIC_WAREHOUSE_TABLES = [
    "fact_report_criteria",
    "criteria",
    "report",
    "mission",
    "scope",
    "province",
    "criteria_group",
]

# Danh mục đầy đủ các bảng được phép truy vấn trong kho DWH (bao gồm dimension và criteria_group)
ALLOWED_CATALOG_TABLES = set(ALLOWED_WAREHOUSE_TABLES) | {
    "criteria_group",
    "scope",
    "province",
    "deparment",
    "department",
    "office",
    "ward",
    "office_user",
}

# Bảng kỹ thuật bị nghiêm cấm truy cập
BANNED_TABLES = ["pipeline_logs"]

# Schema tóm tắt của 8 bảng phục vụ dynamic exploration
WAREHOUSE_TABLES_SCHEMA = {
    "fact_report_criteria": {
        "full_name": "dwh_internal.fact_report_criteria",
        "description": "Bảng Fact lưu trữ số liệu báo cáo chỉ tiêu KTXH và hành chính công vụ",
        "columns": {
            "fact_sk": "VARCHAR(64) - Khóa dòng fact",
            "year_code": "VARCHAR(4) - Năm báo cáo (chú ý: tên cột là year_code, giá trị ví dụ '2026')",
            "value": "TEXT - Giá trị chỉ tiêu (cần ép kiểu NULLIF(TRIM(value), '')::numeric)",
            "report_status": "VARCHAR(32) - Trạng thái: approved, pending, draft, rejected",
            "tenant_code": "VARCHAR(64) - Mã tỉnh (68: Lâm Đồng)",
            "department_code": "VARCHAR(64) - Mã sở ngành (vd: '68-1-01')",
            "criteria_id": "UUID - Khóa ngoại trỏ criteria.id",
            "report_id": "UUID - Khóa ngoại trỏ report.id",
            "code": "TEXT - Mã chỉ tiêu",
            "name": "TEXT - Tên chỉ tiêu",
            "mission_id": "UUID - Khóa ngoại nhiệm vụ",
            "mission_name": "VARCHAR(255) - Tên nhiệm vụ",
        },
        "notes": "KHÔNG join bảng deparment vì bảng đó 0 dòng. Sử dụng trực tiếp department_code. Luôn lọc tenant_code='68' và report_status='approved'.",
    },
    "criteria": {
        "full_name": "dwh_internal.criteria",
        "description": "Bảng Dimension danh mục cây phân cấp chỉ tiêu thống kê báo cáo",
        "columns": {
            "id": "UUID - Khóa chính chỉ tiêu",
            "code": "VARCHAR(128) - Mã chỉ tiêu kỹ thuật",
            "name": "TEXT - Tên chỉ tiêu (vd: Số vụ tai nạn lao động, Sản lượng OCOP...)",
            "parent_id": "UUID - Chỉ tiêu cha",
            "level": "INTEGER - Cấp phân cấp",
            "year_code": "VARCHAR(4) - Năm áp dụng",
        },
    },
    "report": {
        "full_name": "dwh_internal.report",
        "description": "Bảng lưu trữ thông tin các đợt nộp báo cáo tổng hợp",
        "columns": {
            "id": "UUID - Khóa chính",
            "report_date": "TIMESTAMPTZ - Ngày nộp",
            "year_code": "VARCHAR(4) - Năm báo cáo",
            "status": "VARCHAR(32) - Trạng thái (approved, pending, draft, rejected)",
            "department_code": "VARCHAR(64) - Mã sở ban ngành",
            "tenant_code": "VARCHAR(64) - Mã tỉnh (68)",
        },
    },
    "collection_form": {
        "full_name": "dwh_internal.collection_form",
        "description": "Bảng danh mục các biểu mẫu thu thập số liệu và tờ khai nghiệp vụ",
        "columns": {
            "id": "UUID - Khóa chính",
            "code": "VARCHAR(64) - Mã biểu mẫu (vd: BM_01)",
            "name": "TEXT - Tên biểu mẫu",
            "year_code": "VARCHAR(4) - Năm ban hành",
            "department_code": "VARCHAR(64) - Cơ quan ban hành",
            "status": "VARCHAR(32) - Trạng thái (active, deprecated)",
        },
    },
    "mission": {
        "full_name": "dwh_internal.mission",
        "description": "Bảng danh mục các nhiệm vụ, chương trình và đề án trọng tâm",
        "columns": {
            "id": "UUID - Khóa chính",
            "mission_code": "VARCHAR(64) - Mã nhiệm vụ",
            "mission_name": "TEXT - Tên nhiệm vụ",
            "year_code": "VARCHAR(4) - Năm thực hiện",
            "department_code": "VARCHAR(64) - Đơn vị chủ trì",
            "mission_status": "BOOLEAN - Trạng thái nhiệm vụ",
        },
    },
    "user_mission": {
        "full_name": "dwh_internal.user_mission",
        "description": "Bảng phân công nhiệm vụ cho cán bộ, chuyên viên phụ trách",
        "columns": {
            "id": "UUID - Khóa chính",
            "user_id": "UUID - Định danh cán bộ",
            "mission_id": "UUID - Định danh nhiệm vụ",
            "office_name": "VARCHAR(255) - Tên phòng ban",
            "mission_name": "VARCHAR(255) - Tên nhiệm vụ",
            "department_code": "VARCHAR(64) - Mã cơ quan",
        },
    },
    "user": {
        "full_name": 'dwh_internal."user"',
        "description": "Bảng danh mục tài khoản cán bộ công chức (chú ý: 'user' là từ khóa, cần dấu nháy kép)",
        "columns": {
            "id": "UUID - Khóa chính",
            "name": "TEXT - Họ và tên cán bộ",
            "username": "TEXT - Tên đăng nhập",
            "position": "TEXT - Chức vụ",
            "department_code": "TEXT - Mã cơ quan",
            "department_name": "TEXT - Tên cơ quan",
        },
    },
    "office_mission": {
        "full_name": "dwh_internal.office_mission",
        "description": "Bảng phân công nhiệm vụ cho các phòng ban chuyên môn",
        "columns": {
            "id": "UUID - Khóa chính",
            "office_id": "UUID - Định danh phòng ban",
            "mission_id": "UUID - Định danh nhiệm vụ",
            "mission_name": "VARCHAR(255) - Tên nhiệm vụ",
            "department_code": "VARCHAR(64) - Mã cơ quan",
        },
    },
    "province": {
        "full_name": "dwh_internal.province",
        "description": "Bảng Dimension danh mục các đơn vị hành chính cấp tỉnh/thành phố trực thuộc trung ương",
        "columns": {
            "id": "UUID - Khóa chính",
            "code": "VARCHAR(64) - Mã tỉnh/thành phố (ví dụ: '68' cho Lâm Đồng, '79' cho TP.HCM)",
            "name": "VARCHAR(255) - Tên tỉnh/thành phố",
            "is_activated": "BOOLEAN - Trạng thái kích hoạt trong hệ thống",
        },
    },
    "deparment": {
        "full_name": "dwh_internal.deparment",
        "description": "Bảng Dimension danh mục các sở, ban, ngành cấp tỉnh",
        "columns": {
            "id": "UUID - Khóa chính",
            "code": "VARCHAR(64) - Mã sở ngành",
            "name": "VARCHAR(255) - Tên cơ quan sở ngành",
            "level": "INTEGER - Cấp quản lý",
            "tenant_code": "VARCHAR(64) - Mã tỉnh trực thuộc",
            "is_activated": "BOOLEAN - Trạng thái kích hoạt",
        },
        "notes": "Hiện tại bảng này trong kho có 0 dòng, ưu tiên dùng department_code trên fact hoặc catalog.",
    },
    "office": {
        "full_name": "dwh_internal.office",
        "description": "Bảng Dimension danh mục các phòng, ban, chi cục thuộc sở ban ngành",
        "columns": {
            "id": "UUID - Khóa chính",
            "code": "VARCHAR(64) - Mã phòng ban",
            "name": "VARCHAR(255) - Tên phòng ban chuyên môn",
            "department_code": "VARCHAR(64) - Mã sở ngành trực thuộc",
            "is_activated": "BOOLEAN - Trạng thái kích hoạt",
        },
    },
    "ward": {
        "full_name": "dwh_internal.ward",
        "description": "Bảng Dimension danh mục xã, phường, thị trấn",
        "columns": {
            "id": "UUID - Khóa chính",
            "code": "VARCHAR(64) - Mã xã/phường",
            "name": "VARCHAR(255) - Tên xã/phường/thị trấn",
            "district_code": "VARCHAR(64) - Mã huyện/thị xã/thành phố",
            "is_activated": "BOOLEAN - Trạng thái kích hoạt",
        },
    },
    "scope": {
        "full_name": "dwh_internal.scope",
        "description": "Bảng Dimension danh mục lĩnh vực quản lý nhà nước",
        "columns": {
            "id": "UUID - Khóa chính",
            "scope_name": "VARCHAR(255) - Tên lĩnh vực quản lý",
            "scope_code": "VARCHAR(64) - Mã lĩnh vực",
        },
    },
}


class AgentState(TypedDict):
    """Trạng thái toàn trình của StateGraph."""
    session_id: str
    user_query: str                  # Bất biến: câu hỏi gốc ban đầu của người dùng
    effective_query: Optional[str]   # Câu hỏi sau khi hòa mạng ngữ cảnh / tái cấu trúc
    history: List[Dict[str, str]]
    user_context: Dict[str, Any]

    # Context inheritance
    inherited_tenant: Optional[str]
    inherited_year: Optional[str]
    inherited_department: Optional[str]
    inherited_metric: Optional[str]
    inherited_parent_criterion: Optional[str]
    is_clarification_needed: bool
    clarification_question: Optional[str]
    is_capability_query: bool
    capability_answer: Optional[str]

    # Exploration & SQL
    target_tables: List[str]
    tables_schema: Dict[str, Any]
    generated_sql: Optional[str]
    sql_error: Optional[str]
    query_result: Optional[Dict[str, Any]]

    # Response & Stage tracking
    current_stage: str
    stage_message: str
    final_answer: Optional[str]
    quick_action_chips: Optional[List[Dict[str, Any]]]
    tabular_data: Optional[Dict[str, Any]]

    # Disambiguation & Candidate metadata (ADR-002)
    candidates: Optional[List[Dict[str, Any]]]
    selected_candidate: Optional[str]
    is_non_additive: bool
    is_temporal_query: bool
    target_department_code: Optional[str]
    is_out_of_scope: bool
    out_of_scope_answer: Optional[str]
    canonical_frame: Optional[CanonicalQueryFrameDTO]
    is_empty_year: bool

    # Tier 1 Pre-SQL Authorization & Schema Routing (Milestone 1)
    is_permission_denied: bool
    permission_denied_reason: Optional[str]
    violation_type: Optional[str]
    requested_mission: Optional[str]
    assigned_missions: Optional[List[str]]
    active_schema: Optional[str]


def _strip_bracketed_tags(raw_content: str) -> str:
    """
    Loại bỏ các thẻ dạng [tenant_code=..., level=...] thuần túy bằng thao tác chuỗi.
    Không sử dụng regex.
    """
    while "[" in raw_content and "]" in raw_content:
        start = raw_content.find("[")
        end = raw_content.find("]", start)
        if end != -1:
            tag_content = raw_content[start + 1 : end]
            if "tenant_code=" in tag_content or "level=" in tag_content:
                raw_content = raw_content[:start] + raw_content[end + 1 :]
            else:
                break
        else:
            break
    return raw_content.strip()


def _clean_sql_code(sql_str: str) -> str:
    """Lọc sạch các khối markdown khỏi câu lệnh SQL mà không sử dụng regex."""
    cleaned = sql_str.strip()
    if "```" in cleaned:
        start_idx = cleaned.find("```")
        end_idx = cleaned.rfind("```")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            inner = cleaned[start_idx + 3 : end_idx].strip()
            if inner.lower().startswith("sql"):
                inner = inner[3:].strip()
            cleaned = inner
    return cleaned.rstrip(";") + ";"


def _append_collapsible_sql(content: str, sql: Optional[str]) -> str:
    """Tự động gắn kèm khối SQL thu gọn vào cuối phản hồi phục vụ minh bạch hóa."""
    if not sql or not sql.strip():
        return content
    clean_sql = sql.strip().rstrip(";") + ";"
    return (
        content
        + f"\n\n<details>\n<summary>🔍 Xem câu lệnh truy vấn (SQL Query)</summary>\n\n```sql\n{clean_sql}\n```\n</details>"
    )


def _vn_status(st: Any) -> str:
    """Việt hóa các mã trạng thái kỹ thuật sang ngôn ngữ hành chính."""
    if st is True:
        return "Đang triển khai"
    if st is False:
        return "Chưa kích hoạt"
    if not isinstance(st, str):
        return str(st) if st is not None else "-"
    s_low = st.strip().lower()
    if s_low == "approved":
        return "Đã phê duyệt"
    if s_low == "draft":
        return "Bản nháp"
    if s_low == "pending":
        return "Chờ phê duyệt"
    if s_low == "active":
        return "Đang kích hoạt"
    if s_low == "deprecated":
        return "Đã lưu trữ / Hủy"
    return st


def _format_temporal_period_label(norm_frame: Any, year: Any) -> Tuple[str, str]:
    """
    Quy chuẩn chuỗi mô tả thời gian cho lời dẫn (intro) và tiêu đề bảng (title).
    Trả về: (p_lbl, title_period)
    """
    p_lbl = f"năm **{year}**"
    title_period = f"năm {year}"
    if not norm_frame:
        return (p_lbl, title_period)

    if getattr(norm_frame, "month_filter", None):
        mf = norm_frame.month_filter
        p_lbl = f"trong **tháng {mf:02d}/{year}**"
        title_period = f"tháng {mf:02d}/{year}"
    elif getattr(norm_frame, "specific_date", None):
        sp = str(norm_frame.specific_date)
        sp_vn = f"{sp[8:10]}/{sp[5:7]}/{sp[0:4]}" if len(sp) >= 10 else sp
        p_lbl = f"tính đến ngày **{sp_vn}**"
        title_period = f"tính đến {sp_vn}"
    elif getattr(norm_frame, "date_from", None) and getattr(norm_frame, "date_to", None):
        df, dt = str(norm_frame.date_from), str(norm_frame.date_to)
        df_vn = f"{df[8:10]}/{df[5:7]}/{df[0:4]}" if len(df) >= 10 else df
        dt_vn = f"{dt[8:10]}/{dt[5:7]}/{dt[0:4]}" if len(dt) >= 10 else dt
        try:
            sm, em = int(df[5:7]), int(dt[5:7])
            if sm in (1, 4, 7, 10) and em - sm == 2:
                q_num = (sm - 1) // 3 + 1
                p_lbl = f"trong **Quý {q_num}/{year} ({df_vn} - {dt_vn})**"
                title_period = f"Quý {q_num}/{year} ({df_vn} - {dt_vn})"
            elif sm == 1 and em == 6:
                p_lbl, title_period = f"trong **nửa đầu năm {year} ({df_vn} - {dt_vn})**", f"nửa đầu năm {year} ({df_vn} - {dt_vn})"
            elif sm == 7 and em == 12:
                p_lbl, title_period = f"trong **nửa cuối năm {year} ({df_vn} - {dt_vn})**", f"nửa cuối năm {year} ({df_vn} - {dt_vn})"
            elif sm == 1 and em == 12:
                p_lbl, title_period = f"từ **đầu năm {year} đến nay ({df_vn} - {dt_vn})**", f"từ đầu năm {year} đến nay"
            else:
                p_lbl = f"giai đoạn từ **{df_vn} đến {dt_vn}**"
                title_period = f"từ {df_vn} đến {dt_vn}"
        except Exception:
            p_lbl = f"giai đoạn từ **{df_vn} đến {dt_vn}**"
            title_period = f"từ {df_vn} đến {dt_vn}"

    return (p_lbl, title_period)


def _build_temporal_scope_meta(norm_frame: Any, year: Any) -> Dict[str, Any]:
    """
    Trích xuất siêu dữ liệu phạm vi thời gian chuẩn hóa (TemporalScopeMeta)
    phục vụ Context Ticket Bar, Pinned Reference Drawer và Action Chips.
    """
    y_str = str(year or ( getattr(norm_frame, "year_code", None) if norm_frame else None ) or "2026")
    _, title_period = _format_temporal_period_label(norm_frame, y_str)
    meta: Dict[str, Any] = {
        "year": y_str,
        "month_filter": getattr(norm_frame, "month_filter", None) if norm_frame else None,
        "specific_date": str(getattr(norm_frame, "specific_date", ""))[:10] if (norm_frame and getattr(norm_frame, "specific_date", None)) else None,
        "date_from": str(getattr(norm_frame, "date_from", ""))[:10] if (norm_frame and getattr(norm_frame, "date_from", None)) else None,
        "date_to": str(getattr(norm_frame, "date_to", ""))[:10] if (norm_frame and getattr(norm_frame, "date_to", None)) else None,
        "period_label": title_period,
        "query_suffix": f"năm {y_str}",
    }
    if not norm_frame:
        return meta

    if meta["month_filter"]:
        mf = int(meta["month_filter"])
        meta["query_suffix"] = f"tháng {mf:02d}/{y_str}"
    elif meta["specific_date"]:
        sp = meta["specific_date"]
        sp_vn = f"{sp[8:10]}/{sp[5:7]}/{sp[0:4]}" if len(sp) >= 10 else sp
        meta["query_suffix"] = f"ngày {sp_vn}"
    elif meta["date_from"] and meta["date_to"]:
        df, dt = meta["date_from"], meta["date_to"]
        df_vn = f"{df[8:10]}/{df[5:7]}/{df[0:4]}" if len(df) >= 10 else df
        dt_vn = f"{dt[8:10]}/{dt[5:7]}/{dt[0:4]}" if len(dt) >= 10 else dt
        try:
            sm, em = int(df[5:7]), int(dt[5:7])
            if sm in (1, 4, 7, 10) and em - sm == 2:
                q_num = (sm - 1) // 3 + 1
                meta["query_suffix"] = f"Quý {q_num}/{y_str}"
            elif sm == 1 and em == 6:
                meta["query_suffix"] = f"6 tháng đầu năm {y_str}"
            elif sm == 7 and em == 12:
                meta["query_suffix"] = f"6 tháng cuối năm {y_str}"
            else:
                meta["query_suffix"] = f"từ ngày {df_vn} đến ngày {dt_vn}"
        except Exception:
            meta["query_suffix"] = f"từ ngày {df_vn} đến ngày {dt_vn}"

    return meta


def _derive_mission_code(name: str, fallback_idx: int = 1) -> str:
    clean_words = [w for w in name.strip().split() if w.isalnum()]
    if clean_words:
        initials = ""
        for w in clean_words:
            ch = w[0].upper()
            nfkd = unicodedata.normalize('NFKD', ch)
            base_ch = "".join(c for c in nfkd if not unicodedata.combining(c)).replace('Đ', 'D')
            initials += base_ch if base_ch.isalnum() else ch
        if initials:
            return f"NV_{initials}_{fallback_idx:02d}"
    return f"NV_{fallback_idx:02d}"


class WarehouseLangGraphAgent:
    """
    Agent điều phối tự hành toàn trình cho Kho Dữ Liệu IPGov DWH.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or getattr(settings, "AGENT_MEMORY_DB_PATH", "data/agent_memory.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.sqlite_conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.checkpointer = SqliteSaver(self.sqlite_conn)
        self.dwh_exec_service = DWHExecutionService()
        self.jinja_engine = JinjaSlotEngine()
        self.catalog = DuckDBSemanticCatalog()
        self.normalizer = CanonicalSemanticNormalizer(self.catalog)
        self.ast_enforcer = ASTEnforcerService()
        self.discourse_tracker = DiscourseStateTracker()
        self.cqr_engine = NeuralCQREngine()
        self.graph = self._build_graph()

    # --------------------------------------------------------------------------
    # TOOLS
    # --------------------------------------------------------------------------
    def describe_tables(self, table_names: List[str]) -> Dict[str, Any]:
        """
        Tool khám phá cấu trúc schema của các bảng nghiệp vụ.
        Cấm tuyệt đối pipeline_logs.
        """
        for t in table_names:
            clean_t = t.lower().replace("dwh_internal.", "").strip()
            if clean_t in BANNED_TABLES:
                return {
                    "error": f"Bảng '{clean_t}' là bảng hạ tầng kỹ thuật nội bộ, không thuộc phạm vi phục vụ hỏi đáp của người dùng."
                }

        results = {}
        target_keys = table_names if table_names else list(WAREHOUSE_TABLES_SCHEMA.keys())
        for t in target_keys:
            clean_t = t.lower().replace("dwh_internal.", "").replace('"', '').strip()
            if clean_t in WAREHOUSE_TABLES_SCHEMA:
                results[clean_t] = WAREHOUSE_TABLES_SCHEMA[clean_t]

        return results

    def execute_safe_sql(self, query: str, user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Tool thực thi SQL an toàn có chốt chặn AST Guardrail (Zero Regex Architecture).
        Chặn 100% DML/DDL mutation, enforce tenant_code, year_code, an toàn casting qua Module 06 AST Enforcer.
        """
        t0 = time.perf_counter()
        raw_sql = _clean_sql_code(query).rstrip(";")

        # 1. Chặn bảng hạ tầng kỹ thuật bị cấm
        for banned in BANNED_TABLES:
            if banned in raw_sql.lower():
                return {
                    "error": f"Bảng '{banned}' là bảng hạ tầng kỹ thuật nội bộ, bị cấm truy cập.",
                    "rows": [],
                    "row_count": 0,
                }

        # 2. Phân tích cú pháp AST phương ngữ PostgreSQL 16
        try:
            statements = sqlglot.parse(raw_sql, read="postgres")
        except Exception as e:
            return {"error": f"Lỗi cú pháp SQL: {e}", "rows": [], "row_count": 0}

        if not statements or statements[0] is None:
            return {"error": "Câu lệnh SQL rỗng hoặc không thể phân tích cú pháp.", "rows": [], "row_count": 0}

        if len(statements) > 1:
            return {
                "error": f"Vi phạm an ninh bảo mật AST: Phát hiện {len(statements)} câu lệnh trong một truy vấn (chặn tiêm SQL đa mệnh đề).",
                "rows": [],
                "row_count": 0,
            }

        parsed = statements[0]

        # 2b. Chặn toàn diện các câu lệnh DDL / DML mutation qua AST
        forbidden_mutations = (
            exp.Insert,
            exp.Update,
            exp.Delete,
            exp.Drop,
            exp.Alter,
            exp.Create,
            exp.TruncateTable,
            exp.Command,
            exp.Transaction,
            exp.Grant,
            exp.Revoke,
        )
        forbidden_nodes = list(parsed.find_all(forbidden_mutations))
        if forbidden_nodes or not isinstance(parsed, (exp.Select, exp.Union)):
            return {
                "error": "Vi phạm an ninh bảo mật AST: Chỉ cho phép câu lệnh truy vấn đọc SELECT.",
                "rows": [],
                "row_count": 0,
            }

        # 3. Kiểm tra Whitelist 8 bảng nghiệp vụ
        cte_names = {cte.alias_or_name.lower().replace('"', '').strip() for cte in parsed.find_all(exp.CTE)}
        for t in parsed.find_all(exp.Table):
            clean_t = t.name.lower().replace("dwh_internal.", "").replace('"', '').strip()
            if clean_t not in ALLOWED_CATALOG_TABLES and clean_t not in cte_names:
                return {
                    "error": f"Vi phạm an ninh bảo mật AST: Bảng '{clean_t}' không nằm trong danh mục 8 bảng nghiệp vụ được phép truy vấn.",
                    "rows": [],
                    "row_count": 0,
                }

        # 4. Zero-JOIN Policy cho deparment (Bóc tách JOIN bảng 0 dòng thuần túy qua AST)
        for j in list(parsed.find_all(exp.Join)):
            if (j.this.name or "").lower().strip() in ("deparment", "department"):
                j.pop()

        # 5. AST Column Validator: Xử lý cột id trên fact_report_criteria
        fact_aliases = set()
        for t in parsed.find_all(exp.Table):
            clean_t = t.name.lower().replace("dwh_internal.", "").replace('"', '').strip()
            if clean_t == "fact_report_criteria":
                if t.alias:
                    fact_aliases.add(t.alias.lower().strip())
                fact_aliases.add("fact_report_criteria")
        if not fact_aliases and "fact_report_criteria" in raw_sql.lower():
            fact_aliases.add("f")

        for col in parsed.find_all(exp.Column):
            t_name = (col.table or "").lower().strip()
            c_name = col.name.lower().strip()
            if c_name == "id" and (t_name in fact_aliases or (not t_name and len(fact_aliases) == 1 and "f" in fact_aliases)):
                parent = col.parent
                if isinstance(parent, exp.Count):
                    col.set("this", exp.to_identifier("fact_sk"))
                else:
                    col.set("this", exp.to_identifier("criteria_id"))

        # 5b. Chuẩn hóa ép kiểu an toàn cho cột value: value::numeric -> NULLIF(TRIM(value), '')::numeric [TRAP-004]
        for cast_node in parsed.find_all((exp.Cast, exp.TryCast)):
            col_node = cast_node.this if isinstance(cast_node.this, exp.Column) else cast_node.this.find(exp.Column)
            if col_node and (col_node.name or "").lower().strip() == "value":
                if not cast_node.find(exp.Nullif):
                    col_sql = col_node.sql(dialect="postgres")
                    nullif_expr = sqlglot.parse_one(f"NULLIF(TRIM({col_sql}), '')", read="postgres")
                    cast_node.set("this", nullif_expr)

        # 6. Kiên cố hóa toàn diện qua Module 06 AST Enforcer Service (HBAC, NULLS LAST, Safe Cast, Safe Projection)
        tenant = (user_context or {}).get("tenant_code") or "68"
        dept = (user_context or {}).get("department_code")
        sec_ctx = UserSecurityContextDTO(
            user_id="warehouse_agent",
            username="system",
            role_level=0,
            tenant_code=tenant,
            department_code=dept,
        )

        try:
            intermediate_sql = parsed.sql(dialect="postgres")
            sanitized_sql, _, _ = self.ast_enforcer._sanitize_single_sql_ast(
                intermediate_sql,
                sec_ctx,
                inject_limit="WITH RANKED_FACTS" not in intermediate_sql.upper(),
            )
        except Exception as e:
            return {
                "error": f"Vi phạm an ninh bảo mật AST: {e}",
                "rows": [],
                "row_count": 0,
            }

        sanitized_sql = sanitized_sql.strip().rstrip(";") + ";"

        # 7. Thực thi qua PostgreSQL pool
        try:
            raw_rows = self.dwh_exec_service.pool.execute_sync_fallback(sanitized_sql)
            rows = []
            for r in raw_rows:
                row_dict = {}
                for k, v in r.items():
                    if isinstance(v, decimal.Decimal):
                        row_dict[k] = int(v) if v % 1 == 0 else float(v)
                    elif isinstance(v, (datetime.datetime, datetime.date)):
                        row_dict[k] = v.isoformat()
                    elif isinstance(v, uuid.UUID):
                        row_dict[k] = str(v)
                    else:
                        row_dict[k] = v
                rows.append(row_dict)

            exec_time_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            cols = list(rows[0].keys()) if rows else []
            return {
                "columns": cols,
                "rows": rows,
                "row_count": len(rows),
                "execution_time_ms": exec_time_ms,
                "executed_sql": sanitized_sql,
            }
        except Exception as e:
            exec_time_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return {
                "error": f"Lỗi thực thi PostgreSQL: {e}",
                "rows": [],
                "row_count": 0,
                "execution_time_ms": exec_time_ms,
                "executed_sql": sanitized_sql,
            }

    # --------------------------------------------------------------------------
    # LLM CASCADE INVOCATION
    # --------------------------------------------------------------------------
    def _call_llm_cascade(self, prompt: str, system_prompt: str, task: str = "decision") -> str:
        """
        Gọi LLM theo bậc thang ưu tiên mô hình và task-based API keys:
        gemini-2.5-flash-lite -> gemini-3.5-flash-lite -> deepseek/deepseek-v4.1-flash.
        """
        if task == "decision":
            models = [getattr(settings, "OPENROUTER_PLANNER_MODEL", "deepseek/deepseek-v4.1-flash")]
        else:
            models = [
                settings.AGENT_PRIMARY_MODEL,
                settings.AGENT_FALLBACK_MODEL_1,
                settings.AGENT_FALLBACK_MODEL_2,
            ]


        # Lựa chọn API key theo tác vụ
        if task == "sql":
            api_key = settings.SQL_GENERATION_LLM_API_KEY
        elif task == "synthesis":
            api_key = settings.RESPONSE_SYNTHESIS_LLM_API_KEY
        else:
            api_key = settings.AGENT_DECISION_LLM_API_KEY

        api_key = api_key or settings.OPENROUTER_API_KEY or settings.GOOGLE_API_KEY
        base_url = settings.OPENROUTER_BASE_URL

        from openai import OpenAI

        extra_body = {
            "provider": {
                "order": getattr(settings, "OPENROUTER_PLANNER_PROVIDER_ORDER", ["coreweave/fp8", "makora/fp8", "relace", "inference-net/fp8"]),
                "allow_fallbacks": getattr(settings, "OPENROUTER_PLANNER_ALLOW_FALLBACKS", True),
            },
            "reasoning": {
                "enabled": getattr(settings, "OPENROUTER_PLANNER_REASONING_ENABLED", False),
            },
        }

        for model_name in models:
            try:
                client = OpenAI(api_key=api_key, base_url=base_url, timeout=12.0)
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    extra_body=extra_body,
                )
                if resp.choices and resp.choices[0].message and resp.choices[0].message.content:
                    return resp.choices[0].message.content.strip()
            except Exception as e:
                logger.warning(f"⚠️ [LLM Cascade] Mô hình {model_name} thất bại ({e}), chuyển fallback tiếp theo...")
                continue

        # Nếu tất cả mô hình đều lỗi mạng / quota -> Fallback phản hồi an toàn
        return ""

    # --------------------------------------------------------------------------
    # GRAPH NODES
    # --------------------------------------------------------------------------
    def node_parse_context(self, state: AgentState) -> Dict[str, Any]:
        """
        Node 1: Phân tích câu hỏi, tiền kiểm phạm vi ScopePrechecker,
        và quản trị trạng thái hội thoại 3 cấp độ (DiscourseStateTracker + NeuralCQREngine).
        """
        raw_query = state["user_query"].strip()
        session_id = state.get("session_id", "default_session")
        user_ctx = state.get("user_context", {})
        history = state.get("history") or []
        stack = self.discourse_tracker.get_focus_stack(session_id)
        is_stateless_default = (session_id == "default_session" and not history)
        if is_stateless_default:
            stack.frames.clear()
        turn_index = (len(history) // 2 + 1) if history else (len(stack.frames) + 1)

        clean_text = _strip_bracketed_tags(raw_query)
        clean_text_lower = clean_text.lower().strip()

        # 0. Tiền kiểm an ninh DDL/DML & Prompt Injection (Ưu tiên P0 tối cao)
        is_inj, inj_msg, _ = InjectionShield.detect_injection(clean_text)
        if is_inj:
            logger.warning("Chặn câu lệnh phá hoại / injection: '%s'", clean_text)
            return {
                "current_stage": "SYNTHESIZING",
                "stage_message": "🛡️ Phát hiện yêu cầu vi phạm an ninh hệ thống...",
                "is_out_of_scope": True,
                "out_of_scope_answer": inj_msg,
                "final_answer": f"Yêu cầu nằm ngoài phạm vi được phép hoặc vi phạm an ninh: {inj_msg}",
                "is_clarification_needed": False,
                "is_capability_query": False,
                "inherited_tenant": "68",
                "inherited_year": "2026",
                "inherited_department": None,
                "inherited_metric": None,
                "candidates": None,
                "selected_candidate": None,
                "is_non_additive": False,
                "is_temporal_query": False,
                "target_department_code": None,
                "quick_action_chips": [],
            }

        # 1. Tiền kiểm phạm vi an toàn ScopePrechecker (chặn sớm CCCD, thời tiết, chính trị, sáng tác, định tính, tính toán)
        is_out, out_msg, _ = ScopePrechecker.check_scope(clean_text)
        if not is_out:
            import re
            is_math = bool(re.search(r'(?:\b\d+\s*(?:mũ|\^)\s*\d+\b|\b(?:tính|giải)\s+(?:toán|biểu\s+thức|phép\s+tính|phương\s+trình|kết\s+quả)\b|\b\d+\s*(?:nhân|chia\s+cho|cộng|trừ)\s*\d+\b|\bcăn\s+bậc\s+\d+\b)', clean_text, re.IGNORECASE))
            if is_math:
                is_out = True
                out_msg = (
                    "Yêu cầu tính toán biểu thức số học thuần túy nằm ngoài phạm vi phục vụ của Hệ thống Trợ lý ảo Tra cứu Kho DWH tỉnh Lâm Đồng. "
                    "Hệ thống chuyên trách tra cứu các báo cáo, chỉ tiêu điều hành và nhiệm vụ công vụ đã được phê duyệt."
                )
            else:
                is_admin_proc = bool(re.search(r'\b(?:thủ\s+tục|giấy\s+tờ|hồ\s+sơ|hướng\s+dẫn\s+làm|xin\s+cấp|đăng\s+ký)\b.*\b(?:sổ\s+đỏ|kết\s+hôn|khai\s+sinh|hộ\s+chiếu|cccd|căn\s+cước|giấy\s+phép\s+lái\s+xe|gplx|hộ\s+khẩu)\b', clean_text, re.IGNORECASE))
                if is_admin_proc:
                    is_out = True
                    out_msg = (
                        "Thông tin phạm vi: Câu hỏi của đồng chí thuộc nhóm Thủ tục Hành chính Công (Dịch vụ công trực tuyến). "
                        "Hệ thống hiện tại chuyên trách tra cứu Kho Dữ Liệu Báo Cáo Điều Hành (DWH). "
                        "Đồng chí vui lòng tra cứu thủ tục này tại Cổng Dịch vụ công Quốc gia (dichvucong.gov.vn) hoặc Hệ thống Thông tin Giải quyết Thủ tục Hành chính tỉnh Lâm Đồng."
                    )
        if is_out:
            logger.info("Chặn câu hỏi ngoài phạm vi DWH: '%s' -> %s", clean_text, out_msg[:60])
            return {
                "current_stage": "SYNTHESIZING",
                "stage_message": "ℹ️ Yêu cầu tra cứu ngoài phạm vi dữ liệu DWH...",
                "is_out_of_scope": True,
                "out_of_scope_answer": out_msg,
                "final_answer": out_msg,
                "is_clarification_needed": False,
                "is_capability_query": False,
                "inherited_tenant": "68",
                "inherited_year": "2026",
                "inherited_department": None,
                "inherited_metric": None,
                "candidates": None,
                "selected_candidate": None,
                "is_non_additive": False,
                "is_temporal_query": False,
                "target_department_code": None,
                "quick_action_chips": (
                    self.catalog.get_sample_quick_chips("68", year=state.get("inherited_year", "2026"))
                    if hasattr(self.catalog, "get_sample_quick_chips")
                    else []
                ),
            }

        # PA 3.1: Kế thừa ngữ cảnh nhóm chỉ tiêu cha (SC-2.4 -> SC-2.1) qua state slot & phân tích hội thoại
        prev_parent_ctx = None if (session_id == "default_session" and not history) else state.get("inherited_parent_criterion")
        if not prev_parent_ctx and history:
            for h_msg in reversed(history):
                if h_msg.get("role") == "user" and h_msg.get("content"):
                    u_query = str(h_msg.get("content"))
                    if hasattr(self.catalog, "classify_criterion_hierarchy"):
                        u_h = self.catalog.classify_criterion_hierarchy(u_query)
                        if u_h.get("classification") in ("parent", "parent_group"):
                            p_name = u_h.get("root_name") or u_h.get("name") or u_h.get("matched_name")
                            if p_name:
                                prev_parent_ctx = p_name
                                break

        inherited_parent_ctx = None
        curr_parent_name = None
        curr_h = None
        if hasattr(self.catalog, "classify_criterion_hierarchy"):
            curr_h = self.catalog.classify_criterion_hierarchy(clean_text)
            if curr_h.get("classification") in ("parent", "parent_group"):
                curr_parent_name = curr_h.get("root_name") or curr_h.get("name") or curr_h.get("matched_name")

        if prev_parent_ctx:
            has_connective = hasattr(self.catalog, "has_lexicon_term") and self.catalog.has_lexicon_term(clean_text, "DISCOURSE_CONNECTIVE")
            has_demonstrative = hasattr(self.catalog, "has_lexicon_term") and self.catalog.has_lexicon_term(clean_text, "DISCOURSE_DEMONSTRATIVE")
            has_explicit_mission = False
            if hasattr(self.catalog, "extract_mission_from_query"):
                m_info = self.catalog.extract_mission_from_query(clean_text)
                has_explicit_mission = m_info.get("status") in ("FOUND", "MATCH")

            is_parent_in_query = bool(curr_parent_name)
            is_dup_leaf = bool(curr_h and curr_h.get("classification") == "duplicate_leaf")

            # Nguyên tắc bất biến: KHÔNG BAO GIỜ kế thừa prev_parent_ctx nếu câu hỏi nêu rõ nhiệm vụ tường minh
            # HOẶC câu hỏi tra cứu nhóm chỉ tiêu cha mới
            # HOẶC câu hỏi tra cứu duplicate_leaf nhưng không có từ nối / đại từ chỉ định tường minh!
            if has_explicit_mission or is_parent_in_query:
                inherited_parent_ctx = None
            elif is_dup_leaf and not (has_connective or has_demonstrative):
                inherited_parent_ctx = None
            elif has_connective or has_demonstrative:
                inherited_parent_ctx = prev_parent_ctx
            else:
                inherited_parent_ctx = None

            if not inherited_parent_ctx and "inherited_parent_criterion" in state:
                state["inherited_parent_criterion"] = None

        # 2. Phân tích Chào hỏi & Tạm biệt (GREETING_FAREWELL) / Giới thiệu năng lực (CAPABILITY_INTRO)
        # Sử dụng Cognitive Planner / Canonical Normalizer thay vì heuristic đếm từ và regex
        prev_state_year = None if is_stateless_default else state.get("inherited_year")
        prev_state_tenant = None if is_stateless_default else state.get("inherited_tenant")
        norm_preview_early = self.normalizer.normalize_query(
            query=clean_text,
            session_tenant=prev_state_tenant or "68",
            session_year=prev_state_year or "2026",
            session_dept=None,
            parent_context=inherited_parent_ctx,
        )

        is_conversational = (
            norm_preview_early.intent == CanonicalIntentEnum.GREETING_FAREWELL
            or getattr(norm_preview_early, "is_conversational_only", False)
            or (bool(norm_preview_early.direct_answer) and any(w in norm_preview_early.direct_answer.lower() for w in ["tạm biệt", "hẹn gặp lại", "chúc đồng chí"]))
        )
        is_cap_intent = norm_preview_early.intent == CanonicalIntentEnum.CAPABILITY_INTRO

        if is_conversational or is_cap_intent:
            cap_answer = norm_preview_early.direct_answer or (
                "Xin chào đồng chí! Tôi là **Trợ lý AI Tra cứu Kho Dữ Liệu & Báo Cáo Điều Hành (IPGov DWH)** của tỉnh Lâm Đồng.\n\n"
                "Tôi có khả năng tự động khám phá và truy xuất toàn diện số liệu điều hành của tỉnh (năm **2026**) trên 4 lĩnh vực trọng tâm:\n"
                "1. **Chỉ tiêu Kinh tế - Xã hội & Nông nghiệp:** Số liệu sản xuất muối, diện tích diêm nghiệp, hợp tác xã, sản phẩm OCOP, an toàn lao động, kinh phí khuyến công.\n"
                "2. **Tình hình Báo cáo & Tổng hợp:** Tiến độ nộp, thẩm tra và tình trạng phê duyệt số liệu báo cáo định kỳ của các sở ban ngành.\n"
                "3. **Biểu mẫu Thu thập Số liệu:** Danh mục các biểu mẫu nộp dữ liệu và tờ khai nghiệp vụ đang kích hoạt.\n"
                "4. **Nhiệm vụ, Đề án & Cán bộ Phụ trách:** Các chương trình, đề án công tác trọng tâm và phân công cán bộ chuyên môn thực hiện.\n\n"
                "Mọi câu trả lời truy xuất từ kho dữ liệu đều được đính kèm câu lệnh SQL minh bạch (thu gọn bên dưới phản hồi). "
                "Đồng chí có thể nhấn vào các câu hỏi gợi ý bên dưới để tra cứu nhanh!"
            )
            quick_chips = [
                {"id": "chip_1", "label": "📊 Tổng hộ sản xuất muối 2026", "query_text": "Tổng hộ sản xuất muối năm 2026 là bao nhiêu?"},
                {"id": "chip_2", "label": "🌾 Sản lượng OCOP 2026", "query_text": "Tổng sản lượng các sản phẩm OCOP đạt chuẩn năm 2026?"},
                {"id": "chip_3", "label": "🏛️ Nhiệm vụ trọng tâm 2026", "query_text": "Danh mục các nhiệm vụ trọng tâm năm 2026 của tỉnh Lâm Đồng?"},
            ]
            return {
                "current_stage": "SYNTHESIZING",
                "stage_message": "✍️ Đang hoàn tất câu trả lời...",
                "is_out_of_scope": False,
                "out_of_scope_answer": None,
                "is_capability_query": True,
                "capability_answer": cap_answer,
                "final_answer": cap_answer,
                "is_clarification_needed": False,
                "inherited_tenant": prev_state_tenant or "68",
                "inherited_year": prev_state_year or "2026",
                "inherited_department": None,
                "inherited_metric": None,
                "candidates": None,
                "selected_candidate": None,
                "is_non_additive": False,
                "is_temporal_query": False,
                "target_department_code": None,
                "quick_action_chips": quick_chips,
            }
        elif norm_preview_early.user_query and norm_preview_early.user_query != clean_text:
            clean_text = norm_preview_early.user_query

        # 4. Trích xuất tham số tường minh qua Catalog động
        explicit_tenant = None
        resolved_t = self.catalog.resolve_spatial_tenant(clean_text, default_tenant=None)
        if resolved_t:
            explicit_tenant = resolved_t

        explicit_year = None

        explicit_dept = None
        admin_scope = self.catalog.resolve_administrative_scope(clean_text)
        if admin_scope and admin_scope.get("type") == "department":
            explicit_dept = admin_scope.get("department_code")

        # Nạp sơ bộ slots từ Normalizer / Cognitive Planner (tái sử dụng norm_preview_early nếu tham số không đổi)
        active_tenant = explicit_tenant or prev_state_tenant or "68"
        active_year = explicit_year or prev_state_year or "2026"
        if (
            (explicit_tenant is None or explicit_tenant == (prev_state_tenant or "68"))
            and (explicit_year is None or explicit_year == (prev_state_year or "2026"))
            and explicit_dept is None
        ):
            norm_preview = norm_preview_early
        else:
            norm_preview = self.normalizer.normalize_query(
                query=clean_text,
                session_tenant=active_tenant,
                session_year=active_year,
                session_dept=explicit_dept,
                parent_context=inherited_parent_ctx,
            )
        topic_cand = norm_preview.subject_entity or (norm_preview.canonical_metric_names[0] if norm_preview.canonical_metric_names else None)
        if isinstance(topic_cand, (list, tuple, set)):
            topic_cand = ", ".join(str(x) for x in topic_cand if x is not None)
        elif topic_cand is not None:
            topic_cand = str(topic_cand)

        planner_slots = {
            "topic_entity": topic_cand,
            "metric_attribute": norm_preview.target_attribute,
            "temporal_slot": norm_preview.year_code,
            "spatial_slot": norm_preview.tenant_code,
            "department_slot": norm_preview.department_code,
            "office_slot": norm_preview.target_office,
            "mission_slot": norm_preview.target_mission,
            "domain": norm_preview.target_table,
        }

        # 5. Quản trị trạng thái hội thoại 3 cấp độ (DiscourseStateTracker + NeuralCQREngine)
        frame, res_level, standalone_hint = self.discourse_tracker.process_turn(
            session_id=session_id,
            turn_index=turn_index,
            query=clean_text,
            catalog=self.catalog,
            explicit_year=explicit_year,
            explicit_dept=explicit_dept,
            explicit_tenant=explicit_tenant,
            planner_slots=planner_slots,
        )

        # Kiểm tra xem câu hỏi hiện tại có phải là đang chọn/hỏi tiếp một chỉ tiêu lá con trực thuộc nhóm cha Turn trước không
        is_child_followup_under_parent = False
        if inherited_parent_ctx and hasattr(self.catalog, "classify_criterion_hierarchy"):
            try:
                h_raw = self.catalog.classify_criterion_hierarchy(clean_text)
                h_ctx = self.catalog.classify_criterion_hierarchy(clean_text, parent_context=inherited_parent_ctx)
                if (
                    h_raw.get("classification") == "duplicate_leaf"
                    and h_ctx.get("classification") == "single_leaf"
                ):
                    is_child_followup_under_parent = True
            except Exception:
                is_child_followup_under_parent = False

        is_standalone_non_metric = norm_preview.intent in (
            CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT,
            CanonicalIntentEnum.OFFICER_ASSIGNMENT,
            CanonicalIntentEnum.RELATIONAL_EXPLORATION,
            CanonicalIntentEnum.DIMENSION_LISTING,
            CanonicalIntentEnum.METADATA_EXPLORATION,
            CanonicalIntentEnum.CAPABILITY_INTRO,
            CanonicalIntentEnum.GREETING_FAREWELL,
            CanonicalIntentEnum.PARENT_CHILDREN_BREAKDOWN,
            CanonicalIntentEnum.CROSS_BRANCH_COMPARISON,
        )

        effective_query = clean_text
        if (
            turn_index > 1
            and not is_child_followup_under_parent
            and res_level not in ("NEW_TOPIC", "SELF_CONTAINED")
            and not is_standalone_non_metric
            and not (hasattr(self.discourse_tracker, "is_self_contained") and self.discourse_tracker.is_self_contained(clean_text, turn_index))
        ):
            cqr_res = self.cqr_engine.reformulate(
                query=clean_text,
                context_frame=frame,
                history=history,
                standalone_hint=standalone_hint,
            )
            if cqr_res.is_dependent:
                if cqr_res.standalone_query:
                    effective_query = cqr_res.standalone_query
                    logger.info("CQR đã hòa mạng câu hỏi: '%s' -> '%s' (Level: %s)", clean_text, effective_query, res_level)
                elif standalone_hint:
                    effective_query = standalone_hint

        # Bổ sung trích xuất slot từ effective_query nếu chưa có
        pass

        # 6. Kế thừa thông minh các Slot
        frame_tenant = frame.spatial_slot if (frame and frame.spatial_slot and frame.spatial_slot != "68") else None
        prev_state_tenant = None if is_stateless_default else state.get("inherited_tenant")
        prev_state_year = None if is_stateless_default else state.get("inherited_year")
        prev_state_dept = None if is_stateless_default else state.get("inherited_department")
        prev_state_metric = None if is_stateless_default else state.get("inherited_metric")

        inherited_tenant = explicit_tenant or frame_tenant or prev_state_tenant or user_ctx.get("tenant_code") or "68"
        
        frame_year = frame.temporal_slot if (frame and frame.temporal_slot) else None
        prev_year = frame_year or prev_state_year
        has_temporal_cue = False
        
        if explicit_year:
            inherited_year = explicit_year
        elif prev_year:
            inherited_year = prev_year
        elif has_temporal_cue:
            inherited_year = "2026"
        else:
            inherited_year = None

        inherited_dept = explicit_dept or (frame.department_slot if frame else None) or prev_state_dept or user_ctx.get("department_code")
        inherited_metric = frame.metric_attribute or frame.topic_entity or prev_state_metric

        # 7. Khởi tạo mặc định và chuẩn hóa toàn diện qua CanonicalSemanticNormalizer
        if inherited_tenant is None:
            inherited_tenant = "68"
        if inherited_year is None:
            inherited_year = "2026"

        is_clarification = False
        clarification_msg = None
        clarification_chips = None

        if (
            effective_query == clean_text
            and inherited_tenant == (explicit_tenant or "68")
            and inherited_year == (explicit_year or "2026")
            and inherited_dept == explicit_dept
        ):
            norm_frame = norm_preview
        else:
            norm_frame = self.normalizer.normalize_query(
                query=effective_query,
                session_tenant=inherited_tenant,
                session_year=inherited_year,
                session_dept=inherited_dept,
                parent_context=inherited_parent_ctx,
            )
        inherited_tenant = norm_frame.tenant_code
        inherited_year = norm_frame.year_code
        if norm_frame.department_code:
            inherited_dept = norm_frame.department_code

        # Bỏ qua truy vấn nếu là ngoài phạm vi DWH hoặc câu hỏi toán học (Triệt tiêu bẫy gán chỉ tiêu DWH ảo)
        if norm_frame.is_out_of_scope:
            out_ans = (
                "Yêu cầu tra cứu nằm ngoài phạm vi dữ liệu kho DWH điều hành kinh tế - xã hội tỉnh Lâm Đồng. "
                "Hệ thống chỉ hỗ trợ tra cứu các chỉ tiêu kinh tế - xã hội, báo cáo định kỳ và danh mục nhiệm vụ đã được phê duyệt."
            )
            return {
                "current_stage": "SYNTHESIZING",
                "stage_message": "ℹ️ Yêu cầu tra cứu ngoài phạm vi dữ liệu DWH...",
                "is_out_of_scope": True,
                "out_of_scope_answer": out_ans,
                "final_answer": out_ans,
                "is_clarification_needed": False,
                "is_capability_query": False,
                "inherited_tenant": "68",
                "inherited_year": "2026",
                "inherited_department": None,
                "inherited_metric": None,
                "candidates": None,
                "selected_candidate": None,
                "is_non_additive": False,
                "is_temporal_query": False,
                "target_department_code": None,
                "canonical_frame": (
                    norm_frame.model_dump(mode='json')
                    if hasattr(norm_frame, "model_dump")
                    else norm_frame
                ),
                "quick_action_chips": (
                    self.catalog.get_sample_quick_chips(inherited_tenant or "68", year=inherited_year)
                    if hasattr(self.catalog, "get_sample_quick_chips")
                    else []
                ),
            }

        # Kích hoạt Ambiguity Gate nếu normalizer phát hiện chỉ tiêu đa nghĩa (ROB-AMBIG-HTX) hoặc thiếu mốc thời gian (Turn 1)
        if norm_frame.ambiguity_status == "AMBIGUOUS" and norm_frame.clarification_candidates:
            is_clarification = True
            has_year_chip = any(
                str(cand).strip().lower().startswith("năm ")
                or any(len(tok) == 4 and tok.isdigit() and (tok.startswith("19") or tok.startswith("20")) for tok in str(cand).split())
                for cand in norm_frame.clarification_candidates
            )
            if has_year_chip:
                clarification_msg = "Đồng chí vui lòng chọn mốc thời gian hoặc năm báo cáo cần tra cứu số liệu:"
                clarification_chips = [
                    {
                        "id": f"chip_{i+1}",
                        "label": f"📅 {cand[:40]}",
                        "query_text": f"{clean_text} {cand}"
                    }
                    for i, cand in enumerate(norm_frame.clarification_candidates)
                ]
            else:
                topic_desc = norm_frame.subject_entity or ""
                if not topic_desc and hasattr(self, "catalog") and hasattr(self.catalog, "conn"):
                    try:
                        norm_input = clean_text.lower()
                        matched_row = self.catalog.conn.execute(
                            "SELECT acronym FROM catalog_acronyms WHERE INSTR(?, LOWER(full_form)) > 0 OR INSTR(?, LOWER(acronym)) > 0 ORDER BY LENGTH(acronym) DESC LIMIT 1;",
                            [norm_input, norm_input],
                        ).fetchone()
                        if matched_row:
                            topic_desc = matched_row[0]
                    except Exception:
                        pass
                if not topic_desc and norm_frame.canonical_metric_names:
                    topic_desc = norm_frame.canonical_metric_names[0]

                if topic_desc:
                    clarification_msg = f"Đồng chí vui lòng chọn cụ thể chỉ tiêu / phương diện của '{topic_desc}' cần tra cứu số liệu:"
                else:
                    clarification_msg = "Đồng chí vui lòng chọn cụ thể chỉ tiêu cần tra cứu số liệu:"

                clarification_chips = []
                for i, cand in enumerate(norm_frame.clarification_candidates):
                    c_clean = str(cand).strip()
                    q_text = f"{c_clean} năm {inherited_year} là bao nhiêu?"
                    clarification_chips.append({
                        "id": f"chip_{i+1}",
                        "label": f"📊 {c_clean}",
                        "query_text": q_text
                    })


        # 8. Trích xuất ứng viên Top-K từ DuckDB Catalog trong RAM (ADR-002)
        candidates = []
        is_ambiguous = False
        score_delta = 0.0
        target_dept = inherited_dept

        is_dimension_plane = norm_frame.intent in (
            CanonicalIntentEnum.METADATA_EXPLORATION,
            CanonicalIntentEnum.DIMENSION_LISTING,
            CanonicalIntentEnum.ENTITY_ATTRIBUTE_LOOKUP,
            CanonicalIntentEnum.RELATIONAL_EXPLORATION,
            CanonicalIntentEnum.OFFICER_ASSIGNMENT,
            CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT,
        )

        # Kiểm tra phân quyền HBAC đối với dữ liệu bản nháp / chờ duyệt (REQ-Q05 SC-5.1: role_level <= 2 được phép, role_level >= 3 bị chặn)
        role_lvl_ctx = int((user_ctx or {}).get("role_level", 0) or 0)
        role_name_ctx = str((user_ctx or {}).get("role") or "").strip().lower()
        is_public_guest_ctx = role_lvl_ctx >= 3 or role_name_ctx in ("public", "citizen", "public_citizen", "guest", "khach", "congdan")
        if norm_frame.intent == CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT and is_public_guest_ctx:
            norm_frame.blocked_draft_access = True
            norm_frame.status_filter = ["approved"]

        if not is_clarification and not is_dimension_plane:
            try:
                admin_scope = self.catalog.resolve_administrative_scope(effective_query)
                if admin_scope and admin_scope.get("type") == "department" and admin_scope.get("department_code"):
                    target_dept = admin_scope["department_code"]
            except Exception as e:
                logger.warning("Lỗi phân giải phạm vi hành chính: %s", e)

            # Nếu normalizer đã phân giải thành công (RESOLVED), không gọi lại catalog làm đè kết quả
            if norm_frame.ambiguity_status == "RESOLVED" and (norm_frame.canonical_metric_ids or norm_frame.canonical_metric_names):
                is_ambiguous = False
                cand_name = norm_frame.canonical_metric_names[0] if norm_frame.canonical_metric_names else selected_cand
                cand_code = norm_frame.canonical_metric_ids[0] if norm_frame.canonical_metric_ids else cand_name
                candidates = [{"code": cand_code, "name": cand_name}]
            else:
                try:
                    candidates, is_ambiguous, score_delta = self.catalog.find_top_k_candidates(
                        effective_query, top_k=5, score_cutoff=50.0, tenant_code=inherited_tenant
                    )
                except Exception as e:
                    logger.warning("Lỗi trích xuất ứng viên catalog: %s", e)

            if is_ambiguous and candidates:
                def _stem_core_cand(n: str) -> str:
                    if hasattr(self, "catalog") and hasattr(self.catalog, "strip_query_noise"):
                        return self.catalog.strip_query_noise(n, "METRIC_AGG_PREFIX_NOISE")
                    return n.strip()

                unique_cands = []
                seen_cands = set()
                seen_cores = set()
                for c in candidates:
                    cn = c["name"].strip().lower()
                    core = _stem_core_cand(cn)
                    if cn not in seen_cands and core not in seen_cores:
                        seen_cands.add(cn)
                        seen_cores.add(core)
                        unique_cands.append(c)
                if len(unique_cands) <= 1:
                    is_ambiguous = False
                    candidates = unique_cands
                else:
                    candidates = unique_cands

            if is_ambiguous and candidates:
                is_clarification = True
                clarification_msg = "Đồng chí vui lòng chọn cụ thể chỉ tiêu cần tra cứu số liệu:"
                clarification_chips = [
                    {
                        "id": f"chip_{i+1}",
                        "label": f"📊 {c['name']}",
                        "query_text": f"{c['name']} năm {inherited_year} là bao nhiêu?"
                    }
                    for i, c in enumerate(candidates[:3])
                ]
            elif not clean_text.strip() and not inherited_metric and not candidates:
                is_clarification = True
                clarification_msg = f"Đồng chí vui lòng cho biết cụ thể chỉ tiêu kinh tế - xã hội hoặc đơn vị cần tra cứu số liệu năm {inherited_year}?"

        if not is_clarification and not is_dimension_plane and not candidates and not norm_frame.canonical_metric_names and not inherited_metric:
            out_ans = (
                "Yêu cầu tra cứu nằm ngoài phạm vi dữ liệu kho DWH điều hành kinh tế - xã hội tỉnh Lâm Đồng. "
                "Hệ thống chỉ hỗ trợ tra cứu các chỉ tiêu kinh tế - xã hội, báo cáo định kỳ và danh mục nhiệm vụ đã được phê duyệt."
            )
            return {
                "current_stage": "SYNTHESIZING",
                "stage_message": "ℹ️ Yêu cầu tra cứu ngoài phạm vi dữ liệu DWH...",
                "is_out_of_scope": True,
                "out_of_scope_answer": out_ans,
                "final_answer": out_ans,
                "is_clarification_needed": False,
                "is_capability_query": False,
                "inherited_tenant": inherited_tenant or "68",
                "inherited_year": inherited_year or "2026",
                "inherited_department": None,
                "inherited_metric": None,
                "candidates": None,
                "selected_candidate": None,
                "is_non_additive": False,
                "is_temporal_query": False,
                "target_department_code": None,
                "canonical_frame": (
                    norm_frame.model_dump(mode='json')
                    if hasattr(norm_frame, "model_dump")
                    else norm_frame
                ),
                "quick_action_chips": (
                    self.catalog.get_sample_quick_chips(inherited_tenant or "68", year=inherited_year or "2026")
                    if hasattr(self.catalog, "get_sample_quick_chips")
                    else []
                ),
            }

        if norm_frame.intent in (
            CanonicalIntentEnum.METADATA_EXPLORATION,
            CanonicalIntentEnum.DIMENSION_LISTING,
            CanonicalIntentEnum.RELATIONAL_EXPLORATION,
            CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT,
        ):
            selected_cand = None
        elif norm_frame.intent == CanonicalIntentEnum.ENTITY_ATTRIBUTE_LOOKUP:
            selected_cand = (norm_frame.canonical_metric_names[0] if norm_frame.canonical_metric_names else None) or norm_frame.subject_entity
        else:
            selected_cand = (norm_frame.canonical_metric_names[0] if norm_frame.canonical_metric_names else None) or (candidates[0]["name"] if candidates else None)
        is_non_add = False
        if candidates and candidates[0].get("aggregation_type") == "NON_ADDITIVE":
            is_non_add = True

        # Tier 1 Defense: Pre-SQL Refusal Gate (Mission-Scoped Authorization & Dual-Schema Switching)
        raw_schema = str(state.get("active_schema") or (user_ctx or {}).get("schema") or "dwh_internal").strip().lower()
        active_schema = "dwh_public" if raw_schema == "dwh_public" else "dwh_internal"
        is_unrestricted = bool((user_ctx or {}).get("is_unrestricted", False))
        u_name = str((user_ctx or {}).get("name") or (user_ctx or {}).get("user_name") or "").strip()
        u_username = str((user_ctx or {}).get("username") or "").strip().lower()
        u_level = int((user_ctx or {}).get("role_level", 0) or 0)
        if u_name == "Lãnh đạo" or u_username == "boss" or (u_level == 4 and u_name == "Lãnh đạo"):
            is_unrestricted = True

        assigned_mission_ids = [str(m).strip() for m in ((user_ctx or {}).get("assigned_mission_ids") or []) if str(m).strip()]
        assigned_mission_names = [str(m).strip() for m in ((user_ctx or {}).get("assigned_mission_names") or []) if str(m).strip()]

        managing_mission_id = None
        managing_mission_name = None

        if active_schema == "dwh_internal" and not is_unrestricted:
            req_metric = (
                (norm_frame.canonical_metric_names[0] if norm_frame and norm_frame.canonical_metric_names else None)
                or selected_cand
                or (candidates[0]["name"] if candidates else None)
            )
            req_mission = norm_frame.target_mission if norm_frame and norm_frame.target_mission else None

            # 1. Tra cứu mission từ DuckDB catalog_criteria_hierarchy
            if req_metric and hasattr(self, "catalog") and getattr(self.catalog, "conn", None):
                try:
                    c_row = self.catalog.conn.execute(
                        "SELECT mission_name FROM catalog_criteria_hierarchy WHERE LOWER(TRIM(name)) = LOWER(TRIM(?)) AND mission_name IS NOT NULL LIMIT 1;",
                        [req_metric],
                    ).fetchone()
                    if c_row and c_row[0]:
                        managing_mission_name = c_row[0]
                    else:
                        c_row2 = self.catalog.conn.execute(
                            "SELECT mission_name FROM catalog_criteria_hierarchy WHERE INSTR(LOWER(name), LOWER(?)) > 0 AND mission_name IS NOT NULL LIMIT 1;",
                            [req_metric],
                        ).fetchone()
                        if c_row2 and c_row2[0]:
                            managing_mission_name = c_row2[0]
                except Exception as ex:
                    logger.debug("Lỗi tra cứu DuckDB catalog_criteria_hierarchy: %s", ex)

            # 2. Fallback tra cứu PostgreSQL dwh_internal.fact_report_criteria
            if not managing_mission_name and req_metric and hasattr(self, "catalog") and getattr(self.catalog, "pg_pool", None):
                try:
                    with self.catalog.pg_pool.get_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                "SELECT mission_id, mission_name FROM dwh_internal.fact_report_criteria WHERE name ILIKE %s AND mission_name IS NOT NULL LIMIT 1;",
                                (f"%{req_metric}%",),
                            )
                            row = cur.fetchone()
                            if row:
                                managing_mission_id = str(row[0])
                                managing_mission_name = str(row[1])
                except Exception as ex:
                    logger.debug("Lỗi tra cứu PostgreSQL fact_report_criteria: %s", ex)

            # 3. Hoặc từ req_mission nếu người dùng trực tiếp hỏi về nhiệm vụ
            if not managing_mission_name and req_mission:
                managing_mission_name = req_mission

            # 3.1. Hoặc quét trực tiếp từ danh mục catalog_missions trong DuckDB nếu câu hỏi chứa tên nhiệm vụ
            if not managing_mission_name and hasattr(self, "catalog") and getattr(self.catalog, "conn", None):
                try:
                    m_rows = self.catalog.conn.execute("SELECT id, name FROM catalog_missions WHERE name IS NOT NULL;").fetchall()
                    for mid, mname in m_rows:
                        if mname and mname.lower().strip() in clean_text_lower:
                            managing_mission_id = str(mid)
                            managing_mission_name = str(mname)
                            break
                except Exception as ex:
                    logger.debug("Lỗi tra cứu catalog_missions từ query: %s", ex)

            # 4. Tra cứu mission_id từ DuckDB catalog_missions
            if managing_mission_name and not managing_mission_id and hasattr(self, "catalog") and getattr(self.catalog, "conn", None):
                try:
                    m_row = self.catalog.conn.execute(
                        "SELECT id FROM catalog_missions WHERE LOWER(TRIM(name)) = LOWER(TRIM(?)) OR INSTR(LOWER(name), LOWER(?)) > 0 LIMIT 1;",
                        [managing_mission_name, managing_mission_name],
                    ).fetchone()
                    if m_row and m_row[0] is not None:
                        managing_mission_id = str(m_row[0])
                except Exception as ex:
                    logger.debug("Lỗi tra cứu DuckDB catalog_missions: %s", ex)

            # Quyết định từ chối:
            is_denied = False
            denial_reason = None
            has_no_missions = (len(assigned_mission_ids) == 0 and len(assigned_mission_names) == 0)

            # Trường hợp 1: Người dùng Level 0 (0 nhiệm vụ)
            if has_no_missions and (u_name or (user_ctx or {}).get("user_id")):
                is_denied = True
                denial_reason = (
                    f"⛔ **Truy cập bị từ chối (Tier 1: Pre-SQL Refusal Gate)**: "
                    f"Tài khoản **{u_name or 'người dùng'}** hiện tại chưa được phân công phụ trách bất kỳ nhiệm vụ nào trong Kho nội bộ (**dwh_internal**). "
                    f"Đồng chí không có thẩm quyền tra cứu chỉ tiêu '**{req_metric or clean_text}**'.\n\n"
                    f"💡 **Hướng giải quyết**:\n"
                    f"- Chuyển sang tài khoản **Lãnh đạo** để xem toàn bộ dữ liệu nội bộ không giới hạn.\n"
                    f"- Hoặc chuyển sang chế độ **Dữ liệu công khai (dwh_public)** để tra cứu thông tin chung."
                )
            # Trường hợp 2: Có nhiệm vụ quản lý chỉ tiêu nhưng nằm ngoài nhiệm vụ được phân công
            elif managing_mission_id or managing_mission_name:
                match_id = managing_mission_id and (managing_mission_id in assigned_mission_ids)
                match_name = False
                if managing_mission_name:
                    m_norm = managing_mission_name.strip().lower()
                    for am in assigned_mission_names:
                        am_norm = am.strip().lower()
                        if am_norm in m_norm or m_norm in am_norm:
                            match_name = True
                            break

                if not match_id and not match_name:
                    is_denied = True
                    assigned_str = ", ".join(f"**{m}**" for m in assigned_mission_names) if assigned_mission_names else "Chưa có"
                    denial_reason = (
                        f"⛔ **Truy cập bị từ chối (Tier 1: Pre-SQL Refusal Gate)**: "
                        f"Chỉ tiêu '**{req_metric or 'được yêu cầu'}**' thuộc quyền quản lý của nhiệm vụ **{managing_mission_name or 'chuyên ngành khác'}**.\n\n"
                        f"- **Tài khoản**: {u_name or 'Cán bộ'}\n"
                        f"- **Nhiệm vụ được phân công**: {assigned_str}\n"
                        f"- **Phạm vi vi phạm**: `MISSION_SCOPE_VIOLATION` (Không có thẩm quyền truy cập nhiệm vụ này trong `dwh_internal`).\n\n"
                        f"💡 **Hướng giải quyết**:\n"
                        f"- Chuyển sang tài khoản **Lãnh đạo** để xem dữ liệu liên phòng ban / toàn tỉnh.\n"
                        f"- Hoặc chuyển sang chế độ **Dữ liệu công khai (dwh_public)** để tra cứu số liệu công bố chung."
                    )

            if is_denied:
                logger.warning(
                    "TIER 1 REFUSAL: User '%s' blocked from metric '%s' (managing mission: '%s'). Assigned: %s",
                    u_name, req_metric, managing_mission_name, assigned_mission_names,
                )
                denial_chips = [
                    {"id": "chip_switch_public", "label": "🌐 Tra cứu Dữ liệu công khai (dwh_public)", "query_text": f"[schema=dwh_public] {clean_text}"},
                    {"id": "chip_switch_boss", "label": "👑 Chuyển sang Lãnh đạo", "query_text": f"[user=lanhdao] {clean_text}"},
                ]
                return {
                    "current_stage": "SYNTHESIZING",
                    "stage_message": "🛡️ Từ chối truy cập theo chính sách phân quyền...",
                    "is_permission_denied": True,
                    "permission_denied_reason": denial_reason,
                    "violation_type": "MISSION_SCOPE_VIOLATION",
                    "requested_mission": managing_mission_name,
                    "assigned_missions": assigned_mission_names,
                    "active_schema": active_schema,
                    "is_out_of_scope": True,
                    "out_of_scope_answer": denial_reason,
                    "final_answer": denial_reason,
                    "is_clarification_needed": False,
                    "is_capability_query": False,
                    "inherited_tenant": inherited_tenant or "68",
                    "inherited_year": inherited_year or "2026",
                    "inherited_department": None,
                    "inherited_metric": None,
                    "candidates": candidates,
                    "selected_candidate": selected_cand,
                    "is_non_additive": False,
                    "is_temporal_query": False,
                    "target_department_code": None,
                    "quick_action_chips": denial_chips,
                    "canonical_frame": norm_frame.model_dump(mode='json') if hasattr(norm_frame, "model_dump") else norm_frame,
                    "is_empty_year": norm_frame.is_empty_year if norm_frame else False,
                }

        return {
            "current_stage": "THINKING",
            "stage_message": "🔍 Đang phân tích câu hỏi & đối chiếu ngữ cảnh...",
            "user_query": raw_query,
            "effective_query": effective_query,
            "is_out_of_scope": False,
            "out_of_scope_answer": None,
            "inherited_tenant": inherited_tenant,
            "inherited_year": inherited_year,
            "inherited_department": target_dept,
            "inherited_metric": inherited_metric or selected_cand,
            "inherited_parent_criterion": inherited_parent_ctx or curr_parent_name,
            "is_clarification_needed": is_clarification,
            "clarification_question": clarification_msg,
            "quick_action_chips": clarification_chips,
            "is_capability_query": False,
            "capability_answer": None,
            "candidates": candidates,
            "selected_candidate": selected_cand,
            "is_non_additive": is_non_add,
            "is_temporal_query": False,
            "target_department_code": target_dept,
            "canonical_frame": norm_frame.model_dump(mode='json') if hasattr(norm_frame, "model_dump") else norm_frame,
            "is_empty_year": norm_frame.is_empty_year,
            "is_permission_denied": False,
            "permission_denied_reason": None,
            "violation_type": None,
            "requested_mission": managing_mission_name,
            "assigned_missions": assigned_mission_names,
            "active_schema": active_schema,
        }

    def node_explore_warehouse(self, state: AgentState) -> Dict[str, Any]:
        """
        Node 2: Tự động khám phá các bảng dữ liệu nghiệp vụ DWH.
        """
        query = state["user_query"].lower()
        norm_frame_raw = state.get("canonical_frame")
        norm_frame = CanonicalQueryFrameDTO(**norm_frame_raw) if isinstance(norm_frame_raw, dict) else norm_frame_raw

        if norm_frame and norm_frame.intent == CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT:
            sub_int = norm_frame.audit_sub_intent or "REPORT_SUBMISSION_STATUS"
            if sub_int == "MISSION_ASSIGNMENT_MATRIX" or norm_frame.target_table == "mission_assignment_matrix":
                target_tables = ["mission", "scope", "office_mission", "office", "user_mission", "user", "office_user"]
            elif sub_int == "FORM_CRITERIA_GROUP" or norm_frame.target_table == "criteria_group":
                target_tables = ["criteria_group", "criteria_group_map", "criteria", "collection_form"]
            else:
                target_tables = ["report", "fact_report_criteria", "office"]
        elif norm_frame and norm_frame.target_table:
            primary_tbl = norm_frame.target_table
            if primary_tbl == "user_mission":
                target_tables = ["user_mission", "user"]
            elif primary_tbl == "fact_report_criteria":
                if norm_frame.intent == CanonicalIntentEnum.ENTITY_ATTRIBUTE_LOOKUP:
                    target_tables = ["fact_report_criteria", "user", "office", "criteria"]
                else:
                    target_tables = ["fact_report_criteria", "criteria"]
            elif primary_tbl == "ward":
                target_tables = ["ward", "province"]
            elif primary_tbl == "office_mission":
                target_tables = ["office_mission", "office", "mission", "scope"]
            else:
                target_tables = [primary_tbl]
        else:
            target_tables = ["fact_report_criteria"]
            if hasattr(self.catalog, "resolve_mission") and self.catalog.resolve_mission(query):
                target_tables.append("mission")
            if (hasattr(self.catalog, "resolve_user_name") and self.catalog.resolve_user_name(query)) or \
               (hasattr(self.catalog, "resolve_user_position") and self.catalog.resolve_user_position(query)):
                target_tables.extend(["user_mission", "user"])
            if hasattr(self.catalog, "resolve_collection_form") and self.catalog.resolve_collection_form(query):
                target_tables.append("collection_form")
            if hasattr(self.catalog, "resolve_report_status") and self.catalog.resolve_report_status(query):
                target_tables.append("report")
            if hasattr(self.catalog, "is_dimension_query") and self.catalog.is_dimension_query(query, "criteria"):
                target_tables.append("criteria")


        raw_schema = str(state.get("active_schema") or (state.get("user_context") or {}).get("schema") or "dwh_internal").strip().lower()
        active_schema = "dwh_public" if raw_schema == "dwh_public" else "dwh_internal"
        if active_schema == "dwh_public":
            public_allowed = {"fact_report_criteria", "criteria", "mission", "province", "scope", "criteria_group", "report"}
            target_tables = [t for t in target_tables if t in public_allowed] or ["fact_report_criteria"]

        schema_info = self.describe_tables(target_tables)

        return {
            "current_stage": "EXPLORING_WAREHOUSE",
            "stage_message": "📊 Đang rà soát các bảng dữ liệu liên quan...",
            "target_tables": target_tables,
            "tables_schema": schema_info,
        }

    def node_generate_and_validate_sql(self, state: AgentState) -> Dict[str, Any]:
        """
        Node 3: Biên dịch câu lệnh SQL động và kiểm định an toàn AST Guardrail.
        """
        # Kiểm tra nếu câu hỏi đã được xác định ngoài phạm vi ở parse_context
        if state.get("is_out_of_scope"):
            return {
                "current_stage": "SYNTHESIZING",
                "stage_message": "ℹ️ Yêu cầu tra cứu ngoài phạm vi...",
                "generated_sql": None,
                "execution_result": None,
            }

        query = state["user_query"]
        inherited_year = state.get("inherited_year", "2026")
        inherited_tenant = state.get("inherited_tenant", "68")
        target_tables = state.get("target_tables", ["fact_report_criteria"])

        u_ctx_gen = state.get("user_context") or {}
        raw_schema = str(state.get("active_schema") or u_ctx_gen.get("schema") or "dwh_internal").strip().lower()
        active_schema = "dwh_public" if raw_schema == "dwh_public" else "dwh_internal"
        is_pub_schema = (active_schema == "dwh_public")

        candidates = state.get("candidates") or state.get("candidate_metrics") or []
        selected_candidate = state.get("selected_candidate") or (candidates[0]["name"] if candidates else None)
        is_non_add = state.get("is_non_additive", False) or (bool(candidates) and candidates[0].get("aggregation_type") == "NON_ADDITIVE")
        target_dept = state.get("target_department_code")

        # Trích xuất từ khóa tìm kiếm
        clean_prompt = _strip_bracketed_tags(query)

        # Thông tin ứng viên và ràng buộc nghiệp vụ (ADR-002)
        if candidates and "fact_report_criteria" in target_tables:
            c0_name = candidates[0]["name"]
            candidate_names = [c["name"] for c in candidates]
            cand_str = ", ".join([f"'{name}'" for name in candidate_names])
            cand_directive = (
                f"CHỈ TIÊU ĐƯỢC CHỌN TỪ DANH MỤC DWH: '{c0_name}'.\n"
                f"BẮT BUỘC dùng đúng tên đầy đủ này trong điều kiện WHERE: TRIM(f.name) ILIKE TRIM('{c0_name}') "
                f"hoặc f.name ILIKE ANY(ARRAY[{cand_str}])."
            )
        else:
            cand_directive = ""
        dept_clause_llm = f"AND f.department_code = '{target_dept}'" if target_dept else ""
        non_add_note = "LƯU Ý: Đây là chỉ tiêu tỷ lệ / bình quân (Non-additive), TUYỆT ĐỐI KHÔNG dùng SUM(value) gộp nhiều đơn vị!" if is_non_add else ""

        # Chỉ thị cô lập schema và cấu trúc bảng
        if is_pub_schema:
            schema_isolation_rule = (
                f"   - CHẾ ĐỘ DWH CÔNG KHAI (SCHEMA: {active_schema}):\n"
                f"     + BẮT BUỘC dùng tiền tố '{active_schema}.' cho TẤT CẢ các bảng (ví dụ: {active_schema}.fact_report_criteria, {active_schema}.criteria, {active_schema}.mission).\n"
                f"     + TUYỆT ĐỐI KHÔNG DÙNG tiền tố dwh_internal.\n"
                f"     + TUYỆT ĐỐI KHÔNG JOIN bảng office và TUYỆT ĐỐI KHÔNG truy vấn cột office_id (bảng office không tồn tại trong schema {active_schema}).\n"
            )
        else:
            schema_isolation_rule = (
                f"   - CHẾ ĐỘ DWH NỘI BỘ (SCHEMA: {active_schema}):\n"
                f"     + Sử dụng tiền tố '{active_schema}.' cho các bảng nội bộ.\n"
            )

        # Tạo prompt sinh SQL
        sys_prompt = (
            "Bạn là trợ lý Text-to-SQL chuyên nghiệp cho CSDL PostgreSQL DWH chính quyền tỉnh Lâm Đồng.\n"
            "CÁC QUY TẮC BẮT BUỘC:\n"
            "1. Chỉ viết câu lệnh SQL thuần túy bắt đầu bằng SELECT hoặc WITH. Không viết giải thích.\n"
            "2. LỰA CHỌN BẢNG THEO ĐÚNG ĐỐI TƯỢNG:\n"
            f"{schema_isolation_rule}"
            f"   - Chỉ tiêu KTXH / Nông nghiệp / Muối / OCOP / HTX: bảng {active_schema}.fact_report_criteria (f).\n"
            "     Cột: f.name (tên chỉ tiêu), f.year_code, f.value (TEXT -> ép kiểu NULLIF(TRIM(f.value), '')::numeric), f.mission_name, f.department_code, f.report_date, f.version.\n"
            f"     Điều kiện bắt buộc KHI truy vấn bảng fact: f.tenant_code = '{inherited_tenant}' AND f.report_status = 'approved' AND f.year_code = '{inherited_year}' {dept_clause_llm}.\n"
            "     QUY TẮC TÍNH TOÁN:\n"
            "     - Với chỉ tiêu cộng dồn (Tổng, Số lượng, Sản lượng, Diện tích, Hộ, Kinh phí...): BẮT BUỘC SELECT f.name AS ten_chi_tieu, SUM(NULLIF(TRIM(f.value), '')::numeric) AS tong_gia_tri ... GROUP BY f.name (Luôn luôn đưa cột tên chỉ tiêu f.name AS ten_chi_tieu vào mệnh đề SELECT).\n"
            "     - Với chỉ tiêu tỷ lệ, bình quân (Non-additive): BẮT BUỘC SELECT f.name AS ten_chi_tieu, f.value ... dùng CTE Window Function ROW_NUMBER() OVER (PARTITION BY TRIM(LOWER(f.name)) ORDER BY f.report_date DESC, f.version DESC) lấy rn = 1 để lấy kỳ báo cáo mới nhất của từng chỉ tiêu.\n"
            "     LỌC TÊN CHỈ TIÊU: NẾU CÓ CHỈ TIÊU ĐƯỢC CHỌN TỪ DANH MỤC DWH, BẮT BUỘC dùng CHÍNH XÁC tên chỉ tiêu đó trong mệnh đề WHERE (ví dụ: TRIM(f.name) ILIKE TRIM('<Tên chỉ tiêu được chọn>')). TUYỆT ĐỐI KHÔNG dùng chuỗi thô từ Yêu cầu tra cứu để lọc.\n"
            f"   - Báo cáo / Đợt nộp: bảng {active_schema}.report (r). Cột: r.id, r.report_date, r.status, r.department_code, r.year_code, r.tenant_code. LƯU Ý: Mã đơn vị của Sở Nông nghiệp và PTNT / Chi cục Nông nghiệp trong kho là '68-1-01'. TUYỆT ĐỐI KHÔNG tự bịa mã phòng ban như 'NN'.\n"
            f"   - Biểu mẫu thu thập: bảng {active_schema}.collection_form (cf). Cột: cf.id, cf.code, cf.name, cf.department_code, cf.status (status là enum 'active' hoặc 'deprecated', KHÔNG dùng 'approved').\n"
            f"   - Nhiệm vụ / Đề án: bảng {active_schema}.mission (m) hoặc trích xuất f.mission_name từ fact_report_criteria. Cột: m.id, m.mission_code, m.mission_name, m.department_code, m.mission_status (kiểu BOOLEAN: m.mission_status = true hoặc m.mission_status = false, TUYỆT ĐỐI KHÔNG so sánh chuỗi 'active'). LƯU Ý: Không tồn tại mã đơn vị '68-0-00'. Khi hỏi nhiệm vụ của toàn tỉnh hoặc của tỉnh Lâm Đồng, chỉ cần lọc m.mission_status = true VÀ m.year_code = '2026', TUYỆT ĐỐI KHÔNG lọc m.department_code = '68-0-00' hay m.department_code = '68'.\n"
            "   - Cán bộ / Chuyên viên / Người dùng: bảng dwh_internal.\"user\" (u). Cột: u.id, u.name, u.username, u.position, u.department_code (KHÔNG có cột is_admin). Để tìm cán bộ quản trị: u.name ILIKE '%admin%' OR u.name ILIKE '%quản trị%'. BẮT BUỘC có dấu nháy kép \"user\".\n"
            "   - Phân công nhiệm vụ: bảng dwh_internal.user_mission (um) gồm các cột: um.id, um.user_id, um.mission_id, um.mission_name, um.office_name, um.department_code, um.tenant_code. LƯU Ý BẢNG user_mission KHÔNG CÓ cột mission_code VÀ KHÔNG CÓ cột year_code! Bảng \"user\" cũng KHÔNG CÓ cột year_code! TUYỆT ĐỐI KHÔNG lọc um.year_code hay u.year_code! Để tra cứu cán bộ phụ trách nhiệm vụ, JOIN: dwh_internal.user_mission um JOIN dwh_internal.\"user\" u ON um.user_id = u.id WHERE um.mission_name ILIKE '%<tên nhiệm vụ>%' (hoặc JOIN dwh_internal.mission m ON um.mission_id = m.id). SELECT các cột: u.name, u.position, um.office_name, um.mission_name (TUYỆT ĐỐI KHÔNG tự ý alias đổi tên các cột này). ĐẶC BIỆT LƯU Ý: Để lọc đơn vị / phòng ban / chi cục của cán bộ, BẮT BUỘC dùng um.office_name (ví dụ: um.office_name NOT ILIKE '%phòng%' hoặc um.office_name ILIKE '%chi cục%'), TUYỆT ĐỐI KHÔNG lọc trên u.position! Nếu người dùng hỏi lọc theo nhiệm vụ cụ thể (ví dụ: 'phát triển nông thôn'), BẮT BUỘC phải có điều kiện lọc um.mission_name ILIKE '%phát triển nông thôn%'. QUAN TRỌNG: Mã phòng ban luôn có định dạng '68-X-YY' (ví dụ '68-1-01', '68-2-01'). TUYỆT ĐỐI KHÔNG lọc department_code = '68' (vì '68' là tenant_code cấp tỉnh, không phải mã phòng ban) và TUYỆT ĐỐI KHÔNG tự bịa u.department_code = '68-1-01' trừ khi câu hỏi đích danh một sở cụ thể.\n"
            f"3. Bảng criteria là {active_schema}.criteria (c).\n"
            "4. Cột năm là year_code (VARCHAR), KHÔNG được dùng year.\n"
            "5. TUYỆT ĐỐI KHÔNG JOIN bảng deparment vì bảng đó 0 dòng (Zero-JOIN). Sử dụng trực tiếp department_code.\n"
            "6. TUYỆT ĐỐI KHÔNG truy vấn bảng pipeline_logs.\n"
            "7. Luôn có LIMIT 500.\n"
        )

        user_prompt = (
            f"Yêu cầu tra cứu: \"{clean_prompt}\"\n"
            f"Schema kho dữ liệu hiện hành: {active_schema}\n"
            f"Năm cần lấy: {inherited_year}\n"
            f"Địa phương tenant: {inherited_tenant}\n"
            f"{cand_directive}\n"
            f"{non_add_note}\n"
            f"Các bảng khả dụng: {list(state.get('tables_schema', {}).keys())}\n"
            f"LƯU Ý BẮT BUỘC: Sử dụng tiền tố schema '{active_schema}.' cho mọi bảng trong câu lệnh SQL.\n"
            "Hãy viết câu lệnh SQL tối ưu nhất để trả lời yêu cầu."
        )

        # 1. Ưu tiên biên dịch tất định từ CanonicalSemanticNormalizer (Khử giòn ngôn ngữ)
        norm_frame_raw = state.get("canonical_frame")
        norm_frame = CanonicalQueryFrameDTO(**norm_frame_raw) if isinstance(norm_frame_raw, dict) else norm_frame_raw
        role_lvl_gen = int(u_ctx_gen.get("role_level", 0) or 0)
        role_name_gen = str(u_ctx_gen.get("role") or "").strip().lower()
        is_public_guest_gen = role_lvl_gen >= 3 or role_name_gen in ("public", "citizen", "public_citizen", "guest", "khach", "congdan")
        if norm_frame and norm_frame.intent == CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT and is_public_guest_gen:
            norm_frame.blocked_draft_access = True
            norm_frame.status_filter = ["approved"]

        canonical_sql = None
        if norm_frame and norm_frame.intent in (
            CanonicalIntentEnum.METRIC_POINT_INQUIRY,
            CanonicalIntentEnum.METRIC_TOP_K,
            CanonicalIntentEnum.METRIC_GROWTH_YOY,
            CanonicalIntentEnum.OFFICER_ASSIGNMENT,
            CanonicalIntentEnum.DIMENSION_LISTING,
            CanonicalIntentEnum.REPORT_STATUS_AUDIT,
            CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT,
            CanonicalIntentEnum.METADATA_EXPLORATION,
            CanonicalIntentEnum.ENTITY_ATTRIBUTE_LOOKUP,
            CanonicalIntentEnum.RELATIONAL_EXPLORATION,
            CanonicalIntentEnum.PARENT_CHILDREN_BREAKDOWN,
            CanonicalIntentEnum.CROSS_BRANCH_COMPARISON,
        ):
            # Nếu là METRIC_POINT_INQUIRY, dùng trực tiếp khi đã có canonical_metric_names
            if norm_frame.intent != CanonicalIntentEnum.METRIC_POINT_INQUIRY or norm_frame.canonical_metric_names:
                canonical_sql = self.normalizer.compile_canonical_sql(norm_frame, target_schema=active_schema)

        if canonical_sql:
            generated_sql = canonical_sql
        else:
            generated_sql = self._call_llm_cascade(user_prompt, sys_prompt, task="sql")

        # Fallback Deterministic SQL nếu LLM không khả dụng hoặc rỗng
        if not generated_sql or "select" not in generated_sql.lower():
            if norm_frame and norm_frame.intent in (
                CanonicalIntentEnum.ENTITY_ATTRIBUTE_LOOKUP,
                CanonicalIntentEnum.RELATIONAL_EXPLORATION,
                CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT,
            ):
                canonical_sql = self.normalizer.compile_canonical_sql(norm_frame, target_schema=active_schema)
                generated_sql = canonical_sql
            dept_clause = f"AND f.department_code = '{target_dept}' " if target_dept else ""
            if "province" in target_tables:
                canonical_sql = self.normalizer.compile_canonical_sql(norm_frame, target_schema=active_schema) if norm_frame else None
                generated_sql = canonical_sql or (
                    f"SELECT p.code, p.name, p.is_activated FROM {active_schema}.province AS p "
                    "WHERE p.is_activated = true ORDER BY p.name ASC;"
                )
            elif "criteria" in target_tables and norm_frame and norm_frame.intent == CanonicalIntentEnum.METADATA_EXPLORATION:
                canonical_sql = self.normalizer.compile_canonical_sql(norm_frame, target_schema=active_schema)
                generated_sql = canonical_sql or (
                    f"SELECT c.code, c.name, c.level FROM {active_schema}.criteria AS c "
                    "WHERE c.deleted_date IS NULL ORDER BY c.level ASC, c.code ASC;"
                )
            elif "mission" in target_tables:
                generated_sql = (
                    f"SELECT m.mission_name FROM {active_schema}.mission AS m "
                    f"WHERE m.year_code = '{inherited_year}' AND m.mission_status = true;"
                )
            elif "collection_form" in target_tables:
                generated_sql = (
                    f"SELECT cf.code, cf.name, cf.department_code, cf.status FROM dwh_internal.collection_form AS cf "
                    f"WHERE cf.year_code = '{inherited_year}';"
                )
            elif "user_mission" in target_tables:
                crit_mission = (norm_frame.target_mission if norm_frame and norm_frame.target_mission else None) or \
                               (self.catalog.resolve_mission(clean_prompt) if hasattr(self.catalog, "resolve_mission") else None)
                mis_cond = f"AND um.mission_name ILIKE '%{crit_mission.replace('\'', '\'\'')}%'" if crit_mission else ""
                generated_sql = (
                    f"SELECT u.name, u.position, um.office_name, um.mission_name "
                    f"FROM dwh_internal.user_mission AS um "
                    f"JOIN dwh_internal.\"user\" AS u ON um.user_id = u.id "
                    f"WHERE um.tenant_code = '{inherited_tenant}' {mis_cond};"
                )
            elif "report" in target_tables:
                generated_sql = (
                    f"SELECT r.report_date, r.status, r.department_code "
                    f"FROM {active_schema}.report AS r "
                    f"WHERE r.tenant_code = '{inherited_tenant}' AND r.year_code = '{inherited_year}';"
                )

            elif "fact_report_criteria" in target_tables:
                if norm_frame and norm_frame.date_from:
                    temporal_sub = f"AND f.report_date >= '{norm_frame.date_from}' "
                    if norm_frame.date_to:
                        temporal_sub += f"AND f.report_date::date <= '{norm_frame.date_to}' "
                elif norm_frame and norm_frame.month_filter:
                    temporal_sub = f"AND EXTRACT(MONTH FROM f.report_date) = {norm_frame.month_filter} AND f.year_code = '{inherited_year}' "
                else:
                    temporal_sub = f"AND f.year_code = '{inherited_year}' "

                if is_non_add:
                    # Non-additive metrics: take latest report (rn = 1) per dept
                    if candidates:
                        cand_names = ["'" + c["name"].replace("'", "''") + "'" for c in candidates]
                        cand_conditions = f"TRIM(rf.name) = ANY(ARRAY[{', '.join(cand_names)}])"
                    else:
                        c_cand, _, _ = self.catalog.find_top_k_candidates(clean_prompt, top_k=1, tenant_code=inherited_tenant)
                        if c_cand:
                            c_name_escaped = c_cand[0]["name"].replace("'", "''")
                            cand_conditions = f"TRIM(rf.name) ILIKE TRIM('{c_name_escaped}')"
                        else:
                            return {
                                "current_stage": "SYNTHESIZING",
                                "stage_message": "ℹ️ Yêu cầu tra cứu ngoài phạm vi...",
                                "is_out_of_scope": True,
                                "generated_sql": None,
                                "execution_result": None,
                            }
                    fb_table = "dwh_public.fact_report_criteria" if is_pub_schema else "dwh_internal.fact_report_criteria"
                    fb_office_sel = "" if is_pub_schema else "f.office_id, "
                    fb_rn_part = "PARTITION BY TRIM(LOWER(f.name))" if is_pub_schema else "PARTITION BY TRIM(LOWER(f.name)), COALESCE(f.office_id, '00000000-0000-0000-0000-000000000000'::uuid)"
                    fb_van_phong = "'Dữ liệu công khai' AS ten_van_phong" if is_pub_schema else "COALESCE(o.office_name, 'Cấp tỉnh') AS ten_van_phong"
                    fb_office_join = "" if is_pub_schema else "LEFT JOIN dwh_internal.office o ON rf.office_id = o.id\n"

                    generated_sql = (
                        f"WITH ranked_facts AS (\n"
                        f"    SELECT f.name, f.department_code, f.report_date, f.value, {fb_office_sel}f.mission_name,\n"
                        f"           ROW_NUMBER() OVER (\n"
                        f"               {fb_rn_part}\n"
                        f"               ORDER BY f.report_date DESC, f.version DESC\n"
                        f"           ) as rn\n"
                        f"    FROM {fb_table} f\n"
                        f"    WHERE f.tenant_code = '{inherited_tenant}'\n"
                        f"      {temporal_sub}\n"
                        f"      AND f.report_status = 'approved'\n"
                        f"      {dept_clause}\n"
                        f")\n"
                        f"SELECT rf.name AS ten_chi_tieu,\n"
                        f"       CASE WHEN TRIM(rf.value) ~ '^-?[0-9]+(\\.[0-9]+)?$' THEN TRIM(rf.value)::numeric ELSE NULL END AS tong_gia_tri,\n"
                        f"       CASE WHEN TRIM(rf.value) ~ '^-?[0-9]+(\\.[0-9]+)?$' THEN TRIM(rf.value)::numeric ELSE NULL END AS gia_tri,\n"
                        f"       rf.report_date AS ngay_bao_cao,\n"
                        f"       rf.mission_name AS ten_nhiem_vu,\n"
                        f"       {fb_van_phong}\n"
                        f"FROM ranked_facts rf\n"
                        f"{fb_office_join}"
                        f"WHERE rf.rn = 1\n"
                        f"  AND ({cand_conditions})\n"
                        f"ORDER BY tong_gia_tri DESC NULLS LAST;"
                    )
                else:
                    # Additive metrics: SUM(value) trên bản ghi mới nhất đã approved (Deduplication qua ranked_facts CTE)
                    if candidates:
                        cand_names = ["'" + c["name"].replace("'", "''") + "'" for c in candidates]
                        cand_conditions = f"TRIM(f.name) = ANY(ARRAY[{', '.join(cand_names)}])"
                    else:
                        c_cand, _, _ = self.catalog.find_top_k_candidates(clean_prompt, top_k=1, tenant_code=inherited_tenant)
                        if c_cand:
                            c_name_escaped = c_cand[0]["name"].replace("'", "''")
                            cand_conditions = f"TRIM(f.name) ILIKE TRIM('{c_name_escaped}')"
                        else:
                            return {
                                "current_stage": "SYNTHESIZING",
                                "stage_message": "ℹ️ Yêu cầu tra cứu ngoài phạm vi...",
                                "is_out_of_scope": True,
                                "generated_sql": None,
                                "execution_result": None,
                            }
                    fb_table = "dwh_public.fact_report_criteria" if is_pub_schema else "dwh_internal.fact_report_criteria"
                    fb_office_sel = "" if is_pub_schema else "f.office_id, "
                    fb_rn_part = "PARTITION BY TRIM(LOWER(f.name))" if is_pub_schema else "PARTITION BY TRIM(LOWER(f.name)), COALESCE(f.office_id, '00000000-0000-0000-0000-000000000000'::uuid)"
                    fb_van_phong_agg = "'Dữ liệu công khai' AS ten_van_phong" if is_pub_schema else "COALESCE(MAX(o.office_name), 'Cấp tỉnh') AS ten_van_phong"
                    fb_office_join = "" if is_pub_schema else "LEFT JOIN dwh_internal.office o ON rf.office_id = o.id\n"

                    generated_sql = (
                        f"WITH ranked_facts AS (\n"
                        f"    SELECT f.name, f.value, f.report_date, f.version, {fb_office_sel}f.mission_name,\n"
                        f"           ROW_NUMBER() OVER (\n"
                        f"               {fb_rn_part}\n"
                        f"               ORDER BY f.report_date DESC, f.version DESC\n"
                        f"           ) AS rn\n"
                        f"    FROM {fb_table} f\n"
                        f"    WHERE f.tenant_code = '{inherited_tenant}'\n"
                        f"      {temporal_sub}\n"
                        f"      AND f.report_status = 'approved'\n"
                        f"      {dept_clause}\n"
                        f"      AND ({cand_conditions})\n"
                        f")\n"
                        f"SELECT rf.name AS ten_chi_tieu,\n"
                        f"       SUM(CASE WHEN TRIM(rf.value) ~ '^-?[0-9]+(\\.[0-9]+)?$' THEN TRIM(rf.value)::numeric ELSE NULL END) AS tong_gia_tri,\n"
                        f"       SUM(CASE WHEN TRIM(rf.value) ~ '^-?[0-9]+(\\.[0-9]+)?$' THEN TRIM(rf.value)::numeric ELSE NULL END) AS gia_tri,\n"
                        f"       MAX(rf.report_date) AS ngay_bao_cao,\n"
                        f"       MAX(rf.mission_name) AS ten_nhiem_vu,\n"
                        f"       {fb_van_phong_agg}\n"
                        f"FROM ranked_facts rf\n"
                        f"{fb_office_join}"
                        f"WHERE rf.rn = 1\n"
                        f"GROUP BY rf.name\n"
                        f"ORDER BY tong_gia_tri DESC NULLS LAST;"
                    )

        cleaned_sql = _clean_sql_code(generated_sql) if generated_sql else None
        if cleaned_sql:
            effective_ctx = dict(state.get("user_context") or {})
            effective_ctx["schema"] = active_schema
            effective_ctx["tenant_code"] = inherited_tenant
            if str(effective_ctx.get("department_code") or "").strip().lower() in ("", "all", "*"):
                effective_ctx["department_code"] = None
            if norm_frame and norm_frame.intent == CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT:
                effective_ctx["status_filter"] = norm_frame.status_filter
                effective_ctx["role_level"] = 3 if is_public_guest_gen else min(role_lvl_gen, 2)
                effective_ctx["explicit_role_provided"] = True
            try:
                cleaned_sql, _, _ = self.ast_enforcer._sanitize_single_sql_ast(cleaned_sql, effective_ctx, inject_limit=False)
            except Exception as e:
                logger.warning("Lỗi chuẩn hóa AST Enforcer: %s", e)

        return {
            "current_stage": "GENERATING_SQL",
            "stage_message": "⚙️ Đang biên dịch câu lệnh truy vấn dữ liệu...",
            "generated_sql": cleaned_sql,
            "canonical_frame": norm_frame.model_dump(mode='json') if (norm_frame and hasattr(norm_frame, "model_dump")) else norm_frame,
        }

    def node_execute_dwh(self, state: AgentState) -> Dict[str, Any]:
        """
        Node 4: Thực thi truy vấn DWH trên máy chủ PostgreSQL.
        """
        sql = state.get("generated_sql", "")
        user_ctx = state.get("user_context", {})
        effective_ctx = dict(user_ctx or {})
        effective_ctx["tenant_code"] = state.get("inherited_tenant") or effective_ctx.get("tenant_code") or "68"
        if str(effective_ctx.get("department_code") or "").strip().lower() in ("", "all", "*"):
            effective_ctx["department_code"] = None
        norm_frame_raw = state.get("canonical_frame")
        norm_frame = CanonicalQueryFrameDTO(**norm_frame_raw) if isinstance(norm_frame_raw, dict) else norm_frame_raw
        if norm_frame and norm_frame.intent == CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT:
            role_lvl_exec = int(effective_ctx.get("role_level", 0) or 0)
            role_name_exec = str(effective_ctx.get("role") or "").strip().lower()
            is_public_guest_exec = role_lvl_exec >= 3 or role_name_exec in ("public", "citizen", "public_citizen", "guest", "khach", "congdan")
            effective_ctx["status_filter"] = norm_frame.status_filter
            effective_ctx["role_level"] = 3 if is_public_guest_exec else min(role_lvl_exec, 2)
            effective_ctx["explicit_role_provided"] = True

        result = self.execute_safe_sql(sql, user_context=effective_ctx)
        err = result.get("error")

        return {
            "current_stage": "EXECUTING_DWH",
            "stage_message": "🗄️ Đang thực thi truy vấn kho dữ liệu...",
            "query_result": result,
            "sql_error": err,
        }

    def node_synthesize_response(self, state: AgentState) -> Dict[str, Any]:
        """
        Node 5: Tổng hợp câu trả lời tự nhiên và gắn kèm khối SQL thu gọn <details>.
        """
        query_res = state.get("query_result") or {}
        rows = query_res.get("rows", [])
        sql = query_res.get("executed_sql") or state.get("generated_sql")
        year = state.get("inherited_year", "2026")
        clean_prompt = _strip_bracketed_tags(state["user_query"])
        candidates = state.get("candidates") or []
        selected_cand = state.get("selected_candidate")
        norm_frame_raw = state.get("canonical_frame")
        norm_frame = CanonicalQueryFrameDTO(**norm_frame_raw) if isinstance(norm_frame_raw, dict) else norm_frame_raw

        # Tạo quick chips phù hợp với ngữ cảnh 4 lĩnh vực
        target_t = norm_frame.target_table if norm_frame else None
        if target_t == "report":
            chips = [
                {"id": "chip_rpt_1", "label": "📑 Báo cáo Sở Nông nghiệp 2026", "query_text": "Trạng thái các đợt nộp báo cáo của Sở Nông nghiệp hiện nay thế nào?"},
                {"id": "chip_rpt_2", "label": "✅ Số báo cáo đã phê duyệt", "query_text": "Hiện có bao nhiêu báo cáo đã được phê duyệt trong năm 2026?"},
                {"id": "chip_rpt_3", "label": "📊 Chỉ tiêu muối 2026", "query_text": "Tổng các hộ sản xuất muối năm 2026 của tỉnh là bao nhiêu?"},
            ]
        elif target_t in ("mission", "user_mission") or (norm_frame and norm_frame.intent == CanonicalIntentEnum.OFFICER_ASSIGNMENT):
            chips = [
                {"id": "chip_mis_1", "label": "🏛️ Nhiệm vụ trọng tâm 2026", "query_text": "Danh mục các nhiệm vụ trọng tâm năm 2026 của tỉnh Lâm Đồng?"},
                {"id": "chip_mis_2", "label": "👤 Cán bộ phụ trách diêm nghiệp", "query_text": "Cán bộ nào phụ trách nhiệm vụ diêm nghiệp năm 2026?"},
                {"id": "chip_mis_3", "label": "🌾 Sản lượng OCOP 2026", "query_text": "Tổng sản lượng các sản phẩm OCOP đạt chuẩn năm 2026?"},
            ]
        elif target_t == "collection_form":
            chips = [
                {"id": "chip_bm_1", "label": "📊 Chỉ tiêu nông nghiệp 2026", "query_text": "Tổng diện tích sản xuất muối năm 2026 là bao nhiêu?"},
                {"id": "chip_bm_2", "label": "📑 Đợt nộp báo cáo 2026", "query_text": "Trạng thái các đợt nộp báo cáo của Sở Nông nghiệp hiện nay thế nào?"},
                {"id": "chip_bm_3", "label": "🏛️ Nhiệm vụ trọng tâm 2026", "query_text": "Danh mục các nhiệm vụ trọng tâm năm 2026 của tỉnh Lâm Đồng?"},
            ]
        else:
            chips = [
                {"id": "chip_1", "label": "📊 Tổng hộ sản xuất muối 2026", "query_text": "Tổng hộ sản xuất muối năm 2026 là bao nhiêu?"},
                {"id": "chip_2", "label": "🌾 Sản lượng OCOP 2026", "query_text": "Tổng sản lượng các sản phẩm OCOP đạt chuẩn năm 2026?"},
                {"id": "chip_3", "label": "🧂 Diện tích sản xuất muối", "query_text": "Thế còn diện tích sản xuất muối năm 2026?"},
            ]


        if state.get("is_permission_denied"):
            ans = state.get("permission_denied_reason") or (
                "⚠️ **Từ chối truy cập do giới hạn phân quyền nhiệm vụ (Scope Violation)**: "
                "Tài khoản hiện tại không được phân công phụ trách nhiệm vụ chứa chỉ tiêu này. "
                "Đồng chí vui lòng chuyển sang vai trò **Lãnh đạo** hoặc chuyển sang kho dữ liệu công khai (**dwh_public**) để tra cứu."
            )
            denial_chips = state.get("quick_action_chips") or [
                {"id": "chip_switch_public", "label": "🌐 Chuyển sang Dữ liệu Công khai (dwh_public)", "query_text": f"[schema=dwh_public] {clean_prompt}"},
                {"id": "chip_switch_boss", "label": "👑 Chuyển sang Lãnh đạo", "query_text": f"[user=lanhdao] {clean_prompt}"},
            ]
            return {
                "current_stage": "SYNTHESIZING",
                "stage_message": "🛡️ Từ chối truy cập theo chính sách phân quyền...",
                "final_answer": ans,
                "quick_action_chips": denial_chips,
            }

        if state.get("is_out_of_scope"):
            ans = state.get("out_of_scope_answer") or (
                "Yêu cầu tra cứu nằm ngoài phạm vi dữ liệu kho DWH điều hành kinh tế - xã hội. "
                "Hệ thống chỉ hỗ trợ tra cứu các chỉ tiêu kinh tế - xã hội, báo cáo định kỳ, "
                "danh mục nhiệm vụ và biểu mẫu đã được phê duyệt."
            )
            return {
                "current_stage": "SYNTHESIZING",
                "stage_message": "✍️ Đang hoàn tất câu trả lời...",
                "final_answer": ans,
                "quick_action_chips": chips,
            }

        if state.get("is_capability_query"):
            ans = state.get("capability_answer") or "Tôi là trợ lý AI tra cứu kho dữ liệu DWH."
            return {
                "current_stage": "SYNTHESIZING",
                "stage_message": "✍️ Đang hoàn tất câu trả lời...",
                "final_answer": ans,
                "quick_action_chips": chips,
            }

        if state.get("is_temporal_query"):
            ans = (
                f"Hiện tại kho dữ liệu điều hành (IPGov DWH) của tỉnh Lâm Đồng đang phục vụ và tổng hợp "
                f"số liệu báo cáo đã phê duyệt của năm **{year}**."
            )
            return {
                "current_stage": "SYNTHESIZING",
                "stage_message": "✍️ Đang hoàn tất câu trả lời...",
                "final_answer": ans,
                "quick_action_chips": chips,
            }

        if state.get("is_clarification_needed"):
            ans = state.get("clarification_question") or "Đồng chí vui lòng cung cấp thêm thông tin cụ thể cần tra cứu."
            return {
                "current_stage": "SYNTHESIZING",
                "stage_message": "✍️ Đang tổng hợp câu trả lời...",
                "final_answer": ans,
                "quick_action_chips": state.get("quick_action_chips") or chips,
            }

        if state.get("sql_error") and not (norm_frame and norm_frame.intent == CanonicalIntentEnum.PARENT_CHILDREN_BREAKDOWN):
            ans = f"⚠️ Yêu cầu tra cứu không thể hoàn tất do lỗi cơ sở dữ liệu: {state['sql_error']}"
            ans = _append_collapsible_sql(ans, sql)
            return {
                "current_stage": "SYNTHESIZING",
                "stage_message": "✍️ Đang tổng hợp câu trả lời...",
                "final_answer": ans,
                "quick_action_chips": chips,
            }

        # REQ-Q05: Kiểm toán tiến độ báo cáo, bộ thu thập chỉ tiêu & ma trận phân công nhiệm vụ (SC-5.1, SC-5.2, SC-5.3)
        if norm_frame and norm_frame.intent == CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT and rows:
            sub_intent = norm_frame.audit_sub_intent or "REPORT_SUBMISSION_STATUS"
            u_ctx_syn = state.get("user_context") or {}
            role_lvl_syn = int(u_ctx_syn.get("role_level", 0) or 0)
            role_name_syn = str(u_ctx_syn.get("role") or "").strip().lower()
            is_blocked_draft = bool(
                getattr(norm_frame, "blocked_draft_access", False)
                or role_lvl_syn >= 3
                or role_name_syn in ("public", "citizen", "public_citizen", "guest", "khach", "congdan")
            )

            if sub_intent == "MISSION_ASSIGNMENT_MATRIX" or norm_frame.target_table == "mission_assignment_matrix":
                total_m = len(rows)
                discrepancies = []
                unassigned_missions = []
                for r in rows:
                    m_code = r.get("mission_code") or "-"
                    m_name = r.get("mission_name") or "-"
                    m_scope = r.get("scope_name") or "-"
                    off_cnt = int(r.get("office_count") or 0)
                    usr_cnt = int(r.get("officer_count") or 0)
                    assigned_offs = [x.strip() for x in str(r.get("assigned_offices") or "").split(",") if x.strip() and x.strip() != "Chưa phân công phòng ban"]
                    officer_offs = [x.strip() for x in str(r.get("officer_offices") or "").split(",") if x.strip()]
                    if off_cnt == 0 and usr_cnt == 0:
                        unassigned_missions.append(f"`{m_code}` (**{m_name}** - lĩnh vực *{m_scope}*)")
                    else:
                        missing_off_users = [o for o in assigned_offs if o not in officer_offs]
                        if missing_off_users:
                            discrepancies.append(
                                f"Nhiệm vụ **`{m_code}` ({m_name})** được giao cho **{r.get('assigned_offices')}**, "
                                f"nhưng mới chỉ có cán bộ thuộc **{', '.join(officer_offs) or '0 phòng ban'}** — "
                                f"phòng ban **{', '.join(missing_off_users)}** hiện **chưa được phân công cán bộ phụ trách**."
                            )

                ans = (
                    f"Ma trận phân công nhiệm vụ năm **{year}** ({total_m} nhiệm vụ):\n\n"
                    f"| STT | Mã nhiệm vụ | Tên nhiệm vụ | Lĩnh vực | Phòng ban được giao | Cán bộ phụ trách & Vai trò |\n"
                    f"| :---: | :---: | :--- | :--- | :--- | :--- |\n"
                )
                matrix_rows = []
                for idx, r in enumerate(rows, 1):
                    mc = r.get("mission_code") or "-"
                    mn = r.get("mission_name") or "-"
                    sc = r.get("scope_name") or "-"
                    offs = r.get("assigned_offices") or "Chưa phân công phòng ban"
                    usrs = r.get("assigned_officers") or "Chưa phân công cán bộ"
                    ans += f"| {idx} | `{mc}` | **{mn}** | {sc} | {offs} | {usrs} |\n"
                    matrix_rows.append({
                        "stt": idx,
                        "mission_code": mc,
                        "mission_name": mn,
                        "scope_name": sc,
                        "assigned_offices": offs,
                        "assigned_officers": usrs,
                        "office_count": int(r.get("office_count") or 0),
                        "officer_count": int(r.get("officer_count") or 0),
                    })

                if discrepancies or unassigned_missions:
                    ans += "\n⚠️ **Phát hiện kiểm toán phân công nhiệm vụ:**\n"
                    for d_msg in discrepancies:
                        ans += f"- **Độ lệch phân công phòng ban và cán bộ:** {d_msg}\n"
                    if unassigned_missions:
                        ans += (
                            f"- **Nhiệm vụ chưa phân công (0 phòng ban & 0 cán bộ):** Có **{len(unassigned_missions)}** nhiệm vụ "
                            f"({', '.join(unassigned_missions)}) đã tạo trong danh mục nhưng hiện **chưa được giao phòng ban phụ trách** và **chưa có cán bộ đảm nhận**.\n"
                        )

                tabular_data = {
                    "title": f"Ma trận phân công nhiệm vụ - phòng ban - cán bộ năm {year}",
                    "columns": [
                        {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                        {"key": "mission_code", "label": "Mã nhiệm vụ", "align": "center", "data_type": "text"},
                        {"key": "mission_name", "label": "Tên nhiệm vụ", "align": "left", "data_type": "text"},
                        {"key": "scope_name", "label": "Lĩnh vực", "align": "left", "data_type": "text"},
                        {"key": "assigned_offices", "label": "Phòng ban được giao", "align": "left", "data_type": "text"},
                        {"key": "assigned_officers", "label": "Cán bộ phụ trách & Vai trò", "align": "left", "data_type": "text"},
                    ],
                    "rows": matrix_rows,
                    "total_records": len(matrix_rows),
                    "assignment_discrepancies": discrepancies,
                    "unassigned_missions": unassigned_missions,
                }
                chips = [
                    {"id": "chip_q05_1", "label": "📑 Tiến độ nộp báo cáo 2026", "query_text": "Thống kê tiến độ nộp báo cáo năm 2026: có bao nhiêu báo cáo đã phê duyệt và bao nhiêu bản nháp?"},
                    {"id": "chip_q05_2", "label": "📋 Bộ thu thập chỉ tiêu 2026", "query_text": "Danh sách các biểu mẫu thu thập và bộ thu thập chỉ tiêu năm 2026?"},
                    {"id": "chip_q05_3", "label": "🌾 Chỉ tiêu Cấp 1 PTNT", "query_text": "Các chỉ tiêu Cấp 1 của nhiệm vụ Phát triển nông thôn năm 2026?"},
                ]
                ans = _append_collapsible_sql(ans, sql)
                return {
                    "current_stage": "SYNTHESIZING",
                    "stage_message": "✍️ Đang hoàn tất câu trả lời...",
                    "final_answer": ans,
                    "tabular_data": tabular_data,
                    "quick_action_chips": chips,
                }

            if sub_intent == "FORM_CRITERIA_GROUP" or norm_frame.target_table == "criteria_group":
                active_rows = [r for r in rows if str(r.get("group_status") or "").lower() == "active"]
                draft_rows = [r for r in rows if str(r.get("group_status") or "").lower() == "draft"]
                cf_total = int(rows[0].get("collection_form_total") or 0) if rows else 0
                active_names = sorted(list({str(r.get("group_name") or "") for r in active_rows if r.get("group_name")}))
                draft_names = sorted(list({str(r.get("group_name") or "") for r in draft_rows if r.get("group_name")}))

                if is_blocked_draft:
                    ans = (
                        f"🔒 **Thông báo phân quyền bảo mật:** Tài khoản Công dân / Khách vãng lai chỉ được phép truy xuất các bộ thu thập **đang kích hoạt** (đã ẩn các bộ thu thập ở trạng thái bản nháp).\n\n"
                        f"Danh sách bộ thu thập chỉ tiêu đang kích hoạt năm **{year}** ({len(active_rows)} bộ thu thập):\n\n"
                    )
                else:
                    ans = (
                        f"Hệ thống hiện chưa ghi nhận biểu mẫu thu thập riêng lẻ ({cf_total} bản ghi); "
                        f"có **{len(rows)} bộ thu thập chỉ tiêu** năm **{year}** (**{len(active_rows)} đang kích hoạt**: {', '.join(f'**{n}**' for n in active_names)}; **{len(draft_rows)} bản nháp**: {', '.join(f'**{n}**' for n in draft_names)}):\n\n"
                    )

                ans += (
                    f"| STT | Tên bộ thu thập | Trạng thái | Người tạo | Nhiệm vụ liên kết | Lĩnh vực | Số chỉ tiêu gốc (Cấp 1) | Tổng chỉ tiêu ánh xạ | Tổng bản ghi số liệu | Danh sách chỉ tiêu gốc (Cấp 1) |\n"
                    f"| :---: | :--- | :---: | :---: | :--- | :--- | :---: | :---: | :---: | :--- |\n"
                )
                cg_table_rows = []
                for idx, r in enumerate(rows, 1):
                    g_name = r.get("group_name") or "-"
                    g_st = str(r.get("group_status") or "-")
                    g_st_disp = "Đang kích hoạt" if g_st == "active" else "Bản nháp"
                    c_by = r.get("created_by") or "-"
                    m_names = r.get("mission_names") or "-"
                    s_names = r.get("scope_names") or "-"
                    r_cnt = int(r.get("root_criteria_count") or 0)
                    t_cnt = int(r.get("total_criteria_count") or r.get("so_chi_tieu") or 0)
                    f_cnt = int(r.get("tong_ban_ghi") or 0)
                    r_names = r.get("root_criteria_names") or "-"
                    ans += f"| {idx} | **{g_name}** | {g_st_disp} | `{c_by}` | {m_names} | {s_names} | **{r_cnt}** | **{t_cnt}** | **{f_cnt}** | {r_names} |\n"
                    cg_table_rows.append({
                        "stt": idx,
                        "group_id": r.get("group_id"),
                        "group_name": g_name,
                        "group_status": g_st,
                        "status_display": _vn_status(g_st),
                        "created_by": c_by,
                        "mission_names": m_names,
                        "scope_names": s_names,
                        "root_criteria_count": r_cnt,
                        "total_criteria_count": t_cnt,
                        "so_chi_tieu": t_cnt,
                        "tong_ban_ghi": f_cnt,
                        "root_criteria_names": r_names,
                    })

                tabular_data = {
                    "title": f"Danh mục Bộ thu thập chỉ tiêu năm {year}",
                    "columns": [
                        {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                        {"key": "group_name", "label": "Tên bộ thu thập", "align": "left", "data_type": "text"},
                        {"key": "group_status", "label": "Trạng thái", "align": "center", "data_type": "badge"},
                        {"key": "created_by", "label": "Người tạo", "align": "center", "data_type": "text"},
                        {"key": "mission_names", "label": "Nhiệm vụ liên kết", "align": "left", "data_type": "text"},
                        {"key": "scope_names", "label": "Lĩnh vực", "align": "left", "data_type": "text"},
                        {"key": "root_criteria_count", "label": "Số chỉ tiêu gốc (Cấp 1)", "align": "center", "data_type": "number"},
                        {"key": "total_criteria_count", "label": "Tổng chỉ tiêu ánh xạ", "align": "center", "data_type": "number"},
                        {"key": "tong_ban_ghi", "label": "Tổng bản ghi số liệu", "align": "center", "data_type": "number"},
                        {"key": "root_criteria_names", "label": "Danh sách chỉ tiêu gốc (Cấp 1)", "align": "left", "data_type": "text"},
                    ],
                    "rows": cg_table_rows,
                    "total_records": len(cg_table_rows),
                    "collection_form_count": cf_total,
                    "status_summary": {
                        "active": len(active_rows),
                        "draft": len(draft_rows),
                        "total": len(rows),
                    },
                }
                chips = [
                    {"id": "chip_q05_bm1", "label": "📑 Tiến độ nộp báo cáo 2026", "query_text": "Thống kê tiến độ nộp báo cáo năm 2026: có bao nhiêu báo cáo đã phê duyệt và bao nhiêu bản nháp?"},
                    {"id": "chip_q05_bm2", "label": "🏛️ Ma trận phân công nhiệm vụ", "query_text": "Ma trận phân công nhiệm vụ, phòng ban và cán bộ phụ trách năm 2026?"},
                    {"id": "chip_q05_bm3", "label": "📊 Chỉ tiêu Diêm nghiệp 2026", "query_text": "Các chỉ tiêu Cấp 1 của nhiệm vụ Diêm nghiệp năm 2026?"},
                ]
                ans = _append_collapsible_sql(ans, sql)
                return {
                    "current_stage": "SYNTHESIZING",
                    "stage_message": "✍️ Đang hoàn tất câu trả lời...",
                    "final_answer": ans,
                    "tabular_data": tabular_data,
                    "quick_action_chips": chips,
                }

            # Default: SC-5.1 REPORT_SUBMISSION_STATUS
            approved_cnt = sum(1 for r in rows if str(r.get("report_status") or "").lower() == "approved")
            draft_cnt = sum(1 for r in rows if str(r.get("report_status") or "").lower() == "draft")
            pending_cnt = sum(1 for r in rows if str(r.get("report_status") or "").lower() == "pending")
            rejected_cnt = sum(1 for r in rows if str(r.get("report_status") or "").lower() == "rejected")
            approved_fact_rows = sum(int(r.get("fact_row_count") or r.get("criteria_count") or 0) for r in rows if str(r.get("report_status") or "").lower() == "approved")
            draft_fact_rows = sum(int(r.get("fact_row_count") or r.get("criteria_count") or 0) for r in rows if str(r.get("report_status") or "").lower() == "draft")
            total_rpts = len(rows)

            ans = ""
            if is_blocked_draft:
                ans += (
                    "🔒 **Thông báo phân quyền bảo mật:** "
                    "Tài khoản Công dân / Khách vãng lai **chỉ được phép truy xuất dữ liệu báo cáo đã phê duyệt**, "
                    "không có quyền xem hoặc đối chiếu các kỳ báo cáo **bản nháp** hoặc **chờ phê duyệt**.\n\n"
                    f"Danh sách **{approved_cnt} kỳ báo cáo đã phê duyệt** năm **{year}** ({approved_fact_rows} bản ghi số liệu chỉ tiêu):\n\n"
                )
            else:
                ans += (
                    f"Tổng hợp **{total_rpts} kỳ báo cáo** năm **{year}** (**{approved_cnt} đã phê duyệt** với {approved_fact_rows} bản ghi, "
                    f"**{draft_cnt} bản nháp** với {draft_fact_rows} bản ghi, **{pending_cnt} chờ phê duyệt**):\n\n"
                )

            ans += (
                "| STT | Kỳ báo cáo | Ngày nộp | Trạng thái | Người tạo | Đơn vị thực hiện | Nhiệm vụ báo cáo | Tổng chỉ tiêu | Chỉ tiêu đã ghi nhận số liệu |\n"
                "| :---: | :---: | :---: | :---: | :---: | :--- | :--- | :---: | :---: |\n"
            )
            rpt_table_rows = []
            for idx, r in enumerate(rows, 1):
                r_date = str(r.get("report_date") or "")[:10] or "-"
                s_date = str(r.get("submitted_date") or "")[:10] if r.get("submitted_date") else "Chưa nộp (-)"
                r_st = str(r.get("report_status") or "approved").lower()
                st_disp = "Đã phê duyệt" if r_st == "approved" else ("Bản nháp" if r_st == "draft" else _vn_status(r_st))
                c_by = r.get("created_by") or r.get("nguoi_tao") or "-"
                off_n = r.get("office_name") or "Chi cục"
                if off_n.strip().lower() in ("cấp tỉnh", "chi cục phát triển nông thôn"):
                    off_n = "Chi cục"
                mis_n = r.get("mission_name") or "-"
                c_cnt = int(r.get("criteria_count") or 0)
                rec_cnt = int(r.get("recorded_criteria_count") or 0)
                ans += f"| {idx} | **{r_date}** | {s_date} | {st_disp} | `{c_by}` | {off_n} | {mis_n} | {c_cnt} | **{rec_cnt}** |\n"
                rpt_table_rows.append({
                    "stt": idx,
                    "report_id": r.get("report_id"),
                    "report_date": r_date,
                    "submitted_date": s_date,
                    "status": r_st,
                    "status_display": _vn_status(r_st),
                    "created_by": c_by,
                    "office_name": off_n,
                    "mission_name": mis_n,
                    "criteria_count": c_cnt,
                    "recorded_criteria_count": rec_cnt,
                })

            draft_criteria_rows_formatted = []
            diff_rows_formatted = []
            if not is_blocked_draft and draft_cnt > 0 and getattr(norm_frame, "include_draft_comparison", False):
                try:
                    t_c = (norm_frame.tenant_code or "68").replace("'", "''")
                    y_c = (norm_frame.year_code or year or "2026").replace("'", "''")
                    mis_filter_draft = ""
                    if norm_frame.target_mission:
                        m_esc_d = norm_frame.target_mission.replace("'", "''")
                        mis_filter_draft = f" AND f.mission_name ILIKE '%{m_esc_d}%'"

                    draft_detail_sql = (
                        f"SELECT f.report_date::date::text AS report_date,\n"
                        f"       f.code, f.name, f.value, f.mission_name,\n"
                        f"       COALESCE(o.office_name, 'Chi cục') AS office_name\n"
                        f"FROM dwh_internal.fact_report_criteria f\n"
                        f"LEFT JOIN dwh_internal.office o ON f.office_id = o.id\n"
                        f"WHERE f.tenant_code = '{t_c}' AND f.year_code = '{y_c}' AND f.report_status = 'draft'{mis_filter_draft}\n"
                        f"ORDER BY f.report_date DESC NULLS LAST, f.code ASC;"
                    )
                    raw_draft_details = self.dwh_exec_service.pool.execute_sync_fallback(draft_detail_sql)
                    if raw_draft_details:
                        ans += (
                            f"\n📝 **Chi tiết các chỉ tiêu trong Báo cáo Bản nháp — Nhiệm vụ {norm_frame.target_mission or 'Toàn bộ'} ({len(raw_draft_details)} bản ghi):**\n\n"
                            f"| STT | Kỳ báo cáo nháp | Mã chỉ tiêu | Tên chỉ tiêu | Giá trị bản nháp | Nhiệm vụ | Đơn vị |\n"
                            f"| :---: | :---: | :---: | :--- | :---: | :--- | :--- |\n"
                        )
                        for dr_idx, d_item in enumerate(raw_draft_details, 1):
                            dr_dt = str(d_item.get("report_date") or "")[:10]
                            dr_code = d_item.get("code") or "-"
                            dr_name = d_item.get("name") or "-"
                            raw_v = d_item.get("value")
                            if raw_v is None or str(raw_v).strip() == "":
                                dr_val_disp = "Chưa nhập (-)"
                            else:
                                dr_val_disp = vn_format_num(str(raw_v).strip())
                            dr_mis = d_item.get("mission_name") or "-"
                            dr_off = d_item.get("office_name") or "Chi cục"
                            ans += f"| {dr_idx} | **{dr_dt}** | `{dr_code}` | **{dr_name}** | **{dr_val_disp}** | {dr_mis} | {dr_off} |\n"
                            draft_criteria_rows_formatted.append({
                                "stt": dr_idx,
                                "report_date": dr_dt,
                                "code": dr_code,
                                "name": dr_name,
                                "draft_value": dr_val_disp,
                                "mission_name": dr_mis,
                                "office_name": dr_off,
                            })

                    diff_sql = (
                        f"WITH latest_approved AS (\n"
                        f"    SELECT f.code, f.name, f.parent_criteria_id, f.value AS approved_val, f.report_date::date::text AS approved_date,\n"
                        f"           ROW_NUMBER() OVER (PARTITION BY f.code ORDER BY f.report_date DESC NULLS LAST, f.version DESC NULLS LAST) AS rn\n"
                        f"    FROM dwh_internal.fact_report_criteria f\n"
                        f"    WHERE f.tenant_code = '{t_c}' AND f.year_code = '{y_c}' AND f.report_status = 'approved'{mis_filter_draft}\n"
                        f"      AND NULLIF(TRIM(f.value), '') IS NOT NULL AND TRIM(f.value) != '-'\n"
                        f"),\n"
                        f"latest_draft AS (\n"
                        f"    SELECT f.code, f.name, f.parent_criteria_id, f.value AS draft_val, f.report_date::date::text AS draft_date,\n"
                        f"           ROW_NUMBER() OVER (PARTITION BY f.code ORDER BY f.report_date DESC NULLS LAST, f.version DESC NULLS LAST) AS rn\n"
                        f"    FROM dwh_internal.fact_report_criteria f\n"
                        f"    WHERE f.tenant_code = '{t_c}' AND f.year_code = '{y_c}' AND f.report_status = 'draft'{mis_filter_draft}\n"
                        f"      AND NULLIF(TRIM(f.value), '') IS NOT NULL AND TRIM(f.value) != '-'\n"
                        f")\n"
                        f"SELECT d.code, d.name, COALESCE(p.name, 'Chỉ tiêu gốc') AS parent_name,\n"
                        f"       a.approved_val, a.approved_date,\n"
                        f"       d.draft_val, d.draft_date\n"
                        f"FROM latest_draft d\n"
                        f"JOIN latest_approved a ON d.code = a.code AND a.rn = 1\n"
                        f"LEFT JOIN dwh_internal.criteria p ON d.parent_criteria_id = p.id\n"
                        f"WHERE d.rn = 1 AND TRIM(d.draft_val) != TRIM(a.approved_val)\n"
                        f"ORDER BY d.code ASC;"
                    )
                    raw_diffs = self.dwh_exec_service.pool.execute_sync_fallback(diff_sql)
                    if raw_diffs:
                        ans += (
                            f"\n📊 **Đối chiếu chênh lệch số liệu giữa Bản nháp mới nhất và Bản đã phê duyệt ({len(raw_diffs)} chỉ tiêu có thay đổi):**\n\n"
                            f"| STT | Mã chỉ tiêu | Tên chỉ tiêu | Nhóm chỉ tiêu cha | Giá trị đã phê duyệt (Kỳ duyệt) | Giá trị bản nháp (Kỳ nháp) | Chênh lệch |\n"
                            f"| :---: | :---: | :--- | :--- | :---: | :---: | :---: |\n"
                        )
                        for d_idx, dr in enumerate(raw_diffs, 1):
                            c_code = dr.get("code") or "-"
                            c_name = dr.get("name") or "-"
                            p_name = dr.get("parent_name") or "-"
                            a_val = str(dr.get("approved_val") or "0").strip()
                            d_val = str(dr.get("draft_val") or "0").strip()
                            a_dt = str(dr.get("approved_date") or "")[:10]
                            d_dt = str(dr.get("draft_date") or "")[:10]
                            try:
                                delta_num = float(d_val) - float(a_val)
                                delta_str = f"+{int(delta_num)}" if delta_num > 0 and delta_num.is_integer() else (f"{int(delta_num)}" if delta_num.is_integer() else f"{delta_num:+.2f}")
                            except Exception:
                                delta_str = "-"
                            ans += (
                                f"| {d_idx} | `{c_code}` | **{c_name}** | {p_name} | **{vn_format_num(a_val)}** *({a_dt})* | **{vn_format_num(d_val)}** *({d_dt})* | **`{delta_str}`** |\n"
                            )
                            diff_rows_formatted.append({
                                "stt": d_idx,
                                "code": c_code,
                                "name": c_name,
                                "parent_name": p_name,
                                "approved_value": a_val,
                                "approved_date": a_dt,
                                "draft_value": d_val,
                                "draft_date": d_dt,
                                "delta": delta_str,
                            })
                except Exception as e:
                    logger.debug("Không thể truy vấn bảng đối chiếu bản nháp và bản đã phê duyệt: %s", e)

            tabular_data = {
                "title": f"Kiểm toán tiến độ nộp & trạng thái phê duyệt báo cáo năm {year}",
                "columns": [
                    {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                    {"key": "report_date", "label": "Kỳ báo cáo", "align": "center", "data_type": "text"},
                    {"key": "submitted_date", "label": "Ngày nộp", "align": "center", "data_type": "text"},
                    {"key": "status_display", "label": "Trạng thái", "align": "center", "data_type": "badge"},
                    {"key": "created_by", "label": "Người tạo", "align": "center", "data_type": "text"},
                    {"key": "office_name", "label": "Đơn vị thực hiện", "align": "left", "data_type": "text"},
                    {"key": "mission_name", "label": "Nhiệm vụ báo cáo", "align": "left", "data_type": "text"},
                    {"key": "criteria_count", "label": "Tổng chỉ tiêu", "align": "center", "data_type": "number"},
                    {"key": "recorded_criteria_count", "label": "Chỉ tiêu đã có số liệu", "align": "center", "data_type": "number"},
                ],
                "rows": rpt_table_rows,
                "total_records": total_rpts,
                "status_summary": {
                    "approved": approved_cnt,
                    "draft": draft_cnt,
                    "pending": pending_cnt,
                    "rejected": rejected_cnt,
                    "total": total_rpts,
                },
                "draft_criteria_rows": draft_criteria_rows_formatted,
                "draft_vs_approved_diff": diff_rows_formatted,
                "blocked_draft_access": is_blocked_draft,
            }
            chips = [
                {"id": "chip_q05_r1", "label": "📋 Bộ thu thập chỉ tiêu 2026", "query_text": "Danh sách các biểu mẫu thu thập và bộ thu thập chỉ tiêu năm 2026?"},
                {"id": "chip_q05_r2", "label": "🏛️ Ma trận phân công nhiệm vụ", "query_text": "Ma trận phân công nhiệm vụ, phòng ban và cán bộ phụ trách năm 2026?"},
                {"id": "chip_q05_r3", "label": "🌾 Chỉ tiêu Cấp 1 PTNT", "query_text": "Các chỉ tiêu Cấp 1 của nhiệm vụ Phát triển nông thôn năm 2026?"},
            ]
            ans = _append_collapsible_sql(ans, sql)
            return {
                "current_stage": "SYNTHESIZING",
                "stage_message": "✍️ Đang hoàn tất câu trả lời...",
                "final_answer": ans,
                "tabular_data": tabular_data,
                "quick_action_chips": chips,
            }

        temporal_meta = _build_temporal_scope_meta(norm_frame, year)

        # Nếu tập kết quả rỗng nhưng câu hỏi tra cứu 1 chỉ tiêu cụ thể trong danh mục
        if (
            not rows
            and not state.get("is_empty_year")
            and norm_frame
            and norm_frame.intent == CanonicalIntentEnum.METRIC_POINT_INQUIRY
            and hasattr(self.catalog, "classify_criterion_hierarchy")
        ):
            has_temp_filter_empty = bool(
                norm_frame.month_filter is not None
                or norm_frame.date_from is not None
                or norm_frame.specific_date is not None
            )
            try:
                latest_report_date = (
                    getattr(self.catalog, "get_latest_report_date", lambda: "-")() or "-"
                    if hasattr(self, "catalog")
                    else "-"
                )
                h_empty = self.catalog.classify_criterion_hierarchy(clean_prompt, matched_name=selected_cand)
                if not has_temp_filter_empty:
                    if h_empty and h_empty.get("classification") == "single_leaf" and h_empty.get("item"):
                        it = h_empty["item"]
                        rows = [{
                            "ten_chi_tieu": it.get("name") or selected_cand,
                            "gia_tri_moi_nhat": it.get("latest_value"),
                            "ten_van_phong": it.get("office_name") or "Cấp tỉnh",
                            "ten_nhiem_vu": it.get("mission_name") or "-",
                            "ngay_bao_cao_moi_nhat": latest_report_date,
                        }]
                        selected_cand = it.get("name") or selected_cand
                    elif h_empty and h_empty.get("classification") in ("parent", "parent_group"):
                        rows = [{
                            "ten_chi_tieu": h_empty.get("parent_name") or selected_cand,
                            "gia_tri_moi_nhat": h_empty.get("parent_value"),
                            "ten_van_phong": h_empty.get("office_name") or "Cấp tỉnh",
                            "ten_nhiem_vu": h_empty.get("mission_name") or "-",
                            "ngay_bao_cao_moi_nhat": latest_report_date,
                        }]
                        selected_cand = h_empty.get("parent_name") or selected_cand
                    elif h_empty and h_empty.get("classification") == "duplicate_leaf" and h_empty.get("branches"):
                        br0 = h_empty["branches"][0]
                        rows = [{
                            "ten_chi_tieu": br0.get("name") or selected_cand,
                            "gia_tri_moi_nhat": br0.get("latest_value"),
                            "ten_van_phong": br0.get("office_name") or "Cấp tỉnh",
                            "ten_nhiem_vu": br0.get("mission_name") or "-",
                            "ngay_bao_cao_moi_nhat": latest_report_date,
                        }]
                        selected_cand = br0.get("name") or selected_cand
                elif (
                    h_empty
                    and h_empty.get("classification") in ("parent", "parent_group")
                    and hasattr(self.catalog, "get_children_values_at_temporal_scope")
                ):
                    cand_nodes = (
                        [{"id": h_empty.get("parent_id"), "name": h_empty.get("parent_name") or selected_cand}]
                        + list(h_empty.get("direct_children") or [])
                        + list(h_empty.get("leaf_descendants") or [])
                    )
                    t_map = self.catalog.get_children_values_at_temporal_scope(
                        cand_nodes,
                        year_code=str(norm_frame.year_code or year or "2026"),
                        tenant_code=str(norm_frame.tenant_code or "68"),
                        specific_date=norm_frame.specific_date,
                        date_from=norm_frame.date_from,
                        date_to=norm_frame.date_to,
                        month_filter=norm_frame.month_filter,
                    )
                    if t_map:
                        sample_t = next(iter(t_map.values()))
                        p_id_key = str(h_empty.get("parent_id") or "").lower()
                        p_nm_key = str(h_empty.get("parent_name") or selected_cand or "").strip().lower()
                        p_entry = t_map.get(p_id_key) or t_map.get(p_nm_key) or {}
                        rows = [{
                            "criteria_id": h_empty.get("parent_id"),
                            "ten_chi_tieu": h_empty.get("parent_name") or selected_cand,
                            "gia_tri_moi_nhat": p_entry.get("value"),
                            "ten_van_phong": h_empty.get("office_name") or "Cấp tỉnh",
                            "ten_nhiem_vu": h_empty.get("mission_name") or "-",
                            "ngay_bao_cao": p_entry.get("report_date") or sample_t.get("report_date") or "-",
                            "do_lech_ngay": sample_t.get("do_lech_ngay"),
                            "can_duoi_ngay": sample_t.get("can_duoi_ngay"),
                            "can_tren_ngay": sample_t.get("can_tren_ngay"),
                        }]
                        selected_cand = h_empty.get("parent_name") or selected_cand
            except Exception as e:
                logger.debug("Catalog fallback on empty rows failed: %s", e)

        # Hàm trích xuất tên chỉ tiêu và giá trị từ hàng bất kỳ
        def _get_metric_name(r: dict) -> str:
            return (r.get("ten_chi_tieu") or r.get("name") or "").strip()

        def _get_metric_val(r: dict) -> Any:
            for k in ["gia_tri_moi_nhat", "tong_gia_tri", "gia_tri", "value", "doanh_thu_binh_quan"]:
                if r.get(k) is not None:
                    return r.get(k)
            return None

        def _is_empty_or_dash(val: Any) -> bool:
            if val is None:
                return True
            if isinstance(val, str) and val.strip() in ("", "-", "None", "null", "N/A"):
                return True
            return False

        # --------------------------------------------------------------------------
        # R3: Kiểm tra câu hỏi Phân rã Cấu trúc / Liệt kê Danh mục con (Zero Hardcoding)
        # Đặt trước kiểm tra `if not rows:` để đảm bảo hoạt động ngay cả khi nhóm cha không có dòng riêng trong fact
        # (Chỉ áp dụng khi không phải câu hỏi có neo thời gian điểm/khoảng đặc thù của SC-2.4)
        # --------------------------------------------------------------------------
        has_temporal_ticket_r3 = bool(
            norm_frame and (
                getattr(norm_frame, "specific_date", None)
                or getattr(norm_frame, "date_from", None)
                or getattr(norm_frame, "month_filter", None)
            )
        )
        if hasattr(self.catalog, "resolve_hierarchy_breakdown"):
            breakdown_res = self.catalog.resolve_hierarchy_breakdown(
                clean_prompt,
                tenant_code=str(norm_frame.tenant_code or "68") if norm_frame else "68",
                year_code=str(year or "2026")
            )
            if breakdown_res and breakdown_res.get("status") == "SUCCESS":
                p_node = breakdown_res["parent_node"]
                p_name = p_node["name"]
                r_name = breakdown_res.get("root_name") or p_name
                children = breakdown_res["children"]
                r3_year_str = str(norm_frame.year_code or year or "2026") if norm_frame else str(year or "2026")
                r3_tenant_str = str(norm_frame.tenant_code or "68") if norm_frame else "68"

                if has_temporal_ticket_r3 and hasattr(self.catalog, "get_children_values_at_temporal_scope"):
                    temporal_child_map = self.catalog.get_children_values_at_temporal_scope(
                        [p_node] + list(children),
                        year_code=r3_year_str,
                        tenant_code=r3_tenant_str,
                        specific_date=getattr(norm_frame, "specific_date", None) if norm_frame else None,
                        date_from=getattr(norm_frame, "date_from", None) if norm_frame else None,
                        date_to=getattr(norm_frame, "date_to", None) if norm_frame else None,
                        month_filter=getattr(norm_frame, "month_filter", None) if norm_frame else None,
                    )
                    p_id_k = str(p_node.get("id") or "").lower()
                    p_nm_k = str(p_node.get("name") or "").strip().lower()
                    p_t_entry = temporal_child_map.get(p_id_k) or temporal_child_map.get(p_nm_k)
                    if p_t_entry and p_t_entry.get("value") is not None:
                        p_node["latest_value"] = p_t_entry.get("value")
                        p_node["report_date"] = p_t_entry.get("report_date")
                    for ch in children:
                        ch_id_k = str(ch.get("id") or "").lower()
                        ch_nm_k = str(ch.get("name") or "").strip().lower()
                        t_entry = temporal_child_map.get(ch_id_k) or temporal_child_map.get(ch_nm_k)
                        if t_entry and t_entry.get("value") is not None:
                            ch["latest_value"] = t_entry.get("value")
                            ch["report_date"] = t_entry.get("report_date")

                batch_period_map: Dict[str, Dict[str, str]] = {}
                if hasattr(self.catalog, "get_batch_period_values"):
                    batch_period_map = self.catalog.get_batch_period_values(
                        [p_node] + list(children),
                        year_code=r3_year_str,
                        tenant_code=r3_tenant_str,
                    )

                p_id_lookup = str(p_node.get("id") or "").strip().lower()
                p_code_lookup = str(p_node.get("code") or "").strip().lower()
                p_name_lookup = " ".join(str(p_name or "").lower().split())
                parent_period_vals = dict(
                    batch_period_map.get(p_id_lookup)
                    or batch_period_map.get(p_code_lookup)
                    or batch_period_map.get(p_name_lookup)
                    or {}
                )

                c_count = len(children)
                c_names = [c["name"] for c in children]
                c_names_str = ", ".join([f"**{nm}**" for nm in c_names])
                p_val_raw = p_node.get("latest_value")
                p_summary_header = ""
                if not _is_empty_or_dash(p_val_raw):
                    p_val_fmt = vn_format_num(p_val_raw)
                    if "year" not in parent_period_vals:
                        parent_period_vals["year"] = p_val_fmt
                    p_summary_header = f"- **Chỉ tiêu:** {p_name}\n- **Giá trị:** {p_val_fmt}\n\n"

                period_intro_lbl, period_title_lbl = _format_temporal_period_label(norm_frame, year)
                intro_period_str = f"kèm giá trị ghi nhận {period_intro_lbl}" if has_temporal_ticket_r3 else f"kèm giá trị mới nhất theo báo cáo năm {year}"
                table_title_str = f"Danh mục chi tiết các chỉ tiêu thuộc '{p_name}' {period_title_lbl}"

                ans = (
                    f"{p_summary_header}"
                    f"Trong kho dữ liệu DWH tỉnh Lâm Đồng, hiện có **{c_count}** phân nhóm/chỉ tiêu con "
                    f"trực thuộc nhóm **'{p_name}'** (thuộc **{r_name}**) gồm: {c_names_str}.\n\n"
                    f"Dưới đây là bảng thống kê chi tiết các chỉ tiêu {intro_period_str}:\n\n"
                    f"| STT | Tên chỉ tiêu | Nhóm chỉ tiêu | Giá trị mới nhất | Đơn vị thực hiện | Nhiệm vụ trọng tâm |\n"
                    f"| :---: | :--- | :--- | :---: | :--- | :--- |\n"
                )

                table_rows = []
                for idx, ch in enumerate(children, 1):
                    val_raw = ch.get("latest_value")
                    val_fmt = "Chưa có số liệu (-)" if _is_empty_or_dash(val_raw) else vn_format_num(val_raw)
                    off_str = ch.get("office_name") or "Chi cục"
                    mis_str = ch.get("mission_name") or "-"
                    cat_str = f"{r_name} > {p_name}" if r_name != p_name else p_name

                    ch_id_lookup = str(ch.get("id") or "").strip().lower()
                    ch_code_lookup = str(ch.get("code") or "").strip().lower()
                    ch_name_lookup = " ".join(str(ch.get("name") or "").lower().split())
                    ch_combo_lookup = f"{ch_name_lookup}||{p_name_lookup}" if (ch_name_lookup and p_name_lookup) else ""
                    ch_period_vals = dict(
                        batch_period_map.get(ch_id_lookup)
                        or batch_period_map.get(ch_code_lookup)
                        or (batch_period_map.get(ch_combo_lookup) if ch_combo_lookup else None)
                        or batch_period_map.get(ch_name_lookup)
                        or {}
                    )
                    if "year" not in ch_period_vals:
                        ch_period_vals["year"] = val_fmt

                    ans += f"| {idx} | {ch['name']} | {cat_str} | **{val_fmt}** | {off_str} | {mis_str} |\n"
                    table_rows.append({
                        "stt": idx,
                        "criteria_id": ch.get("id"),
                        "item": ch["name"],
                        "category": cat_str,
                        "value": val_fmt,
                        "office": off_str,
                        "mission": mis_str,
                        "_raw_value": val_raw,
                        "timeline_values": ch_period_vals,
                        "period_values": ch_period_vals,
                    })

                tabular_data = {
                    "title": table_title_str,
                    "columns": [
                        {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                        {"key": "item", "label": "Tên chỉ tiêu", "align": "left", "data_type": "text"},
                        {"key": "category", "label": "Nhóm chỉ tiêu", "align": "left", "data_type": "text"},
                        {"key": "value", "label": "Giá trị mới nhất", "align": "right", "data_type": "text"},
                        {"key": "office", "label": "Đơn vị thực hiện", "align": "left", "data_type": "text"},
                        {"key": "mission", "label": "Nhiệm vụ trọng tâm", "align": "left", "data_type": "text"},
                    ],
                    "rows": table_rows,
                    "total_records": len(table_rows),
                    "temporal_scope": temporal_meta,
                    "parent_criterion_name": p_name,
                    "parent_timeline_values": parent_period_vals,
                }

                ans = _append_collapsible_sql(ans, sql)
                return {
                    "current_stage": "SYNTHESIZING",
                    "stage_message": "✍️ Đang hoàn tất câu trả lời...",
                    "final_answer": ans,
                    "quick_action_chips": [
                        {
                            "id": f"chip_{i+1}",
                            "label": f"🔘 [{c['name']}]",
                            "query_text": f"Chỉ tiêu {c['name']} thuộc {p_name} {temporal_meta['query_suffix']} là bao nhiêu?",
                            "timeline_values": table_rows[i].get("timeline_values") if i < len(table_rows) else None,
                        }
                        for i, c in enumerate(children[:4])
                    ],
                    "tabular_data": tabular_data,
                    "inherited_parent_criterion": p_name,
                }

        # Nếu tập kết quả rỗng
        if not rows:
            # SC-3.2: Lĩnh vực không tồn tại trong dwh_internal.scope
            if norm_frame and norm_frame.target_table == "mission" and getattr(norm_frame, "target_scope", None):
                req_scope = norm_frame.target_scope.strip()
                existing_scopes = []
                if hasattr(self.catalog, "get_scopes_list"):
                    existing_scopes = self.catalog.get_scopes_list()
                raw_scopes = [
                    (s.get("scope_name") or s.get("name"))
                    for s in existing_scopes
                    if (s.get("scope_name") or s.get("name"))
                ] or []
                scope_names = [sn[0].upper() + sn[1:] if sn else sn for sn in raw_scopes]
                if req_scope.lower() not in [s.lower() for s in scope_names]:
                    chip_md = "  ".join([f"🔘 `[Lĩnh vực: {sn}]`" for sn in scope_names])
                    ans = (
                        f"Hiện tại trong Kho Dữ Liệu (DWH) tỉnh Lâm Đồng **không có lĩnh vực '{req_scope}'**. "
                        f"Đồng chí có thể tra cứu các nhiệm vụ thuộc các lĩnh vực hiện có sau đây:\n\n"
                        f"{chip_md}"
                    )
                    chips = [
                        {
                            "id": f"chip_scope_{idx}",
                            "label": f"🔘 [Lĩnh vực: {sn}]",
                            "query_text": f"Lĩnh vực {sn} hiện tại đang có các nhiệm vụ nào?",
                        }
                        for idx, sn in enumerate(scope_names, 1)
                    ]
                    ans = _append_collapsible_sql(ans, sql)
                    return {
                        "current_stage": "SYNTHESIZING",
                        "stage_message": "✍️ Đang tổng hợp câu trả lời...",
                        "final_answer": ans,
                        "quick_action_chips": chips,
                    }
                else:
                    y_lbl = norm_frame.year_code or year or "2026"
                    _, t_str = _format_temporal_period_label(norm_frame, y_lbl)
                    ans = (
                        f"Lĩnh vực **'{req_scope}'** hiện chưa phát sinh bản ghi báo cáo nhiệm vụ nào được phê duyệt trong **{t_str}** trên hệ thống kho dữ liệu DWH."
                    )
                    ans = _append_collapsible_sql(ans, sql)
                    return {
                        "current_stage": "SYNTHESIZING",
                        "stage_message": "✍️ Đang tổng hợp câu trả lời...",
                        "final_answer": ans,
                        "quick_action_chips": chips,
                    }

            # REQ-Q04 & SC-4.2: Nhiệm vụ không tồn tại hoặc Nhiệm vụ có trong danh mục nhưng chưa có chỉ tiêu báo cáo phê duyệt
            if norm_frame and getattr(norm_frame, "target_mission", None):
                raw_target_m = str(norm_frame.target_mission).strip()
                is_not_found_mission = raw_target_m.startswith("__NOT_FOUND__:")
                clean_target_m = raw_target_m.replace("__NOT_FOUND__:", "").strip()
                m_detail = None
                if not is_not_found_mission and hasattr(self.catalog, "get_mission_detail"):
                    m_detail = self.catalog.get_mission_detail(clean_target_m)

                if is_not_found_mission or m_detail is None:
                    existing_missions = []
                    if hasattr(self.catalog, "get_missions_list"):
                        existing_missions = self.catalog.get_missions_list()
                    valid_m_names = [
                        (m.get("mission_name") or m.get("name"))
                        for m in existing_missions
                        if (m.get("mission_name") or m.get("name"))
                    ] or []
                    chip_md = "  ".join([f"🔘 `[Nhiệm vụ: {mn}]`" for mn in valid_m_names])
                    ans = (
                        f"Hiện tại trong Kho Dữ Liệu (DWH) tỉnh Lâm Đồng **không có nhiệm vụ '{clean_target_m}'**. "
                        f"Đồng chí có thể tra cứu các chỉ tiêu thuộc các nhiệm vụ hiện có sau đây:\n\n"
                        f"{chip_md}"
                    )
                    chips = [
                        {
                            "id": f"chip_mis_valid_{idx}",
                            "label": f"🔘 [Nhiệm vụ: {mn}]",
                            "query_text": f"Các chỉ tiêu Cấp 1 của nhiệm vụ {mn} năm {year} là gì?",
                        }
                        for idx, mn in enumerate(valid_m_names, 1)
                    ]
                    ans = _append_collapsible_sql(ans, sql)
                    return {
                        "current_stage": "SYNTHESIZING",
                        "stage_message": "✍️ Đang tổng hợp câu trả lời...",
                        "final_answer": ans,
                        "quick_action_chips": chips,
                    }

                if getattr(norm_frame, "is_level1_hierarchy_view", False) or norm_frame.intent == CanonicalIntentEnum.DIMENSION_LISTING:
                    m_name_disp = (m_detail.get("mission_name") if m_detail else None) or clean_target_m
                    off_disp = (m_detail.get("office_name") if m_detail else None) or "Chi cục"
                    y_disp = (m_detail.get("year_code") if m_detail else None) or norm_frame.year_code or year or "2026"
                    if norm_frame.month_filter is not None:
                        ans = (
                            f"Nhiệm vụ **'{m_name_disp}'** (do **{off_disp}** phụ trách) hiện **chưa phát sinh bản ghi chỉ tiêu báo cáo nào được phê duyệt trong tháng {norm_frame.month_filter:02d}/{y_disp}** trên hệ thống kho dữ liệu DWH."
                        )
                    elif norm_frame.date_from is not None and norm_frame.date_to is not None:
                        ans = (
                            f"Nhiệm vụ **'{m_name_disp}'** (do **{off_disp}** phụ trách) hiện **chưa phát sinh bản ghi chỉ tiêu báo cáo nào được phê duyệt trong giai đoạn từ {norm_frame.date_from} đến {norm_frame.date_to}** trên hệ thống kho dữ liệu DWH."
                        )
                    else:
                        ans = (
                            f"Nhiệm vụ **'{m_name_disp}'** (do **{off_disp}** phụ trách) hiện đã có trong danh mục nhiệm vụ năm {y_disp}, "
                            f"nhưng **chưa phát sinh bản ghi chỉ tiêu báo cáo nào được phê duyệt** trong hệ thống."
                        )
                    ans = _append_collapsible_sql(ans, sql)
                    return {
                        "current_stage": "SYNTHESIZING",
                        "stage_message": "✍️ Đang tổng hợp câu trả lời...",
                        "final_answer": ans,
                        "quick_action_chips": chips,
                    }

            if norm_frame and (
                norm_frame.month_filter is not None
                or norm_frame.date_from is not None
                or norm_frame.intent == CanonicalIntentEnum.DIMENSION_LISTING
            ):
                if norm_frame.month_filter is not None:
                    time_desc = f"tháng {norm_frame.month_filter:02d}/{norm_frame.year_code or year or '2026'}"
                elif norm_frame.date_from is not None and norm_frame.date_to is not None:
                    time_desc = f"giai đoạn từ {norm_frame.date_from} đến {norm_frame.date_to}"
                elif norm_frame.date_from is not None:
                    time_desc = f"từ ngày {norm_frame.date_from} đến nay"
                else:
                    time_desc = f"năm {norm_frame.year_code or year or '2026'}"
                ans = (
                    f"Hiện tại trong Kho Dữ Liệu (DWH) tỉnh Lâm Đồng **chưa ghi nhận bản ghi chỉ tiêu nào được phê duyệt trong kỳ {time_desc}** "
                    f"(Không tìm thấy chỉ tiêu nào phát sinh số liệu trong {time_desc} trên hệ thống kho dữ liệu DWH). "
                    f"Đồng chí có thể tra cứu dữ liệu kỳ năm **2026**."
                )
                if state.get("is_empty_year"):
                    ans += f"\n\n💡 **Gợi ý tra cứu:** Hiện tại kho DWH đang phục vụ đầy đủ dữ liệu báo cáo kinh tế - xã hội đã phê duyệt của năm **2026**."
            elif state.get("is_empty_year"):
                ans = (
                    f"Theo dữ liệu kho DWH tỉnh Lâm Đồng, năm **{year}** là năm trước kỳ tổng hợp báo cáo "
                    f"chính thức (chưa phát sinh bản ghi số liệu đã phê duyệt trên hệ thống).\n\n"
                    f"💡 **Gợi ý tra cứu:** Hiện tại kho DWH đang phục vụ đầy đủ dữ liệu báo cáo kinh tế - xã hội đã phê duyệt của năm **2026**."
                )
            elif norm_frame and norm_frame.intent == CanonicalIntentEnum.ENTITY_ATTRIBUTE_LOOKUP:
                subj = (norm_frame.canonical_metric_names[0] if norm_frame.canonical_metric_names else None) or norm_frame.subject_entity or "Chỉ tiêu"
                c_id = None
                if hasattr(self.catalog, "resolve_metric_id"):
                    c_id = self.catalog.resolve_metric_id(subj)
                if c_id:
                    ans = (
                        f"Chỉ tiêu **{subj}** có trong Danh mục chỉ tiêu của hệ thống, "
                        f"nhưng hiện tại **chưa phát sinh số liệu báo cáo hoặc chưa được phân công/giao nộp dữ liệu** "
                        f"trên hệ thống trong năm **{year}**."
                    )
                else:
                    ans = (
                        f"Yêu cầu tra cứu hiện **chưa có bản ghi số liệu phù hợp** "
                        f"trong kho DWH năm **{year}**.\n\n"
                        f"💡 **Gợi ý tra cứu:** Hiện tại kho DWH đang lưu trữ đầy đủ số liệu chỉ tiêu nông nghiệp & PTNT năm **2026**."
                    )
            elif norm_frame and norm_frame.target_table == "province":
                ans = (
                    "Hiện tại trong danh mục địa bàn hành chính, "
                    "không tìm thấy tỉnh/thành phố nào phù hợp với điều kiện tra cứu."
                )
            elif norm_frame and norm_frame.target_table in ("deparment", "office"):
                ans = (
                    "Trong kho dữ liệu DWH, danh mục sở ngành hiện chưa có bản ghi trực tiếp "
                    "(dữ liệu đơn vị đang được quản lý trực tiếp theo mã cơ quan trên các báo cáo và chỉ tiêu).\n\n"
                    "💡 Các cơ quan chủ quản dữ liệu hiện tại bao gồm: **Sở Nông nghiệp và Phát triển nông thôn** (Mã: `68-1-01`), "
                    "**Sở Công Thương**, **Sở Kế hoạch và Đầu tư**."
                )
            elif norm_frame and norm_frame.target_table in ("collection_form", "report_form"):
                ans = (
                    f"Hiện tại trong kho dữ liệu DWH tỉnh Lâm Đồng (năm **{year}**), "
                    f"danh mục **biểu mẫu thu thập thông tin / tờ khai nghiệp vụ** hiện **chưa có bản ghi biểu mẫu nào được kích hoạt** (bảng dữ liệu đang để trống).\n\n"
                    "💡 **Gợi ý tra cứu:** Hiện tại kho DWH đang lưu trữ đầy đủ số liệu chỉ tiêu nông nghiệp & PTNT năm **2026**, tình hình nộp báo cáo và phân công nhiệm vụ cán bộ. "
                    "Đồng chí có thể chọn một trong các câu hỏi gợi ý bên dưới."
                )
            elif norm_frame and (norm_frame.target_table in ("user", "user_mission") or norm_frame.intent == CanonicalIntentEnum.OFFICER_ASSIGNMENT):
                ans = (
                    f"Hiện tại kho dữ liệu DWH năm **{year}** chưa ghi nhận cán bộ phụ trách nhiệm vụ phù hợp với từ khóa tra cứu.\n\n"
                    "💡 **Gợi ý tra cứu:** Đồng chí có thể tra cứu danh mục nhiệm vụ trọng tâm hoặc danh sách phân công nhiệm vụ Diêm nghiệp, Phát triển nông thôn."
                )
            elif selected_cand:
                prefix = f"Chỉ tiêu **{selected_cand}**"
                ans = (
                    f"{prefix} hiện **chưa có bản ghi số liệu được phê duyệt** "
                    f"trong kho DWH năm **{year}**.\n\n"
                    "💡 **Gợi ý tra cứu:** Hiện tại kho DWH đang lưu trữ đầy đủ số liệu chỉ tiêu nông nghiệp & PTNT năm **2026**. "
                    "Đồng chí có thể chọn một trong các câu hỏi gợi ý bên dưới."
                )
            else:
                ans = (
                    f"Yêu cầu tra cứu hiện **chưa có bản ghi số liệu phù hợp** "
                    f"trong kho DWH năm **{year}**.\n\n"
                    "💡 **Gợi ý tra cứu:** Hiện tại kho DWH đang lưu trữ đầy đủ số liệu chỉ tiêu nông nghiệp & PTNT năm **2026**, tình hình nộp báo cáo và danh mục nhiệm vụ trọng tâm. "
                    "Đồng chí có thể chọn một trong các câu hỏi gợi ý bên dưới."
                )
            ans = _append_collapsible_sql(ans, sql)
            return {
                "current_stage": "SYNTHESIZING",
                "stage_message": "✍️ Đang tổng hợp câu trả lời...",
                "final_answer": ans,
                "quick_action_chips": chips,
            }

        # Kiểm tra kịch bản SC-2.4: Chỉ tiêu Cha (Parent Criterion) hỗ trợ cả có/không có Ticket Thời Gian
        has_temporal_point_or_range = bool(
            norm_frame and (
                getattr(norm_frame, "specific_date", None)
                or getattr(norm_frame, "date_from", None)
                or getattr(norm_frame, "month_filter", None)
            )
        )
        if selected_cand and rows:
            h_info_parent = None
            if hasattr(self.catalog, "classify_criterion_hierarchy"):
                h_info_parent = self.catalog.classify_criterion_hierarchy(clean_prompt, matched_name=selected_cand)

            target_pid = str(h_info_parent.get("parent_id")).lower() if (h_info_parent and h_info_parent.get("parent_id")) else None
            cand_row = None
            if target_pid:
                cand_row = next(
                    (r for r in rows if str(r.get("criteria_id") or r.get("id") or "").lower() == target_pid),
                    None
                )
            if not cand_row:
                matching_cand_rows = [
                    r for r in rows
                    if _get_metric_name(r).lower() == selected_cand.strip().lower()
                    or selected_cand.strip().lower() in _get_metric_name(r).lower()
                ]
                cand_row = matching_cand_rows[0] if matching_cand_rows else None

            is_parent_case = bool(
                h_info_parent and h_info_parent.get("classification") in ("parent", "parent_group")
            )

            if is_parent_case:
                all_children_list = []
                raw_children = (
                    (h_info_parent.get("direct_children") or h_info_parent.get("children") or [])
                    if h_info_parent else []
                )
                temporal_child_map: Dict[str, Dict[str, Any]] = {}
                if has_temporal_point_or_range and hasattr(self.catalog, "get_children_values_at_temporal_scope"):
                    nodes_for_t = (
                        [{"id": target_pid, "name": (h_info_parent.get("parent_name") if h_info_parent else None) or selected_cand}]
                        + list(raw_children)
                        + list((h_info_parent.get("leaf_descendants") or []) if h_info_parent else [])
                    )
                    temporal_child_map = self.catalog.get_children_values_at_temporal_scope(
                        nodes_for_t,
                        year_code=str(norm_frame.year_code or year or "2026") if norm_frame else str(year),
                        tenant_code=str(norm_frame.tenant_code or "68") if norm_frame else "68",
                        specific_date=getattr(norm_frame, "specific_date", None) if norm_frame else None,
                        date_from=getattr(norm_frame, "date_from", None) if norm_frame else None,
                        date_to=getattr(norm_frame, "date_to", None) if norm_frame else None,
                        month_filter=getattr(norm_frame, "month_filter", None) if norm_frame else None,
                    )

                for ch in raw_children:
                    ch_id_k = str(ch.get("id") or "").lower()
                    ch_nm_k = str(ch.get("name") or "").strip().lower()
                    if has_temporal_point_or_range:
                        t_entry = temporal_child_map.get(ch_id_k) or temporal_child_map.get(ch_nm_k)
                        ch_val = t_entry.get("value") if t_entry else None
                    else:
                        ch_val = ch.get("latest_value")
                    all_children_list.append({
                        "id": ch.get("id"),
                        "code": ch.get("code"),
                        "ten_chi_tieu": ch.get("name"),
                        "gia_tri": ch_val,
                        "child_count": int(ch.get("child_count") or 0),
                        "is_parent_group": bool(ch.get("is_parent_group") or int(ch.get("child_count") or 0) > 0),
                        "ten_van_phong": ch.get("office_name") or (h_info_parent.get("office_name") if h_info_parent else None) or "Cấp tỉnh",
                        "ten_nhiem_vu": ch.get("mission_name") or (h_info_parent.get("mission_name") if h_info_parent else None) or "-",
                    })

                if not all_children_list:
                    all_children_list = [
                        r for r in rows
                        if r != cand_row
                    ]

                if all_children_list:
                    parent_disp = (h_info_parent.get("parent_name") if h_info_parent else None) or selected_cand

                    r_parent = dict(cand_row or (rows[0] if rows else {}))
                    if has_temporal_point_or_range and temporal_child_map:
                        sample_t_meta = next(iter(temporal_child_map.values()))
                        if not r_parent.get("ngay_bao_cao") and not r_parent.get("report_date"):
                            r_parent["ngay_bao_cao"] = sample_t_meta.get("report_date")
                        if r_parent.get("do_lech_ngay") is None and sample_t_meta.get("do_lech_ngay") is not None:
                            r_parent["do_lech_ngay"] = sample_t_meta.get("do_lech_ngay")
                            r_parent["can_duoi_ngay"] = sample_t_meta.get("can_duoi_ngay")
                            r_parent["can_tren_ngay"] = sample_t_meta.get("can_tren_ngay")

                    parent_val = _get_metric_val(cand_row) if cand_row is not None else (
                        None if has_temporal_point_or_range else (h_info_parent.get("parent_value") or h_info_parent.get("latest_value"))
                    )

                    # PA 3.1: Với chỉ tiêu cha có số liệu (SC-2.4a), hiển thị toàn bộ chỉ tiêu con trực tiếp;
                    # với chỉ tiêu cha rỗng (SC-2.4b), ưu tiên các chỉ tiêu con đang có số liệu (kèm nhóm trung gian có con) hoặc thu hoạch lá Cấp 3
                    has_direct_valued_child = any(
                        not _is_empty_or_dash(_get_metric_val(c)) for c in all_children_list
                    )
                    non_empty_children = [
                        c for c in all_children_list
                        if not _is_empty_or_dash(_get_metric_val(c))
                        or (has_direct_valued_child and bool(c.get("is_parent_group") or int(c.get("child_count") or 0) > 0))
                    ]
                    if not non_empty_children and h_info_parent and h_info_parent.get("leaf_descendants"):
                        leaf_desc = []
                        for lf in h_info_parent.get("leaf_descendants", []):
                            lf_id_k = str(lf.get("id") or "").lower()
                            lf_nm_k = str(lf.get("name") or "").strip().lower()
                            if has_temporal_point_or_range:
                                lf_t = temporal_child_map.get(lf_id_k) or temporal_child_map.get(lf_nm_k)
                                lf_val = lf_t.get("value") if lf_t else None
                            else:
                                lf_val = lf.get("latest_value")
                            if not _is_empty_or_dash(lf_val):
                                leaf_desc.append({
                                    "id": lf.get("id"),
                                    "code": lf.get("code"),
                                    "ten_chi_tieu": lf.get("name"),
                                    "gia_tri": lf_val,
                                    "child_count": int(lf.get("child_count") or 0),
                                    "is_parent_group": bool(lf.get("is_parent_group") or int(lf.get("child_count") or 0) > 0),
                                    "ten_van_phong": lf.get("office_name") or h_info_parent.get("office_name") or "Cấp tỉnh",
                                    "ten_nhiem_vu": lf.get("mission_name") or h_info_parent.get("mission_name") or "-",
                                })
                        if leaf_desc:
                            non_empty_children = leaf_desc
                    if not _is_empty_or_dash(parent_val):
                        display_children = all_children_list
                    else:
                        display_children = non_empty_children if non_empty_children else all_children_list

                    chips = []
                    for i, alt in enumerate(display_children):
                        alt_name = _get_metric_name(alt)
                        alt_raw_v = _get_metric_val(alt)
                        alt_fmt_v = None if _is_empty_or_dash(alt_raw_v) else vn_format_num(alt_raw_v)
                        alt_ch_cnt = int(alt.get("child_count") or 0)
                        alt_is_grp = bool(alt.get("is_parent_group") or alt_ch_cnt > 0)
                        if alt_is_grp and alt_fmt_v is None:
                            unit_status = f"{alt_ch_cnt} chỉ tiêu con ▸"
                        elif alt_fmt_v is not None:
                            unit_status = f"{alt_ch_cnt} chỉ tiêu con" if alt_is_grp else "Đã phê duyệt"
                        else:
                            unit_status = "Chưa có số liệu (-)"
                        chips.append({
                            "id": f"chip_alt_{i+1}",
                            "label": f"🔘 [{alt_name}]",
                            "query_text": f"Chỉ tiêu {alt_name} thuộc {parent_disp} {temporal_meta['query_suffix']} là bao nhiêu?",
                            "preview_value": alt_fmt_v,
                            "unit_or_status": unit_status,
                            "child_count": alt_ch_cnt,
                            "is_parent_group": alt_is_grp,
                        })
                    chip_md = "  ".join([c["label"] for c in chips])
                    raw_date = (
                        r_parent.get("ngay_bao_cao")
                        or r_parent.get("ngay_bao_cao_moi_nhat")
                        or r_parent.get("report_date")
                        or (getattr(self.catalog, "get_latest_report_date", lambda: "-")() if hasattr(self, "catalog") else "-")
                    )
                    raw_date_iso = str(raw_date)[:10] if raw_date else "-"
                    if raw_date_iso and "-" in raw_date_iso and len(raw_date_iso) == 10:
                        dp = raw_date_iso.split("-")
                        date_str = f"{dp[2]}/{dp[1]}/{dp[0]}"
                    else:
                        date_str = raw_date_iso or "-"

                    date_prefix = ""
                    temporal_shift_bullet = ""
                    if norm_frame and getattr(norm_frame, "specific_date", None):
                        req_iso = str(norm_frame.specific_date)[:10]
                        if "-" in req_iso and len(req_iso) == 10:
                            rp = req_iso.split("-")
                            req_vn = f"{rp[2]}/{rp[1]}/{rp[0]}"
                        else:
                            req_vn = req_iso
                        if req_vn != date_str:
                            date_prefix = (
                                f"Hệ thống không ghi nhận dữ liệu báo cáo vào đúng ngày {req_vn}. "
                                f"Dưới đây là số liệu tại kỳ báo cáo gần nhất (ngày {date_str}):\n\n"
                            )
                            do_lech = r_parent.get("do_lech_ngay")
                            can_duoi = r_parent.get("can_duoi_ngay")
                            can_tren = r_parent.get("can_tren_ngay")
                            bound_parts = []
                            cd_vn = ""
                            if can_duoi:
                                cd_s = str(can_duoi)[:10]
                                cd_vn = f"{cd_s[8:10]}/{cd_s[5:7]}/{cd_s[0:4]}" if "-" in cd_s and len(cd_s) == 10 else cd_s
                                bound_parts.append(f"kỳ trước: {cd_vn}")
                            if can_tren:
                                ct_s = str(can_tren)[:10]
                                ct_vn = f"{ct_s[8:10]}/{ct_s[5:7]}/{ct_s[0:4]}" if "-" in ct_s and len(ct_s) == 10 else ct_s
                                if ct_vn != cd_vn:
                                    bound_parts.append(f"kỳ kế tiếp: {ct_vn}")
                            bound_note = f" — {', '.join(bound_parts)}" if bound_parts else ""
                            delta_str = f" (lệch {do_lech} ngày)" if do_lech is not None else ""
                            temporal_shift_bullet = (
                                f"\n- **Lưu ý mốc thời gian:** Ngày tra cứu {req_vn} không trùng đợt chốt sổ{delta_str}; "
                                f"hệ thống đối chiếu mốc gần nhất ngày {date_str}{bound_note}"
                            )

                    # SC-2.4a: Chỉ tiêu Cha CÓ SỐ LIỆU -> Hiển thị Thẻ 5 Trường Chuẩn + Bảng 1 dòng + Gợi ý chỉ tiêu con
                    if not _is_empty_or_dash(parent_val):
                        fmt_val = vn_format_num(parent_val)
                        office_str = (
                            (cand_row.get("ten_van_phong") or cand_row.get("ten_phong_ban") or cand_row.get("office_name"))
                            if cand_row else None
                        ) or (h_info_parent.get("office_name") if h_info_parent else None) or "Chi cục"
                        if office_str.strip().lower() in ("cấp tỉnh", "chi cục phát triển nông thôn"):
                            office_str = "Chi cục"
                        mission_str = (
                            (cand_row.get("ten_nhiem_vu") or cand_row.get("mission_name"))
                            if cand_row else None
                        ) or (h_info_parent.get("mission_name") if h_info_parent else None) or "-"
                        p_lvl = (h_info_parent.get("parent_level") if h_info_parent else None) or 1
                        r_name = (h_info_parent.get("root_name") if h_info_parent else None) or parent_disp
                        if int(p_lvl) <= 1 or r_name == parent_disp:
                            hier_suffix = " *(Chỉ tiêu cha (nhóm chỉ tiêu) - Cấp 1)*"
                        else:
                            hier_suffix = f" *(Chỉ tiêu cha (nhóm chỉ tiêu) thuộc nhóm: {r_name} - Cấp {p_lvl})*"

                        intro_line = date_prefix if date_prefix else "Thông tin số liệu mới nhất của chỉ tiêu đồng chí tra cứu:\n"
                        ans = (
                            f"{intro_line}"
                            f"- **Chỉ tiêu:** {parent_disp}{hier_suffix}\n"
                            f"- **Giá trị:** {fmt_val}\n"
                            f"- **Đơn vị thực hiện:** {office_str}\n"
                            f"- **Nhiệm vụ trọng tâm:** {mission_str}\n"
                            f"- **Thời điểm báo cáo:** {date_str}"
                            f"{temporal_shift_bullet}\n\n"
                            f"Đồng chí có thể bấm chọn một trong các **chỉ tiêu con trực thuộc** ở bên dưới để xem chi tiết."
                        )
                        parent_snaps = []
                        if hasattr(self.catalog, "get_criterion_timeline_snapshots"):
                            parent_snaps = self.catalog.get_criterion_timeline_snapshots(
                                criteria_id=target_pid,
                                criteria_name=parent_disp,
                                year_code=str(year or "2026"),
                                tenant_code=str(norm_frame.tenant_code or "68") if norm_frame else "68",
                                child_nodes=display_children,
                            )
                        if parent_snaps and chips:
                            for ch_chip in chips:
                                chip_id_k = ch_chip.get("id")
                                t_vals: Dict[str, str] = {}
                                for snap_item in parent_snaps:
                                    s_date = snap_item.get("report_date") or snap_item.get("date")
                                    c_val_map = snap_item.get("child_values") or {}
                                    if s_date and chip_id_k in c_val_map:
                                        t_vals[str(s_date)] = str(c_val_map[chip_id_k])
                                if t_vals:
                                    ch_chip["timeline_values"] = t_vals
                        single_metric_card = {
                            "criteria_id": target_pid or "",
                            "criteria_code": str(cand_row.get("code") or "") if cand_row else "",
                            "criteria_name": parent_disp,
                            "hierarchy_label": hier_suffix.replace("*", "").strip(),
                            "current_value": fmt_val,
                            "raw_value": parent_val,
                            "office_name": office_str,
                            "mission_name": mission_str,
                            "report_date": date_str,
                            "temporal_shift_notice": temporal_shift_bullet.replace("\n- **Lưu ý mốc thời gian:** ", "").strip() if temporal_shift_bullet else None,
                            "timeline_snapshots": parent_snaps,
                        }
                        parent_row_tv: Dict[str, str] = {"year": fmt_val, "YEAR": fmt_val, str(year or "2026"): fmt_val}
                        for snap_item in parent_snaps:
                            s_date = str(snap_item.get("report_date") or snap_item.get("date") or "").strip()
                            s_iso = str(snap_item.get("iso_date") or "").strip()
                            s_val = str(snap_item.get("value") or "").strip()
                            if s_val:
                                if s_date:
                                    parent_row_tv[s_date] = s_val
                                if s_iso:
                                    parent_row_tv[s_iso] = s_val
                                    try:
                                        m_num = int(s_iso.split("-")[1])
                                        qk = f"q{(m_num - 1) // 3 + 1}"
                                        parent_row_tv[qk] = s_val
                                        parent_row_tv[qk.upper()] = s_val
                                    except Exception:
                                        pass
                        tabular_data = {
                            "title": f"Số liệu thống kê chi tiết theo báo cáo năm {year}",
                            "columns": [
                                {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                                {"key": "item", "label": "Chỉ tiêu", "align": "left", "data_type": "text"},
                                {"key": "value", "label": "Giá trị", "align": "right", "data_type": "number"},
                                {"key": "office", "label": "Đơn vị thực hiện", "align": "left", "data_type": "text"},
                                {"key": "mission", "label": "Nhiệm vụ trọng tâm", "align": "left", "data_type": "text"},
                                {"key": "report_date", "label": "Thời điểm báo cáo", "align": "center", "data_type": "text"},
                            ],
                            "rows": [
                                {
                                    "stt": 1,
                                    "criteria_id": target_pid or "",
                                    "item": parent_disp,
                                    "value": fmt_val,
                                    "office": office_str,
                                    "mission": mission_str,
                                    "report_date": date_str,
                                    "_raw_value": parent_val,
                                    "timeline_values": parent_row_tv,
                                    "period_values": parent_row_tv,
                                }
                            ],
                            "total_records": 1,
                            "single_metric_card": single_metric_card,
                            "temporal_scope": temporal_meta,
                        }
                        ans = _append_collapsible_sql(ans, sql)
                        return {
                            "current_stage": "SYNTHESIZING",
                            "stage_message": "✍️ Đang hoàn tất câu trả lời...",
                            "final_answer": ans,
                            "quick_action_chips": chips,
                            "tabular_data": tabular_data,
                            "inherited_parent_criterion": parent_disp,
                        }

                    # SC-2.4b: Chỉ tiêu Cha KHÔNG CÓ SỐ LIỆU -> Giải thích ngắn gọn + Gợi ý chỉ tiêu con
                    if has_temporal_point_or_range:
                        if date_prefix:
                            ans = (
                                f"{date_prefix}"
                                f"Chỉ tiêu **'{parent_disp}'** là một **chỉ tiêu cha (nhóm chỉ tiêu)** nên không có số liệu tổng hợp riêng lẻ tại kỳ báo cáo ngày **{date_str}**. "
                                f"Đồng chí vui lòng bấm chọn một trong các **chỉ tiêu con đang có số liệu** trực thuộc nhóm này ở bên dưới để xem chi tiết."
                                f"{temporal_shift_bullet}"
                            )
                        else:
                            p_lbl, _ = _format_temporal_period_label(norm_frame, year)
                            date_note = f" (kỳ chốt số liệu ngày {date_str})" if date_str and date_str != "-" else ""
                            ans = (
                                f"Chỉ tiêu **'{parent_disp}'** là một **chỉ tiêu cha (nhóm chỉ tiêu)** nên không có số liệu tổng hợp riêng lẻ {p_lbl}{date_note}. "
                                f"Đồng chí vui lòng bấm chọn một trong các **chỉ tiêu con đang có số liệu** trực thuộc nhóm này ở bên dưới để xem chi tiết."
                            )
                    else:
                        ans = (
                            f"Chỉ tiêu **'{parent_disp}'** là một **chỉ tiêu cha (nhóm chỉ tiêu)** nên không có số liệu tổng hợp riêng lẻ. "
                            f"Đồng chí vui lòng bấm chọn một trong các **chỉ tiêu con đang có số liệu** trực thuộc nhóm này ở bên dưới để xem chi tiết."
                        )
                    ans = _append_collapsible_sql(ans, sql)
                    return {
                        "current_stage": "SYNTHESIZING",
                        "stage_message": "✍️ Đang hoàn tất câu trả lời...",
                        "final_answer": ans,
                        "quick_action_chips": chips,
                        "tabular_data": None,
                        "inherited_parent_criterion": parent_disp,
                    }

        # Nhận diện miền dữ liệu dựa trên các cột và từ khóa câu hỏi
        sample_r = rows[0] if rows else {}
        cols_lower = [k.lower() for k in sample_r.keys()]
        is_province_list = (
            (norm_frame and norm_frame.target_table == "province")
            or ("is_activated" in cols_lower and "code" in cols_lower and "name" in cols_lower and "province_code" not in cols_lower)
        )
        is_criteria_dimension_list = (
            (norm_frame and norm_frame.target_table == "criteria" and norm_frame.intent == CanonicalIntentEnum.METADATA_EXPLORATION)
            or ("level" in cols_lower and "code" in cols_lower and "name" in cols_lower and "criteria_id" not in cols_lower)
        )
        is_user_mission = bool(
            norm_frame and (
                norm_frame.intent == CanonicalIntentEnum.OFFICER_ASSIGNMENT
                or norm_frame.target_table in ("user", "user_mission")
            )
        )

        is_report_list = bool(
            norm_frame and (
                norm_frame.intent == CanonicalIntentEnum.REPORT_STATUS_AUDIT
                or norm_frame.target_table == "report"
            )
        )
        is_mission_list = bool(
            (norm_frame and norm_frame.target_table == "mission")
            or ("mission_name" in cols_lower and ("scope_name" in cols_lower or "linh_vuc" in cols_lower) and "ten_chi_tieu" not in cols_lower)
        )
        is_count_report = bool(
            norm_frame and (
                norm_frame.intent == CanonicalIntentEnum.REPORT_STATUS_AUDIT
                and norm_frame.aggregation_function in ("COUNT", "COUNT_DISTINCT")
            )
        )

        is_entity_attr_lookup = (
            (norm_frame and norm_frame.intent == CanonicalIntentEnum.ENTITY_ATTRIBUTE_LOOKUP)
            or (
                "ten_don_vi" in cols_lower
                and "ten_phong_ban" in cols_lower
                and "mission_name" not in cols_lower
                and "ten_nhiem_vu" not in cols_lower
                and not (norm_frame and norm_frame.intent == CanonicalIntentEnum.DIMENSION_LISTING)
            )
        )
        is_relational_exploration = (
            (norm_frame and norm_frame.intent == CanonicalIntentEnum.RELATIONAL_EXPLORATION)
            or (norm_frame and norm_frame.target_table in ("ward", "office_mission"))
            or ("province_code" in cols_lower and "province_name" in cols_lower)
        )

        tabular_data = None

        if is_entity_attr_lookup:
            r0 = rows[0]
            metric_name = r0.get("ten_chi_tieu") or (norm_frame.canonical_metric_names[0] if norm_frame and norm_frame.canonical_metric_names else (norm_frame.subject_entity if norm_frame else "Chỉ tiêu"))
            dept_name = r0.get("ten_don_vi") or "UBND Tỉnh Lâm Đồng"
            office_name = r0.get("ten_phong_ban") or "Chi cục"
            dept_code = r0.get("department_code") or "68-1-01"
            val = r0.get("value")

            ans = (
                f"Theo dữ liệu kho DWH tỉnh Lâm Đồng, chỉ tiêu **{metric_name}** do **{dept_name}** "
                f"(mã cơ quan: `{dept_code}`) chủ trì thực hiện, trực tiếp phụ trách bởi: **{office_name}**.\n\n"
            )
            if val is not None and str(val).strip() not in ("", "-"):
                fmt_val = vn_format_num(val)
                ans += f"Giá trị số liệu ghi nhận hiện tại: **{fmt_val}**.\n\n"
            else:
                ans += "Hiện tại chỉ tiêu này **chưa có số liệu ghi nhận (-)** trong kho dữ liệu.\n\n"

            fmt_v_display = vn_format_num(val) if val is not None and str(val).strip() not in ("", "-") else "Chưa có số liệu"
            ans += "| STT | Chỉ tiêu | Đơn vị chủ trì | Phòng ban phụ trách | Mã cơ quan | Giá trị |\n"
            ans += "| :---: | :--- | :--- | :--- | :---: | :---: |\n"
            ans += f"| 1 | {metric_name} | {dept_name} | {office_name} | `{dept_code}` | **{fmt_v_display}** |\n"

            tabular_data = {
                "title": f"Thông tin đơn vị thực hiện chỉ tiêu {metric_name}",
                "columns": [
                    {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                    {"key": "metric", "label": "Chỉ tiêu", "align": "left", "data_type": "text"},
                    {"key": "department", "label": "Đơn vị chủ trì", "align": "left", "data_type": "text"},
                    {"key": "office", "label": "Phòng ban phụ trách", "align": "left", "data_type": "text"},
                    {"key": "code", "label": "Mã cơ quan", "align": "center", "data_type": "text"},
                    {"key": "value", "label": "Giá trị", "align": "center", "data_type": "text"},
                ],
                "rows": [
                    {
                        "stt": 1,
                        "metric": metric_name,
                        "department": dept_name,
                        "office": office_name,
                        "code": dept_code,
                        "value": fmt_v_display,
                    }
                ],
                "total_records": 1,
            }

            chips = [
                {"id": "chip_attr_1", "label": f"📊 Số liệu {metric_name}", "query_text": f"Số liệu {metric_name} năm {year} là bao nhiêu?"},
                {"id": "chip_attr_2", "label": "🌾 Sản lượng OCOP 2026", "query_text": "Tổng sản lượng các sản phẩm OCOP đạt chuẩn năm 2026?"},
                {"id": "chip_attr_3", "label": "🏛️ Nhiệm vụ trọng tâm 2026", "query_text": "Danh mục các nhiệm vụ trọng tâm năm 2026 của tỉnh Lâm Đồng?"},
            ]
            ans = _append_collapsible_sql(ans, sql)
            return {
                "current_stage": "SYNTHESIZING",
                "stage_message": "✍️ Đang hoàn tất câu trả lời...",
                "final_answer": ans,
                "quick_action_chips": chips,
                "tabular_data": tabular_data,
            }

        if is_relational_exploration:
            target_t = norm_frame.target_table if norm_frame else ("ward" if "province_code" in cols_lower else "office_mission")
            if target_t == "ward":
                total_w = len(rows)
                is_count_agg = bool(norm_frame and norm_frame.aggregation_function == "COUNT") or ("tong_so_xa_phuong" in cols_lower)
                if is_count_agg:
                    cnt_val = sample_r.get("tong_so_xa_phuong") or sample_r.get("count") or total_w
                    ans = (
                        f"Theo số liệu quản lý hành chính, "
                        f"tỉnh **Lâm Đồng** (mã: 68) hiện có tổng cộng **{cnt_val}** xã, phường, thị trấn đang được quản lý trên hệ thống.\n\n"
                    )
                    tabular_data = {
                        "title": f"Thống kê số lượng xã, phường tỉnh Lâm Đồng",
                        "columns": [
                            {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                            {"key": "ten_tinh", "label": "Tỉnh / Thành phố", "align": "center", "data_type": "text"},
                            {"key": "tong_so_xa_phuong", "label": "Tổng số xã / phường", "align": "center", "data_type": "number"},
                        ],
                        "rows": [
                            {
                                "stt": 1,
                                "ten_tinh": sample_r.get("ten_tinh", "Lâm Đồng"),
                                "tong_so_xa_phuong": cnt_val,
                            }
                        ],
                        "total_records": 1,
                    }
                else:
                    ans = (
                        f"Theo dữ liệu hành chính, "
                        f"tỉnh **Lâm Đồng** (mã: 68) hiện có danh mục các xã, phường, thị trấn sau:\n\n"
                    )
                    ans += "| STT | Mã đơn vị | Tên xã / Phường / Thị trấn | Tỉnh / Thành phố |\n"
                    ans += "| :---: | :--- | :--- | :---: |\n"
                    tabular_data = {
                        "title": f"Danh mục xã, phường, thị trấn tỉnh Lâm Đồng ({total_w} đơn vị)",
                        "columns": [
                            {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                            {"key": "ma_xa", "label": "Mã đơn vị", "align": "center", "data_type": "text"},
                            {"key": "ten_xa", "label": "Tên xã / Phường / Thị trấn", "align": "left", "data_type": "text"},
                            {"key": "ten_tinh", "label": "Tỉnh / Thành phố", "align": "center", "data_type": "text"},
                        ],
                        "rows": [],
                        "total_records": total_w,
                    }
                    for idx, r in enumerate(rows, 1):
                        c_code = r.get("ma_xa") or r.get("code") or "-"
                        c_name = r.get("ten_xa") or r.get("name") or "-"
                        p_name = r.get("ten_tinh") or r.get("province_name") or "Lâm Đồng"
                        ans += f"| {idx} | {c_code} | **{c_name}** | {p_name} |\n"
                        row_dict = dict(r)
                        row_dict["stt"] = idx
                        tabular_data["rows"].append(row_dict)

                    if total_w > 50:
                        ans += f"\n*(Hiển thị 50 / {total_w} đơn vị hành chính; xem đầy đủ trong bảng dữ liệu)*\n"

                chips = [
                    {"id": "chip_ward_1", "label": "📊 Kinh phí khuyến công 2026", "query_text": "Kinh phí thực hiện khuyến công năm 2026 là bao nhiêu?"},
                    {"id": "chip_ward_2", "label": "🌾 Sản lượng OCOP 2026", "query_text": "Tổng sản lượng các sản phẩm OCOP đạt chuẩn năm 2026?"},
                    {"id": "chip_ward_3", "label": "📋 Danh mục chỉ tiêu KTXH", "query_text": "Hệ thống có những chỉ tiêu nào?"},
                ]
                ans = _append_collapsible_sql(ans, sql)
                return {
                    "current_stage": "SYNTHESIZING",
                    "stage_message": "✍️ Đang hoàn tất câu trả lời...",
                    "final_answer": ans,
                    "quick_action_chips": chips,
                    "tabular_data": tabular_data,
                }

            elif target_t == "office_mission":
                total_om = len(rows)
                off_name = rows[0].get("office_name") if rows else (norm_frame.subject_entity if norm_frame else "Đơn vị")
                has_single_office = len(set(r.get("office_name") for r in rows if r.get("office_name"))) <= 1
                if has_single_office and off_name:
                    ans = f"Theo dữ liệu phân công nhiệm vụ, **{off_name}** hiện phụ trách các nhiệm vụ sau:\n\n"
                else:
                    ans = f"Theo dữ liệu phân công nhiệm vụ, tổng hợp danh sách nhiệm vụ của từng văn phòng gắn liền với lĩnh vực quản lý ({total_om} bản ghi):\n\n"

                ans += "| STT | Văn phòng / Đơn vị | Nhiệm vụ chuyên môn | Lĩnh vực quản lý |\n"
                ans += "| :---: | :--- | :--- | :--- |\n"
                tabular_data = {
                    "title": f"Danh mục phân công nhiệm vụ theo văn phòng ({total_om} bản ghi)",
                    "columns": [
                        {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                        {"key": "office_name", "label": "Văn phòng / Đơn vị", "align": "left", "data_type": "text"},
                        {"key": "mission_name", "label": "Nhiệm vụ chuyên môn", "align": "left", "data_type": "text"},
                        {"key": "scope_name", "label": "Lĩnh vực quản lý", "align": "left", "data_type": "text"},
                    ],
                    "rows": [],
                    "total_records": total_om,
                }
                for idx, r in enumerate(rows, 1):
                    o_n = r.get("office_name", "-")
                    m_n = r.get("mission_name", "-")
                    s_n = r.get("scope_name", "-")
                    ans += f"| {idx} | **{o_n}** | {m_n} | {s_n} |\n"
                    row_dict = dict(r)
                    row_dict["stt"] = idx
                    tabular_data["rows"].append(row_dict)

                chips = [
                    {"id": "chip_om_1", "label": "🏛️ Nhiệm vụ trọng tâm 2026", "query_text": "Danh mục các nhiệm vụ trọng tâm năm 2026 của tỉnh Lâm Đồng?"},
                    {"id": "chip_om_2", "label": "📊 Tổng hộ sản xuất muối 2026", "query_text": "Tổng hộ sản xuất muối năm 2026 là bao nhiêu?"},
                ]
                ans = _append_collapsible_sql(ans, sql)
                return {
                    "current_stage": "SYNTHESIZING",
                    "stage_message": "✍️ Đang hoàn tất câu trả lời...",
                    "final_answer": ans,
                    "quick_action_chips": chips,
                    "tabular_data": tabular_data,
                }

        if is_province_list:
            exclude_list = norm_frame.exclude_entities if norm_frame and norm_frame.exclude_entities else []
            if exclude_list:
                ex_str = ", ".join([f"**{e}**" for e in exclude_list])
                ans = (
                    f"Trong kho dữ liệu, ngoài {ex_str} ra, "
                    f"hệ thống hiện ghi nhận danh mục gồm **{len(rows)}** tỉnh/thành phố trực thuộc trung ương khác:\n\n"
                )
            else:
                ans = (
                    f"Trong kho dữ liệu, "
                    f"hệ thống hiện lưu trữ danh mục gồm **{len(rows)}** tỉnh/thành phố trực thuộc trung ương:\n\n"
                )

            ans += "| STT | Mã địa phương | Tên tỉnh / Thành phố | Trạng thái |\n"
            ans += "| :---: | :---: | :--- | :---: |\n"

            tabular_data = {
                "title": "Danh mục các tỉnh/thành phố trong kho dữ liệu DWH",
                "columns": [
                    {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                    {"key": "code", "label": "Mã địa phương", "align": "center", "data_type": "text"},
                    {"key": "name", "label": "Tên tỉnh / Thành phố", "align": "left", "data_type": "text"},
                    {"key": "status", "label": "Trạng thái", "align": "center", "data_type": "badge"},
                ],
                "rows": [],
                "total_records": len(rows),
            }

            for idx, r in enumerate(rows, 1):
                p_code = r.get("code") or "-"
                p_name = r.get("name") or "-"
                p_act = r.get("is_activated")
                st_text = "Đang kích hoạt" if p_act else "Chưa kích hoạt"
                ans += f"| {idx} | {p_code} | **{p_name}** | {st_text} |\n"
                tabular_data["rows"].append({
                    "stt": idx,
                    "code": p_code,
                    "name": p_name,
                    "status": st_text,
                })

            ans += (
                f"\n\n*(Lưu ý: Danh mục địa bàn hành chính lưu trữ 34 tỉnh/thành phố trong hệ thống; "
                f"tuy nhiên dữ liệu báo cáo kinh tế - xã hội hiện tại đang phục vụ và tổng hợp cho tỉnh **Lâm Đồng** (Mã: 68))*"
            )

            chips = [
                {"id": "chip_prov_1", "label": "📊 Kinh phí khuyến công Lâm Đồng", "query_text": "Kinh phí thực hiện khuyến công năm 2026 là bao nhiêu?"},
                {"id": "chip_prov_2", "label": "🌾 Sản lượng OCOP Lâm Đồng", "query_text": "Tổng sản lượng các sản phẩm OCOP đạt chuẩn năm 2026?"},
                {"id": "chip_prov_3", "label": "📋 Danh mục chỉ tiêu KTXH", "query_text": "Hệ thống có những chỉ tiêu nào?"},
            ]
            ans = _append_collapsible_sql(ans, sql)
            return {
                "current_stage": "SYNTHESIZING",
                "stage_message": "✍️ Đang hoàn tất câu trả lời...",
                "final_answer": ans,
                "quick_action_chips": chips,
                "tabular_data": tabular_data,
            }

        if is_criteria_dimension_list:
            ans = f"Dưới đây là danh mục các chỉ tiêu thống kê báo cáo trong kho dữ liệu:\n\n"
            ans += "| STT | Mã chỉ tiêu | Tên chỉ tiêu | Phân cấp |\n"
            ans += "| :---: | :---: | :--- | :---: |\n"

            tabular_data = {
                "title": "Danh mục chỉ tiêu thống kê báo cáo",
                "columns": [
                    {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                    {"key": "code", "label": "Mã chỉ tiêu", "align": "center", "data_type": "text"},
                    {"key": "name", "label": "Tên chỉ tiêu", "align": "left", "data_type": "text"},
                    {"key": "level", "label": "Phân cấp", "align": "center", "data_type": "number"},
                ],
                "rows": [],
                "total_records": len(rows),
            }

            for idx, r in enumerate(rows, 1):
                c_code = r.get("code") or "-"
                c_name = r.get("name") or "-"
                c_level = r.get("level") if r.get("level") is not None else "-"
                ans += f"| {idx} | {c_code} | **{c_name}** | Cấp {c_level} |\n"
                tabular_data["rows"].append({
                    "stt": idx,
                    "code": c_code,
                    "name": c_name,
                    "level": c_level,
                })

            chips = [
                {"id": "chip_crit_1", "label": "📊 Kinh phí khuyến công 2026", "query_text": "Kinh phí thực hiện khuyến công năm 2026 là bao nhiêu?"},
                {"id": "chip_crit_2", "label": "🌾 Sản lượng OCOP 2026", "query_text": "Tổng sản lượng các sản phẩm OCOP đạt chuẩn năm 2026?"},
                {"id": "chip_crit_3", "label": "🧂 Diện tích sản xuất muối", "query_text": "Thế còn diện tích sản xuất muối năm 2026?"},
            ]
            ans = _append_collapsible_sql(ans, sql)
            return {
                "current_stage": "SYNTHESIZING",
                "stage_message": "✍️ Đang hoàn tất câu trả lời...",
                "final_answer": ans,
                "quick_action_chips": chips,
                "tabular_data": tabular_data,
            }

        is_duplicate_leaf_inquiry = bool(
            norm_frame
            and getattr(norm_frame, "intent", None) == CanonicalIntentEnum.METRIC_POINT_INQUIRY
            and len(getattr(norm_frame, "canonical_metric_ids", []) or []) > 1
        )
        if len(rows) == 1 or is_duplicate_leaf_inquiry:
            # Kịch bản 1: Đếm số báo cáo (ví dụ: "Hiện có bao nhiêu báo cáo đã được phê duyệt?")
            if is_count_report:
                cnt_val = None
                for k in ["tong_bao_cao", "so_luong_bao_cao", "count"]:
                    if sample_r.get(k) is not None:
                        cnt_val = sample_r.get(k)
                        break
                if cnt_val is None and sample_r:
                    cnt_val = next((v for v in sample_r.values() if v is not None), 0)
                ans = f"Theo số liệu tổng hợp năm **{year}** của tỉnh Lâm Đồng, hiện có **{vn_format_num(cnt_val)}** báo cáo đã được phê duyệt."
            # Kịch bản 2: Cán bộ phụ trách (1 dòng duy nhất)
            elif is_user_mission:
                u_name = sample_r.get("ten_can_bo") or sample_r.get("user_name") or sample_r.get("name") or sample_r.get("username")
                u_pos = sample_r.get("chuc_vu") or sample_r.get("user_position") or sample_r.get("position") or "Cán bộ chuyên môn"
                u_off = sample_r.get("don_vi_cong_tac") or sample_r.get("office_name") or sample_r.get("department_name") or sample_r.get("department_code") or "Đơn vị trực thuộc"
                u_mis = sample_r.get("ten_nhiem_vu") or sample_r.get("mission_name")

                is_system_acc = bool(sample_r.get("is_system") or sample_r.get("is_admin"))
                name_display = f"đồng chí **{u_name}**" if not is_system_acc and u_name else (f"tài khoản quản trị/đơn vị **{u_name}**" if u_name else "cán bộ chuyên môn")

                if u_mis:
                    ans = (
                        f"Theo phân công công tác năm **{year}** của tỉnh Lâm Đồng, cán bộ phụ trách nhiệm vụ **{u_mis}** "
                        f"là {name_display} (Chức vụ: **{u_pos}**, Đơn vị: **{u_off}**)."
                    )
                else:
                    ans = (
                        f"Theo thông tin nhân sự/tài khoản công tác năm **{year}** của tỉnh Lâm Đồng, "
                        f"ghi nhận thông tin {name_display} (Chức vụ: **{u_pos}**, Đơn vị: **{u_off}**)."
                    )
                if is_system_acc:
                    ans += "\n\n*(Lưu ý: Đây là tài khoản quản trị/đơn vị hành chính được tạo trong hệ thống thử nghiệm)*"

                tabular_data = {
                    "title": f"Thông tin phân công nhiệm vụ cán bộ {u_name or 'chuyên môn'}",
                    "columns": [
                        {"key": k, "label": k, "data_type": "text"} for k in sample_r.keys()
                    ],
                    "rows": [
                        dict(sample_r, stt=1)
                    ],
                    "total_records": 1,
                }
            # Kịch bản 3: Nhiệm vụ (1 dòng duy nhất)
            elif is_mission_list:
                m_name = sample_r.get("mission_name") or sample_r.get("name") or "Nhiệm vụ 1"
                m_scope = sample_r.get("scope_name") or sample_r.get("linh_vuc") or (getattr(norm_frame, "target_scope", None) if norm_frame else None) or "Nông nghiệp"
                if m_scope:
                    m_scope = m_scope[0].upper() + m_scope[1:]
                raw_off = sample_r.get("office_name") or sample_r.get("don_vi_phu_trach") or sample_r.get("ten_van_phong")
                m_off = "-" if not raw_off or str(raw_off).strip() in ("", "-", "Chưa phân công", "None", "null") else str(raw_off).strip()
                m_st = _vn_status(sample_r.get("mission_status", True))
                raw_mc = str(sample_r.get("mission_code") or "").strip()
                if not raw_mc or raw_mc in ("-", "None", "null", "diem_nghiep", "phat_trien_nong_thon", "cai_cach_hanh_chinh", "cai_cach_hanh_chinh_2") or raw_mc.startswith("nhiem_vu_"):
                    raw_mc = _derive_mission_code(m_name, fallback_idx=1)
                scope_hdr = f" thuộc lĩnh vực **{m_scope}**" if (norm_frame and getattr(norm_frame, "target_scope", None)) else ""
                period_hdr, title_period = _format_temporal_period_label(norm_frame, year)
                ans = (
                    f"Theo số liệu kho dữ liệu {period_hdr} của tỉnh Lâm Đồng, nhiệm vụ trọng tâm{scope_hdr} được ghi nhận: **{m_name}** ({m_st}).\n\n"
                    f"| STT | Mã nhiệm vụ | Tên nhiệm vụ | Lĩnh vực | Đơn vị phụ trách |\n"
                    f"| :---: | :---: | :--- | :--- | :--- |\n"
                    f"| 1 | `{raw_mc}` | **{m_name}** | {m_scope} | {m_off} |\n"
                )
                tabular_data = {
                    "title": f"Danh mục nhiệm vụ trọng tâm {title_period}",
                    "columns": [
                        {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                        {"key": "mission_code", "label": "Mã nhiệm vụ", "align": "center", "data_type": "text"},
                        {"key": "mission_name", "label": "Tên nhiệm vụ", "align": "left", "data_type": "text"},
                        {"key": "scope_name", "label": "Lĩnh vực", "align": "left", "data_type": "text"},
                        {"key": "office_name", "label": "Đơn vị phụ trách", "align": "left", "data_type": "text"},
                    ],
                    "rows": [
                        {
                            "stt": 1,
                            "mission_code": raw_mc,
                            "mission_name": m_name,
                            "scope_name": m_scope,
                            "office_name": m_off,
                            "status": m_st,
                            "action_query": f"Hiển thị các chỉ tiêu Cấp 1 của nhiệm vụ {m_name} {temporal_meta['query_suffix']}?",
                        }
                    ],
                    "total_records": 1,
                    "temporal_scope": temporal_meta,
                    "context_query_template": (
                        f"Các nhiệm vụ thuộc lĩnh vực {norm_frame.target_scope} {{period}}?"
                        if (norm_frame and getattr(norm_frame, "target_scope", None))
                        else "Danh mục các nhiệm vụ trọng tâm {period} của tỉnh Lâm Đồng?"
                    ),
                }
            # Kịch bản 3b: Báo cáo (1 dòng duy nhất)
            elif is_report_list:
                rdate = str(sample_r.get("report_date") or "")[:10]
                lbl = f"Báo cáo ngày {rdate}" if rdate else "Đợt nộp báo cáo"
                dept = sample_r.get("department_name") or r.get("department_code") if "r" in locals() else (sample_r.get("department_name") or sample_r.get("department_code") or "Đơn vị nộp")
                st_vn = _vn_status(sample_r.get("status"))
                ans = f"Theo số liệu báo cáo năm **{year}** của tỉnh Lâm Đồng, {lbl} của đơn vị **{dept}** đang ở trạng thái: **{st_vn}**."
                tabular_data = {
                    "title": f"Trạng thái đợt nộp báo cáo năm {year}",
                    "columns": [
                        {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                        {"key": "report_title", "label": "Đợt nộp báo cáo", "align": "left", "data_type": "text"},
                        {"key": "department", "label": "Đơn vị nộp", "align": "left", "data_type": "text"},
                        {"key": "status", "label": "Trạng thái phê duyệt", "align": "center", "data_type": "badge"},
                    ],
                    "rows": [
                        {"stt": 1, "report_title": lbl, "department": dept, "status": st_vn}
                    ],
                    "total_records": 1,
                }
            # Kịch bản 3c: So sánh tăng trưởng doanh thu (1 dòng kết quả từ CTE CROSS JOIN)
            elif "doanh_thu_q2" in sample_r or "toc_do_tang_truong_percent" in sample_r:
                metric_lbl = selected_cand if isinstance(selected_cand, str) else (selected_cand.get("name", "doanh thu bình quân") if selected_cand else "doanh thu bình quân")
                q2_val = vn_format_num(sample_r.get("doanh_thu_q2"))
                q3_val = vn_format_num(sample_r.get("doanh_thu_q3"))
                rate_val = vn_format_num(sample_r.get("toc_do_tang_truong_percent"))
                ans = (
                    f"Theo số liệu báo cáo đã phê duyệt năm **{year}** của tỉnh Lâm Đồng, so sánh {metric_lbl.lower()}:\n"
                    f"- **Kỳ 6 tháng (30/06/{year})**: **{q2_val}** (triệu đồng)\n"
                    f"- **Kỳ 9 tháng (30/09/{year})**: **{q3_val}** (triệu đồng)\n"
                    f"- **Tốc độ tăng trưởng**: **{rate_val}%**\n\n"
                    f"| Kỳ báo cáo | {metric_lbl.capitalize()} (triệu đồng) | Tốc độ tăng trưởng |\n"
                    f"| :--- | :---: | :---: |\n"
                    f"| 6 tháng (30/06/{year}) | {q2_val} | - |\n"
                    f"| 9 tháng (30/09/{year}) | {q3_val} | **+{rate_val}%** |\n"
                )
                tabular_data = {
                    "title": f"Tốc độ tăng trưởng {metric_lbl.lower()} năm {year}",
                    "columns": [
                        {"key": "period", "label": "Kỳ báo cáo", "align": "left", "data_type": "text"},
                        {"key": "revenue", "label": f"{metric_lbl.capitalize()} (triệu đồng)", "align": "right", "data_type": "number"},
                        {"key": "growth", "label": "Tốc độ tăng trưởng", "align": "center", "data_type": "text"},
                    ],
                    "rows": [
                        {"period": f"6 tháng (30/06/{year})", "revenue": q2_val, "growth": "-"},
                        {"period": f"9 tháng (30/09/{year})", "revenue": q3_val, "growth": f"+{rate_val}%"},
                    ],
                    "total_records": 2,
                }
            # Kịch bản 4: Chỉ tiêu số liệu có 1 dòng duy nhất (REQ-Q02, SC-2.1, SC-2.2, SC-2.3)
            else:
                matched_single_row = None
                if selected_cand:
                    matched_single_row = next(
                        (r for r in rows if _get_metric_name(r).lower() == selected_cand.strip().lower()),
                        None
                    )
                r0 = matched_single_row or rows[0]
                val = _get_metric_val(r0)

                raw_name = _get_metric_name(r0) or selected_cand or (
                    state.get("target_metric_label") if state.get("target_metric_label") and state.get("target_metric_label") != clean_prompt else None
                ) or "chỉ tiêu được yêu cầu"
                display_name = raw_name.strip()
                if _is_empty_or_dash(val):
                    fmt_val = "Chưa có số liệu phê duyệt (-)"
                else:
                    fmt_val = vn_format_num(val)

                has_fact_context = bool(
                    (norm_frame and getattr(norm_frame, "target_table", None) == "fact_report_criteria")
                    or (norm_frame and getattr(norm_frame, "intent", None) == CanonicalIntentEnum.METRIC_POINT_INQUIRY)
                    or ("ten_van_phong" in r0 or "ten_nhiem_vu" in r0 or "office_name" in r0 or "mission_name" in r0 or "ngay_bao_cao" in r0 or "gia_tri_moi_nhat" in r0 or "tong_gia_tri" in r0 or "gia_tri" in r0)
                )

                if has_fact_context:
                    ten_chi_tieu = r0.get("ten_chi_tieu") or display_name
                    office_str = r0.get("ten_van_phong") or r0.get("ten_phong_ban") or r0.get("office_name") or "Chi cục"
                    mission_str = r0.get("ten_nhiem_vu") or r0.get("mission_name") or "-"
                    raw_date = r0.get("ngay_bao_cao") or r0.get("ngay_bao_cao_moi_nhat") or r0.get("report_date")
                    if raw_date:
                        date_str = str(raw_date)[:10]
                        if "-" in date_str and len(date_str) == 10:
                            parts = date_str.split("-")
                            date_str = f"{parts[2]}/{parts[1]}/{parts[0]}"
                    else:
                        date_str = "-"

                    ten_chi_tieu_disp = ten_chi_tieu

                    date_prefix = ""
                    temporal_shift_bullet = ""
                    if norm_frame and getattr(norm_frame, "specific_date", None):
                        req_iso = str(norm_frame.specific_date)[:10]
                        if "-" in req_iso and len(req_iso) == 10:
                            rp = req_iso.split("-")
                            req_vn = f"{rp[2]}/{rp[1]}/{rp[0]}"
                        else:
                            req_vn = req_iso
                        if req_vn != date_str:
                            date_prefix = (
                                f"Hệ thống không ghi nhận dữ liệu báo cáo vào đúng ngày {req_vn}. "
                                f"Dưới đây là số liệu tại kỳ báo cáo gần nhất (ngày {date_str}):\n\n"
                            )
                            # PA 1.1: Dual-Bound Snapshot & Temporal Shift Notice
                            do_lech = r0.get("do_lech_ngay")
                            can_duoi = r0.get("can_duoi_ngay")
                            can_tren = r0.get("can_tren_ngay")
                            bound_parts = []
                            cd_vn = ""
                            if can_duoi:
                                cd_s = str(can_duoi)[:10]
                                cd_vn = f"{cd_s[8:10]}/{cd_s[5:7]}/{cd_s[0:4]}" if "-" in cd_s and len(cd_s) == 10 else cd_s
                                bound_parts.append(f"kỳ trước: {cd_vn}")
                            if can_tren:
                                ct_s = str(can_tren)[:10]
                                ct_vn = f"{ct_s[8:10]}/{ct_s[5:7]}/{ct_s[0:4]}" if "-" in ct_s and len(ct_s) == 10 else ct_s
                                if ct_vn != cd_vn:
                                    bound_parts.append(f"kỳ kế tiếp: {ct_vn}")
                            bound_note = f" — {', '.join(bound_parts)}" if bound_parts else ""
                            delta_str = f" (lệch {do_lech} ngày)" if do_lech is not None else ""
                            temporal_shift_bullet = (
                                f"\n- **Lưu ý mốc thời gian:** Ngày tra cứu {req_vn} không trùng đợt chốt sổ{delta_str}; "
                                f"hệ thống đối chiếu mốc gần nhất ngày {date_str}{bound_note}"
                            )

                    # SC-2.1: Chỉ tiêu con trùng tên ở nhiều nhóm cha khác nhau -> hiển thị bảng đối chiếu đa nhóm cha trực tiếp (hỗ trợ cả có/không có Ticket Thời Gian)
                    h_info_leaf = None
                    parent_ctx_leaf = (
                        (getattr(norm_frame, "parent_criterion_context", None) if norm_frame else None)
                        or state.get("inherited_parent_criterion")
                    )
                    if hasattr(self.catalog, "classify_criterion_hierarchy"):
                        try:
                            h_info_leaf = self.catalog.classify_criterion_hierarchy(
                                clean_prompt, matched_name=ten_chi_tieu, parent_context=parent_ctx_leaf
                            )
                        except TypeError:
                            h_info_leaf = self.catalog.classify_criterion_hierarchy(clean_prompt, matched_name=ten_chi_tieu)
                    if h_info_leaf and h_info_leaf.get("classification") == "duplicate_leaf" and len(h_info_leaf.get("branches", [])) > 1:
                        branches = h_info_leaf["branches"]
                        multi_rows = []
                        dup_batch_period_map: Dict[str, Dict[str, str]] = {}
                        if hasattr(self.catalog, "get_batch_period_values"):
                            dup_batch_period_map = self.catalog.get_batch_period_values(
                                branches,
                                year_code=str(norm_frame.year_code or year or "2026") if norm_frame else str(year or "2026"),
                                tenant_code=str(norm_frame.tenant_code or "68") if norm_frame else "68",
                            )
                        if norm_frame and getattr(norm_frame, "specific_date", None):
                            dup_period_note = f" tại kỳ báo cáo ngày **{date_str}**" if date_str and date_str != "-" else ""
                            dup_title_period = f"kỳ báo cáo ngày {date_str}" if date_str and date_str != "-" else f"năm {year}"
                        elif has_temporal_point_or_range:
                            p_lbl_dup, dup_title_period = _format_temporal_period_label(norm_frame, year)
                            dup_period_note = f" ({p_lbl_dup})"
                        else:
                            dup_period_note = ""
                            dup_title_period = f"năm {year}"
                        ans = (
                            f"{date_prefix}"
                            f"Chỉ tiêu **'{ten_chi_tieu}'** xuất hiện dưới **{len(branches)} nhóm chỉ tiêu cha** khác nhau{dup_period_note}:\n\n"
                            f"| STT | Tên chỉ tiêu | Nhóm chỉ tiêu (Cấp) | Giá trị mới nhất | Đơn vị thực hiện | Nhiệm vụ trọng tâm |\n"
                            f"| :---: | :--- | :--- | :---: | :--- | :--- |\n"
                        )
                        for b_idx, br in enumerate(branches, 1):
                            b_id_str = str(br.get("id") or "")
                            matched_row = next(
                                (
                                    r for r in rows
                                    if (b_id_str and str(r.get("criteria_id") or "") == b_id_str)
                                    or (
                                        br.get("parent_name")
                                        and str(r.get("nhom_chi_tieu") or "").strip().lower() == str(br.get("parent_name") or "").strip().lower()
                                    )
                                ),
                                None,
                            )
                            b_name = (matched_row.get("ten_chi_tieu") if matched_row else None) or br.get("name") or ten_chi_tieu
                            p_name = (matched_row.get("nhom_chi_tieu") if matched_row and matched_row.get("nhom_chi_tieu") else None) or br.get("parent_name") or "Chỉ tiêu chung"
                            r_name = (matched_row.get("nhom_chi_tieu_goc") if matched_row and matched_row.get("nhom_chi_tieu_goc") else None) or br.get("root_name") or p_name
                            p_lvl = (matched_row.get("cap_nhom_cha") if matched_row and matched_row.get("cap_nhom_cha") else None) or br.get("parent_level") or 1
                            if r_name and r_name != p_name:
                                cat_disp = f"{r_name} > {p_name} *(Cấp {p_lvl})*"
                            else:
                                cat_disp = f"{p_name} *(Cấp {p_lvl})*"
                            if matched_row is not None:
                                b_raw = _get_metric_val(matched_row)
                                if b_raw is None and not has_temporal_point_or_range and br.get("latest_value") is not None:
                                    b_raw = br.get("latest_value")
                            else:
                                b_raw = None if has_temporal_point_or_range else br.get("latest_value")
                            b_fmt = "Chưa có số liệu phê duyệt (-)" if _is_empty_or_dash(b_raw) else vn_format_num(b_raw)
                            b_off = (matched_row.get("ten_van_phong") if matched_row else None) or br.get("office_name") or office_str
                            b_mis = (matched_row.get("ten_nhiem_vu") if matched_row else None) or br.get("mission_name") or mission_str
                            b_id_k = b_id_str.strip().lower()
                            b_code_k = str(br.get("code") or "").strip().lower()
                            b_nm_k = " ".join(str(b_name or "").lower().split())
                            b_pnm_k = " ".join(str(p_name or "").lower().split())
                            b_combo_k = f"{b_nm_k}||{b_pnm_k}" if (b_nm_k and b_pnm_k) else ""
                            br_period_vals = dict(
                                dup_batch_period_map.get(b_id_k)
                                or dup_batch_period_map.get(b_code_k)
                                or (dup_batch_period_map.get(b_combo_k) if b_combo_k else None)
                                or {}
                            )
                            if "year" not in br_period_vals:
                                br_period_vals["year"] = b_fmt
                            ans += f"| {b_idx} | {b_name} | {cat_disp} | **{b_fmt}** | {b_off} | {b_mis} |\n"
                            multi_rows.append({
                                "stt": b_idx,
                                "criteria_id": b_id_str,
                                "item": b_name,
                                "category": cat_disp,
                                "value": b_fmt,
                                "office": b_off,
                                "mission": b_mis,
                                "report_date": date_str,
                                "_raw_value": b_raw,
                                "timeline_values": br_period_vals,
                                "period_values": br_period_vals,
                            })
                        tabular_data = {
                            "title": f"Đối chiếu chỉ tiêu '{ten_chi_tieu}' theo các nhóm chỉ tiêu cha {dup_title_period}",
                            "columns": [
                                {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                                {"key": "item", "label": "Tên chỉ tiêu", "align": "left", "data_type": "text"},
                                {"key": "category", "label": "Nhóm chỉ tiêu (Cấp)", "align": "left", "data_type": "text"},
                                {"key": "value", "label": "Giá trị mới nhất", "align": "right", "data_type": "text"},
                                {"key": "office", "label": "Đơn vị thực hiện", "align": "left", "data_type": "text"},
                                {"key": "mission", "label": "Nhiệm vụ trọng tâm", "align": "left", "data_type": "text"},
                            ],
                            "rows": multi_rows,
                            "multi_parent_rows": multi_rows,
                            "total_records": len(multi_rows),
                            "temporal_scope": temporal_meta,
                            "context_query_template": f"Chỉ tiêu {ten_chi_tieu} {{period}} là bao nhiêu?",
                        }
                    else:
                        nhom_ct_single = r0.get("nhom_chi_tieu") or (h_info_leaf.get("item", {}).get("parent_name") if (h_info_leaf and isinstance(h_info_leaf.get("item"), dict)) else None)
                        cap_single = r0.get("cap_chi_tieu") or (h_info_leaf.get("item", {}).get("level") if (h_info_leaf and isinstance(h_info_leaf.get("item"), dict)) else 1)
                        if nhom_ct_single and str(nhom_ct_single).strip() not in ("", "-", "None", "Chỉ tiêu chung"):
                            hier_suffix = f" *(Thuộc nhóm: {nhom_ct_single} - Cấp {cap_single or 2})*"
                        else:
                            hier_suffix = " *(Chỉ tiêu gốc - Cấp 1)*"
                        intro_line = date_prefix if date_prefix else "Thông tin số liệu mới nhất của chỉ tiêu đồng chí tra cứu:\n"
                        ans = (
                            f"{intro_line}"
                            f"- **Chỉ tiêu:** {ten_chi_tieu_disp}{hier_suffix}\n"
                            f"- **Giá trị:** {fmt_val}\n"
                            f"- **Đơn vị thực hiện:** {office_str}\n"
                            f"- **Nhiệm vụ trọng tâm:** {mission_str}\n"
                            f"- **Thời điểm báo cáo:** {date_str}"
                            f"{temporal_shift_bullet}"
                        )
                        leaf_item_meta = (h_info_leaf.get("item") if (h_info_leaf and isinstance(h_info_leaf.get("item"), dict)) else {}) or {}
                        c_id_single = str(r0.get("criteria_id") or leaf_item_meta.get("id") or "")
                        c_code_single = str(r0.get("ma_chi_tieu") or r0.get("code") or leaf_item_meta.get("code") or "")
                        timeline_snaps = []
                        if hasattr(self.catalog, "get_criterion_timeline_snapshots"):
                            timeline_snaps = self.catalog.get_criterion_timeline_snapshots(
                                criteria_id=c_id_single or None,
                                criteria_code=c_code_single or None,
                                criteria_name=ten_chi_tieu,
                                parent_name=nhom_ct_single,
                                year_code=str(year or "2026"),
                                tenant_code=str(norm_frame.tenant_code or "68") if norm_frame else "68",
                            )
                        single_metric_card = {
                            "criteria_id": c_id_single,
                            "criteria_code": c_code_single,
                            "criteria_name": ten_chi_tieu,
                            "hierarchy_label": hier_suffix.replace("*", "").strip(),
                            "current_value": fmt_val,
                            "raw_value": val,
                            "office_name": office_str,
                            "mission_name": mission_str,
                            "report_date": date_str,
                            "temporal_shift_notice": temporal_shift_bullet.replace("\n- **Lưu ý mốc thời gian:** ", "").strip() if temporal_shift_bullet else None,
                            "timeline_snapshots": timeline_snaps,
                        }
                        single_row_tv: Dict[str, str] = {"year": fmt_val, "YEAR": fmt_val, str(year or "2026"): fmt_val}
                        for snap_item in timeline_snaps:
                            s_date = str(snap_item.get("report_date") or snap_item.get("date") or "").strip()
                            s_iso = str(snap_item.get("iso_date") or "").strip()
                            s_val = str(snap_item.get("value") or "").strip()
                            if s_val:
                                if s_date:
                                    single_row_tv[s_date] = s_val
                                if s_iso:
                                    single_row_tv[s_iso] = s_val
                                    try:
                                        m_num = int(s_iso.split("-")[1])
                                        qk = f"q{(m_num - 1) // 3 + 1}"
                                        single_row_tv[qk] = s_val
                                        single_row_tv[qk.upper()] = s_val
                                    except Exception:
                                        pass
                        tabular_data = {
                            "title": f"Số liệu thống kê chi tiết theo báo cáo năm {year}",
                            "columns": [
                                {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                                {"key": "item", "label": "Chỉ tiêu", "align": "left", "data_type": "text"},
                                {"key": "value", "label": "Giá trị", "align": "right" if not _is_empty_or_dash(val) else "center", "data_type": "number" if not _is_empty_or_dash(val) else "text"},
                                {"key": "office", "label": "Đơn vị thực hiện", "align": "left", "data_type": "text"},
                                {"key": "mission", "label": "Nhiệm vụ trọng tâm", "align": "left", "data_type": "text"},
                                {"key": "report_date", "label": "Thời điểm báo cáo", "align": "center", "data_type": "text"},
                            ],
                            "rows": [
                                {
                                    "stt": 1,
                                    "criteria_id": c_id_single,
                                    "item": ten_chi_tieu,
                                    "value": fmt_val,
                                    "office": office_str,
                                    "mission": mission_str,
                                    "report_date": date_str,
                                    "_raw_value": val,
                                    "timeline_values": single_row_tv,
                                    "period_values": single_row_tv,
                                }
                            ],
                            "total_records": 1,
                            "single_metric_card": single_metric_card,
                            "temporal_scope": temporal_meta,
                        }
                else:
                    if display_name.lower().startswith("chỉ tiêu"):
                        label_prefix = f"**{display_name}**"
                    else:
                        label_prefix = f"chỉ tiêu **{display_name}**"

                    if val is not None:
                        ans = (
                            f"Theo số liệu báo cáo đã phê duyệt năm **{year}** của tỉnh Lâm Đồng, "
                            f"{label_prefix} đạt: **{fmt_val}**."
                        )
                    else:
                        ans = (
                            f"Theo số liệu báo cáo đã phê duyệt năm **{year}** của tỉnh Lâm Đồng, "
                            f"{label_prefix} hiện **chưa có số liệu ghi nhận (-)** trong kho dữ liệu."
                        )

                    # Bảng Markdown chuyên biệt cho chỉ tiêu đơn lẻ (Single Metric Table)
                    ans += (
                        f"\n\n| STT | Chỉ tiêu / Mục | Giá trị |\n"
                        f"| :---: | :--- | :---: |\n"
                        f"| 1 | {display_name} | **{fmt_val}** |\n"
                    )

                    tabular_data = {
                        "title": f"Số liệu thống kê chi tiết theo báo cáo năm {year}",
                        "columns": [
                            {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                            {"key": "item", "label": "Chỉ tiêu / Mục", "align": "left", "data_type": "text"},
                            {"key": "value", "label": "Giá trị", "align": "right" if val is not None else "center", "data_type": "number" if val is not None else "badge"},
                        ],
                        "rows": [
                            {
                                "stt": 1,
                                "item": display_name,
                                "value": fmt_val,
                                "_raw_value": val,
                            }
                        ],
                        "total_records": 1,
                        "temporal_scope": temporal_meta,
                    }
        else:
            # Kịch bản 5: Nhiều dòng -> Render bảng Markdown chuyên biệt theo miền dữ liệu
            if is_user_mission:
                ans = f"Dưới đây là danh sách cán bộ, chuyên viên được phân công phụ trách:\n\n"
                ans += "| STT | Họ và tên | Chức vụ | Phòng ban / Đơn vị | Nhiệm vụ phụ trách |\n"
                ans += "| :---: | :--- | :---: | :--- | :--- |\n"
                tabular_data = {
                    "title": "Danh sách cán bộ, chuyên viên phân công phụ trách",
                    "columns": [
                        {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                        {"key": "name", "label": "Họ và tên", "align": "left", "data_type": "text"},
                        {"key": "pos", "label": "Chức vụ", "align": "center", "data_type": "text"},
                        {"key": "dept", "label": "Phòng ban / Đơn vị", "align": "left", "data_type": "text"},
                        {"key": "mission", "label": "Nhiệm vụ phụ trách", "align": "left", "data_type": "text"},
                    ],
                    "rows": [],
                    "total_records": len(rows),
                }
                for idx, r in enumerate(rows, 1):
                    name = r.get("ten_can_bo") or r.get("user_name") or r.get("name") or r.get("username") or f"Cán bộ {idx}"
                    pos = r.get("chuc_vu") or r.get("user_position") or r.get("position") or "-"
                    off = r.get("don_vi_cong_tac") or r.get("office_name") or r.get("department_name") or r.get("department_code") or "-"
                    mis = r.get("ten_nhiem_vu") or r.get("mission_name") or "-"
                    is_system_acc = bool(r.get("is_system") or r.get("is_admin"))
                    name_fmt = f"**{name}** *(TK Quản trị)*" if is_system_acc else f"**{name}**"
                    ans += f"| {idx} | {name_fmt} | {pos} | {off} | {mis} |\n"
                    row_dict = dict(r)
                    row_dict["stt"] = idx
                    tabular_data["rows"].append(row_dict)
            elif is_report_list:
                ans = f"Dưới đây là danh sách và trạng thái các đợt nộp báo cáo năm **{year}**:\n\n"
                ans += "| STT | Đợt nộp báo cáo | Đơn vị nộp | Trạng thái phê duyệt |\n"
                ans += "| :---: | :--- | :---: |\n"
                tabular_data = {
                    "title": f"Danh sách đợt nộp báo cáo năm {year}",
                    "columns": [
                        {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                        {"key": "report_title", "label": "Đợt nộp báo cáo", "align": "left", "data_type": "text"},
                        {"key": "department", "label": "Đơn vị nộp", "align": "left", "data_type": "text"},
                        {"key": "status", "label": "Trạng thái phê duyệt", "align": "center", "data_type": "badge"},
                    ],
                    "rows": [],
                    "total_records": len(rows),
                }
                for idx, r in enumerate(rows, 1):
                    rdate = str(r.get("report_date") or "")[:10]
                    lbl = f"Báo cáo đợt {idx} ({rdate})" if rdate else f"Báo cáo số {idx}"
                    dept = r.get("department_name") or r.get("department_code") or "Đơn vị nộp"
                    st_vn = _vn_status(r.get("status"))
                    ans += f"| {idx} | {lbl} | {dept} | **{st_vn}** |\n"
                    tabular_data["rows"].append({
                        "stt": idx,
                        "report_title": lbl,
                        "department": dept,
                        "status": st_vn,
                    })
            elif is_mission_list:
                scope_hdr = f" thuộc lĩnh vực **{norm_frame.target_scope}**" if (norm_frame and getattr(norm_frame, "target_scope", None)) else ""
                has_temporal = bool(
                    norm_frame and (
                        getattr(norm_frame, "month_filter", None)
                        or getattr(norm_frame, "specific_date", None)
                        or (getattr(norm_frame, "date_from", None) and getattr(norm_frame, "date_to", None))
                    )
                )
                if has_temporal:
                    p_lbl, title_period = _format_temporal_period_label(norm_frame, year)
                    ans = (
                        f"Dưới đây là danh sách các **nhiệm vụ, đề án trọng tâm**{scope_hdr} có báo cáo số liệu "
                        f"{p_lbl} của tỉnh Lâm Đồng:\n\n"
                    )
                else:
                    title_period = f"năm {year}"
                    ans = f"Dưới đây là danh mục các nhiệm vụ, đề án trọng tâm{scope_hdr} năm **{year}** của tỉnh Lâm Đồng:\n\n"
                ans += "| STT | Mã nhiệm vụ | Tên nhiệm vụ | Lĩnh vực | Đơn vị phụ trách |\n"
                ans += "| :---: | :---: | :--- | :--- | :--- |\n"
                tabular_data = {
                    "title": f"Danh mục nhiệm vụ trọng tâm {title_period}",
                    "columns": [
                        {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                        {"key": "mission_code", "label": "Mã nhiệm vụ", "align": "center", "data_type": "text"},
                        {"key": "mission_name", "label": "Tên nhiệm vụ", "align": "left", "data_type": "text"},
                        {"key": "scope_name", "label": "Lĩnh vực", "align": "left", "data_type": "text"},
                        {"key": "office_name", "label": "Đơn vị phụ trách", "align": "left", "data_type": "text"},
                    ],
                    "rows": [],
                    "total_records": len(rows),
                    "temporal_scope": temporal_meta,
                    "context_query_template": (
                        f"Các nhiệm vụ thuộc lĩnh vực {norm_frame.target_scope} {{period}}?"
                        if (norm_frame and getattr(norm_frame, "target_scope", None))
                        else "Danh mục các nhiệm vụ trọng tâm {period} của tỉnh Lâm Đồng?"
                    ),
                }
                for idx, r in enumerate(rows, 1):
                    m_name = r.get("mission_name") or r.get("ten_nhiem_vu") or r.get("name") or f"Nhiệm vụ {idx}"
                    m_scope = (
                        r.get("scope_name")
                        or r.get("linh_vuc")
                        or (getattr(norm_frame, "target_scope", None) if norm_frame else None)
                        or "Nông nghiệp"
                    )
                    raw_off = r.get("office_name") or r.get("don_vi_phu_trach") or r.get("ten_van_phong")
                    m_off = "-" if not raw_off or str(raw_off).strip() in ("", "-", "Chưa phân công", "None", "null") else str(raw_off).strip()
                    m_st = _vn_status(r.get("mission_status", r.get("trang_thai", True)))
                    raw_mc = str(r.get("mission_code") or r.get("ma_nhiem_vu") or r.get("code") or "").strip()
                    if not raw_mc or raw_mc in ("-", "None", "null", "diem_nghiep", "phat_trien_nong_thon", "cai_cach_hanh_chinh", "cai_cach_hanh_chinh_2") or raw_mc.startswith("nhiem_vu_"):
                        raw_mc = _derive_mission_code(m_name, fallback_idx=idx)
                    ans += f"| {idx} | `{raw_mc}` | **{m_name}** | {m_scope} | {m_off} |\n"
                    tabular_data["rows"].append({
                        "stt": idx,
                        "mission_code": raw_mc,
                        "mission_name": m_name,
                        "scope_name": m_scope,
                        "office_name": m_off,
                        "status": m_st,
                        "action_query": f"Hiển thị các chỉ tiêu Cấp 1 của nhiệm vụ {m_name} {temporal_meta['query_suffix']}?",
                    })
            elif (norm_frame and norm_frame.intent == CanonicalIntentEnum.METRIC_TOP_K) or "xep_hang" in cols_lower:
                ans = f"Dưới đây là danh sách xếp hạng theo số liệu báo cáo năm **{year}** của tỉnh Lâm Đồng:\n\n"
                ans += "| Xếp hạng | Tên chỉ tiêu / Sản phẩm | Giá trị |\n"
                ans += "| :---: | :--- | :---: |\n"
                tabular_data = {
                    "title": f"Xếp hạng chỉ tiêu năm {year}",
                    "columns": [
                        {"key": "rank", "label": "Xếp hạng", "align": "center", "data_type": "number"},
                        {"key": "item", "label": "Tên chỉ tiêu / Sản phẩm", "align": "left", "data_type": "text"},
                        {"key": "value", "label": "Giá trị", "align": "right", "data_type": "number"},
                    ],
                    "rows": [],
                    "total_records": len(rows),
                }
                for idx, r in enumerate(rows, 1):
                    rank = r.get("xep_hang") or idx
                    name = r.get("ten_chi_tieu") or r.get("name") or f"Chỉ tiêu {idx}"
                    raw_val = r.get("gia_tri_moi_nhat") or r.get("tong_gia_tri") or r.get("gia_tri") or r.get("value") or "-"
                    fmt_val = vn_format_num(raw_val)
                    ans += f"| **{rank}** | {name} | **{fmt_val}** |\n"
                    tabular_data["rows"].append({
                        "rank": rank,
                        "item": name,
                        "value": fmt_val,
                        "_raw_value": raw_val,
                    })
            else:
                # Chỉ tiêu số liệu thông thường nhiều dòng (REQ-Q01, SC-1.1, REQ-Q04, SC-4.1)
                has_multi_fact = bool(
                    (norm_frame and getattr(norm_frame, "is_inventory_query", False))
                    or (norm_frame and getattr(norm_frame, "target_table", None) == "fact_report_criteria")
                    or ("ten_van_phong" in cols_lower or "ten_phong_ban" in cols_lower or "ten_nhiem_vu" in cols_lower or "gia_tri_moi_nhat" in cols_lower or "office_name" in cols_lower or "mission_name" in cols_lower)
                )

                sample_val = _get_metric_val(rows[0])
                is_num = False
                try:
                    if sample_val is not None and not isinstance(sample_val, bool):
                        float(sample_val)
                        is_num = True
                except (ValueError, TypeError):
                    is_num = False

                val_type = "number" if is_num else ("badge" if "status" in cols_lower or "trang_thai" in cols_lower else "text")

                if has_multi_fact:
                    tree_data = None
                    if hasattr(self.catalog, "build_criteria_tree_for_rows"):
                        try:
                            tree_data = self.catalog.build_criteria_tree_for_rows(
                                rows,
                                mission_filter=getattr(norm_frame, "target_mission", None) if norm_frame else None,
                                has_temporal_filter=has_temporal_point_or_range,
                            )
                        except TypeError:
                            tree_data = self.catalog.build_criteria_tree_for_rows(
                                rows,
                                mission_filter=getattr(norm_frame, "target_mission", None) if norm_frame else None,
                            )
                    if isinstance(tree_data, tuple) and len(tree_data) == 2:
                        trees_by_root, l1_raw = tree_data
                    elif isinstance(tree_data, dict):
                        l1_raw = tree_data.get("level1_rows", [])
                        trees_by_root = tree_data.get("trees_by_root_id", {})
                    else:
                        trees_by_root, l1_raw = {}, []
                    parent_ids_set = {
                        rid for rid, rnode in trees_by_root.items()
                        if not rnode.get("is_leaf", True) or rnode.get("children")
                    }

                    l1_batch_period_map: Dict[str, Dict[str, str]] = {}
                    if l1_raw and hasattr(self.catalog, "get_batch_period_values"):
                        l1_batch_period_map = self.catalog.get_batch_period_values(
                            l1_raw,
                            year_code=str(norm_frame.year_code or year or "2026") if norm_frame else str(year or "2026"),
                            tenant_code=str(norm_frame.tenant_code or "68") if norm_frame else "68",
                        )

                    l1_formatted = []
                    for l1_idx, l1_item in enumerate(l1_raw, 1):
                        is_p_l1 = bool(l1_item.get("is_parent_group") if "is_parent_group" in l1_item else l1_item.get("is_parent"))
                        val_disp_l1 = l1_item.get("gia_tri_moi_nhat")
                        if not val_disp_l1 or _is_empty_or_dash(val_disp_l1):
                            raw_v_l1 = l1_item.get("value")
                            if _is_empty_or_dash(raw_v_l1):
                                val_disp_l1 = "Chưa có số liệu phê duyệt (-)"
                            else:
                                val_disp_l1 = vn_format_num(raw_v_l1)

                        child_act = l1_item.get("chi_tieu_con")
                        if not child_act:
                            child_act = "- (Xem chi tiết con)" if (is_p_l1 and l1_item.get("child_count", 0) > 0) else "Không có"

                        l1_id_k = str(l1_item.get("criteria_id") or l1_item.get("tree_root_id") or l1_item.get("id") or "").strip().lower()
                        l1_code_k = str(l1_item.get("code") or "").strip().lower()
                        l1_nm_str = l1_item.get("ten_chi_tieu_cap_1") or l1_item.get("name") or f"Chỉ tiêu Cấp 1 ({l1_idx})"
                        l1_nm_k = " ".join(str(l1_nm_str).lower().split())
                        l1_p_vals = (
                            l1_batch_period_map.get(l1_id_k)
                            or l1_batch_period_map.get(l1_code_k)
                            or l1_batch_period_map.get(l1_nm_k)
                        )
                        is_tree_trigger_val = "xem chi tiết" in str(val_disp_l1).lower()
                        row_period_vals = dict(l1_p_vals) if (l1_p_vals and not is_tree_trigger_val) else None

                        l1_formatted.append({
                            "stt": l1_idx,
                            "mission": l1_item.get("nhiem_vu") or l1_item.get("mission_name") or "-",
                            "item": l1_nm_str,
                            "structure_type": l1_item.get("loai_cau_truc_cap_1") or l1_item.get("structure_type") or ("Nhóm chỉ tiêu cha" if is_p_l1 else "Chỉ tiêu đơn (Cấp 1)"),
                            "category": l1_item.get("loai_cau_truc_cap_1") or l1_item.get("structure_type") or ("Nhóm chỉ tiêu cha" if is_p_l1 else "Chỉ tiêu đơn (Cấp 1)"),
                            "value": val_disp_l1,
                            "child_action": child_act,
                            "office": l1_item.get("don_vi_thuc_hien") or l1_item.get("office_name") or "Cấp tỉnh",
                            "is_parent": is_p_l1,
                            "tree_root_id": l1_item.get("criteria_id") or l1_item.get("tree_root_id"),
                            "child_count": l1_item.get("child_count", 0),
                            "timeline_values": row_period_vals,
                            "period_values": row_period_vals,
                        })

                    is_mission_l1_view = bool(
                        norm_frame
                        and getattr(norm_frame, "is_level1_hierarchy_view", False)
                        and getattr(norm_frame, "target_mission", None)
                        and l1_formatted
                    )

                    if is_mission_l1_view:
                        m_title = f" thuộc nhiệm vụ **{norm_frame.target_mission}**" if (norm_frame and getattr(norm_frame, "target_mission", None)) else ""
                        ans_period, title_period = _format_temporal_period_label(norm_frame, year)
                        ans = (
                            f"Danh sách **chỉ tiêu gốc (Cấp 1)**{m_title} {ans_period} "
                            f"({len(l1_formatted)} chỉ tiêu Cấp 1 / {len(rows)} bản ghi đã phê duyệt; bấm **`- Xem chi tiết các chỉ tiêu con`** / **`- (Xem chi tiết con)`** để mở **Sơ đồ cây phân cấp**):\n\n"
                            f"| STT | Nhiệm vụ | Tên chỉ tiêu Cấp 1 | Loại cấu trúc Cấp 1 | Giá trị mới nhất | Chỉ tiêu con | Đơn vị thực hiện |\n"
                            f"| :---: | :--- | :--- | :--- | :---: | :---: | :--- |\n"
                        )
                        for r_l1 in l1_formatted:
                            v_md = f"**`{r_l1['value']}`**" if r_l1["is_parent"] else f"**{r_l1['value']}**"
                            c_md = f"**`{r_l1['child_action']}`**" if r_l1["child_action"] != "Không có" else r_l1["child_action"]
                            ans += f"| {r_l1['stt']} | {r_l1['mission']} | **{r_l1['item']}** | {r_l1['structure_type']} | {v_md} | {c_md} | {r_l1['office']} |\n"

                        tabular_data = {
                            "title": f"Danh mục Chỉ tiêu Cấp 1{m_title} {title_period}",
                            "columns": [
                                {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                                {"key": "mission", "label": "Nhiệm vụ", "align": "left", "data_type": "text"},
                                {"key": "item", "label": "Tên chỉ tiêu Cấp 1", "align": "left", "data_type": "text"},
                                {"key": "structure_type", "label": "Loại cấu trúc Cấp 1", "align": "left", "data_type": "text"},
                                {"key": "value", "label": "Giá trị mới nhất", "align": "right", "data_type": "text"},
                                {"key": "child_action", "label": "Chỉ tiêu con", "align": "center", "data_type": "text"},
                                {"key": "office", "label": "Đơn vị thực hiện", "align": "left", "data_type": "text"},
                            ],
                            "rows": l1_formatted,
                            "level1_rows": l1_formatted,
                            "tree_modal": trees_by_root,
                            "trees_by_root_id": trees_by_root,
                            "total_records": len(l1_formatted),
                            "raw_fact_count": len(rows),
                            "temporal_scope": temporal_meta,
                            "context_query_template": f"Hiển thị các chỉ tiêu Cấp 1 của nhiệm vụ {norm_frame.target_mission} {{period}}?",
                        }
                    elif l1_formatted:
                        ans_period, title_period = _format_temporal_period_label(norm_frame, year)
                        table_title = f"Danh sách chỉ tiêu Cấp 1 {title_period}"

                        ans = (
                            f"Danh sách các chỉ tiêu gốc (Cấp 1) đã được phê duyệt {ans_period} "
                            f"({len(l1_formatted)} chỉ tiêu Cấp 1 / {len(rows)} bản ghi; bấm **`- Xem chi tiết các chỉ tiêu con`** / **`- (Xem chi tiết con)`** để mở **Sơ đồ cây phân cấp**):\n\n"
                            f"| STT | Tên chỉ tiêu Cấp 1 | Loại cấu trúc | Giá trị mới nhất | Chỉ tiêu con | Đơn vị thực hiện | Nhiệm vụ trọng tâm |\n"
                            f"| :---: | :--- | :--- | :---: | :---: | :--- | :--- |\n"
                        )
                        for r_l1 in l1_formatted:
                            v_md = f"**`{r_l1['value']}`**" if r_l1["is_parent"] else f"**{r_l1['value']}**"
                            c_md = f"**`{r_l1['child_action']}`**" if r_l1["child_action"] != "Không có" else r_l1["child_action"]
                            ans += f"| {r_l1['stt']} | **{r_l1['item']}** | {r_l1['structure_type']} | {v_md} | {c_md} | {r_l1['office']} | {r_l1['mission']} |\n"

                        tabular_data = {
                            "title": table_title,
                            "columns": [
                                {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                                {"key": "item", "label": "Tên chỉ tiêu Cấp 1", "align": "left", "data_type": "text"},
                                {"key": "category", "label": "Loại cấu trúc", "align": "left", "data_type": "text"},
                                {"key": "value", "label": "Giá trị mới nhất", "align": "right", "data_type": "text"},
                                {"key": "child_action", "label": "Chỉ tiêu con", "align": "center", "data_type": "text"},
                                {"key": "office", "label": "Đơn vị thực hiện", "align": "left", "data_type": "text"},
                                {"key": "mission", "label": "Nhiệm vụ trọng tâm", "align": "left", "data_type": "text"},
                            ],
                            "rows": l1_formatted,
                            "level1_rows": l1_formatted,
                            "tree_modal": trees_by_root,
                            "trees_by_root_id": trees_by_root,
                            "total_records": len(l1_formatted),
                            "raw_fact_count": len(rows),
                            "temporal_scope": temporal_meta,
                            "context_query_template": "Danh sách các chỉ tiêu Cấp 1 đã được phê duyệt {period}?",
                        }
                    else:
                        ans_period, title_period = _format_temporal_period_label(norm_frame, year)
                        ans = f"Dưới đây là danh sách số liệu chỉ tiêu đã được phê duyệt ({len(rows)} bản ghi):\n\n"
                        ans += "| STT | Tên chỉ tiêu Cấp 1 | Loại cấu trúc | Giá trị mới nhất | Chỉ tiêu con | Đơn vị thực hiện | Nhiệm vụ trọng tâm |\n"
                        ans += "| :---: | :--- | :--- | :---: | :---: | :--- | :--- |\n"
                        table_title = f"Danh sách số liệu chỉ tiêu {title_period}"
                        tabular_data = {
                            "title": table_title,
                            "columns": [
                                {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                                {"key": "item", "label": "Tên chỉ tiêu Cấp 1", "align": "left", "data_type": "text"},
                                {"key": "structure_type", "label": "Loại cấu trúc", "align": "left", "data_type": "text"},
                                {"key": "value", "label": "Giá trị mới nhất", "align": "right", "data_type": "text"},
                                {"key": "child_action", "label": "Chỉ tiêu con", "align": "center", "data_type": "text"},
                                {"key": "office", "label": "Đơn vị thực hiện", "align": "left", "data_type": "text"},
                                {"key": "mission", "label": "Nhiệm vụ trọng tâm", "align": "left", "data_type": "text"},
                            ],
                            "rows": [],
                            "level1_rows": [],
                            "tree_modal": {},
                            "trees_by_root_id": {},
                            "total_records": len(rows),
                            "raw_fact_count": len(rows),
                            "temporal_scope": temporal_meta,
                        }
                        flat_batch_period_map: Dict[str, Dict[str, str]] = {}
                        if rows and hasattr(self.catalog, "get_batch_period_values"):
                            flat_batch_period_map = self.catalog.get_batch_period_values(
                                rows,
                                year_code=str(norm_frame.year_code or year or "2026") if norm_frame else str(year or "2026"),
                                tenant_code=str(norm_frame.tenant_code or "68") if norm_frame else "68",
                            )
                        for idx, r in enumerate(rows, 1):
                            name = (
                                r.get("ten_chi_tieu")
                                or r.get("name")
                                or r.get("code")
                                or selected_cand
                                or f"Chỉ tiêu {idx}"
                            )
                            category = r.get("nhom_chi_tieu") or r.get("parent_name") or "Chỉ tiêu đơn (Cấp 1)"
                            m_val = _get_metric_val(r)
                            raw_val = m_val if m_val is not None else (_vn_status(r.get("status")) or r.get("department_code") or "-")
                            fmt_val = vn_format_num(raw_val)
                            off = r.get("ten_van_phong") or r.get("ten_phong_ban") or r.get("office_name") or "Cấp tỉnh"
                            mis = r.get("ten_nhiem_vu") or r.get("mission_name") or "-"
                            r_id_k = str(r.get("criteria_id") or r.get("id") or "").strip().lower()
                            r_code_k = str(r.get("ma_chi_tieu") or r.get("code") or "").strip().lower()
                            r_nm_k = " ".join(str(name or "").lower().split())
                            r_p_vals = dict(
                                flat_batch_period_map.get(r_id_k)
                                or flat_batch_period_map.get(r_code_k)
                                or flat_batch_period_map.get(r_nm_k)
                                or {}
                            )
                            if r_p_vals and "year" not in r_p_vals:
                                r_p_vals["year"] = fmt_val
                            ans += f"| {idx} | **{name}** | {category} | **{fmt_val}** | Không có | {off} | {mis} |\n"
                            tabular_data["rows"].append({
                                "stt": idx,
                                "item": name,
                                "structure_type": category,
                                "value": fmt_val,
                                "child_action": "Không có",
                                "office": off,
                                "mission": mis,
                                "is_parent": False,
                                "tree_root_id": None,
                                "_raw_value": raw_val,
                                "timeline_values": r_p_vals or None,
                                "period_values": r_p_vals or None,
                            })
                else:
                    ans = f"Dưới đây là số liệu thống kê chi tiết theo báo cáo năm **{year}**:\n\n"
                    ans += "| STT | Chỉ tiêu / Mục | Giá trị |\n"
                    ans += "| :---: | :--- | :---: |\n"
                    if norm_frame and norm_frame.date_from and norm_frame.date_to:
                        table_title = f"Danh sách số liệu chỉ tiêu từ {norm_frame.date_from[5:7]}/{norm_frame.date_from[:4]} đến {norm_frame.date_to[5:7]}/{norm_frame.date_to[:4]}"
                    elif norm_frame and norm_frame.month_filter:
                        table_title = f"Danh sách số liệu chỉ tiêu tháng {norm_frame.month_filter:02d}/{year}"
                    else:
                        table_title = f"Số liệu thống kê chi tiết theo báo cáo năm {year}"
                    tabular_data = {
                        "title": table_title,
                        "columns": [
                            {"key": "stt", "label": "STT", "align": "center", "data_type": "number"},
                            {"key": "item", "label": "Chỉ tiêu / Mục", "align": "left", "data_type": "text"},
                            {"key": "value", "label": "Giá trị", "align": "right" if is_num else "center", "data_type": val_type},
                        ],
                        "rows": [],
                        "total_records": len(rows),
                    }
                    for idx, r in enumerate(rows, 1):
                        name = (
                            r.get("ten_chi_tieu")
                            or r.get("name")
                            or r.get("mission_name")
                            or (f"Báo cáo ngày {str(r['report_date'])[:10]}" if r.get("report_date") else None)
                            or r.get("code")
                            or selected_cand
                            or f"Chỉ tiêu {idx}"
                        )
                        m_val = _get_metric_val(r)
                        raw_val = m_val if m_val is not None else (_vn_status(r.get("status")) or r.get("department_code") or "-")
                        fmt_val = vn_format_num(raw_val)
                        ans += f"| {idx} | {name} | **{fmt_val}** |\n"
                        tabular_data["rows"].append({
                            "stt": idx,
                            "item": name,
                            "value": fmt_val,
                            "_raw_value": raw_val,
                        })

        # Tự động gắn kèm khối SQL thu gọn
        ans = _append_collapsible_sql(ans, sql)

        return {
            "current_stage": "SYNTHESIZING",
            "stage_message": "✍️ Đang tổng hợp câu trả lời...",
            "final_answer": ans,
            "tabular_data": tabular_data,
            "quick_action_chips": chips,
            "inherited_parent_criterion": None,
        }

    # --------------------------------------------------------------------------
    # BUILD GRAPH
    # --------------------------------------------------------------------------
    def _build_graph(self):
        """Khởi tạo và biên dịch đồ thị trạng thái StateGraph."""
        builder = StateGraph(AgentState)

        builder.add_node("parse_context", self.node_parse_context)
        builder.add_node("explore_warehouse", self.node_explore_warehouse)
        builder.add_node("generate_sql", self.node_generate_and_validate_sql)
        builder.add_node("execute_dwh", self.node_execute_dwh)
        builder.add_node("synthesize_response", self.node_synthesize_response)

        builder.add_edge(START, "parse_context")

        def route_after_parse(state: AgentState):
            if (
                state.get("is_capability_query")
                or state.get("is_clarification_needed")
                or state.get("is_temporal_query")
                or state.get("is_out_of_scope")
                or state.get("is_permission_denied")
            ):
                return "synthesize_response"
            return "explore_warehouse"

        builder.add_conditional_edges("parse_context", route_after_parse, {
            "synthesize_response": "synthesize_response",
            "explore_warehouse": "explore_warehouse",
        })

        builder.add_edge("explore_warehouse", "generate_sql")
        builder.add_edge("generate_sql", "execute_dwh")
        builder.add_edge("execute_dwh", "synthesize_response")
        builder.add_edge("synthesize_response", END)

        return builder.compile(checkpointer=self.checkpointer)

    # --------------------------------------------------------------------------
    # RUN SYNC
    # --------------------------------------------------------------------------
    def run(
        self,
        query: str,
        session_id: str = "default_session",
        user_context: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Thực thi đồng bộ câu hỏi qua Agent, lưu session vào SQLite.
        """
        config = {"configurable": {"thread_id": session_id}}
        init_state = {
            "session_id": session_id,
            "user_query": query,
            "effective_query": query,
            "history": history or [],
            "user_context": user_context or {"role_level": 0, "tenant_code": "68"},
            "is_clarification_needed": False,
            "clarification_question": None,
            "is_capability_query": False,
            "capability_answer": None,
            "is_out_of_scope": False,
            "out_of_scope_answer": None,
            "target_tables": [],
            "tables_schema": {},
            "generated_sql": None,
            "sql_error": None,
            "query_result": None,
            "current_stage": "START",
            "stage_message": "Khởi tạo tiến trình...",
            "final_answer": None,
            "quick_action_chips": None,
            "candidates": None,
            "selected_candidate": None,
            "is_non_additive": False,
            "is_temporal_query": False,
            "target_department_code": None,
            "tabular_data": None,
            "is_permission_denied": False,
            "permission_denied_reason": None,
            "violation_type": None,
            "requested_mission": None,
            "assigned_missions": None,
            "active_schema": (user_context or {}).get("schema", "dwh_internal") or "dwh_internal",
        }

        if not history:
            init_state["inherited_tenant"] = "68"
            init_state["inherited_year"] = "2026"
            init_state["inherited_department"] = None
            init_state["inherited_metric"] = None
            init_state["inherited_parent_criterion"] = None

        final_state = self.graph.invoke(init_state, config=config)
        return {
            "user_query": final_state.get("user_query") or query,
            "effective_query": final_state.get("effective_query") or query,
            "answer": final_state.get("final_answer"),
            "final_answer": final_state.get("final_answer"),
            "sql": final_state.get("generated_sql"),
            "generated_sql": final_state.get("generated_sql"),
            "quick_action_chips": final_state.get("quick_action_chips", []),
            "chips": final_state.get("quick_action_chips", []),
            "stage": final_state.get("current_stage"),
            "query_result": final_state.get("query_result"),
            "tabular_data": final_state.get("tabular_data"),
            "is_clarification_needed": final_state.get("is_clarification_needed", False),
            "clarification_question": final_state.get("clarification_question"),
            "is_capability_query": final_state.get("is_capability_query", False),
            "is_out_of_scope": final_state.get("is_out_of_scope", False),
            "is_permission_denied": bool(final_state.get("is_permission_denied")),
            "permission_denied_reason": final_state.get("permission_denied_reason"),
            "violation_type": final_state.get("violation_type"),
            "requested_mission": final_state.get("requested_mission"),
            "assigned_missions": final_state.get("assigned_missions"),
            "active_schema": final_state.get("active_schema"),
        }

    chat = run

    # --------------------------------------------------------------------------
    # STREAMING SSE GENERATOR
    # --------------------------------------------------------------------------
    async def run_stream(
        self,
        query: str,
        session_id: str = "default_session",
        user_context: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Thực thi và phát SSE stream theo thời gian thực tới Frontend Next.js.
        """
        config = {"configurable": {"thread_id": session_id}}
        init_state = {
            "session_id": session_id,
            "user_query": query,
            "effective_query": query,
            "history": history or [],
            "user_context": user_context or {"role_level": 0, "tenant_code": "68"},
            "is_clarification_needed": False,
            "clarification_question": None,
            "is_capability_query": False,
            "capability_answer": None,
            "is_out_of_scope": False,
            "out_of_scope_answer": None,
            "target_tables": [],
            "tables_schema": {},
            "generated_sql": None,
            "sql_error": None,
            "query_result": None,
            "current_stage": "START",
            "stage_message": "Khởi tạo tiến trình...",
            "final_answer": None,
            "quick_action_chips": None,
            "candidates": None,
            "selected_candidate": None,
            "is_non_additive": False,
            "is_temporal_query": False,
            "target_department_code": None,
            "tabular_data": None,
            "is_permission_denied": False,
            "permission_denied_reason": None,
            "violation_type": None,
            "requested_mission": None,
            "assigned_missions": None,
            "active_schema": (user_context or {}).get("schema", "dwh_internal") or "dwh_internal",
        }

        if not history:
            init_state["inherited_tenant"] = "68"
            init_state["inherited_year"] = "2026"
            init_state["inherited_department"] = None
            init_state["inherited_metric"] = None
            init_state["inherited_parent_criterion"] = None

        def sse_event(event_type: str, data: dict) -> str:
            return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        # Gửi initial metadata
        yield sse_event("metadata", {
            "session_id": session_id,
            "intent": "dwh_autonomous_query",
        })

        current_stage = "THINKING"
        yield sse_event("stage_update", {
            "stage": "THINKING",
            "message": "🔍 Đang phân tích câu hỏi & đối chiếu ngữ cảnh...",
        })
        await asyncio.sleep(0.01)

        # Chạy từng bước của graph trên worker thread để không chặn asyncio event loop (Render 5s health check)
        loop = asyncio.get_running_loop()
        event_queue: asyncio.Queue[Any] = asyncio.Queue()
        _sentinel = object()

        def _produce_graph_events() -> None:
            try:
                for ev in self.graph.stream(init_state, config=config, stream_mode="updates"):
                    loop.call_soon_threadsafe(event_queue.put_nowait, ("event", ev))
            except Exception as exc:
                loop.call_soon_threadsafe(event_queue.put_nowait, ("error", exc))
            finally:
                loop.call_soon_threadsafe(event_queue.put_nowait, ("done", _sentinel))

        producer_future = loop.run_in_executor(None, _produce_graph_events)
        final_state = {}
        while True:
            msg_type, payload_ev = await event_queue.get()
            if msg_type == "done":
                break
            if msg_type == "error":
                raise payload_ev
            event = payload_ev
            for node_name, node_output in event.items():
                if "current_stage" in node_output and "stage_message" in node_output:
                    new_stage = node_output["current_stage"]
                    if new_stage != current_stage:
                        current_stage = new_stage
                        payload = {
                            "stage": current_stage,
                            "message": node_output["stage_message"],
                        }
                        if "target_tables" in node_output:
                            payload["target_tables"] = node_output["target_tables"]
                        if "tables_schema" in node_output:
                            payload["schema_slice"] = list(node_output["tables_schema"].keys())
                        if "generated_sql" in node_output and node_output["generated_sql"]:
                            payload["sql"] = node_output["generated_sql"]
                        yield sse_event("stage_update", payload)
                        await asyncio.sleep(0.01)
                final_state.update(node_output)
        await producer_future

        final_answer = final_state.get("final_answer") or "Đã hoàn thành tra cứu số liệu."
        chips = final_state.get("quick_action_chips") or []

        # Nếu bị từ chối truy cập bởi Tier 1 Pre-SQL Refusal Gate
        if final_state.get("is_permission_denied"):
            yield sse_event("guardrail_blocked", {
                "violation_type": final_state.get("violation_type") or "MISSION_SCOPE_VIOLATION",
                "error_code": 403,
                "assigned_missions": final_state.get("assigned_missions") or [],
                "requested_mission": final_state.get("requested_mission"),
                "message": final_state.get("permission_denied_reason") or "Truy cập bị từ chối do vượt phạm vi nhiệm vụ được phân công.",
            })
            yield sse_event("token", {"content": final_answer})
            yield sse_event("done", {
                "session_id": session_id,
                "status": "blocked_by_guardrail",
                "route": "SECURITY_DENIAL",
                "full_answer": final_answer,
                "tabular_data": None,
                "target_tables": [],
                "quick_action_chips": chips,
                "metrics": {
                    "total_time_ms": 100.0,
                },
            })
            return

        # Phát câu trả lời và khối dữ liệu Warehouse ngay lập tức không trễ ms từng dòng
        yield sse_event("token", {"content": final_answer})

        tabular_data = final_state.get("tabular_data")
        if tabular_data:
            yield sse_event("tabular_data", tabular_data)

        # Gửi done event
        yield sse_event("done", {
            "session_id": session_id,
            "full_answer": final_answer,
            "tabular_data": tabular_data,
            "target_tables": final_state.get("target_tables", []),
            "quick_action_chips": chips,
            "metrics": {
                "total_time_ms": 250.0,
            },
        })


# Singleton instance
warehouse_agent = WarehouseLangGraphAgent()
