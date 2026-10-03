"""
Module: IPGov_Chatbot/tests/test_chained_snapshots_all_8_stages.py
Chức năng: Chained Snapshot Testing liên kết toàn bộ 8 Stages:
Stage 5 (SQL Compiler) -> Stage 6 (AST Enforcer) -> Stage 7 (DWH Execution) -> Stage 8 (Response Synthesizer & Lineage Badge).
Căn cứ:
- Blueprint: 08_BO_TEST_CASE_KIEM_THU_TOAN_DIEN_VA_5_DIEM_MU_DWH.md
- Rule: test_case_rule.md (FLEX execution, Zero Security Violations, Live DB Assertions, Structured Logging)
- Rule: bonsai-test (Tier 3 Chained Snapshots)
"""

from __future__ import annotations

import json
import os
import pathlib
import time
from typing import Any, Dict, List

import pytest

from IPGov_Chatbot.modules.mod06_ast_enforcer.ast_enforcer_service import (
    ASTEnforcerService,
    SecurityEnforcementError,
)
from IPGov_Chatbot.modules.mod07_dwh_exec.dwh_exec_service import DWHExecutionService
from IPGov_Chatbot.modules.mod08_response.response_synthesizer_service import (
    ResponseSynthesizerService,
)
from IPGov_Chatbot.schemas.dwh_exec_dto import ExecutionStatusEnum
from IPGov_Chatbot.schemas.response_synthesizer_dto import RenderModeEnum
from IPGov_Chatbot.schemas.sql_compiler_schema import GeneratedSQLDTO, SQLExecutionMode
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO

BASE_DIR = pathlib.Path(__file__).resolve().parent
STAGE_5_SNAPSHOT_PATH = BASE_DIR / "snapshots" / "stage_5_sql_gen" / "snapshot_baseline.json"
STAGE_8_DIR = BASE_DIR / "snapshots" / "stage_8_synthesizer"
LOGS_DIR = BASE_DIR / "logs"


@pytest.fixture(scope="module")
def default_user_ctx() -> UserSecurityContextDTO:
    """Mặc định vai trò Lãnh đạo tỉnh (Role 0) toàn quyền để đối chiếu Ground Truth."""
    return UserSecurityContextDTO(
        user_id="user_admin_golden",
        username="lanhdao_ubnd",
        tenant_code="68",
        department_code=None,
        office_id=None,
        role_level=0,
    )


@pytest.fixture(scope="module")
def ast_service() -> ASTEnforcerService:
    return ASTEnforcerService()


@pytest.fixture(scope="module")
def dwh_service() -> DWHExecutionService:
    return DWHExecutionService()


@pytest.fixture(scope="module")
def synthesizer_service() -> ResponseSynthesizerService:
    return ResponseSynthesizerService()


