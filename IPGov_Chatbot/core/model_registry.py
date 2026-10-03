"""
Module: IPGov_Chatbot/core/model_registry.py
Chức năng: Quản lý vòng đời mô hình học máy (Model Lifecycle Management) cấp độ Process.
Áp dụng mẫu thiết kế Process-Level Singleton & Thread-Safe Double-Checked Locking:
- Đảm bảo SentenceTransformer chỉ tồn tại ĐÚNG 1 BẢN SAO trong toàn bộ tiến trình Python.
- Ngăn chặn triệt để Memory Leak (OOM) khi các module khởi tạo nhiều Catalog / Pruner instances.
- Hỗ trợ Pre-warm JIT graph & tensor buffers qua Dummy Forward-Pass.
- Phục vụ Non-blocking Lifespan Hydration cho FastAPI.
Căn cứ: Seldon Core Architecture, implementation_plan.md v1.5.0
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Optional

from IPGov_Chatbot.config import settings

logger = logging.getLogger("ipgov.model_registry")


class ModelRegistry:
    """
    Process-Level Singleton Registry quản lý tập trung các mô hình ML trong bộ nhớ RAM.
    """
    _instance_lock = threading.RLock()
    _embed_model: Optional[Any] = None
    _is_warmed_up: bool = False
    _model_name: Optional[str] = None
    _warmup_time_ms: float = 0.0

    @classmethod
    def get_embedding_model(cls, model_name: Optional[str] = None) -> Any:
        """
        Lấy đối tượng mô hình embedding đã nạp sẵn trong RAM hoặc Remote HF Space.
        Nếu chưa có, thực hiện nạp an toàn đa luồng (Double-Checked Locking).
        Ưu tiên RemoteHFEmbeddingModel (Zero-RAM Cloud) khi USE_REMOTE_EMBEDDING=True.
        """
        target_name = model_name or getattr(settings, "EMBEDDING_MODEL_NAME", "AITeamVN/Vietnamese_Embedding_v2")
        use_remote = getattr(settings, "USE_REMOTE_EMBEDDING", True)

        if cls._embed_model is None or cls._model_name != target_name:
            with cls._instance_lock:
                if cls._embed_model is None or cls._model_name != target_name:
                    t0 = time.perf_counter()

                    if use_remote:
                        logger.info("⚡ [ModelRegistry] Kết nối Remote HuggingFace Space ZeroGPU (%s)...", getattr(settings, "HF_EMBEDDING_SPACE_URL", ""))
                        from IPGov_Chatbot.core.remote_embedding import RemoteHFEmbeddingModel
                        space_url = getattr(settings, "HF_EMBEDDING_SPACE_URL", "https://nato1306-vietnamese-embedding-api.hf.space")
                        token = getattr(settings, "HF_TOKEN", "")
                        cls._embed_model = RemoteHFEmbeddingModel(space_url=space_url, token=token)
                        cls._model_name = target_name
                        cls._warmup_time_ms = (time.perf_counter() - t0) * 1000
                        logger.info("✅ [ModelRegistry] Khởi tạo RemoteHFEmbeddingModel thành công (Zero-RAM mode).")
                        return cls._embed_model

                    logger.info("⚡ [ModelRegistry] Đang nạp SentenceTransformer vào RAM: %s...", target_name)
                    try:
                        from sentence_transformers import SentenceTransformer
                        try:
                            # Ưu tiên nạp từ local cache để tránh nghẽn mạng HTTPS tới HuggingFace Hub
                            cls._embed_model = SentenceTransformer(target_name, local_files_only=True)
                        except Exception:
                            cls._embed_model = SentenceTransformer(target_name)
                        cls._model_name = target_name
                        cls._warmup_time_ms = (time.perf_counter() - t0) * 1000
                        logger.info(
                            "✅ [ModelRegistry] Nạp model local thành công trong %.1f ms (%s).",
                            cls._warmup_time_ms,
                            target_name
                        )
                    except Exception as e:
                        logger.warning("⚠️ [ModelRegistry] Không thể nạp SentenceTransformer local (%s). Fallback sang RemoteHFEmbeddingModel...", e)
                        from IPGov_Chatbot.core.remote_embedding import RemoteHFEmbeddingModel
                        space_url = getattr(settings, "HF_EMBEDDING_SPACE_URL", "https://nato1306-vietnamese-embedding-api.hf.space")
                        token = getattr(settings, "HF_TOKEN", "")
                        cls._embed_model = RemoteHFEmbeddingModel(space_url=space_url, token=token)
                        cls._model_name = target_name
                        cls._warmup_time_ms = (time.perf_counter() - t0) * 1000
                        logger.info("✅ [ModelRegistry] Fallback RemoteHFEmbeddingModel thành công.")

        return cls._embed_model

    @classmethod
    def warmup_embedding_model(cls, model_name: Optional[str] = None) -> None:
        """
        Thực hiện Warm-up chủ động:
        1. Nạp trọng số mô hình vào RAM (391 tensors).
        2. Chạy 1 chuỗi Dummy Inference Forward-Pass để biên dịch đồ thị PyTorch và cấp phát bộ nhớ tensor cache.
        """
        if not cls._is_warmed_up:
            with cls._instance_lock:
                if not cls._is_warmed_up:
                    t0 = time.perf_counter()
                    model = cls.get_embedding_model(model_name)
                    logger.info("🔥 [ModelRegistry] Bắt đầu Warm-up Dummy Forward-Pass...")
                    _ = model.encode(
                        ["Khởi động hệ thống IPGov DWH phục vụ điều hành tỉnh Lâm Đồng"],
                        normalize_embeddings=True
                    )
                    cls._is_warmed_up = True
                    elapsed = (time.perf_counter() - t0) * 1000
                    logger.info("🔥 [ModelRegistry] Warm-up Dummy Inference hoàn tất trong %.1f ms (Sẵn sàng phục vụ request < 1s).", elapsed)

    @classmethod
    def is_warmed_up(cls) -> bool:
        """Kiểm tra mô hình đã được warm-up sẵn sàng chưa."""
        return cls._is_warmed_up

    @classmethod
    def reset(cls) -> None:
        """Xóa cache mô hình (chỉ dùng trong testing)."""
        with cls._instance_lock:
            cls._embed_model = None
            cls._is_warmed_up = False
            cls._model_name = None
            cls._warmup_time_ms = 0.0
