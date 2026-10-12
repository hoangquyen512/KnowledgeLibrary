"use client";

import { emptyPrompts } from "./strings";
import { askAI } from "./strings";

export function AskAIEmptyState({ onPick }: { onPick: (prompt: string) => void }) {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center px-4 py-16 text-center">
      <h2 className="text-xl font-semibold text-foreground">{askAI.emptyTitle}</h2>
      <p className="mt-2 text-sm text-muted">{askAI.emptySubtitle}</p>
      <div className="mt-8 grid w-full gap-2 sm:grid-cols-2">
        {emptyPrompts.map((p) => (
          <button
            key={p.title}
            type="button"
            className="rounded-xl border border-border bg-surface px-3 py-3 text-left text-sm transition hover:border-primary/40 hover:bg-blue-50/40 dark:hover:bg-blue-950/20"
            onClick={() => onPick(p.prompt)}
          >
            <span className="font-medium text-foreground">{p.title}</span>
            <span className="mt-1 block text-xs text-muted">{p.prompt}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

export function AskAIErrorState({
  title,
  body,
  actionLabel,
  actionHref,
}: {
  title: string;
  body: string;
  actionLabel?: string;
  actionHref?: string;
}) {
  return (
    <div className="mx-auto max-w-md rounded-2xl border border-border bg-surface p-6 text-center">
      <h2 className="text-base font-semibold text-foreground">{title}</h2>
      <p className="mt-2 text-sm text-muted">{body}</p>
      {actionLabel && actionHref ? (
        <a href={actionHref} className="primary-button mt-4 inline-flex">
          {actionLabel}
        </a>
      ) : null}
    </div>
  );
}

export function StreamingIndicator() {
  return (
    <div className="flex flex-wrap gap-2 text-xs text-muted">
      <span className="rounded-full bg-surface-muted px-2.5 py-1">{askAI.findingSources}</span>
      <span className="rounded-full bg-surface-muted px-2.5 py-1">{askAI.synthesizing}</span>
      <span className="rounded-full bg-blue-50 px-2.5 py-1 text-primary dark:bg-blue-950/40">
        {askAI.writingAnswer}
      </span>
    </div>
  );
}
