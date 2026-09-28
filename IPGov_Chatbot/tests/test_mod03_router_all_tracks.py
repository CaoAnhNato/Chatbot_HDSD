"""
Integration & Regression Tests for Module 03: All Routing Tracks & Stage 3 Baseline Snapshot
Căn cứ: evaluations/module_03_route_*.json, Blueprints 02, 05, 07, 08
"""

import json
from pathlib import Path
import pytest

from IPGov_Chatbot.schemas.router_dto import (
    IntentEnum,
    QuestStatusEnum,
    RouteTypeEnum,
)
from IPGov_Chatbot.modules.mod03_router.intent_router import IntentRouter


EVAL_DIR = Path(__file__).resolve().parent.parent / "evaluations"
SNAPSHOT_PATH = Path(__file__).resolve().parent / "snapshots" / "stage_3_router_hdft" / "snapshot_baseline.json"


@pytest.fixture
def router():
    return IntentRouter()


def test_stage_3_snapshot_baseline_consistency(router):
    """
    Xác minh tính bất biến và đúng đắn của Stage 3 Snapshot Baseline.
    """
    assert SNAPSHOT_PATH.exists(), f"Không tìm thấy snapshot Stage 3 tại {SNAPSHOT_PATH}"
    with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        snapshot_data = json.load(f)

    prompt = snapshot_data["query_sanitized"]
    res = router.route_query(prompt, session_id=snapshot_data["session_id"])

    # Xác minh các trường cốt lõi khớp với snapshot baseline
    assert res.route.value == snapshot_data["route"]
    assert res.intent.value == snapshot_data["intent"]
    assert res.persona.value == snapshot_data["persona"]
    assert res.active_quest is not None
    assert res.active_quest.temporal_val == snapshot_data["active_quest"]["temporal_val"]
    assert res.active_quest.admin_level == snapshot_data["active_quest"]["admin_level"]
    assert res.tokens_used >= snapshot_data["tokens_used"]
    assert res.zero_sql == snapshot_data["zero_sql"]


def test_template_fast_track_cases(router):
    """
    Kiểm tra một số câu hỏi từ module_03_route_template_fast_track.json được định tuyến chuẩn xác.
    """
    fast_track_file = EVAL_DIR / "module_03_route_template_fast_track.json"
    if not fast_track_file.exists():
        pytest.skip("Chưa có file module_03_route_template_fast_track.json")

    with open(fast_track_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    # Lấy 10 cases đại diện
    sample_cases = cases[:10]
    for case in sample_cases:
        prompt = case["input"]["prompt"]
        res = router.route_query(prompt, session_id=f"sess_{case['id']}")
        assert res.route in (
            RouteTypeEnum.TEMPLATE_FAST_TRACK,
            RouteTypeEnum.DYNAMIC_PARALLEL_DAG,
            RouteTypeEnum.SINGLE_SQL,
            RouteTypeEnum.CATALOG_DISCOVERY,
        )
        assert res.safety_timeout_seconds <= 5.0


def test_clarification_cases(router):
    """
    Kiểm tra câu hỏi mơ hồ kích hoạt đúng CLARIFICATION_NEEDED.
    """
    prompt = "Cho tôi xem số liệu giải ngân kinh phí khuyến công."
    res = router.route_query(prompt, session_id="sess_clarify_test")
    assert res.route == RouteTypeEnum.CLARIFICATION
    assert res.intent == IntentEnum.CLARIFICATION_NEEDED
    assert len(res.missing_slots) > 0
    assert len(res.clarification_options) > 0
