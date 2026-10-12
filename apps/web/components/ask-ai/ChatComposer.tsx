"use client";

import { Send, Square, Sparkles } from "lucide-react";
import { useEffect, useRef } from "react";
import { askAI } from "./strings";

export function ChatComposer({
  value,
  onChange,
  onSend,
  onStop,
  disabled,
  busy,
  noSpace,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  onStop?: () => void;
  disabled?: boolean;
  busy?: boolean;
  noSpace?: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(Math.max(el.scrollHeight, 56), 160)}px`;
  }, [value]);

  const canSend = !disabled && !busy && !!value.trim() && !noSpace;

  return (
    <div className="sticky bottom-0 border-t border-border bg-surface/95 p-3 backdrop-blur">
      {noSpace ? <p className="mb-2 text-xs text-amber-700 dark:text-amber-300">{askAI.noSpace}</p> : null}
      <div className="flex items-end gap-2 rounded-2xl border border-border bg-surface px-2 py-2 shadow-sm focus-within:border-primary focus-within:ring-2 focus-within:ring-blue-100 dark:focus-within:ring-blue-950">
        <span className="mb-1.5 grid h-9 w-9 place-items-center text-muted" title="Ask AI">
          <Sparkles size={16} />
        </span>
        <textarea
          ref={ref}
          className="max-h-40 min-h-[56px] flex-1 resize-none bg-transparent py-3 text-sm outline-none placeholder:text-muted"
          placeholder={askAI.composerPlaceholder}
          value={value}
          disabled={disabled || busy}
          rows={1}
          title={askAI.enterToSend}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (canSend) onSend();
            }
          }}
        />
        {busy && onStop ? (
          <button type="button" className="secondary-button mb-0.5 h-10 px-3" onClick={onStop} title={askAI.stop}>
            <Square size={14} className="fill-current" />
            <span className="sr-only sm:not-sr-only">{askAI.stop}</span>
          </button>
        ) : (
          <button
            type="button"
            className="primary-button mb-0.5 h-10 w-10 shrink-0 px-0"
            disabled={!canSend}
            onClick={onSend}
            title={askAI.send}
          >
            <Send size={16} />
          </button>
        )}
      </div>
      <p className="mt-1.5 text-[11px] text-muted">{askAI.enterToSend}</p>
    </div>
  );
}
