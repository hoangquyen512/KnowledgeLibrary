import { BrandLogo } from "@/components/brand/BrandLogo";
import { BRAND } from "@/components/brand/tokens";
import { googleLoginHref, type LoginAuthProps } from "@/lib/auth-public";
import { GoogleSignInButton } from "./GoogleSignInButton";
import { LoginAbstractArt } from "./LoginAbstractArt";
import "./login-screen.css";

export function SimpleLoginScreen({
  googleConfigured,
  authStatusOk,
  error,
  nextPath,
}: LoginAuthProps) {
  const showUnavailable = authStatusOk && !googleConfigured && !error;
  const showStatusError = !authStatusOk;

  return (
    <main
      className="login-screen"
      data-testid="login-screen"
      data-google-configured={googleConfigured ? "true" : "false"}
      data-auth-status-ok={authStatusOk ? "true" : "false"}
    >
      <div className="login-screen-bg" aria-hidden="true">
        <LoginAbstractArt />
      </div>
      <div className="stat-card login-screen-card" aria-labelledby="login-title">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <BrandLogo variant="mark" priority showWordmark />
          <p className="eyebrow">{BRAND.tagline}</p>
        </div>

        <h1 id="login-title" className="text-center text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
          Đăng nhập vào thư viện
        </h1>
        <p className="mt-2 text-center text-sm leading-relaxed text-muted">
          Dùng tài khoản Google của công ty để truy cập workspace, space và tài liệu đã được phân quyền.
        </p>

        {error ? (
          <p
            className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200"
            role="alert"
            data-testid="login-error"
          >
            {error}
          </p>
        ) : null}

        {showStatusError ? (
          <p
            className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100"
            role="status"
            data-testid="login-status-error"
          >
            Không kết nối được máy chủ. Vui lòng thử lại sau.
          </p>
        ) : null}

        <div className="mt-6">
          <GoogleSignInButton
            href={googleLoginHref(nextPath)}
            disabled={!authStatusOk || !googleConfigured}
          />
          {showUnavailable ? (
            <p className="mt-3 text-center text-xs text-muted" data-testid="login-oauth-unavailable">
              Đăng nhập Google chưa được bật trên môi trường này.
            </p>
          ) : null}
        </div>

        <p className="mt-6 flex items-start justify-center gap-2 border-t border-border pt-4 text-center text-xs text-muted">
          <LockIcon />
          <span>Dữ liệu workspace được bảo vệ theo phân quyền và kiểm soát truy cập.</span>
        </p>
      </div>
    </main>
  );
}

function LockIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className="mt-0.5 shrink-0"
    >
      <rect x="5" y="11" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M8 11V8a4 4 0 0 1 8 0v3"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}