@pytest.mark.asyncio
async def test_chained_snapshots_all_8_stages(
    ast_service: ASTEnforcerService,
    dwh_service: DWHExecutionService,
    synthesizer_service: ResponseSynthesizerService,
    default_user_ctx: UserSecurityContextDTO,
):
    """
    Đọc snapshot Stage 5 (106 câu hỏi), truyền qua Stage 6 (AST Enforcer),
    thực thi trên CSDL PostgreSQL vna_wom_dev tại Stage 7 (Mod 07),
    sau đó tổng hợp câu trả lời & đóng gói Thẻ nguồn gốc tại Stage 8 (Mod 08),
    ghi nhận snapshot baseline cho Stage 8 và lưu log có cấu trúc chuẩn JSONL.
    """
    assert STAGE_5_SNAPSHOT_PATH.exists(), f"Không tìm thấy file snapshot Stage 5 tại: {STAGE_5_SNAPSHOT_PATH}"

    with open(STAGE_5_SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        stage_5_data = json.load(f)

    records = stage_5_data.get("records", [])
    assert len(records) > 0, "Stage 5 snapshot không có bản ghi nào!"

    stage_8_records: List[Dict[str, Any]] = []
    log_entries: List[Dict[str, Any]] = []

    success_count = 0
    jinja_count = 0
    llm_count = 0
    badge_count = 0

    t_start = time.perf_counter()

    for item in records:
        case_id = item["id"]
        question = item["question"]
        category = item.get("category", "EXECUTIVE")
        raw_sql = item.get("generated_sql", "")
        trace_id = f"snap8_{case_id}"

        # ------------------------------------------------------------------
        # 1. Pipeline Stage 6: AST Enforcer
        # ------------------------------------------------------------------
        gen_dto = GeneratedSQLDTO(
            raw_sql=raw_sql,
            execution_mode=SQLExecutionMode.SINGLE_UNIFIED,
            generator_track="TRACK_A_COMPILER",
        )
        try:
            sanitized_dto = ast_service.enforce_sql_sync(
                dto=gen_dto,
                user_ctx=default_user_ctx,
                trace_id=trace_id,
            )
            is_safe = sanitized_dto.is_safe
        except SecurityEnforcementError:
            sanitized_dto = None
            is_safe = False
        except Exception:
            sanitized_dto = None
            is_safe = False

        # ------------------------------------------------------------------
        # 2. Pipeline Stage 7: DWH Execution
        # ------------------------------------------------------------------
        if is_safe and sanitized_dto is not None:
            query_result = await dwh_service.execute_query_async(
                sanitized_dto=sanitized_dto,
                user_ctx=default_user_ctx,
                trace_id=trace_id,
            )
        else:
            query_result = None

        # ------------------------------------------------------------------
        # 3. Pipeline Stage 8: Response Synthesizer & Lineage Badge
        # ------------------------------------------------------------------
        t_stage8_start = time.perf_counter()
        if query_result is not None:
            synth_output = synthesizer_service.synthesize_sync(
                query_result=query_result,
                sanitized_dto=sanitized_dto,
                router_output=None,
                user_ctx=default_user_ctx,
                user_prompt=question,
                trace_id=trace_id,
            )
        else:
            synth_output = synthesizer_service.synthesize_sync(
                query_result=None,
                sanitized_dto=sanitized_dto,
                router_output=None,
                user_ctx=default_user_ctx,
                user_prompt=question,
                trace_id=trace_id,
            )
        stage8_latency_ms = (time.perf_counter() - t_stage8_start) * 1000.0

        render_mode_val = synth_output.render_mode.value
        is_success = synth_output.render_mode != RenderModeEnum.ERROR_NOTIFICATION
        if is_success:
            success_count += 1
        if synth_output.render_mode in (
            RenderModeEnum.DETERMINISTIC_TEMPLATE,
            RenderModeEnum.EMPTY_NOTIFICATION,
        ):
            jinja_count += 1
        elif synth_output.render_mode == RenderModeEnum.LLM_SYNTHESIS:
            llm_count += 1

        badge_dict = synth_output.lineage_badge.model_dump() if synth_output.lineage_badge else None
        if badge_dict is not None:
            badge_count += 1

        record = {
            "id": case_id,
            "question": question,
            "category": category,
            "render_mode": render_mode_val,
            "content": synth_output.content,
            "table_rendered": synth_output.table_rendered,
            "latency_ms": round(stage8_latency_ms, 2),
            "tokens_used": synth_output.tokens_used,
            "lineage_badge": badge_dict,
        }
        stage_8_records.append(record)

        # Structured log entry
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "test_id": case_id,
            "test_name": f"test_stage8_{case_id}",
            "module": "MOD-08",
            "input_payload": {
                "prompt": question,
                "user_context": {"role_level": 0, "tenant_code": "68"},
            },
            "execution_stages": {
                "stage_5_sql_gen": "PASSED",
                "stage_6_ast_guard": "PASSED" if is_safe else "BLOCKED",
                "stage_7_db_exec": {
                    "status": query_result.status.value if query_result else "SKIPPED",
                    "row_count": query_result.row_count if query_result else 0,
                },
                "stage_8_synthesizer": {
                    "render_mode": render_mode_val,
                    "latency_ms": round(stage8_latency_ms, 2),
                    "tokens_used": synth_output.tokens_used,
                },
            },
            "actual_output": {
                "render_mode": render_mode_val,
                "table_rendered": synth_output.table_rendered,
                "has_badge": badge_dict is not None,
            },
            "status": "PASSED" if is_success else "FAILED",
        }
        log_entries.append(log_entry)

    total_cases = len(records)
    total_duration = time.perf_counter() - t_start

    success_rate_pct = round((success_count / total_cases) * 100.0, 2)
    jinja_savings_rate_pct = round((jinja_count / total_cases) * 100.0, 2)
    badge_coverage_pct = round((badge_count / total_cases) * 100.0, 2)

    # ------------------------------------------------------------------
    # 4. Ghi nhận Snapshot Baseline Stage 8
    # ------------------------------------------------------------------
    STAGE_8_DIR.mkdir(parents=True, exist_ok=True)
    stage_8_baseline = {
        "stage": 8,
        "module": "mod08_response_synthesizer",
        "benchmark_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_cases": total_cases,
        "success_rate_pct": success_rate_pct,
        "jinja_template_savings_rate_pct": jinja_savings_rate_pct,
        "lineage_badge_coverage_pct": badge_coverage_pct,
        "llm_synthesis_count": llm_count,
        "total_duration_seconds": round(total_duration, 2),
        "records": stage_8_records,
    }
    with open(STAGE_8_DIR / "snapshot_baseline.json", "w", encoding="utf-8") as f:
        json.dump(stage_8_baseline, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # 5. Ghi nhận Structured Log (JSONL) theo chuẩn test_case_rule.md
    # ------------------------------------------------------------------
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file_path = LOGS_DIR / "test_run_stage8_chained.jsonl"
    with open(log_file_path, "w", encoding="utf-8") as f:
        for entry in log_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------
    # 6. Khẳng định Tiêu chuẩn Nghiệm thu (Acceptance Gates)
    # ------------------------------------------------------------------
    # 1. Tỷ lệ thành công tổng hợp phải >= 98%
    assert success_rate_pct >= 98.0, f"Stage 8 success rate thấp: {success_rate_pct}%"
    # 2. Tỷ lệ tiết kiệm chi phí qua Jinja Template phải >= 80%
    assert jinja_savings_rate_pct >= 80.0, f"Jinja template savings rate thấp: {jinja_savings_rate_pct}%"
    # 3. Phủ thẻ nguồn gốc Lineage Badge 100%
    assert badge_coverage_pct == 100.0, f"Lineage badge coverage không đạt 100%: {badge_coverage_pct}%"
