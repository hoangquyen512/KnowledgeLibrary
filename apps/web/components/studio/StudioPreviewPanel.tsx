"use client";

import {
  ChevronDown,
  Info,
  LayoutList,
  Maximize2,
  Minus,
  Network,
  Plus,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { StudioArtifact, StudioMindmapNode, StudioSlide } from "@/lib/studio";
import { isStudioActive } from "@/lib/studio";
import { MindmapViewer } from "./MindmapViewer";
import { PresentationViewer } from "./PresentationViewer";
import { StudioMindmapPlaceholder, StudioPresentationPlaceholder } from "./StudioMindmapPlaceholder";
import { StudioProgress, StudioWarnings } from "./StudioProgress";
import type { StudioSourceRef } from "@/lib/studio";
import { studio } from "./strings";

export function StudioPreviewPanel({
  filterType,
  focusPrompt,
  artifact,
  localSlides,
  localNodes,
  workspaceId,
  fallbackSpaceId,
  modelName,
  onChangeSlides,
  onChangeNodes,
  onRegenerateSlide,
  onSelectSource,
  onToggleCollapse,
}: {
  filterType: "PRESENTATION" | "MINDMAP";
  focusPrompt: string;
  artifact: StudioArtifact | null | undefined;
  localSlides: StudioSlide[] | null;
  localNodes: StudioMindmapNode[] | null;
  workspaceId: string;
  fallbackSpaceId: string | null;
  modelName: string;
  onChangeSlides: (slides: StudioSlide[]) => void;
  onChangeNodes: (nodes: StudioMindmapNode[]) => void;
  onRegenerateSlide: (slideId: string) => void;
  onSelectSource: (source: StudioSourceRef) => void;
  onToggleCollapse: (nodeId: string) => void;
}) {
  const [zoom, setZoom] = useState(100);
  const [viewMode, setViewMode] = useState<"graph" | "list">("graph");
  const [fullscreen, setFullscreen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  const isMindmap = filterType === "MINDMAP";
  const showResult = artifact?.status === "COMPLETED";
  const showProgress = artifact && isStudioActive(artifact);
  const showPlaceholder = !artifact || (!showResult && !showProgress && artifact.status !== "FAILED");

  const centerLabel =
    focusPrompt.trim() ||
    artifact?.focus_prompt?.trim() ||
    artifact?.title ||
    (isMindmap ? "Mind map" : "Presentation");

  useEffect(() => {
    if (!fullscreen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setFullscreen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [fullscreen]);

  const toggleFullscreen = useCallback(async () => {
    if (!panelRef.current) return;
    if (!document.fullscreenElement) {
      await panelRef.current.requestFullscreen?.();
      setFullscreen(true);
    } else {
      await document.exitFullscreen?.();
      setFullscreen(false);
    }
  }, []);

  useEffect(() => {
    const onFs = () => setFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", onFs);
    return () => document.removeEventListener("fullscreenchange", onFs);
  }, []);

  const hint = isMindmap ? studio.previewMindmapHint : studio.previewPresentationHint;
  const footer = isMindmap ? studio.previewFooterMindmap : studio.previewFooterPresentation;

  return (
    <div
      ref={panelRef}
      className={`flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-surface-muted/30 ${
        fullscreen ? "fixed inset-0 z-50 bg-background" : ""
      }`}
    >
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-2.5 sm:px-5">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-foreground">{studio.preview}</h2>
          <p className="truncate text-[11px] text-muted">{hint}</p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-1">
          {isMindmap ? (
            <>
              <button
                type="button"
                title="Graph view"
                className={`icon-button h-8 w-8 ${viewMode === "graph" ? "bg-surface text-primary" : ""}`}
                onClick={() => setViewMode("graph")}
              >
                <Network size={15} />
              </button>
              <button
                type="button"
                title="List view"
                className={`icon-button h-8 w-8 ${viewMode === "list" ? "bg-surface text-primary" : ""}`}
                onClick={() => setViewMode("list")}
              >
                <LayoutList size={15} />
              </button>
            </>
          ) : null}
          <button
            type="button"
            className="icon-button h-8 w-8"
            onClick={() => setZoom((z) => Math.max(50, z - 10))}
            aria-label={studio.zoomOut}
          >
            <Minus size={15} />
          </button>
          <span className="min-w-[3rem] text-center text-xs font-medium text-muted">{zoom}%</span>
          <button
            type="button"
            className="icon-button h-8 w-8"
            onClick={() => setZoom((z) => Math.min(150, z + 10))}
            aria-label={studio.zoomIn}
          >
            <Plus size={15} />
          </button>
          <button
            type="button"
            className="secondary-button h-8 px-2 text-xs"
            onClick={() => void toggleFullscreen()}
          >
            <Maximize2 size={14} />
            {studio.fullscreen}
          </button>
        </div>
      </div>

      <div className="relative min-h-0 flex-1 overflow-auto p-3 sm:p-4">
        <div className="mx-auto flex min-h-full items-center justify-center rounded-2xl border border-border bg-surface p-4">
          <div
            className="w-full origin-center transition-transform"
            style={{ transform: `scale(${zoom / 100})` }}
          >
            {showProgress ? (
              <div className="flex min-h-[280px] flex-col items-center justify-center p-6">
                <StudioProgress stage={artifact!.stage} percent={artifact!.progress_percent} />
              </div>
            ) : null}

            {artifact?.status === "FAILED" ? (
              <div className="flex min-h-[280px] items-center justify-center p-6">
                <p className="max-w-md rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-100">
                  {artifact.error_message || "Generation failed."}
                </p>
              </div>
            ) : null}

            {showResult && isMindmap ? (
              <div className="min-h-[320px] p-2">
                {viewMode === "graph" ? (
                  <MindmapViewer
                    nodes={localNodes || []}
                    onSelectSource={onSelectSource}
                    onToggleCollapse={onToggleCollapse}
                  />
                ) : (
                  <MindmapListView nodes={localNodes || []} />
                )}
              </div>
            ) : null}

            {showResult && !isMindmap ? (
              <div className="p-2">
                <PresentationViewer
                  slides={localSlides || []}
                  workspaceId={workspaceId}
                  fallbackSpaceId={fallbackSpaceId}
                  onChange={onChangeSlides}
                  onRegenerateSlide={onRegenerateSlide}
                  onSelectSource={onSelectSource}
                />
              </div>
            ) : null}

            {showPlaceholder ? (
              <div className="flex min-h-[280px] items-center justify-center">
                {isMindmap ? (
                  <StudioMindmapPlaceholder centerLabel={centerLabel} />
                ) : (
                  <StudioPresentationPlaceholder title={centerLabel} />
                )}
              </div>
            ) : null}
          </div>
        </div>

        {artifact && showResult ? (
          <div className="pointer-events-none absolute left-5 right-5 top-5 max-w-lg">
            <div className="pointer-events-auto">
              <StudioWarnings warnings={artifact.warning_json} />
            </div>
          </div>
        ) : null}
      </div>

      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-t border-border px-4 py-2 sm:px-5">
        <p className="flex min-w-0 items-center gap-1.5 text-[11px] text-muted">
          <Info size={13} className="shrink-0 text-primary/80" />
          <span className="truncate">{footer}</span>
        </p>
        <div className="flex shrink-0 items-center gap-1 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-[11px] text-muted">
          <span>{studio.model}:</span>
          <span className="font-medium text-foreground">{modelName}</span>
          <ChevronDown size={12} className="opacity-50" />
        </div>
      </div>
    </div>
  );
}

function MindmapListView({ nodes }: { nodes: StudioMindmapNode[] }) {
  const roots = nodes.filter((n) => !n.parent_id);
  const childrenOf = (id: string) => nodes.filter((n) => n.parent_id === id);

  function Branch({ node, depth }: { node: StudioMindmapNode; depth: number }) {
    const kids = childrenOf(node.id);
    return (
      <li className="text-sm">
        <span
          className="font-medium text-foreground"
          style={{ paddingLeft: depth * 16 }}
        >
          {node.label}
        </span>
        {kids.length ? (
          <ul className="mt-1 space-y-1 border-l border-border pl-3">
            {kids.map((k) => (
              <Branch key={k.id} node={k} depth={depth + 1} />
            ))}
          </ul>
        ) : null}
      </li>
    );
  }

  if (!nodes.length) {
    return <p className="p-6 text-sm text-muted">{studio.emptyMindmap}</p>;
  }

  return (
    <ul className="space-y-2 p-4">
      {roots.map((r) => (
        <Branch key={r.id} node={r} depth={0} />
      ))}
    </ul>
  );
}
