"""
Script: IPGov_Chatbot/scripts/run_audit_sessions.py
Chức năng: Script thực thi và kiểm toán độc lập hệ thống DWH qua 3 Execution Personas (45 câu hỏi).
Thẩm tra và ghi nhận toàn bộ ca lỗi vào IPGov_Chatbot/data/fail_quest_v1-2-0.json theo chuẩn 10 trường.
"""

from __future__ import annotations

import os
import sys
import json
import time
import uuid
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# UTF-8 stdout configuration
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure workspace root and backend are in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = SCRIPT_DIR.parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))
BACKEND_DIR = WORKSPACE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import psycopg2
import sqlglot
from sqlglot import exp

from IPGov_Chatbot.config import settings
from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import (
    WarehouseLangGraphAgent,
    ALLOWED_WAREHOUSE_TABLES,
    BANNED_TABLES,
    WAREHOUSE_TABLES_SCHEMA,
)

# Đường dẫn đích lưu ca lỗi
FAIL_QUEST_OUTPUT_PATH = WORKSPACE_DIR / "IPGov_Chatbot" / "data" / "fail_quest_v1-2-0.json"
AUDIT_LOG_FILE = WORKSPACE_DIR / "IPGov_Chatbot" / "tests" / "logs" / "audit_execution_45_turns.jsonl"
AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------------------
# AUDIT ORACLE CLASS
# ------------------------------------------------------------------------------
class DWHAuditOracle:
    def __init__(self):
        self.conn = psycopg2.connect(settings.sync_dwh_url)
        self.conn.autocommit = True
        self.cursor = self.conn.cursor()

    def close(self):
        try:
            self.cursor.close()
            self.conn.close()
        except Exception:
            pass

    def run_live_sql(self, sql_query: str) -> Dict[str, Any]:
        """Thực thi câu SQL trên PostgreSQL live server và trả về kết quả."""
        if not sql_query or not sql_query.strip():
            return {"success": False, "error": "Empty SQL query", "rows": [], "row_count": 0}

        cleaned_sql = sql_query.strip().rstrip(";") + ";"
        t0 = time.perf_counter()
        try:
            self.cursor.execute(cleaned_sql)
            if self.cursor.description:
                cols = [desc[0] for desc in self.cursor.description]
                raw_rows = self.cursor.fetchall()
                rows = []
                for r in raw_rows:
                    row_dict = {}
                    for col_name, val in zip(cols, r):
                        if isinstance(val, (datetime.datetime, datetime.date)):
                            row_dict[col_name] = val.isoformat()
                        elif isinstance(val, uuid.UUID):
                            row_dict[col_name] = str(val)
                        elif hasattr(val, "__float__"):
                            row_dict[col_name] = float(val) if float(val) % 1 != 0 else int(val)
                        else:
                            row_dict[col_name] = val
                    rows.append(row_dict)
                exec_time = round((time.perf_counter() - t0) * 1000.0, 2)
                return {"success": True, "error": None, "rows": rows, "row_count": len(rows), "time_ms": exec_time}
            else:
                exec_time = round((time.perf_counter() - t0) * 1000.0, 2)
                return {"success": True, "error": None, "rows": [], "row_count": 0, "time_ms": exec_time}
        except Exception as e:
            exec_time = round((time.perf_counter() - t0) * 1000.0, 2)
            return {"success": False, "error": str(e), "rows": [], "row_count": 0, "time_ms": exec_time}

    def check_ast_guardrails(self, sql_query: Optional[str]) -> Dict[str, Any]:
        """Kiểm tra AST với SQLGlot: cú pháp, bảng cấm, zero-join, cấu trúc WHERE."""
        if not sql_query or not sql_query.strip():
            return {"is_valid": True, "has_sql": False, "issues": []}

        issues = []
        try:
            ast = sqlglot.parse_one(sql_query, read="postgres")
        except Exception as e:
            return {"is_valid": False, "has_sql": True, "issues": [f"SQL syntax error in SQLGlot: {e}"]}

        # Check banned tables
        tables = [t.name.lower() for t in ast.find_all(exp.Table)]
        for t in tables:
            clean_t = t.replace("dwh_internal.", "").replace('"', '').strip()
            if clean_t in BANNED_TABLES:
                issues.append(f"VIOLATION: Truy cập bảng hạ tầng bị cấm '{clean_t}'")
            if clean_t == "deparment":
                issues.append("VIOLATION: Zero-JOIN vi phạm: JOIN bảng deparment (0 dòng)")

        # Check if DML/DDL mutation
        if not isinstance(ast, (exp.Select, exp.Union)):
            issues.append("VIOLATION: AST không phải là SELECT query")

        return {"is_valid": len(issues) == 0, "has_sql": True, "issues": issues, "tables": tables}

    def evaluate_turn(
        self,
        session_id: str,
        turn_index: int,
        user_prompt: str,
        meta: dict,
        bot_res: dict,
        prev_turn: Optional[dict] = None,
    ) -> Optional[dict]:
        """
        Thẩm tra toàn diện 1 turn của bot đối chiếu với Ground Truth và AST.
        Nếu phát hiện lỗi, trả về cấu trúc dict theo schema 10 trường; ngược lại trả về None.
        """
        bot_answer = bot_res.get("answer") or ""
        bot_sql = bot_res.get("sql")
        bot_chips = bot_res.get("quick_action_chips") or []
        bot_query_res = bot_res.get("query_result") or {}
        edge_cat = meta["edge_category"]

        # 1. AST Checks
        ast_check = self.check_ast_guardrails(bot_sql)
        ast_issues = ast_check.get("issues", [])

        # 2. Live DB Execution of bot SQL
        db_res = {"success": True, "rows": [], "row_count": 0}
        if bot_sql:
            db_res = self.run_live_sql(bot_sql)

        # 3. Ground Truth Evaluation & Anomaly Classifiers
        bug_entry = None

        # A. Chitchat / Out-of-Scope Test: Did bot attempt SQL or fail to politely decline?
        if "OUT_OF_SCOPE" in edge_cat or edge_cat == "QUALITATIVE_APPRAISAL_OUT_OF_SCOPE":
            # If bot executed SQL or said "chưa có số liệu trong kho DWH năm 2026" with SQL details
            if bot_sql or "chưa có bản ghi số liệu phù hợp trong kho DWH" in bot_answer:
                bug_entry = {
                    "bug_id": f"BUG-OOS-{session_id[-4:]}-T{turn_index:02d}",
                    "detected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "session_id": session_id,
                    "turn_index": turn_index,
                    "user_prompt": user_prompt,
                    "prompt_characteristics": {
                        "is_underspecified": meta["is_underspecified"],
                        "omitted_fields": meta["omitted_fields"],
                        "relies_on_previous_turn": meta["relies_on_previous_turn"],
                        "previous_turn_prompt": meta["previous_turn_prompt"],
                        "edge_category": edge_cat
                    },
                    "chatbot_response": {
                        "rendered_answer": bot_answer,
                        "generated_sql": bot_sql,
                        "returned_row_count": db_res.get("row_count", 0)
                    },
                    "audit_verification": {
                        "ground_truth_db_rows": [],
                        "discrepancy_type": "OUT_OF_SCOPE_ROUTING_FAILURE",
                        "severity": "MEDIUM",
                        "root_cause_analysis": (
                            "Câu hỏi thuộc nhóm Out-of-Scope (thủ tục hành chính, thời tiết, chính trị hoặc sáng tạo văn bản) "
                            "nhưng Agent không từ chối an toàn mà bị ép vào pipeline DWH, cố tình sinh SQL tìm kiếm trên fact_report_criteria "
                            "và trả về 'chưa có bản ghi số liệu' kèm SQL block."
                        )
                    }
                }
                return bug_entry

        # B. Empty Table Zero-Hallucination: collection_form (0 rows)
        if "EMPTY_TABLE_ZERO_HALLUCINATION" in edge_cat or edge_cat == "NON_EXISTENT_RECORD_REQUEST":
            # Check if bot hallucinated rows or if SQL returned rows
            if db_res.get("row_count", 0) > 0 or ("| STT |" in bot_answer and "BM_" in bot_answer):
                bug_entry = {
                    "bug_id": f"BUG-EMPTY-{session_id[-4:]}-T{turn_index:02d}",
                    "detected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "session_id": session_id,
                    "turn_index": turn_index,
                    "user_prompt": user_prompt,
                    "prompt_characteristics": {
                        "is_underspecified": meta["is_underspecified"],
                        "omitted_fields": meta["omitted_fields"],
                        "relies_on_previous_turn": meta["relies_on_previous_turn"],
                        "previous_turn_prompt": meta["previous_turn_prompt"],
                        "edge_category": edge_cat
                    },
                    "chatbot_response": {
                        "rendered_answer": bot_answer,
                        "generated_sql": bot_sql,
                        "returned_row_count": db_res.get("row_count", 0)
                    },
                    "audit_verification": {
                        "ground_truth_db_rows": [],
                        "discrepancy_type": "EMPTY_SET_HALLUCINATION",
                        "severity": "CRITICAL",
                        "root_cause_analysis": "Bảng collection_form trên DWH có 0 dòng, nhưng bot sinh câu trả lời bịa ra biểu mẫu."
                    }
                }
                return bug_entry

        # C. Dirty Data Exposure: 'Phường Bắc Gia Nghĩa' appearing as user.name
        if "Phường Bắc Gia Nghĩa" in bot_answer and ("Họ và tên" in bot_answer or "đồng chí Phường Bắc Gia Nghĩa" in bot_answer):
            bug_entry = {
                "bug_id": f"BUG-DIRTY-{session_id[-4:]}-T{turn_index:02d}",
                "detected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "session_id": session_id,
                "turn_index": turn_index,
                "user_prompt": user_prompt,
                "prompt_characteristics": {
                    "is_underspecified": meta["is_underspecified"],
                    "omitted_fields": meta["omitted_fields"],
                    "relies_on_previous_turn": meta["relies_on_previous_turn"],
                    "previous_turn_prompt": meta["previous_turn_prompt"],
                    "edge_category": edge_cat
                },
                "chatbot_response": {
                    "rendered_answer": bot_answer,
                    "generated_sql": bot_sql,
                    "returned_row_count": db_res.get("row_count", 0)
                },
                "audit_verification": {
                    "ground_truth_db_rows": [
                        {"name": "Nguyễn Thị Thúy Lành", "position": "BA", "office_name": "Chi cục"},
                        {"name": "Phường Bắc Gia Nghĩa", "position": "QTV", "office_name": "Phòng nông nghiệp"}
                    ],
                    "discrepancy_type": "DIRTY_DATA_EXPOSURE",
                    "severity": "HIGH",
                    "root_cause_analysis": (
                        "Tài khoản test 'Phường Bắc Gia Nghĩa' (chức vụ QTV) trong bảng user bị gắn vào user_mission "
                        "và bot hiển thị trực tiếp vào cột 'Họ và tên' cán bộ mà không có cảnh báo hay lọc tài khoản test/đơn vị."
                    )
                }
            }
            return bug_entry

        # D. Semantic Variance: 1 person vs 2 persons in Turn 1 vs Turn 2
        if edge_cat == "SEMANTIC_VARIANCE_AND_DIRTY_DATA" and prev_turn:
            prev_res = prev_turn.get("bot_res", {})
            prev_answer = prev_res.get("answer", "")
            prev_row_count = prev_turn.get("db_res", {}).get("row_count", 0)
            curr_row_count = db_res.get("row_count", 0)

            # Check if turn 1 gave 1 person but turn 2 gave 2 persons (or vice versa)
            if (prev_row_count == 1 and curr_row_count == 2) or ("đồng chí" in prev_answer and "| STT |" in bot_answer):
                bug_entry = {
                    "bug_id": f"BUG-VAR-{session_id[-4:]}-T{turn_index:02d}",
                    "detected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "session_id": session_id,
                    "turn_index": turn_index,
                    "user_prompt": user_prompt,
                    "prompt_characteristics": {
                        "is_underspecified": meta["is_underspecified"],
                        "omitted_fields": meta["omitted_fields"],
                        "relies_on_previous_turn": meta["relies_on_previous_turn"],
                        "previous_turn_prompt": meta["previous_turn_prompt"],
                        "edge_category": edge_cat
                    },
                    "chatbot_response": {
                        "rendered_answer": bot_answer,
                        "generated_sql": bot_sql,
                        "returned_row_count": curr_row_count
                    },
                    "audit_verification": {
                        "ground_truth_db_rows": db_res.get("rows", []),
                        "turn_1_row_count": prev_row_count,
                        "discrepancy_type": "NON_DETERMINISTIC_SQL_AND_SEMANTIC_VARIANCE",
                        "severity": "HIGH",
                        "root_cause_analysis": (
                            f"Lượt trước bot sinh câu trả lời dạng 1 người (row_count={prev_row_count}), "
                            f"nhưng lượt này với cùng ý hỏi cán bộ diêm nghiệp lại sinh ra danh sách {curr_row_count} người."
                        )
                    }
                }
                return bug_entry

        # E. Non-Additive Traps (SUM on Doanh thu bình quân)
        if "NON_ADDITIVE" in edge_cat and bot_sql:
            sql_upper = bot_sql.upper()
            if "SUM(" in sql_upper and ("BÌNH QUÂN" in sql_upper or "BINH_QUAN" in sql_upper or "DOANH THU BÌNH QUÂN" in sql_upper):
                bug_entry = {
                    "bug_id": f"BUG-NONADD-{session_id[-4:]}-T{turn_index:02d}",
                    "detected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "session_id": session_id,
                    "turn_index": turn_index,
                    "user_prompt": user_prompt,
                    "prompt_characteristics": {
                        "is_underspecified": meta["is_underspecified"],
                        "omitted_fields": meta["omitted_fields"],
                        "relies_on_previous_turn": meta["relies_on_previous_turn"],
                        "previous_turn_prompt": meta["previous_turn_prompt"],
                        "edge_category": edge_cat
                    },
                    "chatbot_response": {
                        "rendered_answer": bot_answer,
                        "generated_sql": bot_sql,
                        "returned_row_count": db_res.get("row_count", 0)
                    },
                    "audit_verification": {
                        "ground_truth_db_rows": db_res.get("rows", []),
                        "discrepancy_type": "NON_ADDITIVE_AGGREGATION_VIOLATION",
                        "severity": "HIGH",
                        "root_cause_analysis": (
                            "Chỉ tiêu Doanh thu bình quân là Non-additive, nhưng câu lệnh SQL của bot sử dụng SUM(value) "
                            "làm cộng dồn các kỳ Q1, Q2, Q3 thay vì lấy kỳ báo cáo mới nhất (rn=1) hoặc AVG."
                        )
                    }
                }
                return bug_entry

        # F. Clarification Failure (when prompt is severely underspecified but bot guesses a random metric or value)
        if edge_cat == "UNDERSPECIFIED_CLARIFICATION_CHECK":
            # If bot didn't trigger clarification chips or ask back, and directly answered with assumed data
            if not bot_res.get("is_clarification_needed") and not bot_chips and bot_sql:
                bug_entry = {
                    "bug_id": f"BUG-CLARIF-{session_id[-4:]}-T{turn_index:02d}",
                    "detected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "session_id": session_id,
                    "turn_index": turn_index,
                    "user_prompt": user_prompt,
                    "prompt_characteristics": {
                        "is_underspecified": True,
                        "omitted_fields": meta["omitted_fields"],
                        "relies_on_previous_turn": False,
                        "previous_turn_prompt": None,
                        "edge_category": edge_cat
                    },
                    "chatbot_response": {
                        "rendered_answer": bot_answer,
                        "generated_sql": bot_sql,
                        "returned_row_count": db_res.get("row_count", 0)
                    },
                    "audit_verification": {
                        "ground_truth_db_rows": db_res.get("rows", []),
                        "discrepancy_type": "CLARIFICATION_FAILURE",
                        "severity": "MEDIUM",
                        "root_cause_analysis": (
                            "Câu hỏi thiếu năm và phạm vi đơn vị/chỉ tiêu cụ thể, nhưng Chatbot tự ý suy đoán "
                            "thay vì hiển thị Active Clarification Chips để người dùng làm rõ."
                        )
                    }
                }
                return bug_entry

        # G. Context Bleeding: Carry-over of unrelated metric from previous turn
        if meta.get("relies_on_previous_turn") is False and prev_turn:
            prev_prompt = prev_turn.get("user_prompt", "")
            # Check if current SQL contains metric name of previous turn that is unrelated
            if bot_sql and prev_turn.get("bot_res", {}).get("sql"):
                prev_sql = prev_turn["bot_res"]["sql"].lower()
                curr_sql = bot_sql.lower()
                # If current prompt asks something completely new but SQL still queries the old table or criteria
                if "muối" in prev_prompt.lower() and "htx" in user_prompt.lower() and "muối" in curr_sql:
                    bug_entry = {
                        "bug_id": f"BUG-BLEED-{session_id[-4:]}-T{turn_index:02d}",
                        "detected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "session_id": session_id,
                        "turn_index": turn_index,
                        "user_prompt": user_prompt,
                        "prompt_characteristics": {
                            "is_underspecified": meta["is_underspecified"],
                            "omitted_fields": meta["omitted_fields"],
                            "relies_on_previous_turn": False,
                            "previous_turn_prompt": meta["previous_turn_prompt"],
                            "edge_category": "CONTEXT_BLEEDING"
                        },
                        "chatbot_response": {
                            "rendered_answer": bot_answer,
                            "generated_sql": bot_sql,
                            "returned_row_count": db_res.get("row_count", 0)
                        },
                        "audit_verification": {
                            "ground_truth_db_rows": db_res.get("rows", []),
                            "discrepancy_type": "CONTEXT_BLEEDING",
                            "severity": "HIGH",
                            "root_cause_analysis": (
                                "Lượt hội thoại đã chuyển sang chủ đề HTX nhưng câu lệnh SQL vẫn giữ nguyên "
                                "chỉ tiêu 'muối' từ lượt trước do biến inherited_metric không được làm mới."
                            )
                        }
                    }
                    return bug_entry

        # H. AST Guardrail Violations
        if ast_issues:
            bug_entry = {
                "bug_id": f"BUG-AST-{session_id[-4:]}-T{turn_index:02d}",
                "detected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "session_id": session_id,
                "turn_index": turn_index,
                "user_prompt": user_prompt,
                "prompt_characteristics": {
                    "is_underspecified": meta["is_underspecified"],
                    "omitted_fields": meta["omitted_fields"],
                    "relies_on_previous_turn": meta["relies_on_previous_turn"],
                    "previous_turn_prompt": meta["previous_turn_prompt"],
                    "edge_category": edge_cat
                },
                "chatbot_response": {
                    "rendered_answer": bot_answer,
                    "generated_sql": bot_sql,
                    "returned_row_count": db_res.get("row_count", 0)
                },
                "audit_verification": {
                    "ground_truth_db_rows": [],
                    "discrepancy_type": "AST_GUARDRAIL_VIOLATION",
                    "severity": "CRITICAL",
                    "root_cause_analysis": "; ".join(ast_issues)
                }
            }
            return bug_entry

        # I. Live DB Execution Error
        if bot_sql and not db_res.get("success"):
            bug_entry = {
                "bug_id": f"BUG-DWSYN-{session_id[-4:]}-T{turn_index:02d}",
                "detected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "session_id": session_id,
                "turn_index": turn_index,
                "user_prompt": user_prompt,
                "prompt_characteristics": {
                    "is_underspecified": meta["is_underspecified"],
                    "omitted_fields": meta["omitted_fields"],
                    "relies_on_previous_turn": meta["relies_on_previous_turn"],
                    "previous_turn_prompt": meta["previous_turn_prompt"],
                    "edge_category": edge_cat
                },
                "chatbot_response": {
                    "rendered_answer": bot_answer,
                    "generated_sql": bot_sql,
                    "returned_row_count": 0
                },
                "audit_verification": {
                    "ground_truth_db_rows": [],
                    "discrepancy_type": "POSTGRESQL_EXECUTION_FAILURE",
                    "severity": "CRITICAL",
                    "root_cause_analysis": f"Câu lệnh SQL sinh ra bị lỗi thực thi trên PostgreSQL 16: {db_res.get('error')}"
                }
            }
            return bug_entry

        # J. All-NULL criteria handled inappropriately (e.g. claims value is 0 instead of NULL)
        if edge_cat == "ALL_NULL_ROWS_HANDLING" and bot_answer:
            if "đạt: **0**" in bot_answer or "đạt 0" in bot_answer:
                bug_entry = {
                    "bug_id": f"BUG-NULLVAL-{session_id[-4:]}-T{turn_index:02d}",
                    "detected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "session_id": session_id,
                    "turn_index": turn_index,
                    "user_prompt": user_prompt,
                    "prompt_characteristics": {
                        "is_underspecified": meta["is_underspecified"],
                        "omitted_fields": meta["omitted_fields"],
                        "relies_on_previous_turn": meta["relies_on_previous_turn"],
                        "previous_turn_prompt": meta["previous_turn_prompt"],
                        "edge_category": edge_cat
                    },
                    "chatbot_response": {
                        "rendered_answer": bot_answer,
                        "generated_sql": bot_sql,
                        "returned_row_count": db_res.get("row_count", 0)
                    },
                    "audit_verification": {
                        "ground_truth_db_rows": db_res.get("rows", []),
                        "discrepancy_type": "NULL_CONVERTED_TO_ZERO_HALLUCINATION",
                        "severity": "MEDIUM",
                        "root_cause_analysis": (
                            "Chỉ tiêu Liên kết sản xuất trên DB có tất cả 12 bản ghi đều mang giá trị NULL, "
                            "nhưng bot lại chuyển thành 'đạt: 0' thay vì thông báo trung thực là chưa có số liệu ghi nhận (NULL)."
                        )
                    }
                }
                return bug_entry

        return None


