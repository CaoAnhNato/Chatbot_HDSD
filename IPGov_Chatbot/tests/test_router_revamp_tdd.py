"""
TDD Tests for Module 03 Router Revamp (Phase 1: DTO Contract & Enums)
"""
import pytest
from IPGov_Chatbot.schemas.router_dto import (
    RouterOutputDTO,
    RouteTypeEnum,
    IntentEnum,
    PersonaEnum,
    QuestActionEnum,
    QuestStatusEnum,
)

def test_router_dto_has_revamp_fields():
    dto = RouterOutputDTO(
        session_id="test_session",
        query_sanitized="test query",
        route=RouteTypeEnum.DYNAMIC_PARALLEL_DAG,
        intent=IntentEnum.COMPLEX_DAG_ANALYTICS,
        persona=PersonaEnum.SPECIALIST,
        active_quest_action=QuestActionEnum.INIT,
        dag_archetype="TEMPORAL_COMPARISON",
        subquery_count=2,
        complexity="HIGH_PARALLEL_DAG",
        safety_timeout_seconds=5.0,
    )
    assert dto.dag_archetype == "TEMPORAL_COMPARISON"
    assert dto.subquery_count == 2
    assert dto.complexity == "HIGH_PARALLEL_DAG"
    assert dto.safety_timeout_seconds == 5.0
    assert dto.action == "INIT"

def test_quest_action_enum_has_refuse():
    assert hasattr(QuestActionEnum, "REFUSE")
    assert QuestActionEnum.REFUSE.value == "REFUSE"

def test_intent_enum_has_security_denial():
    assert hasattr(IntentEnum, "SECURITY_DENIAL")
    assert IntentEnum.SECURITY_DENIAL.value == "SECURITY_DENIAL"

def test_semantic_strategy_interface():
    from IPGov_Chatbot.modules.mod03_router.semantic_strategy_interface import (
        SemanticRouterStrategy,
        SemanticMatchResult,
    )
    res = SemanticMatchResult(
        confidence_score=0.9,
        matched_track=RouteTypeEnum.CATALOG_DISCOVERY,
        intent=IntentEnum.META_CAPABILITY,
        extracted_slots={"scope": "kinh_te"},
        dag_archetype=None,
        subquery_count=None,
        complexity=None,
    )
    assert res.confidence_score == 0.9
    assert res.matched_track == RouteTypeEnum.CATALOG_DISCOVERY

    class DummyStrategy(SemanticRouterStrategy):
        def evaluate(self, text: str, context=None):
            return res

    strat = DummyStrategy()
    assert strat.evaluate("hello").matched_track == RouteTypeEnum.CATALOG_DISCOVERY

def test_dag_archetype_detector():
    from IPGov_Chatbot.modules.mod03_router.dag_archetype_detector import DAGArchetypeDetector
    detector = DAGArchetypeDetector()
    
    # 1. TEMPORAL_COMPARISON
    res1 = detector.detect("So sánh số vụ tai nạn lao động năm 2025 và 2026 tăng hay giảm bao nhiêu %?")
    assert res1 is not None
    assert res1.archetype == "TEMPORAL_COMPARISON"
    assert res1.subquery_count == 2
    
    # 2. CROSS_ENTITY_COMPARISON
    res2 = detector.detect("So sánh tỷ lệ trạm y tế đạt chuẩn giữa Huyện Đam Rông và Huyện Lâm Hà năm 2025?")
    assert res2 is not None
    assert res2.archetype == "CROSS_ENTITY_COMPARISON"
    assert res2.subquery_count == 2
    
    # 3. RANKING_TOP_K
    res3 = detector.detect("Top 3 huyện có tỷ lệ giải ngân kinh phí khuyến công cao nhất năm 2025?")
    assert res3 is not None
    assert res3.archetype == "RANKING_TOP_K"
    assert res3.subquery_count == 1
    
    # 4. PART_TO_WHOLE
    res4 = detector.detect("Kinh phí khuyến công địa phương chiếm tỷ trọng bao nhiêu % trong tổng kinh phí 2025?")
    assert res4 is not None
    assert res4.archetype == "PART_TO_WHOLE"
    assert res4.subquery_count == 2
    
    # 5. MULTI_CRITERIA_PROFILE
    res5 = detector.detect("Thống kê chi tiết diễn biến số vụ tai nạn lao động và số người chết qua 12 tháng năm 2025?")
    assert res5 is not None
    assert res5.archetype == "MULTI_CRITERIA_PROFILE"
    assert res5.subquery_count >= 2

def test_sql_complexity_classifier():
    from IPGov_Chatbot.modules.mod03_router.sql_complexity_classifier import SQLComplexityClassifier
    classifier = SQLComplexityClassifier()
    
    # Ad-hoc audit query -> SINGLE_SQL, MEDIUM_SINGLE_SQL
    is_adhoc, comp, intent = classifier.classify_ad_hoc("ds ubnd xa ld 2026 bc appr nhung value chi tieu lao dong bi null hoac rong")
    assert is_adhoc is True
    assert comp == "MEDIUM_SINGLE_SQL"
    assert intent == IntentEnum.COMPLEX_RAW_SQL
    
    # Normal query is not ad-hoc
    is_adhoc2, _, _ = classifier.classify_ad_hoc("Số vụ tai nạn lao động năm 2025 toàn tỉnh là bao nhiêu?")
    assert is_adhoc2 is False

