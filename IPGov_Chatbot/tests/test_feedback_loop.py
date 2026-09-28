"""
Unit & Integration Tests for Human-in-the-Loop Feedback & Quest Annotation Logging
Căn cứ: /test-driven-development, /verification-before-completion
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from IPGov_Chatbot.schemas.feedback_dto import (
    ErrorCategoryEnum,
    FeedbackSeverityEnum,
    QuestAnnotationDTO,
)
from IPGov_Chatbot.core.feedback_manager import FeedbackManager
from IPGov_Chatbot.tools.audit_inspector import AuditInspector
from IPGov_Chatbot.main import app


@pytest.fixture
def temp_feedback_file(tmp_path):
    """Tạo đường dẫn tạm thời cho file quest_annotations.jsonl."""
    log_file = tmp_path / "test_quest_annotations.jsonl"
    return log_file


@pytest.fixture
def feedback_mgr(temp_feedback_file):
    """Khởi tạo FeedbackManager sử dụng file log tạm thời."""
    return FeedbackManager(storage_path=temp_feedback_file)


@pytest.fixture
def client():
    """Tạo TestClient cho FastAPI app."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. TEST DTO SCHEMA & ENUMS
# ---------------------------------------------------------------------------

def test_feedback_dto_validation():
    """Kiểm tra tính hợp lệ và các ràng buộc trường của QuestAnnotationDTO."""
    dto = QuestAnnotationDTO(
        trace_id="trace_test_001",
        session_id="sess_test_001",
        turn_index=2,
        prompt="Huyện nào có trạm y tế đạt chuẩn thấp nhất?",
        error_category=ErrorCategoryEnum.SLOT_EXTRACTION_ERROR,
        severity=FeedbackSeverityEnum.MAJOR,
        user_note="Hệ thống gán nhầm cấp tỉnh thay vì cấp huyện Đam Rông",
        expected_behavior="Gán admin_entity='Huyện Đam Rông' và admin_level=1",
        expected_route="TEMPLATE_FAST_TRACK",
        actual_route="TEMPLATE_FAST_TRACK",
        active_quest_snapshot={"admin_level": 0, "temporal_val": "2025"},
        tags=["dam_rong", "y_te", "mod03"]
    )

    assert dto.annotation_id.startswith("note_")
    assert dto.trace_id == "trace_test_001"
    assert dto.error_category == ErrorCategoryEnum.SLOT_EXTRACTION_ERROR
    assert dto.severity == FeedbackSeverityEnum.MAJOR
    assert dto.status == "OPEN"
    assert len(dto.tags) == 3


# ---------------------------------------------------------------------------
# 2. TEST FEEDBACK MANAGER CRUD & FILTERING
# ---------------------------------------------------------------------------

def test_feedback_manager_save_and_retrieve(feedback_mgr):
    """Kiểm tra lưu trữ và truy vấn danh sách ghi chú feedback."""
    dto1 = QuestAnnotationDTO(
        trace_id="trace_01",
        session_id="sess_01",
        prompt="Tỷ lệ giải ngân khuyến công?",
        error_category=ErrorCategoryEnum.ROUTING_MISMATCH,
        severity=FeedbackSeverityEnum.MAJOR,
        user_note="Chạy nhầm sang Chitchat thay vì Clarification",
        expected_route="CLARIFICATION",
        tags=["khuyen_cong", "route"]
    )
    dto2 = QuestAnnotationDTO(
        trace_id="trace_02",
        session_id="sess_02",
        prompt="DROP TABLE fact_report_criteria;",
        error_category=ErrorCategoryEnum.GUARDRAIL_FALSE_NEGATIVE,
        severity=FeedbackSeverityEnum.CRITICAL,
        user_note="Chưa chặn được biến thể DDL",
        tags=["security", "ddl"]
    )

    # 1. Lưu 2 annotations
    saved1 = feedback_mgr.save_annotation(dto1)
    saved2 = feedback_mgr.save_annotation(dto2)
    assert saved1 is True
    assert saved2 is True

    # 2. Đọc tất cả
    all_notes = feedback_mgr.get_all_annotations()
    assert len(all_notes) == 2

    # 3. Lọc theo ErrorCategory
    route_errors = feedback_mgr.filter_by_category(ErrorCategoryEnum.ROUTING_MISMATCH)
    assert len(route_errors) == 1
    assert route_errors[0].trace_id == "trace_01"

    # 4. Tìm kiếm theo từ khóa (keyword search)
    search_res = feedback_mgr.search_annotations(keyword="DDL")
    assert len(search_res) == 1
    assert search_res[0].severity == FeedbackSeverityEnum.CRITICAL

    # 5. Đánh dấu giải quyết (Mark Resolved)
    res_status = feedback_mgr.mark_resolved(
        annotation_id=dto1.annotation_id,
        resolution_notes="Đã bổ sung regex và fix slot repair trong Mod 3"
    )
    assert res_status is True

    # 6. Kiểm tra lại danh sách OPEN chỉ còn 1
    open_notes = feedback_mgr.get_open_annotations()
    assert len(open_notes) == 1
    assert open_notes[0].annotation_id == dto2.annotation_id


