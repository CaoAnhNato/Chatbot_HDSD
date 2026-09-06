'use client';

import React, { useState, useEffect, useRef } from 'react';
import { ChatMessage, ChatSession, QuickActionChip } from '@/types/chat';
import { sendMessageStream, fetchChatSessions, fetchSessionHistory } from '@/lib/api';
import {
  loadSessions,
  saveSession,
  deleteSession,
  renameSession,
  clearAllSessions,
} from '@/lib/storage';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { MediaViewer } from './MediaViewer';
import { ChatSidebar } from './ChatSidebar';
import {
  Bot,
  RefreshCcw,
  ShieldCheck,
  Building2,
  Landmark,
  PanelLeft,
} from 'lucide-react';

const WELCOME_CHIPS_PHUONG: QuickActionChip[] = [
  { id: 'chip_p_create', label: '➕ Tạo tài khoản Phường/Xã', query_text: 'Hướng dẫn tạo mới tài khoản phường xã' },
  { id: 'chip_p_edit', label: '✏️ Sửa tài khoản', query_text: 'Cách sửa thông tin tài khoản tuyến dưới' },
  { id: 'chip_p_reset', label: '🔓 Khôi phục mật khẩu', query_text: 'Cách khôi phục mật khẩu tài khoản phường xã' },
  { id: 'chip_p_del', label: '🗑️ Xóa tài khoản', query_text: 'Làm sao để xóa tài khoản phường xã?' },
  { id: 'chip_p_dotxuat', label: '🚨 Báo cáo TNLĐ đột xuất', query_text: 'Quy trình báo cáo tai nạn lao động đột xuất không theo HĐLĐ' },
  { id: 'chip_p_dinhky', label: '📊 Báo cáo TNLĐ định kỳ', query_text: 'Hướng dẫn báo cáo tai nạn lao động định kỳ cho người không có HĐLĐ' },
  { id: 'chip_p_info', label: '👤 Đổi thông tin cán bộ', query_text: 'Hướng dẫn thay đổi thông tin cá nhân cán bộ' },
  { id: 'chip_p_contact', label: '📞 Hotline hỗ trợ', query_text: 'Cho tôi thông tin hotline hỗ trợ kỹ thuật' },
];

const WELCOME_CHIPS_DN: QuickActionChip[] = [
  { id: 'chip_reg', label: '📝 Đăng ký tài khoản', query_text: 'Hướng dẫn đăng ký tài khoản mới' },
  { id: 'chip_pwd', label: '🔑 Thay đổi mật khẩu', query_text: 'Hướng dẫn đổi mật khẩu' },
  { id: 'chip_dn', label: '🏢 Đổi thông tin DN', query_text: 'Hướng dẫn thay đổi thông tin doanh nghiệp' },
  { id: 'chip_tnld', label: '⚠️ Báo cáo TNLĐ', query_text: 'Hướng dẫn nộp báo cáo tai nạn lao động' },
  { id: 'chip_atvsld', label: '🛡️ Báo cáo ATVSLĐ', query_text: 'Hướng dẫn nộp báo cáo An toàn vệ sinh lao động' },
  { id: 'chip_stat', label: '📊 Xem số liệu thống kê', query_text: 'Làm sao để xem thống kê báo cáo?' },
  { id: 'chip_contact', label: '📞 Hotline & Zalo hỗ trợ', query_text: 'Cho tôi thông tin hotline và zalo hỗ trợ kỹ thuật' },
];

const WELCOME_CONTACT_PHUONG = {
  title: 'THÔNG TIN LIÊN HỆ HỖ TRỢ KỸ THUẬT (PHƯỜNG/XÃ)',
  working_hours: 'Thứ 2 - Thứ 6 (Sáng: 07h30 – 11h30, Chiều: 13h00 – 17h00)',
  hotlines: ['028 3535 2524'],
};

const WELCOME_CONTACT_DN = {
  title: 'THÔNG TIN LIÊN HỆ HỖ TRỢ KỸ THUẬT (DOANH NGHIỆP)',
  working_hours: 'Thứ 2 - Thứ 6 (Sáng: 08h00 – 11h00, Chiều: 13h00 – 17h00)',
  hotlines: ['028 3535 2523', '028 3535 2524'],
  zalo: '0967 862 523',
};

