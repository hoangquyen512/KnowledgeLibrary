"use client";

import {
  filterValidCitationIndices,
  toPlainText,
  type AskCitation,
  type AskHighlight,
} from "@/lib/ask-ai";
import { CitationBadge } from "./CitationBadge";

export function AnswerHighlights({
  items,
  citations,
  workspaceId,
  fallbackSpaceId,
}: {
  items: AskHighlight[];
  citations: AskCitation[];
  workspaceId: string;
  fallbackSpaceId?: string | null;
}) {
  if (!items.length) return null;
  return (
    <section>
      <h3 className="mb-2.5 flex items-center gap-2 text-[15px] font-semibold text-foreground">
        <span className="text-base" aria-hidden>
          ⓘ
        </span>
        Notable details
      </h3>
      <ul className="space-y-2.5 text-[14px] leading-[1.65] text-foreground/90">
        {items.map((item, i) => {
          const indices = filterValidCitationIndices(item.citation_indices, citations);
          const text = toPlainText(item.text).replace(/\s*\[\d+\]\s*/g, " ").trim();
          if (!text) return null;
          return (
            <li key={i} className="flex gap-2.5">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400 dark:bg-slate-500" />
              <span>
                {text}{" "}
                {indices.map((idx) => (
                  <CitationBadge
                    key={idx}
                    index={idx}
                    citations={citations}
                    workspaceId={workspaceId}
                    fallbackSpaceId={fallbackSpaceId}
                  />
                ))}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
