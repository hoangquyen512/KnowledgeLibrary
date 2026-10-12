"use client";

import { LayoutTemplate, Trash2 } from "lucide-react";
import { useAppRouter } from "@/components/navigation-progress";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { CancelImportDialog } from "@/components/ingestion/CancelImportDialog";
import { CurrentImportItems } from "@/components/ingestion/CurrentImportItems";
import { ImportProgressBar } from "@/components/ingestion/ImportProgressBar";
import { ImportStageList } from "@/components/ingestion/ImportStageList";
import {
  formatDuration,
  formatEta,
  importTitle,
  mapErrorMessage,
  safeProgressPercent,
  type ImportJob,
} from "@/lib/import-status";
import { clientApi } from "@/lib/api";
import { toast } from "sonner";

export function ImportProgressPanel({
  job,
  workspaceId,
  canManage,
  onViewDocuments,
  onRetry,
}: {
  job: ImportJob;
  workspaceId: string;
  canManage: boolean;
  onViewDocuments: () => void;
  onRetry?: () => void;
}) {
  const router = useAppRouter();
  const client = useQueryClient();
  const [cancelOpen, setCancelOpen] = useState(false);
  const [canceling, setCanceling] = useState(false);
  const copy = importTitle(job.source?.type, job.job_type);
  const stats = job.stats;
  const percent = safeProgressPercent(job.progress_percent);
  const stopping = job.status === "CANCEL_REQUESTED" || !!job.cancel_requested;
  const active =
    job.status === "QUEUED" || job.status === "RUNNING" || job.status === "CANCEL_REQUESTED";

  if (job.status === "COMPLETED") {
    return (
      <CompletedCard
        job={job}
        onViewDocuments={onViewDocuments}
        onSyncAgain={onRetry}
      />
    );
  }
  if (job.status === "COMPLETED_WITH_ERRORS") {
    return <PartialCard job={job} onViewDocuments={onViewDocuments} onRetry={onRetry} />;
  }
  if (job.status === "FAILED") {
    return (
      <FailedCard
        job={job}
        workspaceId={workspaceId}
        onRetry={onRetry}
      />
    );
  }
  if (job.status === "CANCELLED") {
    return (
      <section className="rounded-2xl border border-border bg-surface p-5">
        <h2 className="text-lg font-semibold">Import canceled</h2>
        <p className="mt-2 text-sm text-muted">The import was stopped. Imported content remains.</p>
        <button type="button" className="primary-button mt-4" onClick={onViewDocuments}>
          View documents
        </button>
      </section>
    );
  }

  if (job.status === "QUEUED" || !job.status || (job.stage === "QUEUED" && percent < 1)) {
    return (
      <section className="rounded-2xl border border-border bg-surface p-5">
        <h2 className="text-lg font-semibold">Preparing import</h2>
        <p className="mt-1 text-sm text-muted">
          Reading Confluence structure and estimating content…
        </p>
        <div className="mt-6">
          <ImportProgressBar percent={Math.max(percent, 2)} />
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-border bg-surface p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">Import Progress</p>
      <h2 className="mt-1 text-xl font-semibold">
        {stopping ? "Stopping import…" : copy.title}
      </h2>
      <p className="mt-1 text-sm text-muted">
        {stopping
          ? "Cancel requested. Waiting for the current download to finish, then the job will stop. Click Cancel again to force-stop."
          : copy.subtitle}
      </p>

      <div className="mt-6">
        <ImportProgressBar percent={percent} />
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Stat label="Overall progress" value={`${Math.round(percent)}%`} accent />
        {stats && (stats.total_pages > 0 || stats.processed_pages > 0) ? (
          <Stat
            label="Pages imported"
            value={`${stats.processed_pages} / ${stats.total_pages || "—"}`}
          />
        ) : null}
        {stats && stats.total_attachments > 0 ? (
          <Stat
            label="Attachments imported"
            value={`${stats.processed_attachments} / ${stats.total_attachments}`}
          />
        ) : null}
        {stats && stats.total_diagrams > 0 ? (
          <Stat
            label="Diagrams imported"
            value={`${stats.processed_diagrams} / ${stats.total_diagrams}`}
          />
        ) : null}
        {active && !stopping ? (
          <Stat label="Est. time remaining" value={formatEta(job.eta_seconds)} />
        ) : null}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div>
          <h3 className="mb-3 text-sm font-semibold">Import stages</h3>
          <ImportStageList stages={job.stages || []} />
        </div>
        <div>
          <h3 className="mb-3 text-sm font-semibold">Currently importing</h3>
          <CurrentImportItems items={job.current_items || []} />
        </div>
      </div>

      <div className="mt-6 flex flex-wrap gap-2 border-t border-border pt-4">
        <button
          type="button"
          className="primary-button"
          onClick={() => router.push(`/app/workspaces/${workspaceId}`)}
        >
          <LayoutTemplate size={16} />
          Run in background
        </button>
        {canManage ? (
          <button
            type="button"
            className="secondary-button"
            disabled={canceling}
            onClick={() => setCancelOpen(true)}
          >
            <Trash2 size={16} />
            {stopping ? "Force stop" : "Cancel import"}
          </button>
        ) : null}
      </div>

      <CancelImportDialog
        open={cancelOpen}
        pending={canceling}
        force={stopping}
        onKeep={() => setCancelOpen(false)}
        onConfirm={async () => {
          setCanceling(true);
          try {
            const updated = await clientApi<ImportJob>(`/jobs/${job.id}/cancel`, {
              method: "POST",
            });
            client.setQueryData(["import-job", job.id], updated);
            client.invalidateQueries({ queryKey: ["sources", job.space_id] });
            client.invalidateQueries({ queryKey: ["space", job.space_id] });
            toast.success("Import canceled.");
            setCancelOpen(false);
          } catch (e) {
            toast.error((e as Error).message);
          } finally {
            setCanceling(false);
          }
        }}
      />
    </section>
  );
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface-muted/40 px-3 py-2">
      <p className="text-[11px] text-muted">{label}</p>
      <p className={`mt-1 text-sm font-semibold ${accent ? "text-primary" : ""}`}>{value}</p>
    </div>
  );
}

