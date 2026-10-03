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
  PRESET_ROLES,
  UserRoleProfile,
  generateMockJWT,
} from '@/components/RoleSelector';
import {
  Bot,
  RefreshCcw,
  ShieldCheck,
  Building2,
  Landmark,
  PanelLeft,
} from 'lucide-react';

const CHIPS_LEVEL_0: QuickActionChip[] = [
  { id: 'chip_l0_1', label: '📊 Kinh phí khuyến công 2026', query_text: 'Kinh phí thực hiện khuyến công năm 2026 là bao nhiêu?' },
  { id: 'chip_l0_2', label: '⚠️ TNLĐ toàn tỉnh 2026', query_text: 'Năm 2026 toàn tỉnh có bao nhiêu vụ tai nạn lao động?' },
  { id: 'chip_l0_3', label: '📈 Xếp hạng khuyến công 2026', query_text: 'Xếp hạng các huyện có kinh phí khuyến công cao nhất năm 2026' },
  { id: 'chip_l0_4', label: '🏢 Danh mục Sở Ban Ngành', query_text: 'Báo cáo danh sách tất cả các sở, ban, ngành và đơn vị trực thuộc tỉnh Lâm Đồng' },
  { id: 'chip_l0_5', label: '📋 Biểu mẫu active 2026', query_text: 'Hiện tại trong năm 2026 có những biểu mẫu thu thập thông tin nào đang kích hoạt?' },
  { id: 'chip_l0_6', label: 'ℹ️ Lĩnh vực quản lý DWH', query_text: 'Hệ thống hiện đang quản lý và theo dõi số liệu của những ngành, lĩnh vực nào?' },
];

const CHIPS_LEVEL_1: QuickActionChip[] = [
  { id: 'chip_l1_1', label: '📋 Biểu mẫu active 2026', query_text: 'Hiện tại trong năm 2026 có những biểu mẫu thu thập thông tin nào đang kích hoạt?' },
  { id: 'chip_l1_2', label: '📊 Kinh phí khuyến công 2026', query_text: 'Kinh phí thực hiện khuyến công năm 2026 là bao nhiêu?' },
  { id: 'chip_l1_3', label: '🏢 Danh sách phòng ban trực thuộc', query_text: 'Báo cáo danh sách các đơn vị và phòng ban trực thuộc' },
  { id: 'chip_l1_4', label: '⚠️ Tình hình an toàn lao động 2026', query_text: 'Năm 2026 có bao nhiêu vụ tai nạn lao động?' },
  { id: 'chip_l1_5', label: 'ℹ️ Lĩnh vực quản lý DWH', query_text: 'Hệ thống hiện đang quản lý và theo dõi số liệu của những ngành, lĩnh vực nào?' },
];

const CHIPS_LEVEL_2: QuickActionChip[] = [
  { id: 'chip_l2_1', label: '📊 Báo cáo phòng ban gần nhất', query_text: 'Kiểm tra trạng thái nộp báo cáo của các phòng ban trong kỳ gần nhất' },
  { id: 'chip_l2_2', label: '⚠️ TNLĐ toàn tỉnh 2026', query_text: 'Năm 2026 toàn tỉnh có bao nhiêu vụ tai nạn lao động?' },
  { id: 'chip_l2_3', label: '📊 Kinh phí khuyến công 2026', query_text: 'Kinh phí thực hiện khuyến công năm 2026 là bao nhiêu?' },
  { id: 'chip_l2_4', label: '🔍 Hướng dẫn cán bộ mới', query_text: 'Tôi là cán bộ mới thì nên bắt đầu tra cứu số liệu như thế nào?' },
  { id: 'chip_l2_5', label: '📞 Hotline hỗ trợ kỹ thuật', query_text: 'Cho tôi thông tin hotline hỗ trợ kỹ thuật' },
];

const CHIPS_LEVEL_3: QuickActionChip[] = [
  { id: 'chip_l3_1', label: 'ℹ️ Lĩnh vực quản lý DWH', query_text: 'Hệ thống hiện đang quản lý và theo dõi số liệu của những ngành, lĩnh vực nào?' },
  { id: 'chip_l3_2', label: '📋 Hướng dẫn tra cứu công khai', query_text: 'Hướng dẫn tra cứu các chỉ tiêu kinh tế - xã hội công khai của tỉnh' },
  { id: 'chip_l3_3', label: '📈 Số liệu tai nạn lao động 2026', query_text: 'Năm 2026 toàn tỉnh có bao nhiêu vụ tai nạn lao động?' },
  { id: 'chip_l3_4', label: '📞 Hotline hỗ trợ công dân', query_text: 'Cho tôi thông tin hotline hỗ trợ công dân' },
];

