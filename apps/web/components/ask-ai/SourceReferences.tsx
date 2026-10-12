"use client";

import { useState } from "react";
import Link from "next/link";
import { citationPageHref, type AskCitation } from "@/lib/ask-ai";
import { askAI } from "./strings";

const DEFAULT_VISIBLE = 5;

export function SourceReferences({
  citations,
  workspaceId,
  fallbackSpaceId,
}: {
  citations: AskCitation[];
  workspaceId: string;
  fallbackSpaceId?: string | null;
}) {
  const [expanded, setExpanded] = useState(false);
  if (!citations.length) return null;

  const sorted = [...citations].sort((a, b) => a.citation_index - b.citation_index);
  const visible = expanded ? sorted : sorted.slice(0, DEFAULT_VISIBLE);
  const canToggle = sorted.length > DEFAULT_VISIBLE;

  return (
    <section>
      <div className="mb-2.5 flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-[15px] font-semibold text-foreground">
          <span className="text-base" aria-hidden>
            📖
          </span>
          {askAI.references}
        </h3>
        {canToggle ? (
          <button
            type="button"
            className="text-xs font-medium text-primary hover:underline"
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? askAI.collapseSources : askAI.expandSources}
          </button>
        ) : null}
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {visible.map((c) => {
          const href = citationPageHref(workspaceId, c, fallbackSpaceId);
          const card = (
            <div className="rounded-xl border border-border bg-surface px-3 py-2.5 transition hover:border-primary/40 hover:bg-blue-50/40 dark:hover:bg-blue-950/20">
              <span className="inline-flex rounded-md bg-blue-100 px-1.5 py-0.5 text-[11px] font-semibold text-blue-700 dark:bg-blue-950/60 dark:text-blue-300">
                [{c.citation_index}]
              </span>
              <p className="mt-1.5 line-clamp-2 text-sm font-medium text-foreground">
                {c.title || "Source"}
              </p>
              {c.section_heading ? (
                <p className="mt-0.5 line-clamp-1 text-xs text-muted">{c.section_heading}</p>
              ) : null}
              {c.snippet ? (
                <p className="mt-1 line-clamp-2 text-xs text-muted">"{c.snippet}"</p>
              ) : null}
            </div>
          );
          return href ? (
            <Link key={c.id} href={href} className="block">
              {card}
            </Link>
          ) : (
            <div key={c.id}>{card}</div>
          );
        })}
      </div>
    </section>
  );
}
