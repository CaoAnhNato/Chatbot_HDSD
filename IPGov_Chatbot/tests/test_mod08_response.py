"""
Unit & Contract Tests cho Module 08: Response Synthesizer & Lineage Badge
Tuân thủ chuẩn Bonsai Testing (Black-Box Observable Behavior, YAGNI, không mock thô, chạy < 2s).
"""

import pytest
from IPGov_Chatbot.schemas.response_synthesizer_dto import (
    RenderModeEnum,
    LineageBadgeDTO,
    SynthesizerOutputDTO,
)
from IPGov_Chatbot.schemas.dwh_exec_dto import QueryResultDTO, ExecutionStatusEnum, ColumnMetadataDTO
from IPGov_Chatbot.schemas.ast_enforcer_dto import SanitizedSQLDTO
from IPGov_Chatbot.schemas.router_dto import (
    RouterOutputDTO,
    RouteTypeEnum,
    IntentEnum,
    ActiveQuestFrameDTO,
)
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO
from IPGov_Chatbot.modules.mod08_response.jinja_slot_engine import (
    JinjaSlotEngine,
    vn_format_num,
    safe_percentage,
    vn_status_translate,
)
from IPGov_Chatbot.modules.mod08_response.lineage_badge_builder import LineageBadgeBuilder
from IPGov_Chatbot.modules.mod08_response.response_synthesizer_service import ResponseSynthesizerService


# ------------------------------------------------------------------------------
# 1. KIỂM THỬ ĐỊNH DẠNG SỐ TIẾNG VIỆT & TỶ LỆ AN TOÀN
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "val, expected",
    [
        (1000, "1,000"),
        (4500000000, "4,500,000,000"),
        (1234.56, "1,234.56"),
        (0, "0"),
        (None, "0"),
        ("1250000", "1,250,000"),
    ],
)
def test_vn_format_num(val, expected):
    """Đảm bảo định dạng số theo chuẩn phân cách hàng nghìn."""
    assert vn_format_num(val) == expected


def test_safe_percentage_division_by_zero():
    """Bảo vệ khỏi ZeroDivisionError khi kỳ gốc bằng 0."""
    pct, text, note = safe_percentage(val_2=150.0, val_1=0.0)
    assert pct is None
    assert "Không tính toán % tăng trưởng" in text
    assert "Kỳ gốc ghi nhận 0" in note


def test_safe_percentage_small_base_effect():
    """Cảnh báo khi kỳ gốc nhỏ (< 5) gây đột biến tỷ lệ phần trăm."""
    pct, text, note = safe_percentage(val_2=20.0, val_1=2.0)
    assert pct == 900.0
    assert "tăng +900.0%" in text
    assert note is not None
    assert "Số liệu kỳ gốc nhỏ (2.0)" in note


def test_safe_percentage_normal_growth():
    """Tính toán bình thường khi số liệu lớn."""
    pct, text, note = safe_percentage(val_2=1200.0, val_1=1000.0)
    assert pct == 20.0
    assert "tăng +20.0%" in text
    assert note is None


# ------------------------------------------------------------------------------
# 2. KIỂM THỬ ĐỘNG CƠ JINJA2 TẤT ĐỊNH (JINJA SLOT ENGINE)
# ------------------------------------------------------------------------------
def test_jinja_render_direct_metric():
    """Kiểm thử render chỉ tiêu đơn lẻ chuẩn BLUF."""
    engine = JinjaSlotEngine()
    content = engine.render("DIRECT_METRIC", {
        "period": "2024",
        "entity_name": "Sở Công Thương",
        "metric_name": "Tổng kinh phí khuyến công",
        "value_formatted": "4.500.000.000",
        "unit": "VNĐ",
    })
    assert "Theo số liệu báo cáo đã phê duyệt năm 2024 của Sở Công Thương" in content
    assert "Tổng kinh phí khuyến công là: **4.500.000.000 VNĐ**." in content


def test_jinja_render_ranking_top_k():
    """Kiểm thử render bảng xếp hạng Top-K với độ lệch spread."""
    engine = JinjaSlotEngine()
    items = [
        {"name": "Đà Lạt", "value_formatted": "150.000.000", "val_num": 150000000},
        {"name": "Bảo Lộc", "value_formatted": "120.000.000", "val_num": 120000000},
        {"name": "Đức Trọng", "value_formatted": "90.000.000", "val_num": 90000000},
    ]
    content = engine.render("RANKING_TOP_K", {
        "items": items,
        "metric_name": "Kinh phí",
        "period": "2024",
        "unit": "VNĐ",
        "spread_formatted": "60.000.000",
    })
    assert "Top 3 đơn vị có Kinh phí cao nhất năm 2024, dẫn đầu là **Đà Lạt**" in content
    assert "| Hạng | Đơn vị | Giá trị (VNĐ) | Ghi chú |" in content
    assert "| 1 | Đà Lạt | 150.000.000 |" in content
    assert "Chênh lệch giữa đơn vị dẫn đầu và cuối nhóm là 60.000.000 VNĐ." in content


