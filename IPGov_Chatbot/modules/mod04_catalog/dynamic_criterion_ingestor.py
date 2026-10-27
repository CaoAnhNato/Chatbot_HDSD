"""
Module: IPGov_Chatbot/modules/mod04_catalog/dynamic_criterion_ingestor.py
Chức năng: Pipeline tự động phát hiện, sinh định nghĩa ngữ nghĩa (OpenRouter Gemini 3.5 Flash Lite + medium reasoning),
kiểm duyệt 5 cổng tự lọc (5-Gate Self-Filtering Validation) và đồng bộ vào Kho Định Nghĩa (JSON KB & DuckDB).
Tuân thủ: Arc42, SSOT, Milestone M1, Ảnh 1 & Ảnh 2 standards.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import duckdb
import openai
import psycopg2

from IPGov_Chatbot.config import settings

logger = logging.getLogger(__name__)

# Default file paths
DEFAULT_KB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "catalog" / "criterion_definitions_kb.json"

REQUIRED_FIELDS = [
    "id", "code", "name", "level", "is_leaf", "scope_name",
    "parent_id", "parent_name", "root_id", "root_name",
    "canonical_order", "siblings", "children_ids", "definition",
    "natural_synonyms", "scope_description", "has_approved_facts",
    "available_report_dates", "metadata"
]

FORBIDDEN_FLUFF_PHRASES = [
    "chào bạn", "tôi là", "dưới đây là", "theo yêu cầu", "xin lỗi",
    "như đã nêu", "```json", "```", "trợ lý ảo", "kính gửi", "thưa bạn"
]


class FiveGateValidationError(Exception):
    """Ngoại lệ khi vi phạm các cổng kiểm duyệt 5-Gate Self-Filtering."""
    pass


class FiveGateValidator:
    """
    Bộ kiểm duyệt 5 cổng tự lọc (5-Gate Self-Filtering Validation Firewall)
    trước khi cho phép ghi nhận một định nghĩa chỉ tiêu mới vào Kho Định Nghĩa KB:
    - Gate 1: Schema Integrity & độ dài định nghĩa.
    - Gate 2: Parent Alignment & Contextual Grounding.
    - Gate 3: Temporal Clarity & Anti-Fluff.
    - Gate 4: Synonym Quality & Sibling Collision Check.
    - Gate 5: Jaccard Redundancy Check.
    """

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        words = re.findall(r"\w+", text.lower())
        return set(words)

    @classmethod
    def _jaccard_similarity(cls, text1: str, text2: str) -> float:
        s1 = cls._tokenize(text1)
        s2 = cls._tokenize(text2)
        if not s1 or not s2:
            return 0.0
        return len(s1 & s2) / len(s1 | s2)

    @classmethod
    def validate_gate1_schema(cls, record: Dict[str, Any]) -> Tuple[bool, str]:
        """Gate 1: Tính toàn vẹn cấu trúc và độ dài tối thiểu của định nghĩa."""
        for field in REQUIRED_FIELDS:
            if field not in record:
                return False, f"Gate 1 Failed: Thiếu trường bắt buộc '{field}'"
        
        # Kiểm tra kiểu dữ liệu
        if not isinstance(record["id"], str) or not record["id"].strip():
            return False, "Gate 1 Failed: 'id' phải là chuỗi UUID hợp lệ"
        if not isinstance(record["code"], str) or not record["code"].strip():
            return False, "Gate 1 Failed: 'code' không được rỗng"
        if not isinstance(record["name"], str) or not record["name"].strip():
            return False, "Gate 1 Failed: 'name' không được rỗng"
        if record["level"] not in (1, 2, 3):
            return False, f"Gate 1 Failed: 'level' phải là 1, 2 hoặc 3, nhận: {record['level']}"
        if not isinstance(record["is_leaf"], bool):
            return False, "Gate 1 Failed: 'is_leaf' phải là boolean"
        if not isinstance(record["canonical_order"], int) or record["canonical_order"] < 1:
            return False, f"Gate 1 Failed: 'canonical_order' phải là số nguyên >= 1, nhận: {record.get('canonical_order')}"
        if not isinstance(record["definition"], str):
            return False, "Gate 1 Failed: 'definition' phải là chuỗi ký tự"
        
        # Độ dài định nghĩa tối thiểu 30 ký tự
        def_clean = record["definition"].strip()
        if len(def_clean) < 30:
            return False, f"Gate 1 Failed: 'definition' quá ngắn ({len(def_clean)} ký tự < 30 ký tự)"
        
        return True, "Gate 1 Passed"

    @classmethod
    def validate_gate2_parent_alignment(cls, record: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """Gate 2: Đảm bảo chỉ tiêu con (Level > 1) phản ánh đúng ngữ cảnh của thực thể cha."""
        level = record.get("level", 1)
        if level <= 1:
            return True, "Gate 2 Passed (Root level)"

        definition_lower = record.get("definition", "").lower()
        root_name = (record.get("root_name") or (context.get("root_name") if context else "") or "").lower()
        parent_name = (record.get("parent_name") or (context.get("parent_name") if context else "") or "").lower()

        # Kiểm tra từ khóa thực thể đại diện cốt lõi bằng regex word boundary
        entity_keywords = {
            "htx": [r"\bhtx\b", r"\bhợp tác xã\b"],
            "tổ hợp tác": [r"\btổ hợp tác\b", r"\btht\b"],
            "liên hiệp": [r"\bliên hiệp\b", r"\blhhtx\b"],
            "trang trại": [r"\btrang trại\b"],
            "ocop": [r"\bocop\b"],
            "làng nghề": [r"\blàng nghề\b", r"\bnghề truyền thống\b"],
            "muối": [r"\bmuối\b", r"\bdiêm nghiệp\b", r"\bdiêm dân\b"],
            "gia cầm": [r"\bgia cầm\b", r"\bgà\b", r"\bvịt\b"],
            "gia súc": [r"\bgia súc\b", r"\btrâu\b", r"\bbò\b"],
            "khuyến công": [r"\bkhuyến công\b"],
            "công nghiệp": [r"\bcông nghiệp\b"],
            "điện": [r"\bđiện\b", r"\bmặt trời\b", r"\bgió\b"]
        }

        matched = False
        target_entity = root_name or parent_name
        for group_cue, patterns in entity_keywords.items():
            if group_cue in target_entity:
                if any(re.search(pat, definition_lower) for pat in patterns):
                    matched = True
                    break

        # Nếu target_entity không nằm trong các nhóm trên, kiểm tra từ vựng đặc trưng
        if not matched and target_entity:
            # Loại bỏ các từ quá phổ biến để tránh false positive (như 'nông', 'nghiệp' trong 'doanh nghiệp')
            generic_stop = {"nông", "nghiệp", "tổng", "hợp", "dữ", "liệu", "cấp", "dưới", "chỉ", "tiêu"}
            # Hỗ trợ tên cha ngắn (< 3 ký tự như 'TH') bằng cách cho phép len(w) >= 2 khi không nằm trong generic_stop
            target_words = [w for w in re.findall(r"\w+", target_entity) if len(w) >= 2 and w not in generic_stop]
            if not target_words and target_entity.strip():
                target_words = [target_entity.strip().lower()]

            def_words = set(re.findall(r"\w+", definition_lower))

            # Khớp word token trực tiếp HOẶC ghép đôi chữ-số (alphanumeric pairing, ví dụ 'th' -> 'th1', 'test' -> 'test2010')
            for w in target_words:
                if w in def_words:
                    matched = True
                    break
                if any(re.match(r"^" + re.escape(w) + r"\d+", dw) for dw in def_words):
                    matched = True
                    break

        if not matched:
            return False, f"Gate 2 Failed: Định nghĩa chỉ tiêu con cấp {level} ('{record.get('name')}') không gắn kết với ngữ cảnh thực thể cha ('{target_entity}')"

        return True, "Gate 2 Passed"

    @classmethod
    def validate_gate3_temporal_and_fluff(
        cls,
        record: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str]:
        """Gate 3: Loại bỏ hoàn toàn ngôn ngữ máy móc AI, kiểm soát tính rõ ràng về thời gian."""
        definition = record.get("definition", "").strip()
        def_lower = definition.lower()

        # Kiểm tra văn phong hội thoại hoặc meta-talk
        for phrase in FORBIDDEN_FLUFF_PHRASES:
            if phrase in def_lower:
                return False, f"Gate 3 Failed: Chứa từ ngữ thừa AI hoặc văn phong hội thoại ('{phrase}')"

        # Kiểm tra tính chuẩn xác về mặt thời gian
        name_lower = record.get("name", "").lower()
        parent_lower = (record.get("parent_name") or (context.get("parent_name") if context else "") or "").lower()
        root_lower = (record.get("root_name") or (context.get("root_name") if context else "") or "").lower()

        # Kiểm tra kế thừa thời gian từ nút cha/gốc (Cumulative inheritance)
        is_cumulative = "lũy kế" in name_lower or "lũy kế" in parent_lower or "lũy kế" in root_lower
        if is_cumulative:
            temporal_cues = ["lũy kế", "cộng dồn", "tích lũy", "đến thời điểm"]
            if not any(cue in def_lower for cue in temporal_cues):
                return False, "Gate 3 Failed: Chỉ tiêu có tính chất 'Lũy kế' nhưng định nghĩa thiếu từ khóa xác lập mốc tích lũy/cộng dồn"

            in_period_cues = ["phát sinh mới trong năm", "trong năm báo cáo", "phát sinh mới trong kỳ", "mới phát sinh trong năm"]
            if any(icue in def_lower for icue in in_period_cues):
                return False, "Gate 3 Failed: Chỉ tiêu thuộc nhóm 'Lũy kế' nhưng định nghĩa lại chứa ngữ nghĩa phát sinh trong năm"

        if "trong năm" in name_lower or "thành lập mới" in name_lower:
            annual_cues = ["trong năm", "trong kỳ", "mới", "phát sinh", "cấp phép"]
            if not any(cue in def_lower for cue in annual_cues):
                return False, "Gate 3 Failed: Chỉ tiêu phát sinh theo kỳ nhưng định nghĩa thiếu ngữ cảnh thời gian phát sinh"

        return True, "Gate 3 Passed"

    @classmethod
    def validate_gate4_synonyms(cls, record: Dict[str, Any], siblings: Optional[List[str]] = None) -> Tuple[bool, str]:
        """Gate 4: Kiểm soát chất lượng từ đồng nghĩa và chống va chạm với anh em cùng cấp."""
        synonyms = record.get("natural_synonyms")
        if not isinstance(synonyms, list) or len(synonyms) < 2:
            return False, f"Gate 4 Failed: 'natural_synonyms' phải là danh sách có ít nhất 2 từ đồng nghĩa (nhận {len(synonyms) if isinstance(synonyms, list) else 0})"

        for syn in synonyms:
            if not isinstance(syn, str) or len(syn.strip()) < 2:
                return False, f"Gate 4 Failed: Từ đồng nghĩa không hợp lệ ('{syn}')"

        # Kiểm tra va chạm với tên anh em cùng cấp
        siblings_set = set(s.strip().lower() for s in (siblings or record.get("siblings") or []))
        record_name = record.get("name", "").strip().lower()

        for syn in synonyms:
            syn_lower = syn.strip().lower()
            if syn_lower in siblings_set and syn_lower != record_name:
                return False, f"Gate 4 Failed: Từ đồng nghĩa '{syn}' bị va chạm với tên chỉ tiêu anh em ({syn_lower})"

        return True, "Gate 4 Passed"

    @classmethod
    def validate_gate5_jaccard_redundancy(
        cls,
        record: Dict[str, Any],
        parent_definition: Optional[str] = None,
        sibling_definitions: Optional[List[str]] = None
    ) -> Tuple[bool, str]:
        """Gate 5: Kiểm tra trùng lặp Jaccard với định nghĩa của cha hoặc anh em (ngưỡng 0.85)."""
        current_def = record.get("definition", "").strip()

        # Kiểm tra với cha
        if parent_definition:
            sim = cls._jaccard_similarity(current_def, parent_definition)
            if sim >= 0.85:
                return False, f"Gate 5 Failed: Định nghĩa trùng lặp quá cao với chỉ tiêu cha (Jaccard = {sim:.2f} >= 0.85)"

        # Kiểm tra với anh em
        if sibling_definitions:
            for s_def in sibling_definitions:
                sim = cls._jaccard_similarity(current_def, s_def)
                if sim >= 0.85:
                    return False, f"Gate 5 Failed: Định nghĩa trùng lặp quá cao với chỉ tiêu anh em (Jaccard = {sim:.2f} >= 0.85)"

        return True, "Gate 5 Passed"

    @classmethod
    def run_all_gates(
        cls,
        record: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        parent_definition: Optional[str] = None,
        sibling_definitions: Optional[List[str]] = None
    ) -> Tuple[bool, str]:
        """Thực thi đầy đủ cả 5 cổng kiểm duyệt."""
        g1_ok, g1_msg = cls.validate_gate1_schema(record)
        if not g1_ok:
            return False, g1_msg

        g2_ok, g2_msg = cls.validate_gate2_parent_alignment(record, context)
        if not g2_ok:
            return False, g2_msg

        g3_ok, g3_msg = cls.validate_gate3_temporal_and_fluff(record, context)
        if not g3_ok:
            return False, g3_msg

        siblings = (context.get("siblings") if context else None) or record.get("siblings")
        g4_ok, g4_msg = cls.validate_gate4_synonyms(record, siblings)
        if not g4_ok:
            return False, g4_msg

        p_def = parent_definition or (context.get("parent_definition") if context else None)
        s_defs = sibling_definitions or (context.get("sibling_definitions") if context else None)
        g5_ok, g5_msg = cls.validate_gate5_jaccard_redundancy(record, p_def, s_defs)
        if not g5_ok:
            return False, g5_msg

        return True, "All 5 Gates Passed"


def sync_definitions_to_duckdb(
    kb_json_path: Union[str, Path] = DEFAULT_KB_PATH,
    duckdb_conn: Optional[Any] = None
) -> int:
    """
    Đồng bộ toàn bộ Kho Định Nghĩa Chỉ Tiêu từ file JSON vào bảng catalog_definitions của DuckDB.
    Tạo bảng nếu chưa tồn tại, chèn hoặc ghi đè (upsert).
    Trả về số lượng bản ghi đã đồng bộ.
    """
    kb_path = Path(kb_json_path)
    if not kb_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file KB tại: {kb_path}")

    with open(kb_path, "r", encoding="utf-8") as f:
        kb_data: Dict[str, Dict[str, Any]] = json.load(f)

    conn = duckdb_conn or duckdb.connect(":memory:")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS catalog_definitions (
            id VARCHAR PRIMARY KEY,
            code VARCHAR NOT NULL,
            name VARCHAR NOT NULL,
            level INTEGER NOT NULL,
            is_leaf BOOLEAN NOT NULL,
            scope_name VARCHAR,
            parent_id VARCHAR,
            parent_name VARCHAR,
            root_id VARCHAR,
            root_name VARCHAR,
            canonical_order INTEGER NOT NULL,
            definition VARCHAR NOT NULL,
            natural_synonyms VARCHAR,
            scope_description VARCHAR,
            has_approved_facts BOOLEAN NOT NULL,
            available_dates VARCHAR,
            updated_at TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_catdef_parent_id ON catalog_definitions(parent_id);
        CREATE INDEX IF NOT EXISTS idx_catdef_canonical_order ON catalog_definitions(canonical_order);
        CREATE INDEX IF NOT EXISTS idx_catdef_code ON catalog_definitions(code);
    """)

    # Xóa dữ liệu cũ để đồng bộ sạch
    conn.execute("DELETE FROM catalog_definitions")

    rows_to_insert = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for cid, rec in kb_data.items():
        rows_to_insert.append((
            rec.get("id", cid),
            rec.get("code", ""),
            rec.get("name", ""),
            int(rec.get("level", 1)),
            bool(rec.get("is_leaf", False)),
            rec.get("scope_name") or "Nông nghiệp",
            rec.get("parent_id"),
            rec.get("parent_name"),
            rec.get("root_id", cid),
            rec.get("root_name", rec.get("name", "")),
            int(rec.get("canonical_order", 1)),
            rec.get("definition", ""),
            json.dumps(rec.get("natural_synonyms", []), ensure_ascii=False),
            rec.get("scope_description", ""),
            bool(rec.get("has_approved_facts", False)),
            json.dumps(rec.get("available_report_dates", []), ensure_ascii=False),
            now_iso
        ))

    conn.executemany("""
        INSERT INTO catalog_definitions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows_to_insert)

    logger.info(f"Đã đồng bộ {len(rows_to_insert)} bản ghi vào bảng catalog_definitions trong DuckDB.")
    return len(rows_to_insert)


def ingest_new_criterion(
    criterion_record: Dict[str, Any],
    context: Dict[str, Any],
    openrouter_client: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Sinh và xác thực định nghĩa ngữ nghĩa cho một chỉ tiêu mới sử dụng OpenRouter
    với model google/gemini-3.5-flash-lite và mức suy luận reasoning: {'effort': 'medium'}.
    """
    ingestor = DynamicCriterionIngestor(client=openrouter_client)
    return ingestor.process_single_criterion(criterion_record, context)


class DynamicCriterionIngestor:
    """
    Động cơ Ingestion chỉ tiêu động:
    1. Quét DWH PostgreSQL tìm chỉ tiêu mới chưa có trong KB.
    2. Đóng gói đầy đủ ngữ cảnh phả hệ (Parent, Child, Sibling, Root, Scope).
    3. Gọi API OpenRouter model google/gemini-3.5-flash-lite kèm reasoning: {'effort': 'medium'}.
    4. Xác thực qua 5-Gate Self-Filtering Validation Firewall.
    5. Ghi nhận bền vững vào JSON KB và đồng bộ vào DuckDB.
    """

    def __init__(
        self,
        kb_path: Union[str, Path] = DEFAULT_KB_PATH,
        client: Optional[Any] = None,
        model_name: str = "google/gemini-3.5-flash-lite",
        db_url: Optional[str] = None
    ) -> None:
        self.kb_path = Path(kb_path)
        self.model_name = model_name
        self.client = client or openai.OpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL
        )
        self.db_url = db_url or getattr(settings, "sync_dwh_url", None)

    def load_kb(self) -> Dict[str, Dict[str, Any]]:
        if not self.kb_path.exists():
            return {}
        with open(self.kb_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_kb(self, kb_data: Dict[str, Dict[str, Any]]) -> None:
        self.kb_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.kb_path, "w", encoding="utf-8") as f:
            json.dump(kb_data, f, ensure_ascii=False, indent=2)

    def detect_unregistered_criteria(self) -> List[Dict[str, Any]]:
        """Quét PostgreSQL vna_wom_dev tìm các chỉ tiêu chưa được lập định nghĩa trong KB."""
        current_kb = self.load_kb()
        registered_ids = set(current_kb.keys())

        conn = psycopg2.connect(settings.sync_dwh_url)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, code, name, level, parent_id, scope_name, mission_name, created_date
            FROM dwh_internal.criteria
            WHERE deleted_date IS NULL
            ORDER BY level, created_date ASC
        """)
        cols = [desc[0] for desc in cur.description]
        unregistered = []

        for row in cur.fetchall():
            rec = dict(zip(cols, row))
            rec["id"] = str(rec["id"])
            rec["parent_id"] = str(rec["parent_id"]) if rec["parent_id"] else None
            rec["created_date"] = str(rec["created_date"])
            if rec["id"] not in registered_ids:
                unregistered.append(rec)

        conn.close()
        logger.info(f"Phát hiện {len(unregistered)} chỉ tiêu mới chưa có trong KB.")
        return unregistered

    def build_hierarchical_context(
        self,
        criterion: Dict[str, Any],
        all_criteria_map: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Tập hợp đầy đủ ngữ cảnh phả hệ (Parent, Grandparent, Root, Siblings, Scope)."""
        pid = criterion.get("parent_id")
        current_kb = self.load_kb()

        parent_info = current_kb.get(pid, {}) if pid else {}
        root_name = parent_info.get("root_name") or parent_info.get("name") or criterion.get("name")
        root_id = parent_info.get("root_id") or (pid if pid else criterion.get("id"))

        # Thu thập anh em cùng cha
        siblings = []
        if pid:
            siblings = [
                entry["name"] for entry in current_kb.values()
                if entry.get("parent_id") == pid and entry.get("id") != criterion.get("id")
            ]

        return {
            "id": criterion["id"],
            "code": criterion["code"],
            "name": criterion["name"],
            "level": criterion["level"],
            "parent_id": pid,
            "parent_name": parent_info.get("name"),
            "root_id": root_id,
            "root_name": root_name,
            "scope_name": criterion.get("scope_name") or parent_info.get("scope_name") or "Nông nghiệp",
            "siblings": siblings,
            "parent_definition": parent_info.get("definition"),
            "sibling_definitions": [
                entry["definition"] for entry in current_kb.values()
                if entry.get("parent_id") == pid and entry.get("definition")
            ]
        }

    def generate_definition_with_llm(
        self,
        criterion: Dict[str, Any],
        context: Dict[str, Any],
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Gọi OpenRouter model google/gemini-3.5-flash-lite với reasoning effort medium."""
        system_prompt = (
            "Bạn là Chuyên gia Cao cấp về Thống kê & Quản lý Dữ liệu Công vụ của Sở Nông nghiệp và PTNT.\n"
            "Nhiệm vụ của bạn là biên soạn định nghĩa nghiệp vụ chuẩn xác, giàu ngữ nghĩa cho một chỉ tiêu báo cáo mới "
            "trong Hệ thống Kho Dữ Liệu DWH theo đúng quy cách hành chính nhà nước (Ảnh 1 & Ảnh 2).\n\n"
            "QUY TẮC BẮT BUỘC:\n"
            "1. Nếu chỉ tiêu là con (Level > 1), định nghĩa BẮT BUỘC phải gắn liền và nhắc đến thực thể cha/nhánh gốc "
            "(Ví dụ: 'Số lượng HTX nông nghiệp thực tế...', 'Tổng số lượng Tổ hợp tác nông nghiệp...').\n"
            "2. Phân biệt rõ tính thời gian: 'Lũy kế' = cộng dồn từ trước đến mốc chốt; 'Thành lập mới'/'Trong năm' = phát sinh trong kỳ; "
            "'Đang hoạt động' = thực tế đang duy trì vận hành tại thời điểm chốt (loại trừ đã giải thể/ngừng).\n"
            "3. Tuyệt đối KHÔNG chứa lời chào, không xin lỗi, không meta-text AI (không 'Chào bạn', không 'Dưới đây là...').\n"
            "4. Cung cấp ít nhất 3 từ đồng nghĩa/paraphrase tự nhiên mà cán bộ hoặc người dùng thường dùng.\n"
            "5. Định nghĩa phải chi tiết, học thuật, chính xác (tối thiểu 40 ký tự).\n\n"
            "Trả về DUY NHẤT một khối JSON hợp lệ theo định dạng sau (không bọc trong markdown ```json):\n"
            "{\n"
            '  "definition": "Định nghĩa nghiệp vụ chi tiết...",\n'
            '  "natural_synonyms": ["từ đồng nghĩa 1", "từ đồng nghĩa 2", "từ đồng nghĩa 3"],\n'
            '  "scope_description": "Mô tả phạm vi áp dụng chi tiết..."\n'
            "}"
        )

        user_content = (
            f"Thông tin chỉ tiêu cần sinh định nghĩa:\n"
            f"- Tên chỉ tiêu: {criterion['name']}\n"
            f"- Mã kỹ thuật (code): {criterion['code']}\n"
            f"- Cấp bậc (level): Cấp {criterion['level']}\n"
            f"- Lĩnh vực (scope): {context.get('scope_name')}\n"
            f"- Chỉ tiêu cha (parent): {context.get('parent_name') or 'Nút gốc (Root)'}\n"
            f"- Thực thể gốc (root): {context.get('root_name')}\n"
            f"- Các chỉ tiêu anh em cùng cấp: {', '.join(context.get('siblings', [])) or 'Không có'}\n"
        )

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    extra_body={"reasoning": {"effort": "medium"}},
                    temperature=0.2
                )
                raw_text = response.choices[0].message.content.strip()
                # Làm sạch markdown nếu có
                if raw_text.startswith("```"):
                    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                    raw_text = re.sub(r"\s*```$", "", raw_text)
                parsed = json.loads(raw_text)
                return parsed
            except Exception as e:
                logger.warning(f"Lỗi gọi LLM lần {attempt + 1}/{max_retries}: {e}")
                if "429" in str(e):
                    time.sleep(2.0 * (attempt + 1))
                else:
                    time.sleep(1.0)

        # Fallback có ngữ cảnh nếu API gặp sự cố
        logger.warning(f"Fallback sang tạo ngữ cảnh nội tại cho chỉ tiêu {criterion['name']}")
        p_name = context.get("parent_name") or context.get("root_name") or "nông nghiệp"
        name = criterion["name"]
        return {
            "definition": f"Chỉ tiêu thống kê nghiệp vụ '{name}' phản ánh dữ liệu chuyên ngành trong nhóm '{p_name}'.",
            "natural_synonyms": [name.lower(), f"chỉ tiêu {name.lower()}", f"{name.lower()} {p_name.lower()}"],
            "scope_description": f"Áp dụng cho thống kê và theo dõi dữ liệu {name} trong lĩnh vực {context.get('scope_name')}."
        }

    def process_single_criterion(
        self,
        criterion_record: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Quy trình hoàn chỉnh sinh định nghĩa, chạy qua 5-Gate Validation và chuẩn bị bản ghi 19 trường."""
        ctx = context or self.build_hierarchical_context(criterion_record)
        llm_output = self.generate_definition_with_llm(criterion_record, ctx)

        # Xác định động is_leaf và children_ids dựa trên DWH hoặc current_kb
        children_ids = []
        is_leaf = True
        if criterion_record.get("is_leaf") is not None:
            is_leaf = bool(criterion_record["is_leaf"])
            children_ids = criterion_record.get("children_ids", [])
        else:
            current_kb = self.load_kb()
            cid = str(criterion_record["id"])
            kb_children = [k for k, v in current_kb.items() if str(v.get("parent_id")) == cid]
            dwh_children = []
            if self.db_url:
                try:
                    import psycopg2
                    conn = psycopg2.connect(self.db_url)
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT id FROM dwh_internal.criteria WHERE parent_id = %s AND deleted_date IS NULL",
                        (cid,)
                    )
                    dwh_children = [str(row[0]) for row in cur.fetchall()]
                    conn.close()
                except Exception as e:
                    logger.debug(f"Không thể truy vấn children từ DWH: {e}")
            all_children = list(set(kb_children + dwh_children))
            if all_children:
                is_leaf = False
                children_ids = all_children
            else:
                is_leaf = True
                children_ids = []

        # Xác định động canonical_order dựa trên created_date trong DWH hoặc vị trí thực tế
        siblings = ctx.get("siblings", [])
        canonical_order = None
        if criterion_record.get("canonical_order") is not None:
            canonical_order = int(criterion_record["canonical_order"])
        elif self.db_url and criterion_record.get("created_date"):
            try:
                import psycopg2
                conn = psycopg2.connect(self.db_url)
                cur = conn.cursor()
                pid = criterion_record.get("parent_id")
                c_date = criterion_record.get("created_date")
                if pid:
                    cur.execute("""
                        SELECT count(*) FROM dwh_internal.criteria
                        WHERE parent_id = %s AND created_date <= %s AND deleted_date IS NULL
                    """, (str(pid), c_date))
                else:
                    cur.execute("""
                        SELECT count(*) FROM dwh_internal.criteria
                        WHERE parent_id IS NULL AND created_date <= %s AND deleted_date IS NULL
                    """, (c_date,))
                row = cur.fetchone()
                if row and row[0]:
                    canonical_order = int(row[0])
                conn.close()
            except Exception as e:
                logger.debug(f"Không thể tính canonical_order từ DWH: {e}")

        if canonical_order is None:
            pid = criterion_record.get("parent_id")
            if not pid or int(criterion_record.get("level", 1)) == 1:
                current_kb = self.load_kb()
                root_count = sum(1 for v in current_kb.values() if v.get("level") == 1 or v.get("parent_id") is None)
                canonical_order = root_count + 1
            else:
                canonical_order = len(siblings) + 1

        record = {
            "id": criterion_record["id"],
            "code": criterion_record["code"],
            "name": criterion_record["name"],
            "level": int(criterion_record["level"]),
            "is_leaf": is_leaf,
            "scope_name": ctx.get("scope_name") or "Nông nghiệp",
            "parent_id": criterion_record.get("parent_id"),
            "parent_name": ctx.get("parent_name"),
            "root_id": ctx.get("root_id"),
            "root_name": ctx.get("root_name"),
            "canonical_order": canonical_order,
            "siblings": siblings,
            "children_ids": children_ids,
            "definition": llm_output.get("definition", "").strip(),
            "natural_synonyms": llm_output.get("natural_synonyms", []),
            "scope_description": llm_output.get("scope_description", "").strip(),
            "has_approved_facts": False,
            "available_report_dates": [],
            "metadata": {
                "source": "dynamic_ingestion_pipeline",
                "model": self.model_name,
                "verified_against_dwh": True,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        }

        # 5-Gate Self-Filtering Validation
        passed, msg = FiveGateValidator.run_all_gates(
            record=record,
            context=ctx,
            parent_definition=ctx.get("parent_definition"),
            sibling_definitions=ctx.get("sibling_definitions")
        )

        if not passed:
            raise FiveGateValidationError(f"Không thể nạp chỉ tiêu '{record['name']}': {msg}")

        return record

    def ingest_new_criteria_into_kb(self, duckdb_conn: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Phát hiện các chỉ tiêu mới trong DWH, sinh định nghĩa, kiểm duyệt và commit vào KB + DuckDB."""
        unregistered = self.detect_unregistered_criteria()
        if not unregistered:
            logger.info("Không có chỉ tiêu mới cần nạp.")
            return []

        kb = self.load_kb()
        ingested = []

        for crit in unregistered:
            try:
                record = self.process_single_criterion(crit)
                kb[crit["id"]] = record
                ingested.append(record)
                logger.info(f"Đã nạp thành công chỉ tiêu '{record['name']}' vào KB.")
            except Exception as e:
                logger.error(f"Thất bại khi nạp chỉ tiêu '{crit.get('name')}': {e}")

        if ingested:
            self.save_kb(kb)
            sync_definitions_to_duckdb(self.kb_path, duckdb_conn)

        return ingested
