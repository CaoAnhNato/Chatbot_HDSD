import axios from "axios";
import { ChatApiResponse, ChatSession, ChatMessage } from "@/types/chat";

const getApiBaseUrl = (): string => {
  const envUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
  let trimmed = envUrl.trim().replace(/\/+$/, "");
  if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) {
    trimmed = `https://${trimmed}`;
  }
  return trimmed.endsWith("/api/v1") ? trimmed : `${trimmed}/api/v1`;
};

const API_BASE_URL = getApiBaseUrl();

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

export const fetchChatSessions = async (limit: number = 50): Promise<ChatSession[]> => {
  try {
    const response = await apiClient.get(`/chat/sessions?limit=${limit}`);
    if (response.data && response.data.success) {
      return response.data.data;
    }
    return [];
  } catch (err) {
    console.warn("Failed to fetch chat sessions from server:", err);
    return [];
  }
};

export const fetchSessionHistory = async (sessionId: string): Promise<ChatMessage[]> => {
  try {
    const response = await apiClient.get(`/chat/history/${sessionId}`);
    if (response.data && response.data.success) {
      return response.data.data.map((m: any) => ({
        ...m,
        timestamp: m.timestamp || m.created_at || new Date().toISOString(),
      }));
    }
    return [];
  } catch (err) {
    console.warn(`Failed to fetch session history for ${sessionId}:`, err);
    return [];
  }
};

export const sendMessageToBot = async (
  query: string,
  sessionId?: string,
  history: Array<{ role: string; content: string }> = [],
  role: string = "phuong",
  collection?: string,
  level?: number,
  tenant_code?: string,
  token?: string
): Promise<ChatApiResponse> => {
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await apiClient.post(
    "/chat",
    {
      prompt: query,
      query,
      session_id: sessionId,
      history,
      role,
      level,
      tenant_code,
      collection,
    },
    { headers }
  );

  if (response.data && response.data.success) {
    return response.data.data;
  }
  throw new Error(response.data?.message || "Failed to send message");
};

export interface StreamDonePayload {
  full_answer: string;
  contact_support?: any;
  quick_action_chips?: any[];
  tabular_data?: any;
  metrics?: any;
}

export interface StreamHandlers {
  onStageUpdate?: (stageData: { stage: string; message: string; [key: string]: any }) => void;
  onMetadata?: (metadata: Partial<ChatApiResponse>) => void;
  onToken?: (token: string) => void;
  onDone?: (doneData: StreamDonePayload) => void;
  onError?: (error: string) => void;
}

export const sendMessageStream = async (
  query: string,
  sessionId: string | undefined,
  history: Array<{ role: string; content: string }> = [],
  handlers: StreamHandlers,
  role: string = "phuong",
  collection?: string,
  level?: number,
  tenant_code?: string,
  token?: string
) => {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      prompt: query,
      query,
      session_id: sessionId,
      history,
      role,
      level,
      tenant_code,
      collection,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("Response body is not readable");
  }

  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";

    for (const block of blocks) {
      const lines = block.split("\n");
      let eventType = "message";
      let dataStr = "";

      for (const line of lines) {
        if (line.startsWith("event: ")) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          dataStr = line.slice(6).trim();
        }
      }

      if (dataStr) {
        try {
          const data = JSON.parse(dataStr);
          if (eventType === "stage_update") {
            handlers.onStageUpdate?.(data);
          } else if (eventType === "metadata") {
            handlers.onMetadata?.(data);
          } else if (eventType === "token" || eventType === "content_chunk") {
            handlers.onToken?.(data.content ?? data.chunk ?? "");
          } else if (eventType === "done") {
            handlers.onDone?.({
              full_answer: data.full_answer ?? "",
              contact_support: data.contact_support,
              quick_action_chips: data.quick_action_chips,
              tabular_data: data.tabular_data,
              metrics: data.metrics,
            });
          } else if (eventType === "error") {
            handlers.onError?.(data.message ?? data.error ?? "Lỗi xử lý");
          } else {
            // Fallback inference if eventType is default
            if (data.stage !== undefined) {
              handlers.onStageUpdate?.(data);
            } else if (data.images !== undefined || data.youtube_links !== undefined) {
              handlers.onMetadata?.(data);
            } else if (data.content !== undefined || data.chunk !== undefined) {
              handlers.onToken?.(data.content ?? data.chunk ?? "");
            } else if (data.full_answer !== undefined) {
              handlers.onDone?.({
                full_answer: data.full_answer,
                contact_support: data.contact_support,
                quick_action_chips: data.quick_action_chips,
                tabular_data: data.tabular_data,
                metrics: data.metrics,
              });
            }
          }
        } catch (e) {
          console.error("Failed to parse SSE line:", block, e);
        }
      }
    }
  }
};

export const checkApiHealth = async () => {
  const response = await apiClient.get("/health");
  return response.data;
};
