export type AdminSparkPoint = {
  date: string;
  value: number;
};

export type AdminKpi = {
  key: string;
  label: string;
  value: number;
  period_value: number;
  previous_period_value: number;
  change_percent: number | null;
  has_comparison: boolean;
  sparkline: AdminSparkPoint[];
};

export type AdminOverview = {
  user_count: number;
  active_user_count: number;
  suspended_user_count: number;
  workspace_count: number;
  space_count: number;
  source_count: number;
  document_count: number;
  running_job_count: number;
  ai_message_count: number;
  ai_input_tokens: number;
  ai_output_tokens: number;
  timezone: string;
  range_start: string;
  range_end: string;
  previous_range_start: string;
  previous_range_end: string;
  range_start_date: string;
  range_end_date: string;
  previous_range_start_date: string;
  previous_range_end_date: string;
  kpis: AdminKpi[];
};

export type AdminActivityPoint = {
  date: string;
  documents: number;
  ai_queries: number;
  users: number;
};

export type AdminActivitySeries = {
  granularity: "daily" | "weekly" | "monthly";
  timezone: string;
  range_start: string;
  range_end: string;
  points: AdminActivityPoint[];
};

export type AdminSourceSlice = {
  key: string;
  label: string;
  count: number;
  percent: number;
};

export type AdminSourceDistribution = {
  total: number;
  items: AdminSourceSlice[];
};

export type AdminAiUsage = {
  period: string;
  timezone: string;
  range_start: string;
  range_end: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  message_count: number;
};

export type AdminRecentActivityItem = {
  id: string;
  action: string;
  message: string;
  actor_name: string | null;
  created_at: string;
};

export type AdminRecentActivity = {
  items: AdminRecentActivityItem[];
  total: number;
};

export type AdminTopDocument = {
  id: string;
  title: string;
  source_type: string;
  workspace_name: string;
  space_name: string;
  views: number;
  last_viewed_at: string | null;
};

export type AdminTopDocuments = {
  views_tracked: boolean;
  items: AdminTopDocument[];
};

export type AdminHealthStatus = "healthy" | "warning" | "degraded" | "offline" | "unknown";

export type AdminHealthItem = {
  key: string;
  label: string;
  status: AdminHealthStatus;
  detail: string;
  verified: boolean;
  used_bytes?: number | null;
  used_percent?: number | null;
  value?: number | null;
};

export type AdminSystemHealth = {
  timezone: string;
  items: AdminHealthItem[];
};

export type AdminGranularity = "daily" | "weekly" | "monthly";
export type AdminAiPeriod = "today" | "this_week" | "this_month" | "custom";
