"""
Module: IPGov_Chatbot/tests/test_ci_catalog_discovery.py
Chức năng: Bộ kiểm thử bắt buộc CI-CATALOG-DISCOVERY (18 Test Cases HITL từ golden_full_suite.json)
và 5 kịch bản kết nối bảng cầu nối NetworkX Minimal Steiner Tree.
Căn cứ kiến trúc: Blueprints 01, 03, 08 và Master Plan Stage 4.
"""

import json
from pathlib import Path
import pytest

from IPGov_Chatbot.schemas.catalog_dto import CatalogPrunedDTO
from IPGov_Chatbot.modules.mod04_catalog.schema_pruner import SchemaPruner
from IPGov_Chatbot.modules.mod04_catalog.steiner_tree_builder import SteinerTreeBuilder
from IPGov_Chatbot.modules.mod04_catalog.capability_discovery_engine import CapabilityDiscoveryEngine


# ---------------------------------------------------------------------------
# 1. 10 TEST CASES KHÁM PHÁ NĂNG LỰC & SIÊU DỮ LIỆU (DISC_01 -> DISC_10)
# ---------------------------------------------------------------------------
DISC_TEST_CASES = [
    {
        "id": "DISC_01",
        "question": "Hệ thống này có chức năng gì?",
        "expected_keywords": ["chức năng", "tra cứu", "KTXH", "so sánh", "tiến độ", "xuất"],
        "min_chips": 2,
    },
    {
        "id": "DISC_02",
        "question": "Hệ thống đang theo dõi số liệu của những ngành, lĩnh vực nào?",
        "expected_keywords": ["8 lĩnh vực", "Lao động", "Xây dựng", "Công thương", "Y tế"],
        "min_chips": 3,
    },
    {
        "id": "DISC_03",
        "question": "Số liệu báo cáo trong hệ thống có từ năm nào đến năm nào?",
        "expected_keywords": ["2024", "2025", "2026"],
        "min_chips": 2,
    },
    {
        "id": "DISC_04",
        "question": "Chỉ tiêu tỷ lệ giải ngân kinh phí khuyến công được tính như thế nào?",
        "expected_keywords": ["giải ngân", "kinh phí khuyến công", "dự toán"],
        "min_chips": 2,
    },
    {
        "id": "DISC_05",
        "question": "Hệ thống hiện có những loại biểu mẫu báo cáo nào đang áp dụng?",
        "expected_keywords": ["biểu mẫu", "ATVSLĐ", "khuyến công", "xây dựng"],
        "min_chips": 2,
    },
    {
        "id": "DISC_06",
        "question": "Tài khoản chuyên viên cấp phòng thì tôi tra cứu được những dữ liệu nào?",
        "expected_keywords": ["chuyên viên cấp phòng", "HBAC", "nội bộ", "công khai"],
        "min_chips": 2,
    },
    {
        "id": "DISC_07",
        "question": "Chatbot có hỗ trợ xuất dữ liệu ra bảng Excel hoặc file PDF không?",
        "expected_keywords": ["Excel", "Word", "PDF"],
        "min_chips": 2,
    },
    {
        "id": "DISC_08",
        "question": "Báo cáo có những trạng thái duyệt nào và trạng thái nào là số liệu chính thức?",
        "expected_keywords": ["Approved", "Pending", "Draft", "Rejected", "chính thức"],
        "min_chips": 2,
    },
    {
        "id": "DISC_09",
        "question": "Dữ liệu báo cáo hôm nay đã được cập nhật từ phần mềm tác nghiệp về kho dữ liệu tổng hợp chưa?",
        "expected_keywords": ["ETL", "cập nhật", "dữ liệu"],
        "min_chips": 2,
    },
    {
        "id": "DISC_10",
        "question": "Xin chào, tôi là cán bộ mới thì nên bắt đầu tra cứu số liệu như thế nào?",
        "expected_keywords": ["cán bộ mới", "bước", "tra cứu"],
        "min_chips": 2,
    },
]


