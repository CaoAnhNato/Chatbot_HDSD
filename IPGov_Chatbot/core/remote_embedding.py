"""
Module: IPGov_Chatbot/core/remote_embedding.py
Chức năng: Adapter gọi trực tiếp Hugging Face Space 'Nato1306/vietnamese-embedding-api'
chạy ZeroGPU (A10G) phục vụ trích xuất vector embedding 1024 chiều (AITeamVN/Vietnamese_Embedding_v2)
mà không tốn RAM trên Render (Zero-RAM footprint).
Giao diện tương thích 100% với SentenceTransformer (.encode).
"""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from typing import Any, List, Optional, Union

import numpy as np

logger = logging.getLogger("ipgov.remote_embedding")


class RemoteHFEmbeddingModel:
    """
    Client gọi API Gradio 4/5 SSE tới Hugging Face Space ZeroGPU của người dùng.
    Hỗ trợ xử lý văn bản đơn lẻ và batch với cơ chế retry tự động.
    """

    def __init__(
        self,
        space_url: str = "https://nato1306-vietnamese-embedding-api.hf.space",
        token: Optional[str] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.space_url = space_url.rstrip("/")
        self.token = token or ""
        self.timeout_seconds = timeout_seconds

    def _call_gradio(self, endpoint: str, data_payload: List[Any], max_retries: int = 3) -> Any:
        url = f"{self.space_url}/gradio_api/call/{endpoint}"
        headers = {
            "Content-Type": "application/json",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        body = json.dumps({"data": data_payload}).encode("utf-8")

        last_error = None
        for attempt in range(max_retries):
            try:
                # 1. Gửi request khởi tạo tác vụ trên Gradio Space
                req = urllib.request.Request(url, data=body, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    event_id = resp_data.get("event_id")

                if not event_id:
                    raise ValueError(f"Không nhận được event_id từ HF Space: {resp_data}")

                # 2. Polling kết quả SSE từ event_id
                poll_url = f"{self.space_url}/gradio_api/call/{endpoint}/{event_id}"
                req_poll = urllib.request.Request(poll_url, headers=headers)

                t_end = time.time() + self.timeout_seconds
                while time.time() < t_end:
                    with urllib.request.urlopen(req_poll, timeout=15) as resp_poll:
                        raw = resp_poll.read().decode("utf-8")
                        for line in raw.splitlines():
                            if line.startswith("data:"):
                                return json.loads(line[5:].strip())
                    time.sleep(0.5)

                raise TimeoutError(f"Quá thời gian chờ ({self.timeout_seconds}s) nhận vector từ HF Space.")
            except Exception as e:
                last_error = e
                logger.warning(
                    "⚠️ [RemoteHFEmbedding] Lỗi kết nối HF Space (thử lần %d/%d): %s",
                    attempt + 1,
                    max_retries,
                    e,
                )
                if attempt < max_retries - 1:
                    time.sleep(1.0 * (attempt + 1))

        raise RuntimeError(f"Không thể kết nối HF Space sau {max_retries} lần thử: {last_error}")

    def encode(
        self,
        sentences: Union[str, List[str]],
        normalize_embeddings: bool = True,
        batch_size: int = 32,
        **kwargs: Any,
    ) -> np.ndarray:
        """
        Trích xuất vector embedding tương thích hoàn toàn với SentenceTransformer.encode.
        - Trả về np.ndarray (1024,) nếu đầu vào là 1 chuỗi ký tự (str).
        - Trả về np.ndarray (N, 1024) nếu đầu vào là danh sách (List[str]).
        """
        is_single = isinstance(sentences, str)
        if is_single:
            texts = [sentences]
        else:
            texts = list(sentences)

        if not texts:
            return np.empty((0, 1024), dtype=np.float32)

        # Xử lý theo từng batch_size nếu danh sách quá dài
        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), batch_size):
            chunk = texts[i : i + batch_size]
            batch_text = "\n".join([t.replace("\n", " ").strip() for t in chunk])
            
            res = self._call_gradio("batch_embed", [batch_text])
            if res and isinstance(res, list) and len(res) > 0:
                chunk_embs = res[0].get("embeddings", [])
                all_embeddings.extend(chunk_embs)
            else:
                logger.error("❌ [RemoteHFEmbedding] Payload phản hồi không hợp lệ: %s", res)
                raise ValueError("Payload trả về từ HF Space không đúng định dạng mong đợi.")

        arr = np.array(all_embeddings, dtype=np.float32)

        if normalize_embeddings and arr.size > 0:
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms[norms == 0] = 1e-12
            arr = arr / norms

        if is_single:
            return arr[0]
        return arr
