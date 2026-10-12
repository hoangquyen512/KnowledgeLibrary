"use client";

import { Check } from "lucide-react";
import { useMemo } from "react";
import type { PageTreeNode } from "@/lib/pages";
import { studio } from "./strings";

function flattenTree(nodes: PageTreeNode[]): PageTreeNode[] {
  return nodes;
}

export function DocumentPicker({
  trees,
  selected,
  onToggle,
  onSelectAll,
  onClear,
}: {
  trees: Record<string, PageTreeNode[]>;
  selected: string[];
  onToggle: (id: string) => void;
  onSelectAll: () => void;
  onClear: () => void;
}) {
  const allNodes = useMemo(() => {
    const out: PageTreeNode[] = [];
    for (const nodes of Object.values(trees)) {
      out.push(...flattenTree(nodes));
    }
    return out;
  }, [trees]);

  if (!allNodes.length) return null;

  return (
    <div>
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold text-foreground">{studio.documentPicker}</p>
        <div className="flex gap-2">
          <button type="button" className="text-[11px] font-medium text-primary hover:underline" onClick={onSelectAll}>
            {studio.selectAllPages}
          </button>
          <button type="button" className="text-[11px] font-medium text-muted hover:underline" onClick={onClear}>
            {studio.clearPages}
          </button>
        </div>
      </div>
      <p className="mt-1 text-[11px] leading-relaxed text-muted">{studio.documentPickerHint}</p>
      <ul className="mt-2 space-y-1">
        {allNodes.map((node) => {
          const on = selected.includes(node.id);
          return (
            <li key={node.id}>
              <button
                type="button"
                onClick={() => onToggle(node.id)}
                className={`flex w-full items-center gap-2 rounded-lg border px-2.5 py-2 text-left text-xs transition ${
                  on
                    ? "border-primary/50 bg-blue-50 text-foreground dark:border-primary/40 dark:bg-blue-950/35"
                    : "border-border bg-surface text-foreground hover:bg-surface-muted"
                }`}
              >
                <span
                  className={`grid h-3.5 w-3.5 shrink-0 place-items-center rounded border ${
                    on ? "border-primary bg-primary text-primary-foreground" : "border-border bg-surface"
                  }`}
                >
                  {on ? <Check size={8} strokeWidth={3} /> : null}
                </span>
                <span className="truncate">{node.title}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
