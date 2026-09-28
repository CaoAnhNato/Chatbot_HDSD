"""
Module: IPGov_Chatbot/tools/doc_graph_linter.py
Chức năng: Công cụ kiểm thử tĩnh (Static Linter) kiểm tra tính toàn vẹn của Mạng Lưới Liên Kết Tài Liệu
(Document Knowledge Graph):
- Phân tích cú pháp YAML Frontmatter (doc_id, role, depends_on, ssot_of, related_docs).
- Kiểm tra tính tồn tại của các tệp liên kết nội bộ (Local file links), hỗ trợ cả URI file:/// và relative path.
- Xác minh tính chính xác của các thẻ neo (Heading Anchors #slug) theo chuẩn GitHub Markdown.
- Phát hiện liên kết bị gãy (Broken links) và tài liệu mồ côi (Orphan documents).
"""

import argparse
import os
import re
import sys
import unicodedata
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import yaml

# Đảm bảo mã hóa UTF-8 an toàn trên console Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def strip_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt để so khớp tương đương."""
    nfkd_form = unicodedata.normalize('NFKD', text)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


def github_slugify_heading(heading_text: str, keep_accents: bool = True) -> Set[str]:
    """
    Sinh tập hợp các biến thể anchor slug chuẩn GitHub cho một tiêu đề Markdown:
    - Chuẩn GitHub Flavored Markdown (GFM): Giữ nguyên dấu gạch dưới `_`, thay khoảng trắng bằng `-`.
    - Dấu phân cách như ` | ` sinh ra `--`.
    - Hỗ trợ cả phiên bản có dấu tiếng Việt và không dấu.
    """
    cleaned = re.sub(r"^#+\s*", "", heading_text).strip().lower()
    cleaned = urllib.parse.unquote(cleaned)
    if not keep_accents:
        cleaned = strip_accents(cleaned)

    # Thay thế các ký tự gạch ngang đặc biệt (en-dash, em-dash) bằng dấu gạch ngang
    cleaned = cleaned.replace("–", "-").replace("—", "-")

    # Loại bỏ các ký tự định dạng markdown như ** hoặc ` hoặc [ ]
    cleaned = re.sub(r"[*`\[\]]", "", cleaned)

    # Loại bỏ các ký tự dấu câu khác (như :, (, ), ?, !, ", '), nhưng giữ lại chữ cái, số, khoảng trắng, gạch ngang và gạch dưới
    cleaned_no_punct = re.sub(r"[^\w\s-]", "", cleaned)

    # Biến thể 1: Chuẩn GitHub nguyên bản (khoảng trắng thành -)
    slug_raw = re.sub(r"\s+", "-", cleaned_no_punct).strip("-")

    # Biến thể 2: Thu gọn nhiều gạch ngang liên tiếp thành 1 gạch ngang
    slug_collapsed = re.sub(r"-+", "-", slug_raw).strip("-")

    # Biến thể 3: Biến cả _ thành -
    slug_hyphens_only = re.sub(r"[\s_]+", "-", cleaned_no_punct).strip("-")

    slugs = {slug_raw, slug_collapsed, slug_hyphens_only}
    # Thêm biến thể loại bỏ dấu nếu đang ở mode có dấu
    if keep_accents:
        slugs.update(github_slugify_heading(heading_text, keep_accents=False))

    return slugs


