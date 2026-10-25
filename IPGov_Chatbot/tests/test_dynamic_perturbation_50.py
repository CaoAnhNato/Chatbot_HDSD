# -*- coding: utf-8 -*-
"""
Dynamic Perturbation Test Harness (50 Cases) for AC2:
Warehouse-Grounded NLU & Dynamic Perturbation Suite

Tests 10 Quests x 5 variations (Base, +Noise, -Reduce, ~Invert, *Combo) = 50 test cases:
- QUEST-E01: Lĩnh vực HTX (8 lĩnh vực)
- QUEST-E02: Mức đánh giá hiệu quả HTX (4 mức)
- QUEST-E03: Loại diện tích muối (2 loại)
- QUEST-E04: Lĩnh vực THT (8 lĩnh vực)
- QUEST-E05: Mức hiệu quả THT (3 mức)
- QUEST-E06: Lĩnh vực LHHTX (8 lĩnh vực)
- QUEST-E07: Lĩnh vực trang trại (7 lĩnh vực)
- QUEST-E08: Loại sản lượng muối (2 loại)
- QUEST-D01: Lũy kế tổng số lượng chủ thể (must resolve to 'Lũy kế  tổng số lượng chủ thể đến thời điểm báo cáo', never leaf 5-star or annual)
- QUEST-D02: Lũy kế tổng số lượng sản phẩm OCOP (must resolve to 'Lũy kế  tổng số lượng sản phẩm OCOP đến thời điểm báo cáo', never annual)

Assertions:
- For E01-E08: verify exact count returned in natural summary, bold names present, 6-column markdown table generated, zero fallback/scalar failure.
- For D01-D02: verify Top 1 candidate is cumulative parent metric without star ratings.
- Zero test-case leakage and zero regex/keyword shortcuts (assert dynamic generalization).
"""

import sys
from pathlib import Path
from typing import Any, Dict, List

# Reconfigure stdout/stderr to utf-8 for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog
from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import WarehouseLangGraphAgent