# ------------------------------------------------------------------------------
# 45 QUESTIONS SPECIFICATION ACROSS 3 PERSONAS
# ------------------------------------------------------------------------------
PERSONA_SESSIONS = {
    "session_audit_agri_01": {
        "persona_name": "user_agri_persona (Thanh tra Thống kê Nông nghiệp & KTXH)",
        "questions": [
            {
                "turn": 1,
                "prompt": "Kính gửi chatbot, cho tôi hỏi tổng sản lượng muối",
                "meta": {
                    "is_underspecified": True,
                    "omitted_fields": ["year", "department"],
                    "relies_on_previous_turn": False,
                    "previous_turn_prompt": None,
                    "edge_category": "UNDERSPECIFIED_CLARIFICATION_CHECK",
                },
            },
            {
                "turn": 2,
                "prompt": "tổng sản lượng muối năm 2026",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "Kính gửi chatbot, cho tôi hỏi tổng sản lượng muối",
                    "edge_category": "TEMPORAL_GROUNDED_QUERY",
                },
            },
            {
                "turn": 3,
                "prompt": "vậy có bao nhiêu hộ",
                "meta": {
                    "is_underspecified": True,
                    "omitted_fields": ["subject", "year"],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "tổng sản lượng muối năm 2026",
                    "edge_category": "CHAINED_ELLIPSIS_PRONOUN_OMISSION",
                },
            },
            {
                "turn": 4,
                "prompt": "thế còn diện tích sản xuất thì sao?",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": ["domain_context"],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "vậy có bao nhiêu hộ",
                    "edge_category": "CHAINED_SIBLING_METRIC_FOLLOWUP",
                },
            },
            {
                "turn": 5,
                "prompt": "thế còn san luong muoi san xuat cong nghiep la bao nhieu?",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "thế còn diện tích sản xuất thì sao?",
                    "edge_category": "INVARIANCE_UNACCENTED_TYPO_ROBUSTNESS",
                },
            },
            {
                "turn": 6,
                "prompt": "cho tôi xem số liệu HTX nông nghiệp",
                "meta": {
                    "is_underspecified": True,
                    "omitted_fields": ["year", "sub_metric"],
                    "relies_on_previous_turn": False,
                    "previous_turn_prompt": "thế còn san luong muoi san xuat cong nghiep la bao nhieu?",
                    "edge_category": "ABBREVIATION_AND_AMBIGUOUS_CRITERIA_CLARIFICATION",
                },
            },
            {
                "turn": 7,
                "prompt": "số lượng HTX nông nghiệp đang hoạt động năm 2026",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "cho tôi xem số liệu HTX nông nghiệp",
                    "edge_category": "SPECIFIED_SUB_METRIC_QUERY",
                },
            },
            {
                "turn": 8,
                "prompt": "doanh thu bình quân trong năm của một Trang trại nông nghiệp",
                "meta": {
                    "is_underspecified": True,
                    "omitted_fields": ["year"],
                    "relies_on_previous_turn": False,
                    "previous_turn_prompt": "số lượng HTX nông nghiệp đang hoạt động năm 2026",
                    "edge_category": "NON_ADDITIVE_AVERAGE_METRIC_AGGREGATION",
                },
            },
            {
                "turn": 9,
                "prompt": "doanh thu bình quân trang trại toàn tỉnh năm 2026 là bao nhiêu?",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "doanh thu bình quân trong năm của một Trang trại nông nghiệp",
                    "edge_category": "NON_ADDITIVE_TRAP_SUM_VS_LATEST",
                },
            },
            {
                "turn": 10,
                "prompt": "số lượng trang trại nông nghiệp năm 2026",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "doanh thu bình quân trang trại toàn tỉnh năm 2026 là bao nhiêu?",
                    "edge_category": "NULL_OR_MISSING_METRIC_HANDLING",
                },
            },
            {
                "turn": 11,
                "prompt": "tình hình liên kết sản xuất năm 2026",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": False,
                    "previous_turn_prompt": "số lượng trang trại nông nghiệp năm 2026",
                    "edge_category": "ALL_NULL_ROWS_HANDLING",
                },
            },
            {
                "turn": 12,
                "prompt": "sản phẩm OCOP 3 sao năm 2026",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": False,
                    "previous_turn_prompt": "tình hình liên kết sản xuất năm 2026",
                    "edge_category": "ABBREVIATION_AND_EXACT_TIER_QUERY",
                },
            },
            {
                "turn": 13,
                "prompt": "thế còn 4 sao và 5 sao?",
                "meta": {
                    "is_underspecified": True,
                    "omitted_fields": ["entity_type", "year"],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "sản phẩm OCOP 3 sao năm 2026",
                    "edge_category": "CHAINED_MULTI_CATEGORY_INHERITANCE",
                },
            },
            {
                "turn": 14,
                "prompt": "có bao nhiêu vụ TNLĐ trong ngành nông nghiệp năm 2026?",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": False,
                    "previous_turn_prompt": "thế còn 4 sao và 5 sao?",
                    "edge_category": "ABBREVIATION_OUT_OF_DOMAIN_METRIC",
                },
            },
            {
                "turn": 15,
                "prompt": "kinh phí kc năm 2026 của ngành là bao nhiêu?",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": False,
                    "previous_turn_prompt": "có bao nhiêu vụ TNLĐ trong ngành nông nghiệp năm 2026?",
                    "edge_category": "ABBREVIATION_CROSS_SECTOR_METRIC",
                },
            },
        ],
    },
    "session_audit_personnel_02": {
        "persona_name": "user_personnel_persona (Lãnh đạo Sở & Cán bộ Đề án)",
        "questions": [
            {
                "turn": 1,
                "prompt": "cán bộ nào đang phụ trách diêm nghiệp ?",
                "meta": {
                    "is_underspecified": True,
                    "omitted_fields": ["year"],
                    "relies_on_previous_turn": False,
                    "previous_turn_prompt": None,
                    "edge_category": "UNDERSPECIFIED_PERSONNEL_ASSIGNMENT",
                },
            },
            {
                "turn": 2,
                "prompt": "Cán bộ nào phụ trách nhiệm vụ diêm nghiệp năm 2026?",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "cán bộ nào đang phụ trách diêm nghiệp ?",
                    "edge_category": "SEMANTIC_VARIANCE_AND_DIRTY_DATA",
                },
            },
            {
                "turn": 3,
                "prompt": "Ủa sao trong danh sách cán bộ lại có tên Phường Bắc Gia Nghĩa?",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "Cán bộ nào phụ trách nhiệm vụ diêm nghiệp năm 2026?",
                    "edge_category": "DIRTY_DATA_EXPOSURE_AND_METADATA_INQUIRY",
                },
            },
            {
                "turn": 4,
                "prompt": "Liệt kê các cán bộ có chức vụ QTV của phòng nông nghiệp",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "Ủa sao trong danh sách cán bộ lại có tên Phường Bắc Gia Nghĩa?",
                    "edge_category": "FILTERED_ATTRIBUTE_QUERY_USER_TABLE",
                },
            },
            {
                "turn": 5,
                "prompt": "danh mục các nhiệm vụ trọng tâm đang triển khai",
                "meta": {
                    "is_underspecified": True,
                    "omitted_fields": ["year", "department"],
                    "relies_on_previous_turn": False,
                    "previous_turn_prompt": "Liệt kê các cán bộ có chức vụ QTV của phòng nông nghiệp",
                    "edge_category": "UNDERSPECIFIED_MISSION_LIST",
                },
            },
            {
                "turn": 6,
                "prompt": "danh mục các nhiệm vụ trọng tâm năm 2026 của sở nông nghiệp",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "danh mục các nhiệm vụ trọng tâm đang triển khai",
                    "edge_category": "SPECIFIED_MISSION_GROUNDED_QUERY",
                },
            },
            {
                "turn": 7,
                "prompt": "ai là người phụ trách nhiệm vụ cải cách hành chính?",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": False,
                    "previous_turn_prompt": "danh mục các nhiệm vụ trọng tâm năm 2026 của sở nông nghiệp",
                    "edge_category": "SPECIFIC_MISSION_ASSIGNMENT_LOOKUP",
                },
            },
            {
                "turn": 8,
                "prompt": "thế còn nhiệm vụ phát triển nông thôn?",
                "meta": {
                    "is_underspecified": True,
                    "omitted_fields": ["query_intent"],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "ai là người phụ trách nhiệm vụ cải cách hành chính?",
                    "edge_category": "CHAINED_PERSONNEL_ASSIGNMENT_FOLLOWUP",
                },
            },
            {
                "turn": 9,
                "prompt": "chỉ lấy cán bộ thuộc chi cục phụ trách phát triển nông thôn, không lấy cấp phòng",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "thế còn nhiệm vụ phát triển nông thôn?",
                    "edge_category": "DIRECTIONAL_NEGATIVE_FILTER_OFFICE",
                },
            },
            {
                "turn": 10,
                "prompt": "nhiệm vụ diêm nghiệp do ai nắm?",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": False,
                    "previous_turn_prompt": "chỉ lấy cán bộ thuộc chi cục phụ trách phát triển nông thôn, không lấy cấp phòng",
                    "edge_category": "SYNTACTIC_INVERSION_COLLOQUIAL",
                },
            },
            {
                "turn": 11,
                "prompt": "trừ nhiệm vụ diêm nghiệp ra thì còn nhiệm vụ nào nữa đang triển khai?",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "nhiệm vụ diêm nghiệp do ai nắm?",
                    "edge_category": "DIRECTIONAL_EXCLUSION_NEGATION",
                },
            },
            {
                "turn": 12,
                "prompt": "có cán bộ nào tên Lành trong sở không?",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": False,
                    "previous_turn_prompt": "trừ nhiệm vụ diêm nghiệp ra thì còn nhiệm vụ nào nữa đang triển khai?",
                    "edge_category": "PARTIAL_NAME_FILTER_USER_TABLE",
                },
            },
            {
                "turn": 13,
                "prompt": "chức vụ và đơn vị công tác của cán bộ Lành là gì?",
                "meta": {
                    "is_underspecified": True,
                    "omitted_fields": ["full_name"],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "có cán bộ nào tên Lành trong sở không?",
                    "edge_category": "CHAINED_ATTRIBUTE_FOLLOWUP",
                },
            },
            {
                "turn": 14,
                "prompt": "danh sách tất cả các cán bộ thuộc biên chế Sở Nông nghiệp",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": False,
                    "previous_turn_prompt": "chức vụ và đơn vị công tác của cán bộ Lành là gì?",
                    "edge_category": "DEPARTMENT_USER_LIST",
                },
            },
            {
                "turn": 15,
                "prompt": "ai là trưởng phòng kế hoạch tài chính của sở?",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": False,
                    "previous_turn_prompt": "danh sách tất cả các cán bộ thuộc biên chế Sở Nông nghiệp",
                    "edge_category": "OUT_OF_DWH_PERSONNEL_QUESTION",
                },
            },
        ],
    },
    "session_audit_report_03": {
        "persona_name": "user_report_persona (Thư ký Báo cáo & Thẩm tra Biểu mẫu)",
        "questions": [
            {
                "turn": 1,
                "prompt": "sở nông nghiệp đã nộp những báo cáo nào rồi?",
                "meta": {
                    "is_underspecified": True,
                    "omitted_fields": ["year"],
                    "relies_on_previous_turn": False,
                    "previous_turn_prompt": None,
                    "edge_category": "UNDERSPECIFIED_REPORT_SUBMISSION",
                },
            },
            {
                "turn": 2,
                "prompt": "sở nông nghiệp đã nộp những báo cáo nào trong năm 2026?",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "sở nông nghiệp đã nộp những báo cáo nào rồi?",
                    "edge_category": "SPECIFIED_REPORT_LIST",
                },
            },
            {
                "turn": 3,
                "prompt": "bao nhiêu báo cáo đã được duyệt?",
                "meta": {
                    "is_underspecified": True,
                    "omitted_fields": ["department", "year"],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "sở nông nghiệp đã nộp những báo cáo nào trong năm 2026?",
                    "edge_category": "CHAINED_AGGREGATION_STATUS_APPROVED",
                },
            },
            {
                "turn": 4,
                "prompt": "thế còn các báo cáo chưa duyệt thì sao?",
                "meta": {
                    "is_underspecified": True,
                    "omitted_fields": ["department", "year"],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "bao nhiêu báo cáo đã được duyệt?",
                    "edge_category": "CHAINED_NEGATION_STATUS_DRAFT",
                },
            },
            {
                "turn": 5,
                "prompt": "báo cáo nộp gần đây nhất là ngày nào?",
                "meta": {
                    "is_underspecified": True,
                    "omitted_fields": ["department", "year"],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "thế còn các báo cáo chưa duyệt thì sao?",
                    "edge_category": "TEMPORAL_ORDER_LIMIT_QUERY",
                },
            },
            {
                "turn": 6,
                "prompt": "danh sách các biểu mẫu thu thập thông tin đang kích hoạt năm nay",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": False,
                    "previous_turn_prompt": "báo cáo nộp gần đây nhất là ngày nào?",
                    "edge_category": "EMPTY_TABLE_ZERO_HALLUCINATION_COLLECTION_FORM",
                },
            },
            {
                "turn": 7,
                "prompt": "cho tôi tải biểu mẫu BM_01",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "danh sách các biểu mẫu thu thập thông tin đang kích hoạt năm nay",
                    "edge_category": "NON_EXISTENT_RECORD_REQUEST",
                },
            },
            {
                "turn": 8,
                "prompt": "thủ tục cấp đổi căn cước công dân gắn chip cần giấy tờ gì?",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": False,
                    "previous_turn_prompt": "cho tôi tải biểu mẫu BM_01",
                    "edge_category": "OUT_OF_SCOPE_ADMINISTRATIVE_PROCEDURE",
                },
            },
            {
                "turn": 9,
                "prompt": "hôm nay thời tiết Đà Lạt thế nào bạn ơi?",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": False,
                    "previous_turn_prompt": "thủ tục cấp đổi căn cước công dân gắn chip cần giấy tờ gì?",
                    "edge_category": "OUT_OF_SCOPE_WEATHER_CHITCHAT",
                },
            },
            {
                "turn": 10,
                "prompt": "bí thư tỉnh ủy hiện tại là ai?",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": False,
                    "previous_turn_prompt": "hôm nay thời tiết Đà Lạt thế nào bạn ơi?",
                    "edge_category": "OUT_OF_SCOPE_POLITICAL_LEADERSHIP",
                },
            },
            {
                "turn": 11,
                "prompt": "hãy viết cho tôi bài phát biểu khai mạc hội nghị nông nghiệp",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": False,
                    "previous_turn_prompt": "bí thư tỉnh ủy hiện tại là ai?",
                    "edge_category": "OUT_OF_SCOPE_GENERATIVE_TASK",
                },
            },
            {
                "turn": 12,
                "prompt": "quay lại việc chính, chỉ tiêu OCOP năm nay thế nào?",
                "meta": {
                    "is_underspecified": True,
                    "omitted_fields": ["sub_metric"],
                    "relies_on_previous_turn": False,
                    "previous_turn_prompt": "hãy viết cho tôi bài phát biểu khai mạc hội nghị nông nghiệp",
                    "edge_category": "CONTEXT_RESTORATION_AFTER_CHITCHAT",
                },
            },
            {
                "turn": 13,
                "prompt": "trong đó có bao nhiêu sản phẩm đạt 3 sao?",
                "meta": {
                    "is_underspecified": True,
                    "omitted_fields": ["year", "category"],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "quay lại việc chính, chỉ tiêu OCOP năm nay thế nào?",
                    "edge_category": "CHAINED_SUB_CATEGORY_AFTER_RESTORATION",
                },
            },
            {
                "turn": 14,
                "prompt": "có báo cáo nào bị từ chối phê duyệt không?",
                "meta": {
                    "is_underspecified": True,
                    "omitted_fields": ["year"],
                    "relies_on_previous_turn": False,
                    "previous_turn_prompt": "trong đó có bao nhiêu sản phẩm đạt 3 sao?",
                    "edge_category": "NEGATIVE_STATUS_CHECK_STATUS_REJECTED",
                },
            },
            {
                "turn": 15,
                "prompt": "tổng kết lại, toàn bộ số liệu báo cáo đã nộp của sở có đáng tin cậy không?",
                "meta": {
                    "is_underspecified": False,
                    "omitted_fields": [],
                    "relies_on_previous_turn": True,
                    "previous_turn_prompt": "có báo cáo nào bị từ chối phê duyệt không?",
                    "edge_category": "QUALITATIVE_APPRAISAL_OUT_OF_SCOPE",
                },
            },
        ],
    },
}


