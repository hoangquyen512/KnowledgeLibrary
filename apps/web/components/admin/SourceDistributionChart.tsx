"use client";

import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import { formatNumber } from "@/lib/admin-format";
import type { AdminSourceDistribution } from "@/lib/admin-types";
import { AdminPanelEmpty, AdminPanelError } from "./AdminMetricCard";

const COLORS: Record<string, string> = {
  confluence: "#3b82f6",
  jira: "#0052cc",
  google_drive: "#22c55e",
  upload: "#f59e0b",
  web: "#ef4444",
  other: "#8b5cf6",
};

export function SourceDistributionChart({
  data,
  isError,
}: {
  data?: AdminSourceDistribution;
  isError?: boolean;
}) {
  const items = data?.items ?? [];
  const hasValues = (data?.total ?? 0) > 0;

  return (
    <section className="admin-panel flex min-h-[340px] flex-col p-5">
      <header className="mb-2 flex items-center justify-between gap-3">
        <h3 className="text-base font-semibold">Sources Distribution</h3>
        <span className="admin-select pointer-events-none">All sources</span>
      </header>
      {isError ? (
        <AdminPanelError message="Could not load source distribution." />
      ) : !data ? (
        <div className="h-64 animate-pulse rounded-xl bg-surface-muted" />
      ) : !hasValues ? (
        <AdminPanelEmpty message="No sources connected yet." />
      ) : (
        <div className="mt-2 flex flex-1 flex-col gap-4 lg:flex-row lg:items-center">
          <div className="relative mx-auto h-44 w-44 shrink-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={items.filter((i) => i.count > 0)}
                  dataKey="count"
                  nameKey="label"
                  innerRadius={52}
                  outerRadius={72}
                  paddingAngle={2}
                  stroke="none"
                >
                  {items
                    .filter((i) => i.count > 0)
                    .map((item) => (
                      <Cell key={item.key} fill={COLORS[item.key] || COLORS.other} />
                    ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <p className="text-[11px] text-muted">Total</p>
              <p className="text-xl font-semibold tabular-nums">{formatNumber(data.total)}</p>
            </div>
          </div>
          <ul className="min-w-0 flex-1 space-y-2.5">
            {items.map((item) => (
              <li key={item.key} className="flex items-center justify-between gap-2 text-sm">
                <span className="flex min-w-0 items-center gap-2">
                  <span
                    className="h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ background: COLORS[item.key] || COLORS.other }}
                  />
                  <span className="truncate">{item.label}</span>
                </span>
                <span className="shrink-0 tabular-nums text-muted">
                  {formatNumber(item.count)}
                  <span className="ml-1.5 text-foreground">{item.percent.toFixed(1)}%</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
