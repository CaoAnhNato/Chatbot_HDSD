"""
Module: IPGov_Chatbot/tests/test_chained_snapshots_mod06_07.py
Chức năng: Chained Snapshot Testing liên kết Stage 5 -> Stage 6 (AST Enforcer) -> Stage 7 (DWH Execution).
Căn cứ:
- Blueprint: 08_BO_TEST_CASE_KIEM_THU_TOAN_DIEN_VA_5_DIEM_MU_DWH.md
- Rule: test_case_rule.md (FLEX execution, Zero Security Violations, Live DB Assertions)
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
from IPGov_Chatbot.schemas.dwh_exec_dto import ExecutionStatusEnum
from IPGov_Chatbot.schemas.sql_compiler_schema import GeneratedSQLDTO, SQLExecutionMode
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO

BASE_DIR = pathlib.Path(__file__).resolve().parent
STAGE_5_SNAPSHOT_PATH = BASE_DIR / "snapshots" / "stage_5_sql_gen" / "snapshot_baseline.json"
STAGE_6_DIR = BASE_DIR / "snapshots" / "stage_6_ast_enforcer"
STAGE_7_DIR = BASE_DIR / "snapshots" / "stage_7_dwh_exec"


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


@pytest.mark.asyncio
async def test_chained_snapshots_stage_5_to_6_and_7(
    ast_service: ASTEnforcerService,
    dwh_service: DWHExecutionService,
    default_user_ctx: UserSecurityContextDTO,
):
    """
    Đọc snapshot Stage 5 (106 câu hỏi), truyền qua Mod 06 kiên cố hóa AST,
    sau đó thực thi trên Docker CSDL PostgreSQL vna_wom_dev tại Mod 07,
    và ghi nhận 2 snapshot baselines cho Stage 6 và Stage 7.
    """
    assert STAGE_5_SNAPSHOT_PATH.exists(), f"Không tìm thấy file snapshot Stage 5 tại: {STAGE_5_SNAPSHOT_PATH}"

    with open(STAGE_5_SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        stage_5_data = json.load(f)

    records = stage_5_data.get("records", [])
    assert len(records) > 0, "Stage 5 snapshot không có bản ghi nào!"

    stage_6_records: List[Dict[str, Any]] = []
    stage_7_records: List[Dict[str, Any]] = []

    stage_6_safe_count = 0
    stage_7_success_count = 0

    t_start = time.perf_counter()

    for item in records:
        case_id = item["id"]
        question = item["question"]
        category = item.get("category", "EXECUTIVE")
        raw_sql = item.get("generated_sql", "")

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
                trace_id=f"snap_{case_id}",
            )
            is_safe = sanitized_dto.is_safe
            error_violation = None
        except SecurityEnforcementError as e:
            sanitized_dto = None
            is_safe = False
            error_violation = {
                "violation_type": e.violation_type.value,
                "message": str(e),
                "forbidden_tokens": e.forbidden_tokens,
            }
        except Exception as e:
            sanitized_dto = None
            is_safe = False
            error_violation = {
                "violation_type": "UNKNOWN_ERROR",
                "message": str(e),
                "forbidden_tokens": [],
            }

        stage_6_rec = {
            "id": case_id,
            "question": question,
            "category": category,
            "raw_sql": raw_sql,
            "sanitized_sql": sanitized_dto.sanitized_sql if sanitized_dto else "",
            "is_safe": is_safe,
            "violation": error_violation,
            "execution_mode": sanitized_dto.execution_mode.value if sanitized_dto else "BLOCKED",
        }
        stage_6_records.append(stage_6_rec)

        if is_safe:
            stage_6_safe_count += 1

        # ------------------------------------------------------------------
        # 2. Pipeline Stage 7: DWH Execution
        # ------------------------------------------------------------------
        if is_safe and sanitized_dto is not None:
            query_result = await dwh_service.execute_query_async(
                sanitized_dto=sanitized_dto,
                user_ctx=default_user_ctx,
                trace_id=f"snap_{case_id}",
            )
            stage_7_rec = {
                "id": case_id,
                "question": question,
                "category": category,
                "executed_sql": query_result.executed_sql,
                "status": query_result.status.value,
                "row_count": query_result.row_count,
                "is_empty": query_result.is_empty,
                "execution_time_ms": round(query_result.execution_time_ms, 2),
                "error_code": query_result.error_code,
                "sample_row": query_result.rows[0] if query_result.rows else None,
            }
            if query_result.status in (ExecutionStatusEnum.SUCCESS, ExecutionStatusEnum.EMPTY):
                stage_7_success_count += 1
        else:
            stage_7_rec = {
                "id": case_id,
                "question": question,
                "category": category,
                "executed_sql": "",
                "status": "BLOCKED_BY_AST",
                "row_count": 0,
                "is_empty": True,
                "execution_time_ms": 0.0,
                "error_code": "AST_SECURITY_VIOLATION",
                "sample_row": None,
            }

        stage_7_records.append(stage_7_rec)

    total_cases = len(records)
    total_duration = time.perf_counter() - t_start

    stage_6_safe_rate_pct = round((stage_6_safe_count / total_cases) * 100.0, 2)
    stage_7_success_rate_pct = round((stage_7_success_count / total_cases) * 100.0, 2)

    # ------------------------------------------------------------------
    # 3. Ghi nhận Snapshot Baseline Stage 6
    # ------------------------------------------------------------------
    STAGE_6_DIR.mkdir(parents=True, exist_ok=True)
    stage_6_baseline = {
        "stage": 6,
        "module": "mod06_ast_enforcer",
        "benchmark_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_cases": total_cases,
        "safe_ast_rate_pct": stage_6_safe_rate_pct,
        "security_violation_rate_pct": round(100.0 - stage_6_safe_rate_pct, 2),
        "records": stage_6_records,
    }
    with open(STAGE_6_DIR / "snapshot_baseline.json", "w", encoding="utf-8") as f:
        json.dump(stage_6_baseline, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # 4. Ghi nhận Snapshot Baseline Stage 7
    # ------------------------------------------------------------------
    STAGE_7_DIR.mkdir(parents=True, exist_ok=True)
    stage_7_baseline = {
        "stage": 7,
        "module": "mod07_dwh_exec",
        "benchmark_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_cases": total_cases,
        "execution_success_rate_pct": stage_7_success_rate_pct,
        "total_duration_seconds": round(total_duration, 2),
        "records": stage_7_records,
    }
    with open(STAGE_7_DIR / "snapshot_baseline.json", "w", encoding="utf-8") as f:
        json.dump(stage_7_baseline, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # 5. Khẳng định Tiêu chuẩn Nghiệm thu (Acceptance Gates)
    # ------------------------------------------------------------------
    # AST Enforcer phải giữ tỷ lệ an toàn >= 95% trên tập sinh của Mod 05
    assert stage_6_safe_rate_pct >= 95.0, f"Stage 6 safe rate thấp: {stage_6_safe_rate_pct}%"
    # DWH Execution phải thành công trên CSDL thật >= 85%
    assert stage_7_success_rate_pct >= 85.0, f"Stage 7 execution success rate thấp: {stage_7_success_rate_pct}%"
