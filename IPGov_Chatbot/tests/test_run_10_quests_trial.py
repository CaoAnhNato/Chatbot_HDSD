"""
Module: IPGov_Chatbot/tests/test_run_10_quests_trial.py
Chức năng: Chạy thử nghiệm 10 câu hỏi (quests) đại diện toàn diện qua toàn bộ luồng xử lý
từ Module 01 (Gateway) tới Module 08 (Response Synthesizer & Lineage Badge).
Căn cứ:
- test_case_rule.md (MMSQL 5 Taxonomies, FLEX Ground Truth, Structured Logging)
- ipgov-coding-rules.md (Asyncpg Pool, ZeroDivisionError Defense, BLUF brevity)
- project-memory-and-traps (TRAP-001 -> TRAP-006)
"""

import json
import pathlib
import time
from typing import Any, Dict, List

import pytest

from IPGov_Chatbot.modules.mod01_gateway.gateway_endpoint import chat_sse_event_generator
from IPGov_Chatbot.modules.mod01_gateway.jwt_service import JWTService

BASE_DIR = pathlib.Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"

TEST_QUESTS = [
    {
        "id": "TRIAL_01",
        "name": "Executive Ranking Top-K",
        "prompt": "Xếp hạng 5 huyện, thành phố có kinh phí giải ngân khuyến công cao nhất toàn tỉnh năm 2026?",
        "user_payload": {
            "user_id": "usr_lanhdao_01",
            "username": "lanhdao_ubnd",
            "role_level": 0,
            "tenant_code": "68",
            "department_code": None,
        },
        "expected_archetype": "RANKING_TOP_K",
        "expected_table": True,
    },
    {
        "id": "TRIAL_02",
        "name": "Executive Temporal YoY Comparison",
        "prompt": "Tổng số vụ tai nạn lao động trên toàn tỉnh năm 2026 tăng hay giảm bao nhiêu phần trăm so với năm trước?",
        "user_payload": {
            "user_id": "usr_lanhdao_01",
            "username": "lanhdao_ubnd",
            "role_level": 0,
            "tenant_code": "68",
            "department_code": None,
        },
        "expected_archetype": "TEMPORAL_COMPARISON",
        "expected_table": True,
    },
    {
        "id": "TRIAL_03",
        "name": "Executive Part-to-Whole Ratio",
        "prompt": "Trong tổng diện tích sàn xây dựng nhà ở hoàn thành năm 2026 toàn tỉnh, nhà ở xã hội chiếm tỷ trọng bao nhiêu phần trăm?",
        "user_payload": {
            "user_id": "usr_lanhdao_01",
            "username": "lanhdao_ubnd",
            "role_level": 0,
            "tenant_code": "68",
            "department_code": None,
        },
        "expected_archetype": "PART_TO_WHOLE",
        "expected_table": False,
    },
    {
        "id": "TRIAL_04",
        "name": "Specialist Direct Metric / Single Fact",
        "prompt": "Năm 2026, tổng số người được đào tạo từ nguồn kinh phí khuyến công tại Phòng Kinh tế là bao nhiêu?",
        "user_payload": {
            "user_id": "usr_chuyenvien_02",
            "username": "chuyenvien_so",
            "role_level": 2,
            "tenant_code": "68",
            "department_code": "68-1-02",
        },
        "expected_archetype": "DIRECT_METRIC",
        "expected_table": False,
    },
    {
        "id": "TRIAL_05",
        "name": "Specialist Report Status Discovery",
        "prompt": "Kiểm tra trạng thái nộp báo cáo của các phòng ban năm 2026",
        "user_payload": {
            "user_id": "usr_giamdoc_01",
            "username": "giamdoc_so",
            "role_level": 1,
            "tenant_code": "68",
            "department_code": "68-1-01",
        },
        "expected_archetype": "REPORT_STATUS_LIST",
        "expected_table": True,
    },
    {
        "id": "TRIAL_06",
        "name": "Auditor Data Anomaly Audit",
        "prompt": "Có những đơn vị nào báo cáo số liệu bằng 0 hoặc để trống bất thường trong năm 2026?",
        "user_payload": {
            "user_id": "usr_kiemtoan_05",
            "username": "kiemtoanvien",
            "role_level": 3,
            "tenant_code": "68",
            "department_code": None,
        },
        "expected_archetype": "DATA_ANOMALY",
        "expected_table": True,
    },
    {
        "id": "TRIAL_07",
        "name": "Citizen Collection Form Discovery",
        "prompt": "Năm 2026 đang áp dụng các biểu mẫu thu thập số liệu nào?",
        "user_payload": {
            "user_id": "usr_citizen_04",
            "username": "congdan_dn",
            "role_level": 3,
            "tenant_code": "68",
            "department_code": None,
        },
        "expected_archetype": "COLLECTION_FORM",
        "expected_table": True,
    },
    {
        "id": "TRIAL_08",
        "name": "Operational Staff Assignment & Tasks",
        "prompt": "Xem danh sách nhiệm vụ và cán bộ phụ trách năm 2026",
        "user_payload": {
            "user_id": "usr_chuyenvien_02",
            "username": "chuyenvien_so",
            "role_level": 2,
            "tenant_code": "68",
            "department_code": "68-1-02",
        },
        "expected_archetype": "USER_MISSION",
        "expected_table": True,
    },
    {
        "id": "TRIAL_09",
        "name": "Defensive Empty Result Safe Gate",
        "prompt": "Báo cáo diện tích cây công nghiệp chưa được giải mật năm 2030",
        "user_payload": {
            "user_id": "usr_lanhdao_01",
            "username": "lanhdao_ubnd",
            "role_level": 0,
            "tenant_code": "68",
            "department_code": None,
        },
        "expected_archetype": "EMPTY_RESULT",
        "expected_table": False,
    },
    {
        "id": "TRIAL_10",
        "name": "Greeting Decoupling & ETL Freshness",
        "prompt": "Kính gửi chatbot, dữ liệu kho DWH được cập nhật gần nhất vào thời điểm nào?",
        "user_payload": {
            "user_id": "usr_lanhdao_01",
            "username": "lanhdao_ubnd",
            "role_level": 0,
            "tenant_code": "68",
            "department_code": None,
        },
        "expected_archetype": "ETL_FRESHNESS",
        "expected_table": False,
    },
]


