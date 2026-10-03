import { ChatSession } from '@/types/chat';

const SESSIONS_STORAGE_KEY = 'hdsd_chat_sessions_v1';
const MAX_SAVED_SESSIONS = 50;

export const loadSessions = (): ChatSession[] => {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(SESSIONS_STORAGE_KEY);
    if (!raw) return [];
    const sessions: ChatSession[] = JSON.parse(raw);
    return Array.isArray(sessions)
      ? sessions.sort(
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

export const saveSession = (session: ChatSession): void => {
  if (typeof window === 'undefined') return;
  try {
    const sessions = loadSessions();
    const existingIndex = sessions.findIndex((s) => s.id === session.id);

    const updatedSession: ChatSession = {
      ...session,
      updatedAt: new Date().toISOString(),
    };

    if (existingIndex >= 0) {
      sessions[existingIndex] = updatedSession;
    } else {
      sessions.unshift(updatedSession);
    }

    const trimmed = sessions.slice(0, MAX_SAVED_SESSIONS);
    localStorage.setItem(SESSIONS_STORAGE_KEY, JSON.stringify(trimmed));
  } catch (err) {
    console.error('Failed to save chat session to localStorage:', err);
  }
};

export const deleteSession = (sessionId: string): void => {
  if (typeof window === 'undefined') return;
  try {
    const sessions = loadSessions().filter((s) => s.id !== sessionId);
    localStorage.setItem(SESSIONS_STORAGE_KEY, JSON.stringify(sessions));
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
      localStorage.setItem(SESSIONS_STORAGE_KEY, JSON.stringify(sessions));
    }
  } catch (err) {
    console.error('Failed to rename chat session in localStorage:', err);
  }
};

export const clearAllSessions = (): void => {
  if (typeof window === 'undefined') return;
  try {
    localStorage.removeItem(SESSIONS_STORAGE_KEY);
  } catch (err) {
    console.error('Failed to clear chat sessions from localStorage:', err);
  }
};