function CompletedCard({
  job,
  onViewDocuments,
  onSyncAgain,
}: {
  job: ImportJob;
  onViewDocuments: () => void;
  onSyncAgain?: () => void;
}) {
  const s = job.stats;
  return (
    <section className="rounded-2xl border border-border bg-surface p-5">
      <h2 className="text-xl font-semibold text-emerald-700 dark:text-emerald-300">
        Import completed
      </h2>
      <p className="mt-3 text-sm text-muted">
        {s?.total_pages ?? 0} pages
        {s && s.total_attachments > 0 ? ` · ${s.total_attachments} attachments` : ""}
        {s && s.total_diagrams > 0 ? ` · ${s.total_diagrams} diagrams` : ""}
      </p>
      <p className="mt-1 text-sm text-muted">
        Completed in {formatDuration(job.started_at, job.completed_at)}
      </p>
      <div className="mt-4">
        <ImportProgressBar percent={100} />
      </div>
      <div className="mt-5 flex flex-wrap gap-2">
        <button type="button" className="primary-button" onClick={onViewDocuments}>
          View documents
        </button>
        {onSyncAgain ? (
          <button type="button" className="secondary-button" onClick={onSyncAgain}>
            Sync again
          </button>
        ) : null}
      </div>
    </section>
  );
}

function PartialCard({
  job,
  onViewDocuments,
  onRetry,
}: {
  job: ImportJob;
  onViewDocuments: () => void;
  onRetry?: () => void;
}) {
  const s = job.stats;
  const pagesDone = s?.processed_pages ?? 0;
  const pagesTotal = s?.total_pages ?? 0;
  const failed = s?.failed_items ?? 0;
  const hasPageCounts = pagesTotal > 0 || pagesDone > 0;
  return (
    <section className="rounded-2xl border border-amber-200 bg-amber-50/40 p-5 dark:border-amber-900 dark:bg-amber-950/20">
      <h2 className="text-xl font-semibold text-amber-800 dark:text-amber-200">
        Import completed with some issues
      </h2>
      <p className="mt-3 text-sm">
        {hasPageCounts
          ? `${pagesDone} of ${pagesTotal || pagesDone} pages imported`
          : "Pages were imported, but some attachments could not be saved."}
        {s && s.total_attachments > 0
          ? ` · ${s.processed_attachments} of ${s.total_attachments} attachments`
          : ""}
      </p>
      <p className="mt-1 text-sm text-muted">
        {failed > 0 ? `${failed} items failed` : "Some items had recoverable issues during store."}
      </p>
      <div className="mt-5 flex flex-wrap gap-2">
        <button type="button" className="primary-button" onClick={onViewDocuments}>
          View documents
        </button>
        {onRetry && failed > 0 ? (
          <button type="button" className="secondary-button" onClick={onRetry}>
            Retry failed
          </button>
        ) : null}
      </div>
    </section>
  );
}

function FailedCard({
  job,
  workspaceId,
  onRetry,
}: {
  job: ImportJob;
  workspaceId: string;
  onRetry?: () => void;
}) {
  const router = useAppRouter();
  return (
    <section className="rounded-2xl border border-rose-200 bg-rose-50/40 p-5 dark:border-rose-900 dark:bg-rose-950/20">
      <h2 className="text-xl font-semibold text-rose-800 dark:text-rose-200">Import failed</h2>
      <p className="mt-2 text-sm text-muted">
        We couldn&apos;t complete the{" "}
        {job.source?.type === "FILE_UPLOAD" ? "file" : "Confluence"} import.
      </p>
      <p className="mt-3 text-sm">
        <span className="font-medium">Reason:</span>{" "}
        {mapErrorMessage(job.error_code, job.error_message || job.message)}
      </p>
      <div className="mt-5 flex flex-wrap gap-2">
        {onRetry ? (
          <button type="button" className="primary-button" onClick={onRetry}>
            Retry
          </button>
        ) : null}
        <button
          type="button"
          className="secondary-button"
          onClick={() => router.push(`/app/workspaces/${workspaceId}/settings`)}
        >
          Update connection
        </button>
      </div>
    </section>
  );
}
