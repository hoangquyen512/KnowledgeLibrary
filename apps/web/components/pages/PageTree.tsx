"use client";

import { ChevronDown, ChevronRight, FileText, Plus } from "lucide-react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { clientApi } from "@/lib/api";
import type { PageSearchHit, PageTreeNode } from "@/lib/pages";

const STORAGE_KEY = (spaceId: string) => `kl-page-tree-expanded:${spaceId}`;

function loadExpanded(spaceId: string): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = localStorage.getItem(STORAGE_KEY(spaceId));
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch {
    return new Set();
  }
}

function saveExpanded(spaceId: string, set: Set<string>) {
  localStorage.setItem(STORAGE_KEY(spaceId), JSON.stringify([...set]));
}

export function PageTree({
  spaceId,
  sourceId,
  selectedId,
  onSelect,
  onCreateChild,
  canManage,
  pageHref,
  compact = false,
}: {
  spaceId: string;
  sourceId: string;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onCreateChild?: (parentId: string | null) => void;
  canManage?: boolean;
  /** When set, page titles use Link for prefetch. */
  pageHref?: (id: string) => string;
  compact?: boolean;
}) {
  const [expanded, setExpanded] = useState<Set<string>>(() => loadExpanded(spaceId));
  const [childrenMap, setChildrenMap] = useState<Record<string, PageTreeNode[]>>({});
  const [loadingIds, setLoadingIds] = useState<Set<string>>(new Set());
  const inFlight = useRef<Set<string>>(new Set());

  const treeQuery = (parentId?: string) => {
    const params = new URLSearchParams({ source_id: sourceId });
    if (parentId) params.set("parent_id", parentId);
    return `/spaces/${spaceId}/pages/tree?${params.toString()}`;
  };

  const { data: roots = [], isLoading } = useQuery({
    queryKey: ["page-tree", spaceId, sourceId, "root"],
    queryFn: () => clientApi<PageTreeNode[]>(treeQuery()),
    enabled: !!sourceId,
  });

  useEffect(() => {
    setExpanded(loadExpanded(spaceId));
    setChildrenMap({});
    setLoadingIds(new Set());
    inFlight.current = new Set();
  }, [spaceId, sourceId]);

  useEffect(() => {
    saveExpanded(spaceId, expanded);
  }, [spaceId, expanded]);

  const loadChildren = useCallback(
    async (parentId: string, force = false) => {
      if (!force) {
        if (inFlight.current.has(parentId)) return;
        let cached = false;
        setChildrenMap((m) => {
          cached = m[parentId] !== undefined;
          return m;
        });
        if (cached) return;
      }
      inFlight.current.add(parentId);
      setLoadingIds((s) => new Set(s).add(parentId));
      try {
        const kids = await clientApi<PageTreeNode[]>(treeQuery(parentId));
        setChildrenMap((m) => ({ ...m, [parentId]: kids }));
      } catch {
        setChildrenMap((m) => ({ ...m, [parentId]: [] }));
      } finally {
        inFlight.current.delete(parentId);
        setLoadingIds((s) => {
          const next = new Set(s);
          next.delete(parentId);
          return next;
        });
      }
    },
    // treeQuery closes over spaceId/sourceId
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [spaceId, sourceId],
  );

  // Re-fetch children for expanded nodes after localStorage restore / space switch.
  useEffect(() => {
    const nodes = [...roots, ...Object.values(childrenMap).flat()];
    for (const node of nodes) {
      if (
        expanded.has(node.id) &&
        node.has_children &&
        childrenMap[node.id] === undefined &&
        !inFlight.current.has(node.id)
      ) {
        void loadChildren(node.id);
      }
    }
  }, [roots, expanded, childrenMap, loadChildren]);

  const toggle = async (node: PageTreeNode) => {
    const next = new Set(expanded);
    if (next.has(node.id)) {
      next.delete(node.id);
    } else {
      next.add(node.id);
      if (node.has_children) await loadChildren(node.id);
    }
    setExpanded(next);
  };

  const expandPath = useCallback(
    async (ancestorIds: string[]) => {
      const next = new Set(loadExpanded(spaceId));
      for (const id of ancestorIds) {
        next.add(id);
        try {
          const kids = await clientApi<PageTreeNode[]>(treeQuery(id));
          setChildrenMap((m) => ({ ...m, [id]: kids }));
        } catch {
          setChildrenMap((m) => ({ ...m, [id]: [] }));
        }
      }
      setExpanded(next);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [spaceId, sourceId],
  );

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail as { ancestors?: string[] } | undefined;
      if (detail?.ancestors?.length) void expandPath(detail.ancestors);
    };
    window.addEventListener("kl-expand-page-path", handler);
    return () => window.removeEventListener("kl-expand-page-path", handler);
  }, [expandPath]);

  const renderNodes = (nodes: PageTreeNode[], depth: number) => (
    <ul
      className={
        compact
          ? "space-y-0.5"
          : depth === 0
            ? "mt-1 space-y-0.5"
            : "ml-3 space-y-0.5 border-l border-border pl-2"
      }
    >
      {nodes.map((node) => {
        const open = expanded.has(node.id);
        const active = selectedId === node.id;
        const kids = childrenMap[node.id];
        const loading = loadingIds.has(node.id);
        const titleLink = (
          <>
            <FileText size={compact ? 16 : 14} className="shrink-0 opacity-70" />
            {compact ? null : <span className="truncate">{node.title}</span>}
          </>
        );
        return (
          <li key={node.id}>
            <div
              className={`group flex items-center rounded-lg text-sm ${
                compact ? "justify-center" : "gap-0.5 pr-1"
              } ${
                active ? "bg-blue-50 text-primary dark:bg-blue-950/40" : "hover:bg-surface-muted"
              }`}
            >
              {compact ? null : node.has_children ? (
                <button
                  type="button"
                  className="shrink-0 rounded p-1 text-muted hover:text-foreground"
                  aria-label={open ? "Collapse" : "Expand"}
                  onClick={() => void toggle(node)}
                >
                  {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </button>
              ) : (
                <span className="inline-block w-6 shrink-0" />
              )}
              {pageHref ? (
                <Link
                  href={pageHref(node.id)}
                  title={node.title}
                  prefetch
                  data-nav-silent
                  onClick={() => onSelect(node.id)}
                  className={`flex items-center text-left ${
                    compact
                      ? "h-9 w-full items-center justify-center"
                      : "min-w-0 flex-1 gap-1.5 py-1.5"
                  }`}
                >
                  {titleLink}
                </Link>
              ) : (
                <button
                  type="button"
                  title={node.title}
                  onClick={() => onSelect(node.id)}
                  className={`flex items-center text-left ${
                    compact
                      ? "h-9 w-full items-center justify-center"
                      : "min-w-0 flex-1 gap-1.5 py-1.5"
                  }`}
                >
                  {titleLink}
                </button>
              )}
              {compact || !canManage || !onCreateChild ? null : (
                <button
                  type="button"
                  title="Create child page"
                  className="icon-button opacity-0 group-hover:opacity-100"
                  onClick={() => onCreateChild(node.id)}
                >
                  <Plus size={14} />
                </button>
              )}
            </div>
            {open && node.has_children ? (
              kids !== undefined ? (
                kids.length > 0 ? (
                  renderNodes(kids, depth + 1)
                ) : compact ? null : (
                  <p className="ml-8 py-1 text-xs text-muted">No child pages</p>
                )
              ) : compact ? null : (
                <p className="ml-8 py-1 text-xs text-muted">{loading ? "Loading…" : "Loading…"}</p>
              )
            ) : null}
          </li>
        );
      })}
    </ul>
  );

  if (isLoading) {
    return compact ? null : <p className="mt-3 text-sm text-muted">Loading pages…</p>;
  }
  if (roots.length === 0) {
    if (compact) return null;
    return (
      <div className="mt-4 rounded-xl border border-dashed border-border p-4 text-sm text-muted">
        <p>No pages yet.</p>
        {canManage && onCreateChild ? (
          <button
            type="button"
            className="primary-button mt-3 text-xs"
            onClick={() => onCreateChild(null)}
          >
            <Plus size={14} /> Create Page
          </button>
        ) : null}
      </div>
    );
  }

  return renderNodes(roots, 0);
}

