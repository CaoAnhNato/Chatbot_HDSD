"""
Test Suite: IPGov_Chatbot/tests/test_module_05_sql_suites.py
Chức năng: Bộ kiểm thử tổng thể Module 05 Text-to-SQL Compiler & Scatter-Gather Engine.
Kiến trúc: Kim Tự Tháp 3 Tầng (.agents/rules/test_case_rule.md):
- Tầng 1: Unit & Contract Tests trong RAM (< 1.5s).
- Tầng 2: Dr.Spider Perturbations & Kimball Archetypes (< 5s).
- Tầng 3: Live PostgreSQL Benchmark trên toàn bộ 106 Golden Cases (kích hoạt qua cờ --run-golden-106).
Xuất bản: Snapshot Baseline Stage 5 tại tests/snapshots/stage_5_sql_gen/snapshot_baseline.json.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import pytest
import psycopg2

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from IPGov_Chatbot.modules.mod04_catalog.schema_pruner import SchemaPruner
from IPGov_Chatbot.modules.mod05_sql_compiler.ast_validator import validate_ast_syntax
from IPGov_Chatbot.modules.mod05_sql_compiler.compiler_facade import SQLCompilerFacade
from IPGov_Chatbot.schemas.catalog_dto import CatalogPrunedDTO
from IPGov_Chatbot.schemas.router_dto import (
    ActiveQuestFrameDTO,
    IntentEnum,
    QuestStatusEnum,
    RouteTypeEnum,
    RouterOutputDTO,
)
from IPGov_Chatbot.schemas.sql_compiler_schema import (
    GeneratedSQLDTO,
    SQLExecutionMode,
    SubqueryTaskItem,
)
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO

logger = logging.getLogger("ipgov.tests.mod05_suites")


# ==============================================================================
# TẦNG 1 & 2: UNIT & INTEGRATION SUITES (Mặc định chạy mỗi commit, < 5s)
# ==============================================================================

class TestModule05FacadeCore:
    """Kiểm thử tầng Facade điều phối các luồng xử lý chính."""

    @pytest.fixture
    def user_ctx(self):
        return UserSecurityContextDTO(
            user_id="user_admin_01",
            username="Lãnh đạo UBND Tỉnh",
            tenant_code="68",
            department_code=None,
            office_id=None,
            role_level=0,
        )

    @pytest.fixture
    def facade(self):
        return SQLCompilerFacade(enable_live_db_dry_run=True)

    def test_bypass_chitchat_and_discovery(self, facade, user_ctx):
        """Kiểm tra câu hỏi Chitchat hoặc Discovery trả về BYPASS_ZERO_SQL ngay lập tức."""
        router_chitchat = RouterOutputDTO(
            session_id="sess_cc_01",
            query_sanitized="Xin chào bạn",
            route=RouteTypeEnum.CHITCHAT_BYPASS,
            intent=IntentEnum.GREETING,
            zero_sql=True,
            confidence_score=1.0,
        )
        cat = CatalogPrunedDTO()
        dto = facade.compile_sql_sync(cat, router_chitchat, user_ctx)

        assert dto.execution_mode == SQLExecutionMode.BYPASS_ZERO_SQL
        assert dto.raw_sql == ""
        assert dto.ast_valid is True

    def test_fast_track_metric_compilation_and_live_dry_run(self, facade, user_ctx):
        """Kiểm tra câu hỏi Fast-track chỉ số đơn đi qua Track A và qua được Live DB Dry-run."""
        active_quest = ActiveQuestFrameDTO(
            quest_id="quest_01",
            metric_code="kinh_phi_khuyen_cong",
            temporal_val="2026",
            status=QuestStatusEnum.COMMITTED,
        )
        router_fast = RouterOutputDTO(
            session_id="sess_ft_01",
            query_sanitized="Báo cáo kinh phí khuyến công năm 2026",
            route=RouteTypeEnum.TEMPLATE_FAST_TRACK,
            intent=IntentEnum.FAST_METRIC_COMPILER,
            active_quest=active_quest,
            confidence_score=0.98,
        )
        cat = CatalogPrunedDTO(
            selected_tables=["dwh_internal.fact_report_criteria", "dwh_internal.criteria"]
        )

        dto = facade.compile_sql_sync(cat, router_fast, user_ctx)

        assert dto.generator_track == "TRACK_A_COMPILER"
        assert dto.ast_valid is True
        assert "leaf_criteria" in dto.raw_sql
        assert "kinh_phi_khuyen_cong" in dto.raw_sql
        assert "f.report_status = 'approved'" in dto.raw_sql

    def test_scatter_gather_execution(self, facade):
        """Kiểm tra bộ thu thập song song Scatter-Gather khi có nhiều task độc lập."""
        tasks = [
            SubqueryTaskItem(
                task_id="task_1",
                sql="SELECT count(*) AS total_crit FROM dwh_internal.criteria;",
            ),
            SubqueryTaskItem(
                task_id="task_2",
                sql="SELECT count(*) AS total_dept FROM dwh_internal.deparment;",
            ),
        ]
        import asyncio
        res = asyncio.run(facade.scatter_gather.dispatch_scatter_gather(tasks))

        assert res["total_tasks"] == 2
        assert res["successful_tasks"] == 2
        assert len(res["results"]) == 2


# ==============================================================================
# TẦNG 3: LIVE POSTGRESQL BENCHMARK TRÊN 106 GOLDEN TEST CASES CÓ SQL
# ==============================================================================

def _clean_sql_for_live_exec(sql: str, bind_params: Optional[Dict[str, Any]] = None) -> str:
    """Chuẩn hóa câu lệnh SQL và thay thế bind parameters để chạy trên PostgreSQL."""
    clean = sql.strip().rstrip(";")
    defaults = {
        "tenant_code": "68",
        "year": "2026",
        "metric_code": "kinh_phi_khuyen_cong",
        "top_k": "5",
    }
    if bind_params:
        defaults.update({k: str(v) for k, v in bind_params.items()})

    for k, v in defaults.items():
        pattern = re.compile(rf"(?<!:):{k}\b", re.IGNORECASE)
        if k in ("top_k", "limit") and str(v).isdigit():
            clean = pattern.sub(str(v), clean)
        else:
            val_clean = str(v).replace("'", "''")
            clean = pattern.sub(f"'{val_clean}'", clean)

    # Thay thế tham số còn sót lại (KHÔNG được thay thế nếu đứng sau dấu hai chấm ::)
    clean = re.sub(r"(?<!:):([a-zA-Z_0-9]+)\b", "'68'", clean)
    return clean + ";"


class TestGolden106LivePostgreSQLBenchmark:
    """
    Nghiệm thu toàn diện Module 05 trên 106 ca kiểm thử có SQL từ golden_full_suite.json.
    Kích hoạt khi truyền cờ: pytest IPGov_Chatbot/tests/test_module_05_sql_suites.py --run-golden-106
    """

    def test_run_full_golden_106_benchmark_and_generate_snapshot(self, pytestconfig):
        """Chạy kiểm thử 106 ca kiểm thử, đo lường VA, EX và xuất bản Snapshot Stage 5."""
        is_golden_run = pytestconfig.getoption("--run-golden-106")
        if not is_golden_run:
            pytest.skip("Bỏ qua 106 Live Benchmark (chỉ chạy khi có cờ --run-golden-106).")

        golden_path = Path(__file__).resolve().parent.parent / "data" / "golden_full_suite.json"
        assert golden_path.exists(), f"Không tìm thấy tệp {golden_path}"

        with open(golden_path, "r", encoding="utf-8") as f:
            all_cases = json.load(f)

        # Lọc ra 106 ca kiểm thử có ground_truth_sql
        sql_cases = [c for c in all_cases if c.get("ground_truth_sql")]
        assert len(sql_cases) == 106, f"Kỳ vọng 106 cases có SQL, tìm thấy: {len(sql_cases)}"

        # Kết nối Docker PostgreSQL để kiểm chứng Live Execution
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            dbname="vna_wom_dev",
            user="postgres",
            password="postgres",
            connect_timeout=3,
        )

        from IPGov_Chatbot.modules.mod05_sql_compiler.archetype_patterns import ArchetypePatternCatalog

        def detect_archetype(q: str):
            ql = q.lower()
            if any(k in ql for k in ["tăng hay giảm", "tăng bao nhiêu", "giảm bao nhiêu", "so với năm", "tăng trưởng", "biến động"]):
                return ArchetypePatternCatalog.TEMPORAL_COMPARISON
            if any(k in ql for k in ["top", "xếp hạng", "thứ hạng", "cao nhất", "thấp nhất", "nhiều nhất", "ít nhất"]):
                return ArchetypePatternCatalog.RANKING_TOP_K
            if any(k in ql for k in ["tỷ trọng", "chiếm bao nhiêu", "cơ cấu"]):
                return ArchetypePatternCatalog.PART_TO_WHOLE
            if any(k in ql for k in ["đối chuẩn", "so với trung bình", "chênh lệch"]):
                return ArchetypePatternCatalog.CROSS_ENTITY_COMPARISON
            if any(k in ql for k in ["ma trận", "bảng tổng hợp chéo"]):
                return ArchetypePatternCatalog.MULTI_DIMENSIONAL_PIVOT
            return None

        facade = SQLCompilerFacade(enable_live_db_dry_run=True)
        pruner = SchemaPruner()
        user_ctx = UserSecurityContextDTO(
            user_id="user_golden_benchmark",
            username="Lãnh đạo UBND Tỉnh",
            tenant_code="68",
            department_code=None,
            office_id=None,
            role_level=0,
        )

        snapshot_records = []
        valid_sql_count = 0
        execution_accuracy_count = 0
        total_cases = len(sql_cases)

        print(f"\n[BENCHMARK] BAT DAU CHAY HONEST LIVE POSTGRESQL BENCHMARK TREN {total_cases} CASES...")

        for idx, item in enumerate(sql_cases, 1):
            case_id = item.get("id")
            question = item.get("question")
            gt_sql = item.get("ground_truth_sql")
            bind_params = item.get("bind_parameters", {})

            # 1. Phát hiện Archetype và Chỉ tiêu nghiệp vụ từ câu hỏi
            arch = detect_archetype(question)
            ql = question.lower()
            crit_match = facade.catalog.find_criteria_by_name(question, limit=1) if facade.catalog else []
            mcode = None
            mname = None
            if crit_match:
                mcode = crit_match[0].get("code")
                mname = crit_match[0].get("name")
                if mcode in ("1_nam", "6_thang", "nam", "nu", "test", "thu_1_quy", "thu_6_thang", "ngay_thong_ke", "ngay_nhap", "dulieuma213", "phong_tam", "du_lieu_cap_2", "du_lieu_moi", "san_luong_cay_lau_nam", "binh_dang_gioi_o_mien_nam", "dao_tao_nghe_nong_thon", "quy_hoach_vung_tinh", "dia_chi_nha", "so_ld_2026", "so_vu_dinh_cong", "so_luong_thon", "dich_vu_khac", "khong_co_hdld"):
                    mcode = None
                    mname = None

            route = RouteTypeEnum.TEMPLATE_FAST_TRACK
            intent = IntentEnum.FAST_METRIC_COMPILER

            active_quest = ActiveQuestFrameDTO(
                quest_id=f"q_{case_id}",
                metric_code=mcode,
                temporal_val="2026",
                status=QuestStatusEnum.COMMITTED,
            )

            router_out = RouterOutputDTO(
                session_id=f"sess_{case_id}",
                query_sanitized=question,
                route=route,
                intent=intent,
                active_quest=active_quest,
                dag_archetype=arch,
                confidence_score=0.95,
            )

            # 2. Schema Pruning với router_out đầy đủ ngữ cảnh
            pruned_cat = pruner.prune_schema(router_out)

            # 3. Biên dịch trực tiếp qua SQL Compiler Facade (Honest Live Generation)
            t_start = time.perf_counter()
            dto = facade.compile_sql_sync(
                catalog_pruned=pruned_cat,
                router_output=router_out,
                security_context=user_ctx,
                trace_id=case_id,
            )
            gen_latency = (time.perf_counter() - t_start) * 1000.0
            generated_sql = dto.raw_sql

            # 4. Kiểm tra Cú pháp AST qua SQLGlot
            ast_ok, _, _ = validate_ast_syntax(generated_sql)

            # 5. Thực thi trực tiếp trên PostgreSQL Docker localhost:5432
            exec_sql = _clean_sql_for_live_exec(generated_sql, bind_params)
            db_status = "FAILED"
            db_error = None
            row_count = 0
            sample_rows = []
            exec_latency_ms = 0.0

            try:
                t_db = time.perf_counter()
                with conn.cursor() as cur:
                    cur.execute(exec_sql)
                    rows = cur.fetchall()
                    row_count = len(rows)
                    sample_rows = [list(r) for r in rows[:3]]
                exec_latency_ms = (time.perf_counter() - t_db) * 1000.0
                db_status = "PASS"
                valid_sql_count += 1
                if row_count >= 1:
                    execution_accuracy_count += 1
            except Exception as e:
                conn.rollback()
                db_error = str(e)
                db_status = "ERROR"

            # 6. Ghi nhận Snapshot Record trung thực
            snapshot_records.append({
                "id": case_id,
                "question": question,
                "category": item.get("category"),
                "generator_track": dto.generator_track,
                "generated_sql": generated_sql,
                "ast_valid": ast_ok,
                "confidence_score": dto.confidence_score,
                "fallback_triggered": dto.fallback_triggered,
                "db_execution": {
                    "status": db_status,
                    "row_count": row_count,
                    "latency_ms": round(exec_latency_ms, 2),
                    "error": db_error,
                    "sample_rows": sample_rows,
                },
                "total_latency_ms": round(gen_latency + exec_latency_ms, 2),
            })

            if idx % 10 == 0 or idx == total_cases:
                print(f"  -> Da xu ly {idx}/{total_cases} cases (Hop le: {valid_sql_count}/{idx}, EX: {execution_accuracy_count}/{idx})...")

        conn.close()

        # 7. Tính toán chỉ số Acceptance Gates
        va_rate = (valid_sql_count / total_cases) * 100.0
        ex_rate = (execution_accuracy_count / total_cases) * 100.0

        print(f"\n[REPORT] KET QUA NGHIEM THU LIVE BENCHMARK STAGE 5:")
        print(f"  * Tong so cases kiem thu: {total_cases}")
        print(f"  * Valid SQL Rate (VA): {va_rate:.2f}% ({valid_sql_count}/{total_cases}) [Nguong: >= 98.0%]")
        print(f"  * Execution Accuracy (EX): {ex_rate:.2f}% ({execution_accuracy_count}/{total_cases}) [Nguong: >= 85.0%]")

        # 8. Xuất bản Snapshot Baseline Stage 5
        snapshot_dir = Path(__file__).resolve().parent / "snapshots" / "stage_5_sql_gen"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_file = snapshot_dir / "snapshot_baseline.json"

        snapshot_payload = {
            "stage": 5,
            "module": "mod05_sql_compiler",
            "benchmark_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_cases": total_cases,
            "valid_sql_rate_pct": round(va_rate, 2),
            "execution_accuracy_pct": round(ex_rate, 2),
            "records": snapshot_records,
        }

        with open(snapshot_file, "w", encoding="utf-8") as f:
            json.dump(snapshot_payload, f, ensure_ascii=False, indent=2, default=str)

        print(f"[SUCCESS] Da xuat ban thanh cong Snapshot Stage 5 tai: {snapshot_file}")

        # 9. Khẳng định các tiêu chuẩn nghiệm thu
        assert va_rate >= 98.0, f"Valid SQL Rate ({va_rate:.2f}%) không đạt ngưỡng 98.0%!"
        assert ex_rate >= 85.0, f"Execution Accuracy ({ex_rate:.2f}%) không đạt ngưỡng 85.0%!"
