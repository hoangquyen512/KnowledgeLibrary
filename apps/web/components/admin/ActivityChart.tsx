"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatCompactDate } from "@/lib/admin-format";
import type { AdminActivitySeries, AdminGranularity } from "@/lib/admin-types";
import { AdminPanelEmpty, AdminPanelError } from "./AdminMetricCard";

const SERIES = [
  { key: "documents", name: "Documents", color: "#f59e0b" },
  { key: "ai_queries", name: "AI Queries", color: "#22d3ee" },
  { key: "users", name: "Users", color: "#3b82f6" },
] as const;

export function ActivityChart({
  data,
  granularity,
  onGranularityChange,
  isError,
}: {
  data?: AdminActivitySeries;
  granularity: AdminGranularity;
  onGranularityChange: (value: AdminGranularity) => void;
  isError?: boolean;
}) {
  const points = data?.points ?? [];
  const hasValues = points.some((p) => p.documents || p.ai_queries || p.users);
  const chartData = useMemo(
    () =>
      points.map((p) => ({
        ...p,
        label: p.date.includes("W") || p.date.length <= 7 ? p.date : formatCompactDate(p.date),
      })),
    [points],
  );

  return (
    <section className="admin-panel flex min-h-[340px] flex-col p-5">
      <header className="mb-4 flex items-center justify-between gap-3">
        <h3 className="text-base font-semibold">Activity Over Time</h3>
        <select
          className="admin-select"
          value={granularity}
          onChange={(e) => onGranularityChange(e.target.value as AdminGranularity)}
          aria-label="Activity granularity"
        >
          <option value="daily">Daily</option>
          <option value="weekly">Weekly</option>
          <option value="monthly">Monthly</option>
        </select>
      </header>
      {isError ? (
        <AdminPanelError message="Could not load activity series." />
      ) : !data ? (
        <div className="h-64 animate-pulse rounded-xl bg-surface-muted" />
      ) : !hasValues ? (
        <AdminPanelEmpty message="No activity in this date range." />
      ) : (
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 6" vertical={false} stroke="var(--border)" />
              <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 12 }} />
              <YAxis tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 12 }} width={36} />
              <Tooltip
                contentStyle={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: 12,
                  color: "var(--foreground)",
                }}
              />
              <Legend iconType="circle" wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
              {SERIES.map((s) => (
                <Line
                  key={s.key}
                  type="monotone"
                  dataKey={s.key}
                  name={s.name}
                  stroke={s.color}
                  strokeWidth={2.4}
                  dot={{ r: 3.5, strokeWidth: 0 }}
                  activeDot={{ r: 5 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}