# ---------------------------------------------------------------------------
# 2. 8 TEST CASES DANH MỤC CHIỀU DIMENSION DWH (GOLDEN_021 -> GOLDEN_028)
# ---------------------------------------------------------------------------
GOLDEN_DIMENSION_CASES = [
    {
        "id": "GOLDEN_021",
        "question": "Cán bộ cho tôi hỏi, ở tỉnh Lâm Đồng trong năm nay có những nhiệm vụ hay chương trình nào về hỗ trợ việc làm và đào tạo nghề cho người lao động vậy?",
        "expected_tables": ["dwh_internal.mission"],
    },
    {
        "id": "GOLDEN_022",
        "question": "Hộ kinh doanh buôn bán như chúng tôi thì hiện có các biểu mẫu thu thập thông tin hay tờ khai nào cần phải kê khai nộp lên xã không cán bộ?",
        "expected_tables": ["dwh_internal.collection_form"],
    },
    {
        "id": "GOLDEN_023",
        "question": "Dạ anh/chị cho em hỏi chút ạ, em mới nhận việc ở văn phòng xã nên chưa rành hệ thống lắm. Sếp vừa giao em rà soát lại để chuẩn bị triển khai cho các thôn/tổ dân phố, thì hiện tại trong năm 2026 này có những biểu mẫu thu thập thông tin nào đang được kích hoạt và còn hiệu lực áp dụng vậy ạ? Cho em xin danh sách chi tiết các mẫu phiếu đó với ạ!",
        "expected_tables": ["dwh_internal.collection_form"],
    },
    {
        "id": "GOLDEN_024",
        "question": "Dạ thưa anh/chị, bên em đang chuẩn bị làm kế hoạch theo dõi chỉ tiêu định kỳ cho xã mà sếp bảo em phải lọc riêng ra, nhưng em tìm mãi chưa thấy hết. Anh/chị cho em xin danh sách các tiêu chí đánh giá thuộc mảng nhiệm vụ Cải cách hành chính hoặc mảng Lao động việc làm trên phần mềm với ạ, em cảm ơn anh/chị nhiều!",
        "expected_tables": ["dwh_internal.criteria"],
    },
    {
        "id": "GOLDEN_025",
        "question": "Báo cáo danh sách tất cả các sở, ban, ngành và đơn vị trực thuộc tỉnh Lâm Đồng kèm mã đơn vị.",
        "expected_tables": ["dwh_internal.deparment"],
    },
    {
        "id": "GOLDEN_026",
        "question": "Danh mục các nhiệm vụ trọng tâm đã được phê duyệt triển khai trong năm 2026 gồm những nhiệm vụ nào?",
        "expected_tables": ["dwh_internal.mission"],
    },
    {
        "id": "GOLDEN_027",
        "question": "ds phong ban ubnd tinh ld",
        "expected_tables": ["dwh_internal.deparment"],
    },
    {
        "id": "GOLDEN_028",
        "question": "ds bieu mau collection form active 2026",
        "expected_tables": ["dwh_internal.collection_form"],
    },
]


@pytest.fixture(scope="module")
def pruner():
    return SchemaPruner()


@pytest.fixture(scope="module")
def steiner_builder():
    return SteinerTreeBuilder()


@pytest.fixture(scope="module")
def discovery_engine():
    return CapabilityDiscoveryEngine()


class TestCapabilityDiscoverySuite:
    """Xác thực 10 ca kiểm thử Khám phá Năng lực (DISC_01 -> DISC_10)."""

    @pytest.mark.parametrize("case", DISC_TEST_CASES, ids=[c["id"] for c in DISC_TEST_CASES])
    def test_disc_cases(self, case, pruner):
        result = pruner.prune_schema(prompt=case["question"], user_ctx={"tenant_code": "68"})
        assert isinstance(result, CatalogPrunedDTO)
        assert result.discovery_response is not None
        assert len(result.discovery_response) > 20
        # Xác nhận có action chips hỗ trợ tương tác 1 chạm
        assert len(result.suggested_action_chips) >= case["min_chips"]
        # Xác nhận độ trễ < 50ms (Zero Fact SQL)
        assert result.latency_ms < 50.0

        # Kiểm tra từ khóa bắt buộc
        resp_lower = result.discovery_response.lower()
        matched_kw = [kw for kw in case["expected_keywords"] if kw.lower() in resp_lower]
        assert len(matched_kw) >= 1, f"Không khớp từ khóa nào trong {case['expected_keywords']}"


class TestDimensionCatalogSuite:
    """Xác thực 8 ca kiểm thử Tra cứu Danh mục Bảng Chiều (GOLDEN_021 -> GOLDEN_028)."""

    @pytest.mark.parametrize("case", GOLDEN_DIMENSION_CASES, ids=[c["id"] for c in GOLDEN_DIMENSION_CASES])
    def test_golden_dimension_cases(self, case, pruner):
        result = pruner.prune_schema(prompt=case["question"], user_ctx={"tenant_code": "68"})
        assert isinstance(result, CatalogPrunedDTO)
        
        # Xác nhận tập bảng được chọn bao phủ 100% expected_tables
        for exp_tbl in case["expected_tables"]:
            tbl_simple = exp_tbl.split(".")[-1]
            found = any(tbl_simple in st for st in result.selected_tables)
            assert found, f"Bảng {exp_tbl} không xuất hiện trong selected_tables: {result.selected_tables}"

        # Xác nhận có DDL lát cắt tối thiểu
        assert len(result.schema_slice_ddl) > 0


