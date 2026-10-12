"use client";

import { ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import type { StudioSlide, StudioSourceRef } from "@/lib/studio";
import { studio } from "./strings";

export function PresentationViewer({
  slides,
  workspaceId,
  fallbackSpaceId,
  onChange,
  onRegenerateSlide,
  onSelectSource,
}: {
  slides: StudioSlide[];
  workspaceId: string;
  fallbackSpaceId?: string | null;
  onChange: (slides: StudioSlide[]) => void;
  onRegenerateSlide: (slideId: string) => void;
  onSelectSource: (source: StudioSourceRef) => void;
}) {
  const [index, setIndex] = useState(0);
  const slide = slides[index];

  useEffect(() => {
    if (index >= slides.length) setIndex(Math.max(0, slides.length - 1));
  }, [slides.length, index]);

  if (!slides.length) {
    return <p className="text-sm text-muted">{studio.emptyPresentation}</p>;
  }

  const updateSlide = (patch: Partial<StudioSlide>) => {
    const next = slides.map((s, i) => (i === index ? { ...s, ...patch } : s));
    onChange(next);
  };

  const updateBullet = (bi: number, value: string) => {
    const bullets = [...(slide.bullets || [])];
    bullets[bi] = value;
    updateSlide({ bullets });
  };

  const addBullet = () => {
    if ((slide.bullets?.length || 0) >= 6) return;
    updateSlide({ bullets: [...(slide.bullets || []), ""] });
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted">{studio.slideOf(index + 1, slides.length)}</p>
        <div className="flex items-center gap-1">
          <button
            type="button"
            className="icon-button"
            disabled={index <= 0}
            onClick={() => setIndex((i) => Math.max(0, i - 1))}
            aria-label="Previous slide"
          >
            <ChevronLeft size={18} />
          </button>
          <button
            type="button"
            className="icon-button"
            disabled={index >= slides.length - 1}
            onClick={() => setIndex((i) => Math.min(slides.length - 1, i + 1))}
            aria-label="Next slide"
          >
            <ChevronRight size={18} />
          </button>
          <button
            type="button"
            className="secondary-button h-8 px-2 text-xs"
            onClick={() => onRegenerateSlide(slide.id)}
          >
            <RefreshCw size={14} />
            {studio.regenerateSlide}
          </button>
        </div>
      </div>

      <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
        <input
          className="input mb-4 text-lg font-semibold"
          value={slide.title}
          onChange={(e) => updateSlide({ title: e.target.value })}
        />
        <ul className="space-y-2">
          {(slide.bullets || []).map((bullet, bi) => (
            <li key={bi} className="flex gap-2">
              <span className="mt-2 text-primary">•</span>
              <input
                className="input flex-1 text-sm"
                value={bullet}
                onChange={(e) => updateBullet(bi, e.target.value)}
              />
            </li>
          ))}
        </ul>
        {(slide.bullets?.length || 0) < 6 ? (
          <button type="button" className="mt-3 text-xs font-medium text-primary hover:underline" onClick={addBullet}>
            + Add bullet
          </button>
        ) : null}
        <label className="mt-4 block text-xs font-medium text-muted">Speaker notes</label>
        <textarea
          className="input mt-1 min-h-[72px] text-sm"
          value={slide.notes || ""}
          onChange={(e) => updateSlide({ notes: e.target.value })}
        />
        {slide.source_refs?.length ? (
          <div className="mt-4 flex flex-wrap gap-1.5">
            {slide.source_refs.map((ref, ri) => (
              <button
                key={`${ref.document_id}-${ri}`}
                type="button"
                className="rounded-full border border-border bg-surface-muted px-2 py-0.5 text-[11px] hover:border-primary/40"
                onClick={() => onSelectSource({ ...ref, space_id: ref.space_id || fallbackSpaceId || null })}
              >
                {ref.title?.slice(0, 40) || "Source"}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <div className="flex gap-1 overflow-x-auto pb-1">
        {slides.map((s, i) => (
          <button
            key={s.id}
            type="button"
            onClick={() => setIndex(i)}
            className={`min-w-[88px] shrink-0 rounded-lg border px-2 py-2 text-left text-[11px] transition ${
              i === index
                ? "border-primary bg-blue-50 dark:bg-blue-950/30"
                : "border-border bg-surface hover:bg-surface-muted"
            }`}
          >
            <span className="line-clamp-2 font-medium">{s.title || `Slide ${i + 1}`}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
