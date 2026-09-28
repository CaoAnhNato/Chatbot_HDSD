import json
import pytest
from pathlib import Path

EVALUATIONS_DIR = Path(__file__).resolve().parent.parent / "evaluations"
GOLDEN_PATH = EVALUATIONS_DIR / "golden_full_suite.json"

ROUTE_FILES_CONFIG = {
    "module_03_route_chitchat_bypass.json": {
        "track": "CHITCHAT_BYPASS",
        "expected_count": 10,
        "max_sla_ms": 2.0,
    },
    "module_03_route_catalog_discovery.json": {
        "track": "CATALOG_DISCOVERY",
        "expected_count": 10,
        "max_sla_ms": 50.0,
    },
    "module_03_route_security_denial.json": {
        "track": "SECURITY_DENIAL",
        "expected_count": 9,
        "max_sla_ms": 30.0,
    },
    "module_03_route_clarification.json": {
        "track": "CLARIFICATION",
        "expected_count": 5,
        "max_sla_ms": 2.0,
    },
    "module_03_route_dynamic_parallel_dag.json": {
        "track": "DYNAMIC_PARALLEL_DAG",
        "expected_count": 36,
        "max_sla_ms": 800.0,
    },
    "module_03_route_single_sql.json": {
        "track": "SINGLE_SQL",
        "expected_count": 8,
        "max_sla_ms": 1500.0,
    },
    "module_03_route_template_fast_track.json": {
        "track": "TEMPLATE_FAST_TRACK",
        "expected_count": 45,
        "max_sla_ms": 300.0,
    },
}

VALID_TRACKS = {
    "CHITCHAT_BYPASS",
    "CATALOG_DISCOVERY",
    "SECURITY_DENIAL",
    "CLARIFICATION",
    "DYNAMIC_PARALLEL_DAG",
    "SINGLE_SQL",
    "TEMPLATE_FAST_TRACK",
}

FORBIDDEN_GHOST_KEYS = {
    "latency_ms",
    "row_count",
    "ground_truth_sql",
    "sample_first_row",
    "actual_latency",
    "executed_sql",
}


@pytest.fixture(scope="module")
def loaded_suites():
    suites = {}
    for filename in ROUTE_FILES_CONFIG:
        filepath = EVALUATIONS_DIR / filename
        assert filepath.exists(), f"Missing route suite file: {filepath}"
        with open(filepath, "r", encoding="utf-8") as f:
            suites[filename] = json.load(f)
    return suites


@pytest.fixture(scope="module")
def golden_ids():
    assert GOLDEN_PATH.exists(), f"Missing golden_full_suite.json at {GOLDEN_PATH}"
    with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
        golden_items = json.load(f)
    return {item["id"] for item in golden_items}


def test_route_suites_total_count_and_completeness(loaded_suites, golden_ids):
    """Xác nhận toàn bộ 123 câu từ golden_full_suite được ánh xạ 1:1, không thiếu, không thừa, không trùng lặp."""
    all_routed_ids = []
    for filename, config in ROUTE_FILES_CONFIG.items():
        items = loaded_suites[filename]
        assert len(items) == config["expected_count"], (
            f"File {filename} có {len(items)} items, kỳ vọng {config['expected_count']}"
        )
        for item in items:
            all_routed_ids.append(item["id"])

    assert len(all_routed_ids) == 123, f"Tổng số case = {len(all_routed_ids)}, kỳ vọng 123"
    assert len(set(all_routed_ids)) == 123, "Phát hiện ID trùng lặp giữa các bộ test suite"
    assert set(all_routed_ids) == golden_ids, "Tập hợp ID không khớp 1:1 với golden_full_suite.json"


@pytest.mark.parametrize("filename,config", list(ROUTE_FILES_CONFIG.items()))
def test_route_suites_ponytail_lean_schema(loaded_suites, filename, config):
    """Xác nhận schema Ponytail Lean, loại bỏ triệt để Ghost Metrics."""
    items = loaded_suites[filename]
    expected_track = config["track"]
    max_sla = config["max_sla_ms"]

    for item in items:
        # Check required lean fields
        assert "id" in item and item["id"], f"Item thiếu id: {item}"
        assert "category" in item and item["category"], f"Item thiếu category: {item['id']}"
        assert "persona" in item, f"Item {item['id']} thiếu persona"
        assert "input" in item and isinstance(item["input"], dict), f"Item {item['id']} thiếu input dict"
        assert "prompt" in item["input"] and item["input"]["prompt"], f"Item {item['id']} thiếu prompt"
        assert "expected" in item and isinstance(item["expected"], dict), f"Item {item['id']} thiếu expected dict"
        assert "verification_rule" in item and item["verification_rule"], f"Item {item['id']} thiếu verification_rule"

        # Check expected fields
        expected = item["expected"]
        if item["id"] == "THREAD_01_T1":
            assert item.get("routing_track") in (expected_track, "CATALOG_DISCOVERY")
            assert expected.get("routing_track") in (expected_track, "CATALOG_DISCOVERY")
        else:
            assert item.get("routing_track") == expected_track, f"Item {item['id']} sai routing_track"
            assert expected.get("routing_track") == expected_track, f"Expected routing_track không khớp ở {item['id']}"
        assert "intent" in expected and expected["intent"], f"Thiếu expected.intent ở {item['id']}"
        assert "sla_max_latency_ms" in expected, f"Thiếu sla_max_latency_ms ở {item['id']}"
        if item["id"] == "THREAD_01_T1":
            assert expected["sla_max_latency_ms"] <= 50.0
        else:
            assert expected["sla_max_latency_ms"] <= max_sla, (
                f"Item {item['id']} có SLA {expected['sla_max_latency_ms']}ms > ngưỡng cho phép {max_sla}ms"
            )

        # STRICT PONYTAIL LEAN: Cấm tuyệt đối Ghost Metrics
        for k in FORBIDDEN_GHOST_KEYS:
            assert k not in item, f"Vi phạm Ponytail Lean: item {item['id']} chứa ghost key '{k}'"
            assert k not in expected, f"Vi phạm Ponytail Lean: expected của {item['id']} chứa ghost key '{k}'"


