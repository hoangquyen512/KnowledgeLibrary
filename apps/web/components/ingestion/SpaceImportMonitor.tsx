"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Pencil, RefreshCw, Replace, Trash2 } from "lucide-react";
import { useAppRouter } from "@/components/navigation-progress";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ConnectionFormDialog } from "@/components/confluence/ConnectionFormDialog";
import type { ConfluenceConnection } from "@/lib/confluence";
import { DeleteSourceDialog } from "@/components/ingestion/DeleteSourceDialog";
import { DocumentPanel } from "@/components/ingestion/DocumentPanel";
import {
  ExportMdDialog,
  type ExportGroupDepth,
} from "@/components/ingestion/ExportMdDialog";
import { ImportProgressPanel } from "@/components/ingestion/ImportProgressPanel";
import { ImportStatusBadge } from "@/components/ingestion/ImportStatusBadge";
import { UploadFilesDialog } from "@/components/sources/UploadFilesDialog";
import { clientApi, publicApiBase } from "@/lib/api";
import {
  isJobActive,
  isSourceImporting,
  mapErrorMessage,
  type ImportJob,
  type SourceRow,
} from "@/lib/import-status";
import {
  documentUnit,
  isFileSourceType,
  isSyncable,
  sourceTypeIcon,
  sourceTypeLabel,
  type FileSourceTypeHint,
} from "@/lib/sources";

async function downloadSourceMarkdownZip(source: SourceRow, groupDepth: number) {
  const qs = new URLSearchParams({ group_depth: String(groupDepth) });
  const resp = await fetch(`/api/v1/sources/${source.id}/export.md.zip?${qs}`, {
    credentials: "include",
  });
  if (!resp.ok) {
    let message = "Download failed.";
    try {
      const body = (await resp.json()) as { detail?: { message?: string } | string };
      if (typeof body.detail === "string") message = body.detail;
      else if (body.detail && typeof body.detail === "object" && body.detail.message) {
        message = body.detail.message;
      }
    } catch {
      /* ignore */
    }
    throw new Error(message);
  }
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const disposition = resp.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename\*=UTF-8''([^;]+)|filename="([^"]+)"/i);
  const encoded = match?.[1];
  const plain = match?.[2];
  a.download = encoded
    ? decodeURIComponent(encoded)
    : plain || `${source.name || "source"}-export.zip`;
  a.click();
  URL.revokeObjectURL(url);
}

function relativeSync(iso: string | null | undefined) {
  if (!iso) return "Never synced";
  const ms = Date.now() - new Date(iso).getTime();
  const m = Math.round(ms / 60000);
  if (m < 1) return "Synced just now";
  if (m < 60) return `Synced ${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 48) return `Synced ${h}h ago`;
  return `Synced ${Math.round(h / 24)}d ago`;
}

function relativeUploaded(iso: string | null | undefined) {
  if (!iso) return null;
  const ms = Date.now() - new Date(iso).getTime();
  const m = Math.round(ms / 60000);
  if (m < 1) return "Uploaded just now";
  if (m < 60) return `Uploaded ${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 48) return `Uploaded ${h}h ago`;
  return `Uploaded ${Math.round(h / 24)}d ago`;
}

function sourceMetaLine(s: SourceRow): string {
  const label = sourceTypeLabel(s.type);
  const count = s.document_count ?? 0;
  const unit = documentUnit(s.type, count);
  const scope =
    s.type === "CONFLUENCE" && s.import_scope === "SPACE_TREE"
      ? " · Full tree"
      : s.type === "JIRA" && s.import_scope === "PROJECT_ISSUES"
        ? " · Project issues"
        : "";
  return `${label}${scope} · ${count} ${unit}`;
}

