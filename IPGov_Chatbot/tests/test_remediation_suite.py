"""
Test Suite: 15 Remediation Test Cases for IPGov DWH Autonomous Chatbot (v1.4.0)
Tuân thủ: test_case_rule.md, overview-rule-Chatbot.md, và PLAN-REMEDIATION-v1.4.0
Kiểm thử 10 lỗi hệ thống bóc trần từ fail_quest_v1-2-0.json:
1. BUG-CLARIF-agr-T01: Underspecified Turn 1 (Active Clarification Chips)
2. BUG-CTX-agri-T03: Chained Ellipsis Pronoun Omission (Topic & Slot Fusion)
3. Attribute Pivoting: Q1 -> Q2 -> Q3
4. Topic Revival / Topic Return: Cross-domain switching
5. BUG-NONADD-i_01-T09: Non-additive metric trap (Window rn=1 vs SUM)
6. BUG-DIRTY-l_02-T02: Dirty data test account annotation (*(TK Quản trị)*)
7. BUG-FALLBACK-pers-T03: Inquiry about test account (Zero fallback Diêm nghiệp)
8. BUG-PROMPT-pers-T04: User table filtered attribute (Zero fallback Diêm nghiệp)
9. BUG-FILTER-pers-T09: Directional negative office filter
10. BUG-DIRTY-l_02-T10: Syntactic inversion colloquial
11. BUG-FALLBACK-pers-T13: Missing column / None name handling
12. BUG-OOS-t_03-T08: Out-of-Scope Administrative procedure (CCCD)
13. BUG-OOS-t_03-T09: Out-of-Scope Weather chitchat
14. BUG-OOS-t_03-T10: Out-of-Scope Political leadership
15. BUG-OOS-t_03-T11 & T15: Generative task & AST schema safety (COUNT(f.id))
"""

import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import json
import time
from datetime import datetime
import pytest

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import warehouse_agent

LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "logs"))
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "remediation_suite_run.jsonl")


def log_test_result(record: dict):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


