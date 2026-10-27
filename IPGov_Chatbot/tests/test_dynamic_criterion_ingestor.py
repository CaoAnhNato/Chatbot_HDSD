"""
Unit & Integration Test Suite: test_dynamic_criterion_ingestor.py
Chức năng: Kiểm thử toàn diện Milestone M1:
1. Tính toàn vẹn cấu trúc và ngữ nghĩa của Kho Định Nghĩa Chỉ Tiêu (criterion_definitions_kb.json - 155 chỉ tiêu).
2. Quy trình đồng bộ dữ liệu vào bảng catalog_definitions trong In-Memory DuckDB.
3. Bộ lọc kiểm duyệt 5 cổng tự lọc (5-Gate Self-Filtering Validation Firewall).
4. Luồng Dynamic Ingestion tự động phát hiện, sinh định nghĩa và đồng bộ khi có chỉ tiêu mới.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import duckdb
import pytest

from IPGov_Chatbot.modules.mod04_catalog.dynamic_criterion_ingestor import (
    DEFAULT_KB_PATH,
    REQUIRED_FIELDS,
    DynamicCriterionIngestor,
    FiveGateValidator,
    FiveGateValidationError,
    sync_definitions_to_duckdb,
    ingest_new_criterion,
)


@pytest.fixture
def kb_data():
    """Load live criterion_definitions_kb.json."""
    assert DEFAULT_KB_PATH.exists(), f"KB file does not exist at {DEFAULT_KB_PATH}"
    with open(DEFAULT_KB_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


@pytest.fixture
def mock_openrouter_client():
    """Mock client OpenRouter trả về định nghĩa chuẩn đáp ứng 5 gates."""
    client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    
    generated_content = {
        "definition": "Số lượng HTX nông nghiệp thực hiện chuyển đổi số và ứng dụng công nghệ thông tin trong quản lý điều hành sản xuất kinh doanh.",
        "natural_synonyms": [
            "htx nông nghiệp chuyển đổi số",
            "hợp tác xã nông nghiệp ứng dụng công nghệ số",
            "htx chuyển đổi số nông nghiệp"
        ],
        "scope_description": "Áp dụng cho các hợp tác xã nông nghiệp có áp dụng phần mềm kế toán, nhật ký điện tử hoặc sàn thương mại điện tử."
    }
    mock_message.content = json.dumps(generated_content, ensure_ascii=False)
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    client.chat.completions.create.return_value = mock_response
    return client


# ==============================================================================
# TEST SUITE 1: KB SCHEMA INTEGRITY (155 CRITERIA)
# ==============================================================================
def test_kb_schema_integrity(kb_data):
    """Kiểm tra tính toàn vẹn của 155 chỉ tiêu trong Kho Định Nghĩa."""
    assert len(kb_data) == 155, f"Kho định nghĩa phải có đúng 155 chỉ tiêu, hiện có: {len(kb_data)}"

    level_counts = {1: 0, 2: 0, 3: 0}
    facts_approved_count = 0

    for cid, entry in kb_data.items():
        # Kiểm tra 19 trường bắt buộc
        for field in REQUIRED_FIELDS:
            assert field in entry, f"Chỉ tiêu {cid} thiếu trường bắt buộc: {field}"

        # Kiểm tra ID nhất quán
        assert entry["id"] == cid, f"ID không khớp khóa từ điển: {entry['id']} != {cid}"
        assert entry["level"] in (1, 2, 3), f"Level không hợp lệ: {entry['level']}"
        level_counts[entry["level"]] += 1

        # Kiểm tra độ dài định nghĩa >= 30 ký tự
        assert len(entry["definition"].strip()) >= 30, (
            f"Định nghĩa của '{entry['name']}' quá ngắn (< 30 ký tự): {entry['definition']}"
        )

        # Kiểm tra từ đồng nghĩa >= 2
        assert isinstance(entry["natural_synonyms"], list), f"natural_synonyms phải là list trong {cid}"
        assert len(entry["natural_synonyms"]) >= 2, (
            f"Chỉ tiêu '{entry['name']}' phải có ít nhất 2 từ đồng nghĩa"
        )

        # Kiểm tra canonical_order >= 1
        assert isinstance(entry["canonical_order"], int) and entry["canonical_order"] >= 1, (
            f"canonical_order không hợp lệ trong {cid}"
        )

        # Kiểm tra liên kết phân cấp
        if entry["level"] == 1:
            assert entry["parent_id"] is None, f"Chỉ tiêu cấp 1 '{entry['name']}' không được có parent_id"
            assert entry["parent_name"] is None, f"Chỉ tiêu cấp 1 '{entry['name']}' không được có parent_name"
            assert entry["root_id"] == cid, f"Chỉ tiêu cấp 1 '{entry['name']}' phải có root_id = chính nó"
        else:
            assert entry["parent_id"] is not None, f"Chỉ tiêu con '{entry['name']}' phải có parent_id"
            assert entry["parent_name"] is not None, f"Chỉ tiêu con '{entry['name']}' phải có parent_name"

        if entry["has_approved_facts"]:
            facts_approved_count += 1
            assert len(entry["available_report_dates"]) > 0, (
                f"Chỉ tiêu '{entry['name']}' có approved facts nhưng danh sách ngày rỗng"
            )

    # Đối chuẩn phân bổ cấp bậc theo hiện trạng DWH
    assert level_counts[1] == 30, f"Kỳ vọng 30 chỉ tiêu Cấp 1, có: {level_counts[1]}"
    assert level_counts[2] == 60, f"Kỳ vọng 60 chỉ tiêu Cấp 2, có: {level_counts[2]}"
    assert level_counts[3] == 65, f"Kỳ vọng 65 chỉ tiêu Cấp 3, có: {level_counts[3]}"
    assert facts_approved_count == 127, f"Kỳ vọng 127 chỉ tiêu có approved facts, có: {facts_approved_count}"


def test_kb_standard_examples_conformance(kb_data):
    """Kiểm tra các chỉ tiêu tiêu biểu tuân thủ chuẩn Ảnh 1 & Ảnh 2."""
    # Tìm nhánh HTX nông nghiệp
    htx_root = next((e for e in kb_data.values() if e["code"] == "htx_nong_nghiep"), None)
    assert htx_root is not None
    assert "hợp tác xã" in htx_root["definition"].lower()
    assert htx_root["level"] == 1

    # Kiểm tra các chỉ tiêu con của HTX theo Ảnh 2
    luy_ke = next((e for e in kb_data.values() if e["code"] == "luy_ke_den_thoi_diem_bao_cao"), None)
    assert luy_ke is not None
    assert "htx nông nghiệp" in luy_ke["definition"].lower()
    assert any(term in luy_ke["definition"].lower() for term in ["cộng dồn", "lũy kế", "tích lũy"])

    thanh_lap_moi = next((e for e in kb_data.values() if e["code"] == "thanh_lap_moi"), None)
    assert thanh_lap_moi is not None
    assert "htx nông nghiệp" in thanh_lap_moi["definition"].lower()
    assert any(term in thanh_lap_moi["definition"].lower() for term in ["mới", "phát sinh", "kỳ"])

    dang_hoat_dong = next((e for e in kb_data.values() if e["code"] == "dang_hoat_dong"), None)
    assert dang_hoat_dong is not None
    assert "htx nông nghiệp" in dang_hoat_dong["definition"].lower()
    assert any(term in dang_hoat_dong["definition"].lower() for term in ["thực tế", "vận hành", "duy trì"])

    thanh_vien = next((e for e in kb_data.values() if e["code"] == "thanh_vien"), None)
    assert thanh_vien is not None
    assert "htx nông nghiệp" in thanh_vien["definition"].lower()
    assert "thành viên" in thanh_vien["definition"].lower()


# ==============================================================================
# TEST SUITE 2: DUCKDB SYNCHRONIZATION
# ==============================================================================
def test_duckdb_synchronization():
    """Kiểm tra đồng bộ toàn bộ Kho Định Nghĩa vào DuckDB bảng catalog_definitions."""
    conn = duckdb.connect(":memory:")
    synced_count = sync_definitions_to_duckdb(DEFAULT_KB_PATH, conn)
    assert synced_count == 155

    # Kiểm tra cấu trúc bảng
    table_info = conn.execute("PRAGMA table_info('catalog_definitions')").fetchall()
    col_names = [col[1] for col in table_info]
    expected_cols = [
        "id", "code", "name", "level", "is_leaf", "scope_name",
        "parent_id", "parent_name", "root_id", "root_name",
        "canonical_order", "definition", "natural_synonyms",
        "scope_description", "has_approved_facts", "available_dates", "updated_at"
    ]
    for exp_col in expected_cols:
        assert exp_col in col_names, f"Thiếu cột {exp_col} trong DuckDB catalog_definitions"

    # Kiểm tra tổng số bản ghi
    total = conn.execute("SELECT count(*) FROM catalog_definitions").fetchone()[0]
    assert total == 155

    # Kiểm tra truy vấn theo level
    l1_count = conn.execute("SELECT count(*) FROM catalog_definitions WHERE level = 1").fetchone()[0]
    assert l1_count == 30
    l2_count = conn.execute("SELECT count(*) FROM catalog_definitions WHERE level = 2").fetchone()[0]
    assert l2_count == 60
    l3_count = conn.execute("SELECT count(*) FROM catalog_definitions WHERE level = 3").fetchone()[0]
    assert l3_count == 65

    # Kiểm tra truy vấn nhánh HTX nông nghiệp và thứ tự canonical_order
    htx_children = conn.execute("""
        SELECT name, canonical_order, is_leaf
        FROM catalog_definitions
        WHERE parent_name = 'HTX nông nghiệp'
        ORDER BY canonical_order ASC
    """).fetchall()
    assert len(htx_children) == 8
    # Kiểm tra canonical_order tăng dần liên tục từ 1..8
    orders = [row[1] for row in htx_children]
    assert orders == list(range(1, 9))

    # Kiểm tra giải mã JSON danh sách ngày và từ đồng nghĩa
    sample_row = conn.execute("""
        SELECT natural_synonyms, available_dates
        FROM catalog_definitions
        WHERE code = 'htx_nong_nghiep'
    """).fetchone()
    synonyms = json.loads(sample_row[0])
    dates = json.loads(sample_row[1])
    assert isinstance(synonyms, list) and len(synonyms) >= 2
    assert isinstance(dates, list) and len(dates) >= 1
    conn.close()


# ==============================================================================
# TEST SUITE 3: 5-GATE SELF-FILTERING VALIDATION
# ==============================================================================
def test_5_gate_validation_all_pass():
    """Kiểm tra một bản ghi hợp lệ vượt qua thành công cả 5 cổng."""
    valid_record = {
        "id": "11111111-2222-3333-4444-555555555555",
        "code": "htx_cong_nghe_cao",
        "name": "HTX nông nghiệp công nghệ cao",
        "level": 2,
        "is_leaf": True,
        "scope_name": "Nông nghiệp",
        "parent_id": "c3d526e9-b593-41bb-94b1-84c475cf2e09",
        "parent_name": "HTX nông nghiệp",
        "root_id": "c3d526e9-b593-41bb-94b1-84c475cf2e09",
        "root_name": "HTX nông nghiệp",
        "canonical_order": 9,
        "siblings": ["Trồng trọt", "Chăn nuôi"],
        "children_ids": [],
        "definition": "Số lượng HTX nông nghiệp ứng dụng công nghệ cao trong sản xuất canh tác và quản lý vận hành.",
        "natural_synonyms": [
            "htx nông nghiệp công nghệ cao",
            "hợp tác xã nông nghiệp ứng dụng kỹ thuật cao",
            "htx cnc nông nghiệp"
        ],
        "scope_description": "Các đơn vị HTX nông nghiệp được chứng nhận nông nghiệp ứng dụng công nghệ cao.",
        "has_approved_facts": False,
        "available_report_dates": [],
        "metadata": {"source": "test"}
    }
    context = {
        "root_name": "HTX nông nghiệp",
        "parent_name": "HTX nông nghiệp",
        "siblings": ["Trồng trọt", "Chăn nuôi"],
        "parent_definition": "Nhóm đối tượng thống kê chính phản ánh hợp tác xã.",
        "sibling_definitions": ["Số lượng HTX trồng trọt chuyên ngành."]
    }

    ok, msg = FiveGateValidator.run_all_gates(valid_record, context=context)
    assert ok is True
    assert msg == "All 5 Gates Passed"


def test_gate1_schema_failure():
    """Gate 1: Thất bại khi thiếu trường hoặc định nghĩa quá ngắn."""
    # Thiếu trường
    invalid_record = {
        "id": "123",
        "code": "test_code",
        "name": "Test"
    }
    ok, msg = FiveGateValidator.validate_gate1_schema(invalid_record)
    assert ok is False
    assert "Gate 1 Failed" in msg

    # Định nghĩa quá ngắn (< 30 ký tự)
    short_def_record = {
        "id": "123",
        "code": "test_code",
        "name": "Test",
        "level": 1,
        "is_leaf": True,
        "scope_name": "Nông nghiệp",
        "parent_id": None,
        "parent_name": None,
        "root_id": "123",
        "root_name": "Test",
        "canonical_order": 1,
        "siblings": [],
        "children_ids": [],
        "definition": "Định nghĩa ngắn",  # < 30 ký tự
        "natural_synonyms": ["syn1", "syn2"],
        "scope_description": "Scope",
        "has_approved_facts": False,
        "available_report_dates": [],
        "metadata": {}
    }
    ok, msg = FiveGateValidator.validate_gate1_schema(short_def_record)
    assert ok is False
    assert "quá ngắn" in msg


def test_gate2_parent_alignment_failure():
    """Gate 2: Thất bại khi chỉ tiêu con không gắn với ngữ cảnh thực thể cha."""
    unaligned_child = {
        "name": "Chuyển đổi số",
        "level": 2,
        "root_name": "HTX nông nghiệp",
        "parent_name": "HTX nông nghiệp",
        "definition": "Số lượng doanh nghiệp tư nhân ứng dụng phần mềm quản lý kho bãi và chuỗi cung ứng sản phẩm."
    }
    context = {"root_name": "HTX nông nghiệp", "parent_name": "HTX nông nghiệp"}
    ok, msg = FiveGateValidator.validate_gate2_parent_alignment(unaligned_child, context)
    assert ok is False
    assert "Gate 2 Failed" in msg
    assert "không gắn kết với ngữ cảnh thực thể cha" in msg


def test_gate3_temporal_and_fluff_failure():
    """Gate 3: Thất bại khi chứa lời chào hoặc meta-text AI, hoặc sai lệch mốc thời gian."""
    # Chứa lời chào AI
    fluff_record = {
        "name": "Chỉ tiêu kiểm tra",
        "definition": "Chào bạn, dưới đây là định nghĩa số lượng HTX nông nghiệp đang duy trì vận hành sản xuất kinh doanh."
    }
    ok, msg = FiveGateValidator.validate_gate3_temporal_and_fluff(fluff_record)
    assert ok is False
    assert "Gate 3 Failed" in msg

    # Lũy kế nhưng định nghĩa không có từ khóa tích lũy
    temporal_mismatch = {
        "name": "Lũy kế tổng số lượng chủ thể đến thời điểm báo cáo",
        "definition": "Số lượng chủ thể phát sinh đăng ký mới trong tháng vừa qua trên địa bàn tỉnh."
    }
    ok, msg = FiveGateValidator.validate_gate3_temporal_and_fluff(temporal_mismatch)
    assert ok is False
    assert "Lũy kế" in msg


def test_gate4_synonyms_and_collision_failure():
    """Gate 4: Thất bại khi từ đồng nghĩa < 2 hoặc va chạm với tên anh em cùng cấp."""
    # Ít hơn 2 từ đồng nghĩa
    few_synonyms = {
        "name": "Trồng trọt",
        "natural_synonyms": ["nông nghiệp trồng trọt"],
        "siblings": ["Chăn nuôi", "Lâm nghiệp"]
    }
    ok, msg = FiveGateValidator.validate_gate4_synonyms(few_synonyms)
    assert ok is False
    assert "Gate 4 Failed" in msg

    # Va chạm với tên anh em cùng cấp
    colliding_synonyms = {
        "name": "Trồng trọt",
        "natural_synonyms": ["htx trồng trọt", "Chăn nuôi"],  # Va chạm với anh em Chăn nuôi
        "siblings": ["Chăn nuôi", "Lâm nghiệp"]
    }
    ok, msg = FiveGateValidator.validate_gate4_synonyms(colliding_synonyms)
    assert ok is False
    assert "bị va chạm với tên chỉ tiêu anh em" in msg


def test_gate5_jaccard_redundancy_failure():
    """Gate 5: Thất bại khi định nghĩa trùng lặp >= 0.85 với cha hoặc anh em."""
    parent_def = "Số lượng HTX nông nghiệp thực tế đang duy trì vận hành sản xuất kinh doanh tại thời điểm báo cáo."
    # Copy paste gần như 100% của cha
    redundant_record = {
        "name": "HTX hoạt động",
        "definition": "Số lượng HTX nông nghiệp thực tế đang duy trì vận hành sản xuất kinh doanh tại thời điểm báo cáo tỉnh."
    }
    ok, msg = FiveGateValidator.validate_gate5_jaccard_redundancy(redundant_record, parent_definition=parent_def)
    assert ok is False
    assert "Gate 5 Failed" in msg
    assert "trùng lặp quá cao" in msg


# ==============================================================================
# TEST SUITE 4: DYNAMIC INGESTION PIPELINE (END-TO-END FLOW)
# ==============================================================================
def test_dynamic_ingest_single_criterion_with_mock(tmp_path, mock_openrouter_client):
    """Kiểm tra end-to-end quy trình nạp 1 chỉ tiêu mới sử dụng mock LLM."""
    temp_kb_path = tmp_path / "temp_kb.json"
    temp_kb_path.write_text("{}", encoding="utf-8")

    ingestor = DynamicCriterionIngestor(
        kb_path=temp_kb_path,
        client=mock_openrouter_client,
        model_name="google/gemini-3.5-flash-lite"
    )

    new_criterion = {
        "id": "99999999-8888-7777-6666-555555555555",
        "code": "htx_chuyen_doi_so",
        "name": "HTX nông nghiệp chuyển đổi số",
        "level": 2,
        "parent_id": "c3d526e9-b593-41bb-94b1-84c475cf2e09",
        "scope_name": "Nông nghiệp"
    }
    context = {
        "root_name": "HTX nông nghiệp",
        "parent_name": "HTX nông nghiệp",
        "scope_name": "Nông nghiệp",
        "siblings": ["Thành lập mới", "Đang hoạt động"]
    }

    # Thực hiện nạp
    result = ingestor.process_single_criterion(new_criterion, context=context)
    assert result["id"] == new_criterion["id"]
    assert result["code"] == new_criterion["code"]
    assert "HTX nông nghiệp" in result["definition"]
    assert len(result["natural_synonyms"]) >= 2
    assert result["metadata"]["model"] == "google/gemini-3.5-flash-lite"

    # Lưu vào temp KB và đồng bộ vào DuckDB
    kb = {result["id"]: result}
    ingestor.save_kb(kb)

    conn = duckdb.connect(":memory:")
    synced = sync_definitions_to_duckdb(temp_kb_path, conn)
    assert synced == 1

    row = conn.execute("SELECT name, definition FROM catalog_definitions WHERE id = ?", (result["id"],)).fetchone()
    assert row is not None
    assert row[0] == "HTX nông nghiệp chuyển đổi số"
    assert "chuyển đổi số" in row[1].lower()
    conn.close()


def test_dynamic_ingest_rejects_invalid_llm_output(tmp_path):
    """Kiểm tra khi LLM trả về định nghĩa không đạt chuẩn, 5 gates sẽ từ chối và ném FiveGateValidationError."""
    temp_kb_path = tmp_path / "temp_kb.json"
    temp_kb_path.write_text("{}", encoding="utf-8")

    bad_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    
    # Định nghĩa vi phạm Gate 3 (chứa lời chào AI) và Gate 1 (quá ngắn)
    bad_content = {
        "definition": "Chào bạn, đây là test.",
        "natural_synonyms": ["test"]
    }
    mock_message.content = json.dumps(bad_content)
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    bad_client.chat.completions.create.return_value = mock_response

    ingestor = DynamicCriterionIngestor(kb_path=temp_kb_path, client=bad_client)

    new_crit = {
        "id": "88888888-0000-0000-0000-000000000000",
        "code": "test_bad",
        "name": "Chỉ tiêu lỗi",
        "level": 2,
        "parent_id": "c3d526e9-b593-41bb-94b1-84c475cf2e09"
    }

    with pytest.raises(FiveGateValidationError):
        ingestor.process_single_criterion(new_crit)


# ==============================================================================
# TEST SUITE 5: PRODUCTION 155 CRITERIA 5-GATE FULL VALIDATION
# ==============================================================================
def test_all_155_production_kb_entries_pass_five_gates(kb_data):
    """
    Kiểm chứng toàn diện: Toàn bộ 155 chỉ tiêu trong criterion_definitions_kb.json
    phải vượt qua 100% cả 5 cổng kiểm duyệt (Zero False Rejections / Zero Failures).
    """
    assert len(kb_data) == 155, f"Kho KB phải có đúng 155 chỉ tiêu, thực tế có: {len(kb_data)}"

    failures = []
    for cid, record in kb_data.items():
        pid = record.get("parent_id")
        parent_entry = kb_data.get(pid) if pid else None

        context = {
            "root_name": record.get("root_name"),
            "parent_name": record.get("parent_name"),
            "scope_name": record.get("scope_name"),
            "siblings": record.get("siblings", []),
            "parent_definition": parent_entry.get("definition") if parent_entry else None,
            "sibling_definitions": [
                other["definition"] for other in kb_data.values()
                if other.get("parent_id") == pid and other.get("id") != cid and other.get("definition")
            ] if pid else []
        }

        passed, msg = FiveGateValidator.run_all_gates(
            record=record,
            context=context,
            parent_definition=context["parent_definition"],
            sibling_definitions=context["sibling_definitions"]
        )

        if not passed:
            failures.append({
                "id": cid,
                "name": record.get("name"),
                "code": record.get("code"),
                "level": record.get("level"),
                "parent_name": record.get("parent_name"),
                "reason": msg
            })

    assert len(failures) == 0, (
        f"Có {len(failures)} / 155 chỉ tiêu trong KB bị FiveGateValidator từ chối:\n"
        f"{json.dumps(failures, ensure_ascii=False, indent=2)}"
    )
