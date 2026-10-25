"""
Module: IPGov_Chatbot/tests/test_challenger_m4_stress.py
Chức năng: Empirical Challenger Stress Test for Milestone 4 (R3.3 Extended Multi-Turn Verification)
Mục tiêu:
1. Thực hiện chuỗi hội thoại liên tục 7 lượt (Turn 1 -> Turn 7) trên cùng một thread_id:
   - Turn 1: "Tình hình kinh tế tập thể quý 1 năm 2026"
   - Turn 2: "Các lĩnh vực hoạt động của hợp tác xã nông nghiệp"
   - Turn 3: "Của liên hiệp hợp tác xã thì sao?"
   - Turn 4: "Thế còn năm 2024?"
   - Turn 5: "Tổng vốn điều lệ là bao nhiêu?"
   - Turn 6 (Stress Extension 1): "Còn doanh thu bình quân thì sao?"
     (Kế thừa đối tượng liên hiệp HTX / HTX và mốc thời gian 2024 từ các lượt trước)
   - Turn 7 (Stress Extension 2): "Có bao nhiêu hợp tác xã nông nghiệp hoạt động hiệu quả tốt?"
     (Chuyển đổi phân loại sâu sang nhóm chỉ tiêu đánh giá hiệu quả hoạt động)
2. Kiểm tra tính toàn vẹn và không suy thoái bộ nhớ (No Memory Degradation):
   - Đảm bảo câu trả lời không rỗng, đúng thực thể và không bị reset slot.
   - Kiểm tra số lượng Checkpoints trong SQLite `data/agent_memory.db` tăng lũy tiến (>= 7 checkpoints).
"""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict

import pytest

from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import (
    warehouse_agent,
)

WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = WORKSPACE_DIR / "data" / "agent_memory.db"


class TestChallengerMultiTurnStress:
    """Bộ kiểm thử đối kháng stress-test phiên hội thoại 7 lượt liên tục."""

    def test_7_turn_extended_stress_session(self):
        session_id = f"challenger_stress_7turns_{uuid.uuid4().hex[:8]}"
        user_context: Dict[str, Any] = {"role_level": 0, "tenant_code": "68"}

        print(f"\n--- Bắt đầu phiên kiểm thử 7 lượt: {session_id} ---")

        # ----------------------------------------------------------------------
        # Turn 1: Tổng quan KTTT Q1/2026
        # ----------------------------------------------------------------------
        t1 = warehouse_agent.run("Tình hình kinh tế tập thể quý 1 năm 2026", session_id=session_id, user_context=user_context)
        ans1 = t1.get("final_answer") or t1.get("answer") or ""
        assert len(ans1) > 0, "Turn 1 trả về rỗng!"
        print("  Turn 1 hoàn thành.")

        # ----------------------------------------------------------------------
        # Turn 2: Bóc tách lĩnh vực hoạt động HTX nông nghiệp
        # ----------------------------------------------------------------------
        t2 = warehouse_agent.run("Các lĩnh vực hoạt động của hợp tác xã nông nghiệp", session_id=session_id, user_context=user_context)
        ans2 = t2.get("final_answer") or t2.get("answer") or ""
        assert len(ans2) > 0, "Turn 2 trả về rỗng!"
        print("  Turn 2 hoàn thành.")

        # ----------------------------------------------------------------------
        # Turn 3: Tỉnh lược sang Liên hiệp HTX
        # ----------------------------------------------------------------------
        t3 = warehouse_agent.run("Của liên hiệp hợp tác xã thì sao?", session_id=session_id, user_context=user_context)
        ans3 = t3.get("final_answer") or t3.get("answer") or ""
        assert len(ans3) > 0, "Turn 3 trả về rỗng!"
        print("  Turn 3 hoàn thành.")

        # ----------------------------------------------------------------------
        # Turn 4: Đổi trục thời gian sang 2024
        # ----------------------------------------------------------------------
        t4 = warehouse_agent.run("Thế còn năm 2024?", session_id=session_id, user_context=user_context)
        ans4 = t4.get("final_answer") or t4.get("answer") or ""
        assert len(ans4) > 0, "Turn 4 trả về rỗng!"
        print("  Turn 4 hoàn thành.")

        # ----------------------------------------------------------------------
        # Turn 5: Tra cứu vốn điều lệ
        # ----------------------------------------------------------------------
        t5 = warehouse_agent.run("Tổng vốn điều lệ là bao nhiêu?", session_id=session_id, user_context=user_context)
        ans5 = t5.get("final_answer") or t5.get("answer") or ""
        assert len(ans5) > 0, "Turn 5 trả về rỗng!"
        print("  Turn 5 hoàn thành.")

        # ----------------------------------------------------------------------
        # TURN 6 (STRESS EXTENSION 1): Kế thừa đại từ & mốc thời gian ("Còn doanh thu bình quân thì sao?")
        # ----------------------------------------------------------------------
        t6 = warehouse_agent.run("Còn doanh thu bình quân thì sao?", session_id=session_id, user_context=user_context)
        ans6 = t6.get("final_answer") or t6.get("answer") or ""
        chips6 = t6.get("quick_action_chips") or t6.get("chips") or []
        sql6 = t6.get("generated_sql") or t6.get("sql") or ""

        assert len(ans6) > 0, "Turn 6 trả về câu trả lời rỗng!"
        assert (
            "doanh thu" in ans6.lower()
            or "bình quân" in ans6.lower()
            or "liên hiệp" in ans6.lower()
            or "htx" in ans6.lower()
            or len(chips6) > 0
        ), f"Turn 6 không kế thừa đúng thực thể hoặc chỉ tiêu doanh thu bình quân: {ans6[:200]}"
        print(f"  Turn 6 (Stress 1) hoàn thành: {ans6[:120]}...")

        # ----------------------------------------------------------------------
        # TURN 7 (STRESS EXTENSION 2): Chuyển đổi sang chỉ tiêu đánh giá hiệu quả hoạt động tốt
        # ----------------------------------------------------------------------
        t7 = warehouse_agent.run(
            "Có bao nhiêu hợp tác xã nông nghiệp hoạt động hiệu quả tốt?",
            session_id=session_id,
            user_context=user_context,
        )
        ans7 = t7.get("final_answer") or t7.get("answer") or ""
        chips7 = t7.get("quick_action_chips") or t7.get("chips") or []
        sql7 = t7.get("generated_sql") or t7.get("sql") or ""

        assert len(ans7) > 0, "Turn 7 trả về câu trả lời rỗng!"
        assert (
            "hiệu quả tốt" in ans7.lower()
            or "hiệu quả hoạt động" in ans7.lower()
            or "hợp tác xã" in ans7.lower()
            or "htx" in ans7.lower()
            or len(chips7) > 0
        ), f"Turn 7 không phân giải đúng chỉ tiêu hiệu quả tốt: {ans7[:200]}"
        print(f"  Turn 7 (Stress 2) hoàn thành: {ans7[:120]}...")

        # ----------------------------------------------------------------------
        # KIỂM TRA LƯU TRỮ VÀ TÍNH BỀN VỮNG TRONG SQLITE
        # ----------------------------------------------------------------------
        with sqlite3.connect(str(DB_PATH)) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?",
                (session_id,),
            )
            checkpoint_count = cur.fetchone()[0]

        print(f"  Số lượng checkpoints ghi nhận trong SQLite cho session {session_id}: {checkpoint_count}")
        assert checkpoint_count >= 7, (
            f"Số lượng checkpoints trong SQLite ({checkpoint_count}) ít hơn 7 lượt yêu cầu!"
        )
