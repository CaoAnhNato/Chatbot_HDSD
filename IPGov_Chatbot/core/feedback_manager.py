"""
IPGov Chatbot - Core Feedback & Quest Annotation Manager
Quản lý lưu trữ bất biến (JSON Lines), tìm kiếm và cập nhật vòng đời các ghi chú feedback.
Căn cứ: Arc42 Sec 8, Blueprints 06_OBSERVABILITY_TRACING, 08_TEST_SUITE_DESIGN
"""

from __future__ import annotations
import datetime
import json
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional

from IPGov_Chatbot.schemas.feedback_dto import (
    ErrorCategoryEnum,
    FeedbackSeverityEnum,
    QuestAnnotationDTO,
)


DEFAULT_STORAGE_PATH = Path(__file__).resolve().parent.parent / "logs" / "quest_annotations.jsonl"


class FeedbackManager:
    """
    Quản lý lưu trữ và truy vấn các ghi chú lỗi (Quest Annotations).
    Hỗ trợ cơ chế Thread-safe, Append-only JSONL và tìm kiếm/lọc siêu tốc.
    """

    _lock = threading.Lock()

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self.storage_path = storage_path or DEFAULT_STORAGE_PATH
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def save_annotation(self, dto: QuestAnnotationDTO) -> bool:
        """Ghi một bản ghi QuestAnnotationDTO vào tệp JSON Lines (Append-only)."""
        data = dto.model_dump()
        line = json.dumps(data, ensure_ascii=False) + "\n"
        with self._lock:
            try:
                with open(self.storage_path, "a", encoding="utf-8") as f:
                    f.write(line)
                return True
            except Exception as e:
                print(f"[FeedbackManager] Lỗi khi lưu annotation: {e}")
                return False

    def get_all_annotations(self) -> List[QuestAnnotationDTO]:
        """Đọc toàn bộ danh sách ghi chú từ kho lưu trữ."""
        if not self.storage_path.exists():
            return []

        results: List[QuestAnnotationDTO] = []
        with self._lock:
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                data = json.loads(line)
                                results.append(QuestAnnotationDTO(**data))
                            except Exception:
                                continue
            except Exception as e:
                print(f"[FeedbackManager] Lỗi khi đọc annotations: {e}")
        return results

    def get_open_annotations(self) -> List[QuestAnnotationDTO]:
        """Lọc ra các ghi chú chưa được giải quyết (status == 'OPEN')."""
        return [a for a in self.get_all_annotations() if a.status == "OPEN"]

    def filter_by_category(self, category: ErrorCategoryEnum | str) -> List[QuestAnnotationDTO]:
        """Lọc các ghi chú theo nhóm lỗi (ErrorCategory)."""
        cat_val = category.value if isinstance(category, ErrorCategoryEnum) else str(category)
        return [a for a in self.get_all_annotations() if a.error_category.value == cat_val]

    def filter_by_severity(self, severity: FeedbackSeverityEnum | str) -> List[QuestAnnotationDTO]:
        """Lọc các ghi chú theo mức độ nghiêm trọng (Severity)."""
        sev_val = severity.value if isinstance(severity, FeedbackSeverityEnum) else str(severity)
        return [a for a in self.get_all_annotations() if a.severity.value == sev_val]

    def search_annotations(
        self,
        keyword: Optional[str] = None,
        tag: Optional[str] = None
    ) -> List[QuestAnnotationDTO]:
        """Tìm kiếm ghi chú theo từ khóa hoặc thẻ (tag)."""
        all_notes = self.get_all_annotations()
        results = all_notes

        if tag:
            t_lower = tag.lower()
            results = [a for a in results if any(t_lower == t.lower() for t in a.tags)]

        if keyword:
            kw = keyword.lower()
            results = [
                a for a in results
                if kw in a.prompt.lower()
                or kw in a.user_note.lower()
                or (a.expected_behavior and kw in a.expected_behavior.lower())
                or (a.expected_route and kw in a.expected_route.lower())
                or (a.actual_route and kw in a.actual_route.lower())
            ]

        return results

    def mark_resolved(self, annotation_id: str, resolution_notes: str = "") -> bool:
        """Đánh dấu một ghi chú đã được khắc phục/xử lý."""
        all_notes = self.get_all_annotations()
        found = False
        updated_notes = []

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        for note in all_notes:
            if note.annotation_id == annotation_id:
                note.status = "RESOLVED"
                note.resolved_at = now_iso
                note.resolution_notes = resolution_notes
                found = True
            updated_notes.append(note)

        if not found:
            return False

        with self._lock:
            try:
                with open(self.storage_path, "w", encoding="utf-8") as f:
                    for note in updated_notes:
                        f.write(json.dumps(note.model_dump(), ensure_ascii=False) + "\n")
                return True
            except Exception as e:
                print(f"[FeedbackManager] Lỗi khi cập nhật annotation: {e}")
                return False
