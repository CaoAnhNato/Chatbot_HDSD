"""
Unit Tests for Module 04: In-Memory Semantic Catalog, DuckDB FTS, and RapidFuzz
Căn cứ: Blueprints 03_SEMANTIC_LAYER_MDL_VA_IN_MEMORY_CATALOG.md
"""

import pytest
from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog
from IPGov_Chatbot.modules.mod04_catalog.steiner_tree_builder import SteinerTreeBuilder
from IPGov_Chatbot.modules.mod04_catalog.capability_discovery_engine import CapabilityDiscoveryEngine
from IPGov_Chatbot.modules.mod04_catalog.schema_pruner import SchemaPruner
from IPGov_Chatbot.schemas.catalog_dto import CatalogPrunedDTO


@pytest.fixture(scope="module")
def catalog():
    return DuckDBSemanticCatalog()


def test_duckdb_catalog_initialization(catalog):
    """Kiểm tra khởi tạo DuckDB và nạp dữ liệu hybrid seed."""
    assert catalog.conn is not None
    # Kiểm tra số lượng criteria nạp vào
    row = catalog.conn.execute("SELECT count(*) FROM catalog_criteria").fetchone()
    assert row[0] > 0

    # Kiểm tra số lượng department và office
    dept_count = catalog.conn.execute("SELECT count(*) FROM catalog_departments").fetchone()[0]
    office_count = catalog.conn.execute("SELECT count(*) FROM catalog_offices").fetchone()[0]
    assert dept_count > 0
    assert office_count > 0


def test_duckdb_fts_bm25_search(catalog):
    """Kiểm tra tìm kiếm thô bằng DuckDB FTS / BM25 trên siêu dữ liệu bảng."""
    results = catalog.search_tables_by_keywords("tai nạn lao động số vụ chết người")
    assert len(results) > 0
    # Phải có bảng fact_report_criteria hoặc criteria
    table_names = [r["table_name"] for r in results]
    assert any("criteria" in t for t in table_names)


def test_rapidfuzz_abbreviation_matching(catalog):
    """Kiểm tra RapidFuzz C++ phân giải các từ viết tắt công vụ."""
    # Viết tắt tnlđ -> tai_nan_lao_dong
    m = catalog.match_alias_or_abbreviation("tnlđ")
    assert m is not None
    assert "tai_nan_lao_dong" in m["code"] or "tnld" in m["code"]

    # Viết tắt dvc -> dịch vụ công
    m_dvc = catalog.match_alias_or_abbreviation("dvc")
    assert m_dvc is not None
    assert "dvc" in m_dvc["code"] or "dich_vu_cong" in m_dvc["code"]


def test_schema_pruner_full_pipeline():
    """Kiểm tra pipeline tổng thể của SchemaPruner."""
    pruner = SchemaPruner()
    res = pruner.prune_schema(
        prompt="Năm 2025, tổng số vụ tai nạn lao động tại Phòng Văn Hóa là bao nhiêu?",
        user_ctx={"tenant_code": "68", "department_code": "68-1-02"}
    )
    assert isinstance(res, CatalogPrunedDTO)
    assert "fact_report_criteria" in str(res.selected_tables)
    assert len(res.data_contracts) >= 2
    assert any("NULLIF" in c for c in res.data_contracts)
    assert any("approved" in c for c in res.data_contracts)
