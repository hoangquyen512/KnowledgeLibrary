"use client";

import { AlertTriangle, Check, Minus, X } from "lucide-react";
import type { AdminHealthItem, AdminSystemHealth } from "@/lib/admin-types";
import { AdminPanelError } from "./AdminMetricCard";

const STATUS_LABEL: Record<string, string> = {
  healthy: "Healthy",
  warning: "Warning",
  degraded: "Degraded",
  offline: "Offline",
  unknown: "Unverified",
};

function StatusBadge({ status }: { status: AdminHealthItem["status"] }) {
  const styles: Record<string, string> = {
    healthy: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/70 dark:text-emerald-300",
    warning: "bg-amber-50 text-amber-700 dark:bg-amber-950/70 dark:text-amber-300",
    degraded: "bg-orange-50 text-orange-700 dark:bg-orange-950/70 dark:text-orange-300",
    offline: "bg-rose-50 text-rose-700 dark:bg-rose-950/70 dark:text-rose-300",
    unknown: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
  };
  const Icon =
    status === "healthy" ? Check : status === "unknown" ? Minus : status === "offline" ? X : AlertTriangle;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${styles[status]}`}>
      <Icon size={11} />
      {STATUS_LABEL[status]}
    </span>
  );
}

export function SystemHealthPanel({
  data,
  isError,
}: {
  data?: AdminSystemHealth;
  isError?: boolean;
}) {
  return (
    <section className="admin-panel flex min-h-[340px] flex-col p-5">
      <header className="mb-3">
        <h3 className="text-base font-semibold">System Health</h3>
      </header>
      {isError ? (
        <AdminPanelError message="Could not load system health." />
      ) : !data ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-12 animate-pulse rounded-xl bg-surface-muted" />
          ))}
        </div>
      ) : (
        <ul className="divide-y divide-border">
          {data.items.map((item) => (
            <li key={item.key} className="py-3 first:pt-1">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium">{item.label}</p>
                  <p className="mt-0.5 text-xs text-muted">{item.detail}</p>
                </div>
                <StatusBadge status={item.status} />
              </div>
              {item.key === "storage" && item.used_percent != null ? (
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-muted">
                  <div
                    className="h-full rounded-full bg-emerald-500"
                    style={{ width: `${Math.min(item.used_percent, 100)}%` }}
                  />
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