def test_jinja_render_empty_result():
    """Kiểm thử thông báo tập kết quả rỗng không kèm ngữ cảnh năm."""
    engine = JinjaSlotEngine()
    content = engine.render("EMPTY_RESULT", {})
    assert "Không tìm thấy bản ghi số liệu đã được phê duyệt" in content


def test_jinja_render_empty_result_with_temporal_context():
    """Kiểm thử thông báo tập kết quả rỗng có ngữ cảnh năm và gợi ý năm 2026."""
    engine = JinjaSlotEngine()
    content = engine.render("EMPTY_RESULT", {"query_year": "2025", "suggested_year": "2026"})
    assert "trong năm **2025**" in content
    assert "dữ liệu số liệu đầy đủ đã phê duyệt của **năm 2026**" in content


# ------------------------------------------------------------------------------
# 3. KIỂM THỬ THẺ NGUỒN GỐC DỮ LIỆU (LINEAGE BADGE BUILDER)
# ------------------------------------------------------------------------------
def test_lineage_badge_builder_generation():
    """Kiểm thử tạo LineageBadgeDTO với mã hash SHA-256 64 ký tự."""
    builder = LineageBadgeBuilder()

    qr = QueryResultDTO(
        status=ExecutionStatusEnum.SUCCESS,
        executed_sql="SELECT sum(value) FROM fact_report_criteria WHERE department_code = '68';",
        execution_time_ms=15.2,
        row_count=42,
        columns=[ColumnMetadataDTO(name="total_val", data_type="numeric")],
        rows=[{"total_val": 4500000000}],
    )
    user_ctx = UserSecurityContextDTO(
        user_id="usr_test",
        username="test_officer",
        role_level=2,
        tenant_code="68",
        department_code="68",
    )
    router_out = RouterOutputDTO(
        session_id="test_sess_01",
        query_sanitized="Kinh phí khuyến công 2024",
        route=RouteTypeEnum.TEMPLATE_FAST_TRACK,
        intent=IntentEnum.FAST_METRIC_COMPILER,
        extracted_entities={
            "year": "2024",
            "metric_name": "Kinh phí khuyến công",
            "department_code": "68",
        },
    )

    badge = builder.build_badge(
        query_result=qr,
        sanitized_dto=None,
        router_output=router_out,
        user_ctx=user_ctx,
    )

    assert isinstance(badge, LineageBadgeDTO)
    assert badge.department_code == "68"
    assert badge.department_name == "UBND Tỉnh Lâm Đồng"
    assert badge.report_period == "2024"
    assert badge.record_count == 42
    assert badge.report_status == "approved"
    assert len(badge.verification_hash) == 64  # SHA-256 hex string


# ------------------------------------------------------------------------------
# 4. KIỂM THỬ FACADE SERVICE (RESPONSE SYNTHESIZER SERVICE)
# ------------------------------------------------------------------------------
def test_response_synthesizer_empty_result_safe_gate():
    """Kiểm thử phòng vệ Dual-Gate khi CSDL trả về 0 dòng."""
    service = ResponseSynthesizerService()

    qr = QueryResultDTO(
        status=ExecutionStatusEnum.SUCCESS,
        executed_sql="SELECT * FROM fact_report_criteria WHERE year = '2099';",
        execution_time_ms=5.0,
        row_count=0,
        is_empty=True,
        columns=[],
        rows=[],
    )

    out = service.synthesize_sync(query_result=qr, trace_id="tr_empty_01")

    assert out.render_mode == RenderModeEnum.EMPTY_NOTIFICATION
    assert "Không tìm thấy bản ghi số liệu đã được phê duyệt" in out.content
    assert out.tokens_used == 0
    assert out.lineage_badge is not None
    assert out.lineage_badge.record_count == 0


def test_response_synthesizer_empty_result_with_user_prompt_temporal_awareness():
    """Kiểm thử phòng vệ khi CSDL trả về 0 dòng và người dùng hỏi năm 2025."""
    service = ResponseSynthesizerService()

    qr = QueryResultDTO(
        status=ExecutionStatusEnum.SUCCESS,
        executed_sql="SELECT * FROM fact_report_criteria WHERE year = '2025';",
        execution_time_ms=5.0,
        row_count=0,
        is_empty=True,
        columns=[],
        rows=[],
    )

    out = service.synthesize_sync(
        query_result=qr,
        user_prompt="[tenant_code=68, level=0] Kinh phí thực hiện khuyến công năm 2025 là bao nhiêu?",
        trace_id="tr_empty_2025",
    )

    assert out.render_mode == RenderModeEnum.EMPTY_NOTIFICATION
    assert "trong năm **2025**" in out.content
    assert "năm 2026" in out.content
    assert out.tokens_used == 0


