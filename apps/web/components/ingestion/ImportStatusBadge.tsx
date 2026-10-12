"use client";

import { mapJobBadge, mapSourceBadge } from "@/lib/import-status";

export function ImportStatusBadge({
  status,
  kind = "job",
  compact = false,
}: {
  status: string | null | undefined;
  kind?: "job" | "source";
  /** Narrow sidebar: short labels (STOP, OK, RUN). */
  compact?: boolean;
}) {
  const mapped = kind === "source" ? mapSourceBadge(status) : mapJobBadge(status);
  const text = compact ? mapped.shortLabel || mapped.label : mapped.label;
  return (
    <span
      title={mapped.label}
      className={`inline-flex shrink-0 truncate rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
        compact ? "max-w-[4.5rem]" : "max-w-full"
      } ${mapped.className}`}
    >
      {text}
    </span>
  );
}
