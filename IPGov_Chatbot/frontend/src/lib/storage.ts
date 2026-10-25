import { ChatSession, ChatMessage } from '@/types/chat';

const SESSIONS_STORAGE_KEY = 'hdsd_chat_sessions_v1';
const ACTIVE_SESSION_STORAGE_KEY = 'hdsd_active_session_id_v1';
const MAX_SAVED_SESSIONS = 50;

const CONTEXT_PREFIX_RE = /^\[\s*tenant_code\s*[=:][^\]]+\]\s*/i;

export const stripTenantContextPrefix = (text: string): string => {
  return (text || '').replace(CONTEXT_PREFIX_RE, '').trim();
};

export const cleanSessionTitle = (rawTitle: string): string => {
  const cleaned = stripTenantContextPrefix(rawTitle);
  if (!cleaned) return 'Cuộc hội thoại mới';
  return cleaned.length > 42 ? `${cleaned.slice(0, 42)}...` : cleaned;
};

export const compactMessageForStorage = (msg: ChatMessage): ChatMessage => {
  const cleanMsg =
    msg.role === 'user' && msg.content
      ? { ...msg, content: stripTenantContextPrefix(msg.content) }
      : msg;
  if (!cleanMsg.tabular_data) return cleanMsg;
  const td: any = { ...cleanMsg.tabular_data };

  // R1.2: Giới hạn tối đa 20 dòng trong localStorage để chống tràn dung lượng QuotaExceededError
  if (Array.isArray(td.rows) && td.rows.length > 20) {
    td.rows = td.rows.slice(0, 20);
  }

  // Tránh lưu nhân đôi cả tree_modal lẫn trees_by_root_id và level1_rows trùng lặp trong localStorage
  if (td.trees_by_root_id) {
    delete td.trees_by_root_id;
  }
  if (td.level1_rows) {
    delete td.level1_rows;
  }
  if (td.multi_parent_rows && Array.isArray(td.multi_parent_rows) && td.multi_parent_rows.length > 20) {
    td.multi_parent_rows = td.multi_parent_rows.slice(0, 20);
  }

  return {
    ...cleanMsg,
    tabular_data: td,
  };
};

const safeWriteSessions = (sessions: ChatSession[]): void => {
  if (typeof window === 'undefined') return;
  let list = sessions.slice(0, MAX_SAVED_SESSIONS).map((s) => ({
    ...s,
    title: cleanSessionTitle(s.title),
    messages: Array.isArray(s.messages) ? s.messages.map(compactMessageForStorage) : [],
  }));

  while (list.length > 0) {
    try {
      localStorage.setItem(SESSIONS_STORAGE_KEY, JSON.stringify(list));
      return;
    } catch (err) {
      // Nếu đầy bộ nhớ localStorage (QuotaExceededError), cắt bớt phiên cũ nhất để bảo toàn phiên mới
      if (list.length > 1) {
        list = list.slice(0, list.length - 1);
      } else {
        console.error('Failed to write chat sessions to localStorage:', err);
        return;
      }
    }
  }
  try {
    localStorage.setItem(SESSIONS_STORAGE_KEY, '[]');
  } catch {}
};

export const saveActiveSessionId = (sessionId: string | undefined): void => {
  if (typeof window === 'undefined') return;
  try {
    if (sessionId) {
      localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, sessionId);
    } else {
      localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
    }
  } catch {}
};

export const loadActiveSessionId = (): string | null => {
  if (typeof window === 'undefined') return null;
  try {
    return localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY);
  } catch {
    return null;
  }
};