const getWelcomeMessage = (role: 'phuong' | 'dn'): ChatMessage => ({
  id: `welcome-${role}`,
  role: 'assistant',
  content:
    role === 'phuong'
      ? 'Cán bộ có thể chọn nhanh các quy trình hướng dẫn bên dưới hoặc nhập câu hỏi trực tiếp để được hỗ trợ giải đáp:'
      : 'Bạn có thể chọn nhanh các quy trình hướng dẫn bên dưới hoặc nhập câu hỏi trực tiếp để được hỗ trợ giải đáp:',
  contact_support: role === 'phuong' ? WELCOME_CONTACT_PHUONG : WELCOME_CONTACT_DN,
  quick_action_chips: role === 'phuong' ? WELCOME_CHIPS_PHUONG : WELCOME_CHIPS_DN,
  timestamp: new Date().toISOString(),
});

export const ChatContainer: React.FC = () => {
  const [activeRole, setActiveRole] = useState<'phuong' | 'dn'>('phuong');
  const [messages, setMessages] = useState<ChatMessage[]>([getWelcomeMessage('phuong')]);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);
  const [sessions, setSessions] = useState<ChatSession[]>([]);

  const [viewerState, setViewerState] = useState<{
    isOpen: boolean;
    imageUrl: string | null;
    altText: string;
  }>({
    isOpen: false,
    imageUrl: null,
    altText: '',
  });

  // Tải danh sách lịch sử phiên khi khởi động (Local trước để hiện tức thì, sau đó đồng bộ từ Cloud Supabase)
  useEffect(() => {
    const initSessions = async () => {
      const local = loadSessions();
      if (local.length > 0) {
        setSessions(local);
      }
      try {
        const cloudSessions = await fetchChatSessions();
        if (cloudSessions && cloudSessions.length > 0) {
          // Bảo lưu messages đã có trong local nếu cloud chỉ trả về summary rỗng
          const merged = cloudSessions.map((cs) => {
            const found = local.find((ls) => ls.id === cs.id);
            return found && found.messages && found.messages.length > 0 ? found : cs;
          });
          setSessions(merged);
        }
      } catch (err) {
        console.warn('Could not sync sessions from cloud, keeping local state:', err);
      }
    };
    initSessions();
  }, []);

  // Hàm lưu phiên hội thoại độc lập (pure helper)
  const persistSession = (sid: string, msgs: ChatMessage[], currentRole: 'phuong' | 'dn') => {
    const userMessages = msgs.filter((m) => m.role === 'user');
    if (userMessages.length === 0) return;

    const firstUserText = userMessages[0].content;
    const title = firstUserText.length > 38 ? `${firstUserText.slice(0, 38)}...` : firstUserText;

    const currentSessions = loadSessions();
    const existingSession = currentSessions.find((s) => s.id === sid);
    const sessionObj: ChatSession = {
      id: sid,
      title: existingSession?.title || title,
      role: currentRole,
      createdAt: existingSession?.createdAt || new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      messages: msgs,
    };

    saveSession(sessionObj);
    setSessions((prev) => {
      const idx = prev.findIndex((s) => s.id === sid);
      if (idx >= 0) {
        const copy = [...prev];
        copy[idx] = sessionObj;
        return copy;
      }
      return [sessionObj, ...prev];
    });
  };

  const handleRoleChange = (newRole: 'phuong' | 'dn') => {
    if (newRole === activeRole) return;
    setActiveRole(newRole);
    setMessages([getWelcomeMessage(newRole)]);
    setSessionId(undefined);
  };

  const handleNewChat = () => {
    const newSid = `session-${Date.now()}`;
    setSessionId(newSid);
    setMessages([getWelcomeMessage(activeRole)]);
  };

  const handleSelectSession = async (session: ChatSession) => {
    setActiveRole(session.role);
    setSessionId(session.id);

    // Nếu phiên chưa có messages (do tải summary từ Cloud), gọi API lấy toàn bộ tin nhắn
    if (!session.messages || session.messages.length === 0) {
      try {
        const msgs = await fetchSessionHistory(session.id);
        if (msgs && msgs.length > 0) {
          setMessages(msgs);
          session.messages = msgs;
          saveSession(session);
          return;
        }
      } catch (err) {
        console.warn(`Could not load messages for session ${session.id}:`, err);
      }
    }

    setMessages(session.messages && session.messages.length > 0 ? session.messages : [getWelcomeMessage(session.role)]);
  };

  const handleDeleteSession = (sid: string) => {
    deleteSession(sid);
    const updated = loadSessions();
    setSessions(updated);
    if (sessionId === sid) {
      handleNewChat();
    }
  };

  const handleRenameSession = (sid: string, newTitle: string) => {
    renameSession(sid, newTitle);
    setSessions(loadSessions());
  };

  const handleClearAll = () => {
    clearAllSessions();
    setSessions([]);
    handleNewChat();
  };

  const handleSendMessage = async (queryText: string) => {
    const userMsgId = `user-${Date.now()}`;
    const botMsgId = `bot-${Date.now()}`;

    const userMsg: ChatMessage = {
      id: userMsgId,
      role: 'user',
      content: queryText,
      timestamp: new Date().toISOString(),
    };

    const initialBotMsg: ChatMessage = {
      id: botMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
    };

    const nextMessages = [...messages, userMsg, initialBotMsg];
    setMessages(nextMessages);
    setIsLoading(true);

    let effectiveSessionId = sessionId || `session-${Date.now()}`;
    if (!sessionId) {
      setSessionId(effectiveSessionId);
    }

    // Lưu phiên với câu hỏi của user
    persistSession(effectiveSessionId, nextMessages, activeRole);

    try {
      const history = messages
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .slice(-6)
        .map((m) => ({ role: m.role, content: m.content }));

      const collectionName = activeRole === 'phuong' ? 'hdsd_phuong_chunks' : 'hdsd_chunks';

      await sendMessageStream(
        queryText,
        effectiveSessionId,
        history,
        {
          onMetadata: (metadata) => {
            if (metadata.session_id) {
              effectiveSessionId = metadata.session_id;
              setSessionId(metadata.session_id);
            }
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === botMsgId
                  ? {
                      ...msg,
                      images: metadata.images,
                      youtube_links: metadata.youtube_links,
                      contact_support: metadata.contact_support,
                      quick_action_chips: metadata.quick_action_chips,
                      intent: metadata.intent,
                    }
                  : msg
              )
            );
          },
          onToken: (token) => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === botMsgId
                  ? {
                      ...msg,
                      content: msg.content + token,
                    }
                  : msg
              )
            );
          },
          onDone: (doneData) => {
            setMessages((prev) => {
              const updated = prev.map((msg) =>
                msg.id === botMsgId
                  ? {
                      ...msg,
                      content: doneData.full_answer,
                      contact_support: doneData.contact_support || msg.contact_support,
                    }
                  : msg
              );
              // Lưu phiên đã hoàn tất bất đồng bộ
              setTimeout(() => {
                persistSession(effectiveSessionId, updated, activeRole);
              }, 0);
              return updated;
            });
          },
          onError: (errMsg) => {
            setMessages((prev) => {
              const updated = prev.map((msg) =>
                msg.id === botMsgId
                  ? {
                      ...msg,
                      content: `⚠️ ${errMsg}`,
                    }
                  : msg
              );
              setTimeout(() => {
                persistSession(effectiveSessionId, updated, activeRole);
              }, 0);
              return updated;
            });
          },
        },
        activeRole,
        collectionName
      );
    } catch (err: any) {
      setMessages((prev) => {
        const updated = prev.map((msg) =>
          msg.id === botMsgId
            ? {
                ...msg,
                content: `⚠️ Không thể kết nối với máy chủ AI (${err.message || 'Lỗi mạng'}). Vui lòng kiểm tra backend server đang chạy tại port 8000.`,
              }
            : msg
        );
        setTimeout(() => {
          persistSession(effectiveSessionId, updated, activeRole);
        }, 0);
        return updated;
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-full bg-slate-100 overflow-hidden">
      {/* CỘT TRÁI: ChatSidebar */}
      <ChatSidebar
        isOpen={isSidebarOpen}
        onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
        sessions={sessions}
        activeSessionId={sessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onDeleteSession={handleDeleteSession}
        onRenameSession={handleRenameSession}
        onClearAll={handleClearAll}
      />

      {/* CỘT PHẢI: Khung Chat Chính */}
      <div className="flex-1 flex flex-col h-full bg-white relative overflow-hidden">
        {/* Header */}
        <header className="flex flex-wrap items-center justify-between gap-3 px-4 sm:px-6 py-3.5 border-b border-slate-200 bg-white/95 backdrop-blur-md shrink-0">
          <div className="flex items-center gap-3">
            {/* Nút Toggle Sidebar khi Sidebar đang đóng */}
            {!isSidebarOpen && (
              <button
                onClick={() => setIsSidebarOpen(true)}
                className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors border border-slate-200 shadow-xs"
                title="Mở lịch sử chat"
                aria-label="Mở lịch sử chat"
              >
                <PanelLeft className="w-5 h-5" />
              </button>
            )}

            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-md">
              <Bot className="w-6 h-6" />
            </div>

            <div>
              <h1 className="text-base font-bold text-slate-800 flex items-center gap-2">
                HDSD Multimodal Chatbot
                <span className="text-[11px] bg-blue-50 text-blue-700 px-2.5 py-0.5 rounded-full font-medium border border-blue-200">
                  Qwen-3.7-Flash
                </span>
              </h1>
              <p className="text-xs text-slate-500 flex items-center gap-1 mt-0.5">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                {activeRole === 'phuong'
                  ? 'Phân hệ Phường / Xã • 10 Phân hệ + Hỗ trợ kỹ thuật'
                  : 'Phân hệ Doanh nghiệp • Hình ảnh & Video YouTube'}
              </p>
            </div>
          </div>

          {/* Tab Switcher & Reset Button */}
          <div className="flex items-center gap-2">
            <div className="flex bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs font-medium">
              <button
                onClick={() => handleRoleChange('phuong')}
                className={`px-3 py-1.5 rounded-lg transition flex items-center gap-1.5 ${
                  activeRole === 'phuong'
                    ? 'bg-white text-blue-700 shadow-sm font-semibold'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
                title="Chuyển sang Phân hệ Phường / Xã"
              >
                <Landmark className="w-3.5 h-3.5" />
                <span>Phường / Xã</span>
              </button>
              <button
                onClick={() => handleRoleChange('dn')}
                className={`px-3 py-1.5 rounded-lg transition flex items-center gap-1.5 ${
                  activeRole === 'dn'
                    ? 'bg-white text-blue-700 shadow-sm font-semibold'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
                title="Chuyển sang Phân hệ Doanh nghiệp"
              >
                <Building2 className="w-3.5 h-3.5" />
                <span>Doanh nghiệp</span>
              </button>
            </div>

            <button
              onClick={handleNewChat}
              className="p-2.5 rounded-xl text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition border border-transparent hover:border-slate-200"
              title="Làm mới cuộc hội thoại"
            >
              <RefreshCcw className="w-4 h-4" />
            </button>
          </div>
        </header>

        {/* Messages List */}
        <MessageList
          messages={messages}
          isLoading={isLoading}
          onImageClick={(imageUrl, altText) =>
            setViewerState({ isOpen: true, imageUrl, altText })
          }
          onSelectChip={(queryText) => handleSendMessage(queryText)}
        />

        {/* Input Form */}
        <ChatInput onSendMessage={handleSendMessage} isLoading={isLoading} />

        {/* Image Lightbox Viewer */}
        <MediaViewer
          isOpen={viewerState.isOpen}
          imageUrl={viewerState.imageUrl}
          altText={viewerState.altText}
          onClose={() => setViewerState({ isOpen: false, imageUrl: null, altText: '' })}
        />
      </div>
    </div>
  );
};
