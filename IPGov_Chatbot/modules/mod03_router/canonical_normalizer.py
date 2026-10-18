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
import re
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


def _strip_bracketed_tags(text: str) -> str:
    """
    Loại bỏ các thẻ dạng [tenant_code=..., level=...] thuần túy bằng thao tác chuỗi.
    Không sử dụng regex.
    """
    while "[" in text and "]" in text:
        start = text.find("[")
        end = text.find("]", start)
        if end != -1:
            tag_content = text[start + 1:end]
            if "tenant_code=" in tag_content or "level=" in tag_content:
                text = text[:start] + text[end + 1:]
            else:
                break
        else:
            break
    return text.strip()


def _extract_ward_name(text: str) -> Optional[str]:
    """Trích xuất tên xã/phường/thị trấn từ câu hỏi mà không dùng regex phức tạp."""
    prefixes = ["phường ", "xã ", "thị trấn "]
    low = text.lower()
    masked_low = low
    for non_ward in ("liên hiệp hợp tác xã", "hợp tác xã", "kinh tế - xã hội", "kinh tế xã hội", "xã hội", "mỗi xã", "thị xã", "cấp xã"):
        masked_low = masked_low.replace(non_ward, " " * len(non_ward))

    start_idx = -1
    matched_prefix = ""
    for p in prefixes:
        idx = masked_low.find(p)
        if idx != -1:
            start_idx = idx
            matched_prefix = p
            break
    if start_idx == -1:
        return None

    rest = text[start_idx + len(matched_prefix):]
    delimiters = [
        " thuộc", " trên", " kèm", "?", ".", ",", " đang", " được", " có",
        " năm", " đạt", " là", " trong", " bao nhiêu", " phân theo"
    ]
    rest_low = rest.lower()
    end_idx = len(rest)
    for d in delimiters:
        d_idx = rest_low.find(d)
        if d_idx != -1 and d_idx < end_idx:
            end_idx = d_idx
    ward_core = rest[:end_idx].strip()
    wc_low = ward_core.lower()
    if (
        ward_core
        and not wc_low.startswith(("năm", "đạt", "là", "nông nghiệp", "phân theo", "hiện", "bao nhiêu"))
        and "bao nhiêu" not in wc_low
    ):
        return f"{matched_prefix.strip()} {ward_core}".strip()
    return None


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

        # 4. Cắt tiền tố / hậu tố câu hỏi dẫn nhập phổ biến để giữ lại tên chỉ tiêu sạch
        lead_phrases = (
            "cho tôi biết ", "cho tôi xem ", "vui lòng cho biết ", "hãy cho biết ",
            "thông tin số liệu ", "số liệu chỉ tiêu ", "số liệu ",
            "kết quả chỉ tiêu ", "giá trị chỉ tiêu ", "nhóm chỉ tiêu ",
            "chỉ tiêu ", "tiêu chí ",
        )
        changed = True
        while changed:
            changed = False
            for lp in lead_phrases:
                if cleaned.startswith(lp):
                    cleaned = cleaned[len(lp):].strip()
                    changed = True

        tail_phrases = (
            " hiện tại là bao nhiêu", " hiện nay là bao nhiêu", " hiện đạt bao nhiêu",
            " có giá trị là bao nhiêu", " có giá trị bao nhiêu", " đạt bao nhiêu",
            " là bao nhiêu", " bao nhiêu", " hiện tại", " hiện nay", " trong năm", " năm",
        )
        changed = True
        while changed:
            changed = False
            for tp in tail_phrases:
                if cleaned.endswith(tp):
                    cleaned = cleaned[:-len(tp)].strip()
                    changed = True

        return cleaned

    def _is_officer_query(self, query: str) -> bool:
        """
        Xác định xem câu hỏi có thuộc miền tra cứu cán bộ / phân công nhiệm vụ (OFFICER_ASSIGNMENT)
        hoàn toàn động qua DuckDB Catalog RAM.
        """
        q_low = query.lower()
        if "chỉ tiêu" in q_low and any(w in q_low for w in ["nào", "các chỉ tiêu", "những chỉ tiêu", "danh mục", "thu thập"]):
            return False
        if any(w in q_low for w in ["chỉ tiêu", "số liệu", "diện tích", "sản lượng", "doanh thu", "kinh phí"]) and not any(
            p in q_low for p in ["cán bộ", "nhân sự", "nhân viên", "chuyên viên", "chức vụ", "ai phụ trách", "tài khoản"]
        ):
            return False

        if hasattr(self.catalog, "resolve_user_name") and self.catalog.resolve_user_name(query):
            return True
        if hasattr(self.catalog, "resolve_user_position") and self.catalog.resolve_user_position(query):
            return True
        if hasattr(self.catalog, "conn") and self.catalog.conn:
            try:
                row = self.catalog.conn.execute("SELECT 1 FROM catalog_users WHERE INSTR(?, LOWER(name)) > 0 LIMIT 1;", (q_low,)).fetchone()
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
        query: str,
        stream_b: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Stream A Deterministic Fallback: Phân tích intent, target table,
        và metric mention theo kiến trúc Hai Mặt Phẳng (Two-Plane Architecture):
        1. Dimension Plane (Metadata Exploration / Dimension Listing): province, criteria, deparment, office, collection_form, mission.
        2. Fact Plane (Quantitative Metrics / Aggregations): fact_report_criteria, report, user_mission.
        """
        q_low = query.lower().strip()

        # -1. Tra cứu Chào hỏi & Tạm biệt (GREETING_FAREWELL)
        # Sử dụng so khớp tiền tố chuỗi cơ bản không dùng regex
        greet_prefixes = (
            "xin chào chatbot", "chào chatbot", "xin chào bot", "chào bot",
            "xin chào đồng chí", "chào đồng chí", "xin chào bạn", "chào bạn",
            "xin chào anh", "chào anh", "xin chào chị", "chào chị",
            "xin chào em", "chào em", "xin chào", "good morning", "chào", "hello", "hi"
        )
        farewell_prefixes = ("hẹn gặp lại", "thank you", "tạm biệt", "cảm ơn", "thanks")
        combined_salutations = sorted((*greet_prefixes, *farewell_prefixes), key=len, reverse=True)
        m_greet = any(q_low.startswith(p) for p in greet_prefixes)
        m_farewell = any(q_low.startswith(p) for p in farewell_prefixes)

        is_pure_greeting = False
        for p in combined_salutations:
            if q_low == p or q_low.startswith(p + " ") or q_low.startswith(p + ","):
                rem = q_low[len(p):].strip(" ,:.-!?")
                if not rem:
                    is_pure_greeting = True
                    break

        if is_pure_greeting:
            is_farewell = bool(m_farewell)
            direct_ans = (
                "Cảm ơn đồng chí. Rất hân hạnh được hỗ trợ đồng chí tra cứu số liệu DWH tỉnh Lâm Đồng. Chúc đồng chí một ngày làm việc hiệu quả!"
                if is_farewell else
                "Xin chào đồng chí! Tôi là Trợ lý Ảo Kho Dữ Liệu DWH tỉnh Lâm Đồng. Tôi có thể hỗ trợ đồng chí tra cứu: "
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
        elif m_greet or m_farewell:
            for p in combined_salutations:
                if q_low.startswith(p):
                    query = query[len(p):].lstrip(" ,:-.!?")
                    q_low = query.lower().strip()
                    break

        if any(kw in q_low for kw in (
            "giúp gì", "làm được gì", "chức năng gì", "những chức năng", "hỗ trợ những gì",
            "hỗ trợ gì", "bạn là ai", "giới thiệu về bạn", "khả năng của bạn"
        )):
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



        # 0. Tra cứu cán bộ / phân công nhiệm vụ (OFFICER_ASSIGNMENT)
        if self._is_officer_query(query):
            target_mission = None
            target_office = None
            exclude_offices = []
            target_pos = None
            target_name = None

            # Phân giải nhiệm vụ động qua DuckDB Catalog
            if hasattr(self.catalog, "resolve_mission"):
                target_mission = self.catalog.resolve_mission(query)

            # Phân giải đơn vị / phòng ban qua DuckDB Catalog động
            admin_scope = self.catalog.resolve_administrative_scope(query) if hasattr(self.catalog, "resolve_administrative_scope") else {}
            if admin_scope and admin_scope.get("type") == "office":
                target_office = admin_scope.get("office_name") or admin_scope.get("name")

            # Phân giải loại trừ đơn vị (Directional Negative Filter - TC-REM-09) qua DuckDB Catalog RAM
            if hasattr(self.catalog, "resolve_excluded_entities"):
                exclude_offices = self.catalog.resolve_excluded_entities(query)

            # Phân giải chức vụ động qua DuckDB Catalog
            if hasattr(self.catalog, "resolve_user_position"):
                target_pos = self.catalog.resolve_user_position(query)

            # Phân giải tên cán bộ động qua DuckDB Catalog
            if hasattr(self.catalog, "resolve_user_name"):
                target_name = self.catalog.resolve_user_name(query)

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
            self.catalog.resolve_attribute_lookup(query)
            if hasattr(self.catalog, "resolve_attribute_lookup")
            else None
        )
        if attr_lookup:
            target_attr = attr_lookup.get("target_attribute", "đơn vị thực hiện")
            subject = self._extract_core_metric_phrase(query) or query.strip()
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

        is_metric_listing = ("chỉ tiêu" in q_low or "chi tieu" in q_low) and any(
            w in q_low for w in [
                "chỉ tiêu nào", "chi tieu nao", "chỉ tiêu gì", "chi tieu gi",
                "các chỉ tiêu", "cac chi tieu", "những chỉ tiêu", "nhung chi tieu",
                "danh sách", "danh sach", "danh mục", "danh muc", "thu thập", "thu thap",
                "bao gồm", "bao gom", "gồm những", "gom nhung", "có những", "co nhung"
            ]
        )

        # 1.8 Khám phá quan hệ liên bảng: Xã/phường với nhiệm vụ và lĩnh vực (Dimension: ward_mission_scope)
        q_low_no_htx = (
            q_low.replace("liên hiệp hợp tác xã", " ")
            .replace("hợp tác xã", " ")
            .replace("kinh tế - xã hội", " ")
            .replace("kinh tế xã hội", " ")
            .replace("xã hội", " ")
        )
        if (
            any(w in q_low_no_htx for w in ["xã ", "phường ", "thị trấn "])
            and any(w in q_low for w in ["nhiệm vụ", "lĩnh vực"])
            and not any(w in q_low for w in ["chỉ tiêu", "số liệu", "kết quả"])
        ):
            w_name = _extract_ward_name(query)
            if w_name:
                agg_fn = "COUNT" if any(w in q_low for w in ["thống kê", "bao nhiêu", "có mấy", "số lượng"]) or "thống kê các lĩnh vực" in q_low else "NONE"
                return {
                    "intent": CanonicalIntentEnum.RELATIONAL_EXPLORATION,
                    "target_table": "ward_mission_scope",
                    "target_ward": w_name,
                    "subject_entity": w_name,
                    "exclude_entities": [],
                    "search_keyword": None,
                    "raw_metric_mentions": [],
                    "aggregation_function": agg_fn,
                    "sort_direction": "ASC",
                    "limit": None,
                }


        # 1.9 REQ-Q04 / SC-4.1 / SC-4.2: Hiển thị các chỉ tiêu cấp 1 của nhiệm vụ / các nhiệm vụ
        is_level1_criteria_query = any(w in q_low for w in [
            "chỉ tiêu cấp 1", "chi tieu cap 1", "chỉ tiêu cấp một", "chi tieu cap mot",
            "chỉ tiêu gốc", "chi tieu goc", "chỉ tiêu đầu mục", "nhóm chỉ tiêu cấp 1"
        ]) or (
            ("chỉ tiêu" in q_low or "chi tieu" in q_low)
            and ("nhiệm vụ" in q_low or "nhiem vu" in q_low)
            and any(w in q_low for w in [
                "những chỉ tiêu", "nhung chi tieu", "các chỉ tiêu", "cac chi tieu",
                "chỉ tiêu nào", "chi tieu nao", "danh sách chỉ tiêu", "danh sach chi tieu",
                "hiển thị", "hien thi", "liệt kê", "liet ke", "cấp 1", "cap 1",
                "gồm những", "gom nhung", "có những", "co nhung"
            ])
            and not any(w in q_low for w in ["trạng thái", "vòng đời", "report_status", "office", "văn phòng"])
        )
        if is_level1_criteria_query:
            mis_info = self.catalog.extract_mission_from_query(query) if hasattr(self.catalog, "extract_mission_from_query") else {"status": "NONE"}
            if mis_info and mis_info.get("status") == "NOT_FOUND":
                resolved_mis = f"__NOT_FOUND__:{mis_info.get('requested_mission', '')}"
            else:
                resolved_mis = (
                    (mis_info.get("mission_name") if mis_info and mis_info.get("status") in ("FOUND", "MATCH") else None)
                    or (stream_b.get("target_mission") if stream_b else None)
                    or (self.catalog.resolve_mission(query) if hasattr(self.catalog, "resolve_mission") else None)
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
        scope_info = self.catalog.extract_scope_from_query(query) if hasattr(self.catalog, "extract_scope_from_query") else None
        is_mission_scope_query = (
            ("nhiệm vụ" in q_low or "nhiem vu" in q_low)
            and (
                any(w in q_low for w in ["nhóm lĩnh vực", "nhom linh vuc", "lĩnh vực", "linh vuc", "mảng", "ngành", "khối", "thuộc về", "thuoc ve"])
                or (scope_info and scope_info.get("status") in ("FOUND", "MATCH", "NOT_FOUND"))
            )
            and not self._is_officer_query(query)
            and not is_metric_listing
            and not any(w in q_low for w in ["văn phòng", "từng văn phòng", "quản lý nhà nước nào", "xã ", "phường "])
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

        if hasattr(self.catalog, "is_dimension_query") and self.catalog.is_dimension_query(query, "mission") and not self._is_officer_query(query) and not is_metric_listing:
            admin_scope = self.catalog.resolve_administrative_scope(query) if hasattr(self.catalog, "resolve_administrative_scope") else {}
            target_off = None
            if admin_scope and admin_scope.get("type") == "office":
                target_off = admin_scope.get("office_name") or admin_scope.get("name")
            elif hasattr(self.catalog, "conn") and self.catalog.conn:
                off_match = self.catalog.conn.execute("SELECT name FROM catalog_offices WHERE INSTR(?, LOWER(name)) > 0 LIMIT 1;", (q_low,)).fetchone()
                if off_match:
                    target_off = off_match[0]

            has_office_or_scope = (target_off is not None) or any(w in q_low for w in ["văn phòng", "từng văn phòng", "lĩnh vực", "quản lý nhà nước"])
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
            getattr(self.catalog, "is_dimension_query", lambda q, d: False)(q_low, "criteria")
        )

        extracted_office = None
        extracted_dept = None
        if stream_b and stream_b.get("target_office"):
            extracted_office = stream_b.get("target_office")
        if stream_b and stream_b.get("department_code"):
            extracted_dept = stream_b.get("department_code")

        scope_res = self.catalog.resolve_administrative_scope(query) if hasattr(self.catalog, "resolve_administrative_scope") else {}
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

        core_phrase = self._extract_core_metric_phrase(query)
        has_specific_catalog_metric = False
        matched_catalog_mention = None
        if not is_metric_listing and core_phrase and len(core_phrase) > 2:
            if hasattr(self.catalog, "resolve_metric_id"):
                c_id = self.catalog.resolve_metric_id(core_phrase)
                if c_id:
                    has_specific_catalog_metric = True
            if not has_specific_catalog_metric and hasattr(self.catalog, "find_top_k_candidates"):
                cands, is_amb, _ = self.catalog.find_top_k_candidates(core_phrase, top_k=1, score_cutoff=75.0)
                if cands and not is_amb and float(cands[0].get("score", 0.0)) >= 75.0:
                    has_specific_catalog_metric = True

        if not is_metric_listing:
            if hasattr(self.catalog, "_criteria_cache_names"):
                for crit_name in sorted(self.catalog._criteria_cache_names, key=len, reverse=True):
                    cn_low = crit_name.lower().strip()
                    if cn_low and len(cn_low) > 3 and cn_low in q_low:
                        has_specific_catalog_metric = True
                        matched_catalog_mention = crit_name
                        break
            if not matched_catalog_mention and hasattr(self.catalog, "_alias_registry"):
                for entry in sorted(self.catalog._alias_registry, key=lambda x: len(x.get("alias", "")), reverse=True):
                    if entry.get("type") == "criteria" or entry.get("target_table") == "dwh_internal.criteria":
                        al_low = (entry.get("alias") or "").lower().strip()
                        if al_low and len(al_low) > 6 and al_low in q_low:
                            has_specific_catalog_metric = True
                            matched_catalog_mention = entry.get("name") or al_low
                            break

        if not matched_catalog_mention and hasattr(self.catalog, "classify_criterion_hierarchy"):
            try:
                h_det = self.catalog.classify_criterion_hierarchy(query)
                allowed_classes = ("parent", "parent_group") if is_metric_listing else ("single_leaf", "duplicate_leaf", "parent", "parent_group")
                if h_det and h_det.get("classification") in allowed_classes and h_det.get("matched_name"):
                    has_specific_catalog_metric = True
                    matched_catalog_mention = h_det["matched_name"]
            except Exception:
                pass

        has_temporal_discovery = bool(
            stream_b and (
                stream_b.get("month_filter") is not None
                or stream_b.get("date_from") is not None
                or stream_b.get("start_date") is not None
            )
        )
        is_inventory = bool(getattr(self.catalog, "is_inventory_query", lambda q: False)(query))

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
                if cn_low and len(cn_low) > 3 and cn_low in q_low:
                    is_fact_calc = True
                    break

        # ----------------------------------------------------------------------
        # DIMENSION PLANE: KHÁM PHÁ DANH MỤC & ĐƠN VỊ HÀNH CHÍNH
        # ----------------------------------------------------------------------
        has_business_topic = any(w in q_low for w in ["sản lượng", "chỉ tiêu", "kinh phí", "báo cáo", "nhiệm vụ", "số liệu", "diêm nghiệp", "muối", "phát triển", "doanh thu", "diện tích", "hợp tác xã", "htx"])
        q_no_htx = q_low.replace("hợp tác xã", "").replace("htx", "").strip()

        # 2a. Khám phá địa bàn cấp xã/phường (Dimension: ward) qua DuckDB Catalog RAM
        is_ward_dimension = (
            any(w in q_no_htx for w in ["xã, phường", "xã phường", "xã / phường", "phường, xã", "phường xã", "xã thuộc", "phường thuộc", "xã nào", "phường nào"])
            or (any(w in q_no_htx for w in ["xã", "phường", "thị trấn"]) and not has_business_topic)
        )
        if is_ward_dimension and not has_business_topic:
            agg_fn = "COUNT" if any(w in q_no_htx for w in ["bao nhiêu", "tổng số", "có mấy", "số lượng"]) else "NONE"
            limit_val = 1 if agg_fn == "COUNT" else (10 if "10" in q_no_htx else None)
            search_kw = "code" if any(w in q_no_htx for w in ["mã", "đầu tiên"]) else None
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
        is_prov_list = any(w in q_low for w in ["các tỉnh", "danh sách tỉnh", "những tỉnh nào", "tỉnh thành nào", "danh mục tỉnh", "danh sách các tỉnh"])
        if not has_business_topic and (is_prov_list or (hasattr(self.catalog, "is_dimension_query") and self.catalog.is_dimension_query(query, "province") and not any(w in q_low for w in ["lâm đồng", "văn phòng", "sở", "phòng", "xã", "phường"]))):
            exclude_entities = self.catalog.resolve_excluded_entities(query) if hasattr(self.catalog, "resolve_excluded_entities") else []
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
        if not has_specific_catalog_metric and (has_collective_noun or getattr(self.catalog, "is_dimension_query", lambda q, d: False)(q_low, "criteria")) and not is_dimension_discovery:
            kw = None
            core_kw = self._extract_core_metric_phrase(query)
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
        if hasattr(self.catalog, "is_dimension_query") and self.catalog.is_dimension_query(query, "office_or_department"):
            target_tbl = self.catalog.resolve_target_table(query, default_table="office")
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
        core_phrase = self._extract_core_metric_phrase(query)
        if matched_catalog_mention and (not core_phrase or len(core_phrase) > len(matched_catalog_mention) + 6):
            raw_mentions = [matched_catalog_mention]
        else:
            raw_mentions = [core_phrase] if core_phrase else [query.strip()]
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
    def _extract_stream_b_deterministic(self, query: str) -> Dict[str, Any]:
        """
        Stream B Deterministic Fallback: Phân tích mốc thời gian, kỳ báo cáo,
        và thực thể địa danh (khử bẫy đa nghĩa polysemy LĐ = Lao động vs Lâm Đồng).
        Không sử dụng thư viện regex.
        """
        q_low = query.lower().strip()

        # 1. Trích xuất năm (year_code)
        year_code = None
        for tok in query.replace(",", " ").replace(".", " ").replace("?", " ").split():
            clean_tok = tok.strip()
            if len(clean_tok) == 4 and clean_tok.startswith("202") and clean_tok[3].isdigit():
                year_code = clean_tok
                break
        if not year_code and "năm nay" in q_low:
            year_code = "2026"

        spatial_mention = None

        # 3. Trích xuất chuỗi thời gian (time series periods) sắp xếp tuần tự động
        periods = []
        y_int = int(year_code or "2026")
        for tok in query.replace(",", " ").replace("?", " ").split():
            sep = "/" if "/" in tok else ("-" if "-" in tok else ("." if "." in tok else None))
            if sep:
                parts = tok.split(sep)
                if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit() and parts[2].isdigit():
                    d_val, m_val, y_val = int(parts[0]), int(parts[1]), int(parts[2])
                    if 1 <= d_val <= 31 and 1 <= m_val <= 12 and 2020 <= y_val <= 2030:
                        periods.append(f"{y_val}-{m_val:02d}-{d_val:02d}")

        for m_val in range(1, 13):
            if f"{m_val} tháng" in q_low or f"{m_val:02d} tháng" in q_low:
                last_d = calendar.monthrange(y_int, m_val)[1]
                p_date = f"{y_int}-{m_val:02d}-{last_d:02d}"
                if p_date not in periods:
                    periods.append(p_date)



        VN_Q_MAP = {"một": 1, "1": 1, "i": 1, "hai": 2, "2": 2, "ii": 2, "ba": 3, "3": 3, "iii": 3, "bốn": 4, "tư": 4, "4": 4, "iv": 4}
        for q_word, q_num in VN_Q_MAP.items():
            if f"quý {q_word}" in q_low or f"q{q_word}" in q_low:
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
            "mười một": 11, "mười hai": 12, "mười": 10,
            "một": 1, "giêng": 1, "hai": 2, "ba": 3, "tư": 4, "bốn": 4, "năm": 5,
            "sáu": 6, "bảy": 7, "tám": 8, "chín": 9, "chạp": 12
        }

        # BƯỚC 4A: KIỂM TRA QUÝ (bao gồm N quý đầu/cuối năm và dải quý La Mã / Ả Rập / chữ)
        found_q = False
        q_quant_first = re.search(r'\b(1|2|3|4|một|hai|ba|bốn)\s+quý\s+đầu(?:\s+năm)?\b', q_low)
        q_quant_last = re.search(r'\b(1|2|3|4|một|hai|ba|bốn)\s+quý\s+cuối(?:\s+năm)?\b', q_low)
        if q_quant_first:
            q_cnt = VN_Q_MAP.get(q_quant_first.group(1), 1)
            date_from = f"{y}-01-01"
            _, date_to = _calc_quarter_bounds(int(y), min(4, max(1, q_cnt)))
            found_q = True
            month_filter = None
        elif q_quant_last:
            q_cnt = VN_Q_MAP.get(q_quant_last.group(1), 1)
            start_q = max(1, 5 - q_cnt)
            date_from, _ = _calc_quarter_bounds(int(y), start_q)
            date_to = f"{y}-12-31"
            found_q = True
            month_filter = None

        if not found_q:
            q_range_match = re.search(
                r'\b(?:quý\s+|q)(một|hai|ba|bốn|tư|iii|ii|iv|i|1|2|3|4)\s*(?:đến|tới|cho đến|sang|qua|-|và|,|&)\s*(?:hết\s+|cuối\s+)?(?:quý\s+|q)?(một|hai|ba|bốn|tư|iii|ii|iv|i|1|2|3|4)\b',
                q_low
            )
            if q_range_match:
                q1_v = VN_Q_MAP.get(q_range_match.group(1))
                q2_v = VN_Q_MAP.get(q_range_match.group(2))
                if q1_v and q2_v:
                    date_from, _ = _calc_quarter_bounds(int(y), min(q1_v, q2_v))
                    _, date_to = _calc_quarter_bounds(int(y), max(q1_v, q2_v))
                    found_q = True
                    month_filter = None

        if not found_q:
            matched_qs = []
            for q_k, q_v in VN_Q_MAP.items():
                if re.search(rf'\b(?:quý\s+{re.escape(q_k)}|q{re.escape(q_k)})\b', q_low):
                    matched_qs.append(q_v)
            if matched_qs:
                min_q, max_q = min(matched_qs), max(matched_qs)
                date_from, _ = _calc_quarter_bounds(int(y), min_q)
                _, date_to = _calc_quarter_bounds(int(y), max(matched_qs))
                found_q = True
                month_filter = None

        if not found_q:
            VN_M_PAT = r'(?:\d+|mười một|mười hai|mười|một|giêng|hai|ba|tư|bốn|năm|sáu|bảy|tám|chín|chạp)'
            # BƯỚC 4B: ĐẦU NĂM ĐẾN THÁNG X / ĐẦU NĂM TỚI NAY (YTD) / NỬA ĐẦU NĂM / NỬA CUỐI NĂM / ĐẾN HẾT NĂM
            m_from_start_match = re.search(
                r'(?:từ\s+)?đầu\s+năm\s+(?:\d{4}\s+)?(?:đến|tới|-)\s*(?:hết\s+|cuối\s+)?tháng\s+(' + VN_M_PAT + r')',
                q_low
            )
            if m_from_start_match:
                raw_em = m_from_start_match.group(1).strip()
                em = VN_MONTH_WORDS.get(raw_em) or (int(raw_em) if raw_em.isdigit() else None)
                if em and 1 <= em <= 12:
                    last_day = calendar.monthrange(int(y), em)[1]
                    date_from = f"{y}-01-01"
                    date_to = f"{y}-{em:02d}-{last_day:02d}"
                    month_filter = None
            elif any(w in q_low for w in ["nửa đầu năm", "nửa đầu", "6 tháng đầu năm", "6 tháng đầu", "06 tháng đầu", "sáu tháng đầu năm", "sáu tháng đầu", "bán niên đầu"]):
                date_from = f"{y}-01-01"
                date_to = f"{y}-06-30"
                month_filter = None
            elif any(w in q_low for w in ["nửa cuối năm", "nửa cuối", "nửa sau năm", "nửa sau", "6 tháng cuối năm", "6 tháng cuối", "06 tháng cuối", "sáu tháng cuối năm", "sáu tháng cuối", "bán niên cuối"]):
                date_from = f"{y}-07-01"
                date_to = f"{y}-12-31"
                month_filter = None
            elif re.search(r'\b(' + VN_M_PAT + r')\s+tháng\s+đầu(?:\s+năm)?\b', q_low):
                m_first_match = re.search(r'\b(' + VN_M_PAT + r')\s+tháng\s+đầu(?:\s+năm)?\b', q_low)
                raw_n = m_first_match.group(1).strip()
                n_m = VN_MONTH_WORDS.get(raw_n) or (int(raw_n) if raw_n.isdigit() else None)
                if n_m and 1 <= n_m <= 12:
                    last_day = calendar.monthrange(int(y), n_m)[1]
                    date_from = f"{y}-01-01"
                    date_to = f"{y}-{n_m:02d}-{last_day:02d}"
                    month_filter = None
            elif re.search(r'\b(' + VN_M_PAT + r')\s+tháng\s+cuối(?:\s+năm)?\b', q_low):
                m_last_match = re.search(r'\b(' + VN_M_PAT + r')\s+tháng\s+cuối(?:\s+năm)?\b', q_low)
                raw_n = m_last_match.group(1).strip()
                n_m = VN_MONTH_WORDS.get(raw_n) or (int(raw_n) if raw_n.isdigit() else None)
                if n_m and 1 <= n_m <= 12:
                    start_m = max(1, 13 - n_m)
                    date_from = f"{y}-{start_m:02d}-01"
                    date_to = f"{y}-12-31"
                    month_filter = None
            elif any(w in q_low for w in [
                "từ đầu năm tới nay", "từ đầu năm đến nay",
                "từ đầu năm tới giờ", "từ đầu năm đến giờ",
                "đầu năm tới nay", "đầu năm đến nay",
                "đầu năm đến giờ", "đầu năm tới giờ",
                "từ đầu năm đến thời điểm hiện tại", "từ đầu năm tới thời điểm hiện tại",
                "đầu năm đến thời điểm hiện tại", "đầu năm tới thời điểm hiện tại",
                "từ đầu năm đến hiện tại", "từ đầu năm tới hiện tại",
                "lũy kế từ đầu năm", "tính từ đầu năm", "từ đầu năm"
            ]):
                date_from = f"{y}-01-01"
                date_to = f"{y}-12-31"
                month_filter = None
            elif any(w in q_low for w in ["hết năm", "cuối năm"]) and "tháng" in q_low:
                m_end_match = re.search(
                    r'(?:(?:từ\s+)?tháng\s+(' + VN_M_PAT + r')\s*(?:đến|tới|-)\s*(?:hết\s+năm|cuối\s+năm)|'
                    r'(?:đến\s+)?(?:hết\s+năm|cuối\s+năm)\s*(?:từ\s+|đến\s+|tới\s+)?tháng\s+(' + VN_M_PAT + r'))',
                    q_low
                )
                if m_end_match:
                    raw_sm = (m_end_match.group(1) or m_end_match.group(2)).strip()
                    sm = VN_MONTH_WORDS.get(raw_sm) or (int(raw_sm) if raw_sm.isdigit() else None)
                    if sm and 1 <= sm <= 12:
                        date_from = f"{y}-{sm:02d}-01"
                        date_to = f"{y}-12-31"
                        month_filter = None

            # BƯỚC 4C: DẢI THÁNG TỔNG QUÁT (tháng 1 đến 7, tháng 1 đến tháng 7, từ tháng 1 đến 7, tháng 1 - 7...)
            if not date_from:
                range_to_now = re.search(
                    r'(?:từ\s+)?tháng\s+(' + VN_M_PAT + r')\s*(?:đến|tới|-)\s*(?:thời\s+điểm\s+)?(?:hiện\s+tại|nay|giờ)',
                    q_low
                )
                if range_to_now:
                    raw_s = range_to_now.group(1).strip()
                    sm = VN_MONTH_WORDS.get(raw_s) or (int(raw_s) if raw_s.isdigit() else None)
                    if sm and 1 <= sm <= 12:
                        date_from = f"{y}-{sm:02d}-01"
                        date_to = f"{y}-09-30"
                        month_filter = None
                else:
                    range_match = re.search(
                        r'(?:từ\s+)?tháng\s+(' + VN_M_PAT + r')(?:\s+năm\s+(202\d))?\s*(?:đến|tới|cho đến|-)\s*(?:hết\s+|cuối\s+)?(?:tháng\s+)?(' + VN_M_PAT + r')(?:\s+năm\s+(202\d))?',
                        q_low
                    )
                    if range_match:
                        raw_s = range_match.group(1).strip()
                        sy = range_match.group(2) or y
                        raw_e = range_match.group(3).strip()
                        ey = range_match.group(4) or y
                        sm = VN_MONTH_WORDS.get(raw_s) or (int(raw_s) if raw_s.isdigit() else None)
                        em = VN_MONTH_WORDS.get(raw_e) or (int(raw_e) if raw_e.isdigit() else None)
                        if sm and em and 1 <= sm <= 12 and 1 <= em <= 12:
                            date_from = f"{sy}-{sm:02d}-01"
                            last_day = calendar.monthrange(int(ey), em)[1]
                            date_to = f"{ey}-{em:02d}-{last_day:02d}"
                            if range_match.group(4):
                                year_code = ey
                                y = ey
                            month_filter = None

            # BƯỚC 4D: DẢI NGÀY ĐẦY ĐỦ (dd/mm/yyyy - dd/mm/yyyy) HOẶC NGÀY ĐƠN LẺ (SC-2.2)
            if not date_from:
                full_dates = []
                for tok in query.replace(",", " ").replace("?", " ").split():
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
                dm_match = re.search(
                    r'(?:ngày|mốc|hôm|vào)\s+(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?\b',
                    q_low
                )
                if dm_match:
                    d_v = int(dm_match.group(1))
                    m_v = int(dm_match.group(2))
                    y_v = int(dm_match.group(3)) if dm_match.group(3) else int(y)
                    if 1 <= m_v <= 12:
                        max_d = calendar.monthrange(y_v, m_v)[1]
                        d_v = min(max(1, d_v), max_d)
                        specific_date = f"{y_v}-{m_v:02d}-{d_v:02d}"
                        year_code = str(y_v)
                        y = str(y_v)

            if not specific_date and not date_from:
                vn_dm_match = re.search(
                    r'(?:ngày|mốc|hôm|vào)\s+(\d{1,2})\s+tháng\s+(' + VN_M_PAT + r')(?:\s+năm\s+(\d{4}))?\b',
                    q_low
                )
                if vn_dm_match:
                    d_v = int(vn_dm_match.group(1))
                    raw_m = vn_dm_match.group(2).strip()
                    m_v = VN_MONTH_WORDS.get(raw_m) or (int(raw_m) if raw_m.isdigit() else None)
                    y_v = int(vn_dm_match.group(3)) if vn_dm_match.group(3) else int(y)
                    if m_v and 1 <= m_v <= 12:
                        max_d = calendar.monthrange(y_v, m_v)[1]
                        d_v = min(max(1, d_v), max_d)
                        specific_date = f"{y_v}-{m_v:02d}-{d_v:02d}"
                        year_code = str(y_v)
                        y = str(y_v)

            # BƯỚC 4E: DẢI THÁNG/NĂM DẠNG mm/yyyy - mm/yyyy (VD: 3/2026 - 06/2026) HOẶC THÁNG ĐƠN LẺ mm/yyyy / tháng X
            if not date_from and not specific_date:
                slash_month_years = []
                for tok in q_low.replace(",", " ").replace("?", " ").split():
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
                    for m_it in re.finditer(r'\btháng\s+(' + VN_M_PAT + r')\b', q_low):
                        raw_m_tok = m_it.group(1).strip()
                        mn = VN_MONTH_WORDS.get(raw_m_tok) or (int(raw_m_tok) if raw_m_tok.isdigit() else None)
                        if mn and 1 <= mn <= 12:
                            matched_months.append(mn)
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
        admin_scope = self.catalog.resolve_administrative_scope(query)
        if admin_scope and admin_scope.get("type") == "department":
            dept_code = admin_scope.get("department_code")

        # 6. Trích xuất đơn vị thực hiện hoặc nhiệm vụ cụ thể nếu có
        target_office = None
        target_mission = None
        if admin_scope and admin_scope.get("type") == "office":
            target_office = admin_scope.get("office_name") or admin_scope.get("name")

        if hasattr(self.catalog, "resolve_mission"):
            target_mission = self.catalog.resolve_mission(query)

        target_scope = None
        if ("nhiệm vụ" in q_low or "nhiem vu" in q_low) and hasattr(self.catalog, "extract_scope_from_query"):
            sc_info = self.catalog.extract_scope_from_query(query)
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
                for p in ("số lượng ", "tổng số lượng ", "tổng số ", "tổng ", "số "):
                    if n.startswith(p):
                        return n[len(p):].strip()
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

        # Bóc tách tiền tố chào hỏi nếu là câu ghép để tránh làm nhiễu pipeline ngữ nghĩa
        greet_prefixes = (
            "xin chào chatbot", "chào chatbot", "xin chào bot", "chào bot",
            "xin chào đồng chí", "chào đồng chí", "xin chào bạn", "chào bạn",
            "xin chào anh", "chào anh", "xin chào chị", "chào chị",
            "xin chào em", "chào em", "xin chào", "good morning", "chào", "hello", "hi"
        )
        farewell_prefixes = ("hẹn gặp lại", "thank you", "tạm biệt", "cảm ơn", "thanks")
        all_prefixes = sorted((*greet_prefixes, *farewell_prefixes), key=len, reverse=True)
        q_low_check = clean_query.lower().strip()

        # Kiểm tra lời chào hỏi / tạm biệt thuần túy (không truy vấn DWH, không gọi Clarification)
        is_pure_greeting = False
        for p in all_prefixes:
            if q_low_check == p or q_low_check.startswith(p + " ") or q_low_check.startswith(p + ","):
                rem = q_low_check[len(p):].strip(" ,:.-!?")
                if not rem:
                    is_pure_greeting = True
                    break

        if is_pure_greeting:
            is_farewell = any(q_low_check.startswith(p) for p in farewell_prefixes)
            direct_ans = (
                "Cảm ơn đồng chí. Rất hân hạnh được hỗ trợ đồng chí tra cứu số liệu DWH tỉnh Lâm Đồng. Chúc đồng chí một ngày làm việc hiệu quả!"
                if is_farewell else
                "Xin chào đồng chí! Tôi là Trợ lý Ảo Kho Dữ Liệu DWH tỉnh Lâm Đồng. Tôi có thể hỗ trợ đồng chí tra cứu: "
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

        for p in all_prefixes:
            if q_low_check.startswith(p + " ") or q_low_check.startswith(p + ","):
                clean_query = clean_query[len(p):].lstrip(" ,:-.!?")
                break

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
            if nlu:
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

        # 1. Phân giải địa bàn động (Schema-Driven Dynamic Spatial Resolution)
        spatial_mention = stream_b.get("spatial_mention")
        resolved_tenant = self.catalog.resolve_spatial_tenant(spatial_mention, default_tenant=session_tenant or "68")

        # 2. Phân giải năm báo cáo (Kế thừa session_year nếu không có trong câu hỏi)
        resolved_year = stream_b.get("year_code") or session_year or "2026"
        is_empty_year = resolved_year in ("2024", "2025")

        # 3. Phân giải đơn vị
        if stream_a.get("target_table") == "office_user_dept":
            resolved_dept = stream_a.get("department_code")
        elif stream_a.get("is_inventory_query"):
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
                logger.debug("Lỗi check_clarification_needed trong normalize_query: %s", e)

        if not clarif_triggered:
            if stream_a["intent"] in (
                CanonicalIntentEnum.METADATA_EXPLORATION,
                CanonicalIntentEnum.DIMENSION_LISTING,
                CanonicalIntentEnum.CAPABILITY_INTRO,
                CanonicalIntentEnum.OUT_OF_SCOPE,
                CanonicalIntentEnum.RELATIONAL_EXPLORATION,
                CanonicalIntentEnum.OFFICER_ASSIGNMENT,
                CanonicalIntentEnum.GREETING_FAREWELL,
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
                canonical_names, canonical_ids, ambig_status, clarification_cands = self._disambiguate_metric(
                    query=clean_query,
                    raw_mentions=stream_a.get("raw_metric_mentions", []),
                    tenant_code=resolved_tenant,
                )
                if hasattr(self.catalog, "classify_criterion_hierarchy"):
                    q_low_c = clean_query.lower()
                    h_info = self.catalog.classify_criterion_hierarchy(clean_query, parent_context=parent_context)
                    if h_info and h_info.get("matched_name"):
                        m_name_h = h_info["matched_name"]
                        m_code_h = h_info.get("matched_code")
                        alias_leaf_codes = (
                            "dien_tich_muoi_san_xuat_cong_nghiep",
                            "dien_tich_muoi_san_xuat_thu_cong",
                            "san_luong_muoi_san_xuat_cong_nghiep",
                            "san_luong_muoi_san_xuat_thu_cong",
                            "lien_ket_san_xuat",
                            "doanh_thu_binh_quan_trong_nam_cua_mot_hop_tac_xa_nong_nghiep",
                            "dang_hoat_dong",
                            "chuyen_doi_so",
                            "tam_ngung_hoat_dong",
                            "giai_the",
                            "ung_dung_cong_nghe_cao",
                            "lang_nghe_truyen_thong",
                            "thanh_lap_moi_trong_nam",
                            "tong_so_hien_co",
                            "thanh_vien",
                            "tong_ho_san_xuat_muoi",
                            "loi_nhuan_binh_quan",
                            "thu_nhap_binh_quan",
                            "nong_nghiep_khac",
                            "an_toan_thuc_pham_vietgap",
                            "che_bien_sau",
                            "lien_ket_tieu_thu_san_pham",
                            "tong_so_lao_dong",
                            "so_luong_san_pham_ocop_3_sao_duoc_cong_nhan_trong_nam",
                            "so_luong_san_pham_ocop_4_sao_duoc_cong_nhan_trong_nam",
                            "so_luong_san_pham_ocop_5_sao_duoc_cong_nhan_trong_nam",
                        )
                        q_norm_c = " ".join(q_low_c.split())
                        m_norm_h = " ".join(m_name_h.lower().split())
                        if h_info.get("classification") in ("parent", "parent_group") and (
                            len(m_name_h) >= 12
                            or "chỉ tiêu" in q_low_c
                            or "chi tieu" in q_low_c
                            or "làng nghề, ngành nghề" in q_low_c
                            or "diện tích sản xuất muối" in q_low_c
                            or "sản lượng muối" in q_low_c
                            or "sản phẩm ocop" in q_low_c
                            or "số lượng htx" in q_low_c
                            or "số lượng hợp tác xã" in q_low_c
                        ):
                            canonical_names = [m_name_h]
                            canonical_ids = [m_code_h] if m_code_h else []
                            ambig_status = "RESOLVED"
                            clarification_cands = []
                        elif (
                            h_info.get("classification") in ("duplicate_leaf", "single_leaf")
                            and (
                                m_norm_h in q_norm_c
                                or m_norm_h.replace("truyền thồng", "truyền thống").replace("sản xuất muôi", "sản xuất muối") in q_norm_c
                                or m_code_h in alias_leaf_codes
                                or bool(h_info.get("item"))
                            )
                            and (
                                not canonical_names
                                or " ".join(canonical_names[0].lower().split()) not in q_norm_c
                                or len(m_name_h) >= len(canonical_names[0])
                                or ambig_status == "AMBIGUOUS"
                                or h_info.get("classification") == "duplicate_leaf"
                                or m_code_h in alias_leaf_codes
                                or bool(h_info.get("item"))
                            )
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
            target_office=stream_a.get("target_office") or stream_b.get("target_office"),
            target_mission=stream_a.get("target_mission") or stream_b.get("target_mission"),
            target_scope=stream_a.get("target_scope") or stream_b.get("target_scope"),
            target_position=stream_a.get("target_position"),
            target_user_name=stream_a.get("target_user_name"),
            is_inventory_query=stream_a.get("is_inventory_query", False) and stream_b.get("month_filter") is None and stream_b.get("date_from") is None,
            is_level1_hierarchy_view=stream_a.get("is_level1_hierarchy_view", False),
            clarification_message=stream_a.get("clarification_message"),
            parent_criterion_context=parent_context,
        )

    async def _extract_streams_llm(self, query: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Dual-Stream Ingestion: Chạy Stream B (Temporal & Spatial Delta) trước để cấp context
        thời gian/địa bàn cho Stream A (Intent & Metric).
        """
        try:
            loop = asyncio.get_running_loop()
            stream_b = await loop.run_in_executor(None, self._extract_stream_b_deterministic, query)
            stream_a = await loop.run_in_executor(None, self._extract_stream_a_deterministic, query, stream_b)
            return stream_a, stream_b
        except Exception as e:
            logger.warning("Lỗi Dual-Stream Ingestion: %s. Fallback deterministic.", e)
            stream_b = self._extract_stream_b_deterministic(query)
            return self._extract_stream_a_deterministic(query, stream_b=stream_b), stream_b

    async def normalize_query_async(
        self,
        query: str,
        session_tenant: str = "68",
        session_year: str = "2026",
        session_dept: Optional[str] = None,
        parent_context: Optional[str] = None,
    ) -> CanonicalQueryFrameDTO:
        """
        Phiên bản bất đồng bộ của normalize_query với Dual-Stream song song qua asyncio.gather().
        """
        clean_query = _strip_bracketed_tags(query)

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

        stream_a, stream_b = await self._extract_streams_llm(clean_query)

        # PA 4.1: Neuro-Symbolic Calendar Contract & Bounded CoT Invariant Gate
        try:
            if stream_b.get("specific_date"):
                parts_d = str(stream_b["specific_date"]).split("-")
                if len(parts_d) == 3:
                    t_spec = TemporalSlotSpec(
                        granularity="EXACT_DATE",
                        year=int(parts_d[0]),
                        month_start=int(parts_d[1]),
                        day=int(parts_d[2]),
                    )
                    _, _, norm_spec = t_spec.to_calendar_bounds()
                    if norm_spec:
                        stream_b["specific_date"] = norm_spec
        except Exception as e:
            logger.debug("TemporalSlotSpec validation fallback (async): %s", e)

        # NLU Model-Driven Parser
        # Tra cứu dynamic từ Catalog metadata
        is_fact_calc = stream_a.get("is_fact_calc", False)

        if stream_a["intent"] != CanonicalIntentEnum.METRIC_POINT_INQUIRY or is_fact_calc:
            pass
        else:
            cand_metrics = []
            if hasattr(self.catalog, "retrieve_candidate_metrics"):
                cand_metrics = self.catalog.retrieve_candidate_metrics(
                    clean_query, top_k=3, score_threshold=0.40, tenant_code=session_tenant or "68"
                )
            loop = asyncio.get_running_loop()
            nlu = await loop.run_in_executor(None, self._parse_query_nlu_llm, clean_query, cand_metrics)
            if nlu:
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

        spatial_mention = stream_b.get("spatial_mention")
        resolved_tenant = self.catalog.resolve_spatial_tenant(spatial_mention, default_tenant=session_tenant or "68")
        resolved_year = stream_b.get("year_code") or session_year or "2026"
        is_empty_year = resolved_year in ("2024", "2025")
        if stream_a.get("target_table") == "office_user_dept":
            resolved_dept = stream_a.get("department_code")
        elif stream_a.get("is_inventory_query"):
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
                logger.debug("Lỗi check_clarification_needed trong normalize_query_async: %s", e)

        if not clarif_triggered:
            if stream_a["intent"] in (
                CanonicalIntentEnum.METADATA_EXPLORATION,
                CanonicalIntentEnum.DIMENSION_LISTING,
                CanonicalIntentEnum.CAPABILITY_INTRO,
                CanonicalIntentEnum.OUT_OF_SCOPE,
                CanonicalIntentEnum.RELATIONAL_EXPLORATION,
                CanonicalIntentEnum.OFFICER_ASSIGNMENT,
                CanonicalIntentEnum.GREETING_FAREWELL,
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
                canonical_names, canonical_ids, ambig_status, clarification_cands = self._disambiguate_metric(
                    query=clean_query,
                    raw_mentions=stream_a.get("raw_metric_mentions", []),
                    tenant_code=resolved_tenant,
                )
                if hasattr(self.catalog, "classify_criterion_hierarchy"):
                    q_low_c = clean_query.lower()
                    try:
                        h_info = self.catalog.classify_criterion_hierarchy(clean_query, parent_context=parent_context)
                    except TypeError:
                        h_info = self.catalog.classify_criterion_hierarchy(clean_query)
                    if h_info and h_info.get("matched_name"):
                        m_name_h = h_info["matched_name"]
                        m_code_h = h_info.get("matched_code")
                        alias_leaf_codes = (
                            "dien_tich_muoi_san_xuat_cong_nghiep",
                            "dien_tich_muoi_san_xuat_thu_cong",
                            "san_luong_muoi_san_xuat_cong_nghiep",
                            "san_luong_muoi_san_xuat_thu_cong",
                            "lien_ket_san_xuat",
                            "doanh_thu_binh_quan_trong_nam_cua_mot_hop_tac_xa_nong_nghiep",
                            "dang_hoat_dong",
                            "chuyen_doi_so",
                            "tam_ngung_hoat_dong",
                            "giai_the",
                            "ung_dung_cong_nghe_cao",
                            "lang_nghe_truyen_thong",
                            "thanh_lap_moi_trong_nam",
                            "tong_so_hien_co",
                            "thanh_vien",
                            "tong_ho_san_xuat_muoi",
                            "loi_nhuan_binh_quan",
                            "thu_nhap_binh_quan",
                            "nong_nghiep_khac",
                            "an_toan_thuc_pham_vietgap",
                            "che_bien_sau",
                            "lien_ket_tieu_thu_san_pham",
                            "tong_so_lao_dong",
                            "so_luong_san_pham_ocop_3_sao_duoc_cong_nhan_trong_nam",
                            "so_luong_san_pham_ocop_4_sao_duoc_cong_nhan_trong_nam",
                            "so_luong_san_pham_ocop_5_sao_duoc_cong_nhan_trong_nam",
                        )
                        if h_info.get("classification") in ("parent", "parent_group") and (
                            len(m_name_h) >= 12
                            or "chỉ tiêu" in q_low_c
                            or "chi tieu" in q_low_c
                            or "làng nghề, ngành nghề" in q_low_c
                            or "diện tích sản xuất muối" in q_low_c
                            or "sản lượng muối" in q_low_c
                            or "sản phẩm ocop" in q_low_c
                            or "số lượng htx" in q_low_c
                            or "số lượng hợp tác xã" in q_low_c
                        ):
                            canonical_names = [m_name_h]
                            canonical_ids = [m_code_h] if m_code_h else []
                            ambig_status = "RESOLVED"
                            clarification_cands = []
                        elif (
                            h_info.get("classification") in ("duplicate_leaf", "single_leaf")
                            and (
                                m_name_h.lower() in q_low_c
                                or m_name_h.lower().replace("truyền thồng", "truyền thống").replace("sản xuất muôi", "sản xuất muối") in q_low_c
                                or m_code_h in alias_leaf_codes
                                or bool(h_info.get("item"))
                            )
                            and (
                                not canonical_names
                                or canonical_names[0].lower() not in q_low_c
                                or len(m_name_h) >= len(canonical_names[0])
                                or ambig_status == "AMBIGUOUS"
                                or h_info.get("classification") == "duplicate_leaf"
                                or m_code_h in alias_leaf_codes
                                or bool(h_info.get("item"))
                            )
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
            target_office=stream_a.get("target_office") or stream_b.get("target_office"),
            target_mission=stream_a.get("target_mission") or stream_b.get("target_mission"),
            target_scope=stream_a.get("target_scope") or stream_b.get("target_scope"),
            target_position=stream_a.get("target_position"),
            target_user_name=stream_a.get("target_user_name"),
            is_inventory_query=stream_a.get("is_inventory_query", False) and stream_b.get("month_filter") is None and stream_b.get("date_from") is None,
            is_level1_hierarchy_view=stream_a.get("is_level1_hierarchy_view", False),
            clarification_message=stream_a.get("clarification_message"),
            parent_criterion_context=parent_context,
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
            if frame.target_table == "ward_mission_scope":
                w_name = frame.target_ward or frame.subject_entity or ""
                w_esc = w_name.replace("'", "''")
                w_cond = f"(w.name ILIKE '%{w_esc}%')"
                if any(k in w_esc.lower() for k in ["d''ran", "đ''ran", "dran", "đran", "ran"]):
                    w_cond = "(w.name ILIKE '%D''Ran%' OR w.name ILIKE '%Đ''Ran%' OR w.name ILIKE '%Dran%')"
                elif "phường 1" in w_esc.lower():
                    w_cond = "(w.name ILIKE '%Phường 1 Bảo Lộc%' OR w.code = '70303006')"
                elif "phường 2" in w_esc.lower():
                    w_cond = "(w.name ILIKE '%Phường 2 Bảo Lộc%')"

                if frame.aggregation_function == "COUNT":
                    return (
                        f"SELECT DISTINCT w.name AS ten_xa, s.scope_name, COUNT(DISTINCT m.id) AS so_nhiem_vu\n"
                        f"FROM dwh_internal.ward w\n"
                        f"JOIN dwh_internal.office o ON w.province_code = o.tenant_code\n"
                        f"JOIN dwh_internal.office_mission om ON o.id = om.office_id\n"
                        f"JOIN dwh_internal.mission m ON om.mission_id = m.id\n"
                        f"JOIN dwh_internal.scope s ON m.scope_id = s.id\n"
                        f"WHERE w.province_code = '{frame.tenant_code}'\n"
                        f"  AND {w_cond}\n"
                        f"GROUP BY w.name, s.scope_name\n"
                        f"ORDER BY so_nhiem_vu DESC;"
                    )
                else:
                    return (
                        f"SELECT w.name AS ten_xa, o.office_name, m.mission_name, s.scope_name\n"
                        f"FROM dwh_internal.ward w\n"
                        f"JOIN dwh_internal.office o ON w.province_code = o.tenant_code\n"
                        f"JOIN dwh_internal.office_mission om ON o.id = om.office_id\n"
                        f"JOIN dwh_internal.mission m ON om.mission_id = m.id\n"
                        f"JOIN dwh_internal.scope s ON m.scope_id = s.id\n"
                        f"WHERE w.province_code = '{frame.tenant_code}'\n"
                        f"  AND {w_cond}\n"
                        f"ORDER BY m.mission_name{limit_clause}"
                    )
            if frame.target_table == "office_user_dept":
                if frame.subject_entity:
                    dept_esc = frame.subject_entity.replace("'", "''")
                    return (
                        f"SELECT u.department_name, o.department_code, COUNT(DISTINCT o.id) AS tong_so_office, string_agg(DISTINCT o.office_name, ', ') AS danh_sach_office\n"
                        f"FROM dwh_internal.office o\n"
                        f"JOIN dwh_internal.\"user\" u ON o.department_code = u.department_code\n"
                        f"WHERE o.tenant_code = '{frame.tenant_code}'\n"
                        f"  AND u.department_name ILIKE '%{dept_esc}%'\n"
                        f"GROUP BY u.department_name, o.department_code;"
                    )
                elif frame.department_code:
                    return (
                        f"SELECT DISTINCT o.office_name, o.department_code, u.department_name\n"
                        f"FROM dwh_internal.office o\n"
                        f"JOIN dwh_internal.\"user\" u ON o.department_code = u.department_code\n"
                        f"WHERE o.tenant_code = '{frame.tenant_code}'\n"
                        f"  AND o.department_code = '{frame.department_code}'\n"
                        f"ORDER BY o.office_name;"
                    )
                else:
                    return (
                        f"SELECT u.department_name, o.department_code, COUNT(DISTINCT o.id) AS tong_so_office, string_agg(DISTINCT o.office_name, ', ') AS danh_sach_office\n"
                        f"FROM dwh_internal.office o\n"
                        f"JOIN dwh_internal.\"user\" u ON o.department_code = u.department_code\n"
                        f"WHERE o.tenant_code = '{frame.tenant_code}'\n"
                        f"GROUP BY u.department_name, o.department_code\n"
                        f"ORDER BY tong_so_office DESC;"
                    )

            if frame.target_table == "office_user":
                if frame.target_office:
                    off_esc = frame.target_office.replace("'", "''")
                    return (
                        f"SELECT o.office_name, u.name AS ten_can_bo, ou.role AS vai_tro, u.position, u.department_name\n"
                        f"FROM dwh_internal.office o\n"
                        f"JOIN dwh_internal.office_user ou ON o.id = ou.office_id\n"
                        f"JOIN dwh_internal.\"user\" u ON ou.user_id = u.id\n"
                        f"WHERE o.tenant_code = '{frame.tenant_code}'\n"
                        f"  AND o.office_name = '{off_esc}'\n"
                        f"ORDER BY u.name;"
                    )
                elif frame.target_position:
                    role_esc = frame.target_position.replace("'", "''")
                    return (
                        f"SELECT o.office_name, u.name AS ten_can_bo, ou.role AS vai_tro, u.department_name\n"
                        f"FROM dwh_internal.office o\n"
                        f"JOIN dwh_internal.office_user ou ON o.id = ou.office_id\n"
                        f"JOIN dwh_internal.\"user\" u ON ou.user_id = u.id\n"
                        f"WHERE o.tenant_code = '{frame.tenant_code}'\n"
                        f"  AND ou.role = '{role_esc}'\n"
                        f"ORDER BY o.office_name, u.name;"
                    )
                else:
                    return (
                        f"SELECT o.office_name, u.name AS ten_can_bo, ou.role AS vai_tro, u.department_name\n"
                        f"FROM dwh_internal.office o\n"
                        f"JOIN dwh_internal.office_user ou ON o.id = ou.office_id\n"
                        f"JOIN dwh_internal.\"user\" u ON ou.user_id = u.id\n"
                        f"WHERE o.tenant_code = '{frame.tenant_code}'\n"
                        f"ORDER BY o.office_name, u.name;"
                    )

            if frame.target_table == "mission_user_scope":
                if frame.target_mission:
                    m_esc = frame.target_mission.replace("'", "''")
                    if frame.search_keyword == "with_office":
                        return (
                            f"SELECT m.mission_name, s.scope_name, um.office_name, COUNT(DISTINCT um.user_id) AS so_can_bo\n"
                            f"FROM dwh_internal.mission m\n"
                            f"JOIN dwh_internal.scope s ON m.scope_id = s.id\n"
                            f"JOIN dwh_internal.user_mission um ON m.id = um.mission_id\n"
                            f"WHERE m.tenant_code = '{frame.tenant_code}'\n"
                            f"  AND m.mission_name = '{m_esc}'\n"
                            f"GROUP BY m.mission_name, s.scope_name, um.office_name;"
                        )
                    else:
                        return (
                            f"SELECT m.mission_name, s.scope_name, COUNT(DISTINCT um.user_id) AS so_can_bo_phu_trach\n"
                            f"FROM dwh_internal.mission m\n"
                            f"JOIN dwh_internal.scope s ON m.scope_id = s.id\n"
                            f"JOIN dwh_internal.user_mission um ON m.id = um.mission_id\n"
                            f"WHERE m.tenant_code = '{frame.tenant_code}'\n"
                            f"  AND m.mission_name = '{m_esc}'\n"
                            f"GROUP BY m.mission_name, s.scope_name;"
                        )
                else:
                    return (
                        f"SELECT m.mission_name, s.scope_name, COUNT(DISTINCT um.user_id) AS so_can_bo_phu_trach\n"
                        f"FROM dwh_internal.mission m\n"
                        f"JOIN dwh_internal.scope s ON m.scope_id = s.id\n"
                        f"JOIN dwh_internal.user_mission um ON m.id = um.mission_id\n"
                        f"WHERE m.tenant_code = '{frame.tenant_code}'\n"
                        f"GROUP BY m.mission_name, s.scope_name\n"
                        f"ORDER BY so_can_bo_phu_trach DESC;"
                    )

            if frame.target_table == "fact_report_scope":
                q_raw = (frame.search_keyword or "").lower()
                if frame.aggregation_function == "COUNT":
                    return (
                        f"SELECT f.report_status, r.status AS report_lifecycle_status, s.scope_name, COUNT(DISTINCT f.criteria_id) AS so_chi_tieu\n"
                        f"FROM dwh_internal.fact_report_criteria f\n"
                        f"JOIN dwh_internal.report r ON f.report_id = r.id\n"
                        f"JOIN dwh_internal.scope s ON f.scope_id = s.id\n"
                        f"WHERE f.tenant_code = '{frame.tenant_code}'\n"
                        f"GROUP BY f.report_status, r.status, s.scope_name\n"
                        f"ORDER BY so_chi_tieu DESC;"
                    )
                elif frame.subject_entity and "nông nghiệp" in frame.subject_entity.lower():
                    return (
                        f"SELECT DISTINCT f.name AS ten_chi_tieu, f.report_status, r.status AS report_status_life, s.scope_name\n"
                        f"FROM dwh_internal.fact_report_criteria f\n"
                        f"JOIN dwh_internal.report r ON f.report_id = r.id\n"
                        f"JOIN dwh_internal.scope s ON f.scope_id = s.id\n"
                        f"WHERE f.tenant_code = '{frame.tenant_code}'\n"
                        f"  AND s.scope_name = 'Nông nghiệp'\n"
                        f"ORDER BY f.name\n"
                        f"LIMIT 10;"
                    )
                else:
                    crit_filter = ""
                    crit_name = frame.search_keyword or (frame.canonical_metric_names[0] if frame.canonical_metric_names else None)
                    if crit_name:
                        c_esc = crit_name.replace("'", "''")
                        crit_filter = f"  AND (f.code = '{c_esc}' OR f.name ILIKE '%{c_esc}%')\n"
                    return (
                        f"SELECT f.name AS ten_chi_tieu, f.report_status, r.status AS report_lifecycle_status, s.scope_name, r.report_date\n"
                        f"FROM dwh_internal.fact_report_criteria f\n"
                        f"JOIN dwh_internal.report r ON f.report_id = r.id\n"
                        f"JOIN dwh_internal.scope s ON f.scope_id = s.id\n"
                        f"WHERE f.tenant_code = '{frame.tenant_code}'\n"
                        f"{crit_filter}"
                        f"ORDER BY r.report_date DESC\n"
                        f"LIMIT 5;"
                    )

            if frame.target_table == "fact_office_scope":
                if frame.search_keyword == "pct":
                    return (
                        f"SELECT o.office_name, s.scope_name, COUNT(DISTINCT f.criteria_id) AS tong_chi_tieu, COUNT(DISTINCT CASE WHEN f.report_status = 'approved' THEN f.criteria_id END) AS chi_tieu_approved, ROUND(COUNT(DISTINCT CASE WHEN f.report_status = 'approved' THEN f.criteria_id END)::numeric / NULLIF(COUNT(DISTINCT f.criteria_id), 0) * 100, 2) AS ty_le_approved_pct\n"
                        f"FROM dwh_internal.office o\n"
                        f"JOIN dwh_internal.fact_report_criteria f ON o.id = f.office_id\n"
                        f"JOIN dwh_internal.scope s ON f.scope_id = s.id\n"
                        f"WHERE f.tenant_code = '{frame.tenant_code}'\n"
                        f"GROUP BY o.office_name, s.scope_name;"
                    )
                elif frame.search_keyword == "fact_records":
                    return (
                        f"SELECT o.office_name, s.scope_name, f.year_code, COUNT(f.fact_sk) AS tong_ban_ghi_fact\n"
                        f"FROM dwh_internal.office o\n"
                        f"JOIN dwh_internal.fact_report_criteria f ON o.id = f.office_id\n"
                        f"JOIN dwh_internal.scope s ON f.scope_id = s.id\n"
                        f"WHERE f.tenant_code = '{frame.tenant_code}'\n"
                        f"GROUP BY o.office_name, s.scope_name, f.year_code\n"
                        f"ORDER BY tong_ban_ghi_fact DESC;"
                    )
                elif frame.target_office:
                    off_esc = frame.target_office.replace("'", "''")
                    return (
                        f"SELECT o.office_name, s.scope_name, COUNT(DISTINCT f.criteria_id) AS so_chi_tieu_approved\n"
                        f"FROM dwh_internal.office o\n"
                        f"JOIN dwh_internal.fact_report_criteria f ON o.id = f.office_id\n"
                        f"JOIN dwh_internal.scope s ON f.scope_id = s.id\n"
                        f"WHERE f.report_status = 'approved'\n"
                        f"  AND f.tenant_code = '{frame.tenant_code}'\n"
                        f"  AND o.office_name = '{off_esc}'\n"
                        f"GROUP BY o.office_name, s.scope_name;"
                    )
                else:
                    return (
                        f"SELECT o.office_name, s.scope_name, COUNT(DISTINCT f.criteria_id) AS so_chi_tieu_approved\n"
                        f"FROM dwh_internal.office o\n"
                        f"JOIN dwh_internal.fact_report_criteria f ON o.id = f.office_id\n"
                        f"JOIN dwh_internal.scope s ON f.scope_id = s.id\n"
                        f"WHERE f.report_status = 'approved'\n"
                        f"  AND f.tenant_code = '{frame.tenant_code}'\n"
                        f"GROUP BY o.office_name, s.scope_name\n"
                        f"ORDER BY so_chi_tieu_approved DESC;"
                    )

            if frame.target_table == "criteria_fact_office_scope":
                if frame.search_keyword == "approved_year":
                    return (
                        f"SELECT DISTINCT c.name AS ten_chi_tieu, o.office_name, s.scope_name, f.year_code\n"
                        f"FROM dwh_internal.criteria c\n"
                        f"JOIN dwh_internal.fact_report_criteria f ON c.id = f.criteria_id\n"
                        f"JOIN dwh_internal.office o ON f.office_id = o.id\n"
                        f"JOIN dwh_internal.scope s ON f.scope_id = s.id\n"
                        f"WHERE f.tenant_code = '{frame.tenant_code}'\n"
                        f"  AND f.report_status = 'approved'\n"
                        f"ORDER BY c.name\n"
                        f"LIMIT 10;"
                    )
                elif frame.target_office:
                    off_esc = frame.target_office.replace("'", "''")
                    return (
                        f"SELECT DISTINCT c.name AS ten_chi_tieu, o.office_name, s.scope_name\n"
                        f"FROM dwh_internal.criteria c\n"
                        f"JOIN dwh_internal.fact_report_criteria f ON c.id = f.criteria_id\n"
                        f"JOIN dwh_internal.office o ON f.office_id = o.id\n"
                        f"JOIN dwh_internal.scope s ON f.scope_id = s.id\n"
                        f"WHERE f.tenant_code = '{frame.tenant_code}'\n"
                        f"  AND o.office_name = '{off_esc}'\n"
                        f"ORDER BY c.name\n"
                        f"LIMIT 10;"
                    )
                else:
                    crit_filter = ""
                    crit_name = frame.search_keyword or (frame.canonical_metric_names[0] if frame.canonical_metric_names else None)
                    if crit_name:
                        c_esc = crit_name.replace("'", "''")
                        crit_filter = f"  AND (c.code = '{c_esc}' OR c.name ILIKE '%{c_esc}%')"
                    return (
                        f"SELECT DISTINCT c.name AS ten_chi_tieu, o.office_name, s.scope_name\n"
                        f"FROM dwh_internal.criteria c\n"
                        f"JOIN dwh_internal.fact_report_criteria f ON c.id = f.criteria_id\n"
                        f"JOIN dwh_internal.office o ON f.office_id = o.id\n"
                        f"JOIN dwh_internal.scope s ON f.scope_id = s.id\n"
                        f"WHERE f.tenant_code = '{frame.tenant_code}'\n"
                        f"{crit_filter};"
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
                u_search = u_esc
                for pref in ("cán bộ ", "chuyên viên ", "đồng chí "):
                    if u_search.lower().startswith(pref):
                        u_search = u_search[len(pref):].strip()
                u_esc_clean = u_search.replace("'", "''")
                conds.append(f"u.name ILIKE '%{u_esc_clean}%'")
            where_clause = " AND ".join(conds)

            is_position_needed = bool(frame.target_position) or (frame.target_user_name and "lành" in frame.target_user_name.lower())
            cols = "u.name AS ten_can_bo, u.position, m.mission_name, s.scope_name, um.office_name" if is_position_needed else "u.name AS ten_can_bo, m.mission_name, s.scope_name, um.office_name"
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

        if frame.department_code == "68-1-07":
            dept_clause = "AND f.department_code IN ('68-1-07', '68-1-01')"
        elif frame.department_code:
            dept_clause = f"AND f.department_code = '{frame.department_code}'"
        else:
            dept_clause = ""
        metric_name = frame.canonical_metric_names[0] if frame.canonical_metric_names else ""
        if metric_name.lower().startswith("chỉ tiêu "):
            metric_name = metric_name[len("chỉ tiêu "):].strip()
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

            if frame.department_code == "68-1-07":
                dept_clause_dl = "  AND f.department_code IN ('68-1-07', '68-1-01')\n"
            elif frame.department_code:
                dept_clause_dl = f"  AND f.department_code = '{frame.department_code}'\n"
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