class TestSteinerTreeBridgeTables:
    """Xác thực 5 ca kiểm thử Steiner Tree tự động kết nối và bù đắp Bridge Tables."""

    def test_bridge_fact_to_deparment(self, steiner_builder):
        """1. fact_report_criteria -> deparment: bắt buộc có office làm cầu nối."""
        nodes, bridges, joins = steiner_builder.resolve_connected_subgraph(
            ["dwh_internal.fact_report_criteria", "dwh_internal.deparment"]
        )
        assert "dwh_internal.office" in nodes or "office" in nodes
        assert any("office" in b for b in bridges)
        assert len(joins) >= 2

    def test_bridge_fact_to_collection_form(self, steiner_builder):
        """2. fact_report_criteria -> collection_form: bắt buộc có report làm cầu nối."""
        nodes, bridges, joins = steiner_builder.resolve_connected_subgraph(
            ["dwh_internal.fact_report_criteria", "dwh_internal.collection_form"]
        )
        assert "dwh_internal.report" in nodes or "report" in nodes
        assert any("report" in b for b in bridges)
        assert len(joins) >= 2

    def test_bridge_office_to_criteria(self, steiner_builder):
        """3. office -> criteria: bắt buộc có fact_report_criteria làm cầu nối."""
        nodes, bridges, joins = steiner_builder.resolve_connected_subgraph(
            ["dwh_internal.office", "dwh_internal.criteria"]
        )
        assert "dwh_internal.fact_report_criteria" in nodes or "fact_report_criteria" in nodes
        assert any("fact_report_criteria" in b for b in bridges)

    def test_bridge_deparment_to_criteria(self, steiner_builder):
        """4. deparment -> criteria: bắt buộc có cả office và fact_report_criteria."""
        nodes, bridges, joins = steiner_builder.resolve_connected_subgraph(
            ["dwh_internal.deparment", "dwh_internal.criteria"]
        )
        assert any("office" in n for n in nodes)
        assert any("fact_report_criteria" in n for n in nodes)
        assert len(bridges) >= 2

    def test_single_table_no_redundant_bridge(self, steiner_builder):
        """5. Bảng đơn lẻ criteria: không chèn bảng cầu nối dư thừa."""
        nodes, bridges, joins = steiner_builder.resolve_connected_subgraph(
            ["dwh_internal.criteria"]
        )
        assert len(nodes) == 1
        assert len(bridges) == 0
        assert len(joins) == 0


class TestStage4SnapshotBaseline:
    """Xác thực và sinh Snapshot Baseline Stage 4 (CatalogPrunedDTO) theo Master Plan."""

    def test_generate_and_verify_stage_4_snapshot(self, pruner):
        # Nạp snapshot từ Stage 3 hoặc sử dụng câu hỏi chuẩn mực của Golden Quest 001
        prompt = "Năm 2025, tổng số người được đào tạo từ nguồn kinh phí khuyến công tại Phòng Kinh tế là bao nhiêu?"
        user_ctx = {"tenant_code": "68", "department_code": "68-1-02", "office_id": "a0000000-0000-0000-0000-000000000001"}
        trace_id = "trace_snapshot_stage4_001"

        res = pruner.prune_schema(prompt=prompt, user_ctx=user_ctx, trace_id=trace_id)
        assert isinstance(res, CatalogPrunedDTO)
        assert len(res.selected_tables) >= 2
        assert any("fact_report_criteria" in t for t in res.selected_tables)
        assert any("office" in t for t in res.selected_tables or res.bridge_tables)
        assert len(res.schema_slice_ddl) > 50
        assert len(res.data_contracts) >= 2

        # Xuất file snapshot baseline Stage 4
        snapshot_dir = Path(__file__).resolve().parent / "snapshots" / "stage_4_catalog"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_file = snapshot_dir / "snapshot_baseline.json"

        with open(snapshot_file, "w", encoding="utf-8") as f:
            json.dump(res.model_dump(), f, ensure_ascii=False, indent=2)

        assert snapshot_file.exists()
        assert snapshot_file.stat().st_size > 100