const getWelcomeContact = (role: UserRoleProfile) => {
  if (role.role_level === 0) {
    return {
      title: `TRỢ LÝ KHO DỮ LIỆU DWH (LÃNH ĐẠO CẤP TỈNH • ${role.tenant_name})`,
      working_hours: 'Hỗ trợ 24/7 • Dữ liệu đồng bộ trực tiếp từ CSDL vna_wom_dev',
      hotlines: ['028 3535 2524'],
    };
  }
  if (role.role_level === 1) {
    return {
      title: `TRỢ LÝ KHO DỮ LIỆU DWH (LÃNH ĐẠO SỞ / BAN / NGÀNH)`,
      working_hours: 'Hỗ trợ 24/7 • Phân quyền cấp Sở trực thuộc',
      hotlines: ['028 3535 2524'],
    };
  }
  if (role.role_level === 2) {
    return {
      title: `TRỢ LÝ KHO DỮ LIỆU DWH (TRƯỞNG PHÒNG CHUYÊN MÔN)`,
      working_hours: 'Hỗ trợ 24/7 • Phân quyền cấp đơn vị cơ sở',
      hotlines: ['028 3535 2523', '028 3535 2524'],
    };
  }
  return {
    title: `TRỢ LÝ TRA CỨU DWH (CÔNG DÂN / DOANH NGHIỆP)`,
    working_hours: 'Hỗ trợ 24/7 • Tra cứu thông tin chỉ tiêu công khai',
    hotlines: ['028 3535 2523'],
  };
};

const getRoleChips = (level: number): QuickActionChip[] => {
  switch (level) {
    case 0:
      return CHIPS_LEVEL_0;
    case 1:
      return CHIPS_LEVEL_1;
    case 2:
      return CHIPS_LEVEL_2;
    default:
      return CHIPS_LEVEL_3;
  }
};

const getWelcomeMessage = (role: UserRoleProfile): ChatMessage => ({
  id: `welcome-${role.id}`,
  role: 'assistant',
  content: `Xin chào đồng chí! Hệ thống đã kích hoạt phân quyền **Level ${role.role_level} (${role.badge})** cho **${role.label}** (Tenant: ${role.tenant_code}). Bạn có thể chọn câu hỏi gợi ý bên dưới hoặc nhập câu hỏi trực tiếp:`,
  contact_support: getWelcomeContact(role),
  quick_action_chips: getRoleChips(role.role_level),
  timestamp: new Date().toISOString(),
});