# --------------------------------------------------------------------------
# 50-Case Dynamic Perturbation Matrix Definition
# --------------------------------------------------------------------------
PERTURBATION_MATRIX_50 = [
    # ----------------------------------------------------------------------
    # QUEST-E01: Lĩnh vực của HTX (8 lĩnh vực)
    # ----------------------------------------------------------------------
    {
        "quest_id": "QUEST-E01",
        "variation": "Base",
        "query": "bạn hãy cho tôi biết số lĩnh vực của HTX",
        "type": "BREAKDOWN",
        "expected_root": "HTX",
        "expected_count": 8,
        "expected_child_names": ["Trồng trọt", "Chăn nuôi", "Lâm nghiệp", "Thủy sản", "Diêm nghiệp", "Chế biến nông sản", "Nước sạch NT", "Tổng hợp"],
    },
    {
        "quest_id": "QUEST-E01",
        "variation": "+Noise",
        "query": "Đồng chí ơi vui lòng kiểm tra và cho tôi biết số lĩnh vực của HTX hiện có trên địa bàn?",
        "type": "BREAKDOWN",
        "expected_root": "HTX",
        "expected_count": 8,
        "expected_child_names": ["Trồng trọt", "Chăn nuôi", "Lâm nghiệp", "Thủy sản", "Diêm nghiệp", "Chế biến nông sản", "Nước sạch NT", "Tổng hợp"],
    },
    {
        "quest_id": "QUEST-E01",
        "variation": "-Reduce",
        "query": "Số lĩnh vực HTX?",
        "type": "BREAKDOWN",
        "expected_root": "HTX",
        "expected_count": 8,
        "expected_child_names": ["Trồng trọt", "Chăn nuôi", "Lâm nghiệp", "Thủy sản", "Diêm nghiệp", "Chế biến nông sản", "Nước sạch NT", "Tổng hợp"],
    },
    {
        "quest_id": "QUEST-E01",
        "variation": "~Invert",
        "query": "Của HTX thì có bao nhiêu lĩnh vực, cho tôi biết?",
        "type": "BREAKDOWN",
        "expected_root": "HTX",
        "expected_count": 8,
        "expected_child_names": ["Trồng trọt", "Chăn nuôi", "Lâm nghiệp", "Thủy sản", "Diêm nghiệp", "Chế biến nông sản", "Nước sạch NT", "Tổng hợp"],
    },
    {
        "quest_id": "QUEST-E01",
        "variation": "*Combo",
        "query": "HTX nông nghiệp hiện nay đang phân bổ theo những ngành nghề, lĩnh vực nào?",
        "type": "BREAKDOWN",
        "expected_root": "HTX",
        "expected_count": 8,
        "expected_child_names": ["Trồng trọt", "Chăn nuôi", "Lâm nghiệp", "Thủy sản", "Diêm nghiệp", "Chế biến nông sản", "Nước sạch NT", "Tổng hợp"],
    },

    # ----------------------------------------------------------------------
    # QUEST-E02: Mức đánh giá hiệu quả HTX (4 mức)
    # ----------------------------------------------------------------------
    {
        "quest_id": "QUEST-E02",
        "variation": "Base",
        "query": "Bạn hãy cho tôi biết các mức đánh giá hiệu quả hoạt động của hợp tác xã",
        "type": "BREAKDOWN",
        "expected_root": "HTX",
        "expected_count": 4,
        "expected_child_names": ["Số HTX nông nghiệp hoạt động hiệu quả tốt", "Số HTX nông nghiệp hoạt động hiệu quả trung bình", "Số HTX nông nghiệp hoạt động kém hiệu quả", "Chưa đủ điều kiện đánh giá"],
    },
    {
        "quest_id": "QUEST-E02",
        "variation": "+Noise",
        "query": "Chào chatbot, bạn hãy cho tôi biết các mức đánh giá hiệu quả hoạt động của hợp tác xã nông nghiệp năm 2026?",
        "type": "BREAKDOWN",
        "expected_root": "HTX",
        "expected_count": 4,
        "expected_child_names": ["Số HTX nông nghiệp hoạt động hiệu quả tốt", "Số HTX nông nghiệp hoạt động hiệu quả trung bình", "Số HTX nông nghiệp hoạt động kém hiệu quả", "Chưa đủ điều kiện đánh giá"],
    },
    {
        "quest_id": "QUEST-E02",
        "variation": "-Reduce",
        "query": "Các mức đánh giá hiệu quả hoạt động hợp tác xã?",
        "type": "BREAKDOWN",
        "expected_root": "HTX",
        "expected_count": 4,
        "expected_child_names": ["Số HTX nông nghiệp hoạt động hiệu quả tốt", "Số HTX nông nghiệp hoạt động hiệu quả trung bình", "Số HTX nông nghiệp hoạt động kém hiệu quả", "Chưa đủ điều kiện đánh giá"],
    },
    {
        "quest_id": "QUEST-E02",
        "variation": "~Invert",
        "query": "Hợp tác xã có các mức đánh giá hiệu quả hoạt động nào, cho tôi biết?",
        "type": "BREAKDOWN",
        "expected_root": "HTX",
        "expected_count": 4,
        "expected_child_names": ["Số HTX nông nghiệp hoạt động hiệu quả tốt", "Số HTX nông nghiệp hoạt động hiệu quả trung bình", "Số HTX nông nghiệp hoạt động kém hiệu quả", "Chưa đủ điều kiện đánh giá"],
    },
    {
        "quest_id": "QUEST-E02",
        "variation": "*Combo",
        "query": "Hiệu quả hoạt động của HTX nông nghiệp được xếp loại theo những mức nào?",
        "type": "BREAKDOWN",
        "expected_root": "HTX",
        "expected_count": 4,
        "expected_child_names": ["Số HTX nông nghiệp hoạt động hiệu quả tốt", "Số HTX nông nghiệp hoạt động hiệu quả trung bình", "Số HTX nông nghiệp hoạt động kém hiệu quả", "Chưa đủ điều kiện đánh giá"],
    },

    # ----------------------------------------------------------------------
    # QUEST-E03: Loại diện tích muối (2 loại)
    # ----------------------------------------------------------------------
    {
        "quest_id": "QUEST-E03",
        "variation": "Base",
        "query": "Cho tôi biết đang có các loại diện tích sản xuất muối gì?",
        "type": "BREAKDOWN",
        "expected_root": "muối",
        "expected_count": 2,
        "expected_child_names": ["Diện tích muối sản xuất công nghiệp", "Diện tích muối sản xuất thủ công"],
    },
    {
        "quest_id": "QUEST-E03",
        "variation": "+Noise",
        "query": "Đồng chí tra cứu giúp tôi xem hiện tại đang có các loại diện tích sản xuất muối gì được theo dõi?",
        "type": "BREAKDOWN",
        "expected_root": "muối",
        "expected_count": 2,
        "expected_child_names": ["Diện tích muối sản xuất công nghiệp", "Diện tích muối sản xuất thủ công"],
    },
    {
        "quest_id": "QUEST-E03",
        "variation": "-Reduce",
        "query": "Các loại diện tích sản xuất muối?",
        "type": "BREAKDOWN",
        "expected_root": "muối",
        "expected_count": 2,
        "expected_child_names": ["Diện tích muối sản xuất công nghiệp", "Diện tích muối sản xuất thủ công"],
    },
    {
        "quest_id": "QUEST-E03",
        "variation": "~Invert",
        "query": "Diện tích sản xuất muối đang có những loại nào?",
        "type": "BREAKDOWN",
        "expected_root": "muối",
        "expected_count": 2,
        "expected_child_names": ["Diện tích muối sản xuất công nghiệp", "Diện tích muối sản xuất thủ công"],
    },
    {
        "quest_id": "QUEST-E03",
        "variation": "*Combo",
        "query": "Về diện tích làm muối thì hệ thống đang quản lý các hình thức diện tích nào?",
        "type": "BREAKDOWN",
        "expected_root": "muối",
        "expected_count": 2,
        "expected_child_names": ["Diện tích muối sản xuất công nghiệp", "Diện tích muối sản xuất thủ công"],
    },

    # ----------------------------------------------------------------------
    # QUEST-E04: Lĩnh vực THT (8 lĩnh vực)
    # ----------------------------------------------------------------------
    {
        "quest_id": "QUEST-E04",
        "variation": "Base",
        "query": "Liệt kê các lĩnh vực hoạt động của tổ hợp tác nông nghiệp",
        "type": "BREAKDOWN",
        "expected_root": "Tổ hợp tác",
        "expected_count": 8,
        "expected_child_names": None,
    },
    {
        "quest_id": "QUEST-E04",
        "variation": "+Noise",
        "query": "Xin hỏi hệ thống hãy liệt kê các lĩnh vực hoạt động của tổ hợp tác nông nghiệp tỉnh mình?",
        "type": "BREAKDOWN",
        "expected_root": "Tổ hợp tác",
        "expected_count": 8,
        "expected_child_names": None,
    },
    {
        "quest_id": "QUEST-E04",
        "variation": "-Reduce",
        "query": "Lĩnh vực tổ hợp tác nông nghiệp?",
        "type": "BREAKDOWN",
        "expected_root": "Tổ hợp tác",
        "expected_count": 8,
        "expected_child_names": None,
    },
    {
        "quest_id": "QUEST-E04",
        "variation": "~Invert",
        "query": "Tổ hợp tác nông nghiệp gồm những lĩnh vực hoạt động nào?",
        "type": "BREAKDOWN",
        "expected_root": "Tổ hợp tác",
        "expected_count": 8,
        "expected_child_names": None,
    },
    {
        "quest_id": "QUEST-E04",
        "variation": "*Combo",
        "query": "THT nông nghiệp hiện đang có những mảng ngành nghề nào?",
        "type": "BREAKDOWN",
        "expected_root": "Tổ hợp tác",
        "expected_count": 8,
        "expected_child_names": None,
    },

    # ----------------------------------------------------------------------
    # QUEST-E05: Mức hiệu quả THT (3 mức)
    # ----------------------------------------------------------------------
    {
        "quest_id": "QUEST-E05",
        "variation": "Base",
        "query": "Cho biết các mức xếp loại hiệu quả của tổ hợp tác",
        "type": "BREAKDOWN",
        "expected_root": "Tổ hợp tác",
        "expected_count": 3,
        "expected_child_names": None,
    },
    {
        "quest_id": "QUEST-E05",
        "variation": "+Noise",
        "query": "Đồng chí hỗ trợ cho biết các mức xếp loại hiệu quả của tổ hợp tác nông nghiệp?",
        "type": "BREAKDOWN",
        "expected_root": "Tổ hợp tác",
        "expected_count": 3,
        "expected_child_names": None,
    },
    {
        "quest_id": "QUEST-E05",
        "variation": "-Reduce",
        "query": "Mức xếp loại hiệu quả tổ hợp tác?",
        "type": "BREAKDOWN",
        "expected_root": "Tổ hợp tác",
        "expected_count": 3,
        "expected_child_names": None,
    },
    {
        "quest_id": "QUEST-E05",
        "variation": "~Invert",
        "query": "Hiệu quả của tổ hợp tác gồm các mức xếp loại nào?",
        "type": "BREAKDOWN",
        "expected_root": "Tổ hợp tác",
        "expected_count": 3,
        "expected_child_names": None,
    },
    {
        "quest_id": "QUEST-E05",
        "variation": "*Combo",
        "query": "Tổ hợp tác đánh giá hiệu quả hoạt động theo mấy mức?",
        "type": "BREAKDOWN",
        "expected_root": "Tổ hợp tác",
        "expected_count": 3,
        "expected_child_names": None,
    },

    # ----------------------------------------------------------------------
    # QUEST-E06: Lĩnh vực LHHTX (8 lĩnh vực)
    # ----------------------------------------------------------------------
    {
        "quest_id": "QUEST-E06",
        "variation": "Base",
        "query": "Liên hiệp HTX nông nghiệp gồm những lĩnh vực nào?",
        "type": "BREAKDOWN",
        "expected_root": "Liên hiệp",
        "expected_count": 8,
        "expected_child_names": None,
    },
    {
        "quest_id": "QUEST-E06",
        "variation": "+Noise",
        "query": "Chào bạn, cho tôi hỏi Liên hiệp HTX nông nghiệp hiện có những lĩnh vực nào?",
        "type": "BREAKDOWN",
        "expected_root": "Liên hiệp",
        "expected_count": 8,
        "expected_child_names": None,
    },
    {
        "quest_id": "QUEST-E06",
        "variation": "-Reduce",
        "query": "Lĩnh vực Liên hiệp HTX nông nghiệp?",
        "type": "BREAKDOWN",
        "expected_root": "Liên hiệp",
        "expected_count": 8,
        "expected_child_names": None,
    },
    {
        "quest_id": "QUEST-E06",
        "variation": "~Invert",
        "query": "Những lĩnh vực nào thuộc Liên hiệp HTX nông nghiệp?",
        "type": "BREAKDOWN",
        "expected_root": "Liên hiệp",
        "expected_count": 8,
        "expected_child_names": None,
    },
    {
        "quest_id": "QUEST-E06",
        "variation": "*Combo",
        "query": "Phân theo lĩnh vực thì Liên hiệp hợp tác xã có những ngành nào?",
        "type": "BREAKDOWN",
        "expected_root": "Liên hiệp",
        "expected_count": 8,
        "expected_child_names": None,
    },

    # ----------------------------------------------------------------------
    # QUEST-E07: Lĩnh vực trang trại (7 lĩnh vực)
    # ----------------------------------------------------------------------
    {
        "quest_id": "QUEST-E07",
        "variation": "Base",
        "query": "Trang trại nông nghiệp phân theo những lĩnh vực gì?",
        "type": "BREAKDOWN",
        "expected_root": "Trang trại",
        "expected_count": 7,
        "expected_child_names": None,
    },
    {
        "quest_id": "QUEST-E07",
        "variation": "+Noise",
        "query": "Vui lòng tra cứu giúp tôi xem trang trại nông nghiệp hiện phân theo những lĩnh vực gì?",
        "type": "BREAKDOWN",
        "expected_root": "Trang trại",
        "expected_count": 7,
        "expected_child_names": None,
    },
    {
        "quest_id": "QUEST-E07",
        "variation": "-Reduce",
        "query": "Lĩnh vực trang trại nông nghiệp?",
        "type": "BREAKDOWN",
        "expected_root": "Trang trại",
        "expected_count": 7,
        "expected_child_names": None,
    },
    {
        "quest_id": "QUEST-E07",
        "variation": "~Invert",
        "query": "Phân theo lĩnh vực gì đối với trang trại nông nghiệp?",
        "type": "BREAKDOWN",
        "expected_root": "Trang trại",
        "expected_count": 7,
        "expected_child_names": None,
    },
    {
        "quest_id": "QUEST-E07",
        "variation": "*Combo",
        "query": "Các mô hình trang trại nông nghiệp hiện nay gồm có những loại nào?",
        "type": "BREAKDOWN",
        "expected_root": "Trang trại",
        "expected_count": 7,
        "expected_child_names": None,
    },

    # ----------------------------------------------------------------------
    # QUEST-E08: Loại sản lượng muối (2 loại)
    # ----------------------------------------------------------------------
    {
        "quest_id": "QUEST-E08",
        "variation": "Base",
        "query": "Hiện có những loại sản lượng muối nào được thống kê?",
        "type": "BREAKDOWN",
        "expected_root": "muối",
        "expected_count": 2,
        "expected_child_names": ["Sản lượng muối sản xuất công nghiệp", "Sản lượng muối sản xuất thủ công"],
    },
    {
        "quest_id": "QUEST-E08",
        "variation": "+Noise",
        "query": "Đồng chí kiểm tra giúp xem hiện có những loại sản lượng muối nào được thống kê trên báo cáo?",
        "type": "BREAKDOWN",
        "expected_root": "muối",
        "expected_count": 2,
        "expected_child_names": ["Sản lượng muối sản xuất công nghiệp", "Sản lượng muối sản xuất thủ công"],
    },
    {
        "quest_id": "QUEST-E08",
        "variation": "-Reduce",
        "query": "Các loại sản lượng muối?",
        "type": "BREAKDOWN",
        "expected_root": "muối",
        "expected_count": 2,
        "expected_child_names": ["Sản lượng muối sản xuất công nghiệp", "Sản lượng muối sản xuất thủ công"],
    },
    {
        "quest_id": "QUEST-E08",
        "variation": "~Invert",
        "query": "Sản lượng muối được thống kê theo những loại nào?",
        "type": "BREAKDOWN",
        "expected_root": "muối",
        "expected_count": 2,
        "expected_child_names": ["Sản lượng muối sản xuất công nghiệp", "Sản lượng muối sản xuất thủ công"],
    },
    {
        "quest_id": "QUEST-E08",
        "variation": "*Combo",
        "query": "Có mấy loại sản lượng sản xuất muối trong kho dữ liệu?",
        "type": "BREAKDOWN",
        "expected_root": "muối",
        "expected_count": 2,
        "expected_child_names": ["Sản lượng muối sản xuất công nghiệp", "Sản lượng muối sản xuất thủ công"],
    },

    # ----------------------------------------------------------------------
    # QUEST-D01: Lũy kế tổng số lượng chủ thể (must resolve to cumulative parent)
    # ----------------------------------------------------------------------
    {
        "quest_id": "QUEST-D01",
        "variation": "Base",
        "query": "bạn hãy cho tôi biết lũy kế tổng số lượng chủ thể sản phẩm theo dữ liệu mới nhất",
        "type": "DISAMBIGUATION",
        "expected_keyword": "chủ thể",
        "expected_cumul": True,
        "forbidden_star": True,
        "forbidden_annual": True,
    },
    {
        "quest_id": "QUEST-D01",
        "variation": "+Noise",
        "query": "Chào chatbot, bạn hãy cho tôi biết lũy kế tổng số lượng chủ thể sản phẩm theo dữ liệu mới nhất được phê duyệt?",
        "type": "DISAMBIGUATION",
        "expected_keyword": "chủ thể",
        "expected_cumul": True,
        "forbidden_star": True,
        "forbidden_annual": True,
    },
    {
        "quest_id": "QUEST-D01",
        "variation": "-Reduce",
        "query": "Lũy kế tổng số lượng chủ thể sản phẩm?",
        "type": "DISAMBIGUATION",
        "expected_keyword": "chủ thể",
        "expected_cumul": True,
        "forbidden_star": True,
        "forbidden_annual": True,
    },
    {
        "quest_id": "QUEST-D01",
        "variation": "~Invert",
        "query": "Theo dữ liệu mới nhất, lũy kế tổng số lượng chủ thể sản phẩm là bao nhiêu?",
        "type": "DISAMBIGUATION",
        "expected_keyword": "chủ thể",
        "expected_cumul": True,
        "forbidden_star": True,
        "forbidden_annual": True,
    },
    {
        "quest_id": "QUEST-D01",
        "variation": "*Combo",
        "query": "Số liệu lũy kế tính đến nay của tổng số lượng chủ thể sản phẩm là bao nhiêu?",
        "type": "DISAMBIGUATION",
        "expected_keyword": "chủ thể",
        "expected_cumul": True,
        "forbidden_star": True,
        "forbidden_annual": True,
    },

    # ----------------------------------------------------------------------
    # QUEST-D02: Lũy kế tổng số lượng sản phẩm OCOP (must resolve to cumulative parent)
    # ----------------------------------------------------------------------
    {
        "quest_id": "QUEST-D02",
        "variation": "Base",
        "query": "bạn hãy cho tôi biết lũy kế tổng số lượng chủ thể sản phẩm OCOP theo dữ liệu mới nhất",
        "type": "DISAMBIGUATION",
        "expected_keyword": "sản phẩm ocop",
        "expected_cumul": True,
        "forbidden_star": True,
        "forbidden_annual": True,
    },
    {
        "quest_id": "QUEST-D02",
        "variation": "+Noise",
        "query": "Đồng chí ơi cho tôi biết số liệu lũy kế tổng số lượng sản phẩm OCOP theo dữ liệu báo cáo mới nhất?",
        "type": "DISAMBIGUATION",
        "expected_keyword": "sản phẩm ocop",
        "expected_cumul": True,
        "forbidden_star": True,
        "forbidden_annual": True,
    },
    {
        "quest_id": "QUEST-D02",
        "variation": "-Reduce",
        "query": "Lũy kế tổng số lượng sản phẩm OCOP?",
        "type": "DISAMBIGUATION",
        "expected_keyword": "sản phẩm ocop",
        "expected_cumul": True,
        "forbidden_star": True,
        "forbidden_annual": True,
    },
    {
        "quest_id": "QUEST-D02",
        "variation": "~Invert",
        "query": "Số lượng sản phẩm OCOP lũy kế tổng là bao nhiêu theo dữ liệu mới nhất?",
        "type": "DISAMBIGUATION",
        "expected_keyword": "sản phẩm ocop",
        "expected_cumul": True,
        "forbidden_star": True,
        "forbidden_annual": True,
    },
    {
        "quest_id": "QUEST-D02",
        "variation": "*Combo",
        "query": "Lũy kế đến thời điểm báo cáo thì tổng số lượng sản phẩm OCOP đạt bao nhiêu?",
        "type": "DISAMBIGUATION",
        "expected_keyword": "sản phẩm ocop",
        "expected_cumul": True,
        "forbidden_star": True,
        "forbidden_annual": True,
    },
]


