"use client";

import { useMemo, useState } from "react";
import { Copy, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import {
  formatAnswerMeta,
  hasStructuredSections,
  isNotebookLMAnswer,
  toPlainText,
  type AskCitation,
  type AskStructured,
} from "@/lib/ask-ai";
import { AnswerHighlights } from "./AnswerHighlights";
import { AnswerSummary } from "./AnswerSummary";
import { AnswerWithCitations } from "./AnswerWithCitations";
import { CitationDetailPanel } from "./CitationDetailPanel";
import { KeyChangesList } from "./KeyChangesList";
import { SourceReferences } from "./SourceReferences";
import { askAI } from "./strings";

function PlainTextBody({ content }: { content: string }) {
  const text = toPlainText(content);
  if (!text) return null;
  return (
    <div className="whitespace-pre-wrap text-[14px] leading-[1.65] text-foreground/90">{text}</div>
  );
}

export function AIResponseCard({
  content,
  structured,
  citations,
  workspaceId,
  fallbackSpaceId,
  chunkCount,
  docCount,
  streaming,
  onRegenerate,
}: {
  content: string;
  structured?: AskStructured | null;
  citations: AskCitation[];
  workspaceId: string;
  fallbackSpaceId?: string | null;
  chunkCount?: number | null;
  docCount?: number | null;
  streaming?: boolean;
  onRegenerate?: () => void;
}) {
  const [activeCitationIndex, setActiveCitationIndex] = useState<number | null>(null);
  const meta = formatAnswerMeta(chunkCount, docCount);
  const showStructured = hasStructuredSections(structured);
  const notebooklm = isNotebookLMAnswer(structured);
  const isNoSource = structured?.answer_type === "NO_SOURCE";

  const mergedCitations = useMemo(() => {
    if (!notebooklm || !structured?.sources?.length) return citations;
    const byIndex = new Map(citations.map((c) => [c.citation_index, c]));
    return structured.sources.map((src) => {
      const existing = byIndex.get(src.id);
      return {
        id: existing?.id || `src-${src.id}`,
        document_id: existing?.document_id || "",
        chunk_id: existing?.chunk_id || "",
        citation_index: src.id,
        snippet: src.quoted_snippet || existing?.snippet || null,
        title: src.page_title || existing?.title || null,
        space_id: existing?.space_id || null,
        section_heading: src.section_heading || existing?.section_heading || null,
        source_url: src.source_url || existing?.source_url || null,
      } satisfies AskCitation;
    });
  }, [citations, notebooklm, structured?.sources]);

  const activeCitation =
    activeCitationIndex != null
      ? mergedCitations.find((c) => c.citation_index === activeCitationIndex) || null
      : null;

  const copy = async () => {
    const text = toPlainText(
      (notebooklm ? structured?.answer : null) ||
        content ||
        [
          ...(structured?.summary || []),
          ...(structured?.key_changes || []).map((k) => k.title),
          ...(structured?.highlights || []).map((h) => h.text),
          structured?.markdown || "",
        ].join("\n"),
    );
    try {
      await navigator.clipboard.writeText(text);
      toast.success(askAI.copied);
    } catch {
      toast.error("Copy failed");
    }
  };

  return (
    <article className="w-full rounded-2xl border border-border bg-surface shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2 border-b border-border px-4 py-3 sm:px-5">
        <p className="text-sm text-muted">
          {streaming && !meta ? askAI.analyzing : meta || (isNoSource ? askAI.noSourceTitle : "Answer")}
        </p>
        <p className="text-xs text-muted">ⓘ {askAI.citationHint}</p>
      </div>

      <div className={notebooklm && activeCitation ? "grid gap-4 lg:grid-cols-[1fr_320px]" : ""}>
        <div className="space-y-6 px-4 py-5 sm:px-5">
          {structured?.caveat ? (
            <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
              {structured.caveat}
            </p>
          ) : null}

          {isNoSource ? (
            <div className="space-y-2 text-sm">
              <p className="font-medium text-foreground">{askAI.noSourceTitle}</p>
              <p className="text-muted">
                {toPlainText(structured?.answer || structured?.markdown) || askAI.noSourceBody}
              </p>
              <ul className="list-disc space-y-1 pl-5 text-muted">
                <li>Select more Spaces</li>
                <li>Try more specific keywords</li>
                <li>Check that sources are indexed</li>
              </ul>
            </div>
          ) : null}

          {notebooklm && !isNoSource && structured?.answer ? (
            <AnswerWithCitations
              answer={structured.answer}
              citations={mergedCitations}
              workspaceId={workspaceId}
              fallbackSpaceId={fallbackSpaceId}
              onCitationClick={setActiveCitationIndex}
            />
          ) : null}

          {showStructured && !isNoSource && !notebooklm ? (
            <div className="grid gap-6 lg:grid-cols-2">
              <div className="space-y-6">
                <AnswerSummary items={structured?.summary || []} />
                <AnswerHighlights
                  items={structured?.highlights || []}
                  citations={citations}
                  workspaceId={workspaceId}
                  fallbackSpaceId={fallbackSpaceId}
                />
              </div>
              <div className="space-y-6">
                <KeyChangesList
                  items={structured?.key_changes || []}
                  citations={citations}
                  workspaceId={workspaceId}
                  fallbackSpaceId={fallbackSpaceId}
                />
              </div>
            </div>
          ) : null}

          {!notebooklm && !showStructured && content ? <PlainTextBody content={content} /> : null}

          {showStructured && structured?.markdown && !isNoSource && !notebooklm ? (
            <PlainTextBody content={structured.markdown} />
          ) : null}

          {streaming && !content && !showStructured ? (
            <div className="space-y-3 animate-pulse">
              <div className="h-4 w-2/3 rounded bg-surface-muted" />
              <div className="h-4 w-full rounded bg-surface-muted" />
              <div className="h-4 w-5/6 rounded bg-surface-muted" />
              <div className="h-20 rounded-xl bg-surface-muted" />
            </div>
          ) : null}

          {!isNoSource && mergedCitations.length ? (
            <SourceReferences
              citations={mergedCitations}
              workspaceId={workspaceId}
              fallbackSpaceId={fallbackSpaceId}
            />
          ) : null}
        </div>

        {notebooklm && activeCitation ? (
          <div className="border-t border-border p-4 lg:border-l lg:border-t-0">
            <CitationDetailPanel
              citation={activeCitation}
              workspaceId={workspaceId}
              fallbackSpaceId={fallbackSpaceId}
              onClose={() => setActiveCitationIndex(null)}
            />
          </div>
        ) : null}
      </div>

      {!streaming ? (
        <div className="flex flex-wrap gap-2 border-t border-border px-4 py-2.5 sm:px-5">
          <button type="button" className="secondary-button h-8 px-2.5 text-xs" onClick={() => void copy()}>
            <Copy size={14} /> {askAI.copy}
          </button>
          {onRegenerate ? (
            <button type="button" className="secondary-button h-8 px-2.5 text-xs" onClick={onRegenerate}>
              <RefreshCw size={14} /> {askAI.regenerate}
            </button>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
