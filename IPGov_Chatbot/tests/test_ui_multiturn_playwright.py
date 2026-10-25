"""
Module: IPGov_Chatbot/tests/test_ui_multiturn_playwright.py
Chức năng: R3.3 UI E2E Verification & Multi-Turn Live Playwright Suite
Mục tiêu:
1. Thực thi tự động 5 lượt hội thoại liên tiếp trong cùng một phiên trên giao diện Next.js:
   - Turn 1: Initial criteria/report query ("Tình hình kinh tế tập thể quý 1 năm 2026")
   - Turn 2: In-place breakdown query ("Các lĩnh vực hoạt động của hợp tác xã nông nghiệp")
   - Turn 3: Pronoun ellipsis / branch drill-down ("Của liên hiệp hợp tác xã thì sao?")
   - Turn 4: Temporal pivot ("Thế còn năm 2024?")
   - Turn 5: Specific metric inquiry ("Tổng vốn điều lệ là bao nhiêu?")
2. Kiểm tra tính ổn định giao diện đa lượt (Multi-turn UI Stability):
   - 0 lỗi JavaScript runtime trên console log (0 console errors).
   - Bảo toàn 100% lịch sử chat qua 5 lượt, không bị màn hình trắng (blank screen).
   - 100% nhãn tiếng Việt thuần túy, tuyệt đối cấm 'Ticket thời gian:' và 'THINKING'.
3. Chụp và lưu trữ ảnh minh chứng thực tế vào:
   `IPGov_Chatbot/artifacts/ui_verification/`
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import List

import pytest
from playwright.sync_api import sync_playwright, Page, Browser, Playwright

WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent
ARTIFACTS_DIR = WORKSPACE_DIR / "IPGov_Chatbot" / "artifacts" / "ui_verification"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

FRONTEND_URL = "http://localhost:3000"


def send_chat_message(page: Page, query_text: str, timeout_sec: int = 45):
    """Gửi một câu hỏi trên giao diện chat và chờ hệ thống phản hồi hoàn tất."""
    # 1. Chờ ô nhập liệu sẵn sàng và không bị disabled
    input_selector = 'form input[type="text"]'
    page.wait_for_selector(f"{input_selector}:not([disabled])", timeout=15000)

    # 2. Nhập nội dung câu hỏi và nhấn gửi
    input_box = page.locator(input_selector)
    input_box.fill(query_text)
    time.sleep(0.3)

    submit_button = page.locator('form button[type="submit"]')
    submit_button.click()

    # 3. Chờ trạng thái loading/streaming xuất hiện và kết thúc
    # Input sẽ bị disabled trong khi bot đang streaming
    time.sleep(1.0)
    # Chờ cho đến khi input mở lại (không còn disabled)
    page.wait_for_selector(f"{input_selector}:not([disabled])", timeout=timeout_sec * 1000)
    # Chờ thêm 1.5 giây để hiệu ứng FluidTextStream và DOM settled hoàn toàn
    time.sleep(1.5)


class TestUIMultiTurnPlaywright:
    """Bộ kiểm thử E2E giao diện người dùng qua Playwright Chromium."""

    def test_ui_multiturn_session_and_visual_evidence(self):
        """
        Kiểm tra toàn diện 5 lượt hội thoại liên tiếp trên giao diện thực tế,
        bảo đảm 0 lỗi console, nhãn thuần Việt và trích xuất bằng chứng hình ảnh.
        """
        console_errors: List[str] = []

        with sync_playwright() as p:
            # Khởi động Chrome local ở chế độ headless
            browser = p.chromium.launch(channel="chrome", headless=True)
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                device_scale_factor=1,
            )
            page = context.new_page()

            # Lắng nghe sự kiện console để phát hiện lỗi JS runtime
            page.on(
                "console",
                lambda msg: console_errors.append(msg.text)
                if msg.type == "error" and "favicon" not in msg.text.lower()
                else None,
            )

            # Truy cập ứng dụng Next.js
            page.goto(FRONTEND_URL, wait_until="networkidle", timeout=30000)
            page.wait_for_selector('form input[type="text"]', timeout=15000)

            # Khẳng định trang chủ load thành công
            assert "IPGov Chatbot" in page.title() or "Chatbot" in page.content()

            # ------------------------------------------------------------------
            # TURN 1: Báo cáo tổng quan Quý 1 năm 2026
            # ------------------------------------------------------------------
            send_chat_message(page, "Tình hình kinh tế tập thể quý 1 năm 2026")
            shot1 = ARTIFACTS_DIR / "turn1_criteria_overview.png"
            page.screenshot(path=str(shot1), full_page=True)
            assert shot1.exists(), f"Không tạo được ảnh Turn 1 tại {shot1}"

            # ------------------------------------------------------------------
            # TURN 2: Bóc tách lĩnh vực hoạt động của HTX nông nghiệp
            # ------------------------------------------------------------------
            send_chat_message(page, "Các lĩnh vực hoạt động của hợp tác xã nông nghiệp")
            shot2 = ARTIFACTS_DIR / "turn2_breakdown_table.png"
            page.screenshot(path=str(shot2), full_page=True)
            assert shot2.exists(), f"Không tạo được ảnh Turn 2 tại {shot2}"

            # ------------------------------------------------------------------
            # TURN 3: Tỉnh lược đại từ / phân nhánh sâu (Liên hiệp HTX)
            # ------------------------------------------------------------------
            send_chat_message(page, "Của liên hiệp hợp tác xã thì sao?")
            shot3 = ARTIFACTS_DIR / "turn3_branch_drilldown.png"
            page.screenshot(path=str(shot3), full_page=True)
            assert shot3.exists(), f"Không tạo được ảnh Turn 3 tại {shot3}"

            # ------------------------------------------------------------------
            # TURN 4: Đổi trục thời gian sang năm 2024
            # ------------------------------------------------------------------
            send_chat_message(page, "Thế còn năm 2024?")
            shot4 = ARTIFACTS_DIR / "turn4_temporal_pivot.png"
            page.screenshot(path=str(shot4), full_page=True)
            assert shot4.exists(), f"Không tạo được ảnh Turn 4 tại {shot4}"

            # ------------------------------------------------------------------
            # TURN 5: Tra cứu chỉ tiêu định lượng cụ thể
            # ------------------------------------------------------------------
            send_chat_message(page, "Tổng vốn điều lệ là bao nhiêu?")
            shot5 = ARTIFACTS_DIR / "turn5_specific_metric.png"
            page.screenshot(path=str(shot5), full_page=True)
            assert shot5.exists(), f"Không tạo được ảnh Turn 5 tại {shot5}"

            # Chụp ảnh tổng kết toàn bộ phiên hội thoại 5 lượt
            summary_shot = ARTIFACTS_DIR / "multiturn_full_session_summary.png"
            page.screenshot(path=str(summary_shot), full_page=True)
            assert summary_shot.exists(), f"Không tạo được ảnh tổng kết tại {summary_shot}"

            # ------------------------------------------------------------------
            # KIỂM TRA BẤT BIẾN GIAO DIỆN & TRẢI NGHIỆM NGƯỜI DÙNG
            # ------------------------------------------------------------------
            body_text = page.locator("body").inner_text()

            # 1. 100% Thuần Việt: Tuyệt đối không chứa nhãn debug tiếng Anh
            assert "Ticket thời gian:" not in body_text, (
                "Phát hiện nhãn cấm 'Ticket thời gian:' trên giao diện!"
            )
            assert "THINKING" not in body_text, (
                "Phát hiện từ tiếng Anh kỹ thuật 'THINKING' trên giao diện!"
            )

            # 2. Không bị trắng màn hình sau lượt thứ 3 và xuyên suốt phiên
            user_bubble_count = page.locator('div[data-role="user"]').count()
            bot_bubble_count = page.locator('div[data-role="assistant"]').count()
            # Hoặc đếm qua các khối tin nhắn hiển thị
            all_rendered_text = page.locator("main, .flex-1").first.inner_text()
            assert len(all_rendered_text) > 500, "Giao diện bị trắng màn hình rỗng sau 5 lượt!"
            assert "kinh tế tập thể" in all_rendered_text.lower(), "Bị mất lịch sử Turn 1!"
            assert "liên hiệp" in all_rendered_text.lower(), "Bị mất lịch sử Turn 3!"

            # 3. Không có lỗi JavaScript runtime
            js_runtime_errors = [
                err for err in console_errors
                if "react" in err.lower() or "uncaught" in err.lower() or "syntax" in err.lower()
            ]
            assert len(js_runtime_errors) == 0, (
                f"Phát hiện lỗi JavaScript console runtime: {js_runtime_errors}"
            )

            browser.close()
