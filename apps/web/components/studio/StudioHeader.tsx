"use client";

import { ChevronDown, Clock, LayoutTemplate, Network, Sparkles } from "lucide-react";
import { useRef, useState } from "react";
import type { StudioArtifact } from "@/lib/studio";
import { useClickOutside } from "@/lib/use-click-outside";
import { studio } from "./strings";

export function StudioTopBar({
  filterType,
  onFilterType,
  artifacts,
  onSelectArtifact,
}: {
  filterType: "PRESENTATION" | "MINDMAP";
  onFilterType: (t: "PRESENTATION" | "MINDMAP") => void;
  artifacts: StudioArtifact[];
  onSelectArtifact: (id: string) => void;
}) {
  const [recentOpen, setRecentOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useClickOutside(ref, recentOpen, () => setRecentOpen(false));

  const filtered = artifacts.filter((a) => a.artifact_type === filterType);

  return (
    <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border bg-surface px-4 py-2.5 sm:px-5">
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex shrink-0 items-center gap-2">
          <Sparkles size={16} className="text-primary" />
          <span className="text-sm font-semibold text-foreground">{studio.pageTitle}</span>
        </div>
        <div className="flex rounded-lg border border-border bg-surface-muted p-0.5">
          <button
            type="button"
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition ${
              filterType === "PRESENTATION"
                ? "bg-surface text-primary shadow-sm"
                : "text-muted hover:text-foreground"
            }`}
            onClick={() => onFilterType("PRESENTATION")}
          >
            <LayoutTemplate size={14} />
            {studio.presentations}
          </button>
          <button
            type="button"
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition ${
              filterType === "MINDMAP"
                ? "bg-surface text-primary shadow-sm"
                : "text-muted hover:text-foreground"
            }`}
            onClick={() => onFilterType("MINDMAP")}
          >
            <Network size={14} />
            {studio.mindmaps}
          </button>
        </div>
      </div>

      <div className="relative shrink-0" ref={ref}>
        <button
          type="button"
          className="secondary-button h-8 px-2.5 text-xs"
          onClick={() => setRecentOpen((v) => !v)}
        >
          <Clock size={14} />
          {studio.recent}
          <ChevronDown size={14} />
        </button>
        {recentOpen ? (
          <div className="absolute right-0 z-30 mt-1 w-64 rounded-xl border border-border bg-surface p-1 shadow-lg">
            {filtered.length === 0 ? (
              <p className="px-3 py-2 text-xs text-muted">{studio.noArtifacts}</p>
            ) : (
              filtered.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  className="flex w-full flex-col rounded-lg px-3 py-2 text-left text-sm hover:bg-surface-muted"
                  onClick={() => {
                    onSelectArtifact(a.id);
                    setRecentOpen(false);
                  }}
                >
                  <span className="truncate font-medium">{a.title}</span>
                  <span className="text-[10px] capitalize text-muted">{a.status.toLowerCase()}</span>
                </button>
              ))
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function StudioPageHeader({
  filterType,
  onSaveDraft,
  onCreate,
  createDisabled,
  createPending,
}: {
  filterType: "PRESENTATION" | "MINDMAP";
  onSaveDraft: () => void;
  onCreate: () => void;
  createDisabled: boolean;
  createPending: boolean;
}) {
  const isMindmap = filterType === "MINDMAP";
  return (
    <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3 sm:px-5">
      <div className="min-w-0">
        <h1 className="text-lg font-semibold tracking-tight text-foreground">
          {isMindmap ? studio.createMindmap : studio.createPresentation}
        </h1>
        <p className="mt-0.5 text-xs text-muted sm:text-sm">
          {isMindmap ? studio.createMindmapSubtitle : studio.createPresentationSubtitle}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="secondary-button h-9 text-xs" onClick={onSaveDraft}>
          {studio.saveDraft}
        </button>
        <button
          type="button"
          className="primary-button h-9 text-xs"
          disabled={createDisabled || createPending}
          onClick={onCreate}
        >
          <Sparkles size={14} />
          {isMindmap ? studio.createMindmap : studio.createPresentation}
        </button>
      </div>
    </div>
  );
}
