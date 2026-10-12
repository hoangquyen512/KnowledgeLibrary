"use client";

import { useState } from "react";

type GoogleSignInButtonProps = {
  href: string;
  disabled?: boolean;
};

export function GoogleSignInButton({ href, disabled = false }: GoogleSignInButtonProps) {
  const [pending, setPending] = useState(false);
  const busy = pending && !disabled;

  const content = busy ? (
    <span className="welcome-btn-label welcome-btn-label-center">
      <span className="welcome-btn-spinner" aria-hidden="true" />
      Signing you in...
    </span>
  ) : (
    <>
      <span className="welcome-btn-label">
        <GoogleGlyph />
        <span>Sign in with Google</span>
      </span>
      <ArrowRightIcon />
    </>
  );

  if (disabled) {
    return (
      <span className="welcome-btn-primary" aria-disabled="true">
        {content}
      </span>
    );
  }

  return (
    <a
      href={href}
      className="welcome-btn-primary"
      aria-busy={busy || undefined}
      aria-disabled={busy || undefined}
      onClick={(event) => {
        if (busy) {
          event.preventDefault();
          return;
        }
        setPending(true);
      }}
    >
      {content}
    </a>
  );
}

function GoogleGlyph() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#FFC107"
        d="M43.611 20.083H42V20H24v8h11.303C33.654 32.657 29.083 36 24 36c-5.627 0-10.4-3.72-11.928-8.833H9.064v6.555A20 20 0 0 0 24 44c11.046 0 20-8.954 20-20 0-1.341-.138-2.65-.389-3.917z"
      />
      <path
        fill="#FF3D00"
        d="M6.306 14.691 12.88 19.51C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657A19.958 19.958 0 0 0 24 4C16.318 4 9.656 8.337 6.306 14.691z"
      />
      <path
        fill="#4CAF50"
        d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238A11.91 11.91 0 0 1 24 36c-5.048 0-9.376-3.322-10.855-7.887l-6.52 5.025A19.958 19.958 0 0 0 24 44z"
      />
      <path
        fill="#1976D2"
        d="M43.611 20.083H42V20H24v8h11.303a12.04 12.04 0 0 1-4.087 5.571l.003-.002 6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z"
      />
    </svg>
  );
}

function ArrowRightIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M5 12h14M13 6l6 6-6 6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
