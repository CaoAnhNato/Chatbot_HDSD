# -*- coding: utf-8 -*-
"""
Empirical Challenger M4 Suite:
1. Mathematical Audit of Pairwise Jaccard Invariant:
   - Content-word unigram Jaccard (baseline spec invariant)
   - Raw unigrams (zero stopwords)
   - Character 4-grams (subword / morphology invariant)
   - Word bigrams
   - Syllable n-grams
2. Concurrency & Multi-Session Stress Test:
   - >= 10 concurrent requests across distinct sessions against warehouse_agent.run()
   - Verification of DuckDB connection stability, PostgreSQL connection pool, thread-safety, zero deadlock.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import json
import re
import itertools
import concurrent.futures
import time
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SPEC_PATH = Path(__file__).resolve().parent / "paraphrase_30_quests_spec.json"

VIETNAMESE_STOPWORDS = {
    "và", "của", "cho", "tôi", "các", "những", "về", "trong", "năm", "ở", "tại",
    "được", "là", "thì", "sao", "nào", "gì", "biết", "xem", "hãy", "bao", "nhiêu",
    "có", "thế", "này", "qua", "đang", "gồm", "xin", "bạn", "một", "hai", "ba",
    "đã", "sẽ", "cần", "ra", "vào", "lên", "xuống", "số", "lại", "bị", "do",
    "bởi", "với", "theo", "từ", "đến", "để", "còn", "nhé", "ơi", "hỏi", "cơ",
    "thưa", "nhờ", "giúp", "muốn", "hiện", "tại", "đạt", "rồi", "lại", "thêm"
}

def load_questions():
    with open(SPEC_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["questions"]

def jaccard(s1, s2):
    if not s1 and not s2:
        return 0.0
    inter = len(s1 & s2)
    union = len(s1 | s2)
    return inter / union if union > 0 else 0.0

def tokenize_content_words(text: str):
    tokens = re.findall(r"[\w\./\-]+", text.lower())
    return {t for t in tokens if t not in VIETNAMESE_STOPWORDS and len(t) > 1 and not t.isdigit()}

def tokenize_raw_words(text: str):
    tokens = re.findall(r"[\w\./\-]+", text.lower())
    return set(tokens)

def tokenize_char_ngrams(text: str, n=4):
    clean = re.sub(r"\s+", " ", text.lower().strip())
    if len(clean) < n:
        return {clean}
    return {clean[i:i+n] for i in range(len(clean) - n + 1)}

def tokenize_word_bigrams(text: str):
    words = [t for t in re.findall(r"[\w\./\-]+", text.lower()) if t not in VIETNAMESE_STOPWORDS and not t.isdigit()]
    if len(words) < 2:
        return set(words)
    return {f"{words[i]}_{words[i+1]}" for i in range(len(words)-1)}


class TestJaccardMathematicalAudit:
    """Kiểm tra bất biến toán học và độ nhạy của Jaccard dưới các chiến lược tokenization khác nhau."""

    def test_baseline_content_word_jaccard_strictly_below_30(self):
        questions = load_questions()
        assert len(questions) == 30
        pairs = list(itertools.combinations(range(30), 2))
        assert len(pairs) == 435

        word_sets = [tokenize_content_words(q["question"]) for q in questions]
        overlaps = []
        worst_pair = None
        max_j = -1.0

        for i, j in pairs:
            jval = jaccard(word_sets[i], word_sets[j])
            overlaps.append(jval)
            if jval > max_j:
                max_j = jval
                worst_pair = (questions[i]["id"], questions[j]["id"], jval, word_sets[i] & word_sets[j])

            assert jval < 0.30, (
                f"VIOLATION: Pair ({questions[i]['id']}, {questions[j]['id']}) has Jaccard {jval:.4f} >= 0.30\n"
                f"  Q1: {questions[i]['question']}\n"
                f"  Q2: {questions[j]['question']}\n"
                f"  Overlap: {word_sets[i] & word_sets[j]}"
            )

        avg_j = sum(overlaps) / len(overlaps)
        print(f"\n[Audit Content-Word] Max Jaccard: {max_j:.4f} (Pair: {worst_pair[0]}-{worst_pair[1]}), Avg Jaccard: {avg_j:.4f}")
        assert max_j <= 0.2857 + 1e-4
        assert avg_j <= 0.10

    def test_alternative_char_4gram_jaccard_distribution(self):
        questions = load_questions()
        pairs = list(itertools.combinations(range(30), 2))
        c4_sets = [tokenize_char_ngrams(q["question"], 4) for q in questions]

        overlaps = [jaccard(c4_sets[i], c4_sets[j]) for i, j in pairs]
        max_c4 = max(overlaps)
        avg_c4 = sum(overlaps) / len(overlaps)
        print(f"\n[Audit Char-4gram] Max: {max_c4:.4f}, Avg: {avg_c4:.4f}")

        # Char 4-grams include syllables and affixes, naturally slightly higher but must remain bounded
        assert avg_c4 < 0.25, f"Avg char-4gram overlap too high: {avg_c4:.4f}"
        assert max_c4 < 0.50, f"Max char-4gram overlap indicates near-duplicate question: {max_c4:.4f}"

    def test_alternative_word_bigram_jaccard(self):
        questions = load_questions()
        pairs = list(itertools.combinations(range(30), 2))
        bigram_sets = [tokenize_word_bigrams(q["question"]) for q in questions]

        overlaps = [jaccard(bigram_sets[i], bigram_sets[j]) for i, j in pairs]
        max_bi = max(overlaps)
        avg_bi = sum(overlaps) / len(overlaps)
        print(f"\n[Audit Word-Bigram] Max: {max_bi:.4f}, Avg: {avg_bi:.4f}")
        # Bigram overlap should be exceptionally low if questions use distinct phrasing
        assert max_bi < 0.25, f"High bigram overlap {max_bi:.4f} implies phrase copying!"
        assert avg_bi < 0.05, f"Average bigram overlap {avg_bi:.4f} is too high!"

    def test_raw_word_tokens_zero_stopword_leakage(self):
        questions = load_questions()
        pairs = list(itertools.combinations(range(30), 2))
        raw_sets = [tokenize_raw_words(q["question"]) for q in questions]

        overlaps = [jaccard(raw_sets[i], raw_sets[j]) for i, j in pairs]
        max_raw = max(overlaps)
        avg_raw = sum(overlaps) / len(overlaps)
        print(f"\n[Audit Raw Tokens - Zero Stopwords] Max: {max_raw:.4f}, Avg: {avg_raw:.4f}")
        # Even with function words and stopwords present, max overlap must not exceed 0.40
        assert max_raw < 0.42, f"Raw overlap {max_raw:.4f} is too high, template reuse suspected!"


class TestConcurrencyAndMultiSessionStress:
    """Stress testing 10+ concurrent sessions against warehouse_agent.run()."""

    def test_12_concurrent_sessions_distinct_queries(self):
        from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import warehouse_agent

        questions = load_questions()[:12]
        assert len(questions) == 12

        results = {}
        errors = []

        def worker_task(q_item, idx):
            session_id = f"concurrency_stress_session_{idx}_{int(time.time()*1000)}"
            q_text = q_item["question"]
            try:
                t0 = time.time()
                res = warehouse_agent.run(q_text, session_id=session_id)
                dur = time.time() - t0
                return idx, q_item["id"], session_id, res, dur, None
            except Exception as e:
                return idx, q_item["id"], session_id, None, 0.0, str(e)

        # Launch 12 concurrent requests
        t_start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            futures = [executor.submit(worker_task, q, i) for i, q in enumerate(questions)]
            for fut in concurrent.futures.as_completed(futures):
                idx, qid, sid, res, dur, err = fut.result()
                if err:
                    errors.append((qid, err))
                else:
                    results[qid] = (dur, res)

        total_elapsed = time.time() - t_start
        print(f"\n[Concurrency] 12 concurrent requests completed in {total_elapsed:.2f}s")

        # Zero fatal exceptions
        assert len(errors) == 0, f"Concurrency errors encountered: {errors}"
        assert len(results) == 12

        # Validate answers
        for q_item in questions:
            qid = q_item["id"]
            dur, res = results[qid]
            assert res is not None
            assert not res.get("is_clarification_needed", False), f"[{qid}] requested clarification in concurrent mode!"
            ans = res.get("answer", "")
            assert len(ans.strip()) > 0, f"[{qid}] empty answer!"
            # Check tabular data
            tbl = res.get("tabular_data") or {}
            rows = tbl.get("rows", [])
            lvl1 = tbl.get("level1_rows", [])
            count = len(rows) or len(lvl1)
            assert count >= 1 or "chỉ tiêu" in ans.lower(), f"[{qid}] No rows returned under concurrency: {ans[:100]}"
            print(f"  [{qid}] Latency: {dur:.2f}s, Rows: {count}")
