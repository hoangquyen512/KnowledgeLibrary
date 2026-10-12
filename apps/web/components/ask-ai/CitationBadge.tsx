"use client";

import { citationPageHref, type AskCitation } from "@/lib/ask-ai";

export function CitationBadge({
  index,
  citations,
  workspaceId,
  fallbackSpaceId,
  onClick,
}: {
  index: number;
  citations: AskCitation[];
  workspaceId: string;
  fallbackSpaceId?: string | null;
  onClick?: (index: number) => void;
}) {
  const citation = citations.find((c) => c.citation_index === index);
  if (!citation) return null;
  const href = citationPageHref(workspaceId, citation, fallbackSpaceId);
  const label = `[${index}]`;
  const title = citation.section_heading || citation.title || `Source ${index}`;
  const className =
    "mx-0.5 inline-flex cursor-pointer items-center rounded-md bg-blue-100 px-1.5 py-0.5 align-baseline text-[11px] font-semibold text-blue-700 hover:bg-blue-200 dark:bg-blue-950/60 dark:text-blue-300 dark:hover:bg-blue-900/70";

  if (onClick) {
    return (
      <button
        type="button"
        className={className}
        title={title}
        onClick={() => onClick(index)}
      >
        {label}
      </button>
    );
  }

  if (href) {
    return (
      <a href={href} className={className} title={title}>
        {label}
      </a>
    );
  }

  return (
    <span className={className} title={title}>
      {label}
    </span>
  );
}
