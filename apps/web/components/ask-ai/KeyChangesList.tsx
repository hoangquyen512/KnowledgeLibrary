"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import {
  citationPageHref,
  filterValidCitationIndices,
  toPlainText,
  type AskCitation,
  type AskKeyChange,
} from "@/lib/ask-ai";
import { CitationBadge } from "./CitationBadge";

export function KeyChangesList({
  items,
  citations,
  workspaceId,
  fallbackSpaceId,
}: {
  items: AskKeyChange[];
  citations: AskCitation[];
  workspaceId: string;
  fallbackSpaceId?: string | null;
}) {
  if (!items.length) return null;

  return (
    <section>
      <h3 className="mb-2.5 flex items-center gap-2 text-[15px] font-semibold text-foreground">
        <span className="text-base" aria-hidden>
          📋
        </span>
        Key changes
      </h3>
      <ol className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface">
        {items.map((item, i) => {
          const indices = filterValidCitationIndices(item.citation_indices, citations);
          const primary = indices[0]
            ? citations.find((c) => c.citation_index === indices[0])
            : undefined;
          const href = primary
            ? citationPageHref(workspaceId, primary, fallbackSpaceId)
            : null;
          const title = toPlainText(item.title);
          const description = toPlainText(item.description);

          return (
            <li
              key={`${title}-${i}`}
              className="flex items-start gap-3 px-3 py-2.5 text-sm transition hover:bg-blue-50/50 dark:hover:bg-blue-950/20"
            >
              <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-surface-muted text-xs font-semibold text-muted">
                {i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-medium text-foreground">{title}</p>
                {description ? <p className="mt-0.5 text-[13px] text-muted">{description}</p> : null}
              </div>
              <div className="flex shrink-0 items-center gap-1 pt-0.5">
                {indices.map((idx) => (
                  <CitationBadge
                    key={idx}
                    index={idx}
                    citations={citations}
                    workspaceId={workspaceId}
                    fallbackSpaceId={fallbackSpaceId}
                  />
                ))}
                {href ? (
                  <Link
                    href={href}
                    className="text-muted hover:text-primary"
                    aria-label={`Open source for ${title}`}
                  >
                    <ChevronRight size={16} />
                  </Link>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
