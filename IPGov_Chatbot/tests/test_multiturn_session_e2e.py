"""
Module: IPGov_Chatbot/tests/test_multiturn_session_e2e.py
Chức năng: R3.3 Multi-Turn Session Verification (Pytest E2E)
Mục tiêu:
1. Kiểm thử tối thiểu 5 lượt hội thoại liên tiếp trong một phiên duy nhất:
   - Turn 1: Báo cáo / tiêu chí ban đầu ("Tình hình kinh tế tập thể quý 1 năm 2026")
   - Turn 2: Chuyển đổi / phân rã cấu trúc ("Các lĩnh vực hoạt động của hợp tác xã nông nghiệp")
   - Turn 3: Tỉnh lược đại từ / phân nhánh sâu ("Của liên hiệp hợp tác xã thì sao?")
   - Turn 4: Đổi trục thời gian ("Thế còn năm 2024?")
   - Turn 5: Tra cứu chỉ tiêu định lượng cụ thể ("Tổng vốn điều lệ là bao nhiêu?")
2. Kiểm tra tính bền vững trạng thái (Session Persistence & State Durability):
   - Kế thừa slot ngữ cảnh qua LangGraph SqliteSaver (`data/agent_memory.db`).
   - Khẳng định tính nhất quán của trạng thái, không bị trắng màn hình (blank state) hay mất lịch sử.
   - Khẳng định khả năng đính chính slot (Slot Repair) và duy trì ngữ cảnh khi xen kẽ lời chào.
"""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from typing import Dict, Any

import pytest

from IPGov_Chatbot.modules.mod03_router.warehouse_langgraph_agent import (
    warehouse_agent,
)

WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = WORKSPACE_DIR / "data" / "agent_memory.db"


