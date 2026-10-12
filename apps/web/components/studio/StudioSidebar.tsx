"use client";

import { LayoutTemplate, Network, Trash2 } from "lucide-react";
import type { StudioArtifact } from "@/lib/studio";
import { studio } from "./strings";

export function StudioSidebar({
  artifacts,
  selectedId,
  filterType,
  onSelect,
  onFilterType,
  onDelete,
  collapsed,
  onToggleCollapsed,
}: {
  artifacts: StudioArtifact[];
  selectedId: string | null;
  filterType: "PRESENTATION" | "MINDMAP";
  onSelect: (id: string) => void;
  onFilterType: (t: "PRESENTATION" | "MINDMAP") => void;
  onDelete: (id: string) => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
}) {
  const filtered = artifacts.filter((a) => a.artifact_type === filterType);

  return (
    <aside
      className={`flex h-full flex-col border-r border-border bg-surface ${
        collapsed ? "w-12" : "w-64 min-w-[16rem]"
      }`}
    >
      {!collapsed ? (
        <>
          <div className="border-b border-border px-3 py-3">
            <h2 className="text-sm font-semibold">{studio.pageTitle}</h2>
            <div className="mt-2 flex gap-1">
              <button
                type="button"
                className={`flex flex-1 items-center justify-center gap-1 rounded-lg px-2 py-1.5 text-[11px] font-medium ${
                  filterType === "PRESENTATION"
                    ? "bg-primary text-primary-foreground"
                    : "bg-surface-muted text-muted"
                }`}
                onClick={() => onFilterType("PRESENTATION")}
              >
                <LayoutTemplate size={12} />
                {studio.presentations}
              </button>
              <button
                type="button"
                className={`flex flex-1 items-center justify-center gap-1 rounded-lg px-2 py-1.5 text-[11px] font-medium ${
                  filterType === "MINDMAP"
                    ? "bg-primary text-primary-foreground"
                    : "bg-surface-muted text-muted"
                }`}
                onClick={() => onFilterType("MINDMAP")}
              >
                <Network size={12} />
                {studio.mindmaps}
              </button>
            </div>
          </div>
          <ul className="flex-1 overflow-y-auto p-2">
            {filtered.length === 0 ? (
              <li className="px-2 py-4 text-center text-xs text-muted">{studio.noArtifacts}</li>
            ) : (
              filtered.map((a) => (
                <li key={a.id} className="mb-1">
                  <div
                    className={`group flex items-center gap-1 rounded-xl border px-2 py-2 text-left text-sm transition ${
                      selectedId === a.id
                        ? "border-primary/50 bg-blue-50 dark:bg-blue-950/30"
                        : "border-transparent hover:bg-surface-muted"
                    }`}
                  >
                    <button type="button" className="min-w-0 flex-1 truncate text-left" onClick={() => onSelect(a.id)}>
                      <span className="block truncate font-medium">{a.title}</span>
                      <span className="text-[10px] text-muted">{a.status}</span>
                    </button>
                    <button
                      type="button"
                      className="rounded p-1 opacity-0 transition group-hover:opacity-100 hover:bg-surface-muted"
                      onClick={() => {
                        if (confirm(studio.deleteConfirm)) onDelete(a.id);
                      }}
                      aria-label={studio.delete}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </li>
              ))
            )}
          </ul>
        </>
      ) : (
        <button type="button" className="m-2 icon-button" onClick={onToggleCollapsed} aria-label="Expand sidebar">
          →
        </button>
      )}
    </aside>
  );
}
