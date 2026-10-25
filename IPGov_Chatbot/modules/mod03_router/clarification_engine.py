"""
IPGov Chatbot - Module 03: Clarification & Slot-Filling Engine
Phát hiện câu hỏi mơ hồ, khuyết thiếu tham số và sinh Interactive Action Chips.
Căn cứ:
- Blueprints 02_ROUTER_SPEC, 03_SEMANTIC_LAYER, 05_MULTI_AGENT
- Khung REAR (ACL 2024): Margin Gap Distribution (\u0394_margin < \u03c3_threshold)
- Khử sạch 100% Regex và heuristic đếm từ (REJ-07, REJ-08)
"""

from __future__ import annotations
import logging
from typing import Any, List, Optional, Tuple

from IPGov_Chatbot.schemas.router_dto import (
    ActiveQuestFrameDTO,
    SlotClarificationOption,
    SlotTypeEnum,
)

logger = logging.getLogger("ipgov.mod03.clarification_engine")


class ClarificationEngine:
    """
    Động cơ nhận diện câu hỏi mơ hồ và khuyết thiếu tham số theo khung REAR (ACL 2024):
    1. METRIC_DISAMBIGUATION: \u0394_margin(Top 1, Top 2) < \u03c3_threshold tr\u00ean DuckDB Catalog RAM
    2. TEMPORAL_AMBIGUITY: Câu hỏi tính toán chỉ tiêu thiếu hoàn toàn mốc thời gian
    Khử sạch 100% regex và các heuristic đếm số lượng từ ngữ.
    """

    def __init__(self, catalog: Optional[Any] = None) -> None:
        if catalog is None:
            try:
                from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog
                self.catalog = DuckDBSemanticCatalog()
            except Exception:
                self.catalog = None
        else:
            self.catalog = catalog

        # Ngưỡng biên phân phối REAR (\u03c3_threshold = 15.0 trên thang 100)
        self.margin_threshold = 15.0

    def check_clarification_needed(
        self,
        prompt: str,
        active_quest: Optional[ActiveQuestFrameDTO] = None
    ) -> Tuple[bool, List[str], List[SlotClarificationOption], List[str]]:
        """
        Kiểm tra xem câu hỏi có cần hỏi làm rõ (Clarification) hay không.
        Trả về: (needs_clarification, missing_slots, clarification_options, action_chips_labels)
        """
        text = prompt.strip()
        if not text:
            return False, [], [], []

        # Chuẩn hóa văn bản thuần túy không dùng regex
        q_norm = "".join(c if c not in "?!:;\"'[](){}" else " " for c in text.lower()).strip()
        q_norm = " ".join(q_norm.split())

        # Bỏ qua Clarification cho các truy vấn giới thiệu năng lực
        if self.catalog and hasattr(self.catalog, "has_lexicon_term") and self.catalog.has_lexicon_term(text, "CAPABILITY_META"):
            return False, [], [], []
        if self.catalog and hasattr(self.catalog, "resolve_report_audit_intent"):
            try:
                if self.catalog.resolve_report_audit_intent(text):
                    return False, [], [], []
            except Exception:
                pass
        if self.catalog and hasattr(self.catalog, "resolve_attribute_lookup"):
            try:
                if self.catalog.resolve_attribute_lookup(text):
                    return False, [], [], []
            except Exception:
                pass
        if self.catalog and hasattr(self.catalog, "extract_scope_from_query"):
            try:
                if self.catalog.extract_scope_from_query(text).get("status") != "NONE":
                    return False, [], [], []
            except Exception:
                pass
        if self.catalog and hasattr(self.catalog, "has_lexicon_term"):
            has_mission_kw = self.catalog.has_lexicon_term(text, "MISSION_KEYWORD")
            if has_mission_kw:
                has_mission_info = (
                    hasattr(self.catalog, "extract_mission_from_query")
                    and self.catalog.extract_mission_from_query(text).get("status") in ("MATCH", "FOUND")
                )
                has_crit_signal = (
                    self.catalog.has_lexicon_term(text, "METRIC_LIST_TARGET")
                    or self.catalog.has_lexicon_term(text, "METRIC_LIST_TRIGGER")
                    or self.catalog.has_lexicon_term(text, "LEVEL1_CRITERIA_SIGNAL")
                )
                if has_mission_info or has_crit_signal:
                    return False, [], [], []
        if self.catalog and hasattr(self.catalog, "is_dimension_query"):
            try:
                if (
                    self.catalog.is_dimension_query(text, "criteria")
                    or self.catalog.is_dimension_query(text, "fact_report_criteria")
                    or self.catalog.is_dimension_query(text, "mission")
                    or self.catalog.is_dimension_query(text, "office")
                    or self.catalog.is_dimension_query(text, "department")
                    or (hasattr(self.catalog, "is_inventory_query") and self.catalog.is_inventory_query(text))
                ):
                    return False, [], [], []
            except Exception:
                pass

        # 1. KIỂM TRA ĐA NGHĨA CHỈ TIÊU (REAR MARGIN GAP - ACL 2024 & ACRONYM TOPIC DISCOVERY)
        # Tra cứu động qua classify_criterion_hierarchy và catalog_acronyms trong RAM
        has_specific_leaf = False
        has_exact_hierarchy_crit = False
        if self.catalog and hasattr(self.catalog, "classify_criterion_hierarchy"):
            try:
                h_check = self.catalog.classify_criterion_hierarchy(text)
                h_cls = h_check.get("classification")
                h_mname = h_check.get("matched_name") or ""
                if h_check.get("matched_code") or h_check.get("parent_code"):
                    if h_cls in ("single_leaf", "duplicate_leaf"):
                        has_specific_leaf = True
                        has_exact_hierarchy_crit = True
                    elif h_cls in ("parent", "parent_group") and (
                        len(h_mname) >= 6 or (self.catalog and hasattr(self.catalog, "has_lexicon_term") and self.catalog.has_lexicon_term(text, "METRIC_LIST_TARGET"))
                    ):
                        has_specific_leaf = True
                        has_exact_hierarchy_crit = True
            except Exception:
                pass
        if self.catalog and hasattr(self.catalog, "conn"):
            try:
                # Kiểm tra xem câu hỏi có chứa chỉ tiêu cụ thể (lá hoặc nhóm cha >= 10 ký tự) trong catalog_criteria_hierarchy
                hier_rows = self.catalog.conn.execute(
                    "SELECT DISTINCT LOWER(TRIM(name)), NOT is_leaf FROM catalog_criteria_hierarchy;"
                ).fetchall()
                for h_name, h_is_parent in hier_rows:
                    if not h_name:
                        continue
                    if (not h_is_parent and len(h_name) >= 6 and h_name in q_norm) or (
                        h_is_parent and len(h_name) >= 12 and h_name in q_norm
                    ):
                        has_specific_leaf = True
                        has_exact_hierarchy_crit = True
                        break
            except Exception:
                pass

            try:
                # Kiểm tra xem câu hỏi có chứa chỉ tiêu cụ thể hay không (loại trừ false clarification)
                all_crits = self.catalog.conn.execute("SELECT code, name, is_leaf FROM catalog_criteria;").fetchall()
                q_tokens = set("".join(c if c.isalnum() else " " for c in q_norm).split())
                stop_tokens = {
                    "số", "lượng", "tổng", "của", "và", "trong", "năm", "một", "các", "đã", "được", 
                    "toàn", "tỉnh", "cho", "tôi", "biết", "hiện", "nay", "hệ", "thống", "đang", 
                    "có", "những", "nào", "là", "bao", "nhiêu", "mới", "nhất", "tại", "trên", 
                    "địa", "bàn", "thực", "hiện", "kỳ", "báo", "cáo", "đạt", "công", "nhận"
                }
                for c_code, c_name, is_leaf in all_crits:
                    c_low = " ".join(c_name.lower().strip().split())
                    if c_low in q_norm and len(c_low) >= 10:
                        c_toks = set(c_low.split()) - stop_tokens - {"chỉ", "tiêu"}
                        if len(c_toks) >= 1:
                            has_specific_leaf = True
                            break
                    c_toks = set("".join(c if c.isalnum() else " " for c in c_low).split())
                    content_toks = c_toks - stop_tokens
                    if len(content_toks) >= 2 and content_toks.issubset(q_tokens):
                        has_specific_leaf = True
                        break
                    if is_leaf and c_low in q_norm and len(c_low) >= 6:
                        has_specific_leaf = True
                        break

                if not has_specific_leaf:
                    acronym_rows = self.catalog.conn.execute(
                        "SELECT acronym, full_form, category FROM catalog_acronyms WHERE category = 'criteria';"
                    ).fetchall()
                    for acr, full, cat in acronym_rows:
                        acr_low = acr.lower()
                        full_low = full.lower()
                        if acr_low in q_norm.split() or f" {acr_low} " in f" {q_norm} " or q_norm == acr_low or full_low in q_norm:
                            crit_rows = self.catalog.conn.execute("""
                                SELECT code, name FROM catalog_criteria
                                WHERE is_leaf = TRUE AND (
                                    LOWER(name) LIKE '%' || ? || '%' 
                                    OR LOWER(name) LIKE '%' || ? || '%'
                                    OR LOWER(aliases) LIKE '%' || ? || '%'
                                )
                                ORDER BY length(name) ASC
                                LIMIT 5;
                            """, (acr_low, full_low, acr_low)).fetchall()
                            if len(crit_rows) > 1:
                                options = [
                                    SlotClarificationOption(
                                        label=r[1],
                                        slot_key="metric",
                                        value=r[0] or r[1]
                                    )
                                    for r in crit_rows[:3]
                                ]
                                labels = [opt.label for opt in options]
                                return True, ["metric_code"], options, labels
            except Exception as e:
                logger.debug("Lỗi tra cứu acronym trong ClarificationEngine: %s", e)

        # Tra cứu trực tiếp qua DuckDB Semantic Catalog không cắt chuỗi cơ học (REJ-07, REJ-08)
        if not has_exact_hierarchy_crit and self.catalog and hasattr(self.catalog, "find_top_k_candidates"):
            try:
                cands, is_ambig, score_delta = self.catalog.find_top_k_candidates(q_norm, top_k=3)
                if cands and len(cands) >= 2:
                    top1_score = float(cands[0].get("score", 0.0))
                    top2_score = float(cands[1].get("score", 0.0))
                    margin = abs(top1_score - top2_score)

                    # Kích hoạt Clarification khi margin gap nhỏ hơn ngưỡng động phân phối
                    # HOẶC cờ is_ambig từ catalog được kích hoạt, trừ khi Top 1 khớp tuyệt đối
                    top1_name_low = cands[0]["name"].strip().lower()
                    top2_name_low = cands[1]["name"].strip().lower() if len(cands) >= 2 else ""

                    # Chuẩn hóa tiền tố để lấy danh xưng thực thể cốt lõi
                    def _stem_core(n: str) -> str:
                        if hasattr(self, "catalog") and hasattr(self.catalog, "strip_query_noise"):
                            return self.catalog.strip_query_noise(n, "METRIC_AGG_PREFIX_NOISE")
                        return n.strip()

                    core1 = _stem_core(top1_name_low)
                    core2 = _stem_core(top2_name_low)
                    top2_distinct_words = [w for w in top2_name_low.split() if w not in top1_name_low and len(w) > 2]
                    has_sub_words = any(w in q_norm for w in top2_distinct_words)

                    # 1. Khớp nguyên vẹn tên chỉ tiêu hoặc tên cốt lõi un-prefixed (khi không chứa từ phân loại con)
                    has_exact_leaf = (
                        has_specific_leaf
                        or has_exact_hierarchy_crit
                        or (top1_name_low == q_norm)
                        or (top1_name_low in q_norm and len(top1_name_low) >= 6)
                        or (core1 in q_norm and len(core1) >= 6 and not has_sub_words)
                    )

                    # 2. Khử false clarification khi Top 1 là chỉ tiêu tổng hợp và query hỏi đại lượng tổng quát (không chỉ rõ phân loại con)
                    import unicodedata
                    q_nfc = unicodedata.normalize('NFC', q_norm)
                    t1_core_words = [unicodedata.normalize('NFC', w) for w in core1.split() if w not in ("đạt", "chuẩn", "cấp", "số", "lượng", "toàn", "tỉnh", "của", "và")]

                    is_top1_aggregate = (
                        top1_name_low.startswith("tổng ")
                        and not top2_name_low.startswith("tổng ")
                        and not has_sub_words
                        and (core1 in q_norm or (t1_core_words and all(w in q_nfc for w in t1_core_words)))
                    )

                    # 3. Khử false clarification khi Top 1 khớp danh xưng đại lượng cụ thể trong query trong khi Top 2 thì không (động học không hardcode)
                    t1_head = core1.split()[0] if core1.split() else ""
                    is_measure_mismatch = bool(
                        t1_head
                        and len(t1_head) >= 3
                        and t1_head in q_norm
                        and not core2.startswith(t1_head)
                    )

                    # 4. Khử false clarification khi Top 1 và Top 2 là biến thể đồng nghĩa
                    is_synonym_pair = bool(top2_name_low and core1 == core2)

                    # 5. Khử false clarification khi toàn bộ từ cốt lõi của Top 1 xuất hiện trong query và không chứa từ phân biệt của Top 2
                    is_content_covered = bool(
                        t1_core_words
                        and all(w in q_nfc for w in t1_core_words)
                        and not any(w in q_nfc for w in top2_distinct_words)
                    )

                    is_period_report_inquiry = False
                    if self.catalog and hasattr(self.catalog, "is_dimension_query"):
                        is_period_report_inquiry = self.catalog.is_dimension_query(q_norm, "fact_report_criteria")

                    is_exact_top1 = (
                        has_exact_leaf
                        or is_top1_aggregate
                        or is_measure_mismatch
                        or is_synonym_pair
                        or is_period_report_inquiry
                        or is_content_covered
                    )

                    if not is_exact_top1 and (margin < self.margin_threshold or is_ambig):
                        options = [
                            SlotClarificationOption(
                                label=c["name"],
                                slot_key="metric",
                                value=c.get("code") or c["name"]
                            )
                            for c in cands[:3]
                        ]
                        labels = [opt.label for opt in options]
                        return True, ["metric_code"], options, labels
            except Exception as e:
                logger.debug("Lỗi tra cứu candidate trong ClarificationEngine: %s", e)

        # 2. KIỂM TRA THIẾU MỐC THỜI GIAN (TEMPORAL SLOT MISSING)
        # Nhận diện mốc thời gian không dùng regex: kiểm tra năm số 4 chữ số hoặc từ active_quest
        tokens = "".join(c if c not in "/-." else " " for c in q_norm).split()
        has_temporal_year = any(len(tok) == 4 and tok.isdigit() and (tok.startswith("19") or tok.startswith("20")) for tok in tokens)
        has_temporal_anchor = has_temporal_year or bool(active_quest and (active_quest.temporal_val or active_quest.comparison_year))

        has_user = bool(self.catalog.resolve_user_name(q_norm)) if (self.catalog and hasattr(self.catalog, "resolve_user_name")) else False
        has_pos = bool(self.catalog.resolve_user_position(q_norm)) if (self.catalog and hasattr(self.catalog, "resolve_user_position")) else False
        is_officer_inquiry = has_user or has_pos
        is_metadata_or_discovery = bool(self.catalog.is_dimension_query(q_norm, "criteria")) if (self.catalog and hasattr(self.catalog, "is_dimension_query")) else False

        if not has_temporal_anchor and not is_officer_inquiry and not is_metadata_or_discovery:
            is_direct_quantity_query = any(k in q_norm for k in ["bao nhiêu", "đạt bao nhiêu", "mấy", "chiếm bao nhiêu"])
            is_comparison_or_trend = any(k in q_norm for k in ["so sánh", "biến động", "tăng trưởng", "thay đổi", "qua các năm"])
            is_open_ended_request = any(k in q_norm for k in ["cho tôi xem", "tình hình", "giải ngân"]) and not has_exact_hierarchy_crit

            # Chỉ kích hoạt Clarification khi câu hỏi so sánh/biến động thiếu năm
            # hoặc yêu cầu mở thiếu tham số (như 'cho tôi xem số liệu giải ngân').
            # Các câu hỏi trực tiếp về đại lượng chỉ tiêu (CRITERIA_LATEST) mặc định lấy số liệu mới nhất.
            if is_comparison_or_trend or (is_open_ended_request and not is_direct_quantity_query):
                options = [
                    SlotClarificationOption(label="Năm 2026 (Kế hoạch)", slot_key="year", value="2026"),
                    SlotClarificationOption(label="Năm 2025 (Chính thức)", slot_key="year", value="2025"),
                    SlotClarificationOption(label="Năm 2024", slot_key="year", value="2024"),
                ]
                labels = [opt.label for opt in options]
                return True, ["temporal_year"], options, labels

        return False, [], [], []