@pytest.fixture(scope="module")
def catalog():
    return DuckDBSemanticCatalog()


@pytest.fixture(scope="module")
def agent():
    return WarehouseLangGraphAgent()


def execute_single_case(catalog, agent, case):
    """
    Evaluates one case from the 50-Case Dynamic Perturbation Matrix.
    Returns (status: bool, error_msg: str)
    """
    q_type = case["type"]
    query = case["query"]
    quest_id = case["quest_id"]
    variation = case["variation"]

    if q_type == "BREAKDOWN":
        # 1. Catalog breakdown resolution
        res = catalog.resolve_hierarchy_breakdown(query, tenant_code="68", year_code="2026")
        assert res is not None, f"[{quest_id}|{variation}] resolve_hierarchy_breakdown returned None for: {query}"
        assert res.get("status") == "SUCCESS", f"[{quest_id}|{variation}] status must be SUCCESS, got: {res.get('status')}"

        # 2. Check child count and root
        child_count = res.get("child_count", 0)
        expected_count = case["expected_count"]
        assert child_count == expected_count, (
            f"[{quest_id}|{variation}] Child count mismatch. Expected: {expected_count}, Got: {child_count} for: {query}"
        )

        if case.get("expected_root"):
            root_name = res.get("root_name") or ""
            assert case["expected_root"].lower() in root_name.lower(), (
                f"[{quest_id}|{variation}] Root mismatch. Expected '{case['expected_root']}', Got '{root_name}' for: {query}"
            )

        children = res.get("children", [])
        assert len(children) == expected_count, f"Children list length mismatch ({len(children)} vs {expected_count})"

        # Check child names if specified
        if case.get("expected_child_names"):
            retrieved_names = [c["name"] for c in children]
            for exp_name in case["expected_child_names"]:
                assert any(exp_name.lower() in rn.lower() for rn in retrieved_names), (
                    f"[{quest_id}|{variation}] Expected child name '{exp_name}' not found in retrieved: {retrieved_names}"
                )

        # 3. Agent response synthesis verification
        state = {
            "user_query": query,
            "inherited_year": "2026",
            "query_result": {"rows": [{"gia_tri": 100}], "executed_sql": "SELECT 1;"},
            "selected_candidate": res["parent_node"]["name"],
            "canonical_frame": None,
        }
        syn_res = agent.node_synthesize_response(state)
        final_ans = syn_res.get("final_answer", "")

        # Natural summary: must contain exact count
        assert f"**{expected_count}**" in final_ans, (
            f"[{quest_id}|{variation}] Natural summary must mention count '**{expected_count}**'. Final answer:\n{final_ans}"
        )

        # Bold names present
        for ch in children[:2]:  # check bold names
            assert f"**{ch['name']}**" in final_ans, (
                f"[{quest_id}|{variation}] Child name '**{ch['name']}**' must be bold in natural summary."
            )

        # 6-column markdown table header
        exp_table_header = "| STT | Tên chỉ tiêu | Nhóm chỉ tiêu | Giá trị mới nhất | Đơn vị thực hiện | Nhiệm vụ trọng tâm |"
        assert exp_table_header in final_ans, (
            f"[{quest_id}|{variation}] Missing 6-column table header. Final answer:\n{final_ans}"
        )

        # Tabular data structured payload
        tab_data = syn_res.get("tabular_data")
        assert tab_data is not None, f"[{quest_id}|{variation}] Missing tabular_data payload"
        assert len(tab_data.get("columns", [])) == 6, f"Expected 6 table columns, got: {len(tab_data.get('columns', []))}"
        assert len(tab_data.get("rows", [])) == expected_count, (
            f"Expected {expected_count} table rows, got: {len(tab_data.get('rows', []))}"
        )

        # Action chips (capped to 4 by senior UI design)
        chips = syn_res.get("quick_action_chips", [])
        expected_chips_count = min(expected_count, 4)
        assert len(chips) == expected_chips_count, (
            f"Expected {expected_chips_count} action chips, got {len(chips)}"
        )

        # Zero inline duplicate chips
        assert "🔘 [" not in final_ans, f"[{quest_id}|{variation}] Duplicate inline chips '🔘 [' found in final_answer"

    elif q_type == "DISAMBIGUATION":
        # Disambiguation candidate ranking check
        cands, _, _ = catalog.find_top_k_candidates(query, top_k=5, tenant_code="68")
        assert len(cands) > 0, f"[{quest_id}|{variation}] find_top_k_candidates returned no candidates for: {query}"

        top1 = cands[0]
        top1_name = top1["name"].lower()

        # Must contain cumulative keyword
        if case.get("expected_cumul"):
            assert "lũy kế" in top1_name or "đến thời điểm báo cáo" in top1_name, (
                f"[{quest_id}|{variation}] Top 1 candidate must be cumulative. Got: '{top1['name']}' (score: {top1.get('score')})"
            )

        # Must match expected subject/product keyword
        exp_kw = case.get("expected_keyword")
        if exp_kw:
            assert exp_kw.lower() in top1_name, (
                f"[{quest_id}|{variation}] Top 1 candidate must contain '{exp_kw}'. Got: '{top1['name']}'"
            )

        # Forbidden leaf star
        if case.get("forbidden_star"):
            for star in ["3 sao", "4 sao", "5 sao"]:
                assert star not in top1_name, (
                    f"[{quest_id}|{variation}] Top 1 candidate must NOT contain '{star}'. Got: '{top1['name']}'"
                )

        # Forbidden annual
        if case.get("forbidden_annual"):
            assert "trong năm" not in top1_name, (
                f"[{quest_id}|{variation}] Top 1 candidate must NOT contain 'trong năm'. Got: '{top1['name']}'"
            )


