"use client";

import { ChevronDown, ChevronUp, Search, X } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

const HIT = "page-search-hit";
const HIT_ACTIVE = "page-search-hit-active";

function clearMarks(root: HTMLElement) {
  root.querySelectorAll(`mark.${HIT}`).forEach((mark) => {
    const parent = mark.parentNode;
    if (!parent) return;
    while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
    parent.removeChild(mark);
    parent.normalize();
  });
}

function applyMarks(root: HTMLElement, query: string): HTMLElement[] {
  const q = query.trim();
  if (!q) return [];

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const targets: Text[] = [];
  let node = walker.nextNode();
  while (node) {
    const textNode = node as Text;
    const parent = textNode.parentElement;
    if (
      textNode.nodeValue &&
      parent &&
      parent.tagName !== "SCRIPT" &&
      parent.tagName !== "STYLE" &&
      !parent.closest(`mark.${HIT}`) &&
      textNode.nodeValue.toLowerCase().includes(q.toLowerCase())
    ) {
      targets.push(textNode);
    }
    node = walker.nextNode();
  }

  const marks: HTMLElement[] = [];
  const ql = q.toLowerCase();
  for (const textNode of targets) {
    const text = textNode.nodeValue || "";
    const lower = text.toLowerCase();
    const frag = document.createDocumentFragment();
    let last = 0;
    let idx = lower.indexOf(ql, last);
    while (idx !== -1) {
      if (idx > last) frag.appendChild(document.createTextNode(text.slice(last, idx)));
      const mark = document.createElement("mark");
      mark.className = HIT;
      mark.textContent = text.slice(idx, idx + q.length);
      frag.appendChild(mark);
      marks.push(mark);
      last = idx + q.length;
      idx = lower.indexOf(ql, last);
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
    textNode.parentNode?.replaceChild(frag, textNode);
  }
  return marks;
}

function getScrollParent(el: HTMLElement): HTMLElement | null {
  let parent = el.parentElement;
  while (parent) {
    const style = getComputedStyle(parent);
    const oy = style.overflowY;
    if (
      (oy === "auto" || oy === "scroll" || oy === "overlay") &&
      parent.scrollHeight > parent.clientHeight + 1
    ) {
      return parent;
    }
    parent = parent.parentElement;
  }
  return document.scrollingElement instanceof HTMLElement
    ? document.scrollingElement
    : document.documentElement;
}

function scrollMarkIntoView(mark: HTMLElement) {
  if (!mark.isConnected) return;

  const scroller = getScrollParent(mark);
  if (!scroller) {
    mark.scrollIntoView({ block: "center", inline: "nearest", behavior: "auto" });
    return;
  }

  const markRect = mark.getBoundingClientRect();
  const scrollerRect = scroller.getBoundingClientRect();
  const topPad = 24;
  const markCenter = markRect.top + markRect.height / 2;
  const viewCenter = scrollerRect.top + topPad + (scroller.clientHeight - topPad) / 2;
  const nextTop = scroller.scrollTop + (markCenter - viewCenter);

  scroller.scrollTo({
    top: Math.max(0, nextTop),
    behavior: "auto",
  });
}

function activateMatch(marks: HTMLElement[], index: number) {
  if (!marks.length) return;
  const i = ((index % marks.length) + marks.length) % marks.length;
  marks.forEach((m, idx) => m.classList.toggle(HIT_ACTIVE, idx === i));
  const active = marks[i];
  if (!active) return;
  scrollMarkIntoView(active);
  requestAnimationFrame(() => {
    if (active.isConnected) scrollMarkIntoView(active);
  });
}

export function usePageFind(contentRef: React.RefObject<HTMLElement | null>, contentKey: string) {
  const [open, setOpen] = useState(false);
  /** Text currently typed in the input — does not trigger search. */
  const [draft, setDraft] = useState("");
  /** Last query committed with Enter. */
  const [committed, setCommitted] = useState("");
  const [matchCount, setMatchCount] = useState(0);
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const marksRef = useRef<HTMLElement[]>([]);
  const activeIndexRef = useRef(0);
  const committedRef = useRef("");

  const keepInputFocus = () => {
    window.setTimeout(() => {
      inputRef.current?.focus({ preventScroll: true });
    }, 0);
  };

  const clearResults = useCallback(() => {
    marksRef.current = [];
    setMatchCount(0);
    setActiveIndex(0);
    activeIndexRef.current = 0;
    if (contentRef.current) clearMarks(contentRef.current);
  }, [contentRef]);

  const runSearch = useCallback(
    (raw: string, opts?: { scrollToFirst?: boolean }) => {
      const scrollToFirst = opts?.scrollToFirst ?? false;
      const root = contentRef.current;
      const term = raw.trim();
      if (!root) return;

      clearMarks(root);
      marksRef.current = [];

      if (!term) {
        committedRef.current = "";
        setCommitted("");
        setMatchCount(0);
        setActiveIndex(0);
        activeIndexRef.current = 0;
        return;
      }

      const next = applyMarks(root, term);
      marksRef.current = next;
      committedRef.current = term;
      setCommitted(term);
      setMatchCount(next.length);
      setActiveIndex(0);
      activeIndexRef.current = 0;
      if (scrollToFirst && next.length) activateMatch(next, 0);
      keepInputFocus();
    },
    [contentRef],
  );

  const close = () => {
    setOpen(false);
    setDraft("");
    setCommitted("");
    committedRef.current = "";
    clearResults();
  };

  const openFind = () => {
    setOpen(true);
    window.setTimeout(() => {
      inputRef.current?.focus({ preventScroll: true });
      inputRef.current?.select();
    }, 0);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "f") {
        e.preventDefault();
        setOpen(true);
        window.setTimeout(() => {
          inputRef.current?.focus({ preventScroll: true });
          inputRef.current?.select();
        }, 0);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Re-apply committed search when page content changes (e.g. navigate).
  useLayoutEffect(() => {
    if (!open || !committedRef.current) {
      clearResults();
      return;
    }
    runSearch(committedRef.current, { scrollToFirst: false });
  }, [contentKey, open, clearResults, runSearch]);

  const onDraftChange = (value: string) => {
    setDraft(value);
    // Typing alone must not search or scroll; drop stale highlights if query changed.
    if (value.trim() !== committedRef.current) {
      clearResults();
      setCommitted("");
      committedRef.current = "";
    }
  };

  const go = (delta: number) => {
    const marks = marksRef.current.filter((m) => m.isConnected);
    marksRef.current = marks;
    if (!marks.length) {
      setMatchCount(0);
      return;
    }
    const next = (activeIndexRef.current + delta + marks.length) % marks.length;
    activeIndexRef.current = next;
    setActiveIndex(next);
    activateMatch(marks, next);
    keepInputFocus();
  };

  /** Enter: search if draft is new; otherwise jump to next/prev match. */
  const onEnter = (shiftKey: boolean) => {
    const term = draft.trim();
    if (!term) {
      clearResults();
      setCommitted("");
      committedRef.current = "";
      return;
    }
    if (term !== committedRef.current || marksRef.current.length === 0) {
      runSearch(term, { scrollToFirst: true });
      return;
    }
    go(shiftKey ? -1 : 1);
  };

  return {
    open,
    openFind,
    close,
    draft,
    onDraftChange,
    committed,
    matchCount,
    activeIndex,
    go,
    onEnter,
    inputRef,
  };
}

export function PageFindBar({
  open,
  draft,
  onDraftChange,
  committed,
  matchCount,
  activeIndex,
  go,
  onEnter,
  close,
  inputRef,
}: {
  open: boolean;
  draft: string;
  onDraftChange: (v: string) => void;
  committed: string;
  matchCount: number;
  activeIndex: number;
  go: (delta: number) => void;
  onEnter: (shiftKey: boolean) => void;
  close: () => void;
  inputRef: React.RefObject<HTMLInputElement | null>;
}) {
  if (!open) return null;

  const searched = Boolean(committed.trim());
  const countLabel = !searched
    ? "Enter to search"
    : matchCount
      ? `${activeIndex + 1} / ${matchCount}`
      : "0 / 0";

  return (
    <div className="z-30 mb-3 flex shrink-0 flex-wrap items-center gap-2 rounded-xl border border-border bg-surface px-3 py-2.5 shadow-sm">
      <Search size={15} className="shrink-0 text-muted" />
      <input
        ref={inputRef}
        className="input h-8 min-w-[12rem] flex-1 py-1 text-sm"
        placeholder="Type, then press Enter…"
        value={draft}
        onChange={(e) => onDraftChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.preventDefault();
            close();
          } else if (e.key === "Enter") {
            e.preventDefault();
            onEnter(e.shiftKey);
          }
        }}
      />
      <span className="min-w-[6.5rem] text-center text-xs text-muted">{countLabel}</span>
      <button
        type="button"
        className="icon-button h-8 w-8"
        aria-label="Previous match"
        disabled={!matchCount}
        onClick={() => go(-1)}
      >
        <ChevronUp size={16} />
      </button>
      <button
        type="button"
        className="icon-button h-8 w-8"
        aria-label="Next match"
        disabled={!matchCount}
        onClick={() => go(1)}
      >
        <ChevronDown size={16} />
      </button>
      <button type="button" className="icon-button h-8 w-8" aria-label="Close find" onClick={close}>
        <X size={16} />
      </button>
    </div>
  );
}
