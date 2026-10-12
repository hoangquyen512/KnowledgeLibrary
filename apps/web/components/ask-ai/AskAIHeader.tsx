"use client";

import { Lightbulb } from "lucide-react";
import { useRef, useState } from "react";
import { useClickOutside } from "@/lib/use-click-outside";
import { askAI, suggestedPrompts } from "./strings";

export function AskAIHeader({
  onPickPrompt,
  title,
  subtitle,
}: {
  onPickPrompt: (prompt: string) => void;
  title?: string;
  subtitle?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useClickOutside(ref, open, () => setOpen(false));

  return (
    <header className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-4 py-3 sm:px-5">
      <div className="min-w-0">
        <h1 className="text-lg font-semibold tracking-tight text-foreground sm:text-xl">
          {title || askAI.pageTitle}
        </h1>
        <p className="mt-1 text-sm text-muted">{subtitle || askAI.pageSubtitle}</p>
      </div>
      <div className="relative" ref={ref}>
        <button type="button" className="secondary-button text-xs" onClick={() => setOpen((v) => !v)}>
          <Lightbulb size={14} /> {askAI.suggestQuestions}
        </button>
        {open ? (
          <div className="absolute right-0 z-20 mt-2 w-72 rounded-xl border border-border bg-surface p-2 shadow-lg">
            <ul className="space-y-1">
              {suggestedPrompts.map((p) => (
                <li key={p}>
                  <button
                    type="button"
                    className="w-full rounded-lg px-2.5 py-2 text-left text-sm hover:bg-surface-muted"
                    onClick={() => {
                      onPickPrompt(p);
                      setOpen(false);
                    }}
                  >
                    {p}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </header>
  );
}
