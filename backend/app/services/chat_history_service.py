import os
import json
import uuid
import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import psycopg2
from psycopg2.extras import Json
from app.core.config import settings
from app.core.logger import logger
from app.models.chat import ChatResponse, QuickActionChip, ContactSupportInfo
from app.models.chunk import DocumentChunk


class ChatHistoryService:
    """
    Service responsible for persisting chat sessions and chat messages
    into Supabase PostgreSQL asynchronously without blocking the main event loop.
    """

    def __init__(self):
        self.db_url = settings.DATABASE_URL or "postgresql://postgres:cEzQV7AuXRXnmxGb@db.tykwgiubhnxedlpxszdn.supabase.co:5432/postgres"

    def _get_connection(self):
        return psycopg2.connect(self.db_url)

    def _format_chunk_for_db(self, chunk: DocumentChunk) -> dict:
        return {
            "id": chunk.id,
            "document_source": chunk.metadata.document_source,
            "section_title": chunk.metadata.section_title,
            "module": chunk.metadata.module,
            "sub_module": chunk.metadata.sub_module,
            "text_preview": chunk.text_content[:200] + ("..." if len(chunk.text_content) > 200 else "")
        }

    def _save_interaction_sync(
        self,
        session_id: str,
        user_query: str,
        bot_response: ChatResponse,
        role: str = "phuong",
        user_identifier: Optional[str] = None
    ) -> bool:
        """
        Synchronous worker executed in a background worker thread.
        Upserts chat_sessions and inserts user and assistant chat_messages.
        """
        try:
            # Ensure valid UUID for session_id
            try:
                valid_session_uuid = str(uuid.UUID(session_id))
            except Exception:
                valid_session_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, session_id))

            # Truncate user query as session title (max 100 chars)
            title = user_query.strip()[:100]

            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # 1. Upsert session in chat_sessions
                    cur.execute("""
                        INSERT INTO chat_sessions (id, user_identifier, role, title, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, NOW(), NOW())
                        ON CONFLICT (id) DO UPDATE 
                        SET updated_at = NOW(),
                            role = EXCLUDED.role,
                            title = COALESCE(chat_sessions.title, EXCLUDED.title);
                    """, (valid_session_uuid, user_identifier or "anonymous_user", role, title))

                    # 2. Insert user message
                    user_msg_id = str(uuid.uuid4())
                    cur.execute("""
                        INSERT INTO chat_messages (id, session_id, role, content, created_at)
                        VALUES (%s, %s, 'user', %s, NOW());
                    """, (user_msg_id, valid_session_uuid, user_query))

                    # 3. Insert assistant response message with rich metadata
                    bot_msg_id = str(uuid.uuid4())
                    
                    # Prepare JSONB payloads
                    source_chunks_data = [self._format_chunk_for_db(c) for c in bot_response.source_chunks] if bot_response.source_chunks else []
                    images_data = bot_response.images if bot_response.images else []
                    youtube_links_data = bot_response.youtube_links if bot_response.youtube_links else []
                    chips_data = [c.model_dump() for c in bot_response.quick_action_chips] if bot_response.quick_action_chips else []
                    contact_data = bot_response.contact_support.model_dump() if bot_response.contact_support else None

                    cur.execute("""
                        INSERT INTO chat_messages (
                            id, session_id, role, content, intent,
                            source_chunks, images, youtube_links,
                            quick_action_chips, contact_support, created_at
                        )
                        VALUES (%s, %s, 'assistant', %s, %s, %s, %s, %s, %s, %s, NOW());
                    """, (
                        bot_msg_id,
                        valid_session_uuid,
                        bot_response.answer,
                        bot_response.intent or "knowledge_query",
                        Json(source_chunks_data),
                        Json(images_data),
                        Json(youtube_links_data),
                        Json(chips_data),
                        Json(contact_data) if contact_data else None
                    ))

                conn.commit()
            logger.info(f"Successfully saved chat interaction to Supabase (Session: {valid_session_uuid})")
            return True
        except Exception as e:
            logger.error(f"Failed to persist chat interaction to Supabase: {e}", exc_info=True)
            return False

    async def save_chat_interaction_async(
        self,
        session_id: str,
        user_query: str,
        bot_response: ChatResponse,
        role: str = "phuong",
        user_identifier: Optional[str] = None
    ):
        """Non-blocking async wrapper using asyncio.to_thread."""
        try:
            await asyncio.to_thread(
                self._save_interaction_sync,
                session_id=session_id,
                user_query=user_query,
                bot_response=bot_response,
                role=role,
                user_identifier=user_identifier
            )
        except Exception as e:
            logger.error(f"Error in background save_chat_interaction_async: {e}")

    def get_session_messages(self, session_id: str) -> List[dict]:
        """Fetch all messages for a session from Supabase."""
        try:
            try:
                valid_session_uuid = str(uuid.UUID(session_id))
            except Exception:
                valid_session_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, session_id))

            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, role, content, intent, images, youtube_links, quick_action_chips, contact_support, created_at
                        FROM chat_messages
                        WHERE session_id = %s
                        ORDER BY created_at ASC;
                    """, (valid_session_uuid,))
                    rows = cur.fetchall()
                    messages = []
                    for r in rows:
                        created_iso = r[8].isoformat() if r[8] else None
                        messages.append({
                            "id": str(r[0]),
                            "role": r[1],
                            "content": r[2],
                            "intent": r[3],
                            "images": r[4] or [],
                            "youtube_links": r[5] or [],
                            "quick_action_chips": r[6] or [],
                            "contact_support": r[7],
                            "created_at": created_iso,
                            "timestamp": created_iso
                        })
                    return messages
        except Exception as e:
            logger.error(f"Failed to retrieve session messages for {session_id}: {e}")
            return []

    def get_all_sessions(self, limit: int = 50) -> List[dict]:
        """Fetch latest chat sessions summary from Supabase."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, role, title, created_at, updated_at
                        FROM chat_sessions
                        ORDER BY updated_at DESC
                        LIMIT %s;
                    """, (limit,))
                    rows = cur.fetchall()
                    sessions = []
                    for r in rows:
                        sessions.append({
                            "id": str(r[0]),
                            "role": r[1] or "dn",
                            "title": r[2] or "Cuộc hội thoại",
                            "createdAt": r[3].isoformat() if r[3] else None,
                            "updatedAt": r[4].isoformat() if r[4] else None,
                            "messages": []
                        })
                    return sessions
        except Exception as e:
            logger.error(f"Failed to retrieve sessions from Supabase: {e}")
            return []


chat_history_service = ChatHistoryService()
