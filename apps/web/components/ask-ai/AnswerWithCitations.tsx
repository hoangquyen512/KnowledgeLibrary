"use client";

import { useMemo } from "react";
import { CitationBadge } from "./CitationBadge";
import { type AskCitation } from "@/lib/ask-ai";

const CITATION_RE = /\[(\d+)\]/g;

export function AnswerWithCitations({
  answer,
  citations,
  workspaceId,
  fallbackSpaceId,
  onCitationClick,
}: {
  answer: string;
  citations: AskCitation[];
  workspaceId: string;
  fallbackSpaceId?: string | null;
  onCitationClick?: (index: number) => void;
}) {
  const parts = useMemo(() => {
    const nodes: Array<string | { index: number }> = [];
    let last = 0;
    for (const match of answer.matchAll(CITATION_RE)) {
      const idx = match.index ?? 0;
      if (idx > last) nodes.push(answer.slice(last, idx));
      nodes.push({ index: Number(match[1]) });
      last = idx + match[0].length;
    }
    if (last < answer.length) nodes.push(answer.slice(last));
    return nodes;
  }, [answer]);

  return (
    <div className="whitespace-pre-wrap text-[14px] leading-[1.7] text-foreground/90">
      {parts.map((part, i) => {
        if (typeof part === "string") {
          return <span key={`t-${i}`}>{part}</span>;
        }
        return (
          <CitationBadge
            key={`c-${i}-${part.index}`}
            index={part.index}
            citations={citations}
            workspaceId={workspaceId}
            fallbackSpaceId={fallbackSpaceId}
            onClick={onCitationClick}
          />
        );
      })}
    </div>
  );
}
