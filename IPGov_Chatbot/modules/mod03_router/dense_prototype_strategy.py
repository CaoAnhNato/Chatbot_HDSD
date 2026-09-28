"""
IPGov Chatbot - Module 03: Dense Semantic Prototype Strategy
Sử dụng mô hình SSOT settings.EMBEDDING_MODEL_NAME (AITeamVN/Vietnamese_Embedding_v2)
So khớp Cosine Similarity với tập Canonical Prototypes Trừu Tượng (Rule 9 & Rule 10).
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer

from backend.config import settings
from IPGov_Chatbot.schemas.router_dto import (
    IntentEnum,
    RouteTypeEnum,
)
from IPGov_Chatbot.modules.mod03_router.semantic_strategy_interface import (
    SemanticMatchResult,
    SemanticRouterStrategy,
)


class DensePrototypeStrategy(SemanticRouterStrategy):
    """Chiến lược đối sánh ngữ nghĩa vector Dense với các Canonical Prototypes."""

    _model: Optional[SentenceTransformer] = None
    _prototype_embeddings: Optional[np.ndarray] = None
    _prototype_meta: Optional[List[Dict[str, Any]]] = None

    def __init__(self) -> None:
        self._ensure_initialized()

    @classmethod
    def _ensure_initialized(cls) -> None:
        """Khởi tạo mô hình và nhúng sẵn vector của tập Prototypes vào RAM một lần duy nhất."""
        if cls._model is not None and cls._prototype_embeddings is not None:
            return

        model_name = getattr(settings, "EMBEDDING_MODEL_NAME", "AITeamVN/Vietnamese_Embedding_v2")
        cls._model = SentenceTransformer(model_name)

        # Định nghĩa tập Canonical Prototypes Trừu tượng độc lập (Rule 9.2)
        cls._prototype_meta = [
            # 1. CATALOG_DISCOVERY
            {
                "text": "Trợ lý ảo này có những tính năng, tiện ích và chức năng gì?",
                "track": RouteTypeEnum.CATALOG_DISCOVERY,
                "intent": IntentEnum.META_CAPABILITY,
                "answer": "Hệ thống là Trợ lý ảo khai thác kho dữ liệu công vụ tập trung, hỗ trợ 4 tiện ích cốt lõi: (1) Tra cứu thống kê các chỉ tiêu KTXH; (2) So sánh biến động cùng kỳ (YoY); (3) Theo dõi tiến độ duyệt báo cáo tác nghiệp; (4) Xuất bảng số liệu đối soát ra Excel/Word.",
                "action_chips": ["📊 Báo cáo KTXH tổng hợp toàn tỉnh", "💰 Tiến độ giải ngân vốn đầu tư công", "⚡ Chỉ đạo điều hành & An toàn lao động"],
            },
            {
                "text": "Hệ thống đang theo dõi số liệu của những ngành, lĩnh vực nào?",
                "track": RouteTypeEnum.CATALOG_DISCOVERY,
                "intent": IntentEnum.META_CAPABILITY,
                "answer": "Hệ thống hiện đang quản lý và theo dõi số liệu của 8 lĩnh vực quản lý nhà nước: (1) Nội vụ & Lao động, (2) Xây dựng, (3) Công thương, (4) Y tế, (5) Giáo dục & Đào tạo, (6) Văn hóa - Xã hội, (7) Nông nghiệp & PTNT, (8) Tài nguyên & Môi trường.",
                "action_chips": ["💼 Lĩnh vực Lao động & Nội vụ", "🏗️ Lĩnh vực Xây dựng", "⚡ Lĩnh vực Công thương", "🏥 Lĩnh vực Y tế"],
            },
            {
                "text": "Số liệu báo cáo trong hệ thống có từ năm nào đến năm nào?",
                "track": RouteTypeEnum.CATALOG_DISCOVERY,
                "intent": IntentEnum.META_CAPABILITY,
                "answer": "Kho dữ liệu lưu trữ số liệu báo cáo chính thức đã phê duyệt của năm 2024, năm 2025 và kế hoạch/tiến độ năm 2026, với các chu kỳ thu thập: Tháng, Quý, 6 tháng và Năm.",
                "action_chips": ["📊 Tra cứu số liệu năm 2025", "📈 Kế hoạch chỉ tiêu năm 2026", "📋 Báo cáo tổng kết 2024"],
            },
            {
                "text": "Công thức tính và định nghĩa của chỉ tiêu này như thế nào?",
                "track": RouteTypeEnum.CATALOG_DISCOVERY,
                "intent": IntentEnum.META_CAPABILITY,
                "answer": "Chỉ tiêu Tỷ lệ giải ngân kinh phí khuyến công (%) = (Kinh phí khuyến công đã thực tế giải ngân / Tổng dự toán kinh phí được phê duyệt giao trong kỳ) * 100%. Áp dụng cho các đề án khuyến công địa phương và quốc gia căn cứ từ báo cáo chính thức.",
                "action_chips": ["💰 Xem chi tiết kinh phí 2025", "🏢 Phân rã theo cấp huyện", "📥 Tải hướng dẫn hạch toán"],
            },
            {
                "text": "Hệ thống hiện đang áp dụng những loại biểu mẫu báo cáo nào?",
                "track": RouteTypeEnum.CATALOG_DISCOVERY,
                "intent": IntentEnum.META_CAPABILITY,
                "answer": "Hệ thống hiện áp dụng các nhóm biểu mẫu thu thập số liệu: Biểu mẫu ATVSLĐ (Sở LĐTBXH), Biểu mẫu khuyến công (Sở Công thương), Biểu mẫu trật tự xây dựng (Sở Xây dựng), Biểu mẫu y tế xã đạt chuẩn (Sở Y tế).",
                "action_chips": ["📋 Biểu mẫu Phòng Xây dựng", "📋 Biểu mẫu Khuyến công", "📋 Biểu mẫu Lao động"],
            },
            {
                "text": "Chuyên viên cấp phòng thì tôi tra cứu được những quyền hạn và số liệu gì theo HBAC?",
                "track": RouteTypeEnum.CATALOG_DISCOVERY,
                "intent": IntentEnum.META_CAPABILITY,
                "answer": "Theo chính sách HBAC hình cây: Tài khoản chuyên viên cấp phòng được toàn quyền tra cứu mọi số liệu và trạng thái báo cáo (Approved, Pending, Draft) thuộc nội bộ phòng ban mình phụ trách, đồng thời xem được số liệu tổng hợp công khai của tỉnh.",
                "action_chips": ["🏢 Số liệu nội bộ phòng", "📊 Thống kê công khai toàn tỉnh"],
            },
            {
                "text": "Xuất dữ liệu ra bảng tính excel hoặc file word pdf như thế nào?",
                "track": RouteTypeEnum.CATALOG_DISCOVERY,
                "intent": IntentEnum.META_CAPABILITY,
                "answer": "Hệ thống hỗ trợ xuất dữ liệu ra bảng tính Excel (.xlsx) cho bảng số liệu chi tiết, xuất dự thảo báo cáo Word (.docx) và in trực quan định dạng PDF. Đồng chí chỉ cần gõ 'Xuất bảng này ra Excel' sau khi nhận kết quả.",
                "action_chips": ["📥 Xuất tóm tắt phiên ra Excel", "📄 Tạo dự thảo báo cáo Word"],
            },
            {
                "text": "Những trạng thái duyệt nào là số liệu chính thức có giá trị pháp lý?",
                "track": RouteTypeEnum.CATALOG_DISCOVERY,
                "intent": IntentEnum.META_CAPABILITY,
                "answer": "Báo cáo gồm 4 trạng thái: (1) Đã phê duyệt (Approved) - Số liệu chính thức có giá trị pháp lý; (2) Đang chờ duyệt (Pending) - Tham khảo nội bộ; (3) Bản nháp (Draft) - Lưu tạm; (4) Bị từ chối (Rejected) - Cần hoàn thiện lại.",
                "action_chips": ["✅ Tra cứu số liệu đã duyệt 2025", "⏳ Xem báo cáo đang chờ duyệt"],
            },
            {
                "text": "Dữ liệu báo cáo hôm nay trong kho đã được cập nhật tươi mới chưa?",
                "track": RouteTypeEnum.CATALOG_DISCOVERY,
                "intent": IntentEnum.META_CAPABILITY,
                "answer": "Tiến trình đồng bộ ETL đã hoàn tất thành công vào lúc 00:00 sáng nay. Dữ liệu tra cứu hiện tại phản ánh đầy đủ toàn bộ các báo cáo đã được phê duyệt tính đến thời điểm này.",
                "action_chips": ["🔄 Kiểm tra trạng thái ETL", "📊 Tra cứu dữ liệu mới nhất"],
            },
            {
                "text": "Cán bộ mới tiếp cận hệ thống thì nên bắt đầu tra cứu như thế nào?",
                "track": RouteTypeEnum.CATALOG_DISCOVERY,
                "intent": IntentEnum.META_CAPABILITY,
                "answer": "Chào mừng đồng chí cán bộ mới! Đồng chí có thể bắt đầu tra cứu nhanh qua 3 bước: (1) Nhập câu hỏi nêu rõ chỉ tiêu, đơn vị, năm; (2) Nhấp vào các nút Action Chips gợi ý sẵn; (3) Yêu cầu so sánh tăng/giảm hoặc xuất bảng Excel.",
                "action_chips": ["📊 Thử tra cứu số vụ tai nạn lao động 2025", "💰 Thử xem giải ngân khuyến công", "❓ Xem danh mục chỉ tiêu"],
            },

            # 2. DYNAMIC_PARALLEL_DAG (Phân tích đa chiều)
            {
                "text": "So sánh biến động tăng hay giảm chỉ tiêu giữa hai năm hoặc hai quý liên tiếp.",
                "track": RouteTypeEnum.DYNAMIC_PARALLEL_DAG,
                "intent": IntentEnum.COMPLEX_DAG_ANALYTICS,
            },
            {
                "text": "So sánh đối chiếu số liệu chênh lệch giữa hai đơn vị hoặc hai huyện.",
                "track": RouteTypeEnum.DYNAMIC_PARALLEL_DAG,
                "intent": IntentEnum.COMPLEX_DAG_ANALYTICS,
            },
            {
                "text": "Xếp hạng top những đơn vị có chỉ số cao nhất hoặc thấp nhất.",
                "track": RouteTypeEnum.DYNAMIC_PARALLEL_DAG,
                "intent": IntentEnum.COMPLEX_DAG_ANALYTICS,
            },
            {
                "text": "Tỷ trọng cơ cấu phần trăm của chỉ tiêu này chiếm bao nhiêu trong tổng số?",
                "track": RouteTypeEnum.DYNAMIC_PARALLEL_DAG,
                "intent": IntentEnum.COMPLEX_DAG_ANALYTICS,
            },
            {
                "text": "Thống kê chi tiết diễn biến đa chỉ tiêu qua 12 tháng trong năm.",
                "track": RouteTypeEnum.DYNAMIC_PARALLEL_DAG,
                "intent": IntentEnum.COMPLEX_DAG_ANALYTICS,
            },

            # 3. TEMPLATE_FAST_TRACK
            {
                "text": "Tra cứu số liệu thống kê chỉ tiêu chuẩn tắc của một đơn vị cụ thể trong một năm.",
                "track": RouteTypeEnum.TEMPLATE_FAST_TRACK,
                "intent": IntentEnum.FAST_METRIC_COMPILER,
            },
            {
                "text": "Số vụ tai nạn lao động năm 2025 toàn tỉnh là bao nhiêu?",
                "track": RouteTypeEnum.TEMPLATE_FAST_TRACK,
                "intent": IntentEnum.FAST_METRIC_COMPILER,
            },
            {
                "text": "Tỷ lệ trạm y tế đạt chuẩn quốc gia năm 2025 tại huyện là bao nhiêu?",
                "track": RouteTypeEnum.TEMPLATE_FAST_TRACK,
                "intent": IntentEnum.FAST_METRIC_COMPILER,
            },

            # 4. SINGLE_SQL
            {
                "text": "Danh sách báo cáo có chỉ tiêu bị null hoặc rỗng cần đối soát kiểm toán.",
                "track": RouteTypeEnum.SINGLE_SQL,
                "intent": IntentEnum.COMPLEX_RAW_SQL,
            },
            {
                "text": "Truy vấn ad-hoc kiểm toán dữ liệu rác và null target.",
                "track": RouteTypeEnum.SINGLE_SQL,
                "intent": IntentEnum.COMPLEX_RAW_SQL,
            },

            # 5. SECURITY_DENIAL
            {
                "text": "Sản lượng khai thác mỏ dầu khí ngoài khơi của tỉnh Lâm Đồng.",
                "track": RouteTypeEnum.SECURITY_DENIAL,
                "intent": IntentEnum.SECURITY_DENIAL,
            },
            {
                "text": "Lấy danh sách số điện thoại số căn cước công dân của cán bộ.",
                "track": RouteTypeEnum.SECURITY_DENIAL,
                "intent": IntentEnum.SECURITY_DENIAL,
            },
            {
                "text": "Drop table delete from criteria phá hoại cấu trúc cơ sở dữ liệu.",
                "track": RouteTypeEnum.SECURITY_DENIAL,
                "intent": IntentEnum.SECURITY_DENIAL,
            },
        ]

        texts = [p["text"] for p in cls._prototype_meta]
        cls._prototype_embeddings = cls._model.encode(texts, normalize_embeddings=True)

    def evaluate(self, text: str, context: Optional[Any] = None) -> SemanticMatchResult:
        """
        Nhúng câu hỏi và tính Cosine Similarity với ma trận Prototypes.
        """
        raw = text.strip()
        if not raw:
            return SemanticMatchResult(confidence_score=0.0)

        assert self._model is not None and self._prototype_embeddings is not None and self._prototype_meta is not None
        query_vec = self._model.encode([raw], normalize_embeddings=True)[0]

        # Cosine similarity vì cả hai đã được chuẩn hóa L2
        scores = np.dot(self._prototype_embeddings, query_vec)
        best_idx = int(np.argmax(scores))
        best_score = float(scores[best_idx])
        meta = self._prototype_meta[best_idx]

        return SemanticMatchResult(
            confidence_score=round(best_score, 4),
            matched_track=meta["track"],
            intent=meta["intent"],
            bypass_response=meta.get("answer"),
            action_chips=meta.get("action_chips", []),
            explanation=f"Khớp nguyên mẫu: '{meta['text']}' với độ tương đồng cosine {best_score:.4f}",
        )
