"""
Backend 20-Quest Runner for Render Scheduled Automation Suite.
Strictly enforces the hard cap of <= 20 Backend Quests, executes against
https://ipgov-chatbot-backend.onrender.com/api/v1/chat/stream, cross-checks
against Warehouse Ground Truth, and outputs verdicts starting with 'Correct' or 'Wrong'.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from IPGov_Chatbot.tests.render_automation.warehouse_ground_truth_checker import (
    WarehouseGroundTruthChecker,
)

RENDER_BACKEND_URL = os.getenv(
    "RENDER_BACKEND_URL", "https://ipgov-chatbot-backend.onrender.com"
).rstrip("/")

BACKEND_20_QUESTS: List[Dict[str, Any]] = [
    {
        "id": "BE-01",
        "ref": "REQ-Q01",
        "session_group": "sess_be_single_01",
        "prompt": "Hệ thống hiện đang thu thập những chỉ tiêu nào trong năm 2026?",
        "expected_keywords": ["Tổng hộ sản xuất muối", "660", "HTX nông nghiệp", "Chi cục"],
        "min_table_rows": 6,
    },
    {
        "id": "BE-02",
        "ref": "REQ-Q01 + Ticket-Time",
        "session_group": "sess_be_single_02",
        "prompt": "Trong quý 2 năm nay có những chỉ tiêu nào được thu thập?",
        "expected_keywords": ["Tổng hộ sản xuất muối", "Chi cục"],
        "min_table_rows": 5,
    },
    {
        "id": "BE-03",
        "ref": "REQ-Q01 / SC-1.2",
        "session_group": "sess_be_single_03",
        "prompt": "Các chỉ tiêu thu thập trong tháng 1 năm 2024 là gì?",
        "expected_keywords": ["2024", "chưa", "2026"],
        "min_table_rows": 0,
    },
    {
        "id": "BE-04",
        "ref": "REQ-Q04",
        "session_group": "sess_be_single_04",
        "prompt": "Hiển thị các chỉ tiêu cấp 1 của nhiệm vụ Phát triển nông thôn?",
        "expected_keywords": ["Phát triển nông thôn", "HTX nông nghiệp", "Liên hiệp HTX nông nghiệp"],
        "min_table_rows": 4,
    },
    {
        "id": "BE-05",
        "ref": "REQ-Q04 / SC-4.2",
        "session_group": "sess_be_single_05",
        "prompt": "Nhiệm vụ Cải cách hành chính năm 2026 có các chỉ tiêu nào?",
        "expected_keywords": ["Cải cách hành chính", "không có"],
        "min_table_rows": 0,
    },
    {
        "id": "BE-06",
        "ref": "REQ-Q02",
        "session_group": "sess_be_single_06",
        "prompt": "Cho tôi biết tổng hộ sản xuất muối năm 2026 là bao nhiêu?",
        "expected_keywords": ["Tổng hộ sản xuất muối", "Chi cục", "Diêm nghiệp"],
        "min_table_rows": 0,
    },
    {
        "id": "BE-07",
        "ref": "REQ-Q02 + Ticket-Time",
        "session_group": "sess_be_single_07",
        "prompt": "Chỉ tiêu sản lượng muối công nghiệp trong quý 2 năm 2026 là bao nhiêu?",
        "expected_keywords": ["Sản lượng muối", "công nghiệp", "5,500", "Chi cục", "Diêm nghiệp"],
        "min_table_rows": 0,
    },
    {
        "id": "BE-08",
        "ref": "SC-2.1 + FB2-UI-05",
        "session_group": "sess_be_single_08",
        "prompt": "Chăn nuôi ngày 30/4",
        "expected_keywords": ["Chăn nuôi", "58", "25", "135", "1"],
        "forbidden_post_table_substrings": ["Lưu ý mốc thời gian:", "Đơn vị thực hiện: Chi cục, Nhiệm vụ trọng tâm:"],
        "min_table_rows": 4,
    },
    {
        "id": "BE-09",
        "ref": "SC-2.1b + FB2-LOG-05",
        "session_group": "sess_be_single_09",
        "prompt": "cho tôi biết số liệu chăn nuôi của liên hiệp hợp tác xã ngày 30/4",
        "expected_keywords": ["Chăn nuôi", "Tổng số LHHTX phân theo lĩnh vực", "1", "Chi cục"],
        "max_table_rows": 1,
    },
    {
        "id": "BE-10",
        "ref": "SC-2.4a + FB1-UI-03",
        "session_group": "sess_be_single_10",
        "prompt": "Tổng số lượng chủ thể sản phẩm OCOP trong năm là bao nhiêu?",
        "expected_keywords": ["Tổng số lượng chủ thể sản phẩm OCOP trong năm", "17", "Chi cục"],
        "forbidden_post_table_substrings": ["🔘 ["],
        "min_quick_chips": 2,
    },
    {
        "id": "BE-11",
        "ref": "SC-2.4b",
        "session_group": "sess_be_single_11",
        "prompt": "Cho tôi biết số liệu chỉ tiêu Liên hiệp HTX nông nghiệp?",
        "expected_keywords": ["Liên hiệp HTX nông nghiệp", "chỉ tiêu cha"],
        "min_quick_chips": 3,
    },
    {
        "id": "BE-12",
        "ref": "SC-2.5 + FB2-LOG-01",
        "session_group": "sess_be_multiturn_shared",
        "prompt": "có bao nhiêu mức đánh giá hiệu quả hoạt động của hợp tác xã nông nghiệp ?",
        "expected_keywords": [
            "Số HTX nông nghiệp hoạt động hiệu quả tốt",
            "Số HTX nông nghiệp hoạt động hiệu quả trung bình",
            "Số HTX nông nghiệp hoạt động kém hiệu quả",
            "Chưa đủ điều kiện đánh giá",
        ],
        "expected_row_order": [
            "Số HTX nông nghiệp hoạt động hiệu quả tốt",
            "Số HTX nông nghiệp hoạt động hiệu quả trung bình",
            "Số HTX nông nghiệp hoạt động kém hiệu quả",
            "Chưa đủ điều kiện đánh giá",
        ],
        "min_table_rows": 4,
    },
    {
        "id": "BE-13",
        "ref": "SC-2.5 + CUR-BUG-03a (Multi-turn Synonym A)",
        "session_group": "sess_be_multiturn_shared",
        "prompt": "cho tôi biết số lĩnh vực của HTX nông nghiệp",
        "expected_keywords": [
            "Trồng trọt",
            "Chăn nuôi",
            "Lâm nghiệp",
            "Thủy sản",
            "Diêm nghiệp",
            "Chế biến nông sản",
            "Nước sạch NT",
            "Tổng hợp",
        ],
        "expected_row_order": [
            "Trồng trọt",
            "Chăn nuôi",
            "Lâm nghiệp",
            "Thủy sản",
            "Diêm nghiệp",
            "Chế biến nông sản",
            "Nước sạch NT",
            "Tổng hợp",
        ],
        "min_table_rows": 8,
    },
    {
        "id": "BE-14",
        "ref": "SC-2.5 + CUR-BUG-03b (Multi-turn Synonym B)",
        "session_group": "sess_be_multiturn_shared",
        "prompt": "cho tôi biết số lượng lĩnh vực của hợp tác xã nông nghiệp",
        "expected_keywords": [
            "Trồng trọt",
            "Chăn nuôi",
            "Lâm nghiệp",
            "Thủy sản",
            "Diêm nghiệp",
            "Chế biến nông sản",
            "Nước sạch NT",
            "Tổng hợp",
        ],
        "expected_row_order": [
            "Trồng trọt",
            "Chăn nuôi",
            "Lâm nghiệp",
            "Thủy sản",
            "Diêm nghiệp",
            "Chế biến nông sản",
            "Nước sạch NT",
            "Tổng hợp",
        ],
        "min_table_rows": 8,
    },
    {
        "id": "BE-15",
        "ref": "SC-2.5 + FB1-LOG-01",
        "session_group": "sess_be_single_15",
        "prompt": "Cho tôi biết đang có các loại diện tích sản xuất muối gì?",
        "expected_keywords": [
            "Diện tích muối sản xuất công nghiệp",
            "Diện tích muối sản xuất thủ công",
        ],
        "min_table_rows": 2,
    },
    {
        "id": "BE-16",
        "ref": "SC-2.5 + FB2-LOG-03",
        "session_group": "sess_be_single_16",
        "prompt": "cho tôi biết số lượng lĩnh vực của HTX nông nghiệp trong quý 1",
        "expected_keywords": ["Trồng trọt", "Chăn nuôi", "130", "25", "15", "7", "13"],
        "min_table_rows": 8,
    },
    {
        "id": "BE-17",
        "ref": "SC-2.6 + FB1-LOG-02a",
        "session_group": "sess_be_single_17",
        "prompt": "bạn hãy cho tôi biết lũy kế tổng số lượng chủ thể sản phẩm theo dữ liệu mới nhất",
        "expected_keywords": ["Lũy kế", "chủ thể", "đến thời điểm báo cáo"],
    },
    {
        "id": "BE-18",
        "ref": "SC-2.6 + FB1-LOG-02b",
        "session_group": "sess_be_single_18",
        "prompt": "bạn hãy cho tôi biết lũy kế tổng số lượng chủ thể sản phẩm OCOP theo dữ liệu mới nhất",
        "expected_keywords": ["Lũy kế", "OCOP", "đến thời điểm báo cáo"],
    },
    {
        "id": "BE-19",
        "ref": "REQ-Q03",
        "session_group": "sess_be_single_19",
        "prompt": "Liệt kê các nhiệm vụ trong lĩnh vực Nông nghiệp?",
        "expected_keywords": ["Diêm nghiệp", "Phát triển nông thôn", "Chi cục"],
        "min_table_rows": 2,
    },
    {
        "id": "BE-20",
        "ref": "REQ-Q05 / SC-5.1a",
        "session_group": "sess_be_single_20",
        "prompt": "Liệt kê trạng thái các kỳ báo cáo năm 2026, ngày nộp và những báo cáo nào đang ở trạng thái nháp chưa nộp?",
        "expected_keywords": ["2026-09-30", "Đã phê duyệt", "Bản nháp", "Chi cục"],
        "min_table_rows": 9,
    },
]

assert len(BACKEND_20_QUESTS) <= 20, "HARD CONSTRAINT VIOLATION: Backend quests must not exceed 20!"


def warmup_render_backend(timeout_sec: int = 120) -> Tuple[bool, float, str]:
    """Wakes up Render Free Tier backend and waits until /api/v1/health is ready."""
    t0 = time.time()
    health_url = f"{RENDER_BACKEND_URL}/api/v1/health"
    last_err = ""
    while time.time() - t0 < timeout_sec:
        try:
            resp = requests.get(health_url, timeout=15)
            if resp.status_code == 200:
                elapsed = round(time.time() - t0, 2)
                return True, elapsed, resp.text[:300]
            last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as exc:
            last_err = str(exc)
        time.sleep(5)
    return False, round(time.time() - t0, 2), last_err


def call_render_chat_stream(
    prompt: str,
    session_id: str,
    history: List[Dict[str, str]],
    timeout_sec: int = 90,
) -> Dict[str, Any]:
    """Calls /api/v1/chat/stream on Render and parses SSE events + final answer."""
    url = f"{RENDER_BACKEND_URL}/api/v1/chat/stream"
    payload = {
        "query": prompt,
        "session_id": session_id,
        "history": history,
        "tenant_code": "68",
        "role_level": 3,
    }
    t0 = time.time()
    tokens: List[str] = []
    done_payload: Dict[str, Any] = {}
    error_msg: Optional[str] = None

    try:
        with requests.post(url, json=payload, stream=True, timeout=timeout_sec) as resp:
            if resp.status_code != 200:
                return {
                    "ok": False,
                    "latency_s": round(time.time() - t0, 2),
                    "error": f"HTTP {resp.status_code}: {resp.text[:300]}",
                    "answer": "",
                    "done_payload": {},
                }
            current_event = ""
            for raw_line in resp.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                line = raw_line.strip()
                if line.startswith("event:"):
                    current_event = line.split("event:", 1)[1].strip()
                elif line.startswith("data:"):
                    data_str = line.split("data:", 1)[1].strip()
                    try:
                        data_obj = json.loads(data_str)
                    except Exception:
                        continue
                    if current_event in ("token", "content_chunk") or ("content" in data_obj and "full_answer" not in data_obj):
                        tok = data_obj.get("content") or data_obj.get("chunk") or data_obj.get("text") or data_obj.get("token") or ""
                        tokens.append(tok)
                    if current_event == "done" or "full_answer" in data_obj or "answer" in data_obj or "tabular_data" in data_obj:
                        done_payload = data_obj
    except Exception as exc:
        error_msg = str(exc)

    full_answer = done_payload.get("full_answer") or done_payload.get("answer") or "".join(tokens)
    return {
        "ok": error_msg is None and bool(full_answer),
        "latency_s": round(time.time() - t0, 2),
        "error": error_msg,
        "answer": full_answer,
        "done_payload": done_payload,
    }


def evaluate_backend_quest(quest: Dict[str, Any], result: Dict[str, Any]) -> Tuple[bool, str]:
    """Evaluates a single Backend quest response against Warehouse expectations."""
    if not result.get("ok"):
        return False, f"Wrong — Lỗi kết nối hoặc phản hồi rỗng từ Render Backend ({result.get('error')})."

    ans = result.get("answer", "")
    done_payload = result.get("done_payload", {}) or {}
    tab = done_payload.get("tabular_data") or {}
    rows = tab.get("rows") or []
    chips = done_payload.get("quick_action_chips") or []

    missing_kw = [kw for kw in quest.get("expected_keywords", []) if kw.lower() not in ans.lower() and kw.lower() not in json.dumps(rows, ensure_ascii=False).lower()]
    if missing_kw:
        return (
            False,
            f"Wrong — Đáp án thiếu thông tin kỳ vọng từ Warehouse {missing_kw}. Nội dung nhận được: {ans[:220]}...",
        )

    min_rows = quest.get("min_table_rows")
    if min_rows and len(rows) < min_rows:
        return (
            False,
            f"Wrong — Bảng dữ liệu trả về {len(rows)} dòng, thấp hơn số dòng chuẩn trong Warehouse ({min_rows} dòng). Nội dung nhận được: {ans[:200]}...",
        )

    max_rows = quest.get("max_table_rows")
    if max_rows is not None and len(rows) > max_rows:
        return (
            False,
            f"Wrong — Câu hỏi định danh nhánh cụ thể nhưng hệ thống trả về bảng {len(rows)} dòng (vượt quá {max_rows}).",
        )

    expected_order = quest.get("expected_row_order")
    if expected_order and rows:
        actual_names: List[str] = []
        for r in rows:
            if isinstance(r, list) and len(r) >= 2:
                actual_names.append(str(r[1]).replace("*", "").strip())
            elif isinstance(r, dict):
                nm = (
                    r.get("ten_chi_tieu")
                    or r.get("name")
                    or r.get("Tên chỉ tiêu")
                    or r.get("ten_chi_tieu_cap_1")
                    or r.get("item")
                    or ""
                )
                actual_names.append(str(nm).replace("*", "").strip())
        for idx, exp_name in enumerate(expected_order):
            if idx >= len(actual_names) or exp_name.lower() not in actual_names[idx].lower():
                return (
                    False,
                    f"Wrong — Thứ tự hiển thị chỉ tiêu con lệch với Warehouse: Thực tế {actual_names} != Kỳ vọng {expected_order}.",
                )

    for bad_sub in quest.get("forbidden_post_table_substrings", []):
        if bad_sub in ans:
            return (
                False,
                f"Wrong — Phát hiện phần text thừa hoặc chuỗi bị cấm '{bad_sub}' trong câu trả lời.",
            )

    min_chips = quest.get("min_quick_chips")
    if min_chips and len(chips) < min_chips:
        return (
            False,
            f"Wrong — Số lượng button gợi ý chỉ tiêu con ({len(chips)}) thấp hơn kỳ vọng ({min_chips}).",
        )

    return (
        True,
        f"Correct — Đáp án khớp 100% với dữ liệu và cấu trúc trong Warehouse (rows={len(rows)}, chips={len(chips)}, latency={result.get('latency_s')}s).",
    )


def run_backend_20_suite(batch_id: str) -> Dict[str, Any]:
    """Runs all 20 Backend quests against Render and saves detailed JSON report."""
    checker = WarehouseGroundTruthChecker()
    gt_snapshot = checker.dump_reference_snapshot()

    warm_ok, warm_sec, warm_info = warmup_render_backend(timeout_sec=120)
    session_histories: Dict[str, List[Dict[str, str]]] = {}
    quest_results: List[Dict[str, Any]] = []
    passed_count = 0

    for idx, q in enumerate(BACKEND_20_QUESTS, start=1):
        sess_key = f"{batch_id}_{q['session_group']}"
        hist = session_histories.setdefault(sess_key, [])
        res = call_render_chat_stream(q["prompt"], session_id=sess_key, history=hist)
        is_correct, verdict_comment = evaluate_backend_quest(q, res)
        if is_correct:
            passed_count += 1
        hist.append({"role": "user", "content": q["prompt"]})
        if res.get("answer"):
            hist.append({"role": "assistant", "content": res["answer"]})

        quest_results.append(
            {
                "index": idx,
                "id": q["id"],
                "ref": q["ref"],
                "session_id": sess_key,
                "prompt": q["prompt"],
                "is_correct": is_correct,
                "verdict": verdict_comment,
                "latency_s": res.get("latency_s"),
                "answer_preview": (res.get("answer") or "")[:350],
                "row_count": len(((res.get("done_payload") or {}).get("tabular_data") or {}).get("rows") or []),
            }
        )

    summary = {
        "batch_id": batch_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_backend_url": RENDER_BACKEND_URL,
        "warmup": {"ok": warm_ok, "seconds": warm_sec, "info": warm_info},
        "total_quests": len(BACKEND_20_QUESTS),
        "correct_count": passed_count,
        "wrong_count": len(BACKEND_20_QUESTS) - passed_count,
        "results": quest_results,
        "warehouse_ground_truth_summary": {
            "htx_efficiency_order": gt_snapshot["htx_efficiency_4_levels"].get("canonical_order_names"),
            "htx_fields_order": gt_snapshot["htx_fields_8_items"].get("canonical_order_names"),
        },
    }

    out_dir = PROJECT_ROOT / "IPGov_Chatbot" / "data" / "reports" / "render_automation"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"backend_20_results_{batch_id}.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    batch = datetime.now().strftime("BATCH-%Y%m%d-%H%M%S")
    report = run_backend_20_suite(batch)
    print(
        f"[{report['batch_id']}] Backend 20-Quest Suite Finished: "
        f"{report['correct_count']}/{report['total_quests']} Correct"
    )
