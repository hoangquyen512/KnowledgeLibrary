"use client";

import Link from "next/link";
import { ExternalLink, X } from "lucide-react";
import { citationPageHref, type AskCitation } from "@/lib/ask-ai";

export function CitationDetailPanel({
  citation,
  workspaceId,
  fallbackSpaceId,
  onClose,
}: {
  citation: AskCitation;
  workspaceId: string;
  fallbackSpaceId?: string | null;
  onClose: () => void;
}) {
  const internalHref = citationPageHref(workspaceId, citation, fallbackSpaceId);
  const externalUrl = citation.source_url?.trim() || null;

  return (
    <aside className="flex h-full flex-col rounded-xl border border-border bg-surface shadow-lg">
      <div className="flex items-start justify-between gap-2 border-b border-border px-4 py-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">Source [{citation.citation_index}]</p>
          <h3 className="mt-1 text-sm font-semibold text-foreground">
            {citation.title || citation.section_heading || "Source"}
          </h3>
          {citation.section_heading ? (
            <p className="mt-0.5 text-xs text-muted">{citation.section_heading}</p>
          ) : null}
        </div>
        <button
          type="button"
          className="rounded-md p-1 text-muted hover:bg-surface-muted hover:text-foreground"
          onClick={onClose}
          aria-label="Close source panel"
        >
          <X size={16} />
        </button>
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {citation.snippet ? (
          <blockquote className="rounded-lg border border-blue-100 bg-blue-50/60 px-3 py-2 text-sm leading-relaxed text-foreground/90 dark:border-blue-900/50 dark:bg-blue-950/30">
            “{citation.snippet}”
          </blockquote>
        ) : null}
        <div className="flex flex-col gap-2">
          {internalHref ? (
            <Link href={internalHref} className="secondary-button h-9 justify-center text-xs">
              Open in Knowledge Library
            </Link>
          ) : null}
          {externalUrl ? (
            <a
              href={externalUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="secondary-button h-9 justify-center text-xs"
            >
              <ExternalLink size={14} />
              View on Confluence
            </a>
          ) : null}
        </div>
      </div>
    </aside>
  );
}