@pytest.mark.parametrize("case", PERTURBATION_MATRIX_50, ids=[f"{c['quest_id']}_{c['variation']}" for c in PERTURBATION_MATRIX_50])
def test_dynamic_perturbation_case(catalog, agent, case):
    execute_single_case(catalog, agent, case)


def test_end_to_end_agent_run_r2_r3_r4_and_dynamic_warehouse_injection(catalog, agent):
    """
    End-to-End Verification via `agent.run(query)`:
    1. R3 Breakdown E2E: 'bạn hãy cho tôi biết số lĩnh vực của HTX' -> 8 rows in tabular_data + natural summary.
    2. R4 Disambiguation E2E:
       - 'bạn hãy cho tôi biết lũy kế tổng số lượng chủ thể sản phẩm theo dữ liệu mới nhất' -> 'Lũy kế tổng số lượng chủ thể đến thời điểm báo cáo'
       - 'bạn hãy cho tôi biết lũy kế tổng số lượng chủ thể sản phẩm OCOP theo dữ liệu mới nhất' -> 'Lũy kế tổng số lượng sản phẩm OCOP đến thời điểm báo cáo'
    3. R2.4 Child Timeline Values E2E: 'Cho tôi biết Hiệu quả hoạt động của HTX nông nghiệp năm 2026?' -> snapshots contain child_values across periods.
    4. R3 Dynamic Warehouse Injection: Inserting a brand-new parent + 3 children into DuckDB RAM resolves immediately with zero code changes.
    """
    # 1. R3 Breakdown E2E
    res_e01 = agent.run("bạn hãy cho tôi biết số lĩnh vực của HTX")
    assert "**8**" in res_e01["answer"]
    assert len(res_e01["tabular_data"]["rows"]) == 8

    # 2. R4 Disambiguation E2E
    res_d01 = agent.run("bạn hãy cho tôi biết lũy kế tổng số lượng chủ thể sản phẩm theo dữ liệu mới nhất")
    assert "Lũy kế tổng số lượng chủ thể đến thời điểm báo cáo" in res_d01["answer"]
    assert "OCOP 5 sao" not in res_d01["answer"].split("\n")[0]

    res_d02 = agent.run("bạn hãy cho tôi biết lũy kế tổng số lượng chủ thể sản phẩm OCOP theo dữ liệu mới nhất")
    assert "Lũy kế tổng số lượng sản phẩm OCOP đến thời điểm báo cáo" in res_d02["answer"]
    assert "Tổng số lượng sản phẩm OCOP trong năm" not in res_d02["answer"]

    # 3. R2.4 Child Timeline Values E2E
    res_hq = agent.run("Cho tôi biết chỉ tiêu Hiệu quả hoạt động thuộc nhóm HTX nông nghiệp năm 2026?")
    card_hq = (res_hq.get("tabular_data") or {}).get("single_metric_card") or {}
    snaps_hq = card_hq.get("timeline_snapshots") or []
    assert len(snaps_hq) >= 2
    for sn in snaps_hq:
        assert "child_values" in sn and len(sn["child_values"]) >= 4

    # 4. Dynamic Warehouse Injection (Zero Hardcode Proof)
    syn_parent_id = "syn-parent-quy-mo-von-999"
    try:
        catalog.conn.execute(
            "INSERT INTO catalog_criteria_hierarchy VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                syn_parent_id,
                "so_luong_htx_phan_theo_quy_mo_von",
                "Số lượng HTX phân theo quy mô vốn",
                "root-htx-syn",
                "HTX nông nghiệp",
                "root-htx-syn",
                "HTX nông nghiệp",
                2,
                False,
                "Phát triển nông thôn",
                "Chi cục",
                "130",
            ),
        )
        for idx_s, (c_code, c_nm, c_val) in enumerate(
            [
                ("htx_quy_mo_von_lon", "HTX quy mô vốn lớn", "30"),
                ("htx_quy_mo_von_vua", "HTX quy mô vốn vừa", "60"),
                ("htx_quy_mo_von_nho", "HTX quy mô vốn nhỏ", "40"),
            ],
            1,
        ):
            catalog.conn.execute(
                "INSERT INTO catalog_criteria_hierarchy VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"syn-child-von-{idx_s}",
                    c_code,
                    c_nm,
                    syn_parent_id,
                    "Số lượng HTX phân theo quy mô vốn",
                    "root-htx-syn",
                    "HTX nông nghiệp",
                    3,
                    True,
                    "Phát triển nông thôn",
                    "Chi cục",
                    c_val,
                ),
            )
        dyn_res = catalog.resolve_hierarchy_breakdown("Cho tôi biết HTX hiện có các loại quy mô vốn nào?")
        assert dyn_res is not None and dyn_res.get("status") == "SUCCESS"
        assert dyn_res["child_count"] == 3
        assert [c["name"] for c in dyn_res["children"]] == [
            "HTX quy mô vốn lớn",
            "HTX quy mô vốn nhỏ",
            "HTX quy mô vốn vừa",
        ]
    finally:
        catalog.conn.execute(
            "DELETE FROM catalog_criteria_hierarchy WHERE id LIKE 'syn-%';"
        )


