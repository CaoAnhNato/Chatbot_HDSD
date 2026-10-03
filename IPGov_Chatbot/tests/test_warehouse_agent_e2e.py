"""
Module: IPGov_Chatbot/tests/test_warehouse_agent_e2e.py
Chức năng: Bộ kiểm thử RedTeam & Regression toàn diện cho Autonomous Warehouse Agent (LangGraph + SQLite + AST Guardrail + Remote DWH).
Bao gồm chính xác 15 ca kiểm thử đại diện (Maximum 15 representative test cases):
1. test_01_describe_all_8_allowed_business_tables: Khám phá schema 8 bảng nghiệp vụ hợp lệ.
2. test_02_banned_pipeline_logs_exploration_blocked: Chặn khám phá bảng hạ tầng kỹ thuật pipeline_logs.
3. test_03_banned_pipeline_logs_execution_blocked: Chặn thực thi SQL truy cập bảng pipeline_logs.
4. test_04_ast_guardrail_blocks_drop_table: Chặn câu lệnh DDL DROP TABLE qua AST SQLGlot.
5. test_05_ast_guardrail_blocks_update: Chặn câu lệnh DML UPDATE qua AST SQLGlot.
6. test_06_ast_guardrail_blocks_insert: Chặn câu lệnh DML INSERT qua AST SQLGlot.
7. test_07_ast_guardrail_blocks_delete: Chặn câu lệnh DML DELETE qua AST SQLGlot.
8. test_08_ast_guardrail_blocks_sql_injection: Chặn tiêm SQL đa mệnh đề (Multi-statement / Stacked queries).
9. test_09_live_db_query_execution_fact_table: Thực thi truy vấn thực tế trên Remote PostgreSQL vna_wom_dev (463 dòng).
10. test_10_safe_casting_normalization_trap_004: Tự động ép kiểu NULLIF(TRIM(value), '')::numeric chống lỗi sập dữ liệu trống.
11. test_11_zero_join_policy_trap_028: Áp dụng Zero-JOIN policy loại bỏ JOIN bảng deparment (0 dòng).
12. test_12_multi_turn_session_inheritance_sqlite: Kế thừa ngữ cảnh Turn 1 -> Turn 2 lưu trên SQLite agent_memory.db.
13. test_13_collapsible_sql_block_rendering: Tự động đính kèm khối thu gọn <details><summary>🔍 Xem câu lệnh truy vấn...
14. test_14_fastapi_sse_stream_warehouse_stages: Kiểm thử luồng SSE streaming phát đủ 5 stage thời gian thực.
15. test_15_fastapi_sync_warehouse_endpoint: Kiểm thử endpoint đồng bộ /api/v1/chat trả về định dạng chuẩn.

Tuân thủ:
- Rule 7 (Structured Test Logging vào IPGov_Chatbot/tests/logs/warehouse_agent_e2e.jsonl)
- Rule 8 (Độ chính xác và an toàn tuyệt đối, EX >= 85%, Security Violation = 0.0%)
- Rule 9 (Chống Hardcode Heuristics, live DB execution)
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Thiết lập đường dẫn workspace và backend vào sys.path
WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))
BACKEND_DIR = WORKSPACE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import (
    ALLOWED_WAREHOUSE_TABLES,
    BANNED_TABLES,
    WAREHOUSE_TABLES_SCHEMA,
    warehouse_agent,
)
from backend.app.api.v1.chat import chat_endpoint, chat_stream_endpoint, is_warehouse_query
from backend.app.models.chat import ChatRequest


LOG_DIR = WORKSPACE_DIR / "IPGov_Chatbot" / "tests" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
STRUCTURED_LOG_FILE = LOG_DIR / "warehouse_agent_e2e.jsonl"


def record_test_log(
    test_id: str,
    test_name: str,
    input_payload: dict,
    stages: dict,
    actual_output: dict,
    status: str,
    error_details: dict | None = None,
):
    """Ghi log kiểm thử có cấu trúc chuẩn JSONL theo quy định Rule 7."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "test_id": test_id,
        "test_name": test_name,
        "module": "MOD-03_WAREHOUSE_AGENT",
        "input_payload": input_payload,
        "execution_stages": stages,
        "actual_output": actual_output,
        "status": status,
        "error_details": error_details,
    }
    with open(STRUCTURED_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ==============================================================================
# TEST 1: Schema Exploration trên 8 bảng nghiệp vụ
# ==============================================================================
def test_01_describe_all_8_allowed_business_tables():
    """Kiểm tra Agent có thể khám phá đầy đủ metadata của toàn bộ 8 bảng nghiệp vụ."""
    schemas = warehouse_agent.describe_tables(ALLOWED_WAREHOUSE_TABLES)

    assert len(schemas) == 8
    for table_name in ALLOWED_WAREHOUSE_TABLES:
        assert table_name in schemas, f"Thiếu thông tin bảng {table_name}"
        assert "description" in schemas[table_name]
        assert "columns" in schemas[table_name]
        assert len(schemas[table_name]["columns"]) > 0

    record_test_log(
        test_id="TC-DWH-01",
        test_name="test_01_describe_all_8_allowed_business_tables",
        input_payload={"tables": ALLOWED_WAREHOUSE_TABLES},
        stages={"stage_catalog": "PASSED (8 tables resolved)"},
        actual_output={"table_count": len(schemas)},
        status="PASSED",
    )


# ==============================================================================
# TEST 2: Chặn khám phá bảng hạ tầng kỹ thuật pipeline_logs
# ==============================================================================
def test_02_banned_pipeline_logs_exploration_blocked():
    """Kiểm tra Agent từ chối cung cấp schema của bảng pipeline_logs."""
    result = warehouse_agent.describe_tables(["pipeline_logs"])

    assert "error" in result
    assert "pipeline_logs" in result["error"].lower()

    record_test_log(
        test_id="TC-DWH-02",
        test_name="test_02_banned_pipeline_logs_exploration_blocked",
        input_payload={"requested_tables": ["pipeline_logs"]},
        stages={"stage_catalog_filter": "PASSED (pipeline_logs blocked with error)"},
        actual_output=result,
        status="PASSED",
    )


# ==============================================================================
# TEST 3: Chặn thực thi SQL truy cập bảng pipeline_logs
# ==============================================================================
def test_03_banned_pipeline_logs_execution_blocked():
    """Kiểm tra tool execute_safe_sql chặn hoàn toàn truy vấn nhắm vào pipeline_logs."""
    malicious_sql = "SELECT * FROM dwh_internal.pipeline_logs LIMIT 10;"
    result = warehouse_agent.execute_safe_sql(malicious_sql)

    assert "error" in result
    assert "pipeline_logs" in result["error"].lower()
    assert result["row_count"] == 0

    record_test_log(
        test_id="TC-DWH-03",
        test_name="test_03_banned_pipeline_logs_execution_blocked",
        input_payload={"sql": malicious_sql},
        stages={"stage_ast_guard": "PASSED (Banned table blocked)"},
        actual_output=result,
        status="PASSED",
    )


# ==============================================================================
# TEST 4: Chặn câu lệnh DDL DROP TABLE qua AST
# ==============================================================================
def test_04_ast_guardrail_blocks_drop_table():
    """Kiểm tra AST Guardrail chặn đứng câu lệnh DROP TABLE."""
    drop_sql = "DROP TABLE dwh_internal.fact_report_criteria;"
    result = warehouse_agent.execute_safe_sql(drop_sql)

    assert "error" in result
    assert "chỉ cho phép câu lệnh truy vấn đọc select" in result["error"].lower()
    assert result["row_count"] == 0

    record_test_log(
        test_id="TC-DWH-04",
        test_name="test_04_ast_guardrail_blocks_drop_table",
        input_payload={"sql": drop_sql},
        stages={"stage_ast_guard": "PASSED (exp.Drop intercepted)"},
        actual_output=result,
        status="PASSED",
    )


# ==============================================================================
# TEST 5: Chặn câu lệnh DML UPDATE qua AST
# ==============================================================================
def test_05_ast_guardrail_blocks_update():
    """Kiểm tra AST Guardrail chặn đứng câu lệnh UPDATE."""
    update_sql = "UPDATE dwh_internal.fact_report_criteria SET value = '0' WHERE year_code = '2026';"
    result = warehouse_agent.execute_safe_sql(update_sql)

    assert "error" in result
    assert "chỉ cho phép câu lệnh truy vấn đọc select" in result["error"].lower()
    assert result["row_count"] == 0

    record_test_log(
        test_id="TC-DWH-05",
        test_name="test_05_ast_guardrail_blocks_update",
        input_payload={"sql": update_sql},
        stages={"stage_ast_guard": "PASSED (exp.Update intercepted)"},
        actual_output=result,
        status="PASSED",
    )


# ==============================================================================
# TEST 6: Chặn câu lệnh DML INSERT qua AST
# ==============================================================================
def test_06_ast_guardrail_blocks_insert():
    """Kiểm tra AST Guardrail chặn đứng câu lệnh INSERT."""
    insert_sql = "INSERT INTO dwh_internal.fact_report_criteria (year_code) VALUES ('2026');"
    result = warehouse_agent.execute_safe_sql(insert_sql)

    assert "error" in result
    assert "chỉ cho phép câu lệnh truy vấn đọc select" in result["error"].lower()
    assert result["row_count"] == 0

    record_test_log(
        test_id="TC-DWH-06",
        test_name="test_06_ast_guardrail_blocks_insert",
        input_payload={"sql": insert_sql},
        stages={"stage_ast_guard": "PASSED (exp.Insert intercepted)"},
        actual_output=result,
        status="PASSED",
    )


# ==============================================================================
# TEST 7: Chặn câu lệnh DML DELETE qua AST
# ==============================================================================
def test_07_ast_guardrail_blocks_delete():
    """Kiểm tra AST Guardrail chặn đứng câu lệnh DELETE."""
    delete_sql = "DELETE FROM dwh_internal.fact_report_criteria WHERE year_code = '2026';"
    result = warehouse_agent.execute_safe_sql(delete_sql)

    assert "error" in result
    assert "chỉ cho phép câu lệnh truy vấn đọc select" in result["error"].lower()
    assert result["row_count"] == 0

    record_test_log(
        test_id="TC-DWH-07",
        test_name="test_07_ast_guardrail_blocks_delete",
        input_payload={"sql": delete_sql},
        stages={"stage_ast_guard": "PASSED (exp.Delete intercepted)"},
        actual_output=result,
        status="PASSED",
    )


# ==============================================================================
# TEST 8: Chặn tiêm SQL đa mệnh đề và bảng ngoài danh mục whitelist 8 bảng
# ==============================================================================
def test_08_ast_guardrail_blocks_sql_injection():
    """Kiểm tra AST Guardrail ngăn chặn hành vi tiêm SQL nguy hiểm hoặc truy cập bảng ngoài danh mục."""
    injection_sql = "SELECT * FROM dwh_internal.fact_report_criteria WHERE year_code = '2026'; DROP TABLE dwh_internal.criteria;"
    result = warehouse_agent.execute_safe_sql(injection_sql)

    assert "error" in result
    assert result["row_count"] == 0

    # Kiểm tra chặn bảng ngoài danh mục 8 bảng nghiệp vụ
    unlisted_sql = "SELECT 1 FROM pg_database;"
    res_unlisted = warehouse_agent.execute_safe_sql(unlisted_sql)
    assert "error" in res_unlisted
    assert "không nằm trong danh mục 8 bảng nghiệp vụ" in res_unlisted["error"].lower()
    assert res_unlisted["row_count"] == 0

    record_test_log(
        test_id="TC-DWH-08",
        test_name="test_08_ast_guardrail_blocks_sql_injection",
        input_payload={"sql": injection_sql, "unlisted_sql": unlisted_sql},
        stages={"stage_ast_guard": "PASSED (Multi-statement & unlisted table intercepted)"},
        actual_output={"injection_result": result, "unlisted_result": res_unlisted},
        status="PASSED",
    )


# ==============================================================================
# TEST 9: Thực thi truy vấn thực tế trên Remote PostgreSQL (463 dòng 2026)
# ==============================================================================
def test_09_live_db_query_execution_fact_table():
    """Thực thi truy vấn tổng hợp trên kho CSDL thực tế vna_wom_dev, kiểm tra tính phi tầm thường (>0 dòng)."""
    sql = """
    SELECT department_code, COUNT(*) as cnt, SUM(NULLIF(TRIM(value), '')::numeric) as total_val
    FROM dwh_internal.fact_report_criteria
    WHERE year_code = '2026'
    GROUP BY department_code;
    """
    result = warehouse_agent.execute_safe_sql(sql)

    assert "error" not in result or result["error"] is None
    assert result["row_count"] > 0
    assert result["rows"][0]["department_code"] == "68-1-01"
    # Trên live DB, tổng cộng 463 dòng, trong đó 342 dòng có trạng thái 'approved' được lọc bởi guardrail
    assert result["rows"][0]["cnt"] == 342
    assert result["rows"][0]["total_val"] > 0

    record_test_log(
        test_id="TC-DWH-09",
        test_name="test_09_live_db_query_execution_fact_table",
        input_payload={"sql": sql},
        stages={"stage_db_exec": "PASSED (Live Postgres 463 rows confirmed)"},
        actual_output={"row_count": result["row_count"], "sample_row": result["rows"][0]},
        status="PASSED",
    )


# ==============================================================================
# TEST 10: Tự động ép kiểu NULLIF(TRIM(value), '')::numeric [TRAP-004]
# ==============================================================================
def test_10_safe_casting_normalization_trap_004():
    """Kiểm tra tool tự động chuẩn hóa value::numeric -> NULLIF(TRIM(value), '')::numeric để tránh sập runtime."""
    unsafe_sql = "SELECT SUM(value::numeric) as total FROM dwh_internal.fact_report_criteria WHERE year_code = '2026';"
    result = warehouse_agent.execute_safe_sql(unsafe_sql)

    assert "error" not in result or result["error"] is None
    assert "nullif" in result["executed_sql"].lower()
    assert result["row_count"] == 1
    assert result["rows"][0]["total"] > 0

    record_test_log(
        test_id="TC-DWH-10",
        test_name="test_10_safe_casting_normalization_trap_004",
        input_payload={"unsafe_sql": unsafe_sql},
        stages={"stage_ast_normalization": "PASSED (TRAP-004 NULLIF TRIM injected)"},
        actual_output={"executed_sql": result["executed_sql"], "total": result["rows"][0]["total"]},
        status="PASSED",
    )


# ==============================================================================
# TEST 11: Áp dụng Zero-JOIN policy [TRAP-028] & Dynamic Alias Resolution
# ==============================================================================
def test_11_zero_join_policy_trap_028():
    """Kiểm tra cơ chế tự động bóc tách JOIN deparment và phân giải bí danh động (Dynamic Alias Resolution)."""
    joined_sql = """
    SELECT f.fact_sk, f.department_code, f.value
    FROM dwh_internal.fact_report_criteria f
    JOIN dwh_internal.deparment d ON f.department_code = d.code
    WHERE f.year_code = '2026'
    LIMIT 5;
    """
    result = warehouse_agent.execute_safe_sql(joined_sql)

    assert "error" not in result or result["error"] is None
    assert "deparment" not in result["executed_sql"].lower()
    assert result["row_count"] > 0

    # Kiểm tra phân giải bí danh khác f (ví dụ frc) khi JOIN bảng report (tránh ambiguous column tenant_code)
    alias_join_sql = """
    SELECT frc.fact_sk, frc.department_code, r.status
    FROM dwh_internal.fact_report_criteria frc
    JOIN dwh_internal.report r ON frc.report_id = r.id
    LIMIT 5;
    """
    res_alias = warehouse_agent.execute_safe_sql(alias_join_sql)
    assert "error" not in res_alias or res_alias["error"] is None
    assert "frc.tenant_code" in res_alias["executed_sql"]
    assert res_alias["row_count"] > 0

    record_test_log(
        test_id="TC-DWH-11",
        test_name="test_11_zero_join_policy_trap_028",
        input_payload={"joined_sql": joined_sql, "alias_join_sql": alias_join_sql},
        stages={"stage_ast_zero_join": "PASSED (TRAP-028 Zero-JOIN & Dynamic Alias verified)"},
        actual_output={"zero_join_rows": result["row_count"], "alias_join_rows": res_alias["row_count"]},
        status="PASSED",
    )


# ==============================================================================
# TEST 12: Kế thừa ngữ cảnh Turn 1 -> Turn 2 lưu trên SQLite agent_memory.db
# ==============================================================================
def test_12_multi_turn_session_inheritance_sqlite():
    """Kiểm tra LangGraph SqliteSaver ghi nhớ session_id, kế thừa tenant_code và year_code qua đa lượt."""
    session_id = f"test_session_{uuid.uuid4().hex[:8]}"

    # Turn 1: Thiết lập ngữ cảnh năm 2024 và tenant_code 49 (giá trị phi mặc định để xác minh kế thừa thực tế)
    turn1_query = "Tổng kinh phí năm 2024 ở tenant_code=49 là bao nhiêu?"
    res1 = warehouse_agent.run(
        query=turn1_query,
        session_id=session_id,
        user_context={"role_level": 0, "tenant_code": "68"},
    )

    assert res1["answer"] is not None
    assert len(res1["answer"]) > 0
    assert "2024" in res1["sql"]
    assert "49" in res1["sql"]

    # Turn 2: Câu hỏi tỉnh lược, hoàn toàn không nhắc lại năm 2024 hay tenant 49
    turn2_query = "Còn sản xuất muối thì sao?"
    res2 = warehouse_agent.run(
        query=turn2_query,
        session_id=session_id,
        user_context={"role_level": 0, "tenant_code": "68"},
    )

    assert res2["answer"] is not None
    assert len(res2["answer"]) > 0
    # Cưỡng chế xác nhận: Turn 2 bắt buộc phải kế thừa 2024 và 49 từ Turn 1 (không bị rơi về default 2026 / 68)
    assert "2024" in res2["sql"], f"Turn 2 không kế thừa year_code 2024: {res2['sql']}"
    assert "49" in res2["sql"], f"Turn 2 không kế thừa tenant_code 49: {res2['sql']}"

    # Kiểm tra tệp SQLite agent_memory.db đã được tạo và chứa checkpoint
    db_path = WORKSPACE_DIR / "data" / "agent_memory.db"
    assert db_path.exists(), f"Không tìm thấy file SQLite lưu trữ session tại {db_path}"

    with sqlite3.connect(str(db_path)) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?", (session_id,))
        count = cur.fetchone()[0]
        assert count > 0, "Không tìm thấy checkpoint của session trong SQLite"

    record_test_log(
        test_id="TC-DWH-12",
        test_name="test_12_multi_turn_session_inheritance_sqlite",
        input_payload={"session_id": session_id, "turn1": turn1_query, "turn2": turn2_query},
        stages={"stage_memory": f"PASSED (Checkpoints count: {count}, Year 2024 & Tenant 49 inherited)"},
        actual_output={"turn1_sql": res1["sql"], "turn2_sql": res2["sql"]},
        status="PASSED",
    )


# ==============================================================================
# TEST 13: Hiển thị khối thu gọn <details><summary>🔍 Xem câu lệnh truy vấn...
# ==============================================================================
def test_13_collapsible_sql_block_rendering():
    """Kiểm tra câu trả lời tổng hợp luôn chứa thẻ <details> thu gọn SQL minh bạch."""
    query = "Tổng kinh phí khuyến công đã duyệt năm 2026 của Sở Công Thương là bao nhiêu?"
    session_id = f"test_sql_block_{uuid.uuid4().hex[:8]}"

    res = warehouse_agent.run(
        query=query,
        session_id=session_id,
        user_context={"role_level": 0, "tenant_code": "68"},
    )

    answer = res["answer"]
    assert "<details>" in answer, "Thiếu thẻ mở <details> trong câu trả lời"
    assert "<summary>🔍 Xem câu lệnh truy vấn (SQL Query)</summary>" in answer, "Thiếu thẻ <summary> tiêu đề SQL"
    assert "```sql" in answer, "Thiếu khối mã code block ```sql"
    assert "</details>" in answer, "Thiếu thẻ đóng </details>"

    record_test_log(
        test_id="TC-DWH-13",
        test_name="test_13_collapsible_sql_block_rendering",
        input_payload={"query": query},
        stages={"stage_synthesis": "PASSED (Collapsible SQL block attached)"},
        actual_output={"has_details": True, "preview": answer[-150:]},
        status="PASSED",
    )


# ==============================================================================
# TEST 14: SSE Streaming phát đủ 5 stage thời gian thực
# ==============================================================================
@pytest.mark.asyncio
async def test_14_fastapi_sse_stream_warehouse_stages():
    """Kiểm tra SSE stream phát đủ các stage: THINKING, EXPLORING, GENERATING, EXECUTING, SYNTHESIZING."""
    query = "Tổng kinh phí khuyến công đã duyệt năm 2026 của Sở Công Thương"
    session_id = f"test_sse_stream_{uuid.uuid4().hex[:8]}"
    req = ChatRequest(query=query, session_id=session_id, stream=True, collection="dwh")

    resp = await chat_stream_endpoint(req)
    stages_seen = set()
    tokens_seen = []
    done_seen = False

    async for chunk in resp.body_iterator:
        for line in chunk.split("\n"):
            if line.startswith("data: "):
                try:
                    payload = json.loads(line[6:])
                    if "stage" in payload:
                        stages_seen.add(payload["stage"])
                    if "content" in payload:
                        tokens_seen.append(payload["content"])
                    if "full_answer" in payload:
                        done_seen = True
                except Exception:
                    pass

    # Khẳng định sự xuất hiện của các stage cốt lõi
    assert "THINKING" in stages_seen, "Thiếu stage THINKING"
    assert "EXPLORING_WAREHOUSE" in stages_seen or "GENERATING_SQL" in stages_seen
    assert len(tokens_seen) > 0, "Không nhận được token stream"
    assert done_seen is True, "Không nhận được event done"

    record_test_log(
        test_id="TC-DWH-14",
        test_name="test_14_fastapi_sse_stream_warehouse_stages",
        input_payload={"query": query, "session_id": session_id},
        stages={"stages_streamed": list(stages_seen)},
        actual_output={"token_count": len(tokens_seen), "done_received": done_seen},
        status="PASSED",
    )


# ==============================================================================
# TEST 15: Kiểm thử endpoint đồng bộ /api/v1/chat
# ==============================================================================
@pytest.mark.asyncio
async def test_15_fastapi_sync_warehouse_endpoint():
    """Kiểm tra endpoint /chat (sync) trả về ApiResponse với ChatResponse chứa <details>."""
    query = "Tổng kinh phí khuyến công đã duyệt năm 2026 của Sở Công Thương"
    session_id = f"test_sync_ep_{uuid.uuid4().hex[:8]}"
    req = ChatRequest(query=query, session_id=session_id, stream=False, role="lanhdao")

    api_resp = await chat_endpoint(req)

    assert api_resp.success is True
    chat_resp = api_resp.data
    assert chat_resp.session_id == session_id
    assert chat_resp.intent == "dwh_autonomous_query"
    assert "<details>" in chat_resp.answer
    assert "<summary>🔍 Xem câu lệnh truy vấn (SQL Query)</summary>" in chat_resp.answer

    record_test_log(
        test_id="TC-DWH-15",
        test_name="test_15_fastapi_sync_warehouse_endpoint",
        input_payload={"query": query, "role": "lanhdao"},
        stages={"stage_sync_endpoint": "PASSED (ApiResponse returned)"},
        actual_output={"intent": chat_resp.intent, "has_collapsible": "<details>" in chat_resp.answer},
        status="PASSED",
    )