REMEDIATION_CASES = [
    # TC-REM-01: Underspecified Turn 1 (BUG-CLARIF-agr-T01)
    {
        "id": "TC-REM-01",
        "description": "Lượt 1 thiếu mốc thời gian -> Kích hoạt Active Clarification Chips, không suy đoán 2026",
        "turns": [
            {
                "prompt": "Kính gửi chatbot, cho tôi hỏi tổng sản lượng muối",
                "expect_clarification": True,
                "expect_no_sql": True,
                "expected_keywords": ["mốc thời gian", "năm báo cáo"],
                "forbidden_keywords": ["đạt:", "SUM("],
            }
        ]
    },
    # TC-REM-02: Multi-turn ellipsis pronoun omission (BUG-CTX-agri-T03)
    {
        "id": "TC-REM-02",
        "description": "Kế thừa tỉnh lược đại từ: 'vậy có bao nhiêu hộ' kế thừa 'muối' và '2026'",
        "turns": [
            {
                "prompt": "tổng sản lượng muối năm 2026",
                "expect_sql": True,
            },
            {
                "prompt": "vậy có bao nhiêu hộ",
                "expect_sql": True,
                "expected_keywords": ["hộ", "muối"],
                "forbidden_keywords": ["chỉ tiêu chỉ tiêu", "chưa có số liệu ghi nhận (NULL)"],
            }
        ]
    },
    # TC-REM-03: Attribute Pivoting Q1 -> Q2 -> Q3
    {
        "id": "TC-REM-03",
        "description": "Chuyển dịch chỉ tiêu liên hoàn: Diện tích -> Sản lượng -> Số hộ (giữ Topic Muối + Năm 2026)",
        "turns": [
            {
                "prompt": "diện tích sản xuất muối năm 2026 là bao nhiêu?",
                "expect_sql": True,
            },
            {
                "prompt": "thế còn sản lượng?",
                "expect_sql": True,
                "expected_keywords": ["sản lượng"],
            },
            {
                "prompt": "có bao nhiêu hộ tham gia?",
                "expect_sql": True,
                "expected_keywords": ["hộ"],
                "forbidden_keywords": ["chỉ tiêu chỉ tiêu"],
            }
        ]
    },
    # TC-REM-04: Topic Revival / Topic Return (Level 2/3)
    {
        "id": "TC-REM-04",
        "description": "Hồi sinh chủ đề: Muối -> Nhiệm vụ -> Quay lại Muối",
        "turns": [
            {
                "prompt": "tổng sản lượng muối năm 2026 của tỉnh",
                "expect_sql": True,
            },
            {
                "prompt": "danh mục các nhiệm vụ trọng tâm của tỉnh năm 2026",
                "expect_sql": True,
                "expected_keywords": ["nhiệm vụ"],
            },
            {
                "prompt": "thế còn diện tích muối?",
                "expect_sql": True,
                "expected_keywords": ["diện tích", "muối"],
            }
        ]
    },
    # TC-REM-05: Non-additive metric trap (BUG-NONADD-i_01-T09)
    {
        "id": "TC-REM-05",
        "description": "Chỉ tiêu non-additive Doanh thu bình quân -> Dùng ROW_NUMBER() rn=1 hoặc AVG, không cộng dồn SUM",
        "turns": [
            {
                "prompt": "doanh thu bình quân trang trại toàn tỉnh năm 2026 là bao nhiêu?",
                "expect_sql": True,
                "sql_contains_patterns": ["rn = 1", "ROW_NUMBER", "report_date"],
            }
        ]
    },
    # TC-REM-06: Dirty data test account annotation (BUG-DIRTY-l_02-T02)
    {
        "id": "TC-REM-06",
        "description": "Hiển thị danh sách cán bộ có tài khoản test -> Gắn tag *(TK Quản trị)*",
        "user_context": {"role_level": 0, "tenant_code": "68"},
        "turns": [
            {
                "prompt": "Cán bộ nào phụ trách nhiệm vụ diêm nghiệp năm 2026?",
                "expect_sql": True,
                "expected_keywords": ["Nguyễn Thị Thúy Lành", "Phường Bắc Gia Nghĩa", "TK Quản trị"],
            }
        ]
    },
    # TC-REM-07: Inquiry about test account (BUG-FALLBACK-pers-T03)
    {
        "id": "TC-REM-07",
        "description": "Hỏi về tài khoản test Phường Bắc Gia Nghĩa -> Tuyệt đối không gán cứng 'Diêm nghiệp'",
        "turns": [
            {
                "prompt": "Cán bộ nào phụ trách nhiệm vụ diêm nghiệp năm 2026?",
                "expect_sql": True,
            },
            {
                "prompt": "Ủa sao trong danh sách cán bộ lại có tên Phường Bắc Gia Nghĩa?",
                "expect_sql": True,
                "forbidden_keywords": ["cán bộ phụ trách nhiệm vụ **Diêm nghiệp**", "nhiệm vụ **Diêm nghiệp** là đồng chí"],
            }
        ]
    },
    # TC-REM-08: User table filtered attribute (BUG-PROMPT-pers-T04)
    {
        "id": "TC-REM-08",
        "description": "Lọc cán bộ theo chức vụ QTV -> Không hallucinate gán nhiệm vụ Diêm nghiệp",
        "turns": [
            {
                "prompt": "Liệt kê các cán bộ có chức vụ QTV của phòng nông nghiệp",
                "expect_sql": True,
                "forbidden_keywords": ["nhiệm vụ **Diêm nghiệp**"],
            }
        ]
    },
    # TC-REM-09: Directional negative office filter (BUG-FILTER-pers-T09)
    {
        "id": "TC-REM-09",
        "description": "Lọc định hướng phủ định: Lấy cán bộ thuộc chi cục phụ trách phát triển nông thôn, không lấy cấp phòng",
        "turns": [
            {
                "prompt": "chỉ lấy cán bộ thuộc chi cục phụ trách phát triển nông thôn, không lấy cấp phòng",
                "expect_sql": True,
                "sql_contains_patterns": ["NOT", "phát triển nông thôn"],
            }
        ]
    },
    # TC-REM-10: Syntactic inversion colloquial (BUG-DIRTY-l_02-T10)
    {
        "id": "TC-REM-10",
        "description": "Đảo ngữ tự nhiên: 'nhiệm vụ diêm nghiệp do ai nắm?' -> Trả về danh sách cán bộ",
        "turns": [
            {
                "prompt": "nhiệm vụ diêm nghiệp do ai nắm?",
                "expect_sql": True,
                "expected_keywords": ["Nguyễn Thị Thúy Lành"],
            }
        ]
    },
    # TC-REM-11: Missing column / None name handling (BUG-FALLBACK-pers-T13)
    {
        "id": "TC-REM-11",
        "description": "Hỏi chức vụ đơn vị cán bộ Lành -> Không in 'đồng chí None' và không gán cứng Diêm nghiệp",
        "turns": [
            {
                "prompt": "có cán bộ nào tên Lành trong sở không?",
                "expect_sql": True,
            },
            {
                "prompt": "chức vụ và đơn vị công tác của cán bộ Lành là gì?",
                "expect_sql": True,
                "forbidden_keywords": ["đồng chí None", "đồng chí **None**", "nhiệm vụ **Diêm nghiệp**"],
            }
        ]
    },
    # TC-REM-12: Out-of-Scope Administrative procedure (BUG-OOS-t_03-T08)
    {
        "id": "TC-REM-12",
        "description": "Thủ tục hành chính CCCD gắn chip -> Từ chối an toàn, không sinh SQL DWH",
        "turns": [
            {
                "prompt": "thủ tục cấp đổi căn cước công dân gắn chip cần giấy tờ gì?",
                "expect_no_sql": True,
                "expected_keywords": ["phạm vi", "hành chính"],
                "forbidden_keywords": ["<details>", "SELECT"],
            }
        ]
    },
    # TC-REM-13: Out-of-Scope Weather chitchat (BUG-OOS-t_03-T09)
    {
        "id": "TC-REM-13",
        "description": "Thời tiết chitchat -> Từ chối an toàn, không sinh SQL DWH",
        "turns": [
            {
                "prompt": "hôm nay thời tiết Đà Lạt thế nào bạn ơi?",
                "expect_no_sql": True,
                "expected_keywords": ["ngoài phạm vi", "thời tiết"],
                "forbidden_keywords": ["<details>", "SELECT"],
            }
        ]
    },
    # TC-REM-14: Out-of-Scope Political leadership (BUG-OOS-t_03-T10)
    {
        "id": "TC-REM-14",
        "description": "Lãnh đạo chính trị -> Từ chối an toàn, không sinh SQL DWH",
        "turns": [
            {
                "prompt": "bí thư tỉnh ủy hiện tại là ai?",
                "expect_no_sql": True,
                "expected_keywords": ["ngoài phạm vi", "lãnh đạo"],
                "forbidden_keywords": ["<details>", "SELECT"],
            }
        ]
    },
    # TC-REM-15: Generative task & AST schema safety (BUG-OOS-t_03-T11 & T15)
    {
        "id": "TC-REM-15",
        "description": "Sáng tác văn bản & Đánh giá định tính -> Từ chối an toàn, không crash COUNT(f.id)",
        "turns": [
            {
                "prompt": "hãy viết cho tôi bài phát biểu khai mạc hội nghị nông nghiệp",
                "expect_no_sql": True,
                "expected_keywords": ["ngoài phạm vi", "sáng tác"],
                "forbidden_keywords": ["<details>", "SELECT"],
            },
            {
                "prompt": "tổng kết lại, toàn bộ số liệu báo cáo đã nộp của sở có đáng tin cậy không?",
                "forbidden_keywords": ["column f.id does not exist", "500 Internal", "Lỗi thực thi PostgreSQL"],
            }
        ]
    },
]


