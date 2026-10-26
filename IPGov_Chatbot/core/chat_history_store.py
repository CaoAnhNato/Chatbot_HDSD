"""
Module: IPGov_Chatbot/core/chat_history_store.py
Chức năng: Lưu trữ bền vững lịch sử phiên hội thoại (Chat Sessions & Messages) bằng SQLite.
Đảm bảo đồng bộ 2 chiều (Dual-Layer Persistence) với Frontend Next.js (localStorage + Backend SQLite).
"""

import json
import logging
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PREFIX_RE = re.compile(
    r"^\[\s*tenant_code\s*[=:]\s*[^,\]]+\s*,\s*level\s*[=:]\s*\d+\s*\]\s*",
    re.IGNORECASE,
)


def _clean_title_from_prompt(prompt: str) -> str:
    cleaned = _PREFIX_RE.sub("", (prompt or "").strip()).strip()
    if not cleaned:
        return "Cuộc hội thoại mới"
    return f"{cleaned[:42]}..." if len(cleaned) > 42 else cleaned


class ChatHistoryStore:
    """Kho lưu trữ SQLite bền vững cho danh sách phiên chat và lịch sử tin nhắn."""

    _instance: Optional["ChatHistoryStore"] = None
    _lock = threading.Lock()

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            data_dir = Path(__file__).resolve().parents[1] / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = data_dir / "chat_history.sqlite3"
        self.db_path = db_path
        self._db_lock = threading.Lock()
        self._init_db()

    @classmethod
    def get_instance(cls) -> "ChatHistoryStore":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        try:
            with self._db_lock, self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chat_sessions (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT 'phuong',
                        level INTEGER NOT NULL DEFAULT 0,
                        tenant_code TEXT NOT NULL DEFAULT '68',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        seq INTEGER NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        tabular_data_json TEXT,
                        quick_action_chips_json TEXT,
                        timestamp TEXT NOT NULL,
                        FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_chat_messages_session_seq ON chat_messages(session_id, seq)"
                )
                conn.commit()
        except Exception as exc:
            logger.warning("Failed to initialize chat_history.sqlite3: %s", exc)

    def save_turn(
        self,
        session_id: str,
        user_prompt: str,
        assistant_answer: str,
        role: str = "phuong",
        level: int = 0,
        tenant_code: str = "68",
        tabular_data: Optional[Dict[str, Any]] = None,
        quick_action_chips: Optional[List[Any]] = None,
    ) -> None:
        if not session_id or session_id == "default_session":
            return
        now_iso = datetime.now(timezone.utc).isoformat()
        title = _clean_title_from_prompt(user_prompt)

        try:
            tabular_json = json.dumps(tabular_data, ensure_ascii=False) if tabular_data else None
        except Exception:
            tabular_json = None

        try:
            chips_json = json.dumps(quick_action_chips, ensure_ascii=False) if quick_action_chips else None
        except Exception:
            chips_json = None

        try:
            with self._db_lock, self._connect() as conn:
                existing = conn.execute(
                    "SELECT id, title, created_at FROM chat_sessions WHERE id = ?",
                    (session_id,),
                ).fetchone()
                if existing is None:
                    conn.execute(
                        """
                        INSERT INTO chat_sessions (id, title, role, level, tenant_code, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (session_id, title, role or "phuong", int(level or 0), tenant_code or "68", now_iso, now_iso),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE chat_sessions
                        SET updated_at = ?, role = COALESCE(?, role), level = COALESCE(?, level), tenant_code = COALESCE(?, tenant_code)
                        WHERE id = ?
                        """,
                        (now_iso, role, int(level if level is not None else 0), tenant_code, session_id),
                    )

                max_seq_row = conn.execute(
                    "SELECT COALESCE(MAX(seq), 0) AS max_seq FROM chat_messages WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                next_seq = int(max_seq_row["max_seq"] if max_seq_row else 0) + 1

                user_msg_id = f"{session_id}-u-{next_seq}"
                bot_msg_id = f"{session_id}-b-{next_seq + 1}"

                conn.execute(
                    """
                    INSERT OR REPLACE INTO chat_messages
                    (id, session_id, seq, role, content, tabular_data_json, quick_action_chips_json, timestamp)
                    VALUES (?, ?, ?, 'user', ?, NULL, NULL, ?)
                    """,
                    (user_msg_id, session_id, next_seq, user_prompt, now_iso),
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO chat_messages
                    (id, session_id, seq, role, content, tabular_data_json, quick_action_chips_json, timestamp)
                    VALUES (?, ?, ?, 'assistant', ?, ?, ?, ?)
                    """,
                    (bot_msg_id, session_id, next_seq + 1, assistant_answer, tabular_json, chips_json, now_iso),
                )
                conn.commit()
        except Exception as exc:
            logger.warning("Failed to save chat turn for session %s: %s", session_id, exc)

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            with self._db_lock, self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT id, title, role, level, tenant_code, created_at, updated_at
                    FROM chat_sessions
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (max(1, int(limit)),),
                ).fetchall()
                result: List[Dict[str, Any]] = []
                for r in rows:
                    msgs = self._fetch_messages_conn(conn, r["id"])
                    result.append(
                        {
                            "id": r["id"],
                            "title": r["title"],
                            "role": r["role"],
                            "level": r["level"],
                            "tenant_code": r["tenant_code"],
                            "createdAt": r["created_at"],
                            "updatedAt": r["updated_at"],
                            "messages": msgs,
                        }
                    )
                return result
        except Exception as exc:
            logger.warning("Failed to list chat sessions: %s", exc)
            return []

    def _hydrate_legacy_timeline_values(
        self,
        conn: sqlite3.Connection,
        msg_id: str,
        content: str,
        td: Dict[str, Any],
        chips: Optional[List[Dict[str, Any]]],
    ) -> bool:
        t_rows = td.get("rows")
        if not isinstance(t_rows, list) or not t_rows:
            return False

        needs_row_hydration = any(
            isinstance(r, dict)
            and not r.get("timeline_values")
            and (r.get("criteria_id") or r.get("ten_chi_tieu") or r.get("item") or r.get("criteria_name"))
            for r in t_rows
        )
        if not needs_row_hydration:
            return False

        try:
            if not hasattr(self, "_catalog") or self._catalog is None:
                from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog
                self._catalog = DuckDBSemanticCatalog()
            catalog = self._catalog
            if not hasattr(catalog, "get_batch_period_values"):
                return False

            cand_nodes: List[Dict[str, Any]] = []
            for r in t_rows:
                if not isinstance(r, dict):
                    continue
                c_id = r.get("criteria_id") or r.get("id")
                raw_nm = r.get("ten_chi_tieu") or r.get("item") or r.get("criteria_name") or ""
                clean_nm = str(raw_nm).replace("**", "").strip()
                if c_id or clean_nm:
                    cand_nodes.append({"id": c_id, "name": clean_nm})

            p_name = str(td.get("parent_criterion_name") or "").strip()
            if not p_name and content:
                import re
                m_parent = re.search(r"- \*\*Chỉ tiêu:\*\*\s*([^\n]+)", content)
                if m_parent:
                    p_name = m_parent.group(1).strip()
                    td["parent_criterion_name"] = p_name
            if p_name:
                cand_nodes.append({"name": p_name})

            if not cand_nodes:
                return False

            ts = td.get("temporal_scope") or {}
            y_code = str(ts.get("year") or "2026")
            period_map = catalog.get_batch_period_values(cand_nodes, year_code=y_code, tenant_code="68")
            if not period_map:
                return False

            updated = False
            for r in t_rows:
                if not isinstance(r, dict) or r.get("timeline_values"):
                    continue
                c_id_k = str(r.get("criteria_id") or r.get("id") or "").lower()
                c_nm_k = str(r.get("ten_chi_tieu") or r.get("item") or r.get("criteria_name") or "").replace("**", "").strip().lower()
                tv = period_map.get(c_id_k) or period_map.get(c_nm_k)
                if tv:
                    r["timeline_values"] = tv
                    updated = True

            if p_name and not td.get("parent_timeline_values"):
                p_tv = period_map.get(p_name.lower())
                if p_tv:
                    td["parent_timeline_values"] = p_tv
                    updated = True

            if isinstance(chips, list):
                for ch in chips:
                    if not isinstance(ch, dict) or ch.get("timeline_values"):
                        continue
                    lbl = str(ch.get("label") or "").replace("🔘", "").replace("[", "").replace("]", "").strip().lower()
                    if lbl and period_map.get(lbl):
                        ch["timeline_values"] = period_map[lbl]
                        updated = True

            if updated:
                conn.execute(
                    """
                    UPDATE chat_messages
                    SET tabular_data_json = ?, quick_action_chips_json = ?
                    WHERE id = ?
                    """,
                    (
                        json.dumps(td, ensure_ascii=False),
                        json.dumps(chips, ensure_ascii=False) if chips is not None else None,
                        msg_id,
                    ),
                )
                conn.commit()
            return updated
        except Exception as exc:
            logger.debug("Lazy hydration of timeline_values skipped for msg %s: %s", msg_id, exc)
            return False

    def _fetch_messages_conn(self, conn: sqlite3.Connection, session_id: str) -> List[Dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT id, role, content, tabular_data_json, quick_action_chips_json, timestamp
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY seq ASC
            """,
            (session_id,),
        ).fetchall()
        msgs: List[Dict[str, Any]] = []
        for m in rows:
            item: Dict[str, Any] = {
                "id": m["id"],
                "role": m["role"],
                "content": m["content"],
                "timestamp": m["timestamp"],
            }
            if m["tabular_data_json"]:
                try:
                    item["tabular_data"] = json.loads(m["tabular_data_json"])
                except Exception:
                    pass
            if m["quick_action_chips_json"]:
                try:
                    item["quick_action_chips"] = json.loads(m["quick_action_chips_json"])
                except Exception:
                    pass
            if isinstance(item.get("tabular_data"), dict):
                self._hydrate_legacy_timeline_values(
                    conn,
                    m["id"],
                    m["content"] or "",
                    item["tabular_data"],
                    item.get("quick_action_chips"),
                )
            msgs.append(item)
        return msgs

    def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        try:
            with self._db_lock, self._connect() as conn:
                return self._fetch_messages_conn(conn, session_id)
        except Exception as exc:
            logger.warning("Failed to get session messages for %s: %s", session_id, exc)
            return []

    def rename_session(self, session_id: str, new_title: str) -> bool:
        clean = (new_title or "").strip() or "Cuộc hội thoại"
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            with self._db_lock, self._connect() as conn:
                cur = conn.execute(
                    "UPDATE chat_sessions SET title = ?, updated_at = ? WHERE id = ?",
                    (clean, now_iso, session_id),
                )
                conn.commit()
                return cur.rowcount > 0
        except Exception as exc:
            logger.warning("Failed to rename session %s: %s", session_id, exc)
            return False

    def delete_session(self, session_id: str) -> bool:
        try:
            with self._db_lock, self._connect() as conn:
                conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
                cur = conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
                conn.commit()
                return cur.rowcount > 0
        except Exception as exc:
            logger.warning("Failed to delete session %s: %s", session_id, exc)
            return False

    def clear_all_sessions(self) -> None:
        try:
            with self._db_lock, self._connect() as conn:
                conn.execute("DELETE FROM chat_messages")
                conn.execute("DELETE FROM chat_sessions")
                conn.commit()
        except Exception as exc:
            logger.warning("Failed to clear all sessions: %s", exc)