# ---------------------------------------------------------------------------
# 3. TEST FASTAPI ENDPOINTS (/api/v1/chat/feedback)
# ---------------------------------------------------------------------------

def test_api_post_and_get_feedback(client):
    """Kiểm tra API tiếp nhận phản hồi từ UI/Client và trả danh sách feedback."""
    payload = {
        "trace_id": "trace_api_test_999",
        "session_id": "sess_api_test_999",
        "turn_index": 1,
        "prompt": "Hôm nay hệ thống có trực không?",
        "error_category": "ROUTING_MISMATCH",
        "severity": "MINOR",
        "user_note": "Bot trả lời chào mừng thay vì xác nhận trực chiến 24/7",
        "expected_route": "CHITCHAT_BYPASS",
        "actual_route": "CATALOG_DISCOVERY",
        "tags": ["status_check", "mod03"]
    }

    # 1. Gửi request POST
    res_post = client.post("/api/v1/chat/feedback", json=payload)
    assert res_post.status_code == 200
    data = res_post.json()
    assert data["status"] == "recorded"
    assert "annotation_id" in data
    annot_id = data["annotation_id"]

    # 2. Gửi request GET lấy danh sách
    res_get = client.get("/api/v1/chat/feedback")
    assert res_get.status_code == 200
    items = res_get.json()["items"]
    assert any(it["annotation_id"] == annot_id for it in items)

    # 3. Lọc theo category
    res_filtered = client.get("/api/v1/chat/feedback?category=ROUTING_MISMATCH")
    assert res_filtered.status_code == 200
    filtered_items = res_filtered.json()["items"]
    assert len(filtered_items) >= 1


# ---------------------------------------------------------------------------
# 4. TEST AUDIT INSPECTOR FOR AGENT FAST RETRIEVAL & TDD GENERATION
# ---------------------------------------------------------------------------

def test_audit_inspector_stats_and_pytest_export(temp_feedback_file, tmp_path):
    """Kiểm tra AuditInspector phân tích thống kê lỗi và tự động sinh test case pytest."""
    mgr = FeedbackManager(storage_path=temp_feedback_file)
    mgr.save_annotation(QuestAnnotationDTO(
        trace_id="trace_insp_01",
        session_id="sess_insp_01",
        prompt="Kinh phí khuyến công huyện Đam Rông năm 2025?",
        error_category=ErrorCategoryEnum.SLOT_EXTRACTION_ERROR,
        severity=FeedbackSeverityEnum.MAJOR,
        user_note="Nhầm huyện Đam Rông thành toàn tỉnh",
        expected_behavior="admin_entity = 'Huyện Đam Rông'",
        expected_route="TEMPLATE_FAST_TRACK",
        tags=["dam_rong", "khuyen_cong"]
    ))

    inspector = AuditInspector(log_path=temp_feedback_file)
    
    # 1. Thống kê lỗi
    stats = inspector.get_summary_stats()
    assert stats["total_annotations"] == 1
    assert stats["open_annotations"] == 1
    assert stats["by_category"]["SLOT_EXTRACTION_ERROR"] == 1

    # 2. Xuất file test case pytest tự động
    export_test_file = tmp_path / "test_user_reported_generated.py"
    export_ok = inspector.export_to_pytest(output_path=export_test_file)
    assert export_ok is True
    assert export_test_file.exists()

    content = export_test_file.read_text(encoding="utf-8")
    assert "def test_reported_case_trace_insp_01" in content
    assert "Kinh phí khuyến công huyện Đam Rông năm 2025?" in content