export const ChatContainer: React.FC = () => {
  const [selectedRole, setSelectedRole] = useState<UserRoleProfile>(PRESET_ROLES[0]);
  const [messages, setMessages] = useState<ChatMessage[]>([getWelcomeMessage(PRESET_ROLES[0])]);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [currentStage, setCurrentStage] = useState<{ stage: string; message: string } | null>(null);
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

  // Tải danh sách lịch sử phiên khi khởi động
  useEffect(() => {
    const initSessions = async () => {
      const local = loadSessions();
      if (local.length > 0) {
        setSessions(local);
      }
      try {
        const cloudSessions = await fetchChatSessions();
        if (cloudSessions && cloudSessions.length > 0) {
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

  // Hàm lưu phiên hội thoại độc lập
  const persistSession = (sid: string, msgs: ChatMessage[], currentRole: UserRoleProfile) => {
    const userMessages = msgs.filter((m) => m.role === 'user');
    if (userMessages.length === 0) return;

    const firstUserText = userMessages[0].content;
    const title = firstUserText.length > 40 ? `${firstUserText.slice(0, 40)}...` : firstUserText;

    const currentSessions = loadSessions();
    const existingSession = currentSessions.find((s) => s.id === sid);
    const sessionObj: ChatSession = {
      id: sid,
      title: existingSession?.title || title,
      role: currentRole.id,
      level: currentRole.role_level,
      tenant_code: currentRole.tenant_code,
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

  const handleRoleSelect = (newRole: UserRoleProfile) => {
    if (newRole.id === selectedRole.id) return;
    setSelectedRole(newRole);
    setMessages([getWelcomeMessage(newRole)]);
    setSessionId(undefined);
  };

  const handleNewChat = () => {
    const newSid = `session-${Date.now()}`;
    setSessionId(newSid);
    setMessages([getWelcomeMessage(selectedRole)]);
  };

  const handleSelectSession = async (session: ChatSession) => {
    const matchingRole = PRESET_ROLES.find(
      (r) => r.id === session.role || r.role_level === session.level
    ) || PRESET_ROLES[0];
    setSelectedRole(matchingRole);
    setSessionId(session.id);

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

    setMessages(session.messages && session.messages.length > 0 ? session.messages : [getWelcomeMessage(matchingRole)]);
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

    // Chuỗi prompt kèm định danh tenant_code và level trực tiếp như yêu cầu
    const promptWithContext = `[tenant_code=${selectedRole.tenant_code}, level=${selectedRole.role_level}] ${queryText}`;

    const userMsg: ChatMessage = {
      id: userMsgId,
      role: 'user',
      content: promptWithContext,
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
    setCurrentStage({ stage: 'THINKING', message: '🔍 Đang phân tích câu hỏi & đối chiếu ngữ cảnh...' });

    let effectiveSessionId = sessionId || `session-${Date.now()}`;
    if (!sessionId) {
      setSessionId(effectiveSessionId);
    }

    // Lưu phiên
    persistSession(effectiveSessionId, nextMessages, selectedRole);

    try {
      const history = messages
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .slice(-6)
        .map((m) => ({ role: m.role, content: m.content }));

      const collectionName = selectedRole.role_level <= 1 ? 'hdsd_phuong_chunks' : 'hdsd_chunks';
      const mockToken = generateMockJWT(selectedRole);

      await sendMessageStream(
        promptWithContext,
        effectiveSessionId,
        history,
        {
          onStageUpdate: (stageData) => {
            setCurrentStage({
              stage: stageData.stage,
              message: stageData.message || 'Đang xử lý...',
            });
          },
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
            setCurrentStage(null);
            setMessages((prev) => {
              const updated = prev.map((msg) =>
                msg.id === botMsgId
                  ? {
                      ...msg,
                      content: doneData.full_answer,
                      contact_support: doneData.contact_support || msg.contact_support,
                      quick_action_chips: doneData.quick_action_chips || msg.quick_action_chips,
                      tabular_data: doneData.tabular_data || msg.tabular_data,
                    }
                  : msg
              );
              setTimeout(() => {
                persistSession(effectiveSessionId, updated, selectedRole);
              }, 0);
              return updated;
            });
          },
          onError: (errMsg) => {
            setCurrentStage(null);
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
                persistSession(effectiveSessionId, updated, selectedRole);
              }, 0);
              return updated;
            });
          },
        },
        selectedRole.id,
        collectionName,
        selectedRole.role_level,
        selectedRole.tenant_code,
        mockToken
      );
    } catch (err: any) {
      setCurrentStage(null);
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
          persistSession(effectiveSessionId, updated, selectedRole);
        }, 0);
        return updated;
      });
    } finally {
      setIsLoading(false);
      setCurrentStage(null);
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
                IPGov Chatbot Assistant
                <span className="text-[11px] bg-blue-50 text-blue-700 px-2.5 py-0.5 rounded-full font-medium border border-blue-200">
                  {selectedRole.tenant_name} ({selectedRole.tenant_code})
                </span>
              </h1>
              <p className="text-xs text-slate-500 flex items-center gap-1.5 mt-0.5">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                <span className="font-semibold text-slate-700">Level {selectedRole.role_level}:</span>
                <span className="truncate max-w-[260px] sm:max-w-none">{selectedRole.label}</span>
              </p>
            </div>
          </div>

          {/* Role & Level Selector & Reset Button */}
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 bg-slate-100 p-1.5 rounded-xl border border-slate-200">
              <span className="text-[11px] font-semibold text-slate-600 pl-1.5 hidden md:inline">Phân quyền:</span>
              <select
                value={selectedRole.id}
                onChange={(e) => {
                  const found = PRESET_ROLES.find((r) => r.id === e.target.value);
                  if (found) handleRoleSelect(found);
                }}
                className="text-xs bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer shadow-xs"
              >
                {PRESET_ROLES.map((role) => (
                  <option key={role.id} value={role.id}>
                    Level {role.role_level} • {role.label} (Tenant {role.tenant_code})
                  </option>
                ))}
              </select>
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
          currentStage={currentStage}
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
