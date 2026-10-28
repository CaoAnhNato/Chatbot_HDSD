'use client';

import React, { useState, useEffect, useRef } from 'react';
import { ChatMessage, ChatSession, QuickActionChip, PinnedDrawerItem } from '@/types/chat';
import {
  sendMessageStream,
  fetchChatSessions,
  fetchSessionHistory,
  renameChatSessionApi,
  deleteChatSessionApi,
  clearAllChatSessionsApi,
  fetchUserAccounts,
} from '@/lib/api';
import {
  loadSessions,
  saveSession,
  deleteSession,
  renameSession,
  clearAllSessions,
  mergeSessions,
  cleanSessionTitle,
  saveActiveSessionId,
  loadActiveSessionId,
} from '@/lib/storage';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { MediaViewer } from './MediaViewer';
import { ChatSidebar } from './ChatSidebar';
import { PinnedReferenceDrawer } from './PinnedReferenceDrawer';
import {
  PRESET_ROLES,
  UserRoleProfile,
  generateMockJWT,
  getLevelBadgeStyle,
} from '@/components/RoleSelector';
import {
  Bot,
  RefreshCcw,
  ShieldCheck,
  Building2,
  Landmark,
  PanelLeft,
  Database,
  Globe,
} from 'lucide-react';

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

// R1.2: ErrorBoundary bọc MessageList để chống trắng màn hình khi lỗi render tin nhắn
class ChatErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('ChatErrorBoundary caught an error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback || (
          <div className="flex-1 flex items-center justify-center p-6 text-center text-slate-500">
            <div className="max-w-md bg-white border border-amber-200 rounded-2xl p-5 shadow-xs space-y-2">
              <p className="font-semibold text-slate-800 text-sm">
                Đã xảy ra sự cố hiển thị danh sách tin nhắn.
              </p>
              <p className="text-xs text-slate-500">
                Toàn bộ dữ liệu phiên hội thoại vẫn được bảo toàn an toàn trong hệ thống.
              </p>
              <button
                type="button"
                onClick={() => this.setState({ hasError: false })}
                className="mt-2 px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
              >
                Tải lại danh sách tin nhắn
              </button>
            </div>
          </div>
        )
      );
    }
    return this.props.children;
  }
}


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
  if (role.role_level === 4) {
    return {
      title: `TRỢ LÝ KHO DỮ LIỆU DWH (LÃNH ĐẠO CẤP TỈNH • ${role.tenant_name})`,
      working_hours: 'Hỗ trợ 24/7 • Toàn quyền tra cứu dữ liệu CSDL vna_wom_dev',
      hotlines: ['028 3535 2524'],
    };
  }
  if (role.role_level === 3) {
    return {
      title: `TRỢ LÝ KHO DỮ LIỆU DWH (QUẢN TRỊ ĐA NHIỆM VỤ • ${role.tenant_name})`,
      working_hours: 'Hỗ trợ 24/7 • Phân quyền quản trị đa nhiệm vụ',
      hotlines: ['028 3535 2524'],
    };
  }
  if (role.role_level === 2) {
    return {
      title: `TRỢ LÝ KHO DỮ LIỆU DWH (CHUYÊN TRÁCH ĐA NGÀNH • ${role.tenant_name})`,
      working_hours: 'Hỗ trợ 24/7 • Phân quyền theo nhiệm vụ chuyên trách',
      hotlines: ['028 3535 2523', '028 3535 2524'],
    };
  }
  if (role.role_level === 1) {
    return {
      title: `TRỢ LÝ KHO DỮ LIỆU DWH (CHUYÊN VIÊN ĐƠN NHIỆM • ${role.tenant_name})`,
      working_hours: 'Hỗ trợ 24/7 • Phân quyền theo nhiệm vụ đơn ngành',
      hotlines: ['028 3535 2523'],
    };
  }
  return {
    title: `TRỢ LÝ TRA CỨU DWH (CÁN BỘ CƠ SỞ / GIỚI HẠN)`,
    working_hours: 'Hỗ trợ 24/7 • Giới hạn phạm vi nhiệm vụ công vụ',
    hotlines: ['028 3535 2523'],
  };
};

