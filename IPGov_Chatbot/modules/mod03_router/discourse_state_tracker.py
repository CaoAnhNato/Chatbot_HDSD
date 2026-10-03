"""
Module: IPGov_Chatbot/modules/mod03_router/discourse_state_tracker.py
Chức năng: Tầng quản trị trạng thái hội thoại 3 cấp độ (HFS-DSF - Hierarchical Focus Stack & Dynamic Slot Fusion).
Căn cứ:
- SParC (Yu et al., ACL 2019), CoSQL (EMNLP 2019)
- Focus Stack Theory (Grosz & Sidner, 1986)
- Kế hoạch triển khai v1.4.0 (PLAN-REMEDIATION-v1.4.0)

3 Cấp độ quản trị ngữ cảnh:
1. Level 1 (Contiguous Attribute Pivoting - Q1 -> Q2 -> Q3):
   Quản trị bằng Active State Frame + Dynamic Slot Fusion có chốt kiểm định tương thích CSDL (Schema Compatibility Gate).
2. Level 2 (Interleaved Topic Return):
   Quản trị bằng Hierarchical Focus Stack, duyệt ngược ngăn xếp tìm Frame tương thích khi người dùng hỏi xen ngang nhiều chủ đề.
3. Level 3 (Long-Jump Discourse Resumption):
   Áp dụng Frame-Aware D-SAS (tính điểm tương đồng trên cấu trúc Semantic Frame Object) để khôi phục chủ đề sau nhiều lượt nhảy cóc.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from rapidfuzz import fuzz

logger = logging.getLogger("ipgov.mod03.discourse_state_tracker")


class DialogueStateFrame(BaseModel):
    """
    Cấu trúc Semantic Frame Object lưu trữ đầy đủ thực thể, thuộc tính và miền dữ liệu của mỗi lượt hội thoại.
    """
    turn_index: int = 1
    topic_entity: str = ""                         # e.g. "sản xuất muối", "tai nạn lao động", "cán bộ", "báo cáo"
    metric_attribute: Optional[str] = None          # e.g. "diện tích", "Tổng hộ", "sản lượng", "kinh phí", "chức vụ"
    temporal_slot: Optional[str] = None             # e.g. "2026"
    spatial_slot: str = "68"                        # e.g. "68" (Lâm Đồng)
    department_slot: Optional[str] = None           # e.g. "68-1-01"
    domain: str = "fact_criteria"                    # "fact_criteria" | "report" | "mission_personnel" | "collection_form"
    raw_query: str = ""
    keywords: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HierarchicalFocusStack:
    """
    Ngăn xếp Tiêu điểm Đa Tầng (Grosz & Sidner, 1986).
    Duy trì ngăn xếp các DialogueStateFrame cho một phiên hội thoại, hỗ trợ Push/Pop và duyệt ngược tìm Frame tương thích.
    """
    def __init__(self, max_depth: int = 10):
        self.stack: List[DialogueStateFrame] = []
        self.max_depth = max_depth

    @property
    def frames(self) -> List[DialogueStateFrame]:
        return self.stack

    def __len__(self) -> int:
        return len(self.stack)

    def push(self, frame: DialogueStateFrame) -> None:
        """Đẩy một Frame mới vào đỉnh ngăn xếp."""
        self.stack.append(frame)
        if len(self.stack) > self.max_depth:
            self.stack.pop(0)

    def get_active_frame(self) -> Optional[DialogueStateFrame]:
        """Lấy Frame hiện hành ở đỉnh ngăn xếp (Top Frame)."""
        return self.stack[-1] if self.stack else None

    def find_frame_by_topic(self, topic: str) -> Optional[DialogueStateFrame]:
        """
        [Level 2: Topic Return by Entity]
        Duyệt ngược Focus Stack tìm Frame có topic_entity khớp với topic.
        """
        if not topic:
            return None
        t_low = topic.lower().strip()
        for frame in reversed(self.stack):
            if frame.topic_entity:
                f_low = frame.topic_entity.lower().strip()
                if f_low == t_low or t_low in f_low or f_low in t_low:
                    return frame
        return None

    def find_compatible_frame(self, new_metric: str, catalog: Any = None) -> Optional[DialogueStateFrame]:
        """
        [Level 2: Interleaved Topic Return]
        Duyệt ngược Focus Stack (từ đỉnh xuống đáy) tìm Frame có topic_entity
        tương thích với new_metric thông qua Catalog Schema Compatibility Gate.
        """
        if not new_metric:
            return None

        for frame in reversed(self.stack):
            if not frame.topic_entity:
                continue
            if catalog and hasattr(catalog, "is_compatible"):
                if catalog.is_compatible(frame.topic_entity, new_metric):
                    return frame
            else:
                # Heuristic fallback nếu không có catalog
                t_low = frame.topic_entity.lower()
                m_low = new_metric.lower()
                if ("muối" in t_low and any(w in m_low for w in ["diện tích", "sản lượng", "hộ"])) or \
                   ("lao động" in t_low and any(w in m_low for w in ["vụ", "người", "chết", "tai nạn"])) or \
                   ("cán bộ" in t_low and any(w in m_low for w in ["chức vụ", "phòng", "đơn vị", "nhiệm vụ"])):
                    return frame
        return None

    def find_semantically_similar_frame(
        self, query: str, catalog: Any = None, threshold: float = 0.55
    ) -> Optional[DialogueStateFrame]:
        """
        [Level 3: Frame-Aware D-SAS]
        Tính toán độ tương đồng ngữ nghĩa trên cấu trúc Semantic Frame Object
        (topic_entity, keywords, metric_attribute) thay vì câu hỏi thô.
        """
        if not query or not self.stack:
            return None

        q_clean = query.lower().strip()
        best_frame = None
        best_score = 0.0

        for frame in reversed(self.stack):
            # Xây dựng văn bản biểu diễn Frame
            frame_repr = f"{frame.topic_entity} {' '.join(frame.keywords)} {frame.metric_attribute or ''}".strip().lower()
            if not frame_repr:
                continue

            score = fuzz.token_set_ratio(q_clean, frame_repr) / 100.0
            if score > best_score:
                best_score = score
                best_frame = frame

        if best_score >= threshold and best_frame:
            return best_frame
        return None


class DiscourseStateTracker:
    """
    Bộ quản trị trạng thái hội thoại 3 cấp độ (HFS-DSF).
    Cung cấp API xử lý từng lượt hỏi, phân định rõ ràng giữa:
    - Level 1: Contiguous Attribute Pivoting
    - Level 2: Interleaved Topic Return
    - Level 3: Frame-Aware Discourse Resumption
    - New Topic
    """

    # Danh sách các từ khóa đặc trưng của câu hỏi thuộc tính tỉnh lược (Attribute Pivot)
    ATTRIBUTE_PIVOT_PATTERNS = [
        r"\b(?:diện\s+tích|dien\s+tich)\b",
        r"\b(?:sản\s+lượng|san\s+luong)\b",
        r"\b(?:bao\s+nhiêu\s+hộ|so\s+ho|số\s+hộ|có\s+bao\s+nhiêu\s+hộ)\b",
        r"\b(?:kinh\s+phí|kinh\s+phi|ngân\s+sách|dự\s+toán|giải\s+ngân)\b",
        r"\b(?:chức\s+vụ|chuc\s+vu|vị\s+trí|vi\s+tri)\b",
        r"\b(?:phòng\s+ban|đơn\s+vị|chi\s+cục)\b",
        r"\b(?:ai\s+phụ\s+trách|ai\s+nắm|do\s+ai|người\s+nào)\b",
        r"\b(?:trạng\s+thái|tiến\s+độ|tình\s+hình)\b",
        r"\b(?:bao\s+nhiêu|thế\s+nào|ra\s+sao|như\s+thế\s+nào)\b",
    ]

    def __init__(self) -> None:
        self._sessions: Dict[str, HierarchicalFocusStack] = {}

    def get_focus_stack(self, session_id: str) -> HierarchicalFocusStack:
        """Lấy hoặc tạo mới HierarchicalFocusStack cho session_id."""
        if session_id not in self._sessions:
            self._sessions[session_id] = HierarchicalFocusStack(max_depth=10)
        return self._sessions[session_id]

    def extract_metric_attribute(self, text: str) -> Optional[str]:
        """Trích xuất thuộc tính đo lường / trường thông tin cần hỏi."""
        t_low = text.lower().strip()
        if any(k in t_low for k in ["diện tích", "dien tich", "ha"]):
            return "diện tích"
        if any(k in t_low for k in ["sản lượng", "san luong", "tấn"]):
            return "sản lượng"
        if any(k in t_low for k in ["bao nhiêu hộ", "số hộ", "tong so ho", "hộ"]):
            return "Tổng hộ"
        if any(k in t_low for k in ["kinh phí", "kinh phi", "tiền", "ngân sách"]):
            return "kinh phí"
        if any(k in t_low for k in ["chức vụ", "vị trí"]):
            return "chức vụ"
        if any(k in t_low for k in ["đơn vị công tác", "đơn vị", "phòng ban", "chi cục"]):
            return "đơn vị"
        if any(k in t_low for k in ["ai phụ trách", "ai nắm", "do ai"]):
            return "cán bộ phụ trách"
        if any(k in t_low for k in ["trạng thái", "tiến độ"]):
            return "trạng thái"
        return None

    def extract_topic_entity(self, text: str) -> Optional[str]:
        """Trích xuất thực thể chủ đề từ câu hỏi (nếu có nói rõ)."""
        t_low = text.lower().strip()
        topic_map = [
            ("sản xuất muối", ["sản xuất muối", "san xuat muoi", "diêm nghiệp", "diem nghiep", "muối thủ công", "muối công nghiệp", "muối"]),
            ("tai nạn lao động", ["tai nạn lao động", "tai nan lao dong", "tnlđ", "tnld", "an toàn lao động"]),
            ("khuyến công", ["khuyến công", "khuyen cong"]),
            ("hợp tác xã", ["hợp tác xã", "htx"]),
            ("ocop", ["ocop", "sản phẩm ocop"]),
            ("cán bộ", ["cán bộ", "chuyên viên", "nhân sự", "admin"]),
            ("nhiệm vụ", ["nhiệm vụ", "đề án", "chương trình"]),
            ("báo cáo", ["báo cáo", "đợt nộp", "kỳ nộp"]),
            ("biểu mẫu", ["biểu mẫu", "tờ khai", "bm_01", "bm_02"]),
        ]
        for topic, kws in topic_map:
            if any(kw in t_low for kw in kws):
                return topic
        return None

    def is_attribute_followup(self, text: str) -> bool:
        """Xác định xem câu hỏi có phải là câu hỏi tiếp nối chỉ mang thuộc tính mới hay không."""
        t_low = text.lower().strip()
        # Nếu có từ nối tiếp hoặc câu rất ngắn hỏi đại lượng
        has_followup_cue = any(w in t_low for w in ["vậy", "thế", "thì sao", "còn", "bao nhiêu", "thế nào", "ở đâu"])
        words = t_low.split()
        if len(words) <= 7 and (has_followup_cue or self.extract_metric_attribute(text) is not None):
            # Kiểm tra xem có nói rõ chủ đề mới độc lập không
            explicit_topic = self.extract_topic_entity(text)
            if not explicit_topic:
                return True
            # Nếu có chủ đề nhưng là đại từ thay thế
            if any(w in t_low for w in ["đó", "này", "vừa rồi", "trên"]):
                return True
        return False

    def process_turn(
        self,
        session_id: str,
        turn_index: int,
        query: str,
        catalog: Any = None,
        explicit_year: Optional[str] = None,
        explicit_dept: Optional[str] = None,
        explicit_tenant: Optional[str] = None,
    ) -> Tuple[DialogueStateFrame, str, Optional[str]]:
        """
        Xử lý trạng thái hội thoại cho lượt hỏi hiện tại.
        
        Returns:
            Tuple[DialogueStateFrame, str, Optional[str]]:
                - frame: DialogueStateFrame hiện hành (đã hòa mạng hoặc cập nhật).
                - resolution_level: "LEVEL_1_CONTIGUOUS_PIVOT" | "LEVEL_2_INTERLEAVED_RETURN" | "LEVEL_3_RESUMPTION" | "NEW_TOPIC"
                - standalone_hint: Gợi ý câu hỏi độc lập được kiến tạo.
        """
        stack = self.get_focus_stack(session_id)
        active_frame = stack.get_active_frame()
        q_clean = query.strip()

        metric_attr = self.extract_metric_attribute(q_clean)
        explicit_topic = self.extract_topic_entity(q_clean)
        is_attr_query = self.is_attribute_followup(q_clean)

        # ----------------------------------------------------------------------
        # LEVEL 1: Contiguous Attribute Pivoting (Q1 -> Q2 -> Q3)
        # ----------------------------------------------------------------------
        if active_frame and metric_attr and (not explicit_topic or explicit_topic == active_frame.topic_entity):
            # Kiểm tra Schema Compatibility Gate với Active Frame
            is_compat = False
            if catalog and hasattr(catalog, "is_compatible"):
                is_compat = catalog.is_compatible(active_frame.topic_entity, metric_attr)
            else:
                is_compat = True  # Fallback

            if is_compat and (is_attr_query or not explicit_topic):
                fused_frame = DialogueStateFrame(
                    turn_index=turn_index,
                    topic_entity=active_frame.topic_entity,
                    metric_attribute=metric_attr,
                    temporal_slot=explicit_year or active_frame.temporal_slot,
                    spatial_slot=active_frame.spatial_slot,
                    department_slot=explicit_dept or active_frame.department_slot,
                    domain=active_frame.domain,
                    raw_query=q_clean,
                    keywords=list(set(active_frame.keywords + [metric_attr])),
                    metadata={"parent_turn": active_frame.turn_index, "resolution": "LEVEL_1_CONTIGUOUS_PIVOT"}
                )
                stack.push(fused_frame)
                standalone_hint = f"{metric_attr} {active_frame.topic_entity} năm {fused_frame.temporal_slot or '2026'}"
                logger.info("[Level 1 Pivot] Fused attribute '%s' into active topic '%s'", metric_attr, active_frame.topic_entity)
                return (fused_frame, "LEVEL_1_CONTIGUOUS_PIVOT", standalone_hint)

        # ----------------------------------------------------------------------
        # LEVEL 2: Interleaved Topic Return (Hồi sinh chủ đề đã qua trong Stack)
        # ----------------------------------------------------------------------
        # Trường hợp 2A: Người dùng đề cập rõ chủ đề cũ đã từng xuất hiện trong stack
        if active_frame and explicit_topic:
            revived_frame = stack.find_frame_by_topic(explicit_topic)
            if revived_frame and revived_frame.turn_index != active_frame.turn_index:
                fused_frame = DialogueStateFrame(
                    turn_index=turn_index,
                    topic_entity=revived_frame.topic_entity,
                    metric_attribute=metric_attr or revived_frame.metric_attribute,
                    temporal_slot=explicit_year or revived_frame.temporal_slot,
                    spatial_slot=revived_frame.spatial_slot,
                    department_slot=explicit_dept or revived_frame.department_slot,
                    domain=revived_frame.domain,
                    raw_query=q_clean,
                    keywords=list(set(revived_frame.keywords + ([metric_attr] if metric_attr else []))),
                    metadata={"revived_turn": revived_frame.turn_index, "resolution": "LEVEL_2_INTERLEAVED_RETURN"}
                )
                stack.push(fused_frame)
                standalone_hint = f"{fused_frame.metric_attribute or ''} {fused_frame.topic_entity} năm {fused_frame.temporal_slot or '2026'}".strip()
                logger.info("[Level 2 Topic Return] Revived past topic '%s' from Turn %d for query '%s'",
                            revived_frame.topic_entity, revived_frame.turn_index, q_clean)
                return (fused_frame, "LEVEL_2_INTERLEAVED_RETURN", standalone_hint)

        # Trường hợp 2B: Người dùng chỉ hỏi thuộc tính mới, tương thích với Frame cũ trong stack
        if active_frame and metric_attr and is_attr_query:
            compat_frame = stack.find_compatible_frame(metric_attr, catalog=catalog)
            if compat_frame and compat_frame.turn_index != active_frame.turn_index:
                fused_frame = DialogueStateFrame(
                    turn_index=turn_index,
                    topic_entity=compat_frame.topic_entity,
                    metric_attribute=metric_attr,
                    temporal_slot=explicit_year or compat_frame.temporal_slot,
                    spatial_slot=compat_frame.spatial_slot,
                    department_slot=explicit_dept or compat_frame.department_slot,
                    domain=compat_frame.domain,
                    raw_query=q_clean,
                    keywords=list(set(compat_frame.keywords + [metric_attr])),
                    metadata={"revived_turn": compat_frame.turn_index, "resolution": "LEVEL_2_INTERLEAVED_RETURN"}
                )
                stack.push(fused_frame)
                standalone_hint = f"{metric_attr} {compat_frame.topic_entity} năm {fused_frame.temporal_slot or '2026'}"
                logger.info("[Level 2 Metric Return] Revived past topic '%s' from Turn %d for attribute '%s'",
                            compat_frame.topic_entity, compat_frame.turn_index, metric_attr)
                return (fused_frame, "LEVEL_2_INTERLEAVED_RETURN", standalone_hint)

        # ----------------------------------------------------------------------
        # LEVEL 3: Long-Jump Discourse Resumption (Frame-Aware D-SAS)
        # ----------------------------------------------------------------------
        if active_frame and turn_index > 2:
            similar_frame = stack.find_semantically_similar_frame(q_clean, catalog=catalog, threshold=0.60)
            if similar_frame and similar_frame.turn_index != active_frame.turn_index:
                fused_frame = DialogueStateFrame(
                    turn_index=turn_index,
                    topic_entity=similar_frame.topic_entity,
                    metric_attribute=metric_attr or similar_frame.metric_attribute,
                    temporal_slot=explicit_year or similar_frame.temporal_slot,
                    spatial_slot=similar_frame.spatial_slot,
                    department_slot=explicit_dept or similar_frame.department_slot,
                    domain=similar_frame.domain,
                    raw_query=q_clean,
                    keywords=list(set(similar_frame.keywords + ([metric_attr] if metric_attr else []))),
                    metadata={"resumed_turn": similar_frame.turn_index, "resolution": "LEVEL_3_RESUMPTION"}
                )
                stack.push(fused_frame)
                standalone_hint = f"{fused_frame.metric_attribute or ''} {fused_frame.topic_entity} năm {fused_frame.temporal_slot or '2026'}".strip()
                logger.info("[Level 3 Resumption] Resumed past frame from Turn %d", similar_frame.turn_index)
                return (fused_frame, "LEVEL_3_RESUMPTION", standalone_hint)

        # ----------------------------------------------------------------------
        # DEFAULT: New Topic / Explicit Query
        # ----------------------------------------------------------------------
        topic = explicit_topic or (metric_attr if metric_attr else q_clean[:50])
        domain = "fact_criteria"
        if any(k in q_clean.lower() for k in ["cán bộ", "chuyên viên", "admin", "qtv"]):
            domain = "mission_personnel"
        elif any(k in q_clean.lower() for k in ["báo cáo", "nộp", "kỳ"]):
            domain = "report"
        elif any(k in q_clean.lower() for k in ["biểu mẫu", "tờ khai"]):
            domain = "collection_form"
        elif any(k in q_clean.lower() for k in ["nhiệm vụ", "đề án"]):
            domain = "mission_personnel"

        new_frame = DialogueStateFrame(
            turn_index=turn_index,
            topic_entity=topic,
            metric_attribute=metric_attr,
            temporal_slot=explicit_year or (active_frame.temporal_slot if active_frame else None),
            spatial_slot=explicit_tenant or (active_frame.spatial_slot if active_frame else "68"),
            department_slot=explicit_dept or (active_frame.department_slot if active_frame else None),
            domain=domain,
            raw_query=q_clean,
            keywords=[topic] if topic else [],
            metadata={"resolution": "NEW_TOPIC"}
        )
        stack.push(new_frame)
        standalone_hint = None
        if active_frame and new_frame.temporal_slot and not explicit_year:
            standalone_hint = f"{topic} năm {new_frame.temporal_slot}"
        return (new_frame, "NEW_TOPIC", standalone_hint)
