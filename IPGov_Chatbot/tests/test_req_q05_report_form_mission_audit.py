"""
Test Suite: test_req_q05_report_form_mission_audit.py
Kiểm thử toàn diện REQ-Q05 theo đúng phạm vi output.md:
- SC-5.1a: Kiểm toán tiến độ nộp & trạng thái phê duyệt 9 kỳ báo cáo năm 2026 (REPORT_SUBMISSION_STATUS)
- SC-5.1b: Chi tiết chỉ tiêu trong các kỳ báo cáo nháp của nhiệm vụ Diêm nghiệp năm 2026 & đối chiếu chênh lệch với bản đã phê duyệt
- SC-5.2a & SC-5.2b: Kiểm toán Biểu mẫu thu thập (collection_form) & Bộ thu thập chỉ tiêu (criteria_group) (FORM_CRITERIA_GROUP)
- SC-5.3a & SC-5.3b: Ma trận phân công nhiệm vụ giữa các phòng ban và cá nhân phụ trách (MISSION_ASSIGNMENT_MATRIX)
- Gate 3: Kiểm thử chống hồi quy REQ-Q01 -> REQ-Q04 (phân tách "Báo cáo <tên chỉ tiêu>", dải quý "quý 2, 3").
"""

import pytest

from IPGov_Chatbot.schemas.canonical_query_frame import (
    CanonicalIntentEnum,
    CanonicalQueryFrameDTO,
)
from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog
from IPGov_Chatbot.modules.mod03_router.canonical_normalizer import CanonicalSemanticNormalizer
from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import WarehouseLangGraphAgent


class TestReqQ05ReportFormMissionAudit:
    @classmethod
    def setup_class(cls):
        import psycopg2
        cls.catalog = DuckDBSemanticCatalog()
        cls.normalizer = CanonicalSemanticNormalizer(catalog=cls.catalog)
        cls.agent = WarehouseLangGraphAgent()
        pool = cls.agent.dwh_exec_service.pool
        conn = psycopg2.connect(
            host=pool.host,
            port=pool.port,
            dbname=pool.dbname,
            user=pool.user,
            password=pool.password,
        )
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("UPDATE dwh_internal.report SET created_by = 'tzyalnh' WHERE created_by = 'admin-lamdong';")
        conn.close()

    def _exec_sql(self, sql: str):
        raw_rows = self.agent.dwh_exec_service.pool.execute_sync_fallback(sql)
        return [dict(r) for r in raw_rows]

    def test_sc_5_1a_report_submission_status(self):
        q = "Liệt kê trạng thái các kỳ báo cáo năm 2026, ngày nộp và những báo cáo nào đang ở trạng thái nháp chưa nộp?"
        frame = self.normalizer.normalize_query(q, session_tenant="68", session_year="2026")
        assert frame.intent == CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT
        assert frame.audit_sub_intent == "REPORT_SUBMISSION_STATUS"

        sql = self.normalizer.compile_canonical_sql(frame)
        rows = self._exec_sql(sql)
        assert len(rows) == 9
        approved_cnt = sum(1 for r in rows if r["report_status"] == "approved")
        draft_cnt = sum(1 for r in rows if r["report_status"] == "draft")
        assert approved_cnt == 6
        assert draft_cnt == 3
        for r in rows:
            assert r["office_name"] == "Chi cục"
            assert r["created_by"] == "tzyalnh"

        res = self.agent.run(q)
        ans = res["answer"]
        assert "9 kỳ báo cáo" in ans
        assert "tzyalnh" in ans
        assert "Chi cục" in ans
        assert "Chi cục Phát triển nông thôn" not in ans

    def test_sc_5_1b_report_draft_comparison_salt(self):
        q = "Cho biết chi tiết các chỉ tiêu trong các kỳ báo cáo nháp của nhiệm vụ Diêm nghiệp năm 2026 và đối chiếu chênh lệch với bản đã phê duyệt?"
        frame = self.normalizer.normalize_query(q, session_tenant="68", session_year="2026")
        assert frame.intent == CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT
        assert frame.audit_sub_intent == "REPORT_SUBMISSION_STATUS"
        assert frame.include_draft_comparison is True

        res = self.agent.run(q)
        ans = res["answer"]
        assert "Diêm nghiệp" in ans
        assert "Đối chiếu chênh lệch" in ans
        assert "Chi cục" in ans
        assert "Chi cục Phát triển nông thôn" not in ans

    def test_sc_5_2_form_criteria_group(self):
        q = "Hệ thống hiện có những biểu mẫu thu thập hoặc bộ thu thập chỉ tiêu nào đang áp dụng năm 2026?"
        frame = self.normalizer.normalize_query(q, session_tenant="68", session_year="2026")
        assert frame.intent == CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT
        assert frame.audit_sub_intent == "FORM_CRITERIA_GROUP"

        sql = self.normalizer.compile_canonical_sql(frame)
        rows = self._exec_sql(sql)
        assert len(rows) == 5
        active_cnt = sum(1 for r in rows if r["group_status"] == "active")
        draft_cnt = sum(1 for r in rows if r["group_status"] == "draft")
        assert active_cnt == 3
        assert draft_cnt == 2

        res = self.agent.run(q)
        ans = res["answer"]
        assert "Bộ thu thập Diêm nghiệp" in ans
        assert "Bộ thu thập Phát triển nông thôn" in ans
        assert "Chi cục Phát triển nông thôn" not in ans

    def test_sc_5_3_mission_assignment_matrix(self):
        q = "Hiển thị ma trận phân công nhiệm vụ năm 2026 giữa các phòng ban và cá nhân phụ trách?"
        frame = self.normalizer.normalize_query(q, session_tenant="68", session_year="2026")
        assert frame.intent == CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT
        assert frame.audit_sub_intent == "MISSION_ASSIGNMENT_MATRIX"

        sql = self.normalizer.compile_canonical_sql(frame)
        rows = self._exec_sql(sql)
        assert len(rows) == 6

        res = self.agent.run(q)
        ans = res["answer"]
        assert "Diêm nghiệp" in ans
        assert "Phát triển nông thôn" in ans
        assert "Cải cách hành chính" in ans
        assert "Chi cục" in ans
        assert "Chi cục Phát triển nông thôn" not in ans

    def test_gate3_regression_fact_query_with_bao_cao_prefix(self):
        """
        Câu hỏi 'Báo cáo diện tích sản xuất muối tháng 4 năm 2026' phải định tuyến về
        METRIC_POINT_INQUIRY thay vì bị REPORT_FORM_MISSION_AUDIT chiếm quyền.
        """
        q = "Báo cáo diện tích sản xuất muối tháng 4 năm 2026"
        frame = self.normalizer.normalize_query(q, session_tenant="68", session_year="2026")
        assert frame.intent == CanonicalIntentEnum.METRIC_POINT_INQUIRY
        assert frame.month_filter == 4

    def test_gate3_regression_comma_separated_quarters(self):
        """
        Câu hỏi 'Thống kê các chỉ tiêu từ quý 2, 3 năm 2026' phải trích xuất đúng
        date_from = '2026-04-01' và date_to = '2026-09-30'.
        """
        q = "Thống kê các chỉ tiêu từ quý 2, 3 năm 2026"
        frame = self.normalizer.normalize_query(q, session_tenant="68", session_year="2026")
        assert frame.date_from == "2026-04-01"
        assert frame.date_to == "2026-09-30"
