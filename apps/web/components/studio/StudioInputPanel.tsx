"use client";

import { Check, ChevronDown, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { SpaceIcon } from "@/components/spaces/SpaceIcon";
import type { Space, Workspace } from "@/lib/api";
import type { PageTreeNode } from "@/lib/pages";
import { DocumentPicker } from "./DocumentPicker";
import { studio } from "./strings";

const FOCUS_MAX = 500;

export function StudioInputPanel({
  step,
  filterType,
  workspaces,
  workspaceId,
  onWorkspaceChange,
  spaces,
  selectedSpaces,
  onToggleSpace,
  pageTrees,
  selectedDocs,
  onToggleDoc,
  onSelectAllDocs,
  onClearDocs,
  focusPrompt,
  onFocusChange,
  onNext,
  onBack,
  onGenerate,
  canProceed,
  geminiConnected,
  lockWorkspace = false,
}: {
  step: 1 | 2 | 3;
  filterType: "PRESENTATION" | "MINDMAP";
  workspaces: Workspace[];
  workspaceId: string;
  onWorkspaceChange: (id: string) => void;
  spaces: Space[];
  selectedSpaces: string[];
  onToggleSpace: (id: string) => void;
  pageTrees?: Record<string, PageTreeNode[]>;
  selectedDocs: string[];
  onToggleDoc: (id: string) => void;
  onSelectAllDocs: () => void;
  onClearDocs: () => void;
  focusPrompt: string;
  onFocusChange: (v: string) => void;
  onNext: () => void;
  onBack: () => void;
  onGenerate: () => void;
  canProceed: boolean;
  geminiConnected: boolean;
  lockWorkspace?: boolean;
}) {
  const [spaceQ, setSpaceQ] = useState("");
  const suggestions =
    filterType === "MINDMAP"
      ? studio.focusSuggestionsMindmap
      : studio.focusSuggestionsPresentation;

  const filteredSpaces = useMemo(() => {
    const q = spaceQ.trim().toLowerCase();
    if (!q) return spaces;
    return spaces.filter(
      (s) => s.name.toLowerCase().includes(q) || s.slug.toLowerCase().includes(q),
    );
  }, [spaces, spaceQ]);

  const selectedSpaceObjects = spaces.filter((s) => selectedSpaces.includes(s.id));

  if (step === 2) {
    const ws = workspaces.find((w) => w.id === workspaceId);
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain px-4 py-4">
          <h2 className="text-sm font-semibold text-foreground">{studio.reviewTitle}</h2>
          <dl className="space-y-3 text-sm">
            <div className="rounded-xl border border-border bg-surface-muted/50 p-3">
              <dt className="text-xs font-medium text-muted">{studio.reviewWorkspace}</dt>
              <dd className="mt-1 font-medium">{ws?.name || "—"}</dd>
            </div>
            <div className="rounded-xl border border-border bg-surface-muted/50 p-3">
              <dt className="text-xs font-medium text-muted">{studio.reviewSpaces}</dt>
              <dd className="mt-2 space-y-2">
                {selectedSpaceObjects.map((s) => (
                  <div key={s.id} className="flex items-center gap-2 text-sm">
                    <SpaceIcon iconKey={s.icon_key} accent={s.accent_key} size={14} />
                    <span className="font-medium">{s.name}</span>
                    <span className="text-xs text-muted">
                      ({studio.pagesAndSources(s.document_count, s.source_count)})
                    </span>
                  </div>
                ))}
              </dd>
            </div>
            <div className="rounded-xl border border-border bg-surface-muted/50 p-3">
              <dt className="text-xs font-medium text-muted">{studio.reviewFocus}</dt>
              <dd className="mt-1 text-sm">{focusPrompt.trim() || studio.reviewNone}</dd>
            </div>
          </dl>
        </div>
        <div className="flex shrink-0 gap-2 border-t border-border px-4 py-3">
          <button type="button" className="secondary-button flex-1 text-xs" onClick={onBack}>
            {studio.back}
          </button>
          <button
            type="button"
            className="primary-button flex-1 text-xs"
            disabled={!canProceed}
            onClick={onGenerate}
          >
            {studio.generate}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain px-4 py-4">
        {!geminiConnected ? (
          <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-100">
            {studio.connectGemini}{" "}
            <a href="/app/settings/ai" className="font-medium text-primary hover:underline">
              AI Settings
            </a>
          </p>
        ) : null}

        <section>
          <label className="mb-1.5 block text-xs font-semibold text-foreground">
            {studio.selectWorkspace}
          </label>
          <div className="relative">
            <select
              className="input appearance-none pr-8 text-sm font-medium"
              value={workspaceId}
              disabled={lockWorkspace}
              onChange={(e) => onWorkspaceChange(e.target.value)}
            >
              {workspaces.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
            <ChevronDown
              size={14}
              className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-muted"
            />
          </div>
        </section>

        <section>
          <label className="mb-1.5 block text-xs font-semibold text-foreground">
            {studio.selectSpaces}
          </label>
          <div className="relative mb-2">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
            <input
              className="input h-9 pl-8 text-xs"
              placeholder={studio.searchSpaces}
              value={spaceQ}
              onChange={(e) => setSpaceQ(e.target.value)}
            />
          </div>
          <ul className="space-y-1.5">
            {filteredSpaces.map((s) => {
              const on = selectedSpaces.includes(s.id);
              return (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => onToggleSpace(s.id)}
                    className={`flex w-full items-center gap-2.5 rounded-xl border px-2.5 py-2 text-left transition ${
                      on
                        ? "border-primary/40 bg-blue-50/80 dark:bg-blue-950/30"
                        : "border-border bg-surface hover:bg-surface-muted"
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
                    <SpaceIcon iconKey={s.icon_key} accent={s.accent_key} size={14} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{s.name}</span>
                      <span className="block text-[11px] text-muted">
                        {studio.pagesAndSources(s.document_count, s.source_count)}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>

        {selectedSpaces.length > 0 && pageTrees ? (
          <section>
            <DocumentPicker
              trees={pageTrees}
              selected={selectedDocs}
              onToggle={onToggleDoc}
              onSelectAll={onSelectAllDocs}
              onClear={onClearDocs}
            />
          </section>
        ) : null}

        <section>
          <label className="mb-0.5 block text-xs font-semibold text-foreground">
            {studio.focusTopic}
          </label>
          <p className="mb-2 text-[11px] leading-relaxed text-muted">
            {filterType === "MINDMAP"
              ? studio.focusTopicHint
              : studio.focusTopicHintPresentation}
          </p>
          <div className="relative">
            <textarea
              className="input min-h-[96px] resize-none pb-6 text-sm"
              placeholder={studio.focusPlaceholder}
              value={focusPrompt}
              onChange={(e) => onFocusChange(e.target.value.slice(0, FOCUS_MAX))}
              maxLength={FOCUS_MAX}
            />
            <span className="pointer-events-none absolute bottom-2 right-2 text-[10px] text-muted">
              {focusPrompt.length} / {FOCUS_MAX}
            </span>
          </div>
          <p className="mt-2 text-[11px] font-medium text-muted">{studio.suggestedTopics}</p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {suggestions.map((chip) => (
              <button
                key={chip}
                type="button"
                className="rounded-full border border-border bg-surface px-2.5 py-1 text-[11px] font-medium text-foreground transition hover:border-primary/40 hover:bg-blue-50/50 dark:hover:bg-blue-950/20"
                onClick={() => onFocusChange(chip)}
              >
                {chip}
              </button>
            ))}
          </div>
        </section>
      </div>

      <div className="shrink-0 border-t border-border px-4 py-3">
        <button
          type="button"
          className="primary-button w-full text-sm"
          disabled={!canProceed || selectedSpaces.length === 0}
          onClick={onNext}
        >
          {studio.nextReview} &gt;
        </button>
      </div>
    </div>
  );
}
