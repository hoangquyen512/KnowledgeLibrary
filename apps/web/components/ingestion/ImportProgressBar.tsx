"use client";

import { safeProgressPercent } from "@/lib/import-status";

export function ImportProgressBar({ percent }: { percent: number | null | undefined }) {
  const value = Math.round(safeProgressPercent(percent));
  return (
    <div className="flex items-center gap-4">
      <div
        className="h-3 flex-1 overflow-hidden rounded-full bg-surface-muted"
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Import progress"
      >
        <div
          className="h-full rounded-full bg-primary transition-[width] duration-300"
          style={{ width: `${value}%` }}
        />
      </div>
      <span className="min-w-[3rem] text-right text-2xl font-semibold text-primary">{value}%</span>
    </div>
  );
}

export function ImportProgressRing({ percent }: { percent: number | null | undefined }) {
  const value = Math.round(safeProgressPercent(percent));
  const r = 28;
  const c = 2 * Math.PI * r;
  const offset = c - (value / 100) * c;
  return (
    <div className="relative grid h-20 w-20 place-items-center">
      <svg className="h-20 w-20 -rotate-90" viewBox="0 0 72 72" aria-hidden>
        <circle cx="36" cy="36" r={r} fill="none" stroke="var(--border)" strokeWidth="6" />
        <circle
          cx="36"
          cy="36"
          r={r}
          fill="none"
          stroke="var(--primary)"
          strokeWidth="6"
          strokeDasharray={c}
          strokeDashoffset={offset}
          strokeLinecap="round"
        />
      </svg>
      <span className="absolute text-sm font-semibold text-primary">{value}%</span>
    </div>
  );
}
