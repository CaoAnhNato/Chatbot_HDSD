"""
Module: IPGov_Chatbot/modules/mod03_router/canonical_normalizer.py
Chức năng: Tầng Khung Ngữ Nghĩa Chuẩn Tắc (Canonical Semantic Normalizer).
Khắc phục triệt để tính giòn ngôn ngữ (Linguistic Brittleness) và loại bỏ hoàn toàn Regex chắp vá.
Căn cứ:
- Blueprint: remediation_and_normalization_plan.md
- Mô hình Hai Tầng: Two-Stage Canonical Semantic Normalization Framework
- Stream A (Intent & Metric) || Stream B (Temporal & Spatial Delta)
- Two-Stage Hybrid Selection + LLM Ambiguity Gate
- Schema-Driven Dynamic Spatial Resolution (catalog_tenants trong DuckDB RAM)
- AST Assembly Tất Định (Deterministic SQL Synthesis)
"""

from __future__ import annotations

import asyncio
import calendar
import json
import logging
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from IPGov_Chatbot.config import settings
from IPGov_Chatbot.modules.mod03_router.clarification_engine import ClarificationEngine
from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog
from IPGov_Chatbot.schemas.canonical_query_frame import (
    CanonicalIntentEnum,
    CanonicalQueryFrameDTO,
    SemanticQueryIntentDTO,
    TemporalSlotSpec,
)

logger = logging.getLogger("ipgov.mod03.canonical_normalizer")


def _strip_bracketed_tags(raw_content: str) -> str:
    """
    Loại bỏ các thẻ dạng [tenant_code=..., level=...] thuần túy bằng thao tác chuỗi.
    Không sử dụng regex.
    """
    while "[" in raw_content and "]" in raw_content:
        start = raw_content.find("[")
        end = raw_content.find("]", start)
        if end != -1:
            tag_content = raw_content[start + 1:end]
            if "tenant_code=" in tag_content or "level=" in tag_content:
                raw_content = raw_content[:start] + raw_content[end + 1:]
            else:
                break
        else:
            break
    return raw_content.strip()


def _remove_accents(raw_str: str) -> str:
    """Loại bỏ dấu tiếng Việt để xử lý nhiễu chính tả không dấu (Dr.Spider NL-level)."""
    if not raw_str:
        return ""
    nfkd = unicodedata.normalize("NFKD", raw_str)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).replace("đ", "d").replace("Đ", "D")


def _parse_to_date(val: Any):
    """Chuyển đổi chuỗi ISO YYYY-MM-DD, DD/MM/YYYY hoặc datetime/date về datetime.date."""
    from datetime import date, datetime
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    s = str(val).strip()[:10]
    if "/" in s:
        parts = s.split("/")
        if len(parts) == 3:
            if len(parts[2]) == 4:
                return date(int(parts[2]), int(parts[1]), int(parts[0]))
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
    parts = s.split("-")
    if len(parts) == 3 and len(parts[0]) == 4:
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    if len(parts) == 3 and len(parts[2]) == 4:
        return date(int(parts[2]), int(parts[1]), int(parts[0]))
    raise ValueError(f"Không thể phân tích ngày từ giá trị: {val!r}")


def resolve_nearest_report_date(available_dates: List[Any], target_date: Any) -> Any:
    """
    Thuật toán xác định mốc báo cáo gần nhất theo khoảng [A, B] (SC-2.2):
    - Bước 1: Sắp xếp các mốc thu thập số liệu tăng dần D = [d_1, d_2, ..., d_k].
      + Nếu a <= d_1 -> mặc định lấy cận dưới d_1.
      + Nếu a >= d_k -> mặc định lấy cận trên d_k.
      + Ngược lại, xác định khoảng [A, B] = [d_i, d_{i+1}] sao cho A <= a <= B.
    - Bước 2: Tính khoảng cách từ a đến 2 cận A và B:
      + delta_A = (a - A).days, delta_B = (B - a).days.
      + Chọn cận có khoảng cách nhỏ hơn (delta_A < delta_B -> chọn A).
      + Trường hợp 2 đoạn bằng nhau (delta_A == delta_B) hoặc delta_A > delta_B -> mặc định chọn cận trên B.
    """
    if not available_dates:
        return None
    a = _parse_to_date(target_date)
    paired = sorted(
        [(_parse_to_date(d), d) for d in available_dates if d is not None],
        key=lambda x: x[0],
    )
    if not paired:
        return None
    # Loại bỏ trùng lặp ngày nhưng giữ nguyên kiểu dữ liệu gốc của phần tử đầu tiên
    unique_paired: List[Tuple[Any, Any]] = []
    for dt_obj, orig_val in paired:
        if not unique_paired or unique_paired[-1][0] != dt_obj:
            unique_paired.append((dt_obj, orig_val))

    if a <= unique_paired[0][0]:
        return unique_paired[0][1]
    if a >= unique_paired[-1][0]:
        return unique_paired[-1][1]

    for idx in range(len(unique_paired) - 1):
        bound_a, orig_a = unique_paired[idx]
        bound_b, orig_b = unique_paired[idx + 1]
        if bound_a <= a <= bound_b:
            delta_a = (a - bound_a).days
            delta_b = (bound_b - a).days
            if delta_a < delta_b:
                return orig_a
            return orig_b

    return unique_paired[-1][1]


def resolve_nearest_report_date_with_bounds(
    available_dates: List[Any],
    target_date: Any,
) -> Dict[str, Any]:
    """
    Mở rộng PA 1.1 (Dual-Bound Snapshot + Temporal Shift Notice cho SC-2.2):
    Xác định mốc báo cáo gần nhất theo thuật toán khoảng [A, B] đồng thời trả về
    thông tin cận dưới A, cận trên B và độ lệch ngày để minh bạch hóa trên giao diện.
    """
    if not available_dates:
        return {
            "selected_date": None,
            "is_exact_match": False,
            "delta_days": None,
            "bound_a_date": None,
            "delta_a_days": None,
            "bound_b_date": None,
            "delta_b_days": None,
        }
    a = _parse_to_date(target_date)
    paired = sorted(
        [(_parse_to_date(d), d) for d in available_dates if d is not None],
        key=lambda x: x[0],
    )
    if not paired:
        return {
            "selected_date": None,
            "is_exact_match": False,
            "delta_days": None,
            "bound_a_date": None,
            "delta_a_days": None,
            "bound_b_date": None,
            "delta_b_days": None,
        }

    unique_paired: List[Tuple[Any, Any]] = []
    for dt_obj, orig_val in paired:
        if not unique_paired or unique_paired[-1][0] != dt_obj:
            unique_paired.append((dt_obj, orig_val))

    for dt_obj, orig_val in unique_paired:
        if dt_obj == a:
            return {
                "selected_date": orig_val,
                "is_exact_match": True,
                "delta_days": 0,
                "bound_a_date": orig_val,
                "delta_a_days": 0,
                "bound_b_date": orig_val,
                "delta_b_days": 0,
            }

    if a < unique_paired[0][0]:
        b_dt, b_orig = unique_paired[0]
        d_b = (b_dt - a).days
        return {
            "selected_date": b_orig,
            "is_exact_match": False,
            "delta_days": d_b,
            "bound_a_date": None,
            "delta_a_days": None,
            "bound_b_date": b_orig,
            "delta_b_days": d_b,
        }

    if a > unique_paired[-1][0]:
        a_dt, a_orig = unique_paired[-1]
        d_a = (a - a_dt).days
        return {
            "selected_date": a_orig,
            "is_exact_match": False,
            "delta_days": d_a,
            "bound_a_date": a_orig,
            "delta_a_days": d_a,
            "bound_b_date": None,
            "delta_b_days": None,
        }

    for idx in range(len(unique_paired) - 1):
        bound_a, orig_a = unique_paired[idx]
        bound_b, orig_b = unique_paired[idx + 1]
        if bound_a <= a <= bound_b:
            delta_a = (a - bound_a).days
            delta_b = (bound_b - a).days
            if delta_a < delta_b:
                selected = orig_a
                delta = delta_a
            else:
                selected = orig_b
                delta = delta_b
            return {
                "selected_date": selected,
                "is_exact_match": delta == 0,
                "delta_days": delta,
                "bound_a_date": orig_a,
                "delta_a_days": delta_a,
                "bound_b_date": orig_b,
                "delta_b_days": delta_b,
            }

    return {
        "selected_date": unique_paired[-1][1],
        "is_exact_match": False,
        "delta_days": abs((a - unique_paired[-1][0]).days),
        "bound_a_date": unique_paired[-1][1],
        "delta_a_days": abs((a - unique_paired[-1][0]).days),
        "bound_b_date": None,
        "delta_b_days": None,
    }


