import { cache } from "react";

export type MeResponse = {
  id: string;
  email: string;
  email_verified: boolean;
  display_name: string | null;
  avatar_url: string | null;
  status: string;
  is_super_admin: boolean;
  last_login_at: string | null;
  created_at: string | null;
};

export type ThemePreference = "LIGHT" | "DARK" | "SYSTEM";

export type UserSettings = {
  theme: ThemePreference;
  locale: string;
  default_model: string | null;
};

export type Workspace = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  created_by_user_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  my_role: string | null;
  space_count: number;
  source_count: number;
};

export type Space = {
  id: string;
  workspace_id: string;
  name: string;
  slug: string;
  description: string | null;
  icon_key: string;
  accent_key: string;
  created_by_user_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
  deleted_at: string | null;
  my_role: string | null;
  is_starred: boolean;
  document_count: number;
  source_count: number;
  owner: { id: string; display_name: string | null; email: string | null } | null;
};

export type SpaceListResponse = {
  items: Space[];
  total: number;
  page: number;
  page_size: number;
  counts: Record<string, number>;
};

export type WorkspaceOverview = {
  space_count: number;
  document_count: number;
  source_count: number;
  storage_bytes: number;
  member_count: number;
  active_share_link_count: number;
};

export type ShareRedeemResult = {
  target_type: "WORKSPACE" | "SPACE";
  workspace_id: string;
  space_id: string | null;
  role: string;
};

export type Activity = {
  id: string;
  action: string;
  resource_type: string;
  workspace_id: string | null;
  workspace_name: string | null;
  created_at: string;
  metadata: Record<string, unknown> | null;
};

export type Dashboard = {
  summary: {
    owned_workspace_count: number;
    workspace_limit: number;
    space_count: number;
    source_count: number;
    document_count: number;
    conversation_count_month: number;
  };
  recent_workspaces: Workspace[];
  recent_spaces: unknown[];
  activity: Activity[];
};

export type Member = {
  id: string;
  user_id: string;
  role: string;
  source: string;
  email: string | null;
  display_name: string | null;
};

export type ShareLink = {
  id: string;
  role: string;
  status: string;
  use_count: number;
  created_at: string;
  revoked_at: string | null;
  url?: string | null;
  token?: string | null;
};

function apiBase(): string {
  return process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
}

export const fetchMe = cache(async (cookieHeader: string): Promise<MeResponse | null> => {
  try {
    const resp = await fetch(`${apiBase()}/api/v1/me`, {
      headers: { cookie: cookieHeader },
      cache: "no-store",
    });
    if (!resp.ok) return null;
    return (await resp.json()) as MeResponse;
  } catch {
    return null;
  }
});

export function publicApiBase(): string {
  // Browser: same-origin so session cookies work (Next rewrites /api/v1 → API).
  if (typeof window !== "undefined") {
    return "";
  }
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
}

export function csrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  const match = document.cookie.match(/(?:^|; )kl_csrf=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : undefined;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
  ) {
    super(message);
  }
}

export async function clientApi<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const method = (options.method || "GET").toUpperCase();
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  // Let the browser set multipart boundary for FormData uploads.
  if (options.body && !isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrf = csrfToken();
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }

  const response = await fetch(`${publicApiBase()}/api/v1${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message =
      body?.error?.message ||
      (typeof body?.detail === "string" ? body.detail : null) ||
      body?.detail?.message ||
      "Request failed. Please try again.";
    const code = body?.error?.code || body?.detail?.code || undefined;
    throw new ApiError(message, response.status, code);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