const getRoleChips = (level: number): QuickActionChip[] => {
  switch (level) {
    case 4:
      return CHIPS_LEVEL_0;
    case 3:
      return CHIPS_LEVEL_1;
    case 2:
      return CHIPS_LEVEL_2;
    case 1:
      return CHIPS_LEVEL_2;
    case 0:
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
  const [availableUsers, setAvailableUsers] = useState<UserRoleProfile[]>(PRESET_ROLES);
  const [selectedRole, setSelectedRole] = useState<UserRoleProfile>(PRESET_ROLES[0]);
  const [activeSchema, setActiveSchema] = useState<'dwh_internal' | 'dwh_public'>('dwh_internal');
  const [messages, setMessages] = useState<ChatMessage[]>([getWelcomeMessage(PRESET_ROLES[0])]);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [currentStage, setCurrentStage] = useState<{ stage: string; message: string } | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [pinnedItems, setPinnedItems] = useState<PinnedDrawerItem[]>([]);
  const [activePinnedTabId, setActivePinnedTabId] = useState<string | null>(null);
  const [pinnedToast, setPinnedToast] = useState<string | null>(null);

  const availableUsersRef = useRef<UserRoleProfile[]>(availableUsers);
  availableUsersRef.current = availableUsers;

  const selectedRoleRef = useRef<UserRoleProfile>(selectedRole);
  selectedRoleRef.current = selectedRole;

  const handleRoleSelectRef = useRef<(newRole: UserRoleProfile) => void>(() => {});

  const handlePinItem = (item: PinnedDrawerItem) => {
    setPinnedItems((prev) => {
      const existingIdx = prev.findIndex((p) => p.id === item.id);
      if (existingIdx >= 0) {
        setActivePinnedTabId(item.id);
        return prev;
      }
      if (prev.length >= 3) {
        setPinnedToast('Khay ghim tối đa 3 thẻ. Đã tự động thay thế thẻ ghim cũ nhất.');
        setTimeout(() => setPinnedToast(null), 3500);
        const next = [...prev.slice(1), item];
        setActivePinnedTabId(item.id);
        return next;
      }
      const next = [...prev, item];
      setActivePinnedTabId(item.id);
      return next;
    });
  };

  const handleUnpinItem = (id: string) => {
    setPinnedItems((prev) => {
      const next = prev.filter((p) => p.id !== id);
      if (activePinnedTabId === id) {
        setActivePinnedTabId(next.length > 0 ? next[next.length - 1].id : null);
      }
      return next;
    });
  };

  const [viewerState, setViewerState] = useState<{
    isOpen: boolean;
    imageUrl: string | null;
    altText: string;
  }>({
    isOpen: false,
    imageUrl: null,
    altText: '',
  });

  // Tải danh sách lịch sử phiên & tự động khôi phục phiên đang hoạt động khi khởi động
  useEffect(() => {
    let isMounted = true;

    // 1. Khôi phục schema từ localStorage nếu có
    try {
      const savedSchema = localStorage.getItem('ipgov_active_schema');
      if (savedSchema === 'dwh_internal' || savedSchema === 'dwh_public') {
        setActiveSchema(savedSchema);
      }
    } catch (e) {}

    // 2. Khôi phục user từ localStorage nếu có
    try {
      const savedUserJson = localStorage.getItem('ipgov_active_user');
      if (savedUserJson) {
        const parsed = JSON.parse(savedUserJson);
        const matched = PRESET_ROLES.find(
          (u) =>
            u.id === parsed.id ||
            u.username === parsed.username ||
            u.name === parsed.name
        );
        if (matched) {
          setSelectedRole(matched);
        }
      }
    } catch (e) {}

    // 3. Tải danh sách người dùng được phân loại từ API backend
    const loadUsers = async () => {
      try {
        const users = await fetchUserAccounts();
        if (isMounted && users && users.length > 0) {
          setAvailableUsers(users);
          setSelectedRole((current) => {
            const matched = users.find(
              (u) =>
                u.id === current.id ||
                u.username === current.username ||
                u.name === current.name
            );
            return matched || users[0];
          });
        }
      } catch (err) {
        console.warn('Lỗi khi fetch danh sách người dùng động:', err);
      }
    };
    void loadUsers();

    // 4. Lắng nghe custom events từ Playwright test runner hoặc các component khác
    const onSchemaSwitched = (e: Event) => {
      const customEvent = e as CustomEvent<string>;
      const target = customEvent.detail;
      if (target === 'dwh_internal' || target === 'dwh_public') {
        setActiveSchema(target);
      }
    };

    const onUserSwitched = (e: Event) => {
      const customEvent = e as CustomEvent<any>;
      const detail = customEvent.detail;
      if (!detail) return;
      const targetId = detail.user_id || detail.id || detail.username || detail.name;
      const users = availableUsersRef.current;
      const found = users.find(
        (u) =>
          u.id === targetId ||
          u.username === targetId ||
          u.name === targetId
      );
      if (found) {
        handleRoleSelectRef.current(found);
      }
    };

    window.addEventListener('ipgov_schema_switched', onSchemaSwitched);
    window.addEventListener('ipgov_user_switched', onUserSwitched);

    const restoreSessionView = async (target: ChatSession) => {
      const matchingRole =
        PRESET_ROLES.find((r) => r.id === target.role || r.role_level === target.level) ||
        PRESET_ROLES[0];
      setSelectedRole(matchingRole);
      setSessionId(target.id);
      saveActiveSessionId(target.id);

      const hasUnenrichedTable = (target.messages || []).some((m) => {
        const rows = (m.tabular_data as any)?.rows;
        return (
          Array.isArray(rows) &&
          rows.length > 0 &&
          rows.some(
            (r: any) =>
              r &&
              (r.criteria_id || r.ten_chi_tieu || r.item || r.criteria_name) &&
              !r.timeline_values
          )
        );
      });

      if (target.messages && target.messages.length > 0 && !hasUnenrichedTable) {
        setMessages(target.messages);
        return;
      }
      if (target.messages && target.messages.length > 0) {
        setMessages(target.messages);
      }
      try {
        const msgs = await fetchSessionHistory(target.id);
        if (msgs && msgs.length > 0) {
          setMessages(msgs);
          target.messages = msgs;
          saveSession(target, { preserveTimestamp: true });
        }
      } catch (err) {
        console.warn(`Could not restore messages for session ${target.id}:`, err);
      }
    };

    const initSessions = async () => {
      const local = loadSessions();
      if (local.length > 0) {
        setSessions(local);
      }
      let finalSessions = local;
      try {
        const cloudSessions = await fetchChatSessions();
        if (cloudSessions && cloudSessions.length > 0) {
          finalSessions = mergeSessions(local, cloudSessions);
          setSessions(finalSessions);
        }
      } catch (err) {
        console.warn('Could not sync sessions from cloud, keeping local state:', err);
      }

      if (finalSessions.length > 0) {
        const savedActiveId = loadActiveSessionId();
        const target = savedActiveId
          ? finalSessions.find((s) => s.id === savedActiveId)
          : undefined;
        if (target) {
          await restoreSessionView(target);
        }
      }
    };
    initSessions();

    return () => {
      isMounted = false;
      window.removeEventListener('ipgov_schema_switched', onSchemaSwitched);
      window.removeEventListener('ipgov_user_switched', onUserSwitched);
    };
  }, []);

  const handleSchemaSwitch = (nextSchema: 'dwh_internal' | 'dwh_public') => {
    if (nextSchema === activeSchema) return;
    setActiveSchema(nextSchema);
    try {
      localStorage.setItem('ipgov_active_schema', nextSchema);
      window.dispatchEvent(new CustomEvent('ipgov_schema_switched', { detail: nextSchema }));
    } catch (e) {}
  };

  // Hàm lưu phiên hội thoại độc lập
  const persistSession = (sid: string, msgs: ChatMessage[], currentRole: UserRoleProfile) => {
    const persistableMsgs = msgs
      .filter((m) => !String(m.id || '').startsWith('welcome-') && !(m.isStreaming && !m.content))
      .map((m) => (m.isStreaming ? { ...m, isStreaming: false } : m));
    const userMessages = persistableMsgs.filter((m) => m.role === 'user');
    if (userMessages.length === 0) return;

    const firstUserText = userMessages[0].content;
    const title = cleanSessionTitle(firstUserText);

    const currentSessions = loadSessions();
    const existingSession = currentSessions.find((s) => s.id === sid);
    const sessionObj: ChatSession = {
      id: sid,
      title: existingSession?.title ? cleanSessionTitle(existingSession.title) : title,
      role: currentRole.id,
      level: currentRole.role_level,
      tenant_code: currentRole.tenant_code,
      createdAt: existingSession?.createdAt || new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      messages: persistableMsgs,
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
    setSelectedRole(newRole);
    try {
      localStorage.setItem('ipgov_active_user', JSON.stringify(newRole));
    } catch (e) {}

    // CRITICAL CONTINUOUS SESSION RULE:
    // If user messages exist in messages, DO NOT reset messages or sessionId!
    // Keep the entire 30-quest continuous session history intact!
    setMessages((prev) => {
      const hasUserMessages = prev.some((m) => m.role === 'user');
      if (!hasUserMessages) {
        setSessionId(undefined);
        saveActiveSessionId(undefined);
        return [getWelcomeMessage(newRole)];
      }
      return prev;
    });
  };
  handleRoleSelectRef.current = handleRoleSelect;

  const handleNewChat = () => {
    const newSid = `session-${Date.now()}`;
    setSessionId(newSid);
    saveActiveSessionId(undefined);
    setMessages([getWelcomeMessage(selectedRole)]);
  };

  const handleSelectSession = async (session: ChatSession) => {
    const matchingRole = availableUsers.find(
      (r) => r.id === session.role || r.role_level === session.level
    ) || availableUsers[0];
    setSelectedRole(matchingRole);
    setSessionId(session.id);
    saveActiveSessionId(session.id);

    const hasUnenrichedTable = (session.messages || []).some((m) => {
      const rows = (m.tabular_data as any)?.rows;
      return (
        Array.isArray(rows) &&
        rows.length > 0 &&
        rows.some(
          (r: any) =>
            r &&
            (r.criteria_id || r.ten_chi_tieu || r.item || r.criteria_name) &&
            !r.timeline_values
        )
      );
    });

    if (!session.messages || session.messages.length === 0 || hasUnenrichedTable) {
      if (session.messages && session.messages.length > 0) {
        setMessages(session.messages);
      }
      try {
        const msgs = await fetchSessionHistory(session.id);
        if (msgs && msgs.length > 0) {
          setMessages(msgs);
          session.messages = msgs;
          saveSession(session, { preserveTimestamp: true });
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
    void deleteChatSessionApi(sid);
    const updated = loadSessions();
    setSessions(updated);
    if (sessionId === sid) {
      if (updated.length > 0) {
        void handleSelectSession(updated[0]);
      } else {
        handleNewChat();
      }
    }
  };

  const handleRenameSession = (sid: string, newTitle: string) => {
    renameSession(sid, newTitle);
    void renameChatSessionApi(sid, newTitle);
    setSessions(loadSessions());
  };

  const handleClearAll = () => {
    clearAllSessions();
    void clearAllChatSessionsApi();
    setSessions([]);
    handleNewChat();
  };

  const handleSendMessage = async (queryText: string) => {
    const userMsgId = `user-${Date.now()}`;
    const botMsgId = `bot-${Date.now()}`;

    const cleanQueryText = queryText.replace(/^\[[^\]]+\]\s*/i, '').trim();

    // Chuỗi prompt kèm định danh user, level, tenant_code và schema gửi xuống backend API
    const promptWithContext = `[user=${selectedRole.username || selectedRole.id}, level=${selectedRole.role_level}, tenant_code=${selectedRole.tenant_code}, schema=${activeSchema}] ${cleanQueryText}`;

    const userMsg: ChatMessage = {
      id: userMsgId,
      role: 'user',
      content: cleanQueryText,
      timestamp: new Date().toISOString(),
    };

    const initialBotMsg: ChatMessage = {
      id: botMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      isStreaming: true,
    };

    const nextMessages = [...messages, userMsg, initialBotMsg];
    setMessages(nextMessages);
    setIsLoading(true);
    setCurrentStage({ stage: 'ĐANG XỬ LÝ', message: '🔍 Đang phân tích câu hỏi & đối chiếu ngữ cảnh...' });

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
                      isStreaming: false,
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
                      isStreaming: false,
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
        mockToken,
        activeSchema,
        selectedRole.user_id,
        selectedRole.label
      );
    } catch (err: any) {
      setCurrentStage(null);
      setMessages((prev) => {
        const updated = prev.map((msg) =>
          msg.id === botMsgId
            ? {
                ...msg,
                content: `⚠️ Không thể kết nối với máy chủ AI (${err.message || 'Lỗi mạng'}). Vui lòng kiểm tra backend server đang chạy tại port 8000.`,
                isStreaming: false,
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
          <div className="flex items-center gap-3 min-w-0">
            {!isSidebarOpen && (
              <button
                onClick={() => setIsSidebarOpen(true)}
                className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors border border-slate-200 shadow-xs shrink-0"
                title="Mở lịch sử chat"
                aria-label="Mở lịch sử chat"
              >
                <PanelLeft className="w-5 h-5" />
              </button>
            )}

            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-md shrink-0">
              <Bot className="w-6 h-6" />
            </div>

            <div className="min-w-0">
              <h1 className="text-base font-bold text-slate-800 flex items-center gap-2 truncate">
                IPGov Chatbot Assistant
                <span className="text-[11px] bg-blue-50 text-blue-700 px-2.5 py-0.5 rounded-full font-medium border border-blue-200 whitespace-nowrap">
                  {selectedRole.tenant_name} ({selectedRole.tenant_code})
                </span>
              </h1>
              <p className="text-xs text-slate-500 flex items-center gap-1.5 mt-0.5">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                <span className="font-semibold text-slate-700 whitespace-nowrap">Level {selectedRole.role_level}:</span>
                <span className="truncate max-w-[200px] sm:max-w-[320px]">{selectedRole.label}</span>
              </p>
            </div>
          </div>

          {/* Role & Level Selector & Schema Switch & Reset Button */}
          <div className="flex items-center gap-2 shrink-0">
            {/* Fast Schema Switch Pill [dwh_internal | dwh_public] */}
            <div
              data-testid="schema-switch-button"
              className="inline-flex items-center p-1 bg-slate-100 rounded-xl border border-slate-200/90 shadow-xs shrink-0 select-none"
              role="group"
              aria-label="Chọn kho dữ liệu"
            >
              <button
                type="button"
                data-testid="schema-toggle-internal"
                data-state={activeSchema === 'dwh_internal' ? 'active' : 'inactive'}
                aria-pressed={activeSchema === 'dwh_internal'}
                onClick={() => handleSchemaSwitch('dwh_internal')}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all duration-150 whitespace-nowrap cursor-pointer ${
                  activeSchema === 'dwh_internal'
                    ? 'bg-white text-indigo-700 font-semibold shadow-xs border border-indigo-100'
                    : 'text-slate-500 hover:text-slate-800 hover:bg-slate-200/60 border border-transparent'
                }`}
                title="Kho dữ liệu nội bộ (dwh_internal): Phân quyền theo nhiệm vụ công vụ"
              >
                <Database className={`w-3.5 h-3.5 ${activeSchema === 'dwh_internal' ? 'text-indigo-600' : 'text-slate-400'}`} />
                <span>Nội bộ</span>
                <span
                  className={`text-[10px] font-mono px-1 py-0.5 rounded transition-colors ${
                    activeSchema === 'dwh_internal'
                      ? 'bg-indigo-50 text-indigo-700 font-semibold'
                      : 'text-slate-400'
                  }`}
                >
                  dwh_internal
                </span>
              </button>

              <button
                type="button"
                data-testid="schema-toggle-public"
                data-state={activeSchema === 'dwh_public' ? 'active' : 'inactive'}
                aria-pressed={activeSchema === 'dwh_public'}
                onClick={() => handleSchemaSwitch('dwh_public')}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all duration-150 whitespace-nowrap cursor-pointer ${
                  activeSchema === 'dwh_public'
                    ? 'bg-white text-emerald-700 font-semibold shadow-xs border border-emerald-100'
                    : 'text-slate-500 hover:text-slate-800 hover:bg-slate-200/60 border border-transparent'
                }`}
                title="Kho dữ liệu công khai (dwh_public): Mọi tài khoản đều có quyền tra cứu"
              >
                <Globe className={`w-3.5 h-3.5 ${activeSchema === 'dwh_public' ? 'text-emerald-600' : 'text-slate-400'}`} />
                <span>Công khai</span>
                <span
                  className={`text-[10px] font-mono px-1 py-0.5 rounded transition-colors ${
                    activeSchema === 'dwh_public'
                      ? 'bg-emerald-50 text-emerald-700 font-semibold'
                      : 'text-slate-400'
                  }`}
                >
                  dwh_public
                </span>
              </button>
            </div>

            {/* Header User Selector Dropdown with Level Badges & Mission Count */}
            <div
              data-testid="header-user-selector-container"
              className="flex items-center gap-1.5 bg-slate-100 p-1.5 rounded-xl border border-slate-200 shadow-xs shrink-0 select-none"
            >
              {/* Level Badge Chip */}
              <span
                className={`text-xs px-2 py-0.5 rounded-md border flex items-center gap-1 shrink-0 ${getLevelBadgeStyle(selectedRole?.role_level ?? 0)?.chipClass || ''}`}
                title={`Cấp bậc thẩm quyền: Level ${selectedRole?.role_level ?? 0}`}
              >
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Level {selectedRole?.role_level ?? 0}</span>
              </span>

              {/* Mission Count Chip */}
              <span
                className="text-[11px] font-mono px-2 py-0.5 rounded bg-white text-slate-700 border border-slate-200 hidden sm:inline shrink-0"
                title={selectedRole?.is_unrestricted ? 'Toàn quyền truy cập mọi nhiệm vụ' : `Số lượng nhiệm vụ được phân công: ${selectedRole?.mission_count ?? 0}`}
              >
                {selectedRole?.is_unrestricted ? 'Toàn quyền' : `${selectedRole?.mission_count ?? 0} NV`}
              </span>

              {/* Native Select with full Playwright & Human compatibility */}
              <select
                id="header-user-selector"
                name="user_role"
                data-testid="header-user-selector"
                value={selectedRole?.id || ''}
                onChange={(e) => {
                  const found = availableUsers.find(
                    (u) => u.id === e.target.value || u.username === e.target.value
                  );
                  if (found) handleRoleSelect(found);
                }}
                className="text-xs bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer shadow-xs max-w-[210px] sm:max-w-[280px] truncate"
                aria-label="Chọn tài khoản công vụ"
              >
                {availableUsers.map((user) => (
                  <option key={user.id} value={user.id}>
                    Level {user.role_level} • {user.name} ({user.username}) - {user.is_unrestricted ? 'Toàn quyền' : `${user.mission_count} NV`}
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={handleNewChat}
              className="p-2.5 rounded-xl text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition border border-transparent hover:border-slate-200 shrink-0"
              title="Làm mới cuộc hội thoại"
            >
              <RefreshCcw className="w-4 h-4" />
            </button>
          </div>
        </header>

        {/* Khung nội dung Split-Screen: Cột Chat bên trái + Khay Tham Chiếu Đã Ghim bên phải (Feature 2 Tier 2) */}
        <div className="flex-1 flex min-h-0 overflow-hidden">
          <div className="flex-1 flex flex-col min-h-0 relative overflow-hidden">
            {/* Messages List (bọc trong ChatErrorBoundary để chống sập giao diện đa lượt) */}
            <ChatErrorBoundary>
              <MessageList
                messages={messages}
                isLoading={isLoading}
                currentStage={currentStage}
                onImageClick={(imageUrl, altText) =>
                  setViewerState({ isOpen: true, imageUrl, altText })
                }
                onSelectChip={(queryText) => handleSendMessage(queryText)}
                onPinItem={handlePinItem}
              />
            </ChatErrorBoundary>

            {/* Input Form */}
            <ChatInput onSendMessage={handleSendMessage} isLoading={isLoading} />
          </div>

          <PinnedReferenceDrawer
            items={pinnedItems}
            activeTabId={activePinnedTabId}
            onSelectTab={(id) => setActivePinnedTabId(id)}
            onUnpin={handleUnpinItem}
            onClearAll={() => {
              setPinnedItems([]);
              setActivePinnedTabId(null);
            }}
            onSelectChip={(queryText) => handleSendMessage(queryText)}
            toastMessage={pinnedToast}
          />
        </div>

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
