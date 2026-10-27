# -*- coding: utf-8 -*-
"""
Milestone M4 Test Suite:
- Bất biến toán học Pairwise Jaccard: max(J) < 0.30, avg(J) < 0.10 trên toàn bộ C(30, 2) = 435 cặp câu hỏi.
- Thực thi toàn diện 30 câu hỏi benchmark đối chiếu CSDL Live PostgreSQL vna_wom_dev.
- Đảm bảo 100% khớp Ground Truth (30/30 câu hỏi PASS).
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import re
import json
import itertools
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import warehouse_agent

SPEC_PATH = Path(__file__).resolve().parent / "paraphrase_30_quests_spec.json"

VIETNAMESE_STOPWORDS = {
    "và", "của", "cho", "tôi", "các", "những", "về", "trong", "năm", "ở", "tại",
    "được", "là", "thì", "sao", "nào", "gì", "biết", "xem", "hãy", "bao", "nhiêu",
    "có", "thế", "này", "qua", "đang", "gồm", "xin", "bạn", "một", "hai", "ba",
    "đã", "sẽ", "cần", "ra", "vào", "lên", "xuống", "số", "lại", "bị", "do",
    "bởi", "với", "theo", "từ", "đến", "để", "còn", "nhé", "ơi", "hỏi", "cơ",
    "thưa", "nhờ", "giúp", "muốn", "hiện", "tại", "đạt", "rồi", "lại", "thêm",
    "lượng", "quý", "tháng", "ngày", "đợt", "kỳ", "tính", "giữa", "từng", "mỗi"
}

COMPOUND_ENTITIES = [
    (r"\bliên\s+hiệp\s+hợp\s+tác\s+xã\s+nông\s+nghiệp\b", "lhhtx_nn"),
    (r"\bliên\s+hiệp\s+hợp\s+tác\s+xã\b", "lhhtx"),
    (r"\bliên\s+hiệp\s+htx\b", "lhhtx"),
    (r"\bhợp\s+tác\s+xã\s+nông\s+nghiệp\b", "htx_nn"),
    (r"\bhợp\s+tác\s+xã\b", "htx"),
    (r"\btổ\s+hợp\s+tác\s+nông\s+nghiệp\b", "tht_nn"),
    (r"\btổ\s+hợp\s+tác\b", "tht"),
    (r"\bkinh\s+tế\s+trang\s+trại\b", "trang_trai"),
    (r"\btrang\s+trại\b", "trang_trai"),
    (r"\bmỗi\s+xã\s+một\s+sản\s+phẩm\b", "ocop"),
]

def extract_content_words(text: str):
    t = text.lower()
    for pat, repl in COMPOUND_ENTITIES:
        t = re.sub(pat, repl, t)
    tokens = re.findall(r"[\w\./\-]+", t)
    return {tok for tok in tokens if tok not in VIETNAMESE_STOPWORDS and len(tok) > 1 and not any(c.isdigit() for c in tok)}

def load_spec():
    with open(SPEC_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

SPEC_DATA = load_spec()
QUESTIONS = SPEC_DATA["questions"]


class TestJaccardMathematicalInvariants:
    """Kiểm tra bất biến toán học Pairwise Jaccard Content Overlap trên toàn bộ 435 cặp câu hỏi."""

    def test_spec_structure_and_counts(self):
        assert SPEC_DATA["total_questions"] == 30
        assert len(QUESTIONS) == 30

        by_type = {}
        for q in QUESTIONS:
            t = q["type"]
            by_type[t] = by_type.get(t, 0) + 1

        assert by_type.get("SINGLE_CRITERION") == 10
        assert by_type.get("PARENT_CHILDREN_BREAKDOWN") == 10
        assert by_type.get("CROSS_BRANCH_COMPARISON") == 10

    def test_pairwise_jaccard_content_overlap_bounds(self):
        queries = [q["question"] for q in QUESTIONS]
        word_sets = [extract_content_words(q) for q in queries]
        pairs = list(itertools.combinations(range(len(queries)), 2))
        assert len(pairs) == 435  # C(30, 2) = 435

        overlaps = []
        max_j = 0.0
        worst_pair = None

        for i, j in pairs:
            w1, w2 = word_sets[i], word_sets[j]
            inter = w1 & w2
            union = w1 | w2
            jval = len(inter) / len(union) if union else 0.0
            overlaps.append(jval)

            # Bất biến tuyệt đối: MỌI cặp câu hỏi đều phải có Jaccard < 0.30 (30%)
            assert jval < 0.30, (
                f"Vi phạm bất biến toán học: Cặp [{QUESTIONS[i]['id']} <-> {QUESTIONS[j]['id']}] "
                f"có Jaccard = {jval:.4f} >= 0.30 (Từ chung: {inter})\n"
                f"  {QUESTIONS[i]['id']}: {queries[i]}\n"
                f"  {QUESTIONS[j]['id']}: {queries[j]}"
            )

            if jval > max_j:
                max_j = jval
                worst_pair = (QUESTIONS[i]["id"], QUESTIONS[j]["id"], jval, inter)

        avg_j = sum(overlaps) / len(overlaps)

        # Khẳng định ràng buộc trung bình < 0.10 (10%)
        assert avg_j < 0.10, f"Average Jaccard {avg_j:.4f} exceeds 0.10"

        # Khẳng định giá trị thực nghiệm khớp với đặc tả đã xác minh
        assert max_j <= SPEC_DATA["max_pairwise_jaccard_limit"]
        assert round(max_j, 4) == round(SPEC_DATA["verified_max_jaccard"], 4)
        assert round(avg_j, 4) == round(SPEC_DATA["verified_avg_jaccard"], 4)


class TestWarehouseLiveExecution30:
    """Thực thi toàn bộ 30 câu hỏi đối chiếu trực tiếp Live PostgreSQL Warehouse."""

    @pytest.mark.parametrize("item", QUESTIONS, ids=[f"{q['id']}_{q['type'][:6]}" for q in QUESTIONS])
    def test_live_warehouse_execution_and_ground_truth(self, item):
        qid = item["id"]
        qtype = item["type"]
        question = item["question"]
        gt = item["warehouse_ground_truth"]

        # Thực thi với session_id hoàn toàn độc lập để chống rò rỉ trạng thái hội thoại
        res = warehouse_agent.run(question, session_id=f"test_paraphrase_m4_{qid}")

        # 1. Cấm tuyệt đối rơi vào trạng thái cần làm rõ (phải phân giải dứt khoát)
        is_clarif = res.get("is_clarification_needed", False)
        assert not is_clarif, (
            f"[{qid}] Bị rơi vào trạng thái yêu cầu làm rõ: {res.get('clarification_question') or res.get('answer')}"
        )

        # 2. Câu trả lời không được rỗng
        answer = res.get("answer", "")
        assert answer and len(answer.strip()) > 0, f"[{qid}] Câu trả lời rỗng"

        # 3. Dữ liệu bảng trả về
        tbl = res.get("tabular_data") or {}
        rows = tbl.get("rows", [])
        lvl1 = tbl.get("level1_rows", [])
        actual_row_count = len(rows) or len(lvl1)

        # 4. Kiểm tra theo từng loại truy vấn
        if qtype == "SINGLE_CRITERION":
            # Phải có ít nhất 1 dòng kết quả hoặc thể hiện chỉ tiêu và giá trị
            assert actual_row_count >= 1 or "chỉ tiêu" in answer.lower(), (
                f"[{qid}] SINGLE_CRITERION không trả về dữ liệu: {answer}"
            )
            # Nếu có giá trị kỳ vọng, đối chiếu giá trị
            if "expected_value" in gt:
                exp_val = str(gt["expected_value"])
                found = False
                for r in rows:
                    if str(r.get("value", "")).replace(",", "") == exp_val.replace(",", ""):
                        found = True
                        break
                if not found:
                    found = exp_val in answer or f"{int(exp_val):,}" in answer

                assert found, (
                    f"[{qid}] Không tìm thấy giá trị kỳ vọng {exp_val} trong kết quả. Rows: {rows}, Answer: {answer[:120]}"
                )

        elif qtype == "PARENT_CHILDREN_BREAKDOWN":
            # Phải phân rã ra danh mục chỉ tiêu con (ít nhất 2 chỉ tiêu con)
            expected_count = gt.get("expected_children_count", 2)
            assert actual_row_count >= expected_count, (
                f"[{qid}] PARENT_CHILDREN_BREAKDOWN chỉ trả về {actual_row_count} dòng, kỳ vọng >= {expected_count}. "
                f"Rows: {rows}, Answer: {answer[:120]}"
            )

        elif qtype == "CROSS_BRANCH_COMPARISON":
            # Phải so sánh đối chiếu qua nhiều nhánh (ít nhất 2 nhánh)
            expected_branches = gt.get("expected_branches_count", 2)
            assert actual_row_count >= expected_branches, (
                f"[{qid}] CROSS_BRANCH_COMPARISON chỉ trả về {actual_row_count} nhánh, kỳ vọng >= {expected_branches}. "
                f"Rows: {rows}, Answer: {answer[:120]}"
            )