export function PageTreeSearch({
  spaceId,
  sourceId,
  onPick,
}: {
  spaceId: string;
  sourceId: string;
  onPick: (id: string) => void;
}) {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 300);
    return () => clearTimeout(t);
  }, [q]);

  const {
    data: hits = [],
    isFetching,
    isError,
    error,
  } = useQuery({
    queryKey: ["page-search", spaceId, sourceId, debounced],
    queryFn: () =>
      clientApi<PageSearchHit[]>(
        `/spaces/${spaceId}/pages/search?q=${encodeURIComponent(debounced)}&source_id=${encodeURIComponent(sourceId)}`,
      ),
    enabled: debounced.length >= 2 && !!sourceId,
  });

  const showDropdown = open && debounced.length >= 2;

  return (
    <div className="relative">
      <input
        className="input w-full text-sm"
        placeholder="Search pages & content…"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => {
          window.setTimeout(() => setOpen(false), 150);
        }}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            setQ("");
            setOpen(false);
          }
          if (e.key === "Enter" && hits[0]) {
            onPick(hits[0].id);
            setQ("");
            setOpen(false);
          }
        }}
      />
      {showDropdown ? (
        <ul className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-xl border border-border bg-surface shadow-lg">
          {isFetching ? (
            <li className="px-3 py-2 text-xs text-muted">Searching…</li>
          ) : isError ? (
            <li className="px-3 py-2 text-xs text-rose-600">
              {(error as Error)?.message || "Search failed"}
            </li>
          ) : hits.length === 0 ? (
            <li className="px-3 py-2 text-xs text-muted">No pages match “{debounced}”</li>
          ) : (
            hits.map((h) => (
              <li key={h.id}>
                <button
                  type="button"
                  className="w-full px-3 py-2 text-left text-sm hover:bg-surface-muted"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => {
                    onPick(h.id);
                    setQ("");
                    setOpen(false);
                  }}
                >
                  <p className="font-medium">{h.title}</p>
                  {h.snippet ? (
                    <p className="mt-0.5 line-clamp-2 text-[11px] text-muted">{h.snippet}</p>
                  ) : (
                    <p className="truncate text-[11px] text-muted">{h.path.join(" / ")}</p>
                  )}
                  {h.match_field === "content" ? (
                    <p className="mt-0.5 text-[10px] font-medium uppercase tracking-wide text-primary">
                      In content
                    </p>
                  ) : null}
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  );
}