def test_duckdb_fuzzy_strategy():
    from IPGov_Chatbot.modules.mod03_router.duckdb_fuzzy_strategy import DuckDBFuzzyStrategy
    strat = DuckDBFuzzyStrategy()
    
    # 1. Exact match entity and metric
    res = strat.evaluate("Số vụ tai nạn lao động năm 2025 tại Huyện Đam Rông là bao nhiêu?")
    assert res.extracted_slots.get("admin_entity") == "Huyện Đam Rông"
    assert res.extracted_slots.get("temporal_val") == "2025"
    assert "tai nạn lao động" in res.extracted_slots.get("metric_name", "").lower()
    
    # 2. Fuzzy match typo/abbreviation: "ldtbxh" -> "Sở LĐTBXH"
    res_fuzzy = strat.evaluate("biểu mẫu an toàn lao động phòng ldtbxh năm 2025")
    assert "lđtbxh" in res_fuzzy.extracted_slots.get("admin_entity", "").lower()
    
    # 3. Detect ambiguous query missing temporal / scope
    res_ambig = strat.evaluate("Cho tôi xem số liệu giải ngân kinh phí khuyến công.")
    assert len(res_ambig.candidate_options) >= 2
    assert res_ambig.confidence_score < 0.85

def test_dense_prototype_strategy():
    from IPGov_Chatbot.modules.mod03_router.dense_prototype_strategy import DensePrototypeStrategy
    dense_strat = DensePrototypeStrategy()
    
    # 1. Catalog discovery prototype match
    res_disc = dense_strat.evaluate("Trợ lý ảo này có những tính năng và tiện ích gì?")
    assert res_disc.matched_track == RouteTypeEnum.CATALOG_DISCOVERY
    assert res_disc.intent == IntentEnum.META_CAPABILITY
    assert res_disc.confidence_score > 0.6
    
    # 2. DAG archetype prototype match
    res_dag = dense_strat.evaluate("So sánh biến động tăng giảm giữa năm 2024 và 2025?")
    assert res_dag.matched_track == RouteTypeEnum.DYNAMIC_PARALLEL_DAG
    assert res_dag.intent == IntentEnum.COMPLEX_DAG_ANALYTICS
    assert res_dag.confidence_score > 0.4

def test_decouple_greeting_and_business():
    from IPGov_Chatbot.modules.mod03_router.chitchat_bypass import ChitchatBypassEngine
    engine = ChitchatBypassEngine()
    
    # 1. Pure greeting -> is_chitchat is True
    assert engine.is_chitchat("Kính chào trợ lý ảo, chúc một ngày làm việc hiệu quả!") is True
    
    # 2. Compound greeting + business -> is_chitchat is False!
    prompt = "Kính chào trợ lý, cho tôi hỏi số vụ tai nạn lao động năm 2025 là bao nhiêu?"
    assert engine.is_chitchat(prompt) is False
    
    has_g, g_part, biz_payload = engine.decouple_greeting_and_business(prompt)
    assert has_g is True
    assert "số vụ tai nạn lao động" in biz_payload.lower()

def test_intent_router_7_tracks():
    from IPGov_Chatbot.modules.mod03_router.intent_router import IntentRouter
    router = IntentRouter()
    
    # 1. SECURITY_DENIAL
    res_sec = router.route_query("Sản lượng khai thác dầu khí tại Lâm Đồng?")
    assert res_sec.route == RouteTypeEnum.SECURITY_DENIAL
    assert res_sec.intent == IntentEnum.SECURITY_DENIAL
    assert res_sec.action == "REFUSE"
    
    # 2. CHITCHAT_BYPASS
    res_chit = router.route_query("Kính chào trợ lý ảo, chúc một ngày làm việc tốt lành!")
    assert res_chit.route == RouteTypeEnum.CHITCHAT_BYPASS
    assert res_chit.zero_sql is True
    
    # 3. CATALOG_DISCOVERY
    res_disc = router.route_query("Hệ thống này có chức năng gì ?")
    assert res_disc.route == RouteTypeEnum.CATALOG_DISCOVERY
    assert res_disc.intent == IntentEnum.META_CAPABILITY
    
    # 4. CLARIFICATION
    res_clar = router.route_query("Cho tôi xem số liệu giải ngân kinh phí khuyến công.")
    assert res_clar.route == RouteTypeEnum.CLARIFICATION
    assert res_clar.intent == IntentEnum.CLARIFICATION_NEEDED
    assert len(res_clar.missing_slots) > 0
    
    # 5. DYNAMIC_PARALLEL_DAG
    res_dag = router.route_query("So sánh tai nạn lao động 2025 và 2026?")
    assert res_dag.route == RouteTypeEnum.DYNAMIC_PARALLEL_DAG
    assert res_dag.dag_archetype == "TEMPORAL_COMPARISON"
    assert res_dag.complexity == "HIGH_PARALLEL_DAG"
    
    # 6. SINGLE_SQL
    res_sql = router.route_query("ds ubnd xa ld 2026 bc appr nhung value chi tieu lao dong bi null hoac rong")
    assert res_sql.route == RouteTypeEnum.SINGLE_SQL
    assert res_sql.intent == IntentEnum.COMPLEX_RAW_SQL
    assert res_sql.complexity == "MEDIUM_SINGLE_SQL"
    
    # 7. TEMPLATE_FAST_TRACK
    res_fast = router.route_query("Số vụ tai nạn lao động năm 2025 toàn tỉnh là bao nhiêu?")
    assert res_fast.route == RouteTypeEnum.TEMPLATE_FAST_TRACK
    assert res_fast.intent == IntentEnum.FAST_METRIC_COMPILER
    assert res_fast.complexity == "LOW_TEMPLATE"
