"""
IPGov Chatbot - Tool: Audit Inspector & TDD Test Case Generator
Công cụ dành cho Agent và Kỹ sư để tra cứu, phân tích nguyên nhân gốc rễ (RCA)
và tự động chuyển hóa các ghi chú phản hồi lỗi (Quest Annotations) thành test case TDD.
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

# Đảm bảo import IPGov_Chatbot an toàn
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Hỗ trợ UTF-8 an toàn trên Windows Console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from IPGov_Chatbot.core.feedback_manager import FeedbackManager, DEFAULT_STORAGE_PATH
from IPGov_Chatbot.schemas.feedback_dto import ErrorCategoryEnum, QuestAnnotationDTO


class AuditInspector:
    """
    Động cơ truy xuất và phân tích báo cáo lỗi cho Agent/Dev.
    Hỗ trợ:
    1. Thống kê lỗi theo ErrorCategory và Severity.
    2. Lọc nhanh các ca đang mở (`status == 'OPEN'`).
    3. Tự động sinh file test case pytest từ các quest lỗi được báo cáo (TDD Flywheel).
    """

    def __init__(self, log_path: Optional[Path] = None) -> None:
        self.mgr = FeedbackManager(storage_path=log_path or DEFAULT_STORAGE_PATH)

    def get_summary_stats(self) -> Dict[str, Any]:
        """Tổng hợp số liệu thống kê các lỗi được ghi chú."""
        all_notes = self.mgr.get_all_annotations()
        open_notes = [n for n in all_notes if n.status == "OPEN"]
        resolved_notes = [n for n in all_notes if n.status == "RESOLVED"]

        by_cat: Dict[str, int] = {}
        for n in all_notes:
            cat = n.error_category.value
            by_cat[cat] = by_cat.get(cat, 0) + 1

        by_sev: Dict[str, int] = {}
        for n in all_notes:
            sev = n.severity.value
            by_sev[sev] = by_sev.get(sev, 0) + 1

        return {
            "total_annotations": len(all_notes),
            "open_annotations": len(open_notes),
            "resolved_annotations": len(resolved_notes),
            "by_category": by_cat,
            "by_severity": by_sev,
            "top_recent_open": [n.model_dump() for n in open_notes[-5:]],
        }

    def list_open_cases(self, category: Optional[str] = None) -> List[QuestAnnotationDTO]:
        """Liệt kê danh sách các ca lỗi đang mở (status == 'OPEN')."""
        open_cases = self.mgr.get_open_annotations()
        if category:
            open_cases = [c for c in open_cases if c.error_category.value == category]
        return open_cases

    def export_to_pytest(self, output_path: Path) -> bool:
        """
        Tự động chuyển các quest đang mở thành các test cases pytest để kỹ sư/Agent chạy TDD.
        """
        open_cases = self.mgr.get_open_annotations()
        if not open_cases:
            print("[AuditInspector] Không có ca lỗi nào đang mở để xuất test case.")
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            '"""',
            'Automated Regression Test Suite generated from User-Reported Quest Annotations.',
            'File này được tự động sinh bởi IPGov_Chatbot.tools.audit_inspector.',
            '"""',
            '',
            'import pytest',
            'from IPGov_Chatbot.modules.mod03_router.intent_router import IntentRouter',
            'from IPGov_Chatbot.schemas.router_dto import RouteTypeEnum',
            '',
            '@pytest.fixture',
            'def router():',
            '    return IntentRouter()',
            '',
        ]

        for i, case in enumerate(open_cases, 1):
            clean_id = case.trace_id.replace("-", "_").replace(" ", "_")
            func_name = f"test_reported_case_{clean_id}_{i}"
            expected_route = case.expected_route or case.actual_route or "TEMPLATE_FAST_TRACK"
            
            lines.extend([
                f"# Ghi chú người dùng: {case.user_note}",
                f"# Nhóm lỗi: {case.error_category.value} | Độ nghiêm trọng: {case.severity.value}",
                f"def {func_name}(router):",
                f'    prompt = "{case.prompt}"',
                f'    res = router.route_query(prompt, session_id="test_feedback_{clean_id}")',
                f'    assert res is not None',
            ])
            if case.expected_route:
                lines.append(f'    assert res.route.value == "{expected_route}", f"Kỳ vọng {expected_route} nhưng thực tế ra {{res.route.value}}"')
            if case.expected_behavior:
                lines.append(f'    # Hành vi kỳ vọng: {case.expected_behavior}')
            lines.append('')

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            return True
        except Exception as e:
            print(f"[AuditInspector] Lỗi khi xuất file pytest: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description="Công cụ Tra Cứu & Trích Xuất Lỗi Ghi Chú (Audit Inspector)")
    parser.add_argument("--list-open", action="store_true", help="Liệt kê toàn bộ các ca lỗi đang mở")
    parser.add_argument("--stats", action="store_true", help="Hiển thị thống kê tổng hợp lỗi")
    parser.add_argument("--category", type=str, default=None, help="Lọc theo nhóm lỗi (ErrorCategory)")
    parser.add_argument("--search", type=str, default=None, help="Tìm kiếm từ khóa trong ghi chú hoặc prompt")
    parser.add_argument("--tag", type=str, default=None, help="Lọc theo tag")
    parser.add_argument("--export-pytest", type=str, default=None, help="Đường dẫn file .py để xuất test cases pytest")
    parser.add_argument("--resolve", type=str, default=None, help="Annotation ID cần đánh dấu giải quyết")
    parser.add_argument("--notes", type=str, default="Đã xử lý xong", help="Ghi chú cách thức giải quyết")

    args = parser.parse_args()
    inspector = AuditInspector()

    if args.stats:
        stats = inspector.get_summary_stats()
        print("\n📊 BÁO CÁO THỐNG KÊ LỖI ĐƯỢC BÁO CÁO (FEEDBACK AUDIT):")
        print(f" • Tổng số ghi chú:  {stats['total_annotations']}")
        print(f" • Ca đang mở (OPEN): {stats['open_annotations']}")
        print(f" • Đã xử lý (RESOLVED): {stats['resolved_annotations']}")
        print("\n📂 Theo Nhóm Lỗi (Category):")
        for cat, count in stats["by_category"].items():
            print(f"   - {cat}: {count}")
        print("\n⚡ Theo Mức Độ Nghiêm Trọng:")
        for sev, count in stats["by_severity"].items():
            print(f"   - {sev}: {count}")
        print()
        return

    if args.list_open:
        cases = inspector.list_open_cases(category=args.category)
        print(f"\n📋 DANH SÁCH CÁC CA LỖI ĐANG MỞ ({len(cases)} ca):")
        for i, c in enumerate(cases, 1):
            print(f" {i}. [{c.severity.value}] [{c.error_category.value}] ID: {c.annotation_id} | Trace: {c.trace_id}")
            print(f"    Prompt:   \"{c.prompt}\"")
            print(f"    Ghi chú:  \"{c.user_note}\"")
            if c.expected_route:
                print(f"    Kỳ vọng:  Tuyến {c.expected_route} (Thực tế: {c.actual_route})")
            print(f"    Thời gian: {c.created_at[:19]}")
            print("   -------------------------------------------------------------")
        print()
        return

    if args.search or args.tag:
        items = inspector.mgr.search_annotations(keyword=args.search, tag=args.tag)
        print(f"\n🔍 KẾT QUẢ TÌM KIẾM ({len(items)} kết quả):")
        for i, c in enumerate(items, 1):
            print(f" {i}. [{c.status}] [{c.error_category.value}] \"{c.prompt}\" -> Note: \"{c.user_note}\"")
        print()
        return

    if args.resolve:
        ok = inspector.mgr.mark_resolved(annotation_id=args.resolve, resolution_notes=args.notes)
        if ok:
            print(f"[✓] Đã cập nhật trạng thái RESOLVED cho ca {args.resolve}")
        else:
            print(f"[!] Không tìm thấy annotation_id {args.resolve}")
        return

    if args.export_pytest:
        out_path = Path(args.export_pytest)
        ok = inspector.export_to_pytest(out_path)
        if ok:
            print(f"[✓] Đã xuất thành công test case pytest sang: {out_path}")
        return

    # Mặc định in thống kê
    stats = inspector.get_summary_stats()
    print(f"\n[AuditInspector] Sẵn sàng phục vụ. Hiện có {stats['open_annotations']} ca lỗi đang mở. Dùng --help để xem chi tiết các lệnh.\n")


if __name__ == "__main__":
    main()
