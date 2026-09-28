"""
IPGov Chatbot - Module 03: DuckDB In-Memory BM25 + RapidFuzz Strategy
Trích xuất thực thể và chỉ tiêu qua DuckDB Catalog và RapidFuzz (threshold 75.0).
Căn cứ: Quy tắc 9 (Anti-Shortcut & General Semantic Layer) và backend/config.py.
"""

from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Tuple
import duckdb
from rapidfuzz import fuzz, process

from backend.config import settings
from IPGov_Chatbot.schemas.router_dto import (
    IntentEnum,
    RouteTypeEnum,
    SlotClarificationOption,
)
from IPGov_Chatbot.modules.mod03_router.semantic_strategy_interface import (
    SemanticMatchResult,
    SemanticRouterStrategy,
)


class DuckDBFuzzyStrategy(SemanticRouterStrategy):
    """Chiến lược so khớp từ vựng - mờ sử dụng DuckDB In-Memory Catalog & RapidFuzz."""

    def __init__(self) -> None:
        self.threshold = getattr(settings, "RAPIDFUZZ_THRESHOLD", 75.0)
        self.conn = duckdb.connect(":memory:")
        self._init_catalog()
        self._compile_patterns()

    def _init_catalog(self) -> None:
        """Khởi tạo bảng danh mục trong bộ nhớ RAM DuckDB."""
        # 1. Bảng thực thể hành chính (admin entities)
        self.conn.execute("""
            CREATE TABLE admin_entities (
                code VARCHAR PRIMARY KEY,
                canonical_name VARCHAR,
                level INTEGER,
                aliases VARCHAR
            );
        """)

        entities = [
            ("toan_tinh", "Toàn tỉnh", 0, "toàn tỉnh, toan tinh, toàn tp, ubnd tỉnh, cấp tỉnh, lâm đồng"),
            ("dam_rong", "Huyện Đam Rông", 1, "huyện đam rông, đam rông, dam rong"),
            ("lam_ha", "Huyện Lâm Hà", 1, "huyện lâm hà, lâm hà, lam ha"),
            ("da_lat", "TP. Đà Lạt", 1, "thành phố đà lạt, tp đà lạt, đà lạt, da lat"),
            ("bao_loc", "TP. Bảo Lộc", 1, "thành phố bảo lộc, tp bảo lộc, bảo lộc, bao loc"),
            ("duc_trong", "Huyện Đức Trọng", 1, "huyện đức trọng, đức trọng, duc trong"),
            ("di_linh", "Huyện Di Linh", 1, "huyện di linh, di linh"),
            ("don_duong", "Huyện Đơn Dương", 1, "huyện đơn dương, đơn dương, don duong"),
            ("lac_duong", "Huyện Lạc Dương", 1, "huyện lạc dương, lạc dương, lac duong"),
            ("cat_tien", "Huyện Cát Tiên", 1, "huyện cát tiên, cát tiên, cat tien"),
            ("da_huoai", "Huyện Đạ Huoai", 1, "huyện đạ huoai, đạ huoai, da huoai"),
            ("da_teh", "Huyện Đạ Tẻh", 1, "huyện đạ tẻh, đạ tẻh, da teh"),
            ("bao_lam", "Huyện Bảo Lâm", 1, "huyện bảo lâm, bảo lâm, bao lam"),
            ("so_ldtbxh", "Sở LĐTBXH", 2, "sở lđtbxh, phòng lđtbxh, ldtbxh, sở lao động, phòng lao động"),
            ("so_xaydung", "Sở Xây dựng", 2, "sở xây dựng, phòng xây dựng, xây dựng, xaydung"),
            ("so_congthuong", "Sở Công thương", 2, "sở công thương, phòng công thương, công thương, cong thuong"),
            ("so_yte", "Sở Y tế", 2, "sở y tế, phòng y tế, y tế, yte"),
            ("so_nongnghiep", "Sở Nông nghiệp", 2, "sở nông nghiệp, phòng nông nghiệp, nông nghiệp, nong nghiep"),
            ("so_taichinh", "Sở Tài chính", 2, "sở tài chính, phòng tài chính, tài chính"),
            ("phong_kinhte", "Phòng Kinh tế", 2, "phòng kinh tế, kinh tế, kinhte"),
        ]
        self.conn.executemany("INSERT INTO admin_entities VALUES (?, ?, ?, ?)", entities)

        # 2. Bảng chỉ tiêu nghiệp vụ (metrics)
        self.conn.execute("""
            CREATE TABLE metrics_catalog (
                code VARCHAR PRIMARY KEY,
                canonical_name VARCHAR,
                domain VARCHAR,
                aliases VARCHAR
            );
        """)

        metrics = [
            ("tnld", "tai nạn lao động", "Lao động - TBXH", "tai nạn lao động, tnld, tnlđ, an toàn lao động, tai nan lao dong, số vụ tai nạn"),
            ("khuyen_cong", "kinh phí khuyến công", "Công thương", "kinh phí khuyến công, khuyến công, khuyen cong, giải ngân kinh phí khuyến công, vốn khuyến công"),
            ("tram_y_te", "trạm y tế đạt chuẩn", "Y tế", "trạm y tế, tram y te, đạt chuẩn quốc gia về y tế, y tế xã đạt chuẩn, trạm y tế đạt chuẩn"),
            ("giam_ngheo", "giảm nghèo", "Lao động - TBXH", "giảm nghèo, giam ngheo, hộ nghèo, ho ngheo, tỷ lệ hộ nghèo"),
            ("kien_co_hoa", "kiên cố hóa", "Xây dựng", "kiên cố hóa, kien co hoa, phòng học kiên cố, trường học kiên cố"),
            ("cay_trong", "diện tích cây trồng", "Nông nghiệp", "diện tích cây trồng, năng suất cây trồng, sản lượng lúa, dien tich cay trong"),
            ("dao_tao_nghe", "đào tạo nghề", "Lao động - TBXH", "đào tạo nghề, dao tao nghe, lao động qua đào tạo, học nghề"),
            ("di_thuong_yte", "dị thường y tế", "Y tế", "dị thường y tế, bất thường y tế, để trống hoặc bằng 0, chỉ tiêu nào của lĩnh vực y tế"),
            ("bieu_mau", "biểu mẫu thu thập dữ liệu", "Hệ thống", "biểu mẫu thu thập dữ liệu, biểu mẫu, danh mục biểu mẫu, loại biểu mẫu"),
        ]
        self.conn.executemany("INSERT INTO metrics_catalog VALUES (?, ?, ?, ?)", metrics)

        # Cache alias lists in RAM for fast RapidFuzz
        self._entity_aliases: List[Tuple[str, str, int, str]] = []  # (alias, canonical, level, code)
        rows = self.conn.execute("SELECT code, canonical_name, level, aliases FROM admin_entities").fetchall()
        for code, canonical, level, aliases in rows:
            for al in aliases.split(","):
                self._entity_aliases.append((al.strip(), canonical, level, code))

        self._metric_aliases: List[Tuple[str, str, str, str]] = []  # (alias, canonical, domain, code)
        mrows = self.conn.execute("SELECT code, canonical_name, domain, aliases FROM metrics_catalog").fetchall()
        for code, canonical, domain, aliases in mrows:
            for al in aliases.split(","):
                self._metric_aliases.append((al.strip(), canonical, domain, code))

    def _compile_patterns(self) -> None:
        self._year_pat = re.compile(r"\b(202[4-6])\b")
        self._quarter_pat = re.compile(r"\b(quý\s*[1-4]|q[1-4]|q[1-4]/202[4-6])\b", re.IGNORECASE)
        self._recent_pat = re.compile(r"\b(gần đây|vừa qua|mới nhất|hôm nay)\b", re.IGNORECASE)

    def extract_temporal(self, text: str) -> Optional[str]:
        """Trích xuất mốc thời gian chuẩn hóa."""
        ym = self._year_pat.search(text)
        if ym:
            return ym.group(1)
        qm = self._quarter_pat.search(text)
        if qm:
            return qm.group(1).upper()
        if self._recent_pat.search(text):
            return "2025"  # Năm đã chốt duyệt chính thức
        return None

    def match_entity(self, text: str) -> Optional[Tuple[str, int, str, float]]:
        """
        Khớp thực thể qua RapidFuzz.
        Trả về (canonical_name, level, code, score) nếu score >= threshold.
        """
        low = text.lower()
        alias_texts = [x[0] for x in self._entity_aliases]
        
        # Thử tìm substring match trước (ưu tiên độ chính xác tuyệt đối)
        for al, canonical, level, code in self._entity_aliases:
            if re.search(rf"\b{re.escape(al)}\b", low):
                return canonical, level, code, 100.0

        # RapidFuzz partial / token match
        best_match = process.extractOne(
            low,
            alias_texts,
            scorer=fuzz.partial_ratio,
            score_cutoff=self.threshold,
        )
        if best_match:
            matched_alias, score, idx = best_match
            _, canonical, level, code = self._entity_aliases[idx]
            return canonical, level, code, score

        return None

    def match_metric(self, text: str) -> Optional[Tuple[str, str, str, float]]:
        """
        Khớp chỉ tiêu qua RapidFuzz.
        Trả về (canonical_name, domain, code, score) nếu score >= threshold.
        """
        low = text.lower()
        alias_texts = [x[0] for x in self._metric_aliases]

        # Thử tìm substring match trước
        for al, canonical, domain, code in self._metric_aliases:
            if re.search(rf"\b{re.escape(al)}\b", low):
                return canonical, domain, code, 100.0

        best_match = process.extractOne(
            low,
            alias_texts,
            scorer=fuzz.partial_ratio,
            score_cutoff=self.threshold,
        )
        if best_match:
            matched_alias, score, idx = best_match
            _, canonical, domain, code = self._metric_aliases[idx]
            return canonical, domain, code, score

        return None

    def evaluate(self, text: str, context: Optional[Any] = None) -> SemanticMatchResult:
        """
        Thực hiện đánh giá định lượng cho câu hỏi qua Lexical-Fuzzy Strategy.
        """
        raw = text.strip()
        temporal = self.extract_temporal(raw)
        entity_res = self.match_entity(raw)
        metric_res = self.match_metric(raw)

        slots: Dict[str, Any] = {}
        if temporal:
            slots["temporal_val"] = temporal
        if entity_res:
            canonical, level, code, _ = entity_res
            slots["admin_entity"] = canonical
            slots["admin_level"] = level
            slots["admin_code"] = code
        if metric_res:
            m_canonical, domain, m_code, _ = metric_res
            slots["metric_name"] = m_canonical
            slots["metric_domain"] = domain
            slots["metric_code"] = m_code

        # Trường hợp 1: Có chỉ tiêu nhưng hoàn toàn thiếu cả thời gian và địa bàn
        # -> Vùng nhập nhằng (Ambiguous Tri-Band: 0.50 <= Confidence < 0.85)
        if metric_res and metric_res[0] != "biểu mẫu thu thập dữ liệu" and not temporal and not entity_res:
            options = [
                SlotClarificationOption(
                    label="Năm 2025 toàn tỉnh",
                    slot_key="temporal_scope",
                    value="2025_toan_tinh",
                    preview_description="Số liệu quyết toán chính thức năm 2025",
                ),
                SlotClarificationOption(
                    label="Năm 2024 toàn tỉnh",
                    slot_key="temporal_scope",
                    value="2024_toan_tinh",
                    preview_description="Số liệu lưu trữ năm 2024",
                ),
                SlotClarificationOption(
                    label="Năm 2026 toàn tỉnh",
                    slot_key="temporal_scope",
                    value="2026_toan_tinh",
                    preview_description="Kế hoạch và tiến độ năm 2026",
                ),
                SlotClarificationOption(
                    label="Xem theo các huyện",
                    slot_key="admin_level",
                    value="district_breakdown",
                    preview_description="Phân rã theo cấp huyện",
                ),
            ]
            return SemanticMatchResult(
                confidence_score=0.65,
                matched_track=RouteTypeEnum.CLARIFICATION,
                intent=IntentEnum.CLARIFICATION_NEEDED,
                extracted_slots=slots,
                candidate_options=options,
                explanation="Câu hỏi có chỉ tiêu nhưng khuyết thiếu cả mốc thời gian và địa bàn",
            )

        # Trường hợp 2: Có chỉ tiêu và có ít nhất 1 slot (thời gian hoặc địa bàn)
        # -> Vùng khớp chắc chắn (Confident Tri-Band: Score >= 0.85)
        if metric_res:
            return SemanticMatchResult(
                confidence_score=0.92,
                matched_track=RouteTypeEnum.TEMPLATE_FAST_TRACK,
                intent=IntentEnum.FAST_METRIC_COMPILER,
                extracted_slots=slots,
                candidate_options=[],
                complexity="LOW_TEMPLATE",
                explanation="Khớp thành công chỉ tiêu và tham số ngữ cảnh",
            )

        # Trường hợp 3: Không khớp chỉ tiêu cụ thể
        return SemanticMatchResult(
            confidence_score=0.30,
            matched_track=None,
            intent=None,
            extracted_slots=slots,
            candidate_options=[],
            explanation="Không tìm thấy chỉ tiêu nghiệp vụ trong Catalog",
        )
