"""
Test Suite: 30 Warehouse-Focused Test Cases for IPGov DWH Autonomous Chatbot
Tuân thủ: test_case_rule.md & ADR-001
Phân loại 30 câu hỏi kho dữ liệu thực tế (vna_wom_dev, tenant '68', năm 2026):
1. Muối & Diêm nghiệp: 6 câu
2. OCOP, HTX & Nông nghiệp: 6 câu
3. Báo cáo & Đợt nộp: 6 câu
4. Biểu mẫu thu thập: 4 câu
5. Nhiệm vụ & Cán bộ chuyên môn: 4 câu
6. Khả năng Chatbot & Chào hỏi & Ngữ cảnh đa lượt: 4 câu
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
LOG_FILE = os.path.join(LOG_DIR, "warehouse_30_cases_run.jsonl")


# Danh sách 30 câu hỏi kho dữ liệu
WAREHOUSE_30_CASES = [
    # --- NHÓM 1: MUỐI & DIÊM NGHIỆP (6 CÂU) ---
    {
        "id": "TC-SALT-01",
        "category": "Muối & Diêm nghiệp",
        "prompt": "Tổng các hộ sản xuất muối hiện tại là bao nhiêu?",
        "expected_sql": True,
        "expected_keywords": ["1,320", "muối", "hộ"],
    },
    {
        "id": "TC-SALT-02",
        "category": "Muối & Diêm nghiệp",
        "prompt": "Tổng diện tích sản xuất muối năm 2026 của tỉnh là bao nhiêu ha?",
        "expected_sql": True,
        "expected_keywords": ["diện tích", "muối"],
    },
    {
        "id": "TC-SALT-03",
        "category": "Muối & Diêm nghiệp",
        "prompt": "Diện tích muối sản xuất thủ công năm 2026 đạt bao nhiêu?",
        "expected_sql": True,
        "expected_keywords": ["thủ công"],
    },
    {
        "id": "TC-SALT-04",
        "category": "Muối & Diêm nghiệp",
        "prompt": "Diện tích muối sản xuất công nghiệp là bao nhiêu ha?",
        "expected_sql": True,
        "expected_keywords": ["công nghiệp"],
    },
    {
        "id": "TC-SALT-05",
        "category": "Muối & Diêm nghiệp",
        "prompt": "Tổng sản lượng muối năm 2026 toàn tỉnh đạt bao nhiêu tấn?",
        "expected_sql": True,
        "expected_keywords": ["sản lượng", "muối"],
    },
    {
        "id": "TC-SALT-06",
        "category": "Muối & Diêm nghiệp",
        "prompt": "Sản lượng muối sản xuất thủ công năm 2026 là bao nhiêu tấn?",
        "expected_sql": True,
        "expected_keywords": ["thủ công"],
    },

    # --- NHÓM 2: OCOP, HTX & NÔNG NGHIỆP (6 CÂU) ---
    {
        "id": "TC-AGRI-01",
        "category": "OCOP & Nông nghiệp",
        "prompt": "Số lượng chủ thể sản phẩm OCOP 4 sao năm 2026 là bao nhiêu?",
        "expected_sql": True,
        "expected_keywords": ["OCOP", "sao"],
    },
    {
        "id": "TC-AGRI-02",
        "category": "OCOP & Nông nghiệp",
        "prompt": "Chương trình OCOP tỉnh Lâm Đồng năm 2026 có những chỉ tiêu nào?",
        "expected_sql": True,
        "expected_keywords": ["OCOP"],
    },
    {
        "id": "TC-AGRI-03",
        "category": "OCOP & Nông nghiệp",
        "prompt": "Tổng số hợp tác xã nông nghiệp đang hoạt động năm 2026?",
        "expected_sql": True,
        "expected_keywords": ["Tổ hợp tác nông nghiệp", "2026"],
    },
    {
        "id": "TC-AGRI-04",
        "category": "OCOP & Nông nghiệp",
        "prompt": "Số HTX nông nghiệp hoạt động hiệu quả tốt là bao nhiêu đơn vị?",
        "expected_sql": True,
        "expected_keywords": ["hiệu quả", "HTX"],
    },
    {
        "id": "TC-AGRI-05",
        "category": "OCOP & Nông nghiệp",
        "prompt": "Doanh thu bình quân trong năm của một hợp tác xã nông nghiệp là bao nhiêu?",
        "expected_sql": True,
        "expected_keywords": ["doanh thu", "bình quân"],
    },
    {
        "id": "TC-AGRI-06",
        "category": "OCOP & Nông nghiệp",
        "prompt": "Số lượng HTX nông nghiệp trong lĩnh vực trồng trọt năm 2026?",
        "expected_sql": True,
        "expected_keywords": ["HTX nông nghiệp", "2026"],
    },

    # --- NHÓM 3: BÁO CÁO & ĐỢT NỘP (6 CÂU) ---
    {
        "id": "TC-REP-01",
        "category": "Báo cáo & Đợt nộp",
        "prompt": "Có bao nhiêu đợt báo cáo đã được nộp trong năm 2026?",
        "expected_sql": True,
        "expected_keywords": ["báo cáo", "2026"],
    },
    {
        "id": "TC-REP-02",
        "category": "Báo cáo & Đợt nộp",
        "prompt": "Trạng thái các đợt nộp báo cáo của Sở Nông nghiệp 68-1-01?",
        "expected_sql": True,
        "expected_keywords": ["báo cáo", "phê duyệt"],
    },
    {
        "id": "TC-REP-03",
        "category": "Báo cáo & Đợt nộp",
        "prompt": "Danh sách các báo cáo đã được phê duyệt trong kho dữ liệu?",
        "expected_sql": True,
        "expected_keywords": ["báo cáo"],
    },
    {
        "id": "TC-REP-04",
        "category": "Báo cáo & Đợt nộp",
        "prompt": "Đợt báo cáo gần nhất trong năm 2026 được nộp vào ngày nào?",
        "expected_sql": True,
        "expected_keywords": ["báo cáo", "2026"],
    },
    {
        "id": "TC-REP-05",
        "category": "Báo cáo & Đợt nộp",
        "prompt": "Cơ quan nào đã nộp báo cáo chỉ tiêu năm 2026 cho tỉnh Lâm Đồng?",
        "expected_sql": True,
        "expected_keywords": ["68-1-01", "báo cáo"],
    },
    {
        "id": "TC-REP-06",
        "category": "Báo cáo & Đợt nộp",
        "prompt": "Báo cáo quý 1 năm 2026 có những chỉ tiêu tổng hợp nào?",
        "expected_sql": True,
        "expected_keywords": ["2026"],
    },

    # --- NHÓM 4: BIỂU MẪU THU THẬP (4 CÂU) ---
    {
        "id": "TC-FORM-01",
        "category": "Biểu mẫu thu thập",
        "prompt": "Hiện tại có những biểu mẫu thu thập thông tin nào đang kích hoạt?",
        "expected_sql": True,
        "expected_keywords": ["2026"],
    },
    {
        "id": "TC-FORM-02",
        "category": "Biểu mẫu thu thập",
        "prompt": "Danh mục biểu mẫu nộp báo cáo số liệu của tỉnh Lâm Đồng năm 2026?",
        "expected_sql": True,
        "expected_keywords": ["2026"],
    },
    {
        "id": "TC-FORM-03",
        "category": "Biểu mẫu thu thập",
        "prompt": "Biểu mẫu BM_01 được ban hành cho những cơ quan nào?",
        "expected_sql": True,
        "expected_keywords": ["chưa có", "DWH"],
    },
    {
        "id": "TC-FORM-04",
        "category": "Biểu mẫu thu thập",
        "prompt": "Kiểm tra tình trạng các mẫu tờ khai thu thập dữ liệu nông nghiệp",
        "expected_sql": True,
        "expected_keywords": ["2026"],
    },

    # --- NHÓM 5: NHIỆM VỤ & CÁN BỘ (4 CÂU) ---
    {
        "id": "TC-MIS-01",
        "category": "Nhiệm vụ & Cán bộ",
        "prompt": "Danh mục các nhiệm vụ trọng tâm năm 2026 của tỉnh Lâm Đồng?",
        "expected_sql": True,
        "expected_keywords": ["Diêm nghiệp"],
    },
    {
        "id": "TC-MIS-02",
        "category": "Nhiệm vụ & Cán bộ",
        "prompt": "Nhiệm vụ Phát triển nông thôn do phòng ban nào phụ trách?",
        "expected_sql": True,
        "expected_keywords": ["Phát triển nông thôn"],
    },
    {
        "id": "TC-MIS-03",
        "category": "Nhiệm vụ & Cán bộ",
        "prompt": "Danh sách cán bộ quản trị hệ thống của tỉnh Lâm Đồng?",
        "expected_sql": True,
        "expected_keywords": ["Admin Tỉnh Lâm Đồng"],
    },
    {
        "id": "TC-MIS-04",
        "category": "Nhiệm vụ & Cán bộ",
        "prompt": "Cán bộ nào phụ trách nhiệm vụ diêm nghiệp năm 2026?",
        "expected_sql": True,
        "expected_keywords": ["diêm nghiệp"],
    },

    # --- NHÓM 6: KHẢ NĂNG CHATBOT & CHÀO HỎI & ĐA LƯỢT (4 CÂU) ---
    {
        "id": "TC-CAP-01",
        "category": "Khả năng Chatbot",
        "prompt": "Bạn có thể làm được những gì?",
        "expected_sql": False,  # Không được sinh SQL, không dump fact table
        "expected_keywords": ["Trợ lý AI", "Kho Dữ Liệu"],
    },
    {
        "id": "TC-CAP-02",
        "category": "Khả năng Chatbot",
        "prompt": "Bạn giúp được gì cho tôi trong việc tra cứu số liệu?",
        "expected_sql": False,
        "expected_keywords": ["Trợ lý AI", "chỉ tiêu", "báo cáo"],
    },
    {
        "id": "TC-CAP-03",
        "category": "Chào hỏi",
        "prompt": "Xin chào chatbot",
        "expected_sql": False,
        "expected_keywords": ["Xin chào", "Trợ lý AI"],
    },
    {
        "id": "TC-MULTI-01",
        "category": "Ngữ cảnh đa lượt",
        "prompt": "Thế còn sản lượng muối sản xuất công nghiệp thì sao?",
        "expected_sql": True,
        "expected_keywords": ["11,000", "2026"],
        "setup_turn": "Tổng các hộ sản xuất muối hiện tại là bao nhiêu?",
    },
]


def log_test_result(record: dict):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


@pytest.mark.parametrize("tc", WAREHOUSE_30_CASES, ids=[tc["id"] for tc in WAREHOUSE_30_CASES])
def test_warehouse_query(tc):
    test_id = tc["id"]
    category = tc["category"]
    prompt = tc["prompt"]
    expected_sql = tc["expected_sql"]
    expected_kw = tc.get("expected_keywords", [])
    setup_turn = tc.get("setup_turn")

    session_id = f"test_session_{test_id}_{int(time.time())}"
    user_context = {"role_level": 0, "tenant_code": "68", "department_code": "68-1-01"}

    # Run setup turn if multi-turn test
    if setup_turn:
        warehouse_agent.run(setup_turn, session_id=session_id, user_context=user_context)

    t0 = time.perf_counter()
    result = warehouse_agent.run(prompt, session_id=session_id, user_context=user_context)
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    answer = result.get("answer") or ""
    sql = result.get("sql")
    stage = result.get("stage")
    query_res = result.get("query_result") or {}
    row_count = query_res.get("row_count", 0)

    # Assertions
    assert answer, f"Test {test_id} failed: answer is empty!"

    if expected_sql:
        # Warehouse queries MUST generate SQL and execute
        assert sql is not None, f"Test {test_id} failed: expected SQL to be generated but got None!"
        assert "<details>" in answer, f"Test {test_id} failed: answer should contain collapsible <details> SQL block!"
    else:
        # Capability / greeting queries MUST NOT generate SQL and MUST NOT contain <details> SQL
        assert sql is None, f"Test {test_id} failed: capability query should NOT generate SQL but got {sql}!"
        assert "<details>" not in answer, f"Test {test_id} failed: capability query should NOT contain SQL block!"

    # Check for expected keywords
    for kw in expected_kw:
        assert kw.lower() in answer.lower(), (
            f"Test {test_id} failed: keyword '{kw}' not found in answer:\n{answer}"
        )

    # Log structured record
    log_record = {
        "timestamp": datetime.now().isoformat() + "Z",
        "test_id": test_id,
        "category": category,
        "prompt": prompt,
        "executed_sql": sql,
        "row_count": row_count,
        "answer_preview": answer[:200],
        "latency_ms": elapsed_ms,
        "status": "PASSED",
    }
    log_test_result(log_record)


if __name__ == "__main__":
    print("=" * 80)
    print("CHẠY TRỰC TIẾP BỘ KIỂM THỬ 30 CÂU HỎI KHO DỮ LIỆU DWH (RUNNER)")
    print("=" * 80)
    passed = 0
    failed = 0
    results_summary = []

    for idx, tc in enumerate(WAREHOUSE_30_CASES, 1):
        print(f"[{idx}/30] Đang kiểm thử {tc['id']}: {tc['prompt'][:45]}...", end=" ", flush=True)
        try:
            test_warehouse_query(tc)
            print("✅ PASS")
            passed += 1
            results_summary.append((tc["id"], tc["category"], tc["prompt"], "PASS"))
        except Exception as e:
            print(f"❌ FAIL ({e})")
            failed += 1
            results_summary.append((tc["id"], tc["category"], tc["prompt"], f"FAIL: {e}"))

    print("\n" + "=" * 80)
    print(f"KẾT QUẢ TỔNG HỢP: {passed}/30 PASSED ({round(passed / 30 * 100, 1)}%), {failed} FAILED")
    print(f"Log đã được ghi nhận tại: {LOG_FILE}")
    print("=" * 80)