def test_response_synthesizer_error_notification():
    """Kiểm thử khi CSDL gặp lỗi thực thi."""
    service = ResponseSynthesizerService()

    qr = QueryResultDTO(
        status=ExecutionStatusEnum.ERROR,
        executed_sql="SELECT syntax error;",
        execution_time_ms=2.0,
        error_message="syntax error at or near 'syntax'",
    )

    out = service.synthesize_sync(query_result=qr, trace_id="tr_err_01")

    assert out.render_mode == RenderModeEnum.ERROR_NOTIFICATION
    assert "⚠️ Yêu cầu tra cứu không thể hoàn tất do lỗi cơ sở dữ liệu" in out.content
    assert out.tokens_used == 0
    assert out.lineage_badge is None


def test_response_synthesizer_deterministic_direct_metric():
    """Kiểm thử tự động khớp Jinja Direct Metric cho kết quả 1 dòng."""
    service = ResponseSynthesizerService()

    qr = QueryResultDTO(
        status=ExecutionStatusEnum.SUCCESS,
        executed_sql="SELECT sum(value) as val FROM fact_report_criteria WHERE department_code = '68';",
        execution_time_ms=8.5,
        row_count=1,
        columns=[ColumnMetadataDTO(name="val", data_type="numeric")],
        rows=[{"val": 4500000000}],
    )
    router_out = RouterOutputDTO(
        session_id="test_sess_02",
        query_sanitized="Tổng kinh phí khuyến công Sở Công Thương 2024",
        route=RouteTypeEnum.TEMPLATE_FAST_TRACK,
        intent=IntentEnum.FAST_METRIC_COMPILER,
        active_quest=ActiveQuestFrameDTO(
            quest_id="q2",
            admin_entity="Sở Công Thương",
            temporal_val="2024",
            metric_code="Tổng kinh phí khuyến công",
            extra_slots={"unit": "đồng", "department_code": "68"},
        ),
    )

    out = service.synthesize_sync(
        query_result=qr,
        router_output=router_out,
        trace_id="tr_metric_01",
    )

    assert out.render_mode == RenderModeEnum.DETERMINISTIC_TEMPLATE
    assert out.tokens_used == 0
    assert "Theo số liệu báo cáo đã phê duyệt năm 2024 của Sở Công Thương" in out.content
    assert "4,500,000,000 đồng" in out.content
    assert out.lineage_badge is not None
    assert out.lineage_badge.department_name == "Sở Công Thương"
    assert out.tabular_data is None  # 1 dòng thì không tạo tabular_data


def test_response_synthesizer_tabular_data_generation():
    """Kiểm thử tự động sinh TabularDataDTO chuẩn hóa khi kết quả có >= 2 dòng."""
    service = ResponseSynthesizerService()

    qr = QueryResultDTO(
        status=ExecutionStatusEnum.SUCCESS,
        executed_sql="SELECT department_name, sum(value) as tong_gia_tri FROM fact_report_criteria GROUP BY department_name;",
        execution_time_ms=12.0,
        row_count=3,
        columns=[
            ColumnMetadataDTO(name="department_name", data_type="text"),
            ColumnMetadataDTO(name="tong_gia_tri", data_type="numeric"),
        ],
        rows=[
            {"department_name": "Sở Công Thương", "tong_gia_tri": 4500000000},
            {"department_name": "Sở Nông Nghiệp", "tong_gia_tri": 3200000000},
            {"department_name": "Sở Xây Dựng", "tong_gia_tri": 1800000000},
        ],
    )
    router_out = RouterOutputDTO(
        session_id="test_sess_tab_01",
        query_sanitized="Xếp hạng các đơn vị theo tổng giá trị",
        route=RouteTypeEnum.TEMPLATE_FAST_TRACK,
        intent=IntentEnum.FAST_METRIC_COMPILER,
        dag_archetype="RANKING_TOP_K",
        active_quest=ActiveQuestFrameDTO(
            quest_id="q_tab_1",
            temporal_val="2026",
            metric_code="Tổng kinh phí",
        ),
    )

    out = service.synthesize_sync(
        query_result=qr,
        router_output=router_out,
        trace_id="tr_tab_01",
    )

    assert out.table_rendered is True
    assert out.tabular_data is not None
    assert len(out.tabular_data.columns) >= 2
    assert out.tabular_data.total_records == 3
    # Kiểm tra cột tong_gia_tri được căn phải và có kiểu number
    val_col = next(c for c in out.tabular_data.columns if c.key == "tong_gia_tri")
    assert val_col.align.value == "right"
    assert val_col.data_type.value == "number"