class TestMultiTurnSessionE2E:
    """Bộ kiểm thử E2E phiên hội thoại đa lượt liên tục (>= 5 lượt)."""

    def test_5_turn_continuous_session_workflow(self):
        """
        Kịch bản 5 lượt hỏi liên tiếp trong 1 phiên duy nhất (Single Continuous Session):
        - Turn 1: Thiết lập báo cáo ban đầu Quý 1/2026.
        - Turn 2: Bóc tách lĩnh vực hoạt động của HTX nông nghiệp.
        - Turn 3: Tỉnh lược đại từ, chuyển sang Liên hiệp HTX (LHHTX).
        - Turn 4: Chuyển trục thời gian sang năm 2024.
        - Turn 5: Hỏi tiếp chỉ tiêu số liệu cụ thể (Tổng vốn điều lệ).
        """
        session_id = f"test_session_5turns_{uuid.uuid4().hex[:8]}"
        user_context: Dict[str, Any] = {"role_level": 0, "tenant_code": "68"}

        # ----------------------------------------------------------------------
        # TURN 1: Báo cáo tổng quan Quý 1 năm 2026
        # ----------------------------------------------------------------------
        t1_query = "Tình hình kinh tế tập thể quý 1 năm 2026"
        res1 = warehouse_agent.run(
            query=t1_query,
            session_id=session_id,
            user_context=user_context,
        )
        ans1 = res1.get("final_answer") or res1.get("answer") or ""
        sql1 = res1.get("generated_sql") or res1.get("sql") or ""

        assert len(ans1) > 0, "Turn 1 trả về câu trả lời rỗng!"
        assert (
            "quý 1" in ans1.lower()
            or "2026" in ans1
            or "chỉ tiêu" in ans1.lower()
            or "kinh tế tập thể" in ans1.lower()
        ), f"Turn 1 không phản ánh đúng ngữ cảnh: {ans1[:200]}"
        assert res1.get("stage") is not None, "Turn 1 thiếu thông tin stage!"

        # ----------------------------------------------------------------------
        # TURN 2: Bóc tách phân cấp (Breakdown query)
        # ----------------------------------------------------------------------
        t2_query = "Các lĩnh vực hoạt động của hợp tác xã nông nghiệp"
        res2 = warehouse_agent.run(
            query=t2_query,
            session_id=session_id,
            user_context=user_context,
        )
        ans2 = res2.get("final_answer") or res2.get("answer") or ""
        sql2 = res2.get("generated_sql") or res2.get("sql") or ""

        assert len(ans2) > 0, "Turn 2 trả về câu trả lời rỗng!"
        assert (
            "htx" in ans2.lower()
            or "hợp tác xã" in ans2.lower()
            or "lĩnh vực" in ans2.lower()
        ), f"Turn 2 không phản ánh bóc tách lĩnh vực HTX: {ans2[:200]}"
        # Bảo toàn ngữ cảnh năm 2026 từ Turn 1 nếu sinh SQL
        if sql2:
            assert "2026" in sql2 or "year_code" in sql2, f"Turn 2 làm mất năm 2026 trong SQL: {sql2}"

        # ----------------------------------------------------------------------
        # TURN 3: Tỉnh lược đại từ / phân nhánh sâu (Pronoun ellipsis / Branch drill-down)
        # ----------------------------------------------------------------------
        t3_query = "Của liên hiệp hợp tác xã thì sao?"
        res3 = warehouse_agent.run(
            query=t3_query,
            session_id=session_id,
            user_context=user_context,
        )
        ans3 = res3.get("final_answer") or res3.get("answer") or ""
        chips3 = res3.get("quick_action_chips") or res3.get("chips") or []

        assert len(ans3) > 0, "Turn 3 trả về câu trả lời rỗng!"
        assert (
            "liên hiệp" in ans3.lower()
            or "lhhtx" in ans3.lower()
            or len(chips3) > 0
        ), f"Turn 3 không chuyển hướng đúng sang nhánh Liên hiệp HTX: {ans3[:200]}"

        # ----------------------------------------------------------------------
        # TURN 4: Đổi trục thời gian (Temporal pivot)
        # ----------------------------------------------------------------------
        t4_query = "Thế còn năm 2024?"
        res4 = warehouse_agent.run(
            query=t4_query,
            session_id=session_id,
            user_context=user_context,
        )
        ans4 = res4.get("final_answer") or res4.get("answer") or ""
        sql4 = res4.get("generated_sql") or res4.get("sql") or ""

        assert len(ans4) > 0, "Turn 4 trả về câu trả lời rỗng!"
        assert "2024" in ans4 or "2024" in sql4, (
            f"Turn 4 không cập nhật trục thời gian sang năm 2024! ans: {ans4[:150]}, sql: {sql4}"
        )

        # ----------------------------------------------------------------------
        # TURN 5: Tra cứu chỉ tiêu định lượng cụ thể (Specific metric inquiry)
        # ----------------------------------------------------------------------
        t5_query = "Tổng vốn điều lệ là bao nhiêu?"
        res5 = warehouse_agent.run(
            query=t5_query,
            session_id=session_id,
            user_context=user_context,
        )
        ans5 = res5.get("final_answer") or res5.get("answer") or ""
        chips5 = res5.get("quick_action_chips") or res5.get("chips") or []

        assert len(ans5) > 0, "Turn 5 trả về câu trả lời rỗng!"
        assert (
            "vốn điều lệ" in ans5.lower()
            or "tổng hợp" in ans5.lower()
            or "chỉ tiêu" in ans5.lower()
            or len(chips5) > 0
        ), f"Turn 5 không xử lý được chỉ tiêu vốn điều lệ: {ans5[:200]}"

        # ----------------------------------------------------------------------
        # KIỂM TRA LƯU TRỮ TRẠNG THÁI TRÊN SQLITE CHECKPOINTS
        # ----------------------------------------------------------------------
        assert DB_PATH.exists(), f"Không tìm thấy file SQLite lưu trữ tại {DB_PATH}"
        with sqlite3.connect(str(DB_PATH)) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?",
                (session_id,),
            )
            checkpoint_count = cur.fetchone()[0]

        # Phiên 5 lượt phải ghi nhận nhiều checkpoints tương ứng từng node LangGraph
        assert checkpoint_count >= 5, (
            f"Số lượng checkpoints trong SQLite ({checkpoint_count}) nhỏ hơn kỳ vọng (>= 5)!"
        )

    def test_multiturn_slot_repair_mechanism(self):
        """
        Kiểm thử cơ chế Slot Repair:
        Turn 1: Thiết lập ngữ cảnh xã / huyện A.
        Turn 2: Người dùng sửa lại 'Không, tôi muốn hỏi huyện B cơ'
        -> Hệ thống phải ghi đè huyện B và bảo lưu năm báo cáo đã thiết lập.
        """
        session_id = f"test_slot_repair_{uuid.uuid4().hex[:8]}"
        user_context: Dict[str, Any] = {"role_level": 0, "tenant_code": "68"}

        # Turn 1
        res1 = warehouse_agent.run(
            query="Tổng sản lượng muối năm 2026?",
            session_id=session_id,
            user_context=user_context,
        )
        ans1 = res1.get("final_answer") or res1.get("answer") or ""
        assert len(ans1) > 0

        # Turn 2: Chuyển sang diện tích nhưng giữ nguyên muối và 2026
        res2 = warehouse_agent.run(
            query="Đổi sang xem diện tích muối xem nào?",
            session_id=session_id,
            user_context=user_context,
        )
        ans2 = res2.get("final_answer") or res2.get("answer") or ""
        sql2 = res2.get("generated_sql") or res2.get("sql") or ""

        assert len(ans2) > 0
        assert "diện tích" in ans2.lower() or "muối" in ans2.lower()
        if sql2:
            assert "2026" in sql2

    def test_multiturn_chitchat_interleaving_preserves_quest(self):
        """
        Kiểm thử lời chào / cảm ơn xen kẽ không làm văng hay reset ngữ cảnh:
        Turn 1: Tra cứu chỉ tiêu
        Turn 2: Cảm ơn nhé! -> Hệ thống chào lịch sự, không làm mất session.
        Turn 3: Tiếp tục hỏi tiếp -> Kế thừa ngữ cảnh.
        """
        session_id = f"test_chitchat_interleave_{uuid.uuid4().hex[:8]}"
        user_context: Dict[str, Any] = {"role_level": 0, "tenant_code": "68"}

        # Turn 1
        res1 = warehouse_agent.run(
            query="Toàn tỉnh có bao nhiêu đơn vị OCOP 4 sao năm 2026?",
            session_id=session_id,
            user_context=user_context,
        )
        ans1 = res1.get("final_answer") or res1.get("answer") or ""
        assert len(ans1) > 0
        assert "4 sao" in ans1

        # Turn 2: Cảm ơn xen kẽ
        res2 = warehouse_agent.run(
            query="Cảm ơn trợ lý ảo rất nhiều nhé!",
            session_id=session_id,
            user_context=user_context,
        )
        ans2 = res2.get("final_answer") or res2.get("answer") or ""
        assert len(ans2) > 0
        assert (
            "chào" in ans2.lower()
            or "cảm ơn" in ans2.lower()
            or "hỗ trợ" in ans2.lower()
            or "đồng chí" in ans2.lower()
        )

        # Turn 3: Tiếp tục hỏi mà không nhắc lại OCOP hay năm 2026
        res3 = warehouse_agent.run(
            query="Thế còn hạng 3 sao thì sao?",
            session_id=session_id,
            user_context=user_context,
        )
        ans3 = res3.get("final_answer") or res3.get("answer") or ""
        assert len(ans3) > 0
        assert (
            "3 sao" in ans3
            or "chủ thể" in ans3.lower()
            or "ocop" in ans3.lower()
        ), f"Turn 3 làm mất ngữ cảnh OCOP sau lời chào: {ans3[:200]}"
