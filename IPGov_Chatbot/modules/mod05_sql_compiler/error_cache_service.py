"""
Module: IPGov_Chatbot/modules/mod05_sql_compiler/error_cache_service.py
Chức năng: Quản lý Redis Error Cache (cache:sql_err) và Deterministic Error-to-Constraint Mapper.
Căn cứ:
- Blueprint: 05_MULTI_AGENT_WORKFLOW_DIN_MAC_SQL.md (Mục 6)
- Specification: IPGov_Chatbot/docs/MODULE_05_SQL_COMPILER_SPEC.md (Mục 7)
- Tuân thủ TRAPS: [TRAP-004], [TRAP-005], [TRAP-015] (Redis timeout 0.2s, Circuit Breaker)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ipgov.mod05.error_cache")


def map_postgres_error_to_constraint(pg_code: str, error_msg: str) -> str:
    """
    Khối Ánh xạ Tất định theo Mã Lỗi PostgreSQL (Deterministic Error-to-Constraint Mapper).
    Thực thi thuần trong RAM (< 0.1ms, 0 LLM token).
    """
    code_clean = str(pg_code or "").strip().upper()
    err_lower = (error_msg or "").lower()

    if code_clean == "22P02" or "invalid input syntax for type numeric" in err_lower:
        return (
            "RÀNG BUỘC PHỦ ĐỊNH CỐT TỬ ([TRAP-004]): Cột `value` trong fact_report_criteria chứa chuỗi text và rỗng. "
            "TUYỆT ĐỐI CẤM ép kiểu thô `value::numeric`. BẮT BUỘC dùng: NULLIF(TRIM(f.value), '')::numeric."
        )
    elif code_clean == "42703" or "does not exist" in err_lower and "column" in err_lower:
        if "o.name" in err_lower or "name" in err_lower and "office" in err_lower:
            return (
                "RÀNG BUỘC PHỦ ĐỊNH CỘT: Bảng `dwh_internal.office` KHÔNG có cột `name`, tên cột thực tế là `office_name`. "
                "BẮT BUỘC dùng: o.office_name hoặc COALESCE(o.office_name, d.name)."
            )
        return (
            f"RÀNG BUỘC PHỦ ĐỊNH CỘT ([42703]): {error_msg}. "
            f"CHỈ ĐƯỢC DÙNG các cột vật lý có mặt trong Schema Slice DDL."
        )
    elif code_clean == "42P01" or "relation" in err_lower and "does not exist" in err_lower:
        if "department" in err_lower:
            return (
                "RÀNG BUỘC PHỦ ĐỊNH BẢNG ([TRAP-005]): Tên bảng danh mục cơ quan là `dwh_internal.deparment` "
                "(lưu ý chính tả không có chữ 't' thứ hai)."
            )
        return (
            f"RÀNG BUỘC PHỦ ĐỊNH BẢNG ([42P01]): {error_msg}. "
            f"CHỈ ĐƯỢC DÙNG các bảng vật lý có mặt trong Schema Slice DDL."
        )
    elif code_clean == "42803" or "must appear in the group by clause" in err_lower:
        return (
            "RÀNG BUỘC PHỦ ĐỊNH GROUP BY ([42803]): Mọi cột xuất hiện trong mệnh đề SELECT mà không bọc trong hàm "
            "tổng hợp (SUM, AVG, COUNT, MIN, MAX) BẮT BUỘC phải được khai báo trong GROUP BY."
        )
    elif code_clean == "42P10" or "invalid on clause" in err_lower:
        return f"RÀNG BUỘC PHỦ ĐỊNH JOIN ([42P10]): Sai điều kiện ON trong phép kết nối bảng: {error_msg}."

    return f"RÀNG BUỘC PHỦ ĐỊNH: Lỗi runtime CSDL trước đó: {error_msg}. Hãy kiểm tra kỹ cú pháp trước khi sinh."


class RedisSQLErrorCache:
    """
    Dịch vụ lưu vết lỗi và tra cứu Ràng buộc Phủ định trên Redis.
    Tuân thủ [TRAP-015]: socket_connect_timeout=0.2s, Circuit Breaker và Graceful Memory Fallback.
    """

    def __init__(
        self,
        redis_host: Optional[str] = None,
        redis_port: Optional[int] = None,
        ttl_seconds: int = 86400,  # 24 giờ
    ) -> None:
        self.host = redis_host or os.getenv("REDIS_HOST", "localhost")
        self.port = int(redis_port or os.getenv("REDIS_PORT", "6379"))
        self.ttl = ttl_seconds
        self._local_cache: Dict[str, Dict[str, Any]] = {}
        self._circuit_broken_until: float = 0.0
        self._redis_client = None
        self._init_redis()

    def _init_redis(self) -> None:
        """Khởi tạo Redis client với timeout siêu ngắn để không làm nghẽn luồng."""
        try:
            import redis
            self._redis_client = redis.Redis(
                host=self.host,
                port=self.port,
                socket_connect_timeout=0.2,
                socket_timeout=0.5,
                decode_responses=True,
            )
        except Exception as e:
            logger.debug(f"Không thể khởi tạo Redis client: {e}. Fallback sang Local Memory Cache.")
            self._redis_client = None

    def _is_circuit_open(self) -> bool:
        """Kiểm tra xem Redis có đang bị tạm ngắt do mất kết nối không."""
        return time.time() < self._circuit_broken_until

    def _trip_circuit(self, duration: float = 5.0) -> None:
        """Tạm ngắt Redis trong 5 giây nếu gặp lỗi timeout/network."""
        self._circuit_broken_until = time.time() + duration

    def compute_cache_key(self, prompt: str, candidate_tables: Optional[List[str]] = None) -> str:
        """Tạo khóa cache SHA-256 từ câu hỏi và danh sách bảng."""
        tables_str = ",".join(sorted(candidate_tables or []))
        raw = f"{prompt.strip().lower()}|{tables_str.lower()}"
        hash_val = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"cache:sql_err:{hash_val}"

    def get_error_trace(self, prompt: str, candidate_tables: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Tra cứu vết lỗi trước đó. Trả về payload lỗi hoặc None."""
        key = self.compute_cache_key(prompt, candidate_tables)

        # 1. Thử lấy từ Redis nếu khả dụng
        if self._redis_client and not self._is_circuit_open():
            try:
                data_str = self._redis_client.get(key)
                if data_str:
                    return json.loads(data_str)
            except Exception as e:
                logger.debug(f"Redis get error: {e}. Fallback sang Local Cache.")
                self._trip_circuit()

        # 2. Fallback sang Local Memory Cache
        return self._local_cache.get(key)

    def record_error(
        self,
        prompt: str,
        failed_sql: str,
        error_layer: str,
        pg_code: str,
        error_message: str,
        candidate_tables: Optional[List[str]] = None,
    ) -> str:
        """Lưu vết lỗi vào Redis và trả về câu Ràng buộc Phủ định."""
        key = self.compute_cache_key(prompt, candidate_tables)
        neg_constraint = map_postgres_error_to_constraint(pg_code, error_message)

        payload = {
            "failed_sql": failed_sql,
            "error_layer": error_layer,
            "pg_code": pg_code,
            "error_message": error_message,
            "negative_constraint": neg_constraint,
            "occurrence_count": 1,
            "last_failed_at": time.time(),
        }

        # Lưu vào Local Cache
        existing = self._local_cache.get(key)
        if existing:
            payload["occurrence_count"] = existing.get("occurrence_count", 1) + 1
        self._local_cache[key] = payload

        # Lưu vào Redis nếu khả dụng
        if self._redis_client and not self._is_circuit_open():
            try:
                self._redis_client.set(key, json.dumps(payload, ensure_ascii=False), ex=self.ttl)
            except Exception as e:
                logger.debug(f"Redis set error: {e}. Fallback sang Local Cache.")
                self._trip_circuit()

        return neg_constraint

    def clear(self) -> None:
        """Xóa toàn bộ cache (dùng trong test fixtures)."""
        self._local_cache.clear()
        if self._redis_client and not self._is_circuit_open():
            try:
                keys = self._redis_client.keys("cache:sql_err:*")
                if keys:
                    self._redis_client.delete(*keys)
            except Exception:
                pass
