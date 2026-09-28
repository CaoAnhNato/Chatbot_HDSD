"""
IPGov Chatbot - Module 03: Redis Distributed Session Manager
Quản lý bộ nhớ phiên phân tán bằng Redis (Redis Core: String JSON, List, TTL):
- ActiveQuestFrame: JSON Object lưu trữ khung slot nghiệp vụ H-DFT.
- Sliding Window Messages: Redis List lưu trữ các lượt đối thoại gần nhất (Trim).
- SessionEpisodicMemory: Lưu trữ sở thích, mốc năm mặc định và lịch sử quest.
- Semantic Decision Cache: Cache kết quả định tuyến Lượt 1 trong Redis với TTL 1 giờ.
- Sliding Expiration: Tự động gia hạn TTL 1800s (30 phút) sau mỗi tin nhắn mới.
Căn cứ: Blueprints 00_TECH_STACK, 05_MULTI_AGENT_WORKFLOW, .agents/rules/ipgov-coding-rules.md
"""

from __future__ import annotations
import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import redis
from pydantic import ValidationError

from IPGov_Chatbot.config import settings
from IPGov_Chatbot.schemas.router_dto import (
    ActiveQuestFrameDTO,
    SessionEpisodicMemoryDTO,
)

logger = logging.getLogger("ipgov.redis_session")


