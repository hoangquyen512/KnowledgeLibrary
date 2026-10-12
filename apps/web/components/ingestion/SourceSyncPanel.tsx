"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { clientApi } from "@/lib/api";
import { mapErrorMessage, type SourceRow } from "@/lib/import-status";

function relativeSync(iso: string | null | undefined) {
  if (!iso) return "Never";
  const ms = Date.now() - new Date(iso).getTime();
  const m = Math.round(ms / 60000);
  if (m < 1) return "Just now";
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 48) return `${h} hour${h === 1 ? "" : "s"} ago`;
  const d = Math.round(h / 24);
  return `${d} day${d === 1 ? "" : "s"} ago`;
}

function syncStatusLabel(status: string | null | undefined) {
  switch (status) {
    case "SUCCESS":
      return "Success";
    case "PARTIAL":
      return "Partial";
    case "FAILED":
      return "Failed";
    default:
      return null;
  }
}

/** Compact sync controls shown inside each source card. */
export function SourceSyncInline({
  source,
  spaceId,
  disabled,
  onSyncStarted,
}: {
  source: SourceRow;
  spaceId: string;
  disabled?: boolean;
  onSyncStarted?: (jobId: string) => void;
}) {
  const client = useQueryClient();
  const [interval, setInterval] = useState(source.sync_interval || "OFF");
  const [enabled, setEnabled] = useState(Boolean(source.sync_enabled));

  useEffect(() => {
    setInterval(source.sync_interval || "OFF");
    setEnabled(Boolean(source.sync_enabled));
  }, [source.sync_interval, source.sync_enabled, source.id]);

  const saveSettings = useMutation({
    mutationFn: () =>
      clientApi<SourceRow>(`/sources/${source.id}/sync-settings`, {
        method: "PATCH",
        body: JSON.stringify({
          sync_enabled: enabled && interval !== "OFF",
          sync_interval: interval,
        }),
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["sources", spaceId] });
      toast.success("Sync schedule saved");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const syncNow = useMutation({
    mutationFn: () =>
      clientApi<{ id: string }>(`/sources/${source.id}/sync`, { method: "POST" }),
    onSuccess: (job) => {
      client.invalidateQueries({ queryKey: ["sources", spaceId] });
      onSyncStarted?.(job.id);
      toast.success("Sync started");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const statusLabel = syncStatusLabel(source.last_sync_status);
  const errorText =
    source.last_sync_status === "FAILED"
      ? mapErrorMessage(undefined, source.last_sync_error)
      : null;
  const busy = disabled || syncNow.isPending || source.status !== "READY";

  return (
    <div
      className="mt-2 space-y-2 border-t border-border/60 pt-2"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="text-[10px] text-muted">
          Sync: {relativeSync(source.last_sync_at)}
          {statusLabel ? ` · ${statusLabel}` : ""}
        </p>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-md border border-border bg-surface px-2 py-1 text-[10px] font-semibold hover:bg-surface-muted disabled:opacity-50"
          disabled={busy}
          onClick={() => syncNow.mutate()}
        >
          <RefreshCw className={`h-3 w-3 ${syncNow.isPending ? "animate-spin" : ""}`} />
          Sync
        </button>
      </div>
      {errorText ? (
        <p className="rounded-md bg-rose-50 px-2 py-1 text-[10px] leading-snug text-rose-700 dark:bg-rose-950/40 dark:text-rose-200">
          {errorText}
        </p>
      ) : null}
      <div className="flex items-center gap-1.5">
        <select
          className="min-w-0 flex-1 rounded-md border border-border bg-surface px-1.5 py-1 text-[10px]"
          value={interval}
          disabled={source.status !== "READY"}
          onChange={(e) => {
            const v = e.target.value;
            setInterval(v);
            setEnabled(v !== "OFF");
          }}
        >
          <option value="OFF">Auto: Off</option>
          <option value="HOURLY">Auto: Hourly</option>
          <option value="DAILY">Auto: Daily</option>
        </select>
        <button
          type="button"
          className="shrink-0 rounded-md bg-primary px-2 py-1 text-[10px] font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-50"
          disabled={saveSettings.isPending || source.status !== "READY"}
          onClick={() => saveSettings.mutate()}
        >
          Save
        </button>
      </div>
    </div>
  );
}

/** @deprecated Use SourceSyncInline inside source cards. */
export function SourceSyncPanel({
  source,
  spaceId,
  disabled,
  onSyncStarted,
}: {
  source: SourceRow;
  spaceId: string;
  disabled?: boolean;
  onSyncStarted?: (jobId: string) => void;
}) {
  return (
    <SourceSyncInline
      source={source}
      spaceId={spaceId}
      disabled={disabled}
      onSyncStarted={onSyncStarted}
    />
  );
}
