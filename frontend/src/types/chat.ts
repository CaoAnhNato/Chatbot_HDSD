export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  images?: string[];
  youtube_links?: string[];
  contact_support?: ContactSupportInfo;
  quick_action_chips?: QuickActionChip[];
  intent?: string;
}

export interface QuickActionChip {
  id: string;
  label: string;
  query_text: string;
}

export interface ContactSupportInfo {
  title: string;
  working_hours: string;
  hotlines: string[];
  zalo?: string | null;
}

export interface ChatApiResponse {
  session_id: string;
  answer: string;
  images: string[];
  youtube_links: string[];
  quick_action_chips?: QuickActionChip[];
  contact_support?: ContactSupportInfo;
  intent?: string;
}

export interface ChatSession {
  id: string;
  title: string;
  role: 'phuong' | 'dn';
  createdAt: string;
  updatedAt: string;
  messages: ChatMessage[];
}
