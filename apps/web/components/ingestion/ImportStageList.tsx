"use client";

import { AlertTriangle, Check, Circle, Loader2, Minus } from "lucide-react";

export function ImportStageList({
  stages,
}: {
  stages: { key: string; label: string; status: string }[];
}) {
  if (!stages.length) {
    return <p className="text-sm text-muted">Stages will appear once the job starts.</p>;
  }
  return (
    <ul className="space-y-3">
      {stages.map((s) => (
        <li key={s.key} className="flex items-start gap-2.5 text-sm">
          <StageIcon status={s.status} />
          <div className="min-w-0 flex-1">
            <p className="font-medium text-foreground">{s.label}</p>
            <p className="text-xs text-muted">{labelFor(s.status)}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function labelFor(status: string) {
  switch (status) {
    case "completed":
      return "Completed";
    case "in_progress":
      return "In progress";
    case "failed":
      return "Failed";
    case "skipped":
      return "Skipped";
    default:
      return "Pending";
  }
}

function StageIcon({ status }: { status: string }) {
  if (status === "completed") {
    return (
      <span className="mt-0.5 grid h-5 w-5 place-items-center rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
        <Check size={12} aria-hidden />
      </span>
    );
  }
  if (status === "in_progress") {
    return (
      <span className="mt-0.5 grid h-5 w-5 place-items-center text-primary" aria-label="In progress">
        <Loader2 size={16} className="animate-spin" />
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="mt-0.5 grid h-5 w-5 place-items-center text-rose-600">
        <AlertTriangle size={14} />
      </span>
    );
  }
  if (status === "skipped") {
    return (
      <span className="mt-0.5 grid h-5 w-5 place-items-center text-muted">
        <Minus size={14} />
      </span>
    );
  }
  return (
    <span className="mt-0.5 grid h-5 w-5 place-items-center text-muted">
      <Circle size={14} />
    </span>
  );
}
