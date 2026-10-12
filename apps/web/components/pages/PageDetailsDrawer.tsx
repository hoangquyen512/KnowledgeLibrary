"use client";

import { Info, X } from "lucide-react";
import type { PageDetail } from "@/lib/pages";

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function PageDetailsDrawer({
  open,
  onClose,
  page,
  spaceName,
}: {
  open: boolean;
  onClose: () => void;
  page: PageDetail;
  spaceName: string;
}) {
  if (!open) return null;

  const rows: [string, string][] = [
    ["Title", page.title],
    ["Space", spaceName],
    ["Status", page.status],
    ["Origin", page.origin === "CONFLUENCE" ? "Confluence" : "Knowledge Library"],
    ["Created", formatDate(page.created_at)],
    ["Updated", formatDate(page.updated_at)],
  ];
  if (page.external_id) rows.push(["External ID", page.external_id]);
  if (page.external_version) rows.push(["Version", page.external_version]);
  if (page.parent_id) rows.push(["Parent page", page.parent_id]);
  if (page.child_count > 0) rows.push(["Child pages", String(page.child_count)]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <aside
        className="flex h-full w-full max-w-sm flex-col border-l border-border bg-surface shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Info size={16} /> Page details
          </h2>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>
        <dl className="flex-1 space-y-3 overflow-y-auto p-4 text-sm">
          {rows.map(([label, value]) => (
            <div key={label}>
              <dt className="text-xs font-medium uppercase tracking-wide text-muted">{label}</dt>
              <dd className="mt-0.5 break-words text-foreground">{value}</dd>
            </div>
          ))}
          {page.external_url ? (
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-muted">Source URL</dt>
              <dd className="mt-0.5">
                <a
                  href={page.external_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-primary hover:underline"
                >
                  Open in Confluence
                </a>
              </dd>
            </div>
          ) : null}
        </dl>
      </aside>
    </div>
  );
}
