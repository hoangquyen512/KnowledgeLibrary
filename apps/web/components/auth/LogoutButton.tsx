"use client";

import { useAppRouter } from "@/components/navigation-progress";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { publicApiBase } from "@/lib/api";

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export function LogoutButton({
  variant = "menu",
  className = "",
  label,
}: {
  variant?: "menu" | "danger";
  className?: string;
  label?: string;
}) {
  const router = useAppRouter();
  const queryClient = useQueryClient();
  const [loading, setLoading] = useState(false);

  async function onLogout() {
    setLoading(true);
    try {
      const csrf = getCookie("kl_csrf");
      await fetch(`${publicApiBase()}/api/v1/auth/logout`, {
        method: "POST",
        credentials: "include",
        headers: csrf ? { "X-CSRF-Token": csrf } : {},
      });
      queryClient.clear();
      router.push("/login");
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  const text = loading ? "Signing out…" : label || "Sign out";

  if (variant === "danger") {
    return (
      <button
        type="button"
        onClick={onLogout}
        disabled={loading}
        className={`inline-flex items-center justify-center gap-2 rounded-lg border border-rose-300 bg-surface px-3.5 py-2.5 text-sm font-semibold text-rose-600 transition hover:bg-rose-50 disabled:opacity-60 dark:border-rose-800 dark:hover:bg-rose-950/40 ${className}`}
      >
        <LogOut size={16} />
        {text}
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={onLogout}
      disabled={loading}
      className={`menu-link w-full text-left disabled:opacity-60 ${className}`}
    >
      {text}
    </button>
  );
}
