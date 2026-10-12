"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { clientApi } from "@/lib/api";
import { BrandEmptyState } from "@/components/brand";

type Attachment = {
  id: string;
  filename: string;
  media_type: string;
  size_bytes: number;
  is_drawio: boolean;
};

type DocRow = {
  id: string;
  title: string;
  status: string;
  document_type: string;
};

/** Same-origin API rewrite (cookies work). Avoid /api/proxy-attachment for fetch. */
function attachmentContentUrl(id: string) {
  return `/api/v1/attachments/${id}/content`;
}

function baseName(filename: string) {
  return filename.replace(/\.(drawio|dio|xml|png|jpe?g|gif|svg)$/i, "").trim().toLowerCase();
}

export function DocumentPanel({
  spaceId,
  sourceId,
  sourceName,
}: {
  spaceId: string;
  sourceId?: string;
  sourceName?: string;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    setSelectedId(null);
  }, [sourceId]);

  const docsPath =
    sourceId != null
      ? `/spaces/${spaceId}/documents?source_id=${encodeURIComponent(sourceId)}`
      : `/spaces/${spaceId}/documents`;

  const { data: documents = [], isLoading, isError, error } = useQuery({
    queryKey: ["documents", spaceId, sourceId ?? "all"],
    queryFn: () => clientApi<DocRow[]>(docsPath),
    enabled: !!spaceId,
    refetchInterval: 10_000,
  });

  const selected = documents.find((d) => d.id === selectedId) || documents[0] || null;

  const { data: detail } = useQuery({
    queryKey: ["document", selected?.id],
    queryFn: () =>
      clientApi<{
        id: string;
        title: string;
        raw_content: string | null;
        normalized_content: string | null;
      }>(`/documents/${selected!.id}`),
    enabled: !!selected?.id,
  });

  const { data: attachments = [] } = useQuery({
    queryKey: ["document-attachments", selected?.id],
    queryFn: () => clientApi<Attachment[]>(`/documents/${selected!.id}/attachments`),
    enabled: !!selected?.id,
  });

  if (!sourceId) {
    return (
      <BrandEmptyState
        className="min-h-72"
        mood="empty"
        title="Select a source"
        description="Choose a source on the left to browse imported pages."
      />
    );
  }

  if (isLoading) {
    return <p className="text-sm text-muted">Loading documents…</p>;
  }

  if (isError) {
    return (
      <p className="text-sm text-rose-600">
        {(error as Error)?.message || "Could not load documents."}
      </p>
    );
  }

  if (documents.length === 0) {
    return (
      <BrandEmptyState
        className="min-h-72"
        mood="empty"
        title="No pages for this source"
        description={
          sourceName
            ? `“${sourceName}” has no imported pages yet. Run import or sync first.`
            : "Import or sync this source to fetch Confluence pages."
        }
      />
    );
  }

  const html = (detail?.raw_content || "").replace(
    /\/api\/v1\/attachments\/([0-9a-f-]+)\/content/gi,
    "/api/v1/attachments/$1/content",
  );

  const images = attachments.filter((a) => !a.is_drawio && a.media_type.startsWith("image/"));
  const drawioBases = new Set(
    attachments.filter((a) => a.is_drawio).map((a) => baseName(a.filename)),
  );

  return (
    <div className="grid min-h-72 gap-3 lg:grid-cols-[220px_1fr]">
      <div className="min-w-0">
        {sourceName ? (
          <p className="mb-2 truncate text-xs font-medium text-muted">{sourceName}</p>
        ) : null}
        <ul className="max-h-[70vh] space-y-1 overflow-y-auto rounded-xl border border-border bg-surface p-2">
        {documents.map((d) => (
          <li key={d.id}>
            <button
              type="button"
              className={`w-full rounded-lg px-2 py-2 text-left text-sm ${
                (selected?.id || "") === d.id
                  ? "bg-surface-muted font-medium"
                  : "hover:bg-surface-muted/60"
              }`}
              onClick={() => setSelectedId(d.id)}
            >
              {d.title}
            </button>
          </li>
        ))}
        </ul>
      </div>
      <div className="space-y-3 rounded-xl border border-border bg-surface p-4">
        <h3 className="font-semibold">{detail?.title || selected?.title}</h3>
        <div className="flex flex-wrap gap-2">
          {images
            // Skip PNGs used as draw.io previews (shown inline in HTML).
            .filter((a) => {
              if (!a.filename.toLowerCase().endsWith(".png")) return true;
              return !drawioBases.has(baseName(a.filename));
            })
            .map((a) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                key={a.id}
                src={attachmentContentUrl(a.id)}
                alt={a.filename}
                className="max-h-40 rounded-lg border border-border"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = "none";
                }}
              />
            ))}
        </div>
        <div
          className="prose prose-sm max-w-none dark:prose-invert [&_img]:max-w-full"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      </div>
    </div>
  );
}

export function ImportSourceButton({
  sourceId,
  disabled,
}: {
  sourceId: string;
  disabled?: boolean;
}) {
  const client = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);

  const start = useMutation({
    mutationFn: () =>
      clientApi<{ id: string; status: string; progress_percent: number; stage: string }>(
        `/sources/${sourceId}/import`,
        { method: "POST" },
      ),
    onSuccess: (job) => {
      setJobId(job.id);
      client.invalidateQueries({ queryKey: ["sources"] });
    },
  });

  const { data: job } = useQuery({
    queryKey: ["ingestion-job", jobId],
    queryFn: () =>
      clientApi<{
        id: string;
        status: string;
        progress_percent: number;
        stage: string;
        message: string | null;
      }>(`/ingestion-jobs/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      if (s === "COMPLETED" || s === "COMPLETED_WITH_ERRORS" || s === "FAILED") return false;
      return 1500;
    },
  });

  useEffect(() => {
    if (!job) return;
    if (["COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"].includes(job.status)) {
      client.invalidateQueries({ queryKey: ["documents"] });
      client.invalidateQueries({ queryKey: ["space"] });
      client.invalidateQueries({ queryKey: ["sources"] });
    }
  }, [job, client]);

  return (
    <div className="mt-2 space-y-1">
      <button
        type="button"
        className="secondary-button w-full text-xs"
        disabled={
          disabled || start.isPending || job?.status === "RUNNING" || job?.status === "QUEUED"
        }
        onClick={() => start.mutate()}
      >
        {start.isPending ? "Starting…" : "Import"}
      </button>
      {job ? (
        <p className="text-[11px] text-muted">
          {job.stage} · {Math.round(Number(job.progress_percent) || 0)}% · {job.status}
          {job.message ? ` — ${job.message}` : ""}
        </p>
      ) : null}
      {start.isError ? (
        <p className="text-[11px] text-rose-600">{(start.error as Error).message}</p>
      ) : null}
    </div>
  );
}