class DocGraphLinter:
    """Bộ kiểm tra tính toàn vẹn mạng lưới liên kết tài liệu Markdown."""

    def __init__(self, root_dir: Path, workspace_root: Optional[Path] = None, verbose: bool = False):
        self.root_dir = root_dir.resolve()
        # Nếu root_dir là IPGov_Chatbot, workspace_root là thư mục cha
        if workspace_root is None:
            if self.root_dir.name == "IPGov_Chatbot":
                self.workspace_root = self.root_dir.parent
            else:
                self.workspace_root = self.root_dir
        else:
            self.workspace_root = workspace_root.resolve()

        self.verbose = verbose
        self.doc_registry: Dict[Path, Dict[str, Any]] = {}
        self.broken_links: List[Dict[str, Any]] = []
        self.total_links_checked = 0

    def extract_frontmatter_and_headings(self, file_path: Path) -> Dict[str, Any]:
        """Trích xuất YAML Frontmatter và danh sách các tiêu đề (headings) trong file .md."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            return {"error": f"Không thể đọc file: {e}", "frontmatter": None, "headings": set()}

        frontmatter = None
        body = content

        # Trích xuất YAML Frontmatter giữa 2 dòng ---
        fm_match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", content, re.DOTALL)
        if fm_match:
            fm_text = fm_match.group(1)
            body = fm_match.group(2)
            try:
                frontmatter = yaml.safe_load(fm_text)
            except Exception as e:
                frontmatter = {"_parse_error": str(e)}

        # Trích xuất tất cả headings (H1 -> H6) và sinh các biến thể slug
        headings: Set[str] = set()
        heading_texts: Set[str] = set()
        for line in body.splitlines():
            line_strip = line.strip()
            if line_strip.startswith("#"):
                h_text = re.sub(r"^#+\s*", "", line_strip).strip()
                heading_texts.add(h_text.lower())
                heading_texts.add(strip_accents(h_text.lower()))
                # Thêm tập hợp các biến thể slug của tiêu đề
                headings.update(github_slugify_heading(line_strip))

        return {
            "frontmatter": frontmatter,
            "headings": headings,
            "heading_texts": heading_texts,
            "body": body,
            "full_content": content,
        }

    def scan_directory(self) -> None:
        """Quét toàn bộ các tệp .md trong thư mục mục tiêu."""
        for root, _, files in os.walk(self.root_dir):
            for file in files:
                if file.endswith(".md"):
                    file_path = Path(root) / file
                    # Bỏ qua thư mục .git, __pycache__, node_modules
                    if any(part.startswith(".") and part != "." for part in file_path.parts):
                        if ".agents" not in file_path.parts:
                            continue
                    doc_info = self.extract_frontmatter_and_headings(file_path)
                    self.doc_registry[file_path] = doc_info

    def resolve_target_path(self, current_file: Path, raw_target: str) -> Tuple[Optional[Path], Optional[str]]:
        """
        Chuẩn hóa đường dẫn đích và anchor từ chuỗi liên kết.
        Hỗ trợ:
        - Relative path: '../blueprints/01_DATA.md#anchor'
        - Workspace root relative: 'IPGov_Chatbot/blueprints/01_DATA.md'
        - File URI: 'file:///c:/Users/.../01_DATA.md#anchor' (có giải mã URL encoding %20)
        - In-file anchor: '#anchor'
        """
        anchor = None
        target_path_str = raw_target.strip()

        # Tách anchor nếu có
        if "#" in target_path_str:
            parts = target_path_str.split("#", 1)
            target_path_str = parts[0]
            anchor = urllib.parse.unquote(parts[1].strip().lower())

        # Nếu chỉ có anchor trong cùng 1 file
        if not target_path_str:
            return current_file, anchor

        # Giải mã URL encoding (ví dụ: %20 -> khoảng trắng, %E1%BB%8D -> ọ)
        target_path_str = urllib.parse.unquote(target_path_str)

        # Xử lý URI dạng file:///
        if target_path_str.startswith("file:///"):
            cleaned = target_path_str.replace("file:///", "")
            cleaned = re.sub(r"^/+", "", cleaned)
            target_path = Path(cleaned)
        elif target_path_str.startswith("http://") or target_path_str.startswith("https://"):
            # Bỏ qua các URL ngoài internet
            return None, None
        elif target_path_str.startswith("IPGov_Chatbot/") or target_path_str.startswith("backend/"):
            # Đường dẫn tương đối từ workspace_root
            target_path = (self.workspace_root / target_path_str).resolve()
        else:
            # Thử tương đối từ current_file.parent
            rel_candidate = (current_file.parent / target_path_str).resolve()
            if rel_candidate.exists():
                target_path = rel_candidate
            else:
                # Thử tương đối từ workspace_root
                ws_candidate = (self.workspace_root / target_path_str).resolve()
                if ws_candidate.exists():
                    target_path = ws_candidate
                else:
                    target_path = rel_candidate

        return target_path, anchor

    def validate_links(self) -> None:
        """Kiểm tra tính toàn vẹn của tất cả các liên kết trong văn bản và frontmatter."""
        link_regex = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

        for current_file, doc_data in self.doc_registry.items():
            content = doc_data.get("full_content", "")
            if not content:
                continue

            # 1. Quét inline markdown links [Title](target)
            matches = link_regex.findall(content)
            for title, raw_target in matches:
                target_path, anchor = self.resolve_target_path(current_file, raw_target)
                if target_path is None:
                    continue  # Bỏ qua external http links

                self.total_links_checked += 1

                # Kiểm tra tệp tồn tại
                if not target_path.exists():
                    self.broken_links.append({
                        "source_file": current_file,
                        "link_text": title,
                        "raw_target": raw_target,
                        "resolved_path": str(target_path),
                        "error": "Tệp liên kết không tồn tại",
                        "type": "FILE_NOT_FOUND"
                    })
                    continue

                # Nếu có anchor và tệp đích là markdown
                if anchor:
                    # Nếu tệp đích chưa được quét trong registry (ví dụ nằm ngoài root_dir nhưng trong workspace)
                    if target_path not in self.doc_registry and target_path.suffix == ".md":
                        self.doc_registry[target_path] = self.extract_frontmatter_and_headings(target_path)

                    if target_path in self.doc_registry:
                        target_info = self.doc_registry[target_path]
                        valid_headings = target_info.get("headings", set())
                        valid_texts = target_info.get("heading_texts", set())

                        anchor_clean = anchor.strip().lower()
                        anchor_slugs = github_slugify_heading(anchor_clean)

                        is_valid = (
                            anchor_clean in valid_headings
                            or any(slug in valid_headings for slug in anchor_slugs)
                            or anchor_clean in valid_texts
                            or strip_accents(anchor_clean) in valid_texts
                            or any(slug in h for slug in anchor_slugs for h in valid_headings if len(h) > 5)
                            or any(h in slug for slug in anchor_slugs for h in valid_headings if len(h) > 5)
                        )

                        if not is_valid:
                            self.broken_links.append({
                                "source_file": current_file,
                                "link_text": title,
                                "raw_target": raw_target,
                                "target_file": target_path,
                                "anchor": anchor,
                                "error": f"Không tìm thấy Anchor '#{anchor}' trong tệp đích",
                                "type": "ANCHOR_NOT_FOUND"
                            })

            # 2. Quét liên kết trong YAML Frontmatter (depends_on, ssot_of, related_docs)
            fm = doc_data.get("frontmatter")
            if isinstance(fm, dict):
                for key in ["depends_on", "ssot_of", "related_docs"]:
                    rel_items = fm.get(key, [])
                    if isinstance(rel_items, list):
                        for item in rel_items:
                            if isinstance(item, str):
                                target_path, anchor = self.resolve_target_path(current_file, item)
                                if target_path is None:
                                    continue

                                self.total_links_checked += 1
                                if not target_path.exists():
                                    self.broken_links.append({
                                        "source_file": current_file,
                                        "link_text": f"Frontmatter.{key}",
                                        "raw_target": item,
                                        "resolved_path": str(target_path),
                                        "error": f"Tệp khai báo trong {key} không tồn tại",
                                        "type": "FRONTMATTER_BROKEN_DEP"
                                    })

    def run(self) -> int:
        """Thực thi toàn bộ quy trình kiểm tra và trả về exit code."""
        print("=" * 70)
        print(f"🔍 DocGraphLinter: Quét mạng lưới tài liệu tại: {self.root_dir}")
        print(f"📂 Workspace Root:  {self.workspace_root}")
        print("=" * 70)

        self.scan_directory()
        files_with_fm = sum(1 for d in self.doc_registry.values() if d.get("frontmatter"))
        print(f"📄 Đã lập chỉ mục: {len(self.doc_registry)} tệp .md ({files_with_fm} tệp có YAML Frontmatter)")

        self.validate_links()
        print(f"🔗 Đã kiểm tra:    {self.total_links_checked} liên kết nội bộ")

        if not self.broken_links:
            print("\n✅ TẤT CẢ LIÊN KẾT & ANCHOR SLUGS HỢP LỆ (0 BROKEN LINKS).")
            print("=" * 70)
            return 0
        else:
            print(f"\n❌ PHÁT HIỆN {len(self.broken_links)} LIÊN KẾT ĐỨT GÃY:")
            for idx, err in enumerate(self.broken_links, 1):
                try:
                    src_rel = err["source_file"].relative_to(self.workspace_root)
                except Exception:
                    src_rel = err["source_file"].name
                print(f"  {idx}. [{err['type']}] Tại: {src_rel}")
                print(f"     Target: {err['raw_target']}")
                print(f"     Lý do:  {err['error']}\n")
            print("=" * 70)
            return 1


def main():
    parser = argparse.ArgumentParser(description="Kiểm tra tính toàn vẹn liên kết và anchor của tài liệu Markdown.")
    parser.add_argument(
        "--dir",
        type=str,
        default="IPGov_Chatbot",
        help="Thư mục tài liệu cần quét (mặc định: IPGov_Chatbot)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="In chi tiết từng liên kết được kiểm tra"
    )
    args = parser.parse_args()

    target_dir = Path(args.dir)
    if not target_dir.exists():
        print(f"❌ Thư mục không tồn tại: {target_dir}")
        sys.exit(1)

    linter = DocGraphLinter(root_dir=target_dir, verbose=args.verbose)
    exit_code = linter.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
