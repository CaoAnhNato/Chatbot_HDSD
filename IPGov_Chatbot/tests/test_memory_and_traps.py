"""
Test: IPGov_Chatbot/tests/test_memory_and_traps.py
Mục tiêu: Đảm bảo cơ chế Quản trị Bộ nhớ Dự án (Project Memory) và Bẫy Mã Nguồn (TRAPS.md)
luôn tuân thủ đúng quy chuẩn:
1. TRAPS.md tồn tại ở thư mục gốc, có ít nhất 1 bẫy hợp lệ với cấu trúc chuẩn.
2. memory_and_traps_rule.md tồn tại và chứa đủ 5 điều khoản cưỡng chế.
3. project-memory-and-traps SKILL.md tuân thủ chuẩn writing-skills (YAML Frontmatter SDO).
4. AGENTS.md tích hợp điều khoản cưỡng chế quy tắc memory_and_traps_rule.
5. PROJECT_MEMORY.md tồn tại và có phần Core Directives.
"""

from pathlib import Path
import re
import yaml


def get_workspace_root() -> Path:
    # IPGov_Chatbot/tests/test_memory_and_traps.py -> root is parent.parent
    return Path(__file__).resolve().parent.parent.parent


def test_traps_file_integrity():
    workspace_root = get_workspace_root()
    traps_file = workspace_root / "TRAPS.md"
    
    assert traps_file.exists(), "Tệp TRAPS.md phải tồn tại ở thư mục gốc workspace"
    content = traps_file.read_text(encoding="utf-8")
    
    # Kiểm tra có ít nhất 1 mục [TRAP-xxx]
    traps = re.findall(r"###\s*\[TRAP-\d+\].*", content)
    assert len(traps) >= 5, f"TRAPS.md phải chứa ít nhất 5 bẫy hạt nhân ban đầu, tìm thấy {len(traps)}"
    
    # Kiểm tra cấu trúc chuẩn trong bẫy
    assert "Triệu chứng" in content or "Symptoms" in content, "TRAPS.md phải có mục Triệu chứng"
    assert "Nguyên nhân gốc rễ" in content or "Root Cause" in content, "TRAPS.md phải có mục Nguyên nhân gốc rễ"
    assert "Quy tắc dứt điểm" in content, "TRAPS.md phải có mục Quy tắc dứt điểm"
    assert "NEVER:" in content, "TRAPS.md phải có mục NEVER"
    assert "ALWAYS:" in content, "TRAPS.md phải có mục ALWAYS"


def test_memory_and_traps_rule_integrity():
    workspace_root = get_workspace_root()
    rule_file = workspace_root / ".agents" / "rules" / "memory_and_traps_rule.md"
    
    assert rule_file.exists(), "Tệp .agents/rules/memory_and_traps_rule.md phải tồn tại"
    content = rule_file.read_text(encoding="utf-8")
    
    # 5 điều khoản bắt buộc
    assert "2-Tier Memory Grounding" in content or "Cơ Chế Nạp Ngữ Cảnh 2 Tầng" in content
    assert "Auto-Ingestion Protocol" in content or "Tự Động Ghi Nhận Lưu Ý" in content
    assert "Pre-flight Trap Check" in content or "Rà Soát Bẫy Trước Khi Thực Thi Mã" in content
    assert "Post-Fix Trap Logging" in content or "Tự Động Ghi Nhận Bẫy Sau Khi Khắc Phục Lỗi" in content
    assert "Sub-Agent Inheritance Protocol" in content or "Truyền Tải Ngữ Cảnh Cho Sub-Agents" in content


def test_project_memory_and_traps_skill_integrity():
    workspace_root = get_workspace_root()
    skill_file = workspace_root / ".agents" / "skills" / "project-memory-and-traps" / "SKILL.md"
    
    assert skill_file.exists(), "Tệp .agents/skills/project-memory-and-traps/SKILL.md phải tồn tại"
    content = skill_file.read_text(encoding="utf-8")
    
    # Kiểm tra YAML Frontmatter
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    assert match, "SKILL.md bắt buộc phải có YAML Frontmatter"
    
    frontmatter = yaml.safe_load(match.group(1))
    assert "name" in frontmatter, "Frontmatter phải có trường 'name'"
    assert frontmatter["name"] == "project-memory-and-traps", "Tên skill phải là project-memory-and-traps"
    
    assert "description" in frontmatter, "Frontmatter phải có trường 'description'"
    desc = frontmatter["description"]
    assert desc.startswith("Use when"), "Theo chuẩn writing-skills (SDO), description bắt buộc bắt đầu bằng 'Use when...'"
    assert len(desc) <= 500, f"Description không nên vượt quá 500 ký tự (hiện tại: {len(desc)})"


def test_agents_md_references_memory_and_traps_rule():
    workspace_root = get_workspace_root()
    agents_file = workspace_root / ".agents" / "AGENTS.md"
    
    assert agents_file.exists(), ".agents/AGENTS.md phải tồn tại"
    content = agents_file.read_text(encoding="utf-8")
    
    assert "memory_and_traps_rule.md" in content, ".agents/AGENTS.md bắt buộc phải tham chiếu đến memory_and_traps_rule.md"
    assert "TRAPS.md" in content, ".agents/AGENTS.md bắt buộc phải tham chiếu đến TRAPS.md"
    assert "PROJECT_MEMORY.md" in content, ".agents/AGENTS.md bắt buộc phải tham chiếu đến PROJECT_MEMORY.md"


def test_project_memory_file_integrity():
    workspace_root = get_workspace_root()
    memory_file = workspace_root / ".agents" / "PROJECT_MEMORY.md"
    
    assert memory_file.exists(), ".agents/PROJECT_MEMORY.md phải tồn tại"
    content = memory_file.read_text(encoding="utf-8")
    
    assert "CORE DIRECTIVE" in content or "LƯU Ý CỐT LÕI" in content, "PROJECT_MEMORY.md phải chứa mục Core Directive"
    assert "vna_wom_dev" in content, "PROJECT_MEMORY.md phải chứa thông tin CSDL DWH"