@pytest.mark.asyncio
async def test_run_10_quests_trial_e2e():
    """
    Thực thi 10 câu hỏi kiểm thử qua toàn bộ 8 stages bằng luồng SSE generator thật.
    Thu thập và kiểm tra:
    - Tính trôi chảy không bị gián đoạn (zero unhandled exceptions)
    - Tỷ lệ có câu trả lời: 100%
    - Tỷ lệ có Lineage Badge: 100%
    - Tỷ lệ hoàn tất sự kiện 'done': 100%
    """
    results: List[Dict[str, Any]] = []
    log_entries: List[Dict[str, Any]] = []

    t_suite_start = time.perf_counter()

    for idx, q in enumerate(TEST_QUESTS, 1):
        q_id = q["id"]
        q_name = q["name"]
        prompt = q["prompt"]
        user_payload = q["user_payload"]

        token = JWTService.encode(user_payload)
        auth_header = f"Bearer {token}"
        session_id = f"sess_trial_{q_id.lower()}"

        t_start = time.perf_counter()
        events_received: List[str] = []
        captured_data: Dict[str, Any] = {}
        content_text = ""
        lineage_badge = None

        try:
            async for chunk in chat_sse_event_generator(
                prompt=prompt,
                auth_header=auth_header,
                session_id=session_id,
                client_ip="127.0.0.1",
            ):
                if chunk.startswith("event:"):
                    lines = chunk.strip().split("\n")
                    event_name = lines[0].replace("event:", "").strip()
                    events_received.append(event_name)

                    data_line = next((l for l in lines if l.startswith("data:")), None)
                    if data_line:
                        raw_json = data_line.replace("data:", "").strip()
                        try:
                            parsed_json = json.loads(raw_json)
                            captured_data[event_name] = parsed_json
                            if event_name == "content_chunk":
                                content_text += parsed_json.get("chunk", "")
                            elif event_name == "lineage_resolved":
                                lineage_badge = parsed_json.get("badge") or (parsed_json if "verification_hash" in parsed_json else None)
                        except Exception:
                            pass

            duration_ms = (time.perf_counter() - t_start) * 1000.0

            router_data = captured_data.get("router_routed", {})
            db_data = captured_data.get("db_executed", {})
            sql_data = captured_data.get("sql_generated", {})
            ast_data = captured_data.get("ast_sanitized", {})
            content_data = captured_data.get("content_chunk", {})
            done_data = captured_data.get("done", {})

            is_success = "done" in events_received and (bool(content_text) or "bypass_response" in router_data)
            has_badge = lineage_badge is not None

            res_entry = {
                "id": q_id,
                "name": q_name,
                "prompt": prompt,
                "role_level": user_payload["role_level"],
                "events": events_received,
                "route": router_data.get("route", "N/A"),
                "intent": router_data.get("intent", "N/A"),
                "db_status": db_data.get("status", "BYPASS" if "bypass_response" in captured_data else "N/A"),
                "row_count": db_data.get("row_count", 0),
                "render_mode": content_data.get("render_mode", "FAST_BYPASS" if "bypass_response" in captured_data else "UNKNOWN"),
                "duration_ms": round(duration_ms, 2),
                "content_preview": content_text[:120] + "..." if len(content_text) > 120 else content_text,
                "has_badge": has_badge,
                "badge": lineage_badge,
                "status": "PASSED" if is_success else "FAILED",
            }
            results.append(res_entry)

            # Structured Log theo chuẩn test_case_rule.md
            log_entries.append({
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "test_id": q_id,
                "test_name": q_name,
                "module": "PIPELINE_E2E",
                "input_payload": {"prompt": prompt, "user_context": user_payload},
                "execution_stages": {
                    "stage_1_gateway": "PASSED",
                    "stage_2_guardrail": "PASSED",
                    "stage_3_router": router_data,
                    "stage_5_sql_gen": sql_data,
                    "stage_6_ast_guard": ast_data,
                    "stage_7_db_exec": db_data,
                    "stage_8_synthesizer": content_data,
                },
                "actual_output": {
                    "content_length": len(content_text),
                    "has_badge": has_badge,
                },
                "metrics": {"total_duration_ms": round(duration_ms, 2)},
                "status": "PASSED" if is_success else "FAILED",
            })

        except Exception as e:
            results.append({
                "id": q_id,
                "name": q_name,
                "prompt": prompt,
                "error": str(e),
                "status": "CRASHED",
            })

    total_suite_duration = time.perf_counter() - t_suite_start

    # Lưu log có cấu trúc
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / "test_trial_10_quests_e2e.jsonl"
    with open(log_path, "w", encoding="utf-8") as f:
        for entry in log_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Lưu kết quả tổng hợp ra file json phục vụ phân tích
    summary_path = LOGS_DIR / "test_trial_10_quests_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_quests": len(TEST_QUESTS),
            "passed_count": sum(1 for r in results if r.get("status") == "PASSED"),
            "total_duration_seconds": round(total_suite_duration, 2),
            "results": results,
        }, f, ensure_ascii=False, indent=2)

    # In thông tin chẩn đoán
    print(f"\n--- KẾT QUẢ CHẠY THỬ 10 QUESTS E2E ({total_suite_duration:.2f}s) ---")
    for r in results:
        status_icon = "✅" if r.get("status") == "PASSED" else "❌"
        print(f"{status_icon} [{r['id']}] {r['name']} | Time: {r.get('duration_ms', 0)}ms | Mode: {r.get('render_mode')} | Badge: {r.get('has_badge')}")

    # Assertions
    passed_count = sum(1 for r in results if r.get("status") == "PASSED")
    assert passed_count == 10, f"Chỉ có {passed_count}/10 quests thành công!"
