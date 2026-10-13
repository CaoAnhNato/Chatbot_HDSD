import axios from "axios";
import { ChatApiResponse, ChatSession, ChatMessage } from "@/types/chat";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

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
  collection?: string
): Promise<ChatApiResponse> => {
  const response = await apiClient.post("/chat", {
    query,
    session_id: sessionId,
    history,
    role,
    collection,
  });

  if (response.data && response.data.success) {
    return response.data.data;
  }
  throw new Error(response.data?.message || "Failed to send message");
};

export interface StreamDonePayload {
  full_answer: string;
  contact_support?: any;
  metrics?: any;
}

export interface StreamHandlers {
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
  collection?: string
) => {
  const response = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      query,
      session_id: sessionId,
      history,
      role,
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
          if (eventType === "metadata") {
            handlers.onMetadata?.(data);
          } else if (eventType === "token") {
            handlers.onToken?.(data.content ?? "");
          } else if (eventType === "done") {
            handlers.onDone?.({
              full_answer: data.full_answer ?? "",
              contact_support: data.contact_support,
              metrics: data.metrics,
            });
          } else if (eventType === "error") {
            handlers.onError?.(data.message ?? "Lỗi xử lý");
          } else {
            // Fallback inference if eventType is default
            if (data.images !== undefined || data.youtube_links !== undefined) {
              handlers.onMetadata?.(data);
            } else if (data.content !== undefined) {
              handlers.onToken?.(data.content);
            } else if (data.full_answer !== undefined) {
              handlers.onDone?.({
                full_answer: data.full_answer,
                contact_support: data.contact_support,
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
