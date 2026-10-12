"use client";

import { studio } from "./strings";

const STAGE_LABELS: Record<string, string> = {
  QUEUED: studio.loadingSources,
  LOADING: studio.loadingSources,
  SUMMARIZING: studio.summarizing,
  GENERATING: studio.building,
  DONE: studio.building,
};

export function StudioProgress({ stage, percent }: { stage: string; percent: number }) {
  const label = STAGE_LABELS[stage] || studio.generating;
  return (
    <div className="space-y-3 rounded-2xl border border-border bg-surface p-5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold text-foreground">{studio.generating}</p>
        <span className="text-xs text-muted">{Math.round(percent)}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-surface-muted">
        <div
          className="h-full rounded-full bg-primary transition-all duration-500"
          style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
        />
      </div>
      <div className="flex flex-wrap gap-2 text-xs text-muted">
        <span className="rounded-full bg-blue-50 px-2.5 py-1 text-primary dark:bg-blue-950/40">{label}</span>
      </div>
    </div>
  );
}

export function StudioWarnings({ warnings }: { warnings?: Record<string, boolean> | null }) {
  if (!warnings) return null;
  const items: string[] = [];
  if (warnings.map_reduce_used) items.push(studio.warnings.mapReduce);
  if (warnings.documents_capped) items.push(studio.warnings.documentsCapped);
  if (!items.length) return null;
  return (
    <ul className="space-y-1 rounded-xl border border-amber-200 bg-amber-50/80 px-3 py-2 text-xs text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-100">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}
