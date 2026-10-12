export type LoginAuthProps = {
  googleConfigured: boolean;
  /** False when `/auth/status` could not be reached (do not treat as OAuth disabled). */
  authStatusOk: boolean;
  error: string | null;
  nextPath: string;
};

/** @deprecated Use LoginAuthProps */
export type WelcomeAuthProps = LoginAuthProps;

export function safeNextPath(next: string | undefined): string {
  if (next?.startsWith("/") && !next.startsWith("//")) return next;
  return "/app";
}

export function oauthErrorMessage(error: string | undefined): string | null {
  if (!error) return null;
  if (error === "account_suspended") {
    return "Tài khoản của bạn đã bị tạm khóa. Liên hệ quản trị viên nếu cần hỗ trợ.";
  }
  if (error === "oauth_not_configured") {
    return "Đăng nhập Google chưa sẵn sàng. Vui lòng thử lại sau hoặc liên hệ quản trị.";
  }
  return "Không thể đăng nhập bằng Google. Vui lòng thử lại.";
}

export function googleLoginHref(nextPath: string): string {
  const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return `${api.replace(/\/$/, "")}/api/v1/auth/google/login?next=${encodeURIComponent(nextPath)}`;
}

export type GoogleAuthStatus = {
  google_configured: boolean;
  ok: boolean;
};

export async function getGoogleAuthStatus(): Promise<GoogleAuthStatus> {
  const base =
    process.env.API_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://127.0.0.1:8000";

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 1500);
  try {
    const resp = await fetch(`${base}/api/v1/auth/status`, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!resp.ok) return { google_configured: false, ok: false };
    const data = (await resp.json()) as { google_configured: boolean };
    return { google_configured: Boolean(data.google_configured), ok: true };
  } catch {
    return { google_configured: false, ok: false };
  } finally {
    clearTimeout(timer);
  }
}