class RedisSessionManager:
    """
    Quản lý phiên làm việc tập trung qua Redis Core (String, List, Hash, TTL).
    Hỗ trợ Connection Pooling, tự động thử lại khi timeout và Sliding Expiration.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: Optional[int] = None,
        password: Optional[str] = None,
        socket_timeout: Optional[float] = None,
    ) -> None:
        self.host = host or getattr(settings, "REDIS_HOST", "localhost")
        self.port = port or getattr(settings, "REDIS_PORT", 6379)
        self.db = db if db is not None else getattr(settings, "REDIS_DB", 0)
        self.password = password or getattr(settings, "REDIS_PASSWORD", None)
        self.socket_timeout = socket_timeout or getattr(settings, "REDIS_SOCKET_TIMEOUT", 0.5)
        self.socket_connect_timeout = getattr(settings, "REDIS_SOCKET_CONNECT_TIMEOUT", 0.2)
        self.enabled = getattr(settings, "REDIS_ENABLED", True)
        self.ttl = getattr(settings, "SESSION_TTL_SECONDS", 1800)
        self.max_turns = getattr(settings, "SESSION_MAX_HISTORY_TURNS", 3)
        self.decision_cache_ttl = getattr(settings, "DECISION_CACHE_TTL_SECONDS", 3600)
        self._available: Optional[bool] = None
        self._last_ping: float = 0.0
        self._local_cache: Dict[str, Any] = {}

        # Khởi tạo Connection Pool
        self.pool = redis.ConnectionPool(
            host=self.host,
            port=self.port,
            db=self.db,
            password=self.password,
            socket_timeout=self.socket_timeout,
            socket_connect_timeout=self.socket_connect_timeout,
            retry_on_timeout=False,
            max_connections=getattr(settings, "REDIS_MAX_CONNECTIONS", 20),
            decode_responses=True,
        )
        self.client = redis.Redis(connection_pool=self.pool)

    def ping(self) -> bool:
        """Kiểm tra tính sẵn sàng của Redis Server với Circuit Breaker 5s cache."""
        now = time.perf_counter()
        if self._available is not None and (now - self._last_ping < 5.0):
            return self._available
        try:
            res = bool(self.client.ping())
            self._available = res
        except Exception:
            self._available = False
        self._last_ping = now
        return self._available

    # ==============================================================================
    # 1. QUẢN LÝ ACTIVE QUEST FRAME (H-DFT WORKING MEMORY)
    # ==============================================================================
    def get_active_quest(self, session_id: str) -> Optional[ActiveQuestFrameDTO]:
        """Lấy ActiveQuestFrameDTO hiện tại của phiên từ Redis (hoặc In-Memory fallback)."""
        key = f"session:{session_id}:active_quest"
        if not self.ping():
            raw_data = self._local_cache.get(key)
            if not raw_data:
                return None
            try:
                data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                return ActiveQuestFrameDTO.model_validate(data)
            except Exception:
                return None
        try:
            raw_data = self.client.get(key)
            if not raw_data:
                return None
            data = json.loads(raw_data)
            return ActiveQuestFrameDTO.model_validate(data)
        except ValidationError as ve:
            logger.warning(f"Lỗi validate ActiveQuestFrameDTO ({session_id}): {ve}. Reset frame.")
            self.client.delete(key)
            return None
        except Exception as e:
            logger.error(f"Lỗi đọc active_quest từ Redis ({session_id}): {e}")
            return None

    def save_active_quest(
        self, session_id: str, quest: Optional[ActiveQuestFrameDTO]
    ) -> None:
        """Lưu hoặc xóa ActiveQuestFrameDTO trong Redis và gia hạn TTL trượt 30 phút."""
        key = f"session:{session_id}:active_quest"
        if not self.ping():
            if quest is None:
                self._local_cache.pop(key, None)
            else:
                self._local_cache[key] = quest.model_dump(mode="json")
            return
        try:
            if quest is None:
                self.client.delete(key)
                return
            payload = quest.model_dump(mode="json")
            self.client.set(key, json.dumps(payload, ensure_ascii=False), ex=self.ttl)
        except Exception as e:
            logger.error(f"Lỗi lưu active_quest vào Redis ({session_id}): {e}")

    # ==============================================================================
    # 2. QUẢN LÝ SESSION EPISODIC MEMORY (TEMP MEMORY)
    # ==============================================================================
    def get_temp_memory(self, session_id: str) -> SessionEpisodicMemoryDTO:
        """Lấy hồ sơ ngữ cảnh phiên SessionEpisodicMemoryDTO từ Redis."""
        key = f"session:{session_id}:temp_memory"
        if not self.ping():
            raw_data = self._local_cache.get(key)
            if not raw_data:
                default_mem = SessionEpisodicMemoryDTO(
                    session_id=session_id,
                    default_temporal_window="2025",
                    last_updated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
                )
                self.save_temp_memory(session_id, default_mem)
                return default_mem
            data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
            return SessionEpisodicMemoryDTO.model_validate(data)
        try:
            raw_data = self.client.get(key)
            if not raw_data:
                default_mem = SessionEpisodicMemoryDTO(
                    session_id=session_id,
                    default_temporal_window="2025",
                    last_updated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
                )
                self.save_temp_memory(session_id, default_mem)
                return default_mem
            data = json.loads(raw_data)
            return SessionEpisodicMemoryDTO.model_validate(data)
        except Exception as e:
            logger.error(f"Lỗi đọc temp_memory từ Redis ({session_id}): {e}")
            return SessionEpisodicMemoryDTO(session_id=session_id, default_temporal_window="2025")

    def save_temp_memory(
        self, session_id: str, temp_memory: SessionEpisodicMemoryDTO
    ) -> None:
        """Lưu hồ sơ ngữ cảnh phiên SessionEpisodicMemoryDTO và gia hạn TTL."""
        key = f"session:{session_id}:temp_memory"
        if not self.ping():
            self._local_cache[key] = temp_memory.model_dump(mode="json")
            return
        try:
            payload = temp_memory.model_dump(mode="json")
            self.client.set(key, json.dumps(payload, ensure_ascii=False), ex=self.ttl)
        except Exception as e:
            logger.error(f"Lỗi lưu temp_memory vào Redis ({session_id}): {e}")

    # ==============================================================================
    # 3. QUẢN LÝ LỊCH SỬ TIN NHẮN (SLIDING WINDOW TRIM)
    # ==============================================================================
    def append_message(self, session_id: str, role: str, content: str) -> None:
        """
        Thêm một tin nhắn vào Redis List và cắt tỉa (Trim) chỉ giữ tối đa
        2 * SESSION_MAX_HISTORY_TURNS tin nhắn gần nhất.
        """
        key = f"session:{session_id}:messages"
        msg_obj = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
        }
        max_items = self.max_turns * 2  # Ví dụ 3 turns = 6 messages (3 user + 3 assistant)
        if not self.ping():
            msgs = self._local_cache.setdefault(key, [])
            msgs.append(msg_obj)
            if len(msgs) > max_items:
                self._local_cache[key] = msgs[-max_items:]
            return
        try:
            pipe = self.client.pipeline()
            pipe.rpush(key, json.dumps(msg_obj, ensure_ascii=False))
            # Giữ lại max_items phần tử cuối cùng
            pipe.ltrim(key, -max_items, -1)
            pipe.expire(key, self.ttl)
            pipe.execute()
        except Exception as e:
            logger.error(f"Lỗi thêm tin nhắn vào Redis Sliding Window ({session_id}): {e}")

    def get_recent_messages(
        self,
        session_id: str,
        limit: Optional[int] = None,
        max_turns: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        """Lấy danh sách các tin nhắn gần nhất theo thứ tự thời gian tăng dần."""
        key = f"session:{session_id}:messages"
        effective_limit = limit
        if max_turns is not None:
            effective_limit = max_turns * 2
        if not self.ping():
            msgs = self._local_cache.get(key, [])
            if effective_limit and len(msgs) > effective_limit:
                return msgs[-effective_limit:]
            return msgs
        try:
            raw_list = self.client.lrange(key, 0, -1)
            messages = [json.loads(item) for item in raw_list]
            if effective_limit and len(messages) > effective_limit:
                return messages[-effective_limit:]
            return messages
        except Exception as e:
            logger.error(f"Lỗi đọc recent messages từ Redis ({session_id}): {e}")
            return []

    # ==============================================================================
    # 4. GÓI DỮ LIỆU ĐỒNG THỜI (SESSION BUNDLE)
    # ==============================================================================
    def get_session_bundle(
        self, session_id: str
    ) -> Tuple[Optional[ActiveQuestFrameDTO], SessionEpisodicMemoryDTO, List[Dict[str, str]]]:
        """
        Đọc đồng thời toàn bộ gói dữ liệu phiên:
        1. active_quest (Khung slot hiện tại)
        2. temp_memory (Hồ sơ phiên)
        3. recent_messages (Danh sách tin nhắn gần nhất)
        """
        quest = self.get_active_quest(session_id)
        temp_mem = self.get_temp_memory(session_id)
        messages = self.get_recent_messages(session_id)
        return quest, temp_mem, messages

    def reset_active_quest_and_archive(self, session_id: str) -> None:
        """
        Lưu trữ Quest hiện tại vào danh sách lịch sử của temp_memory và reset ActiveQuestFrame.
        Áp dụng khi phát hiện chuyển chủ đề (Topic Shift) hoặc khi Quest đã hoàn thành.
        """
        quest = self.get_active_quest(session_id)
        if quest:
            temp_mem = self.get_temp_memory(session_id)
            if quest.quest_id not in temp_mem.committed_quest_history:
                temp_mem.committed_quest_history.append(quest.quest_id)
                self.save_temp_memory(session_id, temp_mem)
        self.save_active_quest(session_id, None)

    # ==============================================================================
    # 5. SEMANTIC DECISION CACHE (LƯỢT 1 SINGLE-TURN ONLY)
    # ==============================================================================
    @staticmethod
    def hash_prompt(prompt: str) -> str:
        """Tạo khóa băm SHA256 chuẩn hóa cho chuỗi prompt."""
        normalized = " ".join(prompt.lower().strip().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def get_decision_cache(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Lấy kết quả định tuyến đã cache trong Redis cho câu hỏi Lượt 1."""
        if not getattr(settings, "ENABLE_DECISION_CACHE", True):
            return None
        prompt_hash = self.hash_prompt(prompt)
        key = f"cache:router:{prompt_hash}"
        if not self.ping():
            raw_data = self._local_cache.get(key)
            if not raw_data:
                return None
            return json.loads(raw_data) if isinstance(raw_data, str) else raw_data
        try:
            raw_data = self.client.get(key)
            if not raw_data:
                return None
            return json.loads(raw_data)
        except Exception as e:
            logger.debug(f"Lỗi đọc decision cache ({key}): {e}")
            return None

    def set_decision_cache(
        self, prompt: str, output_dict: Dict[str, Any]
    ) -> None:
        """Lưu kết quả định tuyến vào Redis với TTL 1 giờ (Chỉ áp dụng Lượt 1)."""
        if not getattr(settings, "ENABLE_DECISION_CACHE", True):
            return
        prompt_hash = self.hash_prompt(prompt)
        key = f"cache:router:{prompt_hash}"
        if not self.ping():
            self._local_cache[key] = output_dict
            return
        try:
            payload = json.dumps(output_dict, ensure_ascii=False)
            self.client.set(key, payload, ex=self.decision_cache_ttl)
        except Exception as e:
            logger.debug(f"Lỗi lưu decision cache ({key}): {e}")

    def clear_decision_cache(self) -> None:
        """Xóa toàn bộ các khóa cache:router:* trong Redis."""
        try:
            keys = self.client.keys("cache:router:*")
            if keys:
                self.client.delete(*keys)
        except Exception as e:
            logger.debug(f"Lỗi clear decision cache: {e}")

    def clear_session(self, session_id: str) -> None:
        """Xóa toàn bộ các khóa liên quan đến một phiên làm việc."""
        try:
            keys = self.client.keys(f"session:{session_id}:*")
            if keys:
                self.client.delete(*keys)
        except Exception as e:
            logger.debug(f"Lỗi clear session ({session_id}): {e}")
        keys = [
            f"session:{session_id}:active_quest",
            f"session:{session_id}:temp_memory",
            f"session:{session_id}:messages",
        ]
        try:
            self.client.delete(*keys)
        except Exception as e:
            logger.error(f"Lỗi xóa session Redis ({session_id}): {e}")