@pytest.mark.parametrize("case", REMEDIATION_CASES, ids=[c["id"] for c in REMEDIATION_CASES])
def test_remediation_case(case):
    test_id = case["id"]
    desc = case["description"]
    turns = case["turns"]

    session_id = f"session_rem_{test_id}_{int(time.time())}"
    user_context = case.get("user_context") or {"role_level": 0, "tenant_code": "68", "department_code": "68-1-01"}

    for t_idx, turn in enumerate(turns, 1):
        prompt = turn["prompt"]
        t0 = time.perf_counter()
        result = warehouse_agent.run(prompt, session_id=session_id, user_context=user_context)
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        answer = result.get("answer") or ""
        sql = result.get("sql")
        query_res = result.get("query_result") or {}
        row_count = query_res.get("row_count", 0)

        # 1. Check no sql expectation
        if turn.get("expect_no_sql"):
            assert sql is None, f"[{test_id} Turn {t_idx}] Expected no SQL but got: {sql}"
            assert "<details>" not in answer, f"[{test_id} Turn {t_idx}] Answer should not contain collapsible SQL block!"

        # 2. Check sql expectation
        if turn.get("expect_sql"):
            assert sql is not None, f"[{test_id} Turn {t_idx}] Expected SQL to be generated but got None!"

        # 3. Check clarification
        if turn.get("expect_clarification"):
            chips = result.get("quick_action_chips") or []
            assert any("2026" in c.get("label", "") or "2025" in c.get("label", "") for c in chips) or "mốc thời gian" in answer.lower(), (
                f"[{test_id} Turn {t_idx}] Expected clarification prompt/chips but got answer: {answer}"
            )

        # 4. Check expected keywords
        for kw in turn.get("expected_keywords", []):
            assert kw.lower() in answer.lower(), (
                f"[{test_id} Turn {t_idx}] Expected keyword '{kw}' not found in answer:\n{answer}"
            )

        # 5. Check forbidden keywords
        for fkw in turn.get("forbidden_keywords", []):
            assert fkw.lower() not in answer.lower(), (
                f"[{test_id} Turn {t_idx}] Forbidden keyword '{fkw}' found in answer:\n{answer}"
            )

        # 6. Check SQL patterns
        for pattern in turn.get("sql_contains_patterns", []):
            if sql:
                assert pattern.lower() in sql.lower(), (
                    f"[{test_id} Turn {t_idx}] Expected SQL pattern '{pattern}' not found in SQL:\n{sql}"
                )

        # Log turn result
        log_record = {
            "timestamp": datetime.now().isoformat() + "Z",
            "test_id": f"{test_id}_T{t_idx}",
            "description": desc,
            "prompt": prompt,
            "executed_sql": sql,
            "row_count": row_count,
            "answer_preview": answer[:250],
            "latency_ms": elapsed_ms,
            "status": "PASSED",
        }
        log_test_result(log_record)


if __name__ == "__main__":
    print("=" * 80)
    print("CHẠY TRỰC TIẾP BỘ KIỂM THỬ 15 CA REMEDIATION THEO PLAN-REMEDIATION-v1.4.0")
    print("=" * 80)
    passed = 0
    failed = 0
    results_summary = []

    for idx, case in enumerate(REMEDIATION_CASES, 1):
        print(f"[{idx}/15] Đang kiểm thử {case['id']}: {case['description'][:45]}...", end=" ", flush=True)
        try:
            test_remediation_case(case)
            print("✅ PASS")
            passed += 1
            results_summary.append((case["id"], case["description"], "PASS"))
        except Exception as e:
            print(f"❌ FAIL ({e})")
            failed += 1
            results_summary.append((case["id"], case["description"], f"FAIL: {e}"))

    print("\n" + "=" * 80)
    print(f"KẾT QUẢ TỔNG HỢP: {passed}/15 PASSED ({round(passed / 15 * 100, 1)}%), {failed} FAILED")
    print(f"Log đã được ghi nhận tại: {LOG_FILE}")
    print("=" * 80)
