'use client';

import React, { useState, useMemo } from 'react';
import { ChatSession } from '@/types/chat';
import {
  Plus,
  Search,
  MessageSquare,
  Trash2,
  Edit2,
  Check,
  X,
  PanelLeftClose,
  PanelLeft,
  Clock,
  Landmark,
  Building2,
  Trash,
} from 'lucide-react';

interface ChatSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  sessions: ChatSession[];
  activeSessionId?: string;
  onSelectSession: (session: ChatSession) => void;
  onNewChat: () => void;
  onDeleteSession: (sessionId: string) => void;
  onRenameSession: (sessionId: string, newTitle: string) => void;
  onClearAll: () => void;
}

export const ChatSidebar: React.FC<ChatSidebarProps> = ({
  isOpen,
  onToggle,
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  onRenameSession,
  onClearAll,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

  // Lọc danh sách theo từ khóa tìm kiếm
  const filteredSessions = useMemo(() => {
    if (!searchQuery.trim()) return sessions;
    const q = searchQuery.toLowerCase();
    return sessions.filter((s) => s.title.toLowerCase().includes(q));
  }, [sessions, searchQuery]);

  // Phân nhóm theo mốc thời gian
  const groupedSessions = useMemo(() => {
    const groups: { [key: string]: ChatSession[] } = {
      'Hôm nay': [],
      'Hôm qua': [],
      '7 ngày trước': [],
      'Cũ hơn': [],
    };

    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const yesterday = today - 86400000;
    const last7Days = today - 7 * 86400000;

    filteredSessions.forEach((session) => {
      const sessionDate = new Date(session.updatedAt || session.createdAt).getTime();
      if (sessionDate >= today) {
        groups['Hôm nay'].push(session);
      } else if (sessionDate >= yesterday) {
        groups['Hôm qua'].push(session);
      } else if (sessionDate >= last7Days) {
        groups['7 ngày trước'].push(session);
      } else {
        groups['Cũ hơn'].push(session);
      }
    });

    return groups;
  }, [filteredSessions]);

  const handleStartRename = (session: ChatSession, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(session.id);
    setEditTitle(session.title);
  };

  const handleSaveRename = (sessionId: string, e?: React.FormEvent | React.MouseEvent) => {
    e?.stopPropagation();
    if (editTitle.trim()) {
      onRenameSession(sessionId, editTitle.trim());
    }
    setEditingId(null);
  };

  const handleCancelRename = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(null);
  };

  const handleDelete = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm('Bạn có chắc muốn xóa cuộc hội thoại này?')) {
      onDeleteSession(sessionId);
    }
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          onClick={onToggle}
          className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-40 lg:hidden transition-opacity"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed lg:static top-0 left-0 h-full z-50 flex flex-col bg-slate-50 border-r border-slate-200 transition-all duration-300 ease-in-out ${
          isOpen ? 'w-80 translate-x-0' : 'w-0 -translate-x-full lg:w-0 lg:translate-x-0 overflow-hidden border-none'
        }`}
      >
        {isOpen && (
          <div className="flex flex-col h-full w-80">
            {/* Header: Nút New Chat & Toggle */}
            <div className="p-3.5 border-b border-slate-200 bg-white/80 backdrop-blur flex items-center gap-2">
              <button
                onClick={onNewChat}
                className="flex-1 flex items-center justify-center gap-2 px-3.5 py-2 bg-blue-600 hover:bg-blue-700 active:scale-[0.98] text-white rounded-xl text-sm font-semibold shadow-sm shadow-blue-500/20 transition-all"
              >
                <Plus className="w-4 h-4" />
                <span>Cuộc hội thoại mới</span>
              </button>

              <button
                onClick={onToggle}
                className="p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
                title="Thu gọn lịch sử"
                aria-label="Thu gọn lịch sử"
              >
                <PanelLeftClose className="w-5 h-5" />
              </button>
            </div>

            {/* Search Input */}
            <div className="p-3 border-b border-slate-200/60 bg-slate-50/50">
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder="Tìm kiếm hội thoại..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery('')}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>

            {/* Session List */}
            <div className="flex-1 overflow-y-auto p-2 space-y-4">
              {filteredSessions.length === 0 ? (
                <div className="text-center py-12 px-4">
                  <div className="w-10 h-10 mx-auto mb-2 rounded-full bg-slate-100 flex items-center justify-center text-slate-400">
                    <MessageSquare className="w-5 h-5" />
                  </div>
                  <p className="text-xs text-slate-500 font-medium">
                    {searchQuery ? 'Không tìm thấy cuộc hội thoại phù hợp' : 'Chưa có lịch sử hội thoại'}
                  </p>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    {searchQuery ? 'Thử từ khóa khác' : 'Bắt đầu chat để tự động lưu phiên'}
                  </p>
                </div>
              ) : (
                Object.entries(groupedSessions).map(([groupName, groupItems]) => {
                  if (groupItems.length === 0) return null;
                  return (
                    <div key={groupName} className="space-y-1">
                      <div className="px-2.5 py-1 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                        {groupName}
                      </div>

                      {groupItems.map((session) => {
                        const isActive = session.id === activeSessionId;
                        const isEditing = editingId === session.id;
                        const isPhuong = session.role === 'phuong';

                        return (
                          <div
                            key={session.id}
                            onClick={() => !isEditing && onSelectSession(session)}
                            className={`group relative flex items-center gap-2.5 px-3 py-2.5 rounded-xl cursor-pointer transition-all ${
                              isActive
                                ? 'bg-blue-50 text-blue-900 font-semibold shadow-xs border border-blue-200/70'
                                : 'hover:bg-white text-slate-700 hover:text-slate-900 border border-transparent hover:border-slate-200/60'
                            }`}
                          >
                            {/* Role Icon */}
                            <div
                              className={`shrink-0 w-7 h-7 rounded-lg flex items-center justify-center text-xs ${
                                isPhuong
                                  ? isActive
                                    ? 'bg-blue-600 text-white'
                                    : 'bg-blue-100 text-blue-700'
                                  : isActive
                                  ? 'bg-indigo-600 text-white'
                                  : 'bg-indigo-100 text-indigo-700'
                              }`}
                              title={isPhuong ? 'Phân hệ Phường / Xã' : 'Phân hệ Doanh nghiệp'}
                            >
                              {isPhuong ? <Landmark className="w-3.5 h-3.5" /> : <Building2 className="w-3.5 h-3.5" />}
                            </div>

                            {/* Title & Metadata */}
                            <div className="flex-1 min-w-0">
                              {isEditing ? (
                                <form
                                  onSubmit={(e) => handleSaveRename(session.id, e)}
                                  className="flex items-center gap-1"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <input
                                    type="text"
                                    value={editTitle}
                                    onChange={(e) => setEditTitle(e.target.value)}
                                    autoFocus
                                    className="w-full px-1.5 py-0.5 text-xs bg-white border border-blue-500 rounded focus:outline-none"
                                  />
                                  <button
                                    type="button"
                                    onClick={(e) => handleSaveRename(session.id, e)}
                                    className="p-1 text-emerald-600 hover:bg-emerald-50 rounded"
                                  >
                                    <Check className="w-3 h-3" />
                                  </button>
                                  <button
                                    type="button"
                                    onClick={handleCancelRename}
                                    className="p-1 text-rose-500 hover:bg-rose-50 rounded"
                                  >
                                    <X className="w-3 h-3" />
                                  </button>
                                </form>
                              ) : (
                                <>
                                  <p className="text-xs truncate" title={session.title}>
                                    {session.title}
                                  </p>
                                  <p className="text-[10px] text-slate-400 flex items-center gap-1 mt-0.5">
                                    <Clock className="w-2.5 h-2.5" />
                                    <span>
                                      {new Date(session.updatedAt || session.createdAt).toLocaleTimeString([], {
                                        hour: '2-digit',
                                        minute: '2-digit',
                                      })}
                                    </span>
                                    <span>•</span>
                                    <span>{session.messages?.length || 0} tin nhắn</span>
                                  </p>
                                </>
                              )}
                            </div>

                            {/* Hover Actions (Rename, Delete) */}
                            {!isEditing && (
                              <div
                                className={`shrink-0 flex items-center gap-0.5 ${
                                  isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
                                } transition-opacity`}
                              >
                                <button
                                  onClick={(e) => handleStartRename(session, e)}
                                  className="p-1 text-slate-400 hover:text-blue-600 hover:bg-blue-100/50 rounded-md transition-colors"
                                  title="Đổi tên"
                                >
                                  <Edit2 className="w-3 h-3" />
                                </button>
                                <button
                                  onClick={(e) => handleDelete(session.id, e)}
                                  className="p-1 text-slate-400 hover:text-rose-600 hover:bg-rose-100/50 rounded-md transition-colors"
                                  title="Xóa cuộc hội thoại"
                                >
                                  <Trash2 className="w-3 h-3" />
                                </button>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  );
                })
              )}
            </div>

            {/* Footer: Clear All History */}
            {sessions.length > 0 && (
              <div className="p-2.5 border-t border-slate-200 bg-white/60">
                <button
                  onClick={() => {
                    if (confirm('Bạn có chắc muốn xóa TOÀN BỘ lịch sử chat? Hành động này không thể hoàn tác.')) {
                      onClearAll();
                    }
                  }}
                  className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 text-slate-500 hover:text-rose-600 hover:bg-rose-50 rounded-lg text-xs font-medium transition-colors"
                >
                  <Trash className="w-3.5 h-3.5" />
                  <span>Xóa tất cả lịch sử</span>
                </button>
              </div>
            )}
          </div>
        )}
      </aside>
    </>
  );
};