# --------------------------------------------------------------------------
# Standalone CLI Test Runner with Beautiful Scorecard
# --------------------------------------------------------------------------
def run_cli_test_suite():
    import time
    start_time = time.time()
    print("=" * 80)
    print("DYNAMIC PERTURBATION TEST RUNNER - 50 CASES (AC2 EMPIRICAL CHALLENGE)")
    print("=" * 80)

    cat = DuckDBSemanticCatalog()
    ag = WarehouseLangGraphAgent()

    results = []
    passed_count = 0
    failed_count = 0

    for idx, case in enumerate(PERTURBATION_MATRIX_50, 1):
        q_id = case["quest_id"]
        var = case["variation"]
        query = case["query"]
        q_type = case["type"]

        test_name = f"{q_id} [{var}]"
        try:
            execute_single_case(cat, ag, case)
            results.append((idx, q_id, var, q_type, query, "PASS", ""))
            passed_count += 1
            print(f"[{idx:02d}/50] PASS: {test_name}")
        except Exception as e:
            err_msg = str(e)
            results.append((idx, q_id, var, q_type, query, "FAIL", err_msg))
            failed_count += 1
            print(f"[{idx:02d}/50] FAIL: {test_name} -> {err_msg[:80]}")

    elapsed = round(time.time() - start_time, 2)
    print("\n" + "=" * 80)
    print("EXECUTION SCOREBOARD SUMMARY")
    print("=" * 80)
    print(f"Total Test Cases: 50")
    print(f"Passed:           {passed_count} / 50 ({passed_count/50*100:.1f}%)")
    print(f"Failed:           {failed_count} / 50")
    print(f"Duration:         {elapsed}s")
    print("=" * 80)

    # Print breakdown by quest
    from collections import defaultdict
    quest_stats = defaultdict(lambda: {"total": 0, "pass": 0})
    for _, q_id, var, _, _, status, _ in results:
        quest_stats[q_id]["total"] += 1
        if status == "PASS":
            quest_stats[q_id]["pass"] += 1

    print("\nPER-QUEST SCOREBOARD:")
    for q_id, stats in sorted(quest_stats.items()):
        status_sym = "[OK]" if stats["pass"] == stats["total"] else "[FAIL]"
        print(f"  {status_sym} {q_id}: {stats['pass']}/{stats['total']} passed")

    print("\n" + "=" * 80)
    if failed_count == 0:
        print("RESULT: ALL 50 DYNAMIC PERTURBATION CASES PASSED SUCCESSFULLY! (100%)")
        return 0
    else:
        print(f"RESULT: {failed_count} CASES FAILED!")
        return 1


if __name__ == "__main__":
    sys.exit(run_cli_test_suite())