export const loadSessions = (): ChatSession[] => {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(SESSIONS_STORAGE_KEY);
    if (!raw) return [];
    const sessions: ChatSession[] = JSON.parse(raw);
    return Array.isArray(sessions)
      ? sessions
          .map((s) => ({
            ...s,
            title: cleanSessionTitle(s.title),
            messages: Array.isArray(s.messages)
              ? s.messages.map((m) =>
                  m.role === 'user' && m.content
                    ? { ...m, content: stripTenantContextPrefix(m.content) }
                    : m
                )
              : [],
          }))
          .sort(
            (a, b) =>
              new Date(b.updatedAt || b.createdAt).getTime() -
              new Date(a.updatedAt || a.createdAt).getTime()
          )
      : [];
  } catch (err) {
    console.error('Failed to load chat sessions from localStorage:', err);
    return [];
  }
};

export const mergeSessions = (
  localSessions: ChatSession[],
  cloudSessions: ChatSession[]
): ChatSession[] => {
  const byId = new Map<string, ChatSession>();

  for (const ls of localSessions || []) {
    if (!ls || !ls.id) continue;
    byId.set(ls.id, {
      ...ls,
      title: cleanSessionTitle(ls.title),
    });
  }

  for (const cs of cloudSessions || []) {
    if (!cs || !cs.id) continue;
    const existing = byId.get(cs.id);
    if (!existing) {
      byId.set(cs.id, {
        ...cs,
        title: cleanSessionTitle(cs.title),
      });
    } else {
      const localMsgs = existing.messages || [];
      const cloudMsgs = cs.messages || [];
      const chosenMsgs = cloudMsgs.length >= localMsgs.length ? cloudMsgs : localMsgs;
      const newerUpdated =
        new Date(cs.updatedAt || cs.createdAt || 0).getTime() >
        new Date(existing.updatedAt || existing.createdAt || 0).getTime()
          ? cs.updatedAt
          : existing.updatedAt;
      byId.set(cs.id, {
        ...existing,
        ...cs,
        title: cleanSessionTitle(cs.title || existing.title),
        updatedAt: newerUpdated || new Date().toISOString(),
        messages: chosenMsgs,
      });
    }
  }

  const merged = Array.from(byId.values()).sort(
    (a, b) =>
      new Date(b.updatedAt || b.createdAt).getTime() -
      new Date(a.updatedAt || a.createdAt).getTime()
  );
  safeWriteSessions(merged);
  return merged;
};

export const saveSession = (session: ChatSession): void => {
  if (typeof window === 'undefined') return;
  try {
    const sessions = loadSessions();
    const existingIndex = sessions.findIndex((s) => s.id === session.id);

    const updatedSession: ChatSession = {
      ...session,
      title: cleanSessionTitle(session.title),
      updatedAt: new Date().toISOString(),
    };

    if (existingIndex >= 0) {
      sessions[existingIndex] = updatedSession;
    } else {
      sessions.unshift(updatedSession);
    }

    safeWriteSessions(sessions);
    saveActiveSessionId(session.id);
  } catch (err) {
    console.error('Failed to save chat session to localStorage:', err);
  }
};

export const deleteSession = (sessionId: string): void => {
  if (typeof window === 'undefined') return;
  try {
    const sessions = loadSessions().filter((s) => s.id !== sessionId);
    safeWriteSessions(sessions);
    if (loadActiveSessionId() === sessionId) {
      saveActiveSessionId(sessions[0]?.id);
    }
  } catch (err) {
    console.error('Failed to delete chat session from localStorage:', err);
  }
};

export const renameSession = (sessionId: string, newTitle: string): void => {
  if (typeof window === 'undefined') return;
  try {
    const sessions = loadSessions();
    const target = sessions.find((s) => s.id === sessionId);
    if (target) {
      target.title = newTitle.trim() || 'Cuộc hội thoại';
      target.updatedAt = new Date().toISOString();
      safeWriteSessions(sessions);
    }
  } catch (err) {
    console.error('Failed to rename chat session in localStorage:', err);
  }
};

export const clearAllSessions = (): void => {
  if (typeof window === 'undefined') return;
  try {
    localStorage.removeItem(SESSIONS_STORAGE_KEY);
    localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
  } catch (err) {
    console.error('Failed to clear chat sessions from localStorage:', err);
  }
};