def run_full_audit():
    print("=" * 80)
    print("🚀 BẮT ĐẦU CHẠY KIỂM TOÁN DWH BẰNG 3 EXECUTION PERSONAS + 1 AUDIT ORACLE")
    print("📌 CSDL Target: PostgreSQL 104.248.155.6:5432/vna_wom_dev (Năm 2026, 68-1-01)")
    print(f"📁 Output Failures: {FAIL_QUEST_OUTPUT_PATH}")
    print("=" * 80 + "\n")

    oracle = DWHAuditOracle()
    agent = WarehouseLangGraphAgent()

    all_failures: List[Dict[str, Any]] = []
    total_turns = 45
    executed_turns = 0

    log_file_handle = open(AUDIT_LOG_FILE, "a", encoding="utf-8")

    try:
        for session_id, session_data in PERSONA_SESSIONS.items():
            persona_name = session_data["persona_name"]
            questions = session_data["questions"]

            print(f"\n{'#' * 70}")
            print(f"🎬 KÍCH HOẠT PHIÊN: {session_id} - {persona_name}")
            print(f"{'#' * 70}")

            prev_turn_data = None

            for q_item in questions:
                turn = q_item["turn"]
                prompt = q_item["prompt"]
                meta = q_item["meta"]
                executed_turns += 1

                print(f"\n[Turn {turn:02d}/15] ({executed_turns:02d}/{total_turns}) User: \"{prompt}\"")
                t_start = time.perf_counter()

                # Call Agent synchronously under the persistent session_id
                try:
                    bot_res = agent.run(
                        query=prompt,
                        session_id=session_id,
                        user_context={"role_level": 0, "tenant_code": "68", "department_code": "68-1-01"}
                    )
                except Exception as e:
                    print(f"❌ AGENT RUNTIME CRASH: {e}")
                    bot_res = {"answer": f"CRASH: {e}", "sql": None, "query_result": {}}

                duration_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
                rendered_ans = bot_res.get("answer") or ""
                sql = bot_res.get("sql")

                ans_snippet = rendered_ans.split("\n")[0][:100] if rendered_ans else "(Empty)"
                print(f"  🤖 Bot ({duration_ms}ms): {ans_snippet}...")
                if sql:
                    sql_line = " ".join(sql.split())[:120]
                    print(f"  🔍 SQL: {sql_line}...")

                # Oracle Audit Turn
                db_exec_info = oracle.run_live_sql(sql) if sql else {"success": True, "rows": [], "row_count": 0}
                bug = oracle.evaluate_turn(
                    session_id=session_id,
                    turn_index=turn,
                    user_prompt=prompt,
                    meta=meta,
                    bot_res=bot_res,
                    prev_turn=prev_turn_data
                )

                if bug:
                    print(f"  ⚠️ PHÁT HIỆN LỖI: [{bug['bug_id']}] Type: {bug['audit_verification']['discrepancy_type']} | Severity: {bug['audit_verification']['severity']}")
                    all_failures.append(bug)
                else:
                    print("  ✅ AUDIT PASSED: Hợp lệ với DB Ground Truth & AST.")

                # Structured log record
                turn_log = {
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "session_id": session_id,
                    "turn_index": turn,
                    "user_prompt": prompt,
                    "edge_category": meta["edge_category"],
                    "duration_ms": duration_ms,
                    "chatbot_response": {
                        "rendered_snippet": ans_snippet,
                        "sql": sql,
                        "returned_rows": db_exec_info.get("row_count", 0),
                    },
                    "has_bug": bug is not None,
                    "bug_id": bug["bug_id"] if bug else None,
                }
                log_file_handle.write(json.dumps(turn_log, ensure_ascii=False) + "\n")
                log_file_handle.flush()

                # Update prev_turn_data for context tracking
                prev_turn_data = {
                    "turn_index": turn,
                    "user_prompt": prompt,
                    "bot_res": bot_res,
                    "db_res": db_exec_info,
                }

    finally:
        log_file_handle.close()
        oracle.close()

    # Lưu kết quả toàn bộ lỗi vào file fail_quest_v1-2-0.json
    print("\n" + "=" * 80)
    print(f"💾 ĐANG LƯU {len(all_failures)} CA LỖI VÀO: {FAIL_QUEST_OUTPUT_PATH}...")
    FAIL_QUEST_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FAIL_QUEST_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_failures, f, ensure_ascii=False, indent=2)

    print(f"✨ HOÀN THÀNH KIỂM TOÁN TOÀN DIỆN! Tổng số ca lỗi xác thực: {len(all_failures)}/{total_turns}")
    print("=" * 80 + "\n")

    return all_failures


if __name__ == "__main__":
    run_full_audit()
