"use client";

import { ImportProgressRing } from "@/components/ingestion/ImportProgressBar";
import { ImportStatusBadge } from "@/components/ingestion/ImportStatusBadge";
import { safeProgressPercent, type ImportJob } from "@/lib/import-status";

const TERMINAL = new Set(["FAILED", "COMPLETED", "COMPLETED_WITH_ERRORS", "CANCELLED"]);

export function ImportDetailsPanel({
  job,
  spaceName,
}: {
  job: ImportJob;
  spaceName: string;
}) {
  const mode =
    job.import_mode === "SPACE_TREE"
      ? "Full space sync"
      : job.import_mode || job.source?.import_scope || "—";
  const terminal = TERMINAL.has(job.status || "");
  const stopping = job.status === "CANCEL_REQUESTED";
  const percent = safeProgressPercent(job.progress_percent);

  return (
    <aside className="rounded-2xl border border-border bg-surface p-4">
      <h2 className="text-sm font-semibold">Import Details</h2>
      <dl className="mt-4 space-y-3 text-sm">
        <Row label="Source type" value={job.source?.type || "Confluence"} />
        <Row label="Started by" value={job.started_by_name || "—"} />
        <Row label="Start time" value={fmt(job.started_at || job.created_at)} />
        <Row label="Last update" value={fmt(job.updated_at || job.started_at)} />
        <Row label="Import mode" value={mode} />
        <Row label="Destination" value={job.destination_name || spaceName} />
        <div className="flex items-center justify-between gap-2">
          <dt className="text-muted">Status</dt>
          <dd>
            <ImportStatusBadge status={job.status} />
          </dd>
        </div>
      </dl>

      <div className="mt-6 flex flex-col items-center gap-2 border-t border-border pt-4">
        <p className="text-xs font-medium text-muted">Overall progress</p>
        {job.status === "CANCELLED" ? (
          <p className="py-6 text-center text-sm text-muted">Stopped at {Math.round(percent)}%</p>
        ) : job.status === "FAILED" ? (
          <p className="py-6 text-center text-sm text-muted">Import failed</p>
        ) : job.status === "COMPLETED" || job.status === "COMPLETED_WITH_ERRORS" ? (
          <ImportProgressRing percent={100} />
        ) : (
          <ImportProgressRing percent={percent} />
        )}
      </div>

      {terminal ? null : (
        <p className="mt-4 rounded-xl border border-blue-100 bg-blue-50/70 px-3 py-2 text-xs text-blue-900 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-100">
          {stopping
            ? "Stopping… You can leave this page. Click Force stop if it stays stuck."
            : "You can leave this page. The import will continue in the background."}
        </p>
      )}
    </aside>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="shrink-0 text-muted">{label}</dt>
      <dd className="max-w-[60%] break-words text-right font-medium">{value}</dd>
    </div>
  );
}

function fmt(iso: string | null | undefined) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return "—";
  }
}
