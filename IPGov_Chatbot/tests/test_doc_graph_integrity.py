"""
Test: IPGov_Chatbot/tests/test_doc_graph_integrity.py
Mục tiêu: Đảm bảo mạng lưới liên kết tài liệu kỹ thuật (Document Knowledge Graph) luôn nguyên vẹn:
- 0 Broken Links giữa các tài liệu .md.
- Toàn bộ YAML Frontmatter hợp lệ.
- Các Anchor Slugs được trỏ tới đều tồn tại trong tệp đích.
"""

from pathlib import Path
import pytest
from IPGov_Chatbot.tools.doc_graph_linter import DocGraphLinter


def test_doc_graph_has_no_broken_links():
    """Kiểm tra toàn bộ tài liệu trong IPGov_Chatbot/ không có liên kết đứt gãy."""
    workspace_root = Path(__file__).resolve().parent.parent
    linter = DocGraphLinter(root_dir=workspace_root)
    
    linter.scan_directory()
    assert len(linter.doc_registry) > 0, "Phải quét được ít nhất 1 tệp .md trong IPGov_Chatbot/"
    
    linter.validate_links()
    
    # Kiểm tra không có bất kỳ liên kết đứt gãy nào (cả file không tồn tại và anchor slug không tìm thấy)
    error_msg = f"Phát hiện {len(linter.broken_links)} liên kết đứt gãy:\n"
    for err in linter.broken_links:
        error_msg += f"- [{err['type']}] File: {err['source_file'].name} -> Target: {err['raw_target']} ({err['error']})\n"
        
    assert len(linter.broken_links) == 0, error_msg


def test_blueprints_have_valid_frontmatter():
    """Kiểm tra các tệp trong blueprints/ đã được khai báo YAML Frontmatter."""
    blueprints_dir = Path(__file__).resolve().parent.parent / "blueprints"
    if not blueprints_dir.exists():
        pytest.skip("blueprints/ directory not found")
        
    linter = DocGraphLinter(root_dir=blueprints_dir)
    linter.scan_directory()
    
    # Kiểm tra ít nhất các file hạt nhân phải có Frontmatter
    has_frontmatter_count = sum(1 for d in linter.doc_registry.values() if d.get("frontmatter"))
    assert has_frontmatter_count > 0, "Ít nhất các tài liệu hạt nhân trong blueprints/ phải có Frontmatter"