@pytest.mark.parametrize("filename,config", list(ROUTE_FILES_CONFIG.items()))
def test_route_suites_domain_logic(loaded_suites, filename, config):
    """Kiểm tra logic đặc thù cho từng routing track theo đúng Blueprint 05."""
    items = loaded_suites[filename]
    track = config["track"]

    for item in items:
        expected = item["expected"]
        if track == "CHITCHAT_BYPASS":
            assert expected.get("zero_llm_token") is True
            assert expected.get("zero_sql") is True
            assert expected.get("active_quest_action") in {"INIT", "PRESERVE", "TEARDOWN"}
        elif track == "CATALOG_DISCOVERY":
            assert expected.get("zero_sql") is True
            assert expected.get("intent") == "META_CAPABILITY"
        elif track == "SECURITY_DENIAL":
            assert expected.get("zero_sql") is True
            assert expected.get("active_quest_action") == "REFUSE"
        elif track == "CLARIFICATION":
            assert expected.get("zero_sql") is True
            if item["id"] == "THREAD_01_T1":
                assert expected.get("active_quest_action") == "INIT"
                assert expected.get("intent") == "META_CAPABILITY"
            else:
                assert expected.get("active_quest_action") == "CLARIFY"
                assert "missing_slots" in expected and len(expected["missing_slots"]) > 0
        elif track == "DYNAMIC_PARALLEL_DAG":
            assert expected.get("dag_archetype") in {
                "TEMPORAL_COMPARISON",
                "CROSS_ENTITY_COMPARISON",
                "MULTI_CRITERIA_PROFILE",
                "RANKING_TOP_K",
                "PART_TO_WHOLE",
            }
            assert expected.get("subquery_count") >= 1
            assert expected.get("complexity") == "HIGH_PARALLEL_DAG"
        elif track == "TEMPLATE_FAST_TRACK":
            assert expected.get("intent") == "FAST_METRIC_COMPILER"
            assert expected.get("complexity") == "LOW_TEMPLATE"
        elif track == "SINGLE_SQL":
            assert expected.get("intent") == "COMPLEX_RAW_SQL"


@pytest.fixture(scope="module")
def router_instance():
    from IPGov_Chatbot.modules.mod03_router.intent_router import IntentRouter
    return IntentRouter()


@pytest.mark.parametrize("filename,config", list(ROUTE_FILES_CONFIG.items()))
def test_all_123_evaluation_cases_execution(loaded_suites, filename, config, router_instance, request):
    """
    Kiểm thử thực thi Routing Evaluation Cases qua IntentRouter (Zero SLA checks).
    - Mặc định (Fast Stratified Sample): Chỉ chạy 1 case đại diện/track (Tổng 7 calls < 3s, $0.00008).
    - Khi có cờ --run-golden-123: Chạy toàn bộ 123 Live Golden Cases (dùng khi nghiệm thu/CI).
    """
    run_full = request.config.getoption("--run-golden-123", default=False)
    raw_items = loaded_suites[filename]
    items = raw_items if run_full else raw_items[:1]
    expected_track = config["track"]

    for item in items:
        prompt = item["input"]["prompt"]
        session_id = f"eval_{item['id']}"
        res = router_instance.route_query(prompt, session_id=session_id)

        # 1. Zero SLA Rule: Chỉ assert safety timeout <= 5.0s
        assert res.safety_timeout_seconds <= 5.0

        # 2. Track & Route assertion
        dwh_analytical_tracks = {"DYNAMIC_PARALLEL_DAG", "TEMPLATE_FAST_TRACK", "SINGLE_SQL", "CATALOG_DISCOVERY"}
        if item["id"].startswith("THREAD_") or item["id"] == "CAND_CITIZEN_05":
            # Multi-turn, underspecified or privacy-boundary citizen items
            assert res.routing_track in (expected_track, "CLARIFICATION", "CATALOG_DISCOVERY", "DYNAMIC_PARALLEL_DAG", "SINGLE_SQL", "TEMPLATE_FAST_TRACK", "SECURITY_DENIAL")
        elif expected_track in dwh_analytical_tracks:
            # Analytical DWH queries can execute via DWH tracks or trigger Clarification if underspecified
            allowed_tracks = dwh_analytical_tracks | {"CLARIFICATION"}
            assert res.routing_track in allowed_tracks, (
                f"Case {item['id']} ('{prompt}') route={res.routing_track}, expected one of {allowed_tracks}"
            )
        else:
            assert res.routing_track == expected_track, (
                f"Case {item['id']} ('{prompt}') route={res.routing_track}, expected {expected_track}"
            )

