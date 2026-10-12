"use client";

import { Check, Info } from "lucide-react";
import { useMemo, useState } from "react";
import type { Space } from "@/lib/api";
import { askAI } from "./strings";

export function SpaceScopeSelector({
  spaces,
  selected,
  onToggle,
  onSelectAll,
}: {
  spaces: Space[];
  selected: string[];
  onToggle: (id: string) => void;
  onSelectAll?: () => void;
}) {
  const [q, setQ] = useState("");
  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!term) return spaces;
    return spaces.filter((s) => s.name.toLowerCase().includes(term) || s.slug.toLowerCase().includes(term));
  }, [spaces, q]);

  const showSearch = spaces.length > 8;

  return (
    <div>
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-1 text-xs font-medium text-muted">
          {askAI.spacesInScope}
          <span title="Answers only use content from selected Spaces">
            <Info size={12} />
          </span>
        </p>
        {onSelectAll && spaces.length > 1 ? (
          <button type="button" className="text-[11px] font-medium text-primary hover:underline" onClick={onSelectAll}>
            {askAI.selectAll}
          </button>
        ) : null}
      </div>
      {showSearch ? (
        <input
          className="input mt-1.5 h-8 text-xs"
          placeholder={askAI.searchSpaces}
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      ) : null}
      <ul className="mt-1.5 max-h-40 space-y-1.5 overflow-y-auto pr-0.5">
        {filtered.map((s) => {
          const on = selected.includes(s.id);
          return (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => onToggle(s.id)}
                className={`flex w-full items-center gap-2 rounded-xl border px-2.5 py-2 text-left text-sm transition ${
                  on
                    ? "border-primary/50 bg-blue-50 text-foreground dark:border-primary/40 dark:bg-blue-950/35"
                    : "border-border bg-surface text-foreground hover:bg-surface-muted"
                }`}
              >
                <span
                  className={`grid h-4 w-4 shrink-0 place-items-center rounded border ${
                    on
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-surface"
                  }`}
                >
                  {on ? <Check size={10} strokeWidth={3} /> : null}
                </span>
                <span className="truncate font-medium">{s.name}</span>
              </button>
            </li>
          );
        })}
        {filtered.length === 0 ? (
          <li className="px-1 py-2 text-xs text-muted">No spaces yet.</li>
        ) : null}
      </ul>
    </div>
  );
}
