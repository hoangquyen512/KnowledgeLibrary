"use client";

import type { LucideIcon } from "lucide-react";
import { TrendingDown, TrendingUp } from "lucide-react";
import { formatNumber } from "@/lib/admin-format";
import type { AdminKpi } from "@/lib/admin-types";

const TONES = {
  blue: {
    tile: "bg-blue-100 text-blue-600 dark:bg-blue-950/80 dark:text-blue-300",
    line: "#3b82f6",
  },
  green: {
    tile: "bg-emerald-100 text-emerald-600 dark:bg-emerald-950/80 dark:text-emerald-300",
    line: "#10b981",
  },
  violet: {
    tile: "bg-violet-100 text-violet-600 dark:bg-violet-950/80 dark:text-violet-300",
    line: "#8b5cf6",
  },
  amber: {
    tile: "bg-amber-100 text-amber-600 dark:bg-amber-950/80 dark:text-amber-300",
    line: "#f59e0b",
  },
  cyan: {
    tile: "bg-cyan-100 text-cyan-600 dark:bg-cyan-950/80 dark:text-cyan-300",
    line: "#06b6d4",
  },
} as const;

export function AdminMetricCard({
  kpi,
  icon: Icon,
  tone,
  comparisonLabel,
}: {
  kpi: AdminKpi;
  icon: LucideIcon;
  tone: keyof typeof TONES;
  comparisonLabel: string;
}) {
  const colors = TONES[tone];
  const up = (kpi.change_percent ?? 0) >= 0;

  return (
    <article className="admin-panel flex min-h-[148px] flex-col p-4">
      <div className="flex items-start justify-between gap-3">
        <span className={`grid h-10 w-10 place-items-center rounded-full ${colors.tile}`}>
          <Icon size={18} />
        </span>
      </div>
      <p className="mt-3 text-sm text-muted">{kpi.label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight tabular-nums">
        {formatNumber(kpi.value)}
      </p>
      <div className="mt-2 flex items-end justify-between gap-2">
        {kpi.has_comparison && kpi.change_percent != null ? (
          <p className={`flex items-center gap-1 text-xs font-medium ${up ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}`}>
            {up ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
            {up ? "+" : ""}
            {kpi.change_percent}%
            <span className="font-normal text-muted">vs {comparisonLabel}</span>
          </p>
        ) : (
          <p className="text-xs text-muted">No comparison data</p>
        )}
        <MiniSparkline points={kpi.sparkline.map((p) => p.value)} color={colors.line} />
      </div>
    </article>
  );
}

function MiniSparkline({ points, color }: { points: number[]; color: string }) {
  if (!points.length) return null;
  const w = 88;
  const h = 28;
  const max = Math.max(...points, 1);
  const path = points
    .map((value, i) => {
      const x = (i / Math.max(points.length - 1, 1)) * w;
      const y = h - 2 - (value / max) * (h - 6);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden className="shrink-0">
      <path d={path} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function AdminMetricCardSkeleton() {
  return (
    <div className="admin-panel min-h-[148px] animate-pulse p-4">
      <div className="h-10 w-10 rounded-full bg-surface-muted" />
      <div className="mt-4 h-3 w-20 rounded bg-surface-muted" />
      <div className="mt-3 h-7 w-16 rounded bg-surface-muted" />
    </div>
  );
}

export function AdminPanelError({ message }: { message: string }) {
  return (
    <div className="flex min-h-24 items-center justify-center px-4 text-center text-sm text-rose-600 dark:text-rose-400">
      {message}
    </div>
  );
}

export function AdminPanelEmpty({ message }: { message: string }) {
  return (
    <div className="flex min-h-24 items-center justify-center px-4 text-center text-sm text-muted">
      {message}
    </div>
  );
}
