"use client";

import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import { formatNumber } from "@/lib/admin-format";
import type { AdminAiPeriod, AdminAiUsage } from "@/lib/admin-types";
import { AdminPanelEmpty, AdminPanelError } from "./AdminMetricCard";

const SLICES = [
  { key: "input_tokens", label: "Input tokens", color: "#22d3ee" },
  { key: "output_tokens", label: "Output tokens", color: "#8b5cf6" },
] as const;

export function AIUsageChart({
  data,
  period,
  onPeriodChange,
  isError,
}: {
  data?: AdminAiUsage;
  period: AdminAiPeriod;
  onPeriodChange: (value: AdminAiPeriod) => void;
  isError?: boolean;
}) {
  const hasValues = Boolean(data && data.total_tokens > 0);
  const chartItems = data
    ? SLICES.map((s) => ({
        ...s,
        value: data[s.key],
        percent: data.total_tokens ? (data[s.key] / data.total_tokens) * 100 : 0,
      })).filter((s) => s.value > 0)
    : [];

  return (
    <section className="admin-panel flex min-h-[340px] flex-col p-5">
      <header className="mb-2 flex items-center justify-between gap-3">
        <h3 className="text-base font-semibold">AI Usage</h3>
        <select
          className="admin-select"
          value={period}
          onChange={(e) => onPeriodChange(e.target.value as AdminAiPeriod)}
          aria-label="AI usage period"
        >
          <option value="today">Today</option>
          <option value="this_week">This week</option>
          <option value="this_month">This month</option>
          <option value="custom">Custom date range</option>
        </select>
      </header>
      {isError ? (
        <AdminPanelError message="Could not load AI usage." />
      ) : !data ? (
        <div className="h-64 animate-pulse rounded-xl bg-surface-muted" />
      ) : !hasValues ? (
        <AdminPanelEmpty message="No AI token usage recorded for this period." />
      ) : (
        <div className="mt-2 flex flex-1 flex-col gap-4">
          <div className="relative mx-auto h-44 w-44">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={chartItems}
                  dataKey="value"
                  nameKey="label"
                  innerRadius={54}
                  outerRadius={72}
                  paddingAngle={2}
                  stroke="none"
                >
                  {chartItems.map((item) => (
                    <Cell key={item.key} fill={item.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
              <p className="text-lg font-semibold tabular-nums">{formatNumber(data.total_tokens)}</p>
              <p className="text-[11px] text-muted">Total tokens</p>
            </div>
          </div>
          <ul className="space-y-2.5">
            {SLICES.map((s) => {
              const value = data[s.key];
              const percent = data.total_tokens ? (value / data.total_tokens) * 100 : 0;
              return (
                <li key={s.key} className="flex items-center justify-between gap-2 text-sm">
                  <span className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ background: s.color }} />
                    {s.label}
                  </span>
                  <span className="tabular-nums text-muted">
                    {formatNumber(value)}
                    <span className="ml-1.5 text-foreground">{percent.toFixed(1)}%</span>
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}