export function SpaceImportMonitor({
  workspaceId,
  spaceId,
  spaceName: _spaceName,
  canManage,
  onAddSource: _onAddSource,
}: {
  workspaceId: string;
  spaceId: string;
  spaceName: string;
  canManage: boolean;
  onAddSource: () => void;
}) {
  const router = useAppRouter();
  const client = useQueryClient();
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [forceDocuments, setForceDocuments] = useState(false);
  const [deleteSourceId, setDeleteSourceId] = useState<string | null>(null);
  const [editConnection, setEditConnection] = useState<ConfluenceConnection | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [exportSource, setExportSource] = useState<SourceRow | null>(null);
  const [syncInterval, setSyncInterval] = useState("OFF");
  const [syncLabel, setSyncLabel] = useState<string | null>(null);
  const [replaceOpen, setReplaceOpen] = useState(false);
  const [replaceHint, setReplaceHint] = useState<FileSourceTypeHint | undefined>();
  const [replaceSourceId, setReplaceSourceId] = useState<string | null>(null);

  const { data: sources = [] } = useQuery({
    queryKey: ["sources", spaceId],
    queryFn: () => clientApi<SourceRow[]>(`/spaces/${spaceId}/sources`),
    refetchInterval: 8_000,
  });

  const { data: connections = [] } = useQuery({
    queryKey: ["confluence-connections", workspaceId],
    queryFn: () =>
      clientApi<ConfluenceConnection[]>(`/workspaces/${workspaceId}/confluence-connections`),
    enabled: canManage,
  });

  const selected =
    sources.find((s) => s.id === selectedSourceId) ||
    sources.find((s) => isSourceImporting(s.status)) ||
    sources[0] ||
    null;

  useEffect(() => {
    if (selected && !selectedSourceId) {
      setSelectedSourceId(selected.id);
      if (
        selected.status === "READY" ||
        selected.status === "SYNCED" ||
        selected.status === "INDEXED"
      ) {
        setForceDocuments(true);
      }
    }
  }, [selected, selectedSourceId]);

  useEffect(() => {
    setSyncInterval(selected?.sync_interval || "OFF");
  }, [selected?.id, selected?.sync_interval]);

  useEffect(() => {
    if (!selected) {
      setSyncLabel(null);
      return;
    }
    if (isFileSourceType(selected.type)) {
      setSyncLabel(relativeUploaded(selected.last_sync_at));
      return;
    }
    if (selected.status !== "READY" && selected.status !== "SYNCED" && selected.status !== "INDEXED") {
      setSyncLabel(null);
      return;
    }
    setSyncLabel(relativeSync(selected.last_sync_at));
  }, [selected?.id, selected?.status, selected?.last_sync_at, selected?.type]);

  const jobId = selected?.latest_job_id || null;

  const { data: job } = useQuery({
    queryKey: ["import-job", jobId],
    queryFn: () => clientApi<ImportJob>(`/jobs/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      if (!s || isJobActive(s)) return 5_000;
      return false;
    },
  });

  useEffect(() => {
    if (!jobId || !job || !isJobActive(job.status)) return;
    const url = `${publicApiBase()}/api/v1/jobs/${jobId}/events`;
    const es = new EventSource(url);
    const onProgress = (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data) as ImportJob;
        client.setQueryData(["import-job", jobId], data);
        if (!isJobActive(data.status)) {
          client.invalidateQueries({ queryKey: ["sources", spaceId] });
          client.invalidateQueries({ queryKey: ["space", spaceId] });
          client.invalidateQueries({ queryKey: ["documents", spaceId] });
          setForceDocuments(true);
        }
      } catch {
        /* ignore */
      }
    };
    es.addEventListener("job_progress", onProgress);
    es.addEventListener("job_completed", onProgress);
    es.onerror = () => es.close();
    return () => es.close();
  }, [jobId, job?.status, client, spaceId]);

  const startImport = useMutation({
    mutationFn: (sourceId: string) =>
      clientApi<ImportJob>(`/sources/${sourceId}/import`, { method: "POST" }),
    onSuccess: (j) => {
      client.setQueryData(["import-job", j.id], j);
      client.invalidateQueries({ queryKey: ["sources", spaceId] });
      setSelectedSourceId(j.source_id);
      setForceDocuments(false);
      toast.success("Import started.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const syncNow = useMutation({
    mutationFn: (sourceId: string) =>
      clientApi<ImportJob>(`/sources/${sourceId}/sync`, { method: "POST" }),
    onSuccess: (j) => {
      client.setQueryData(["import-job", j.id], j);
      client.invalidateQueries({ queryKey: ["sources", spaceId] });
      setSelectedSourceId(j.source_id);
      setForceDocuments(false);
      toast.success("Sync started.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const saveSyncSettings = useMutation({
    mutationFn: ({ sourceId, interval }: { sourceId: string; interval: string }) =>
      clientApi<SourceRow>(`/sources/${sourceId}/sync-settings`, {
        method: "PATCH",
        body: JSON.stringify({
          sync_enabled: interval !== "OFF",
          sync_interval: interval,
        }),
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["sources", spaceId] });
      toast.success("Sync schedule saved");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteSource = useMutation({
    mutationFn: (sourceId: string) =>
      clientApi<void>(`/sources/${sourceId}`, { method: "DELETE" }),
    onSuccess: (_data, sourceId) => {
      client.invalidateQueries({ queryKey: ["sources", spaceId] });
      client.invalidateQueries({ queryKey: ["space", spaceId] });
      client.invalidateQueries({ queryKey: ["documents", spaceId] });
      client.invalidateQueries({ queryKey: ["page-tree", spaceId] });
      client.invalidateQueries({ queryKey: ["page-archived", spaceId] });
      if (selectedSourceId === sourceId) {
        setSelectedSourceId(null);
      }
      setDeleteSourceId(null);
      toast.success("Source and its pages deleted.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteTarget = sources.find((s) => s.id === deleteSourceId) || null;

  const showMonitor =
    !!selected &&
    !forceDocuments &&
    (isSourceImporting(selected.status) || (!!job && isJobActive(job.status)));

  const readyEmpty =
    !!selected &&
    (selected.status === "READY_TO_IMPORT" || selected.status === "UPLOADED") &&
    (!job || (!isJobActive(job.status) && job.status !== "COMPLETED"));

  const selectedImporting = selected ? isSourceImporting(selected.status) : false;
  const canDownloadSelected =
    !!selected &&
    (selected.status === "READY" ||
      selected.status === "SYNCED" ||
      selected.status === "INDEXED" ||
      (selected.document_count ?? 0) > 0) &&
    !selectedImporting;
  const selectedSyncable = !!selected && isSyncable(selected.type);
  const selectedIsFile = !!selected && isFileSourceType(selected.type);
  const canSyncSelected =
    canManage &&
    !!selected &&
    selectedSyncable &&
    (selected.status === "READY" || selected.status === "SYNCED" || selected.status === "INDEXED") &&
    !selectedImporting;
  const canEditConnection =
    canManage && !!selected && selected.type === "CONFLUENCE" && !!selected.connection_id;

  const handleDownload = async (source: SourceRow, groupDepth: ExportGroupDepth) => {
    if (downloadingId) return;
    setDownloadingId(source.id);
    try {
      await downloadSourceMarkdownZip(source, groupDepth);
      const label =
        groupDepth <= 0 ? "one file per page" : `grouped by tree level ${groupDepth}`;
      toast.success(`Markdown zip downloaded (${label}).`);
      setExportSource(null);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Download failed.");
    } finally {
      setDownloadingId(null);
    }
  };

  const openEditConnection = (source: SourceRow) => {
    if (source.type !== "CONFLUENCE") {
      toast.error("Edit connection is available for Confluence sources.");
      return;
    }
    const conn = connections.find((c) => c.id === source.connection_id);
    if (conn) {
      setEditConnection(conn);
      return;
    }
    toast.error("Connection not found. Use Edit connection on this source.");
  };

  const openReplace = (source: SourceRow) => {
    const hint =
      source.type === "FILE_EXCEL" ||
      source.type === "FILE_CSV" ||
      source.type === "FILE_WORD" ||
      source.type === "FILE_POWERPOINT" ||
      source.type === "FILE_PDF"
        ? (source.type as FileSourceTypeHint)
        : undefined;
    setReplaceHint(hint);
    setReplaceSourceId(source.id);
    setReplaceOpen(true);
  };

  return (
    <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(220px,260px)_minmax(0,1fr)]">
      <aside className="rounded-2xl border border-border bg-surface p-4">
        <h2 className="text-sm font-semibold">Sources</h2>
        {sources.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No sources connected.</p>
        ) : (
          <ul className="mt-3 space-y-1.5">
            {sources.map((s) => {
              const active = selected?.id === s.id;
              const importing = isSourceImporting(s.status);
              const jobForSource = job?.source_id === s.id ? job : null;
              const TypeIcon = sourceTypeIcon(s.type);
              const badge =
                jobForSource?.status === "CANCEL_REQUESTED"
                  ? { status: "CANCEL_REQUESTED", kind: "job" as const }
                  : jobForSource?.status === "RUNNING" ||
                      jobForSource?.status === "QUEUED" ||
                      importing
                    ? { status: "IMPORTING", kind: "source" as const }
                    : jobForSource?.status === "CANCELLED"
                      ? {
                          status:
                            s.status === "READY" || s.status === "SYNCED" || s.status === "INDEXED"
                              ? "READY"
                              : "READY_TO_IMPORT",
                          kind: "source" as const,
                        }
                      : {
                          status:
                            s.status === "READY" || s.status === "SYNCED" || s.status === "INDEXED"
                              ? "READY"
                              : s.status,
                          kind: "source" as const,
                        };
              return (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedSourceId(s.id);
                      setForceDocuments(true);
                    }}
                    className={`w-full rounded-xl border px-3 py-2.5 text-left text-sm transition ${
                      active
                        ? "border-primary bg-blue-50/70 dark:bg-blue-950/30"
                        : "border-transparent bg-surface-muted/60 hover:bg-surface-muted"
                    }`}
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <TypeIcon size={14} className="shrink-0 text-muted" aria-hidden />
                      <p className="min-w-0 flex-1 truncate font-medium leading-snug">{s.name}</p>
                      <ImportStatusBadge status={badge.status} kind={badge.kind} compact />
                    </div>
                    <p className="mt-1 text-[11px] text-muted">{sourceMetaLine(s)}</p>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </aside>

      <div className="min-w-0 space-y-3">
        {selected ? (
          <section className="rounded-2xl border border-border bg-surface p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <h2 className="truncate text-base font-semibold">{selected.name}</h2>
                <p className="mt-0.5 text-xs text-muted">
                  {sourceTypeLabel(selected.type)}
                  {selected.type === "CONFLUENCE" && selected.import_scope === "SPACE_TREE"
                    ? " · Full space sync"
                    : selected.type === "JIRA"
                      ? " · Project issues"
                      : ""}
                  {syncLabel ? ` · ${syncLabel}` : ""}
                </p>
                {selected.last_sync_status === "FAILED" && selected.last_sync_error ? (
                  <p className="mt-1 text-xs text-rose-600">
                    {mapErrorMessage(undefined, selected.last_sync_error)}
                  </p>
                ) : null}
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                {canEditConnection ? (
                  <button
                    type="button"
                    className="secondary-button h-8 px-2.5 text-xs"
                    onClick={() => openEditConnection(selected)}
                  >
                    <Pencil size={14} />
                    Edit connection
                  </button>
                ) : null}
                {canManage && selectedSyncable && (selected.status === "READY" || selected.status === "SYNCED") ? (
                  <label className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-border bg-surface px-2 text-xs text-muted">
                    <span className="whitespace-nowrap">Auto-sync</span>
                    <select
                      className="max-w-[6.5rem] border-0 bg-transparent py-0 text-xs font-medium text-foreground outline-none"
                      value={syncInterval}
                      disabled={saveSyncSettings.isPending || selectedImporting}
                      onChange={(e) => {
                        const next = e.target.value;
                        setSyncInterval(next);
                        saveSyncSettings.mutate({ sourceId: selected.id, interval: next });
                      }}
                    >
                      <option value="OFF">Off</option>
                      <option value="HOURLY">Hourly</option>
                      <option value="DAILY">Daily</option>
                    </select>
                  </label>
                ) : null}
                {canManage && selectedSyncable && (selected.status === "READY" || selected.status === "SYNCED" || selected.status === "INDEXED") ? (
                  <button
                    type="button"
                    className="secondary-button h-8 px-2.5 text-xs"
                    disabled={!canSyncSelected || syncNow.isPending}
                    onClick={() => syncNow.mutate(selected.id)}
                  >
                    <RefreshCw
                      size={14}
                      className={syncNow.isPending ? "animate-spin" : undefined}
                    />
                    Sync
                  </button>
                ) : null}
                {canManage && selectedIsFile ? (
                  <button
                    type="button"
                    className="secondary-button h-8 px-2.5 text-xs"
                    disabled={selectedImporting}
                    onClick={() => openReplace(selected)}
                  >
                    <Replace size={14} />
                    Replace
                  </button>
                ) : null}
                <button
                  type="button"
                  className="secondary-button h-8 px-2.5 text-xs"
                  disabled={!canDownloadSelected || downloadingId === selected.id}
                  title={
                    canDownloadSelected
                      ? "Download Markdown zip for NotebookLM — choose grouping level"
                      : "Import pages before downloading"
                  }
                  onClick={() => setExportSource(selected)}
                >
                  <Download size={14} />
                  Download
                </button>
                {canManage ? (
                  <button
                    type="button"
                    className="icon-button h-8 w-8 text-muted hover:text-rose-600 disabled:opacity-40"
                    title="Delete source"
                    disabled={selectedImporting || deleteSource.isPending}
                    onClick={() => setDeleteSourceId(selected.id)}
                  >
                    <Trash2 size={14} />
                  </button>
                ) : null}
              </div>
            </div>
          </section>
        ) : null}

        {readyEmpty && canManage ? (
          <section className="rounded-2xl border border-border bg-surface p-5">
            <h2 className="text-lg font-semibold">Ready to import</h2>
            <p className="mt-1 text-sm text-muted">The source is connected and ready.</p>
            <button
              type="button"
              className="primary-button mt-4"
              disabled={startImport.isPending}
              onClick={() => selected && startImport.mutate(selected.id)}
            >
              Start import
            </button>
          </section>
        ) : showMonitor && job ? (
          <ImportProgressPanel
            job={job}
            workspaceId={workspaceId}
            canManage={canManage}
            onViewDocuments={() =>
              router.push(`/app/workspaces/${workspaceId}/spaces/${spaceId}/pages`)
            }
            onRetry={canManage && selected ? () => startImport.mutate(selected.id) : undefined}
          />
        ) : (
          <DocumentPanel spaceId={spaceId} sourceId={selected?.id} sourceName={selected?.name} />
        )}
      </div>

      <DeleteSourceDialog
        open={!!deleteTarget}
        sourceName={deleteTarget?.name || ""}
        pending={deleteSource.isPending}
        onCancel={() => setDeleteSourceId(null)}
        onConfirm={() => deleteTarget && deleteSource.mutate(deleteTarget.id)}
      />
      <ExportMdDialog
        open={!!exportSource}
        sourceId={exportSource?.id}
        sourceName={exportSource?.name || ""}
        pending={!!exportSource && downloadingId === exportSource.id}
        onClose={() => {
          if (downloadingId) return;
          setExportSource(null);
        }}
        onConfirm={(depth) => {
          if (exportSource) void handleDownload(exportSource, depth);
        }}
      />
      <ConnectionFormDialog
        open={!!editConnection}
        workspaceId={workspaceId}
        connection={editConnection}
        onClose={() => setEditConnection(null)}
      />
      <UploadFilesDialog
        open={replaceOpen}
        onClose={() => {
          setReplaceOpen(false);
          setReplaceSourceId(null);
        }}
        workspaceId={workspaceId}
        spaceId={spaceId}
        sourceTypeHint={replaceHint}
        replaceSourceId={replaceSourceId || undefined}
      />
    </div>
  );
}