class CanonicalSemanticNormalizer:
    """
    Bộ chuẩn hóa ngữ nghĩa chuẩn tắc hai tầng:
    Tầng 1: Ánh xạ câu hỏi tự do thành CanonicalQueryFrameDTO thông qua Pydantic v2 + Catalog RAM.
    Tầng 2: Biên dịch ra câu lệnh SQL PostgreSQL 16 tất định, duy nhất cho mọi biến thể tương đương.
    """

    def __init__(
        self,
        catalog: Optional[DuckDBSemanticCatalog] = None,
        clarification_engine: Optional[ClarificationEngine] = None,
    ) -> None:
        self.catalog = catalog or DuckDBSemanticCatalog()
        self.clarification_engine = clarification_engine or ClarificationEngine(catalog=self.catalog)

    def _parse_query_nlu_llm(
        self, query: str, candidate_metrics: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[SemanticQueryIntentDTO]:
        """
        NLU Model-Driven Semantic Parser: Phân tích ngữ nghĩa câu hỏi bằng mô hình ngôn ngữ (LLM Lite).
        Đảm bảo LLM quyết định Intent (OUT_OF_SCOPE, ENTITY_ATTRIBUTE_LOOKUP, RELATIONAL_EXPLORATION,
        METRIC_NUMERIC_CALCULATION, METADATA_EXPLORATION, METRIC_POINT_INQUIRY).
        Tích hợp Pre-Retrieval Grounding từ DuckDB In-Memory Catalog.
        """
        api_key = getattr(settings, "AGENT_DECISION_LLM_API_KEY", None) or getattr(settings, "OPENROUTER_API_KEY", None) or getattr(settings, "GOOGLE_API_KEY", None)
        if not api_key:
            return None

        # Fallback tự động tra cứu candidate_metrics nếu chưa được truyền
        if candidate_metrics is None and hasattr(self, "catalog") and hasattr(self.catalog, "retrieve_candidate_metrics"):
            try:
                candidate_metrics = self.catalog.retrieve_candidate_metrics(query, top_k=3, score_threshold=0.40)
            except Exception:
                candidate_metrics = None

        schema_context = ""
        if candidate_metrics:
            schema_lines = [
                f"- Chỉ tiêu khả dụng: \"{m['name']}\" (Độ khớp: {m['score']})"
                for m in candidate_metrics
                if m.get("name")
            ]
            if schema_lines:
                schema_context = (
                    "[NGỮ CẢNH DANH MỤC CHỈ TIÊU DWH KHẢ DỤNG]:\n"
                    + "\n".join(schema_lines) + "\n\n"
                    "LƯU Ý NGHIỆP VỤ ĐẶC THÙ:\n"
                    "- Nếu câu hỏi nhắc đến hoặc chứa các cụm từ tương đồng với các chỉ tiêu khả dụng trên "
                    "(kể cả các chỉ tiêu mang hình thái cụm vị ngữ/trạng thái như 'Chưa đủ điều kiện đánh giá', 'Đạt chuẩn', 'hoạt động hiệu quả tốt'), "
                    "BẮT BUỘC nhận diện đây là câu hỏi tra cứu chỉ tiêu (intent = 'METRIC_POINT_INQUIRY' hoặc 'ENTITY_ATTRIBUTE_LOOKUP'), "
                    "TUYỆT ĐỐI KHÔNG phân loại vào OUT_OF_SCOPE.\n\n"
                )

        prompt = (
            f"Phân tích câu hỏi: \"{query}\"\n\n"
            f"{schema_context}"
            "Hãy suy luận theo từng bước (Chain-of-Thought) trong trường 'reasoning' trước khi đưa ra kết luận:\n"
            "Bước 1: Phân tích bản chất câu hỏi (giao tiếp xã giao, ngoài phạm vi DWH hay tra cứu DWH).\n"
            "Bước 2: Nhận diện ý định định lượng:\n"
            "   - Nếu câu hỏi hỏi số lượng / đếm bao nhiêu chỉ tiêu được thu thập/báo cáo -> intent: 'DIMENSION_LISTING', aggregation_function: 'COUNT'\n"
            "   - Nếu câu hỏi khám phá/liệt kê danh mục theo chuỗi thời gian hoặc kỳ báo cáo -> intent: 'DIMENSION_LISTING', aggregation_function: 'NONE'\n"
            "   - Nếu câu hỏi tra cứu giá trị định lượng của 1 chỉ tiêu lá cụ thể -> intent: 'METRIC_POINT_INQUIRY'\n"
            "   - Nếu câu hỏi hỏi về thuộc tính (đơn vị thực hiện / tỉnh chủ trì) của một chỉ tiêu -> intent: 'ENTITY_ATTRIBUTE_LOOKUP'\n"
            "   - Nếu câu hỏi khám phá quan hệ liên bảng (văn phòng, nhiệm vụ, cán bộ, xã phường) -> intent: 'RELATIONAL_EXPLORATION'\n"
            "Bước 3: Trích xuất mốc thời gian (năm, quý, bán niên, tháng, dải ngày) và thực thể liên quan.\n\n"
            "MỐC THỜI GIAN HỆ THỐNG CỐ ĐỊNH (TEMPORAL GROUNDING): anchor_date: '2026-10-11'. Năm mặc định: '2026'.\n\n"
            "CÁC KHUÔN MẪU TIÊU BIỂU TRỪU TƯỢNG (CANONICAL ABSTRACT PROTOTYPES - <30% TƯƠNG ĐỒNG KÝ TỰ):\n"
            "1. Prototype Temporal Discovery (DIMENSION_LISTING):\n"
            "   'Tổng hợp danh mục các đại lượng đo lường vật lý ghi nhận trong chu kỳ từ giai đoạn Alpha đến Beta'\n"
            "   -> reasoning: 'Khám phá danh mục các chỉ tiêu trong dải thời gian quy định...', intent: 'DIMENSION_LISTING', aggregation_function: 'NONE', subject_entity: null, is_inventory_query: false, target_table: 'fact_report_criteria'\n"
            "2. Prototype Count Aggregation (DIMENSION_LISTING with COUNT):\n"
            "   'Có bao nhiêu thông số vi khí hậu được thu thập trong khoảng thời gian quy định?'\n"
            "   -> reasoning: 'Đo lường số lượng chỉ tiêu phát sinh theo khoảng thời gian...', intent: 'DIMENSION_LISTING', aggregation_function: 'COUNT', subject_entity: null, target_table: 'fact_report_criteria'\n"
            "3. Prototype Entity Attribute Lookup (ENTITY_ATTRIBUTE_LOOKUP):\n"
            "   'Chỉ số độ ẩm cảm biến do đơn vị nào phụ trách vận hành?'\n"
            "   -> reasoning: 'Hỏi về đơn vị chủ trì/thực hiện của một chỉ số cụ thể...', intent: 'ENTITY_ATTRIBUTE_LOOKUP', subject_entity: 'độ ẩm cảm biến', target_attribute: 'đơn vị thực hiện'\n"
            "4. Prototype Relational Exploration (RELATIONAL_EXPLORATION):\n"
            "   'Tổ công tác chuyên trách quản lý các chương trình hành động liên phòng nào?'\n"
            "   -> reasoning: 'Liên kết giữa bộ phận cơ cấu và danh mục chương trình/nhiệm vụ...', intent: 'RELATIONAL_EXPLORATION', subject_entity: 'Tổ công tác chuyên trách'\n"
            "5. Prototype Single Leaf Metric Lookup (METRIC_POINT_INQUIRY):\n"
            "   'Mức tiêu hao năng lượng trung bình của hệ thống trong kỳ vừa qua'\n"
            "   -> reasoning: 'Tra cứu giá trị số liệu của một chỉ tiêu cụ thể...', intent: 'METRIC_POINT_INQUIRY', subject_entity: 'mức tiêu hao năng lượng trung bình'\n"
            "6. Prototype Out of Scope (OUT_OF_SCOPE):\n"
            "   'Giải phương trình vi phân và tính thể tích hình lập phương cạnh 12'\n"
            "   -> reasoning: 'Câu hỏi toán học ngoài phạm vi DWH...', intent: 'OUT_OF_SCOPE', is_out_of_scope: true, direct_answer: null\n"
            "7. Prototype Greeting & Farewell (GREETING_FAREWELL):\n"
            "   'Xin chào trợ lý, cảm ơn bạn rất nhiều nhé'\n"
            "   -> reasoning: 'Lời chào hỏi và cảm ơn xã giao...', intent: 'GREETING_FAREWELL', is_out_of_scope: false, is_conversational_only: true, direct_answer: 'Cảm ơn đồng chí. Rất hân hạnh được hỗ trợ đồng chí tra cứu số liệu DWH tỉnh Lâm Đồng. Chúc đồng chí một ngày làm việc hiệu quả!'\n"
            "8. Prototype Capability Inquiry (CAPABILITY_INTRO):\n"
            "   'Bạn có thể giúp gì cho tôi, hệ thống hỗ trợ những chức năng nào?'\n"
            "   -> reasoning: 'Hỏi về chức năng và khả năng hỗ trợ của trợ lý DWH...', intent: 'CAPABILITY_INTRO', is_out_of_scope: false, is_conversational_only: false, direct_answer: null\n\n"
            "QUY TẮC BẮT BUỘC:\n"
            "- TUYỆT ĐỐI KHÔNG thực hiện tính toán số học, giải toán hoặc trả lời câu hỏi ngoài phạm vi DWH. Luôn gán direct_answer: null cho mọi trường hợp OUT_OF_SCOPE.\n"
            "- Khi câu hỏi mang tính chất khám phá, liệt kê danh sách/danh mục chỉ tiêu theo chuỗi thời gian hoặc kỳ báo cáo (vd: tháng, quý, dải ngày), TUYỆT ĐỐI KHÔNG gán intent là ENTITY_ATTRIBUTE_LOOKUP và KHÔNG gán subject_entity là cụm từ rác ('các chỉ tiêu', 'thu thập'). Bắt buộc điền intent = 'DIMENSION_LISTING'.\n"
            "- Chỉ điền intent = 'ENTITY_ATTRIBUTE_LOOKUP' khi câu hỏi hỏi về thuộc tính của một chỉ tiêu/thực thể cụ thể.\n"
            "- Khi câu hỏi hỏi trợ lý có thể giúp gì, làm được gì, hỗ trợ chức năng nào, BẮT BUỘC điền intent = 'CAPABILITY_INTRO', is_conversational_only = false, direct_answer = null.\n"
            "- Khi câu hỏi là lời chào hỏi, tạm biệt hoặc cảm ơn lịch sự, BẮT BUỘC điền intent = 'GREETING_FAREWELL', is_out_of_scope = false, is_conversational_only = true.\n\n"
            "Trả về JSON duy nhất theo cấu trúc:\n"
            "{\n"
            "  \"reasoning\": string,\n"
            "  \"is_out_of_scope\": boolean,\n"
            "  \"is_conversational_only\": boolean,\n"
            "  \"direct_answer\": string or null,\n"
            "  \"intent\": string,\n"
            "  \"aggregation_function\": \"COUNT\" or \"NONE\",\n"
            "  \"subject_entity\": string or null,\n"
            "  \"target_attribute\": string or null,\n"
            "  \"is_inventory_query\": boolean,\n"
            "  \"target_table\": string or null,\n"
            "  \"time_filter\": \"2026\",\n"
            "  \"spatial_filter\": \"68\",\n"
            "  \"temporal_slot\": null,\n"
            "  \"is_mixed_multi_metric\": boolean,\n"
            "  \"sub_queries\": []\n"
            "}"
        )
        sys_prompt = (
            "Bạn là bộ phân tích ngôn ngữ tự nhiên NLU cho hệ thống IPGov DWH tỉnh Lâm Đồng. "
            "Chỉ trả về JSON thuần túy, không markdown, không giải thích ngoài JSON."
        )

        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=api_key,
                base_url=getattr(settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                timeout=15.0
            )
            # Danh mục 4 mô hình độc quyền được phép sử dụng
            candidate_models = [
                getattr(settings, "OPENROUTER_ROUTER_MODEL", "google/gemini-2.5-flash-lite"),
                "google/gemini-3.1-flash-lite",
                "google/gemini-3.5-flash-lite",
                "deepseek/deepseek-v4.1-flash",
            ]
            for model_name in candidate_models:
                try:
                    kwargs = {
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.0,
                    }
                    if "deepseek" in model_name:
                        kwargs["extra_body"] = {
                            "provider": {
                                "order": getattr(settings, "OPENROUTER_PLANNER_PROVIDER_ORDER", ["coreweave/fp8", "makora/fp8", "relace", "inference-net/fp8"]),
                                "allow_fallbacks": getattr(settings, "OPENROUTER_PLANNER_ALLOW_FALLBACKS", True),
                            },
                            "reasoning": {
                                "enabled": getattr(settings, "OPENROUTER_PLANNER_REASONING_ENABLED", False),
                            },
                        }
                    else:
                        kwargs["response_format"] = {"type": "json_object"}
                    resp = client.chat.completions.create(**kwargs)
                    raw_text = resp.choices[0].message.content.strip()
                    s_idx = raw_text.find("{")
                    e_idx = raw_text.rfind("}")
                    if s_idx != -1 and e_idx != -1 and e_idx > s_idx:
                        data = json.loads(raw_text[s_idx : e_idx + 1])
                        return SemanticQueryIntentDTO(**data)
                except Exception as model_err:
                    logger.debug("NLU model %s thất bại (%s), chuyển sang model kế tiếp...", model_name, model_err)
                    continue
        except Exception as e:
            logger.debug("LLM NLU Parse không khả dụng hoặc lỗi: %s", e)
        return None

    def _extract_core_metric_phrase(self, query: str) -> str:
        """
        Trích xuất cụm từ chỉ tiêu / chủ đề cốt lõi bằng cách loại bỏ
        thực thể địa danh và ký tự đặc biệt động qua DuckDB Catalog RAM.
        """
        import unicodedata
        q_norm = unicodedata.normalize("NFC", query.lower().strip())

        # 1. Loại bỏ năm số
        tokens = q_norm.split()
        clean_tokens = [w for w in tokens if not (len(w) == 4 and w.startswith("202") and w[3].isdigit())]
        q_norm = " " + " ".join(clean_tokens) + " "

        # 2. Loại bỏ địa bàn / tenant động qua DuckDB Catalog RAM
        prov_names = []
        if hasattr(self.catalog, "conn"):
            try:
                p_rows = self.catalog.conn.execute("SELECT DISTINCT name FROM catalog_provinces;").fetchall()
                prov_names = [r[0].lower().strip() for r in p_rows if r[0]]
                t_rows = self.catalog.conn.execute("SELECT DISTINCT name, aliases FROM catalog_tenants;").fetchall()
                for t_name, t_aliases in t_rows:
                    if t_name:
                        prov_names.append(t_name.lower().strip())
                    if t_aliases:
                        for al in t_aliases.split(","):
                            if al.strip():
                                prov_names.append(al.lower().strip())
            except Exception:
                pass
        prov_names.sort(key=len, reverse=True)
        for pn in prov_names:
            target_str = f" {pn} "
            if target_str in q_norm:
                q_norm = q_norm.replace(target_str, " ")

        # Loại bỏ phạm vi hành chính đã phân giải động qua Catalog
        if hasattr(self.catalog, "resolve_administrative_scope"):
            adm_scope = self.catalog.resolve_administrative_scope(query)
            if adm_scope and (adm_scope.get("admin_level") == 0 or adm_scope.get("type") in ("tenant", "province")):
                adm_name = (adm_scope.get("name") or "").lower().strip()
                if adm_name and f" {adm_name} " in q_norm:
                    q_norm = q_norm.replace(f" {adm_name} ", " ")

        # 3. Loại bỏ các ký tự đặc biệt
        for ch in ":.,?!;/-":
            q_norm = q_norm.replace(ch, " ")
        cleaned = " ".join(q_norm.split()).strip()

        # 4. Loại bỏ tiền tố / hậu tố câu hỏi dẫn nhập phổ biến qua DuckDB Catalog để giữ lại tên chỉ tiêu sạch
        if hasattr(self.catalog, "strip_query_noise"):
            cleaned = self.catalog.strip_query_noise(cleaned, "QUERY_LEAD_NOISE")
            cleaned = self.catalog.strip_query_noise(cleaned, "QUERY_TAIL_NOISE")

        return cleaned

    def _is_officer_query(self, raw_input: str) -> bool:
        """
        Xác định xem câu hỏi có thuộc miền tra cứu cán bộ / phân công nhiệm vụ (OFFICER_ASSIGNMENT)
        hoàn toàn động qua DuckDB Catalog RAM.
        """
        norm_val = raw_input.lower()
        has_negative_officer = (
            hasattr(self.catalog, "has_lexicon_term")
            and self.catalog.has_lexicon_term(norm_val, "OFFICER_QUERY_NEGATIVE")
        )
        has_positive_officer = (
            hasattr(self.catalog, "has_lexicon_term")
            and self.catalog.has_lexicon_term(norm_val, "OFFICER_QUERY_POSITIVE")
        )

        has_metric_concept = (
            hasattr(self.catalog, "has_lexicon_term")
            and self.catalog.has_lexicon_term(raw_input, "METRIC_LIST_TARGET")
        ) or any(w in norm_val for w in ("chỉ tiêu", "tiêu chí", "số liệu"))

        if ("chỉ tiêu" in norm_val or "tiêu chí" in norm_val) and has_negative_officer:
            return False
        if has_metric_concept and not has_positive_officer:
            return False

        if hasattr(self.catalog, "resolve_user_name") and self.catalog.resolve_user_name(raw_input):
            return True
        if hasattr(self.catalog, "resolve_user_position") and self.catalog.resolve_user_position(raw_input):
            return True
        if hasattr(self.catalog, "conn") and self.catalog.conn:
            try:
                row = self.catalog.conn.execute("SELECT 1 FROM catalog_users WHERE INSTR(?, LOWER(name)) > 0 LIMIT 1;", (norm_val,)).fetchone()
                if row:
                    return True
            except Exception:
                pass
        return False

    def _get_effective_end_month(self, year_val: int) -> int:
        """
        Xác định tháng kết thúc hiệu lực cho các mốc 'đến nay' / 'hiện tại'.
        Ưu tiên tra cứu mốc báo cáo gần nhất trong DuckDB RAM / Catalog,
        mặc định là tháng kết thúc kỳ báo cáo quý 3 (tháng 9) được tính toán động qua monthrange.
        """
        if hasattr(self.catalog, "conn"):
            try:
                row = self.catalog.conn.execute("SELECT MAX(last_synced_at) FROM catalog_sync_meta;").fetchone()
                if row and row[0]:
                    dt = row[0]
                    if hasattr(dt, "month"):
                        return dt.month
                    elif isinstance(dt, str) and len(dt) >= 7:
                        return int(dt[5:7])
            except Exception:
                pass
        return 9

    # --------------------------------------------------------------------------
    # STREAM A: TRÍCH XUẤT Ý ĐỊNH VÀ CHỈ TIÊU THÔ (INTENT & METRIC EXTRACTOR)
    # --------------------------------------------------------------------------
    def _extract_stream_a_deterministic(
        self,
        raw_input: str,
        stream_b: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Stream A Deterministic Fallback: Phân tích intent, target table,
        và metric mention theo kiến trúc Hai Mặt Phẳng (Two-Plane Architecture):
        1. Dimension Plane (Metadata Exploration / Dimension Listing): province, criteria, deparment, office, collection_form, mission.
        2. Fact Plane (Quantitative Metrics / Aggregations): fact_report_criteria, report, user_mission.
        """
        norm_input = raw_input.lower().strip()

        # -1. Tra cứu Chào hỏi & Tạm biệt (GREETING_FAREWELL) ủy thác qua Catalog RAM
        has_greet_signal = False
        if hasattr(self, "catalog") and hasattr(self.catalog, "has_lexicon_term"):
            has_greet_signal = self.catalog.has_lexicon_term(norm_input, "GREETING_LEAD_NOISE")
        else:
            has_greet_signal = norm_input.startswith(("xin chào", "chào", "hello", "hi", "tạm biệt", "cảm ơn"))

        is_pure_greeting = False
        if has_greet_signal:
            if hasattr(self, "catalog") and hasattr(self.catalog, "strip_query_noise"):
                rem = self.catalog.strip_query_noise(norm_input, "GREETING_LEAD_NOISE")
                if not rem or not rem.strip(" ,:.-!?"):
                    is_pure_greeting = True
            elif norm_input in ("xin chào", "chào", "hello", "hi", "tạm biệt", "cảm ơn"):
                is_pure_greeting = True

        if is_pure_greeting:
            is_farewell = False
            if hasattr(self, "catalog") and hasattr(self.catalog, "has_lexicon_term"):
                is_farewell = self.catalog.has_lexicon_term(norm_input, "FAREWELL_SIGNAL")
            else:
                is_farewell = any(w in norm_input for w in ("tạm biệt", "cảm ơn", "thank", "hẹn gặp lại"))
            prov_name = getattr(settings, "PROVINCE_NAME", "cấp tỉnh")
            direct_ans = (
                f"Cảm ơn đồng chí. Rất hân hạnh được hỗ trợ đồng chí tra cứu số liệu DWH {prov_name}. Chúc đồng chí một ngày làm việc hiệu quả!"
                if is_farewell else
                f"Xin chào đồng chí! Tôi là Trợ lý Ảo Kho Dữ Liệu DWH {prov_name}. Tôi có thể hỗ trợ đồng chí tra cứu: "
                "1. Chỉ tiêu kinh tế - xã hội; "
                "2. Tình hình phê duyệt báo cáo; "
                "3. Danh mục nhiệm vụ trọng tâm; "
                "4. Phân công cán bộ phụ trách nhiệm vụ. Đồng chí cần tra cứu thông tin gì?"
            )
            return {
                "intent": CanonicalIntentEnum.GREETING_FAREWELL,
                "target_table": "none",
                "direct_answer": direct_ans,
                "is_out_of_scope": False,
                "exclude_entities": [],
                "search_keyword": None,
                "raw_metric_mentions": [],
                "aggregation_function": "NONE",
                "sort_direction": "NONE",
                "limit": 0,
            }
        elif has_greet_signal and hasattr(self, "catalog") and hasattr(self.catalog, "strip_query_noise"):
            raw_input = self.catalog.strip_query_noise(raw_input, "GREETING_LEAD_NOISE").lstrip(" ,:-.!?")
            norm_input = raw_input.lower().strip()


        if hasattr(self.catalog, "has_lexicon_term") and self.catalog.has_lexicon_term(norm_input, "CAPABILITY_META"):
            return {
                "intent": CanonicalIntentEnum.CAPABILITY_INTRO,
                "target_table": "none",
                "direct_answer": None,
                "is_out_of_scope": False,
                "exclude_entities": [],
                "search_keyword": None,
                "raw_metric_mentions": [],
                "aggregation_function": "NONE",
                "sort_direction": "NONE",
                "limit": 0,
            }
        audit_info = (
            self.catalog.resolve_report_audit_intent(raw_input)
            if hasattr(self.catalog, "resolve_report_audit_intent")
            else None
        )
        if audit_info:
            resolved_mis = (stream_b.get("target_mission") if stream_b else None) or (
                self.catalog.resolve_mission(raw_input) if hasattr(self.catalog, "resolve_mission") else None
            )
            return {
                "intent": CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT,
                "target_table": audit_info.get("target_table", "report"),
                "audit_sub_intent": audit_info.get("audit_sub_intent"),
                "status_filter": audit_info.get("status_filter"),
                "include_draft_comparison": bool(audit_info.get("include_draft_comparison", False)),
                "target_office": None,
                "target_mission": resolved_mis,
                "target_scope": stream_b.get("target_scope") if stream_b else None,
                "exclude_entities": [],
                "search_keyword": None,
                "raw_metric_mentions": [],
                "aggregation_function": "NONE",
                "sort_direction": "DESC_NULLS_LAST",
                "limit": None,
            }

        # 0. Tra cứu cán bộ / phân công nhiệm vụ (OFFICER_ASSIGNMENT)
        if self._is_officer_query(raw_input):
            target_mission = None
            target_office = None
            exclude_offices = []
            target_pos = None
            target_name = None

            # Phân giải nhiệm vụ động qua DuckDB Catalog
            if hasattr(self.catalog, "resolve_mission"):
                target_mission = self.catalog.resolve_mission(raw_input)

            # Phân giải đơn vị / phòng ban qua DuckDB Catalog động
            admin_scope = self.catalog.resolve_administrative_scope(raw_input) if hasattr(self.catalog, "resolve_administrative_scope") else {}
            if admin_scope and admin_scope.get("type") == "office":
                target_office = admin_scope.get("office_name") or admin_scope.get("name")

            # Phân giải loại trừ đơn vị (Directional Negative Filter - TC-REM-09) qua DuckDB Catalog RAM
            if hasattr(self.catalog, "resolve_excluded_entities"):
                exclude_offices = self.catalog.resolve_excluded_entities(raw_input)

            # Phân giải chức vụ động qua DuckDB Catalog
            if hasattr(self.catalog, "resolve_user_position"):
                target_pos = self.catalog.resolve_user_position(raw_input)

            # Phân giải tên cán bộ động qua DuckDB Catalog
            if hasattr(self.catalog, "resolve_user_name"):
                target_name = self.catalog.resolve_user_name(raw_input)

            return {
                "intent": CanonicalIntentEnum.OFFICER_ASSIGNMENT,
                "target_table": "user_mission",
                "target_mission": target_mission,
                "target_office": target_office,
                "exclude_entities": exclude_offices,
                "target_position": target_pos,
                "target_user_name": target_name,
                "raw_metric_mentions": [],
                "search_keyword": None,
                "aggregation_function": "NONE",
                "sort_direction": "NONE",
                "limit": None,
            }

        # 1. Tra cứu thuộc tính thực thể: đơn vị hoặc tỉnh thực hiện của chỉ tiêu (ENTITY_ATTRIBUTE_LOOKUP) qua DuckDB Catalog RAM
        attr_lookup = (
            self.catalog.resolve_attribute_lookup(raw_input)
            if hasattr(self.catalog, "resolve_attribute_lookup")
            else None
        )
        if attr_lookup:
            target_attr = attr_lookup.get("target_attribute", "đơn vị thực hiện")
            subject = self._extract_core_metric_phrase(raw_input) or raw_input.strip()
            return {
                "intent": CanonicalIntentEnum.ENTITY_ATTRIBUTE_LOOKUP,
                "target_table": "fact_report_criteria",
                "subject_entity": subject,
                "target_attribute": target_attr,
                "exclude_entities": [],
                "search_keyword": None,
                "raw_metric_mentions": [subject],
                "aggregation_function": "NONE",
                "sort_direction": "NONE",
                "limit": None,
            }

        norm_tokens = set(norm_input.replace("?", " ").replace(",", " ").replace(".", " ").replace(";", " ").replace(":", " ").replace("!", " ").split())

        has_lex_target = hasattr(self.catalog, "has_lexicon_term") and self.catalog.has_lexicon_term(raw_input, "METRIC_LIST_TARGET")
        has_lex_trigger = hasattr(self.catalog, "has_lexicon_term") and self.catalog.has_lexicon_term(raw_input, "METRIC_LIST_TRIGGER")
        has_lex_l1 = hasattr(self.catalog, "has_lexicon_term") and self.catalog.has_lexicon_term(raw_input, "LEVEL1_CRITERIA_SIGNAL")

        is_metric_listing = bool(has_lex_target and has_lex_trigger)

        # 1.9 REQ-Q04 / SC-4.1 / SC-4.2: Hiển thị các chỉ tiêu cấp 1 của nhiệm vụ / các nhiệm vụ
        mis_info = self.catalog.extract_mission_from_query(raw_input) if hasattr(self.catalog, "extract_mission_from_query") else {"status": "NONE"}
        has_mission = bool(mis_info and mis_info.get("status") in ("MATCH", "FOUND", "NOT_FOUND")) or (
            hasattr(self.catalog, "has_lexicon_term") and self.catalog.has_lexicon_term(raw_input, "MISSION_KEYWORD")
        )

        has_explicit_level1 = bool(has_lex_l1)

        is_report_status = hasattr(self.catalog, "has_lexicon_term") and self.catalog.has_lexicon_term(norm_input, "REPORT_STATUS_SIGNAL")
        has_prov_scope = hasattr(self.catalog, "has_lexicon_term") and self.catalog.has_lexicon_term(norm_input, "PROVINCE_SCOPE_SIGNAL")
        is_level1_criteria_query = (
            (has_mission and (has_explicit_level1 or is_metric_listing) and not is_report_status)
            or (has_explicit_level1 and has_prov_scope)
        )
        if is_level1_criteria_query:
            if mis_info and mis_info.get("status") == "NOT_FOUND":
                resolved_mis = f"__NOT_FOUND__:{mis_info.get('requested_mission', '')}"
            else:
                resolved_mis = (
                    (mis_info.get("mission_name") if mis_info and mis_info.get("status") in ("FOUND", "MATCH") else None)
                    or (stream_b.get("target_mission") if stream_b else None)
                    or (self.catalog.resolve_mission(raw_input) if hasattr(self.catalog, "resolve_mission") else None)
                )
            return {
                "intent": CanonicalIntentEnum.DIMENSION_LISTING,
                "target_table": "fact_report_criteria",
                "exclude_entities": [],
                "search_keyword": None,
                "raw_metric_mentions": [],
                "target_mission": resolved_mis,
                "is_level1_hierarchy_view": True,
                "aggregation_function": "NONE",
                "sort_direction": "ASC",
                "limit": None,
                "is_inventory_query": True,
            }

        # 2. Khám phá quan hệ liên bảng / nhiệm vụ trọng tâm (Dimension: mission) qua DuckDB Catalog RAM
        scope_info = self.catalog.extract_scope_from_query(raw_input) if hasattr(self.catalog, "extract_scope_from_query") else None
        has_mission_kw = hasattr(self.catalog, "has_lexicon_term") and self.catalog.has_lexicon_term(norm_input, "MISSION_KEYWORD")
        has_mission_scope = hasattr(self.catalog, "has_lexicon_term") and self.catalog.has_lexicon_term(norm_input, "MISSION_SCOPE_CUE")
        has_off_or_ward = hasattr(self.catalog, "has_lexicon_term") and self.catalog.has_lexicon_term(norm_input, "OFFICE_OR_WARD_CUE")
        is_mission_scope_query = (
            has_mission_kw
            and (
                has_mission_scope
                or (scope_info and scope_info.get("status") in ("FOUND", "MATCH", "NOT_FOUND"))
            )
            and not self._is_officer_query(raw_input)
            and not is_metric_listing
            and not has_off_or_ward
        )
        if is_mission_scope_query:
            target_scope_name = (scope_info.get("scope_name") or scope_info.get("requested_scope")) if scope_info else None
            if target_scope_name:
                return {
                    "intent": CanonicalIntentEnum.METADATA_EXPLORATION,
                    "target_table": "mission",
                    "target_scope": target_scope_name,
                    "exclude_entities": [],
                    "search_keyword": None,
                    "raw_metric_mentions": [],
                    "aggregation_function": "NONE",
                    "sort_direction": "ASC",
                    "limit": None,
                }

        if hasattr(self.catalog, "is_dimension_query") and self.catalog.is_dimension_query(raw_input, "mission") and not self._is_officer_query(raw_input) and not is_metric_listing:
            admin_scope = self.catalog.resolve_administrative_scope(raw_input) if hasattr(self.catalog, "resolve_administrative_scope") else {}
            target_off = None
            if admin_scope and admin_scope.get("type") == "office":
                target_off = admin_scope.get("office_name") or admin_scope.get("name")
            elif hasattr(self.catalog, "conn") and self.catalog.conn:
                off_match = self.catalog.conn.execute("SELECT name FROM catalog_offices WHERE INSTR(?, LOWER(name)) > 0 LIMIT 1;", (norm_input,)).fetchone()
                if off_match:
                    target_off = off_match[0]

            has_office_or_scope = (target_off is not None) or (
                hasattr(self.catalog, "has_lexicon_term") and self.catalog.has_lexicon_term(norm_input, "OFFICE_SCOPE_CUE")
            )
            if has_office_or_scope:
                return {
                    "intent": CanonicalIntentEnum.RELATIONAL_EXPLORATION,
                    "target_table": "office_mission",
                    "target_office": target_off,
                    "subject_entity": target_off,
                    "exclude_entities": [],
                    "search_keyword": None,
                    "raw_metric_mentions": [],
                    "aggregation_function": "NONE",
                    "sort_direction": "ASC",
                    "limit": None,
                }
            return {
                "intent": CanonicalIntentEnum.METADATA_EXPLORATION,
                "target_table": "mission",
                "exclude_entities": [],
                "search_keyword": None,
                "raw_metric_mentions": [],
                "aggregation_function": "NONE",
                "sort_direction": "ASC",
                "limit": None,
            }

        # 3. Dynamic Collective Noun & Inventory Resolution qua DuckDB Catalog RAM
        has_collective_noun = bool(
            getattr(self.catalog, "is_dimension_query", lambda q, d: False)(norm_input, "criteria")
        )

        extracted_office = None
        extracted_dept = None
        if stream_b and stream_b.get("target_office"):
            extracted_office = stream_b.get("target_office")
        if stream_b and stream_b.get("department_code"):
            extracted_dept = stream_b.get("department_code")

        scope_res = self.catalog.resolve_administrative_scope(raw_input) if hasattr(self.catalog, "resolve_administrative_scope") else {}
        if not extracted_office and not extracted_dept and scope_res:
            if scope_res.get("type") == "office":
                extracted_office = scope_res.get("office_name") or scope_res.get("name")
                extracted_dept = scope_res.get("department_code")
            elif scope_res.get("type") == "department":
                extracted_dept = scope_res.get("department_code")

        is_provincial = bool(
            scope_res and (
                scope_res.get("admin_level") == 0
                or scope_res.get("type") in ("tenant", "province")
            )
        )

        core_phrase = self._extract_core_metric_phrase(raw_input)
        has_specific_catalog_metric = False
        matched_catalog_mention = None
        if hasattr(self.catalog, "classify_criterion_hierarchy"):
            try:
                h_det = self.catalog.classify_criterion_hierarchy(raw_input)
                allowed_classes = ("single_leaf", "duplicate_leaf", "parent", "parent_group")
                if h_det and h_det.get("classification") in allowed_classes and h_det.get("matched_name"):
                    has_specific_catalog_metric = True
                    matched_catalog_mention = h_det["matched_name"]
            except Exception:
                pass

        if not is_metric_listing and not matched_catalog_mention:
            if hasattr(self.catalog, "_criteria_cache_names"):
                for crit_name in sorted(self.catalog._criteria_cache_names, key=len, reverse=True):
                    cn_low = crit_name.lower().strip()
                    if cn_low and len(cn_low) > 3 and cn_low in norm_input:
                        has_specific_catalog_metric = True
                        matched_catalog_mention = crit_name
                        break
            if not matched_catalog_mention and hasattr(self.catalog, "_alias_registry"):
                for entry in sorted(self.catalog._alias_registry, key=lambda x: len(x.get("alias", "")), reverse=True):
                    if entry.get("type") == "criteria" or entry.get("target_table") == "dwh_internal.criteria":
                        al_low = (entry.get("alias") or "").lower().strip()
                        if al_low and len(al_low) > 6 and al_low in norm_input:
                            has_specific_catalog_metric = True
                            matched_catalog_mention = entry.get("name") or al_low
                            break

        is_inventory = bool(getattr(self.catalog, "is_inventory_query", lambda q: False)(raw_input))

        if (
            not has_specific_catalog_metric
            and not is_metric_listing
            and not is_inventory
            and core_phrase
            and len(core_phrase) > 3
        ):
            if hasattr(self.catalog, "resolve_metric_id"):
                c_id = self.catalog.resolve_metric_id(core_phrase)
                if c_id:
                    has_specific_catalog_metric = True

        has_temporal_discovery = bool(
            stream_b and (
                stream_b.get("month_filter") is not None
                or stream_b.get("date_from") is not None
                or stream_b.get("start_date") is not None
            )
        )

        is_dimension_discovery = (
            (has_temporal_discovery and not has_specific_catalog_metric)
            or ((has_collective_noun or is_metric_listing) and not has_specific_catalog_metric and (is_provincial or extracted_office or bool(extracted_dept) or is_inventory))
        )

        if is_dimension_discovery:
            return {
                "intent": CanonicalIntentEnum.DIMENSION_LISTING,
                "target_table": "fact_report_criteria",
                "exclude_entities": [],
                "search_keyword": None,
                "raw_metric_mentions": [],
                "target_office": extracted_office,
                "department_code": extracted_dept,
                "aggregation_function": "NONE",
                "sort_direction": "ASC",
                "limit": None,
                "is_inventory_query": is_provincial or is_inventory,
            }

        # Kiểm tra các từ khóa tính toán / tổng hợp của Fact Plane bằng tra cứu dynamic từ Catalog
        is_fact_calc = bool(matched_catalog_mention or has_specific_catalog_metric)
        if not is_fact_calc and hasattr(self.catalog, "_criteria_cache_names"):
            for crit_name in self.catalog._criteria_cache_names:
                cn_low = crit_name.lower().strip()
                if cn_low and len(cn_low) > 3 and cn_low in norm_input:
                    is_fact_calc = True
                    break

        has_business_topic = (
            is_fact_calc
            or is_metric_listing
            or has_mission
            or (hasattr(self.catalog, "resolve_report_audit_intent") and bool(self.catalog.resolve_report_audit_intent(raw_input)))
            or (hasattr(self.catalog, "has_lexicon_term") and self.catalog.has_lexicon_term(raw_input, "DOMAIN_SIGNAL"))
        )
        # 2a. Khám phá địa bàn cấp xã/phường (Dimension: ward) qua DuckDB Catalog RAM
        is_ward_dimension = (
            not has_business_topic
            and hasattr(self.catalog, "is_dimension_query")
            and self.catalog.is_dimension_query(raw_input, "ward")
        )
        if is_ward_dimension:
            agg_fn = "COUNT" if (hasattr(self.catalog, "has_lexicon_term") and self.catalog.has_lexicon_term(norm_input, "CRITERIA_COUNT")) else "NONE"
            limit_val = 1 if agg_fn == "COUNT" else next((int(t) for t in norm_input.split() if t.isdigit()), None)
            search_kw = "code" if (hasattr(self.catalog, "has_lexicon_term") and self.catalog.has_lexicon_term(norm_input, "CODE_SEARCH_KEYWORD")) else None
            return {
                "intent": CanonicalIntentEnum.RELATIONAL_EXPLORATION,
                "target_table": "ward",
                "exclude_entities": [],
                "search_keyword": search_kw,
                "raw_metric_mentions": [],
                "aggregation_function": agg_fn,
                "sort_direction": "ASC",
                "limit": limit_val,
            }

        # 2b. Khám phá địa bàn / Tỉnh thành (Dimension: province) qua DuckDB Catalog RAM
        is_prov_list = hasattr(self.catalog, "has_lexicon_term") and self.catalog.has_lexicon_term(norm_input, "PROVINCE_LIST_QUERY")
        has_local_cue = hasattr(self.catalog, "has_lexicon_term") and self.catalog.has_lexicon_term(norm_input, "LOCAL_OFFICE_OR_WARD_CUE")
        if not has_business_topic and (is_prov_list or (hasattr(self.catalog, "is_dimension_query") and self.catalog.is_dimension_query(raw_input, "province") and not has_local_cue)):
            exclude_entities = self.catalog.resolve_excluded_entities(raw_input) if hasattr(self.catalog, "resolve_excluded_entities") else []
            return {
                "intent": CanonicalIntentEnum.METADATA_EXPLORATION,
                "target_table": "province",
                "exclude_entities": exclude_entities,
                "search_keyword": None,
                "raw_metric_mentions": [],
                "aggregation_function": "NONE",
                "sort_direction": "ASC",
                "limit": None,
            }

        # 3. Khám phá danh mục chỉ tiêu (Dimension: criteria)
        if not has_specific_catalog_metric and (has_collective_noun or getattr(self.catalog, "is_dimension_query", lambda q, d: False)(norm_input, "criteria")) and not is_dimension_discovery:
            kw = None
            core_kw = self._extract_core_metric_phrase(raw_input)
            if core_kw and len(core_kw) > 2:
                kw = core_kw
            return {
                "intent": CanonicalIntentEnum.METADATA_EXPLORATION,
                "target_table": "criteria",
                "exclude_entities": [],
                "search_keyword": kw,
                "raw_metric_mentions": [],
                "aggregation_function": "NONE",
                "sort_direction": "ASC",
                "limit": None,
            }

        # 4. Tra cứu danh mục sở ban ngành / phòng ban (Dimension: deparment, office) qua DuckDB Catalog RAM
        if not has_specific_catalog_metric and not is_fact_calc and hasattr(self.catalog, "is_dimension_query") and self.catalog.is_dimension_query(raw_input, "office_or_department"):
            target_tbl = self.catalog.resolve_target_table(raw_input, default_table="office")
            return {
                "intent": CanonicalIntentEnum.DIMENSION_LISTING,
                "target_table": target_tbl,
                "exclude_entities": [],
                "search_keyword": None,
                "raw_metric_mentions": [],
                "aggregation_function": "NONE",
                "sort_direction": "ASC",
                "limit": None,
            }


        # 10. Mặc định Fact Plane: Tra cứu chỉ tiêu KTXH (METRIC_POINT_INQUIRY)
        core_phrase = self._extract_core_metric_phrase(raw_input)
        if matched_catalog_mention and (not core_phrase or len(core_phrase) > len(matched_catalog_mention) + 6):
            raw_mentions = [matched_catalog_mention]
        else:
            raw_mentions = [core_phrase] if core_phrase else [raw_input.strip()]
        return {
            "intent": CanonicalIntentEnum.METRIC_POINT_INQUIRY,
            "target_table": "fact_report_criteria",
            "exclude_entities": [],
            "search_keyword": None,
            "raw_metric_mentions": raw_mentions,
            "aggregation_function": "SUM",
            "sort_direction": "DESC_NULLS_LAST",
            "limit": None,
            "is_fact_calc": is_fact_calc,
        }

    # --------------------------------------------------------------------------
    # STREAM B: TRÍCH XUẤT THỜI GIAN VÀ ĐỊA BÀN (TEMPORAL & SPATIAL DETECTOR)
    # --------------------------------------------------------------------------
    def _extract_stream_b_deterministic(self, raw_input: str) -> Dict[str, Any]:
        """
        Stream B Deterministic Fallback: Phân tích mốc thời gian, kỳ báo cáo,
        và thực thể địa danh (khử bẫy đa nghĩa polysemy LĐ = Lao động vs Lâm Đồng).
        Không sử dụng thư viện regex.
        """
        norm_input = raw_input.lower().strip()

        # 1. Trích xuất năm (year_code)
        year_code = None
        for tok in raw_input.replace(",", " ").replace(".", " ").replace("?", " ").split():
            clean_tok = tok.strip()
            if len(clean_tok) == 4 and clean_tok.isdigit() and 1900 <= int(clean_tok) <= 2100:
                year_code = clean_tok
                break
        if not year_code and "năm nay" in norm_input:
            year_code = "2026"

        spatial_mention = None
        if hasattr(self, "catalog") and hasattr(self.catalog, "conn"):
            try:
                res_t = self.catalog.conn.execute(
                    "SELECT regexp_extract(?, '(?i)tenant_code\\s*[:=]\\s*([a-zA-Z0-9_]+)', 1)",
                    [raw_input],
                ).fetchone()
                if res_t and res_t[0]:
                    spatial_mention = res_t[0]
            except Exception:
                pass

        # 3. Trích xuất chuỗi thời gian (time series periods) sắp xếp tuần tự động
        periods = []
        y_int = int(year_code or "2026")
        for tok in raw_input.replace(",", " ").replace("?", " ").split():
            sep = "/" if "/" in tok else ("-" if "-" in tok else ("." if "." in tok else None))
            if sep:
                parts = tok.split(sep)
                if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit() and parts[2].isdigit():
                    d_val, m_val, y_val = int(parts[0]), int(parts[1]), int(parts[2])
                    if 1 <= d_val <= 31 and 1 <= m_val <= 12 and 2020 <= y_val <= 2030:
                        periods.append(f"{y_val}-{m_val:02d}-{d_val:02d}")

        for m_val in range(1, 13):
            if f"{m_val} tháng" in norm_input or f"{m_val:02d} tháng" in norm_input:
                last_d = calendar.monthrange(y_int, m_val)[1]
                p_date = f"{y_int}-{m_val:02d}-{last_d:02d}"
                if p_date not in periods:
                    periods.append(p_date)

        VN_Q_WORDS = {
            "1": 1, "01": 1, "i": 1, "mot": 1, "một": 1,
            "2": 2, "02": 2, "ii": 2, "hai": 2,
            "3": 3, "03": 3, "iii": 3, "ba": 3,
            "4": 4, "04": 4, "iv": 4, "bon": 4, "bốn": 4, "tu": 4, "tư": 4,
        }
        for q_word, q_num in VN_Q_WORDS.items():
            if f"quý {q_word}" in norm_input or f"q{q_word}" in norm_input:
                em = q_num * 3
                last_d = calendar.monthrange(y_int, em)[1]
                p_date = f"{y_int}-{em:02d}-{last_d:02d}"
                if p_date not in periods:
                    periods.append(p_date)
        periods.sort()

        # 4. Trích xuất Quý, Tháng, hoặc dải thời gian
        date_from = None
        date_to = None
        month_filter = None
        specific_date = None
        y = year_code or "2026"

        def _calc_quarter_bounds(year_val: int, q_idx: int) -> Tuple[str, str]:
            sm = (q_idx - 1) * 3 + 1
            em = q_idx * 3
            last_d = calendar.monthrange(year_val, em)[1]
            return f"{year_val}-{sm:02d}-01", f"{year_val}-{em:02d}-{last_d:02d}"

        VN_MONTH_WORDS = {
            "mười một": 11, "muoi mot": 11, "mười hai": 12, "muoi hai": 12, "mười": 10, "muoi": 10,
            "một": 1, "mot": 1, "giêng": 1, "gieng": 1, "hai": 2, "ba": 3,
            "tư": 4, "tu": 4, "bốn": 4, "bon": 4, "năm": 5, "nam": 5,
            "sáu": 6, "sau": 6, "bảy": 7, "bay": 7, "tám": 8, "tam": 8,
            "chín": 9, "chin": 9, "chạp": 12, "chap": 12,
        }

        q_unacc = _remove_accents(norm_input)
        clean_unacc = q_unacc.replace("?", " ").replace("!", " ").replace(";", " ").replace(":", " ").replace("(", " ").replace(")", " ").replace(",", " ")
        tokens = clean_unacc.split()

        # BƯỚC 4A: KIỂM TRA QUÝ (bao gồm N quý đầu/cuối năm, dải quý và quý đơn lẻ)
        found_q = False
        for i, tok in enumerate(tokens):
            if i + 1 < len(tokens) and tokens[i + 1] == "quy":
                if i + 2 < len(tokens) and tokens[i + 2] == "dau":
                    q_cnt = VN_Q_WORDS.get(tok)
                    if q_cnt:
                        date_from = f"{y}-01-01"
                        _, date_to = _calc_quarter_bounds(int(y), min(4, max(1, q_cnt)))
                        found_q = True
                        month_filter = None
                        break
                elif i + 2 < len(tokens) and tokens[i + 2] == "cuoi":
                    q_cnt = VN_Q_WORDS.get(tok)
                    if q_cnt:
                        start_q = max(1, 5 - q_cnt)
                        date_from, _ = _calc_quarter_bounds(int(y), start_q)
                        date_to = f"{y}-12-31"
                        found_q = True
                        month_filter = None
                        break

        if not found_q:
            matched_qs = []
            i = 0
            while i < len(tokens):
                tok = tokens[i]
                slash_parts = tok.split("/") if "/" in tok else (tok.split("-") if "-" in tok else None)
                if slash_parts and len(slash_parts) == 2 and slash_parts[1].isdigit() and len(slash_parts[1]) == 4:
                    sub_q = slash_parts[0]
                    if (sub_q.startswith("q") and len(sub_q) > 1 and sub_q[1:] in VN_Q_WORDS) or (sub_q.startswith("quy") and len(sub_q) > 3 and sub_q[3:] in VN_Q_WORDS):
                        q_key = sub_q[1:] if sub_q.startswith("q") and not sub_q.startswith("quy") else sub_q[3:]
                        matched_qs.append(VN_Q_WORDS[q_key])
                        year_code = slash_parts[1]
                        y = slash_parts[1]
                    elif sub_q in VN_Q_WORDS and i > 0 and tokens[i - 1] in ("quy", "q"):
                        matched_qs.append(VN_Q_WORDS[sub_q])
                        year_code = slash_parts[1]
                        y = slash_parts[1]
                elif (tok.startswith("q") and len(tok) > 1 and tok[1:] in VN_Q_WORDS) or (tok.startswith("quy") and len(tok) > 3 and tok[3:] in VN_Q_WORDS):
                    sub = tok[1:] if tok.startswith("q") and not tok.startswith("quy") else tok[3:]
                    matched_qs.append(VN_Q_WORDS[sub])
                elif tok in ("quy", "q") and i + 1 < len(tokens):
                    nxt = tokens[i + 1]
                    nxt_slash = nxt.split("/") if "/" in nxt else (nxt.split("-") if "-" in nxt else None)
                    if nxt_slash and len(nxt_slash) == 2 and nxt_slash[0] in VN_Q_WORDS and nxt_slash[1].isdigit() and len(nxt_slash[1]) == 4:
                        matched_qs.append(VN_Q_WORDS[nxt_slash[0]])
                        year_code = nxt_slash[1]
                        y = nxt_slash[1]
                        i += 1
                    elif nxt in VN_Q_WORDS:
                        matched_qs.append(VN_Q_WORDS[nxt])
                        i += 1
                        while i + 1 < len(tokens):
                            nxt_w = tokens[i + 1]
                            if nxt_w in VN_Q_WORDS:
                                matched_qs.append(VN_Q_WORDS[nxt_w])
                                i += 1
                            elif nxt_w in ("va", "den", "toi", "-", "va/hoac") and i + 2 < len(tokens) and tokens[i + 2] in VN_Q_WORDS:
                                matched_qs.append(VN_Q_WORDS[tokens[i + 2]])
                                i += 2
                            else:
                                break
                i += 1

            if matched_qs:
                min_q = min(matched_qs)
                max_q = max(matched_qs)
                date_from, _ = _calc_quarter_bounds(int(y), min_q)
                _, date_to = _calc_quarter_bounds(int(y), max_q)
                found_q = True
                month_filter = None

        # BƯỚC 4B: NỬA ĐẦU/CUỐI NĂM, N THÁNG ĐẦU/CUỐI NĂM, YTD
        if not found_q:
            if any(w in clean_unacc for w in ["nua dau nam", "nua dau", "6 thang dau nam", "6 thang dau", "06 thang dau", "sau thang dau nam", "sau thang dau", "ban nien dau"]):
                date_from = f"{y}-01-01"
                date_to = f"{y}-06-30"
                month_filter = None
            elif any(w in clean_unacc for w in ["nua cuoi nam", "nua cuoi", "nua sau nam", "nua sau", "6 thang cuoi nam", "6 thang cuoi", "06 thang cuoi", "sau thang cuoi nam", "sau thang cuoi", "ban nien cuoi"]):
                date_from = f"{y}-07-01"
                date_to = f"{y}-12-31"
                month_filter = None
            elif any(w in clean_unacc for w in ["thang dau nam", "thang dau"]):
                for i, tok in enumerate(tokens):
                    if tok == "thang" and i + 1 < len(tokens) and tokens[i + 1] == "dau":
                        if i > 0 and (tokens[i - 1] in VN_MONTH_WORDS or tokens[i - 1].isdigit()):
                            n_m = VN_MONTH_WORDS.get(tokens[i - 1]) or (int(tokens[i - 1]) if tokens[i - 1].isdigit() else None)
                            if n_m and 1 <= n_m <= 12:
                                last_day = calendar.monthrange(int(y), n_m)[1]
                                date_from = f"{y}-01-01"
                                date_to = f"{y}-{n_m:02d}-{last_day:02d}"
                                month_filter = None
                                break
            elif any(w in clean_unacc for w in ["thang cuoi nam", "thang cuoi"]):
                for i, tok in enumerate(tokens):
                    if tok == "thang" and i + 1 < len(tokens) and tokens[i + 1] == "cuoi":
                        if i > 0 and (tokens[i - 1] in VN_MONTH_WORDS or tokens[i - 1].isdigit()):
                            n_m = VN_MONTH_WORDS.get(tokens[i - 1]) or (int(tokens[i - 1]) if tokens[i - 1].isdigit() else None)
                            if n_m and 1 <= n_m <= 12:
                                start_m = max(1, 13 - n_m)
                                date_from = f"{y}-{start_m:02d}-01"
                                date_to = f"{y}-12-31"
                                month_filter = None
                                break
            elif any(w in clean_unacc for w in [
                "tu dau nam toi nay", "tu dau nam den nay", "tu dau nam toi gio", "tu dau nam den gio",
                "dau nam toi nay", "dau nam den nay", "dau nam den gio", "dau nam toi gio",
                "tu dau nam den thoi diem hien tai", "tu dau nam toi thoi diem hien tai",
                "dau nam den thoi diem hien tai", "dau nam toi thoi diem hien tai",
                "tu dau nam den hien tai", "tu dau nam toi hien tai",
                "luy ke tu dau nam", "tinh tu dau nam", "tu dau nam"
            ]):
                date_from = f"{y}-01-01"
                date_to = f"{y}-12-31"
                month_filter = None
            elif any(w in clean_unacc for w in ["het nam", "cuoi nam"]) and "thang" in clean_unacc:
                for i, tok in enumerate(tokens):
                    if tok == "thang" and i + 1 < len(tokens):
                        sm = VN_MONTH_WORDS.get(tokens[i + 1]) or (int(tokens[i + 1]) if tokens[i + 1].isdigit() else None)
                        if sm and 1 <= sm <= 12:
                            date_from = f"{y}-{sm:02d}-01"
                            date_to = f"{y}-12-31"
                            month_filter = None
                            break

        # BƯỚC 4C: DẢI THÁNG TỔNG QUÁT (tháng X đến tháng Y, từ tháng X đến thời điểm hiện tại...)
        if not date_from:
            found_months = []
            i = 0
            while i < len(tokens):
                if tokens[i] == "thang" and i + 1 < len(tokens):
                    cand_m = None
                    adv = 1
                    if i + 2 < len(tokens) and f"{tokens[i + 1]} {tokens[i + 2]}" in VN_MONTH_WORDS:
                        cand_m = VN_MONTH_WORDS[f"{tokens[i + 1]} {tokens[i + 2]}"]
                        adv = 2
                    elif tokens[i + 1] in VN_MONTH_WORDS:
                        cand_m = VN_MONTH_WORDS[tokens[i + 1]]
                    elif tokens[i + 1].isdigit():
                        cand_m = int(tokens[i + 1])
                    if cand_m and 1 <= cand_m <= 12:
                        tok_y = y
                        if i + adv + 2 < len(tokens) and tokens[i + adv + 1] == "nam" and tokens[i + adv + 2].isdigit() and len(tokens[i + adv + 2]) == 4:
                            tok_y = tokens[i + adv + 2]
                        found_months.append((i, cand_m, tok_y))
                        i += adv
                i += 1

            if len(found_months) == 1 and any(w in clean_unacc for w in ["den nay", "toi nay", "den gio", "hien tai"]):
                _, sm, sy = found_months[0]
                date_from = f"{sy}-{sm:02d}-01"
                date_to = f"{y}-09-30"
                month_filter = None
            elif len(found_months) >= 2:
                _, sm, sy = found_months[0]
                _, em, ey = found_months[-1]
                last_day = calendar.monthrange(int(ey), em)[1]
                date_from = f"{sy}-{sm:02d}-01"
                date_to = f"{ey}-{em:02d}-{last_day:02d}"
                if ey != y:
                    year_code = ey
                    y = ey
                month_filter = None

        # BƯỚC 4D: DẢI NGÀY ĐẦY ĐỦ (dd/mm/yyyy - dd/mm/yyyy) HOẶC NGÀY ĐƠN LẺ
        if not date_from:
            full_dates = []
            for tok in raw_input.replace(",", " ").replace("?", " ").split():
                sep = "/" if "/" in tok else ("-" if "-" in tok else ("." if "." in tok else None))
                if sep:
                    parts = tok.split(sep)
                    if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit() and parts[2].isdigit():
                        d_val, m_val, y_val = int(parts[0]), int(parts[1]), int(parts[2])
                        if 1 <= d_val <= 31 and 1 <= m_val <= 12 and 2020 <= y_val <= 2030:
                            full_dates.append(f"{y_val}-{m_val:02d}-{d_val:02d}")
            if len(full_dates) >= 2:
                date_from = full_dates[0]
                date_to = full_dates[1]
                month_filter = None
            elif len(full_dates) == 1:
                specific_date = full_dates[0]

        if not specific_date and not date_from:
            for i, tok in enumerate(tokens):
                if ("/" in tok or "-" in tok) and not tok.startswith("-"):
                    s = "/" if "/" in tok else "-"
                    parts = tok.split(s)
                    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                        d_v, m_v = int(parts[0]), int(parts[1])
                        if 1 <= m_v <= 12 and 1 <= d_v <= 31:
                            prev_tok = tokens[i - 1] if i > 0 else ""
                            if prev_tok in ("ngay", "moc", "hom", "vao") or d_v > 12:
                                max_d = calendar.monthrange(int(y), m_v)[1]
                                d_v = min(max(1, d_v), max_d)
                                specific_date = f"{y}-{m_v:02d}-{d_v:02d}"
                                break
                if tok in ("ngay", "moc", "hom", "vao") and i + 3 < len(tokens):
                    if tokens[i + 1].isdigit() and tokens[i + 2] == "thang":
                        d_v = int(tokens[i + 1])
                        cand_m_str = tokens[i + 3]
                        if i + 4 < len(tokens) and f"{tokens[i + 3]} {tokens[i + 4]}" in VN_MONTH_WORDS:
                            m_v = VN_MONTH_WORDS[f"{tokens[i + 3]} {tokens[i + 4]}"]
                        else:
                            m_v = VN_MONTH_WORDS.get(cand_m_str) or (int(cand_m_str) if cand_m_str.isdigit() else None)
                        if m_v and 1 <= m_v <= 12:
                            y_v = int(y)
                            if i + 5 < len(tokens) and tokens[i + 4] == "nam" and tokens[i + 5].isdigit():
                                y_v = int(tokens[i + 5])
                            max_d = calendar.monthrange(y_v, m_v)[1]
                            d_v = min(max(1, d_v), max_d)
                            specific_date = f"{y_v}-{m_v:02d}-{d_v:02d}"
                            year_code = str(y_v)
                            y = str(y_v)
                            break

        # BƯỚC 4E: DẢI THÁNG/NĂM DẠNG mm/yyyy HOẶC THÁNG ĐƠN LẺ
        if not date_from and not specific_date and not found_q:
            slash_month_years = []
            for tok in norm_input.replace(",", " ").replace("?", " ").split():
                if "/" in tok or "." in tok:
                    s = "/" if "/" in tok else "."
                    parts = tok.split(s)
                    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit() and len(parts[1]) == 4:
                        m_num = int(parts[0])
                        y_num = int(parts[1])
                        if 1 <= m_num <= 12 and 2020 <= y_num <= 2030:
                            slash_month_years.append((m_num, str(y_num)))
            if len(slash_month_years) >= 2:
                sm, sy = slash_month_years[0]
                em, ey = slash_month_years[1]
                last_day = calendar.monthrange(int(ey), em)[1]
                date_from = f"{sy}-{sm:02d}-01"
                date_to = f"{ey}-{em:02d}-{last_day:02d}"
                year_code = ey
                y = ey
                month_filter = None
            elif len(slash_month_years) == 1:
                m_num, sy = slash_month_years[0]
                month_filter = m_num
                year_code = sy
                y = sy
                last_day = calendar.monthrange(int(y), month_filter)[1]
                date_from = f"{y}-{month_filter:02d}-01"
                date_to = f"{y}-{month_filter:02d}-{last_day:02d}"
            else:
                matched_months = []
                i = 0
                while i < len(tokens):
                    if tokens[i] == "thang" and i + 1 < len(tokens):
                        cand_m = None
                        adv = 1
                        if i + 2 < len(tokens) and f"{tokens[i + 1]} {tokens[i + 2]}" in VN_MONTH_WORDS:
                            cand_m = VN_MONTH_WORDS[f"{tokens[i + 1]} {tokens[i + 2]}"]
                            adv = 2
                        elif tokens[i + 1] in VN_MONTH_WORDS:
                            cand_m = VN_MONTH_WORDS[tokens[i + 1]]
                        elif tokens[i + 1].isdigit():
                            cand_m = int(tokens[i + 1])
                        if cand_m and 1 <= cand_m <= 12:
                            matched_months.append(cand_m)
                            i += adv
                    i += 1
                matched_months = sorted(set(matched_months))
                if len(matched_months) == 1:
                    month_filter = matched_months[0]
                    last_day = calendar.monthrange(int(y), month_filter)[1]
                    date_from = f"{y}-{month_filter:02d}-01"
                    date_to = f"{y}-{month_filter:02d}-{last_day:02d}"
                elif len(matched_months) >= 2:
                    sm, em = matched_months[0], matched_months[-1]
                    last_day = calendar.monthrange(int(y), em)[1]
                    date_from = f"{y}-{sm:02d}-01"
                    date_to = f"{y}-{em:02d}-{last_day:02d}"
                    month_filter = None


        # 5. Trích xuất phòng ban / sở ngành qua DuckDB Catalog động
        dept_code = None
        admin_scope = self.catalog.resolve_administrative_scope(raw_input)
        if admin_scope and admin_scope.get("type") == "department":
            dept_code = admin_scope.get("department_code")

        # 6. Trích xuất đơn vị thực hiện hoặc nhiệm vụ cụ thể nếu có
        target_office = None
        target_mission = None
        if admin_scope and admin_scope.get("type") == "office":
            target_office = admin_scope.get("office_name") or admin_scope.get("name")

        if hasattr(self.catalog, "resolve_mission"):
            target_mission = self.catalog.resolve_mission(raw_input)

        target_scope = None
        if ("nhiệm vụ" in norm_input or "nhiem vu" in norm_input) and hasattr(self.catalog, "extract_scope_from_query"):
            sc_info = self.catalog.extract_scope_from_query(raw_input)
            if sc_info and sc_info.get("status") != "NONE":
                target_scope = sc_info.get("scope_name") or sc_info.get("requested_scope")

        return {
            "year_code": year_code,
            "spatial_mention": spatial_mention,
            "time_series_periods": periods,
            "department_code": dept_code,
            "month_filter": month_filter,
            "date_from": date_from,
            "date_to": date_to,
            "specific_date": specific_date,
            "target_office": target_office,
            "target_mission": target_mission,
            "target_scope": target_scope,
        }

    # --------------------------------------------------------------------------
    # TWO-STAGE HYBRID SELECTION & AMBIGUITY GATE
    # --------------------------------------------------------------------------
    def _disambiguate_metric(
        self,
        query: str,
        raw_mentions: List[str],
        tenant_code: str,
    ) -> Tuple[List[str], List[str], str, List[str]]:
        """
        Two-Stage Hybrid Selection + LLM Ambiguity Gate:
        Bước 1: DuckDB RAM Catalog lọc Top-5 ứng viên.
        Bước 2: Kiểm định khoảng cách tương đồng và phân giải ngữ cảnh.
        Trả về: (canonical_names, canonical_ids, ambiguity_status, clarification_candidates)
        """
        if not raw_mentions:
            return [], [], "NONE", []

        raw_metric = raw_mentions[0].strip()
        q_low = query.lower()

        # Cơ chế Disambiguation tổng quát từ Catalog DuckDB (Top-K candidates có score_delta)

        # 1. Kiểm tra qua ClarificationEngine (P-05, P-06)
        clarif_checked_not_needed = False
        if hasattr(self, "clarification_engine") and self.clarification_engine:
            is_needed, slots, options, labels = self.clarification_engine.check_clarification_needed(query)
            if is_needed and options and "metric_code" in slots:
                return (
                    [opt.label for opt in options],
                    [opt.value for opt in options],
                    "AMBIGUOUS",
                    [opt.label for opt in options],
                )
            clarif_checked_not_needed = not is_needed

        # Tìm kiếm ứng viên từ DuckDB Catalog
        try:
            candidates, is_ambig, _ = self.catalog.find_top_k_candidates(raw_metric, top_k=5, tenant_code=tenant_code)
        except Exception as e:
            logger.warning("Lỗi tra cứu catalog candidates: %s", e)
            candidates = []
            is_ambig = False

        if clarif_checked_not_needed:
            is_ambig = False

        if candidates:
            # Lọc bỏ các ứng viên trùng tên hiển thị và biến thể đồng nghĩa (ADR-002)
            def _stem_core_local(n: str) -> str:
                if hasattr(self, "catalog") and hasattr(self.catalog, "strip_query_noise"):
                    return self.catalog.strip_query_noise(n, "METRIC_AGG_PREFIX_NOISE")
                return n.strip()


            unique_candidates = []
            seen_cand_names = set()
            seen_cand_cores = dict()
            q_low_toks = set(q_low.split())
            wants_qty = any(w in q_low_toks for w in ("bao", "nhiêu", "số", "lượng"))

            for c in candidates:
                cn = unicodedata.normalize('NFC', c["name"].strip().lower())
                core = _stem_core_local(cn)
                if core in seen_cand_cores:
                    # Nếu query hỏi số lượng và candidate này bắt đầu bằng 'số lượng', ưu tiên candidate này
                    if wants_qty and cn.startswith("số lượng"):
                        prev_idx = seen_cand_cores[core]
                        unique_candidates[prev_idx] = c
                    continue
                seen_cand_cores[core] = len(unique_candidates)
                seen_cand_names.add(cn)
                unique_candidates.append(c)

            if len(unique_candidates) <= 1:
                is_ambig = False

            # P-05 & P-06: Nếu phát hiện câu hỏi mang tính khái quát / đa nghĩa
            if is_ambig and len(unique_candidates) >= 2:
                cand_names = [c["name"] for c in unique_candidates]
                cand_ids = [c.get("id") or c.get("code") or "" for c in unique_candidates]
                return cand_names[:3], cand_ids[:3], "AMBIGUOUS", cand_names[:3]

            # Nếu có ứng viên phù hợp
            top_cand = unique_candidates[0] if unique_candidates else candidates[0]
            canonical_names = [top_cand["name"]]
            cand_id = top_cand.get("id") or top_cand.get("code") or ""
            canonical_ids = [cand_id]
            return canonical_names, canonical_ids, "RESOLVED", []

        # Fallback exact search
        return [raw_metric], [], "RESOLVED", []

    # --------------------------------------------------------------------------
    # NORMALIZE QUERY TO CANONICAL FRAME DTO
    # --------------------------------------------------------------------------
    def normalize_query(
        self,
        query: str,
        session_tenant: str = "68",
        session_year: str = "2026",
        session_dept: Optional[str] = None,
        parent_context: Optional[str] = None,
    ) -> CanonicalQueryFrameDTO:
        """
        Chuẩn hóa toàn diện một câu hỏi sang CanonicalQueryFrameDTO.
        Khởi tạo mặc định: tenant_code = '68' (Lâm Đồng), year_code = '2026'.
        """
        clean_query = _strip_bracketed_tags(query)

        # Bóc tách tiền tố chào hỏi ủy thác qua Catalog RAM
        norm_check = clean_query.lower().strip()
        has_greet_signal = False
        if hasattr(self, "catalog") and hasattr(self.catalog, "has_lexicon_term"):
            has_greet_signal = self.catalog.has_lexicon_term(norm_check, "GREETING_LEAD_NOISE")
        else:
            has_greet_signal = norm_check.startswith(("xin chào", "chào", "hello", "hi", "tạm biệt", "cảm ơn"))

        is_pure_greeting = False
        if has_greet_signal:
            if hasattr(self, "catalog") and hasattr(self.catalog, "strip_query_noise"):
                rem = self.catalog.strip_query_noise(norm_check, "GREETING_LEAD_NOISE")
                if not rem or not rem.strip(" ,:.-!?"):
                    is_pure_greeting = True
            elif norm_check in ("xin chào", "chào", "hello", "hi", "tạm biệt", "cảm ơn"):
                is_pure_greeting = True

        if is_pure_greeting:
            prov_name = getattr(settings, "PROVINCE_NAME", "cấp tỉnh")
            is_farewell = False
            if hasattr(self, "catalog") and hasattr(self.catalog, "has_lexicon_term"):
                is_farewell = self.catalog.has_lexicon_term(norm_check, "FAREWELL_SIGNAL")
            else:
                is_farewell = any(w in norm_check for w in ("tạm biệt", "cảm ơn", "thank", "hẹn gặp lại"))
            direct_ans = (
                f"Cảm ơn đồng chí. Rất hân hạnh được hỗ trợ đồng chí tra cứu số liệu DWH {prov_name}. Chúc đồng chí một ngày làm việc hiệu quả!"
                if is_farewell else
                f"Xin chào đồng chí! Tôi là Trợ lý Ảo Kho Dữ Liệu DWH {prov_name}. Tôi có thể hỗ trợ đồng chí tra cứu: "
                "1. Chỉ tiêu kinh tế - xã hội; "
                "2. Tình hình phê duyệt báo cáo; "
                "3. Danh mục nhiệm vụ trọng tâm; "
                "4. Phân công cán bộ phụ trách nhiệm vụ. Đồng chí cần tra cứu thông tin gì?"
            )
            return CanonicalQueryFrameDTO(
                user_query=query,
                intent=CanonicalIntentEnum.GREETING_FAREWELL,
                target_table="none",
                direct_answer=direct_ans,
                is_out_of_scope=False,
                is_conversational_only=True,
                tenant_code=session_tenant or "68",
                year_code=session_year or "2026",
            )

        if has_greet_signal and hasattr(self, "catalog") and hasattr(self.catalog, "strip_query_noise"):
            clean_query = self.catalog.strip_query_noise(clean_query, "GREETING_LEAD_NOISE").lstrip(" ,:-.!?")


        # 0. Kiểm tra Động cơ Làm Rõ Chủ Động (Active Clarification Gate - P-05, P-06, Turn 1 Temporal)
        if hasattr(self, "clarification_engine") and self.clarification_engine:
            if not self._is_officer_query(clean_query):
                is_needed, slots, options, labels = self.clarification_engine.check_clarification_needed(clean_query)
                if is_needed and options:
                    if "metric_code" in slots or "metric" in slots:
                        return CanonicalQueryFrameDTO(
                            user_query=clean_query,
                            intent=CanonicalIntentEnum.METRIC_POINT_INQUIRY,
                            target_table="fact_report_criteria",
                            ambiguity_status="AMBIGUOUS",
                            clarification_candidates=[opt.label for opt in options],
                            canonical_metric_names=[opt.label for opt in options],
                            canonical_metric_ids=[opt.value for opt in options],
                            tenant_code=session_tenant or "68",
                            year_code=session_year or "2026",
                        )
                    else:
                        return CanonicalQueryFrameDTO(
                            user_query=clean_query,
                            intent=CanonicalIntentEnum.METRIC_POINT_INQUIRY,
                            target_table="fact_report_criteria",
                            ambiguity_status="AMBIGUOUS",
                            clarification_candidates=[opt.label for opt in options],
                            canonical_metric_names=[],
                            canonical_metric_ids=[],
                            tenant_code=session_tenant or "68",
                            year_code=session_year or "2026",
                        )

        # Chạy Stream B trước để lấy context thời gian/địa bàn, sau đó chạy Stream A
        stream_b = self._extract_stream_b_deterministic(clean_query)
        stream_a = self._extract_stream_a_deterministic(clean_query, stream_b=stream_b)

        is_fact_calc = stream_a.get("is_fact_calc", False)

        if stream_a["intent"] != CanonicalIntentEnum.METRIC_POINT_INQUIRY or is_fact_calc:
            pass
        else:
            cand_metrics = []
            if hasattr(self.catalog, "retrieve_candidate_metrics"):
                cand_metrics = self.catalog.retrieve_candidate_metrics(
                    clean_query, top_k=3, score_threshold=0.40, tenant_code=session_tenant or "68"
                )
            nlu = self._parse_query_nlu_llm(clean_query, candidate_metrics=cand_metrics)
            self._apply_nlu_to_streams(clean_query, nlu, stream_a, stream_b)

        return self._build_canonical_frame(
            clean_query=clean_query,
            stream_a=stream_a,
            stream_b=stream_b,
            session_tenant=session_tenant,
            session_year=session_year,
            session_dept=session_dept,
            parent_context=parent_context,
        )

    def _apply_nlu_to_streams(
        self,
        clean_query: str,
        nlu: Any,
        stream_a: Dict[str, Any],
        stream_b: Dict[str, Any],
    ) -> None:
        if not nlu:
            return
        if nlu.intent == "CAPABILITY_INTRO":
            stream_a["intent"] = CanonicalIntentEnum.CAPABILITY_INTRO
            stream_a["is_out_of_scope"] = False
            stream_a["direct_answer"] = None
            stream_a["target_table"] = "none"
        elif nlu.intent == "GREETING_FAREWELL" or getattr(nlu, "is_conversational_only", False):
            stream_a["intent"] = CanonicalIntentEnum.GREETING_FAREWELL
            stream_a["is_out_of_scope"] = False
            stream_a["direct_answer"] = nlu.direct_answer
            stream_a["target_table"] = "none"
        elif nlu.is_out_of_scope:
            stream_a["is_out_of_scope"] = True
            stream_a["direct_answer"] = nlu.direct_answer
            stream_a["intent"] = CanonicalIntentEnum.OUT_OF_SCOPE
        elif nlu.intent == "DIMENSION_LISTING":
            stream_a["intent"] = CanonicalIntentEnum.DIMENSION_LISTING
            stream_a["target_table"] = "fact_report_criteria"
            stream_a["raw_metric_mentions"] = []
            stream_a["subject_entity"] = None
            stream_a["target_attribute"] = None
            stream_a["aggregation_function"] = "NONE"
            stream_a["limit"] = None
            if getattr(nlu, "is_inventory_query", False):
                stream_a["is_inventory_query"] = True
        elif nlu.intent == "ENTITY_ATTRIBUTE_LOOKUP":
            subj_cand = nlu.subject_entity or stream_a.get("subject_entity")
            if subj_cand and getattr(self.catalog, "is_dimension_query", lambda q, d: False)(subj_cand, "criteria"):
                stream_a["intent"] = CanonicalIntentEnum.DIMENSION_LISTING
                stream_a["target_table"] = "fact_report_criteria"
                stream_a["raw_metric_mentions"] = []
                stream_a["subject_entity"] = None
                stream_a["aggregation_function"] = "NONE"
                stream_a["limit"] = None
            else:
                is_office_mission = (nlu.target_table == "office_mission") or (hasattr(self.catalog, "resolve_target_table") and self.catalog.resolve_target_table(clean_query) == "office_mission")
                if is_office_mission:
                    stream_a["intent"] = CanonicalIntentEnum.RELATIONAL_EXPLORATION
                    stream_a["target_table"] = "office_mission"
                    stream_a["subject_entity"] = subj_cand or "Chi cục"
                    stream_a["target_attribute"] = "nhiệm vụ phụ trách"
                else:
                    stream_a["intent"] = CanonicalIntentEnum.ENTITY_ATTRIBUTE_LOOKUP
                    stream_a["target_table"] = nlu.target_table or (self.catalog.resolve_target_table(clean_query) if hasattr(self.catalog, "resolve_target_table") else "fact_report_criteria")
                    stream_a["subject_entity"] = subj_cand
                    stream_a["target_attribute"] = nlu.target_attribute or stream_a.get("target_attribute")
                    if stream_a["subject_entity"]:
                        stream_a["raw_metric_mentions"] = [stream_a["subject_entity"]]
        elif nlu.intent == "RELATIONAL_EXPLORATION":
            stream_a["intent"] = CanonicalIntentEnum.RELATIONAL_EXPLORATION
            stream_a["target_table"] = nlu.target_table or (self.catalog.resolve_target_table(clean_query) if hasattr(self.catalog, "resolve_target_table") else "ward")
            stream_a["subject_entity"] = nlu.subject_entity or stream_a.get("subject_entity")
            stream_a["target_attribute"] = nlu.target_attribute or stream_a.get("target_attribute")
        elif nlu.intent in ("METRIC_POINT_INQUIRY", "METRIC_NUMERIC_CALCULATION"):
            if nlu.is_out_of_scope:
                stream_a["is_out_of_scope"] = True
                stream_a["direct_answer"] = nlu.direct_answer
                stream_a["intent"] = CanonicalIntentEnum.OUT_OF_SCOPE
            else:
                stream_a["intent"] = CanonicalIntentEnum.METRIC_POINT_INQUIRY
                if nlu.subject_entity:
                    stream_a["subject_entity"] = nlu.subject_entity
                    stream_a["raw_metric_mentions"] = [nlu.subject_entity]
        elif nlu.intent == "METADATA_EXPLORATION":
            stream_a["intent"] = CanonicalIntentEnum.METADATA_EXPLORATION
            stream_a["target_table"] = nlu.target_table or (self.catalog.resolve_target_table(clean_query) if hasattr(self.catalog, "resolve_target_table") else "criteria")

        if getattr(nlu, "temporal_slot", None) and isinstance(nlu.temporal_slot, dict):
            try:
                ts_spec = TemporalSlotSpec(**nlu.temporal_slot)
                cal_bounds = ts_spec.to_calendar_bounds()
                for k, v in cal_bounds.items():
                    if v and not stream_b.get(k):
                        stream_b[k] = v
            except Exception:
                pass
            for k, v in nlu.temporal_slot.items():
                if v and not stream_b.get(k):
                    stream_b[k] = v

    def _build_canonical_frame(
        self,
        clean_query: str,
        stream_a: Dict[str, Any],
        stream_b: Dict[str, Any],
        session_tenant: str = "68",
        session_year: str = "2026",
        session_dept: Optional[str] = None,
        parent_context: Optional[str] = None,
    ) -> CanonicalQueryFrameDTO:
        # 1. Phân giải địa bàn động (Schema-Driven Dynamic Spatial Resolution)
        spatial_mention = stream_b.get("spatial_mention")
        resolved_tenant = self.catalog.resolve_spatial_tenant(spatial_mention, default_tenant=session_tenant or "68")

        # 2. Phân giải năm báo cáo (Kế thừa session_year nếu không có trong câu hỏi)
        resolved_year = stream_b.get("year_code") or session_year or "2026"
        is_empty_year = resolved_year in ("2024", "2025")

        # 3. Phân giải đơn vị
        if stream_a.get("is_inventory_query"):
            resolved_dept = stream_a.get("department_code") or stream_b.get("department_code")
        else:
            resolved_dept = stream_a.get("department_code") or stream_b.get("department_code") or session_dept

        # 4. Phân giải chỉ tiêu (Two-Stage Hybrid Selection + Ambiguity Gate)
        clarif_triggered = False
        if (
            hasattr(self, "clarification_engine")
            and self.clarification_engine
            and stream_b.get("date_from") is None
            and stream_b.get("month_filter") is None
            and stream_b.get("specific_date") is None
            and stream_a["intent"] not in (
                CanonicalIntentEnum.OUT_OF_SCOPE,
                CanonicalIntentEnum.GREETING_FAREWELL,
                CanonicalIntentEnum.CAPABILITY_INTRO,
                CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT,
            )
        ):
            try:
                is_needed, slots, options, labels = self.clarification_engine.check_clarification_needed(clean_query)
                if is_needed and options and "metric_code" in slots:
                    canonical_names = [opt.label for opt in options]
                    canonical_ids = [str(opt.value) for opt in options]
                    ambig_status = "AMBIGUOUS"
                    clarification_cands = [opt.label for opt in options]
                    stream_a["intent"] = CanonicalIntentEnum.METRIC_POINT_INQUIRY
                    clarif_triggered = True
            except Exception as e:
                logger.debug("Lỗi check_clarification_needed trong _build_canonical_frame: %s", e)

        if not clarif_triggered:
            if stream_a["intent"] in (
                CanonicalIntentEnum.METADATA_EXPLORATION,
                CanonicalIntentEnum.DIMENSION_LISTING,
                CanonicalIntentEnum.CAPABILITY_INTRO,
                CanonicalIntentEnum.OUT_OF_SCOPE,
                CanonicalIntentEnum.RELATIONAL_EXPLORATION,
                CanonicalIntentEnum.OFFICER_ASSIGNMENT,
                CanonicalIntentEnum.GREETING_FAREWELL,
                CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT,
            ):
                canonical_names = []
                canonical_ids = []
                ambig_status = "RESOLVED"
                clarification_cands = []
            elif stream_a["intent"] == CanonicalIntentEnum.ENTITY_ATTRIBUTE_LOOKUP:
                subj = stream_a.get("subject_entity") or (stream_a.get("raw_metric_mentions", [""])[0] if stream_a.get("raw_metric_mentions") else "")
                cands, _, _ = self.catalog.find_top_k_candidates(subj, top_k=1, tenant_code=resolved_tenant)
                if cands:
                    canonical_names = [cands[0]["name"]]
                    canonical_ids = [cands[0].get("id") or cands[0].get("code") or ""]
                else:
                    canonical_names = [subj] if subj else []
                    canonical_ids = []
                ambig_status = "RESOLVED"
                clarification_cands = []
            else:
                h_info = None
                if hasattr(self.catalog, "classify_criterion_hierarchy"):
                    try:
                        h_info = self.catalog.classify_criterion_hierarchy(clean_query, parent_context=parent_context)
                    except TypeError:
                        h_info = self.catalog.classify_criterion_hierarchy(clean_query)

                if (
                    h_info
                    and h_info.get("matched_name")
                    and h_info.get("classification") in ("parent", "parent_group", "duplicate_leaf", "single_leaf")
                    and (h_info.get("parent_code") or h_info.get("codes") or h_info.get("item"))
                ):
                    m_name_h = h_info["matched_name"]
                    m_code_h = h_info.get("matched_code")
                    canonical_names = [m_name_h]
                    if h_info.get("classification") == "duplicate_leaf" and h_info.get("codes"):
                        canonical_ids = list(h_info.get("codes"))
                    else:
                        canonical_ids = [m_code_h] if m_code_h else []
                    ambig_status = "RESOLVED"
                    clarification_cands = []
                else:
                    canonical_names, canonical_ids, ambig_status, clarification_cands = self._disambiguate_metric(
                        query=clean_query,
                        raw_mentions=stream_a.get("raw_metric_mentions", []),
                        tenant_code=resolved_tenant,
                    )
                    if h_info and h_info.get("matched_name"):
                        m_name_h = h_info["matched_name"]
                        m_code_h = h_info.get("matched_code")
                        q_norm_c = " ".join(clean_query.lower().split())
                        if h_info.get("classification") in ("parent", "parent_group"):
                            canonical_names = [m_name_h]
                            canonical_ids = [m_code_h] if m_code_h else []
                            ambig_status = "RESOLVED"
                            clarification_cands = []
                        elif h_info.get("classification") in ("duplicate_leaf", "single_leaf"):
                            if (
                                not canonical_names
                                or " ".join(canonical_names[0].lower().split()) not in q_norm_c
                                or len(m_name_h) >= len(canonical_names[0])
                                or ambig_status == "AMBIGUOUS"
                                or h_info.get("classification") == "duplicate_leaf"
                                or bool(h_info.get("item"))
                            ):
                                canonical_names = [m_name_h]
                                if h_info.get("classification") == "duplicate_leaf" and h_info.get("codes"):
                                    canonical_ids = list(h_info.get("codes"))
                                else:
                                    canonical_ids = [m_code_h] if m_code_h else []
                                ambig_status = "RESOLVED"
                                clarification_cands = []

        return CanonicalQueryFrameDTO(
            user_query=clean_query,
            intent=stream_a["intent"],
            target_table=stream_a["target_table"],
            is_out_of_scope=stream_a.get("is_out_of_scope", False),
            direct_answer=stream_a.get("direct_answer"),
            subject_entity=None if stream_a["intent"] == CanonicalIntentEnum.DIMENSION_LISTING else stream_a.get("subject_entity"),
            target_attribute=stream_a.get("target_attribute"),
            exclude_entities=stream_a.get("exclude_entities", []),
            search_keyword=stream_a.get("search_keyword"),
            canonical_metric_names=canonical_names,
            canonical_metric_ids=canonical_ids,
            raw_metric_mentions=[] if stream_a["intent"] == CanonicalIntentEnum.DIMENSION_LISTING else stream_a.get("raw_metric_mentions", []),
            spatial_mention=spatial_mention,
            tenant_code=resolved_tenant,
            year_code=resolved_year,
            department_code=resolved_dept,
            aggregation_function=stream_a["aggregation_function"],
            ambiguity_status=ambig_status,
            clarification_candidates=clarification_cands,
            is_snapshot_dedup_needed=stream_a["intent"] in (CanonicalIntentEnum.METRIC_TOP_K, CanonicalIntentEnum.METRIC_GROWTH_YOY),
            sort_direction=stream_a["sort_direction"],
            limit=stream_a["limit"],
            is_empty_year=is_empty_year,
            time_series_periods=stream_b.get("time_series_periods", []),
            date_from=stream_b.get("date_from"),
            date_to=stream_b.get("date_to"),
            month_filter=stream_b.get("month_filter"),
            specific_date=stream_b.get("specific_date"),
            target_office=None if stream_a["intent"] == CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT else (stream_a.get("target_office") or stream_b.get("target_office")),
            target_mission=stream_a.get("target_mission") or stream_b.get("target_mission"),
            target_scope=stream_a.get("target_scope") or stream_b.get("target_scope"),
            target_position=stream_a.get("target_position"),
            target_user_name=stream_a.get("target_user_name"),
            is_inventory_query=stream_a.get("is_inventory_query", False) and stream_b.get("month_filter") is None and stream_b.get("date_from") is None and stream_b.get("date_to") is None and stream_b.get("specific_date") is None,
            is_level1_hierarchy_view=stream_a.get("is_level1_hierarchy_view", False),
            clarification_message=stream_a.get("clarification_message"),
            parent_criterion_context=parent_context,
            status_filter=stream_a.get("status_filter"),
            audit_sub_intent=stream_a.get("audit_sub_intent"),
            include_draft_comparison=stream_a.get("include_draft_comparison", False),
        )


    # --------------------------------------------------------------------------
    # DETERMINISTIC SQL SYNTHESIS (TẦNG 2: BIÊN DỊCH AST TẤT ĐỊNH)
    # --------------------------------------------------------------------------
    def compile_canonical_sql(self, frame: CanonicalQueryFrameDTO) -> str:
        """
        Biên dịch CanonicalQueryFrameDTO thành câu lệnh SQL PostgreSQL 16 tất định duy nhất 100%.
        Triệt tiêu hoàn toàn tính giòn ngôn ngữ.
        """
        # 0. OUT_OF_SCOPE / GREETING_FAREWELL: Không sinh SQL
        if frame.intent in (CanonicalIntentEnum.OUT_OF_SCOPE, CanonicalIntentEnum.GREETING_FAREWELL) or frame.is_out_of_scope:
            return ""

        limit_clause = f"\nLIMIT {frame.limit};" if frame.limit else ";"

        # 0.1. REPORT_FORM_MISSION_AUDIT (REQ-Q05: SC-5.1, SC-5.2, SC-5.3)
        if frame.intent == CanonicalIntentEnum.REPORT_FORM_MISSION_AUDIT:
            t_code = (frame.tenant_code or "68").replace("'", "''")
            y_code = (frame.year_code or "2026").replace("'", "''")
            sub_intent = frame.audit_sub_intent or "REPORT_SUBMISSION_STATUS"

            if sub_intent == "MISSION_ASSIGNMENT_MATRIX" or frame.target_table == "mission_assignment_matrix":
                scope_cond = ""
                if frame.target_scope:
                    sc_esc = frame.target_scope.replace("'", "''")
                    scope_cond = f"\n  AND sl.scope_name ILIKE '%{sc_esc}%'"
                mis_cond = ""
                if frame.target_mission:
                    m_esc = frame.target_mission.replace("'", "''")
                    mis_cond = f"\n  AND m.mission_name ILIKE '%{m_esc}%'"
                return (
                    f"WITH office_agg AS (\n"
                    f"    SELECT om.mission_id,\n"
                    f"           COUNT(DISTINCT o.id) AS office_count,\n"
                    f"           STRING_AGG(DISTINCT o.office_name, ', ' ORDER BY o.office_name) AS assigned_offices\n"
                    f"    FROM dwh_internal.office_mission om\n"
                    f"    JOIN dwh_internal.office o ON om.office_id = o.id\n"
                    f"    WHERE om.tenant_code = '{t_code}'\n"
                    f"      AND om.deleted_date IS NULL\n"
                    f"      AND o.deleted_at IS NULL\n"
                    f"    GROUP BY om.mission_id\n"
                    f"),\n"
                    f"user_role_lookup AS (\n"
                    f"    SELECT ou.user_id, ou.office_id, ou.role\n"
                    f"    FROM dwh_internal.office_user ou\n"
                    f"    WHERE ou.is_active = true\n"
                    f"),\n"
                    f"user_agg AS (\n"
                    f"    SELECT um.mission_id,\n"
                    f"           COUNT(DISTINCT u.id) AS officer_count,\n"
                    f"           STRING_AGG(DISTINCT um.office_name, ', ' ORDER BY um.office_name) AS officer_offices,\n"
                    f"           STRING_AGG(\n"
                    f"               DISTINCT (\n"
                    f"                   u.name || ' (' || COALESCE(u.username, '-') || ')'\n"
                    f"                   || ' - Chức vụ: ' || COALESCE(u.position, '-')\n"
                    f"                   || ' - Vai trò: ' || COALESCE(url.role, '-')\n"
                    f"                   || ' (' || COALESCE(um.office_name, '-') || ')'\n"
                    f"               ),\n"
                    f"               '; '\n"
                    f"           ) AS assigned_officers\n"
                    f"    FROM dwh_internal.user_mission um\n"
                    f"    JOIN dwh_internal.\"user\" u ON um.user_id = u.id\n"
                    f"    LEFT JOIN user_role_lookup url ON url.user_id = u.id AND url.office_id = um.office_id\n"
                    f"    WHERE um.tenant_code = '{t_code}'\n"
                    f"      AND um.deleted_date IS NULL\n"
                    f"      AND u.deleted_at IS NULL\n"
                    f"    GROUP BY um.mission_id\n"
                    f"),\n"
                    f"scope_lookup AS (\n"
                    f"    SELECT s.id, s.scope_name\n"
                    f"    FROM dwh_internal.scope s\n"
                    f"    WHERE s.tenant_code = '{t_code}'\n"
                    f"      AND s.deleted_date IS NULL\n"
                    f")\n"
                    f"SELECT m.mission_code,\n"
                    f"       m.mission_name,\n"
                    f"       COALESCE(sl.scope_name, 'Chưa phân loại') AS scope_name,\n"
                    f"       COALESCE(oa.office_count, 0) AS office_count,\n"
                    f"       COALESCE(oa.assigned_offices, 'Chưa phân công phòng ban') AS assigned_offices,\n"
                    f"       COALESCE(ua.officer_count, 0) AS officer_count,\n"
                    f"       COALESCE(ua.officer_offices, '') AS officer_offices,\n"
                    f"       COALESCE(ua.assigned_officers, 'Chưa phân công cán bộ') AS assigned_officers\n"
                    f"FROM dwh_internal.mission m\n"
                    f"LEFT JOIN scope_lookup sl ON m.scope_id = sl.id\n"
                    f"LEFT JOIN office_agg oa ON m.id = oa.mission_id\n"
                    f"LEFT JOIN user_agg ua ON m.id = ua.mission_id\n"
                    f"WHERE m.tenant_code = '{t_code}'\n"
                    f"  AND m.year_code = '{y_code}'{scope_cond}{mis_cond}\n"
                    f"ORDER BY m.mission_code ASC;"
                )

            if sub_intent == "FORM_CRITERIA_GROUP" or frame.target_table == "criteria_group":
                cg_status_cond = ""
                if frame.blocked_draft_access or frame.status_filter == ["approved"]:
                    cg_status_cond = "\n  AND cg.status = 'active'"
                return (
                    f"WITH crit_agg AS (\n"
                    f"    SELECT cg.id AS group_id,\n"
                    f"           COUNT(DISTINCT CASE WHEN c.parent_id IS NULL THEN c.id END) AS root_criteria_count,\n"
                    f"           COUNT(DISTINCT c.id) AS total_criteria_count,\n"
                    f"           STRING_AGG(\n"
                    f"               DISTINCT CASE WHEN c.parent_id IS NULL THEN c.name END,\n"
                    f"               '; '\n"
                    f"               ORDER BY CASE WHEN c.parent_id IS NULL THEN c.name END\n"
                    f"           ) AS root_criteria_names,\n"
                    f"           STRING_AGG(DISTINCT m.mission_name, ', ' ORDER BY m.mission_name) AS mission_names,\n"
                    f"           STRING_AGG(DISTINCT s.scope_name, ', ' ORDER BY s.scope_name) AS scope_names\n"
                    f"    FROM dwh_internal.criteria_group cg\n"
                    f"    LEFT JOIN dwh_internal.mission m\n"
                    f"      ON m.id = ANY(cg.mission_ids) AND m.deleted_date IS NULL\n"
                    f"    LEFT JOIN dwh_internal.scope s\n"
                    f"      ON s.id = ANY(cg.scope_ids) AND s.deleted_date IS NULL\n"
                    f"    LEFT JOIN dwh_internal.criteria c\n"
                    f"      ON c.mission_id::text = ANY(string_to_array(trim(both '{{}}' from cg.mission_ids::text), ','))\n"
                    f"     AND c.deleted_date IS NULL\n"
                    f"    WHERE cg.tenant_code = '{t_code}'\n"
                    f"      AND cg.year_code = '{y_code}'\n"
                    f"      AND cg.deleted_date IS NULL\n"
                    f"    GROUP BY cg.id\n"
                    f"),\n"
                    f"fact_group_agg AS (\n"
                    f"    SELECT f.criteria_group_id AS group_id,\n"
                    f"           COUNT(f.fact_sk) AS tong_ban_ghi,\n"
                    f"           COUNT(DISTINCT f.criteria_id) AS so_chi_tieu\n"
                    f"    FROM dwh_internal.fact_report_criteria f\n"
                    f"    WHERE f.tenant_code = '{t_code}'\n"
                    f"      AND f.year_code = '{y_code}'\n"
                    f"      AND f.report_status IN ('approved', 'draft')\n"
                    f"    GROUP BY f.criteria_group_id\n"
                    f"),\n"
                    f"form_stats AS (\n"
                    f"    SELECT COUNT(*) AS collection_form_count\n"
                    f"    FROM dwh_internal.collection_form cf\n"
                    f"    WHERE cf.tenant_code = '{t_code}'\n"
                    f"      AND cf.deleted_date IS NULL\n"
                    f")\n"
                    f"SELECT cg.id::text AS group_id,\n"
                    f"       cg.name AS group_name,\n"
                    f"       cg.status AS group_status,\n"
                    f"       cg.year_code,\n"
                    f"       cg.department_code,\n"
                    f"       COALESCE(cg.created_by, '-') AS created_by,\n"
                    f"       COALESCE(ca.mission_names, '-') AS mission_names,\n"
                    f"       COALESCE(ca.scope_names, '-') AS scope_names,\n"
                    f"       COALESCE(ca.root_criteria_count, 0) AS root_criteria_count,\n"
                    f"       COALESCE(ca.total_criteria_count, fga.so_chi_tieu, 0) AS total_criteria_count,\n"
                    f"       COALESCE(ca.total_criteria_count, fga.so_chi_tieu, 0) AS so_chi_tieu,\n"
                    f"       COALESCE(fga.tong_ban_ghi, 0) AS tong_ban_ghi,\n"
                    f"       COALESCE(ca.root_criteria_names, '-') AS root_criteria_names,\n"
                    f"       COALESCE((SELECT collection_form_count FROM form_stats), 0) AS collection_form_total\n"
                    f"FROM dwh_internal.criteria_group cg\n"
                    f"LEFT JOIN crit_agg ca ON cg.id = ca.group_id\n"
                    f"LEFT JOIN fact_group_agg fga ON cg.id = fga.group_id\n"
                    f"WHERE cg.tenant_code = '{t_code}'\n"
                    f"  AND cg.year_code = '{y_code}'\n"
                    f"  AND cg.deleted_date IS NULL{cg_status_cond}\n"
                    f"ORDER BY CASE WHEN cg.status = 'active' THEN 1 ELSE 2 END,\n"
                    f"         cg.name ASC,\n"
                    f"         cg.created_date DESC NULLS LAST;"
                )

            # Default sub-intent: REPORT_SUBMISSION_STATUS (SC-5.1)
            eff_statuses = [str(s).strip().lower() for s in (frame.status_filter or ["approved", "draft", "pending"]) if str(s).strip()]
            if frame.blocked_draft_access or eff_statuses == ["approved"]:
                f_status_clause = "AND f.report_status = 'approved'"
                r_status_clause = "AND r.status = 'approved'"
            elif "all" in eff_statuses:
                f_status_clause = ""
                r_status_clause = ""
            else:
                quoted_st = ", ".join(f"'{s}'" for s in eff_statuses)
                f_status_clause = f"AND f.report_status IN ({quoted_st})"
                r_status_clause = f"AND r.status IN ({quoted_st})"

            return (
                f"WITH fact_agg AS (\n"
                f"    SELECT f.report_id,\n"
                f"           MAX(f.office_id::text)::uuid AS office_id,\n"
                f"           STRING_AGG(DISTINCT f.mission_name, ', ' ORDER BY f.mission_name) AS mission_name,\n"
                f"           COUNT(f.fact_sk) AS fact_row_count,\n"
                f"           COUNT(DISTINCT f.criteria_id) AS criteria_count,\n"
                f"           COUNT(DISTINCT CASE WHEN NULLIF(TRIM(f.value), '') IS NOT NULL AND TRIM(value) != '-' THEN f.criteria_id END) AS recorded_criteria_count\n"
                f"    FROM dwh_internal.fact_report_criteria f\n"
                f"    WHERE f.tenant_code = '{t_code}'\n"
                f"      AND f.year_code = '{y_code}'\n"
                f"      {f_status_clause}\n"
                f"    GROUP BY f.report_id\n"
                f"),\n"
                f"office_lookup AS (\n"
                f"    SELECT o.id, o.office_name\n"
                f"    FROM dwh_internal.office o\n"
                f"    WHERE o.tenant_code = '{t_code}'\n"
                f"      AND o.deleted_at IS NULL\n"
                f")\n"
                f"SELECT r.id::text AS report_id,\n"
                f"       r.report_date::date::text AS report_date,\n"
                f"       r.submitted_date::date::text AS submitted_date,\n"
                f"       r.status AS report_status,\n"
                f"       r.year_code,\n"
                f"       r.department_code,\n"
                f"       COALESCE(r.created_by, '-') AS created_by,\n"
                f"       COALESCE(ol.office_name, 'Chi cục') AS office_name,\n"
                f"       COALESCE(fa.mission_name, '-') AS mission_name,\n"
                f"       COALESCE(fa.fact_row_count, 0) AS fact_row_count,\n"
                f"       COALESCE(fa.criteria_count, 0) AS criteria_count,\n"
                f"       COALESCE(fa.recorded_criteria_count, 0) AS recorded_criteria_count\n"
                f"FROM dwh_internal.report r\n"
                f"LEFT JOIN fact_agg fa ON r.id = fa.report_id\n"
                f"LEFT JOIN office_lookup ol ON fa.office_id = ol.id\n"
                f"WHERE r.tenant_code = '{t_code}'\n"
                f"  AND r.year_code = '{y_code}'\n"
                f"  AND r.deleted_date IS NULL\n"
                f"  {r_status_clause}\n"
                f"ORDER BY CASE WHEN r.status = 'approved' THEN 1 WHEN r.status = 'draft' THEN 2 ELSE 3 END,\n"
                f"         r.report_date DESC NULLS LAST,\n"
                f"         r.submitted_date DESC NULLS LAST;"
            )

        # ENTITY_ATTRIBUTE_LOOKUP: Tra cứu đơn vị / tỉnh thực hiện của chỉ tiêu KTXH
        if frame.intent == CanonicalIntentEnum.ENTITY_ATTRIBUTE_LOOKUP:
            cand_name = frame.canonical_metric_names[0] if frame.canonical_metric_names else (frame.subject_entity or "")
            cand_escaped = cand_name.replace("'", "''")
            return (
                f"SELECT f.name AS ten_chi_tieu, o.office_name AS ten_phong_ban, f.value, f.report_date\n"
                f"FROM dwh_internal.fact_report_criteria f\n"
                f"LEFT JOIN dwh_internal.office o ON f.office_id = o.id\n"
                f"WHERE f.tenant_code = '{frame.tenant_code}'\n"
                f"  AND f.report_status = 'approved'\n"
                f"  AND f.name ILIKE '%{cand_escaped}%'\n"
                f"ORDER BY f.report_date DESC\n"
                f"LIMIT 1;"
            )

        # RELATIONAL_EXPLORATION: Khám phá quan hệ liên bảng (xã phường theo tỉnh, nhiệm vụ theo phòng ban)
        if frame.intent == CanonicalIntentEnum.RELATIONAL_EXPLORATION:
            if frame.target_table == "ward":
                if frame.aggregation_function == "COUNT":
                    return (
                        f"SELECT p.name AS ten_tinh, COUNT(w.id) AS tong_so_xa_phuong\n"
                        f"FROM dwh_internal.province p\n"
                        f"JOIN dwh_internal.ward w ON p.code = w.province_code\n"
                        f"WHERE p.code = '{frame.tenant_code}'\n"
                        f"GROUP BY p.name;"
                    )
                else:
                    order_clause = "w.code ASC" if frame.search_keyword == "code" else "w.name ASC"
                    return (
                        f"SELECT p.name AS ten_tinh, w.code AS ma_xa, w.name AS ten_xa\n"
                        f"FROM dwh_internal.province p\n"
                        f"JOIN dwh_internal.ward w ON p.code = w.province_code\n"
                        f"WHERE p.code = '{frame.tenant_code}'\n"
                        f"  AND w.is_activated = true\n"
                        f"ORDER BY {order_clause}{limit_clause}"
                    )
            if frame.target_table == "office_mission":
                target_off = frame.target_office or frame.subject_entity or ""
                conds = [f"o.tenant_code = '{frame.tenant_code}'"]
                if target_off:
                    off_esc = target_off.replace("'", "''")
                    conds.append(f"o.office_name ILIKE '%{off_esc}%'")
                    cols = "o.office_name, m.mission_name, s.scope_name"
                    order_by = "m.mission_name ASC"
                else:
                    cols = "o.office_name, m.mission_name, s.scope_name, s.scope_code"
                    order_by = "o.office_name, m.mission_name"
                where_clause = " AND ".join(conds)
                return (
                    f"SELECT {cols}\n"
                    f"FROM dwh_internal.office o\n"
                    f"JOIN dwh_internal.office_mission om ON o.id = om.office_id\n"
                    f"JOIN dwh_internal.mission m ON om.mission_id = m.id\n"
                    f"JOIN dwh_internal.scope s ON m.scope_id = s.id\n"
                    f"WHERE {where_clause}\n"
                    f"ORDER BY {order_by}{limit_clause}"
                )

        # OFFICER_ASSIGNMENT: Tra cứu cán bộ phụ trách nhiệm vụ
        if frame.intent == CanonicalIntentEnum.OFFICER_ASSIGNMENT:
            conds = [f"u.tenant_code = '{frame.tenant_code}'"]
            if frame.target_mission:
                m_esc = frame.target_mission.replace("'", "''")
                conds.append(f"m.mission_name ILIKE '%{m_esc}%'")
            if frame.target_office:
                o_esc = frame.target_office.replace("'", "''")
                conds.append(f"um.office_name ILIKE '%{o_esc}%'")
            if frame.exclude_entities:
                for ex in frame.exclude_entities:
                    ex_esc = ex.replace("'", "''")
                    conds.append(f"um.office_name NOT ILIKE '%{ex_esc}%'")
            if frame.target_position:
                p_esc = frame.target_position.replace("'", "''")
                conds.append(f"u.position ILIKE '%{p_esc}%'")
            if frame.target_user_name:
                u_esc = frame.target_user_name.replace("'", "''")
                u_search = self.catalog.strip_query_noise(u_esc, "OFFICER_PREFIX_NOISE") if hasattr(self.catalog, "strip_query_noise") else u_esc
                u_esc_clean = u_search.replace("'", "''")
                conds.append(f"u.name ILIKE '%{u_esc_clean}%'")
            where_clause = " AND ".join(conds)

            cols = "u.name AS ten_can_bo, u.position, m.mission_name, s.scope_name, um.office_name"
            order_clause = "m.mission_name ASC" if frame.target_user_name else "u.name, m.mission_name"

            return (
                f"SELECT {cols}\n"
                f"FROM dwh_internal.\"user\" u\n"
                f"JOIN dwh_internal.user_mission um ON u.id = um.user_id\n"
                f"JOIN dwh_internal.mission m ON um.mission_id = m.id\n"
                f"JOIN dwh_internal.scope s ON m.scope_id = s.id\n"
                f"WHERE {where_clause}\n"
                f"ORDER BY {order_clause}{limit_clause}"
            )

        if frame.department_code:
            dept_codes = self.catalog.get_associated_department_codes(frame.department_code) if hasattr(self.catalog, "get_associated_department_codes") else [frame.department_code]
            if len(dept_codes) > 1:
                in_list = ", ".join(f"'{c}'" for c in dept_codes)
                dept_clause = f"AND f.department_code IN ({in_list})"
            else:
                dept_clause = f"AND f.department_code = '{dept_codes[0]}'"
        else:
            dept_clause = ""
        metric_name = frame.canonical_metric_names[0] if frame.canonical_metric_names else ""
        if hasattr(self.catalog, "strip_query_noise"):
            metric_name = self.catalog.strip_query_noise(metric_name, "METRIC_PREFIX_NOISE")
        metric_escaped = metric_name.replace("'", "''")

        # 0. DIMENSION_LISTING: Liệt kê danh mục chỉ tiêu theo chuỗi thời gian, đơn vị hoặc kiểm kê hệ thống
        if frame.intent == CanonicalIntentEnum.DIMENSION_LISTING and frame.target_table != "criteria":
            temporal_clause = ""
            if frame.month_filter is not None:
                temporal_clause = f"  AND EXTRACT(MONTH FROM f.report_date) = {frame.month_filter}\n"
                if frame.year_code:
                    temporal_clause += f"  AND f.year_code = '{frame.year_code}'\n"
            elif frame.date_from is not None:
                temporal_clause = f"  AND f.report_date >= '{frame.date_from}'\n"
                if frame.date_to:
                    temporal_clause += f"  AND f.report_date::date <= '{frame.date_to}'\n"
                if frame.year_code:
                    temporal_clause += f"  AND f.year_code = '{frame.year_code}'\n"
            elif frame.specific_date is not None:
                temporal_clause = f"  AND f.report_date::date <= '{frame.specific_date}'::date\n"
                if frame.year_code:
                    temporal_clause += f"  AND f.year_code = '{frame.year_code}'\n"
            elif frame.year_code:
                temporal_clause = f"  AND f.year_code = '{frame.year_code}'\n"

            if frame.aggregation_function == "COUNT":
                return (
                    f"SELECT COUNT(DISTINCT f.name) AS tong_so_chi_tieu, COUNT(f.fact_sk) AS tong_ban_ghi\n"
                    f"FROM dwh_internal.fact_report_criteria f\n"
                    f"WHERE f.tenant_code = '{frame.tenant_code}'\n"
                    f"  AND f.report_status = 'approved'\n"
                    f"{temporal_clause};\n"
                ).strip()

            office_filter_clause = ""
            if frame.target_office:
                off_esc = frame.target_office.replace("'", "''")
                office_filter_clause = (
                    f"  AND (\n"
                    f"      f.office_id IN (SELECT id FROM dwh_internal.office WHERE office_name ILIKE '%{off_esc}%')\n"
                    f"      OR f.mission_name IN (\n"
                    f"          SELECT m.mission_name FROM dwh_internal.office_mission om\n"
                    f"          JOIN dwh_internal.office o ON om.office_id = o.id\n"
                    f"          JOIN dwh_internal.mission m ON om.mission_id = m.id\n"
                    f"          WHERE o.office_name ILIKE '%{off_esc}%' AND om.deleted_date IS NULL\n"
                    f"      )\n"
                    f"  )\n"
                )

            mission_filter_clause = ""
            if frame.target_mission:
                raw_mis = frame.target_mission.replace("__NOT_FOUND__:", "")
                mis_esc = raw_mis.replace("'", "''")
                mission_filter_clause = f"  AND f.mission_name ILIKE '%{mis_esc}%'\n"

            if frame.department_code:
                dept_codes_dl = self.catalog.get_associated_department_codes(frame.department_code) if hasattr(self.catalog, "get_associated_department_codes") else [frame.department_code]
                if len(dept_codes_dl) > 1:
                    in_list_dl = ", ".join(f"'{c}'" for c in dept_codes_dl)
                    dept_clause_dl = f"  AND f.department_code IN ({in_list_dl})\n"
                else:
                    dept_clause_dl = f"  AND f.department_code = '{dept_codes_dl[0]}'\n"
            else:
                dept_clause_dl = ""

            return (
                f"WITH ranked_facts AS (\n"
                f"    SELECT f.criteria_id,\n"
                f"           f.parent_criteria_id,\n"
                f"           f.name AS ten_chi_tieu,\n"
                f"           f.value AS gia_tri_moi_nhat,\n"
                f"           f.report_date AS ngay_bao_cao_moi_nhat,\n"
                f"           f.mission_name AS ten_nhiem_vu,\n"
                f"           f.office_id,\n"
                f"           f.department_code,\n"
                f"           ROW_NUMBER() OVER (\n"
                f"               PARTITION BY f.criteria_id, f.office_id\n"
                f"               ORDER BY f.report_date DESC NULLS LAST, f.version DESC NULLS LAST\n"
                f"           ) AS rn\n"
                f"    FROM dwh_internal.fact_report_criteria f\n"
                f"    WHERE f.tenant_code = '{frame.tenant_code}'\n"
                f"      AND f.report_status = 'approved'\n"
                f"{temporal_clause}"
                f"{office_filter_clause}"
                f"{mission_filter_clause}"
                f"{dept_clause_dl}"
                f")\n"
                f"SELECT rf.criteria_id,\n"
                f"       rf.parent_criteria_id,\n"
                f"       rf.ten_chi_tieu,\n"
                f"       COALESCE(p.name, 'Chỉ tiêu chung') AS nhom_chi_tieu,\n"
                f"       rf.gia_tri_moi_nhat,\n"
                f"       rf.ngay_bao_cao_moi_nhat,\n"
                f"       rf.ten_nhiem_vu,\n"
                f"       COALESCE(o.office_name, 'Cấp tỉnh') AS ten_van_phong,\n"
                f"       d.department_name AS ten_co_quan\n"
                f"FROM ranked_facts rf\n"
                f"LEFT JOIN dwh_internal.criteria p ON rf.parent_criteria_id = p.id\n"
                f"LEFT JOIN dwh_internal.office o ON rf.office_id = o.id\n"
                f"LEFT JOIN (SELECT DISTINCT department_code, department_name FROM dwh_internal.\"user\") d ON rf.department_code = d.department_code\n"
                f"WHERE rf.rn = 1\n"
                f"ORDER BY rf.ngay_bao_cao_moi_nhat DESC NULLS LAST, TRIM(LOWER(rf.ten_chi_tieu)) ASC, TRIM(LOWER(COALESCE(p.name, ''))) ASC{limit_clause}"
            )

        # 1. METRIC_POINT_INQUIRY (Tra cứu chỉ tiêu điểm / P-04 Single Metric Snapshot)
        if frame.intent == CanonicalIntentEnum.METRIC_POINT_INQUIRY:
            is_multi_branch = len(frame.canonical_metric_ids) > 1
            cand_id = frame.canonical_metric_ids[0] if frame.canonical_metric_ids else None
            cand_id_esc = cand_id.replace("'", "''") if cand_id else None

            is_dup_name = False
            if metric_name and hasattr(self, "catalog") and getattr(self.catalog, "conn", None):
                try:
                    cnt_row = self.catalog.conn.execute(
                        "SELECT COUNT(*) FROM catalog_criteria_hierarchy WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))",
                        [metric_name],
                    ).fetchone()
                    is_dup_name = bool(cnt_row and cnt_row[0] > 1)
                except Exception:
                    is_dup_name = False

            if (is_dup_name and not is_multi_branch and cand_id_esc) or cand_id_esc in ("lang_nghe_truyen_thong", "san_xuat_muoi"):
                cand_cond = f"f.code = '{cand_id_esc}'"
            elif metric_name and cand_id_esc and not is_dup_name:
                cand_cond = f"(TRIM(f.name) ILIKE '{metric_escaped}' OR f.code = '{cand_id_esc}')"
            elif metric_name:
                cand_cond = f"TRIM(f.name) ILIKE '{metric_escaped}'"
            elif cand_id_esc:
                cand_cond = f"f.code = '{cand_id_esc}'"
            else:
                cand_cond = "1=1"

            where_lines = [
                f"    WHERE f.tenant_code = '{frame.tenant_code}'",
                f"      AND f.year_code = '{frame.year_code}'",
                f"      AND f.report_status = 'approved'",
            ]
            if dept_clause:
                where_lines.append(f"      {dept_clause}")
            if frame.target_mission:
                where_lines.append(f"      AND f.mission_name ILIKE '%{frame.target_mission}%'")
            if frame.date_from is not None:
                where_lines.append(f"      AND f.report_date >= '{frame.date_from}'")
                if frame.date_to:
                    where_lines.append(f"      AND f.report_date::date <= '{frame.date_to}'")
            elif frame.month_filter is not None:
                where_lines.append(f"      AND EXTRACT(MONTH FROM f.report_date) = {frame.month_filter}")
            where_lines.append(f"      AND {cand_cond}")
            where_block = "\n".join(where_lines)

            office_filter = (
                f"\n  AND (o.office_name ILIKE '%{frame.target_office}%' OR lf.office_id IN (SELECT id FROM dwh_internal.office WHERE office_name ILIKE '%{frame.target_office}%'))"
                if frame.target_office else ""
            )

            if frame.specific_date:
                spec_d = frame.specific_date.replace("'", "''")
                rn_order = (
                    f"ORDER BY ABS(f.report_date::date - '{spec_d}'::date) ASC, "
                    f"f.report_date DESC NULLS LAST, f.version DESC NULLS LAST"
                )
                outer_order = (
                    f"ORDER BY ABS(lf.ngay_bao_cao_moi_nhat::date - '{spec_d}'::date) ASC, "
                    f"lf.ngay_bao_cao_moi_nhat DESC NULLS LAST"
                )
                return (
                    f"WITH ranked_facts AS (\n"
                    f"    SELECT\n"
                    f"        f.criteria_id,\n"
                    f"        f.parent_criteria_id,\n"
                    f"        f.name AS ten_chi_tieu,\n"
                    f"        f.value AS gia_tri_moi_nhat,\n"
                    f"        f.mission_name AS ten_nhiem_vu,\n"
                    f"        f.office_id,\n"
                    f"        f.report_date AS ngay_bao_cao_moi_nhat,\n"
                    f"        ABS(f.report_date::date - '{spec_d}'::date) AS do_lech_ngay,\n"
                    f"        MAX(CASE WHEN f.report_date::date <= '{spec_d}'::date THEN f.report_date END) OVER (\n"
                    f"            PARTITION BY f.criteria_id, f.office_id\n"
                    f"        ) AS can_duoi_ngay,\n"
                    f"        MIN(CASE WHEN f.report_date::date >= '{spec_d}'::date THEN f.report_date END) OVER (\n"
                    f"            PARTITION BY f.criteria_id, f.office_id\n"
                    f"        ) AS can_tren_ngay,\n"
                    f"        ROW_NUMBER() OVER (\n"
                    f"            PARTITION BY f.criteria_id, f.office_id\n"
                    f"            {rn_order}\n"
                    f"        ) AS rn\n"
                    f"    FROM dwh_internal.fact_report_criteria AS f\n"
                    f"{where_block}\n"
                    f")\n"
                    f"SELECT\n"
                    f"    lf.criteria_id,\n"
                    f"    lf.ten_chi_tieu,\n"
                    f"    lf.gia_tri_moi_nhat,\n"
                    f"    lf.ten_nhiem_vu,\n"
                    f"    COALESCE(o.office_name, 'Cấp tỉnh') AS ten_van_phong,\n"
                    f"    lf.ngay_bao_cao_moi_nhat,\n"
                    f"    lf.do_lech_ngay,\n"
                    f"    lf.can_duoi_ngay,\n"
                    f"    lf.can_tren_ngay,\n"
                    f"    p.name AS nhom_chi_tieu\n"
                    f"FROM ranked_facts AS lf\n"
                    f"LEFT JOIN dwh_internal.office AS o ON lf.office_id = o.id\n"
                    f"LEFT JOIN dwh_internal.criteria AS p ON lf.parent_criteria_id = p.id\n"
                    f"WHERE lf.rn = 1{office_filter}\n"
                    f"{outer_order}{limit_clause}"
                )
            else:
                rn_order = "ORDER BY f.report_date DESC NULLS LAST, f.version DESC NULLS LAST"
                outer_order = "ORDER BY lf.ngay_bao_cao_moi_nhat DESC NULLS LAST"

                return (
                    f"WITH ranked_facts AS (\n"
                    f"    SELECT\n"
                    f"        f.criteria_id,\n"
                    f"        f.parent_criteria_id,\n"
                    f"        f.name AS ten_chi_tieu,\n"
                    f"        f.value AS gia_tri_moi_nhat,\n"
                    f"        f.mission_name AS ten_nhiem_vu,\n"
                    f"        f.office_id,\n"
                    f"        f.report_date AS ngay_bao_cao_moi_nhat,\n"
                    f"        ROW_NUMBER() OVER (\n"
                    f"            PARTITION BY f.criteria_id, f.office_id\n"
                    f"            {rn_order}\n"
                    f"        ) AS rn\n"
                    f"    FROM dwh_internal.fact_report_criteria AS f\n"
                    f"{where_block}\n"
                    f")\n"
                    f"SELECT\n"
                    f"    lf.criteria_id,\n"
                    f"    lf.ten_chi_tieu,\n"
                    f"    lf.gia_tri_moi_nhat,\n"
                    f"    lf.ten_nhiem_vu,\n"
                    f"    COALESCE(o.office_name, 'Cấp tỉnh') AS ten_van_phong,\n"
                    f"    lf.ngay_bao_cao_moi_nhat,\n"
                    f"    p.name AS nhom_chi_tieu\n"
                    f"FROM ranked_facts AS lf\n"
                    f"LEFT JOIN dwh_internal.office AS o ON lf.office_id = o.id\n"
                    f"LEFT JOIN dwh_internal.criteria AS p ON lf.parent_criteria_id = p.id\n"
                    f"WHERE lf.rn = 1{office_filter}\n"
                    f"{outer_order}{limit_clause}"
                )

        # 2. METRIC_TOP_K (Xếp hạng Top-5, DENSE_RANK)
        if frame.intent == CanonicalIntentEnum.METRIC_TOP_K:
            target_metric = frame.canonical_metric_names[0] if frame.canonical_metric_names else (
                frame.raw_metric_mentions[0] if frame.raw_metric_mentions else ""
            )
            topic_filter = target_metric.replace("'", "''") if target_metric else ""

            filter_clause = ""
            if topic_filter:
                filter_clause = (
                    f"      AND (\n"
                    f"          f.criteria_id IN (\n"
                    f"              SELECT id FROM dwh_internal.criteria\n"
                    f"              WHERE parent_id IN (SELECT id FROM dwh_internal.criteria WHERE name ILIKE '%{topic_filter}%')\n"
                    f"          )\n"
                    f"          OR f.name ILIKE '%{topic_filter}%'\n"
                    f"      )\n"
                )
            top_k_limit = f"\nLIMIT {frame.limit};" if frame.limit else "\nLIMIT 5;"

            return (
                f"WITH latest_fact AS (\n"
                f"    SELECT f.name, f.value, f.office_id,\n"
                f"           ROW_NUMBER() OVER (PARTITION BY TRIM(LOWER(f.name)), COALESCE(f.office_id, '00000000-0000-0000-0000-000000000000'::uuid) ORDER BY f.report_date DESC, f.version DESC) as rn\n"
                f"    FROM dwh_internal.fact_report_criteria f\n"
                f"    WHERE f.tenant_code = '{frame.tenant_code}'\n"
                f"      AND f.year_code = '{frame.year_code}'\n"
                f"      AND f.report_status = 'approved'\n"
                f"{filter_clause}"
                f"      AND NULLIF(TRIM(f.value), '') IS NOT NULL\n"
                f"      AND TRIM(f.value) != '-'\n"
                f")\n"
                f"SELECT name AS ten_chi_tieu, (CASE WHEN TRIM(value) ~ '^-?[0-9]+(\\.[0-9]+)?$' THEN TRIM(value)::numeric ELSE NULL END) AS tong_gia_tri,\n"
                f"       DENSE_RANK() OVER (ORDER BY (CASE WHEN TRIM(value) ~ '^-?[0-9]+(\\.[0-9]+)?$' THEN TRIM(value)::numeric ELSE NULL END) DESC NULLS LAST) AS xep_hang\n"
                f"FROM latest_fact\n"
                f"WHERE rn = 1\n"
                f"ORDER BY tong_gia_tri DESC NULLS LAST{top_k_limit}"
            )

        # 3. METRIC_GROWTH_YOY (So sánh tăng trưởng doanh thu giữa 2 đợt / 2 kỳ)
        if frame.intent == CanonicalIntentEnum.METRIC_GROWTH_YOY:
            target_metric = frame.canonical_metric_names[0] if frame.canonical_metric_names else (
                frame.raw_metric_mentions[0] if frame.raw_metric_mentions else ""
            )
            metric_cond = ""
            if target_metric:
                m_clean = target_metric.replace("'", "''")
                metric_cond = f"      AND name ILIKE '%{m_clean}%'\n"


            periods = frame.time_series_periods
            y_frame = int(frame.year_code or "2026")
            effective_m = self._get_effective_end_month(y_frame)
            m_prev = max(1, effective_m - 3)
            p1_default = f"{y_frame}-{m_prev:02d}-{calendar.monthrange(y_frame, m_prev)[1]:02d}"
            p2_default = f"{y_frame}-{effective_m:02d}-{calendar.monthrange(y_frame, effective_m)[1]:02d}"
            p1 = periods[0] if len(periods) > 0 else p1_default
            p2 = periods[1] if len(periods) > 1 else p2_default

            return (
                f"WITH rev AS (\n"
                f"    SELECT report_date, (CASE WHEN TRIM(value) ~ '^-?[0-9]+(\\.[0-9]+)?$' THEN TRIM(value)::numeric ELSE NULL END) as val\n"
                f"    FROM dwh_internal.fact_report_criteria\n"
                f"    WHERE tenant_code = '{frame.tenant_code}' AND year_code = '{frame.year_code}' AND report_status = 'approved'\n"
                f"{metric_cond}"
                f")\n"
                f"SELECT q2.val AS doanh_thu_q2, q3.val AS doanh_thu_q3,\n"
                f"       ROUND(((q3.val - q2.val) / NULLIF(q2.val, 0)) * 100.0, 2) AS toc_do_tang_truong_percent\n"
                f"FROM (SELECT val FROM rev WHERE report_date::text LIKE '%{p1}%' ORDER BY report_date DESC LIMIT 1) q2\n"
                f"CROSS JOIN (SELECT val FROM rev WHERE report_date::text LIKE '%{p2}%' ORDER BY report_date DESC LIMIT 1) q3;"
            )

        # 4. OFFICER_ASSIGNMENT (Tra cứu cán bộ phân công nhiệm vụ)
        if frame.intent == CanonicalIntentEnum.OFFICER_ASSIGNMENT:
            mis_filter = ""
            if frame.raw_metric_mentions:
                mis_name = frame.raw_metric_mentions[0].replace("'", "''")
                mis_filter = f"  AND um.mission_name ILIKE '%{mis_name}%'\n"
            return (
                f"SELECT u.name, u.position, um.office_name, um.mission_name\n"
                f"FROM dwh_internal.user_mission AS um\n"
                f"JOIN dwh_internal.\"user\" AS u ON um.user_id = u.id\n"
                f"WHERE um.tenant_code = '{frame.tenant_code}'\n"
                f"{mis_filter}".rstrip("\n") + f"{limit_clause}"
            )

        # 5. METADATA_EXPLORATION & DIMENSION_LISTING
        if frame.target_table == "province":
            exclude_clauses = ""
            if frame.exclude_entities:
                for ent in frame.exclude_entities:
                    ent_clean = ent.replace("'", "''").strip()
                    exclude_clauses += f"  AND p.name NOT ILIKE '%{ent_clean}%'\n"
            return (
                f"SELECT p.code, p.name, p.is_activated\n"
                f"FROM dwh_internal.province AS p\n"
                f"WHERE p.is_activated = true\n"
                f"{exclude_clauses}"
                f"ORDER BY p.name ASC{limit_clause}"
            )

        if frame.target_table == "criteria" and frame.intent in (CanonicalIntentEnum.METADATA_EXPLORATION, CanonicalIntentEnum.DIMENSION_LISTING):
            kw_clause = ""
            if frame.search_keyword:
                kw_clean = frame.search_keyword.replace("'", "''").strip()
                kw_clause = f"  AND c.name ILIKE '%{kw_clean}%'\n"
            return (
                f"SELECT c.code, c.name, c.level\n"
                f"FROM dwh_internal.criteria AS c\n"
                f"WHERE c.deleted_date IS NULL\n"
                f"{kw_clause}"
                f"ORDER BY c.level ASC, c.code ASC{limit_clause}"
            )

        if frame.target_table == "deparment":
            return (
                f"SELECT d.code, d.name, d.level, d.tenant_code\n"
                f"FROM dwh_internal.deparment AS d\n"
                f"WHERE d.is_activated = true\n"
                f"ORDER BY d.code ASC{limit_clause}"
            )

        if frame.target_table == "office":
            return (
                f"SELECT o.code, o.name, o.department_code\n"
                f"FROM dwh_internal.office AS o\n"
                f"WHERE o.is_activated = true\n"
                f"ORDER BY o.code ASC{limit_clause}"
            )

        if frame.target_table == "collection_form":
            return (
                f"SELECT cf.code, cf.name, cf.department_code, cf.status\n"
                f"FROM dwh_internal.collection_form AS cf\n"
                f"WHERE cf.year_code = '{frame.year_code}'{limit_clause}"
            )
        if frame.target_table == "mission":
            y_mis = frame.year_code or "2026"
            t_code = frame.tenant_code or "68"
            scope_filter = ""
            if frame.target_scope:
                sc_esc = frame.target_scope.replace("'", "''")
                scope_filter = f"  AND s.scope_name ILIKE '%{sc_esc}%'\n"
            mission_time_filter = ""
            if frame.month_filter is not None:
                mission_time_filter = (
                    f"  AND EXISTS (\n"
                    f"      SELECT 1 FROM dwh_internal.fact_report_criteria f\n"
                    f"      WHERE f.tenant_code = '{t_code}'\n"
                    f"        AND f.year_code = '{y_mis}'\n"
                    f"        AND f.report_status = 'approved'\n"
                    f"        AND (f.mission_id = m.id OR TRIM(LOWER(f.mission_name)) = TRIM(LOWER(m.mission_name)))\n"
                    f"        AND EXTRACT(MONTH FROM f.report_date) = {frame.month_filter}\n"
                    f"  )\n"
                )
            elif frame.specific_date is not None:
                mission_time_filter = (
                    f"  AND EXISTS (\n"
                    f"      SELECT 1 FROM dwh_internal.fact_report_criteria f\n"
                    f"      WHERE f.tenant_code = '{t_code}'\n"
                    f"        AND f.year_code = '{y_mis}'\n"
                    f"        AND f.report_status = 'approved'\n"
                    f"        AND (f.mission_id = m.id OR TRIM(LOWER(f.mission_name)) = TRIM(LOWER(m.mission_name)))\n"
                    f"        AND f.report_date::date <= '{frame.specific_date}'::date\n"
                    f"  )\n"
                )
            elif frame.date_from is not None:
                date_to_cond = f" AND f.report_date::date <= '{frame.date_to}'::date" if frame.date_to else ""
                mission_time_filter = (
                    f"  AND EXISTS (\n"
                    f"      SELECT 1 FROM dwh_internal.fact_report_criteria f\n"
                    f"      WHERE f.tenant_code = '{t_code}'\n"
                    f"        AND f.year_code = '{y_mis}'\n"
                    f"        AND f.report_status = 'approved'\n"
                    f"        AND (f.mission_id = m.id OR TRIM(LOWER(f.mission_name)) = TRIM(LOWER(m.mission_name)))\n"
                    f"        AND f.report_date::date >= '{frame.date_from}'::date{date_to_cond}\n"
                    f"  )\n"
                )
            return (
                f"SELECT m.mission_code, m.mission_name, m.mission_status, m.department_code,\n"
                f"       COALESCE(s.scope_name, 'Chưa phân loại') AS linh_vuc,\n"
                f"       COALESCE(\n"
                f"           (\n"
                f"               SELECT o_f.office_name\n"
                f"               FROM dwh_internal.fact_report_criteria f_off\n"
                f"               JOIN dwh_internal.office o_f ON o_f.id = f_off.office_id\n"
                f"               WHERE f_off.tenant_code = '{t_code}'\n"
                f"                 AND f_off.report_status = 'approved'\n"
                f"                 AND (f_off.mission_id = m.id OR TRIM(LOWER(f_off.mission_name)) = TRIM(LOWER(m.mission_name)))\n"
                f"               ORDER BY f_off.report_date DESC NULLS LAST, f_off.version DESC NULLS LAST\n"
                f"               LIMIT 1\n"
                f"           ),\n"
                f"           (\n"
                f"               SELECT o_m.office_name\n"
                f"               FROM dwh_internal.office_mission om\n"
                f"               JOIN dwh_internal.office o_m ON o_m.id = om.office_id\n"
                f"               WHERE om.mission_id = m.id\n"
                f"                 AND om.deleted_date IS NULL\n"
                f"                 AND om.department_code = m.department_code\n"
                f"               ORDER BY om.created_date DESC NULLS LAST\n"
                f"               LIMIT 1\n"
                f"           ),\n"
                f"           '-'\n"
                f"       ) AS don_vi_phu_trach\n"
                f"FROM dwh_internal.mission AS m\n"
                f"LEFT JOIN dwh_internal.scope AS s ON m.scope_id = s.id\n"
                f"WHERE m.year_code = '{y_mis}' AND m.mission_status = true AND m.deleted_date IS NULL\n"
                f"{scope_filter}"
                f"{mission_time_filter}"
                f"ORDER BY m.mission_name ASC{limit_clause}"
            )

        # 6. REPORT_STATUS_AUDIT
        if frame.target_table == "report":
            return (
                f"SELECT r.report_date, r.status, r.department_code\n"
                f"FROM dwh_internal.report AS r\n"
                f"WHERE r.tenant_code = '{frame.tenant_code}' AND r.year_code = '{frame.year_code}'{limit_clause}"
            )

        # Fallback
        return (
            f"SELECT f.name AS ten_chi_tieu, SUM(CASE WHEN TRIM(f.value) ~ '^-?[0-9]+(\\.[0-9]+)?$' THEN TRIM(f.value)::numeric ELSE NULL END) AS tong_gia_tri\n"
            f"FROM dwh_internal.fact_report_criteria f\n"
            f"WHERE f.tenant_code = '{frame.tenant_code}' AND f.year_code = '{frame.year_code}' AND f.report_status = 'approved'\n"
            f"GROUP BY f.name{limit_clause}"
        )
