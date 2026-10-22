import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import WarehouseLangGraphAgent
from IPGov_Chatbot.modules.mod03_router.intent_router import IntentRouter

agent = WarehouseLangGraphAgent()
router = IntentRouter()

test_queries = [
    "Dữ liệu cải cách 1 đang do tỉnh nào thực hiện?",
    "3 mũ 2 là nhiều?",
    "Tính giúp tôi căn bậc hai của 144 bằng bao nhiêu?",
    "100 cộng 250 nhân 2 bằng mấy?",
    "Tỉnh nào có sản lượng muối trên 20.000 tấn trong báo cáo đã duyệt?"
]

print("\n=== TESTING INTENT ROUTER ===")
for q in test_queries:
    res = router.route_query(q)
    print(f"Query: '{q}'\n  -> Route: {res.routing_track} | Intent: {res.intent} | Msg: {res.bypass_response[:80] if res.bypass_response else 'No bypass'}\n")

print("\n=== TESTING WAREHOUSE LANGGRAPH AGENT ===")
for q in test_queries:
    res = agent.run(q)
    ans = res.get("final_answer", "")
    sql = res.get("sql_query", "")
    has_dump_34 = "dwh_internal.province" in (sql or "") and "cải cách 1" not in ans
    is_fake_fact = "Chỉ tiêu **3 mũ 2" in ans or "3 mũ 2" in (sql or "")
    print(f"Query: '{q}'")
    print(f"  Stage: {res.get('current_stage')} | Out of scope: {res.get('is_out_of_scope')}")
    print(f"  Dump 34 province bug: {has_dump_34} | Fake metric bug: {is_fake_fact}")
    print(f"  Answer preview: {ans[:120]}...\n")


