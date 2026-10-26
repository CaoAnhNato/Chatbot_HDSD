export interface TableColumn {
  key: string;
  label: string;
  align: 'left' | 'center' | 'right';
  data_type: 'text' | 'number' | 'badge' | 'date';
}

export interface TemporalScopeMeta {
  period_type?: 'YEAR' | 'QUARTER' | 'HALF_YEAR' | 'MONTH' | 'MONTH_SPAN' | 'SPECIFIC_DATE' | string;
  period_label?: string;
  label?: string;
  year: string;
  date_from?: string | null;
  date_to?: string | null;
  specific_date?: string | null;
  month_filter?: number | null;
  active_report_date?: string | null;
  query_suffix: string;
}

export interface TimelineSnapshotItem {
  date?: string;            // DD/MM/YYYY
  report_date: string;      // DD/MM/YYYY
  iso_date: string;         // YYYY-MM-DD
  period_label: string;     // VD: "Kỳ Q1 (31/03/2026)"
  value: string;            // Giá trị hiển thị
  raw_value?: number | null;
  office: string;
  mission: string;
  delta_prev?: number | null;
  delta_pct?: number | null;
}

export interface SingleMetricCardData {
  criterion_id?: string;
  criteria_id?: string;
  criterion_name?: string;
  criteria_name?: string;
  parent_name?: string;
  hierarchy_badge?: string;
  hierarchy_label?: string;
  current_value?: string;
  active_value?: string;
  raw_value?: number | null;
  office?: string;
  office_name?: string;
  mission?: string;
  mission_name?: string;
  report_date?: string;
  active_report_date?: string;
  temporal_shift_notice?: string;
  temporal_scope?: TemporalScopeMeta;
  timeline_snapshots: TimelineSnapshotItem[];
}

export interface TabularData {
  columns: TableColumn[];
  rows: Record<string, any>[];
  total_records: number;
  title?: string;
  raw_fact_count?: number;
  mission_filter?: string | null;
  multi_parent_rows?: Record<string, any>[];
  temporal_scope?: TemporalScopeMeta;
  context_query_template?: string;
  single_metric_card?: SingleMetricCardData;
  status_summary?: {
    approved: number;
    draft: number;
    pending: number;
    rejected: number;
    total: number;
  };
  draft_criteria_rows?: Record<string, any>[];
  draft_vs_approved_diff?: Record<string, any>[];
  blocked_draft_access?: boolean;
  tree_modal?: Record<string, any>;
  trees_by_root_id?: Record<string, any>;
  level1_rows?: Record<string, any>[];
  period_snapshots?: Record<string, Record<string, any>[]>;
  parent_criterion_name?: string;
  parent_timeline_values?: Record<string, string>;
}

export interface PinnedDrawerItem {
  id: string;
  title: string;
  subtitle?: string;
  type: 'table' | 'tree' | 'comparison' | 'metric' | 'metric_card';
  pinnedAt: string;
  temporal_scope?: TemporalScopeMeta;
  payload?: any;
  tabular_data?: TabularData;
  tree_node?: any;
  comparison_nodes?: any[];
}

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
  tabular_data?: TabularData;
  isStreaming?: boolean;
}

export interface QuickActionChip {
  id: string;
  label: string;
  query_text: string;
  preview_value?: string | null;
  unit_or_status?: string | null;
  child_count?: number;
  is_parent_group?: boolean;
  timeline_values?: Record<string, string>;
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
  tabular_data?: TabularData;
}

export interface ChatSession {
  id: string;
  title: string;
  role: string;
  level?: number;
  tenant_code?: string;
  createdAt: string;
  updatedAt: string;
  messages: ChatMessage[];
}

