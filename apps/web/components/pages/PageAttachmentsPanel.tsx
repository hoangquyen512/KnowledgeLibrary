"use client";

import { Download, FileText, Paperclip } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { clientApi } from "@/lib/api";

export type PageAttachment = {
  id: string;
  document_id: string;
  filename: string;
  media_type: string;
  size_bytes: number;
  is_drawio: boolean;
  created_at: string;
};

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function PageAttachmentsPanel({ pageId }: { pageId: string }) {
  const { data: attachments = [], isLoading } = useQuery({
    queryKey: ["page-attachments", pageId],
    queryFn: () => clientApi<PageAttachment[]>(`/documents/${pageId}/attachments`),
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <section className="mt-8 border-t border-border pt-6">
        <p className="text-sm text-muted">Loading attachments…</p>
      </section>
    );
  }
  if (!attachments.length) return null;

  return (
    <section className="mt-8 border-t border-border pt-6">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
        <Paperclip size={16} />
        Attachments ({attachments.length})
      </h2>
      <ul className="mt-3 divide-y divide-border rounded-xl border border-border">
        {attachments.map((att) => (
          <li key={att.id} className="flex items-center justify-between gap-3 px-3 py-2.5 text-sm">
            <div className="flex min-w-0 items-center gap-2">
              <FileText size={16} className="shrink-0 text-muted" />
              <div className="min-w-0">
                <p className="truncate font-medium">{att.filename}</p>
                <p className="text-xs text-muted">
                  {formatBytes(att.size_bytes)}
                  {att.is_drawio ? " · draw.io" : ""}
                </p>
              </div>
            </div>
            <a
              href={`/api/proxy-attachment/${att.id}`}
              className="secondary-button shrink-0"
              download={att.filename}
              title="Download"
            >
              <Download size={14} />
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
