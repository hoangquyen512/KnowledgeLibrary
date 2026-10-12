"use client";

import { useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { Archive, ChevronLeft, ChevronRight, Plus, Star } from "lucide-react";
import Link from "next/link";
import { useAppRouter } from "@/components/navigation-progress";
import { useEffect, useRef, useState } from "react";
import { ArchivedPagesPanel } from "@/components/pages/ArchivedPagesPanel";
import { CreatePageDialog } from "@/components/pages/CreatePageDialog";
import { PageContentView } from "@/components/pages/PageContent";
import { PageTree, PageTreeSearch } from "@/components/pages/PageTree";
import { clientApi, type Space } from "@/lib/api";
import type { SourceRow } from "@/lib/import-status";
import type { PageDetail, PageTreeNode } from "@/lib/pages";
import { sourceTypeLabel } from "@/lib/sources";

const PAGE_TREE_COLLAPSED_KEY = "kl-page-tree-collapsed";
const PAGE_TREE_WIDTH_KEY = "kl-page-tree-width";
const PAGE_TREE_EXPANDED_WIDTH_KEY = "kl-page-tree-expanded-width";
const PAGE_SOURCE_KEY = (spaceId: string) => `kl-page-source:${spaceId}`;
const PAGE_TREE_DEFAULT_WIDTH = 300;
const PAGE_TREE_ICON_WIDTH = 56;
const PAGE_TREE_COMPACT_WIDTH = 160;
const PAGE_TREE_MIN_WIDTH = PAGE_TREE_ICON_WIDTH;
const PAGE_TREE_MAX_WIDTH = 640;

function clampTreeWidth(width: number) {
  const viewportMax =
    typeof window === "undefined" ? PAGE_TREE_MAX_WIDTH : Math.max(PAGE_TREE_MIN_WIDTH, window.innerWidth - 360);
  return Math.min(PAGE_TREE_MAX_WIDTH, viewportMax, Math.max(PAGE_TREE_MIN_WIDTH, Math.round(width)));
}

function readStoredSourceId(spaceId: string): string | null {
  try {
    return localStorage.getItem(PAGE_SOURCE_KEY(spaceId));
  } catch {
    return null;
  }
}

function writeStoredSourceId(spaceId: string, sourceId: string) {
  try {
    localStorage.setItem(PAGE_SOURCE_KEY(spaceId), sourceId);
  } catch {
    /* ignore */
  }
}

function PageTreeResizeGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden className={className}>
      <path d="M3 12 9.2 6.8v10.4L3 12Z" />
      <rect x="10.2" y="4.5" width="2.4" height="15" rx="1.2" />
      <rect x="14.4" y="4.5" width="2.4" height="15" rx="1.2" />
      <path d="M21 12 14.8 6.8v10.4L21 12Z" />
    </svg>
  );
}

export function SpacePagesShell({
  workspaceId,
  spaceId,
  pageId,
}: {
  workspaceId: string;
  spaceId: string;
  pageId?: string;
}) {
  const router = useAppRouter();
  const client = useQueryClient();
  const [createParent, setCreateParent] = useState<string | null | undefined>(undefined);
  const [mobileTree, setMobileTree] = useState(false);
  const [archivedOpen, setArchivedOpen] = useState(false);
  const [treeWidth, setTreeWidth] = useState(PAGE_TREE_DEFAULT_WIDTH);
  const [resizing, setResizing] = useState(false);
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const treeWidthRef = useRef(treeWidth);
  const treeScrollRef = useRef<HTMLDivElement>(null);
  const expandedWidthRef = useRef(PAGE_TREE_DEFAULT_WIDTH);
  const sourceSwitchRef = useRef(false);
  treeWidthRef.current = treeWidth;
  const compact = treeWidth < PAGE_TREE_COMPACT_WIDTH;

  useEffect(() => {
    try {
      const collapsed = localStorage.getItem(PAGE_TREE_COLLAPSED_KEY) === "1";
      const stored = Number(localStorage.getItem(PAGE_TREE_WIDTH_KEY));
      const expanded = Number(localStorage.getItem(PAGE_TREE_EXPANDED_WIDTH_KEY));
      if (Number.isFinite(expanded) && expanded >= PAGE_TREE_COMPACT_WIDTH) {
        expandedWidthRef.current = clampTreeWidth(expanded);
      }
      if (collapsed) {
        setTreeWidth(PAGE_TREE_ICON_WIDTH);
      } else if (Number.isFinite(stored) && stored > 0) {
        setTreeWidth(clampTreeWidth(stored));
      }
    } catch {
      /* ignore */
    }
  }, []);

  const persistTreeWidth = (width: number) => {
    const next = clampTreeWidth(width);
    setTreeWidth(next);
    const collapsed = next < PAGE_TREE_COMPACT_WIDTH;
    try {
      localStorage.setItem(PAGE_TREE_WIDTH_KEY, String(next));
      localStorage.setItem(PAGE_TREE_COLLAPSED_KEY, collapsed ? "1" : "0");
      if (!collapsed) {
        expandedWidthRef.current = next;
        localStorage.setItem(PAGE_TREE_EXPANDED_WIDTH_KEY, String(next));
      }
    } catch {
      /* ignore */
    }
  };

  const toggleTree = () => {
    if (compact) persistTreeWidth(expandedWidthRef.current || PAGE_TREE_DEFAULT_WIDTH);
    else persistTreeWidth(PAGE_TREE_ICON_WIDTH);
  };

  const { data: space } = useQuery({
    queryKey: ["space", spaceId],
    queryFn: () => clientApi<Space>(`/spaces/${spaceId}`),
    staleTime: 60_000,
  });

  const { data: sources = [], isLoading: sourcesLoading } = useQuery({
    queryKey: ["space-sources", spaceId],
    queryFn: () => clientApi<SourceRow[]>(`/spaces/${spaceId}/sources`),
    staleTime: 60_000,
  });

  useEffect(() => {
    if (!sources.length) {
      setSelectedSourceId(null);
      return;
    }
    const stored = readStoredSourceId(spaceId);
    const match = stored && sources.some((s) => s.id === stored) ? stored : sources[0].id;
    setSelectedSourceId(match);
    if (match !== stored) writeStoredSourceId(spaceId, match);
  }, [spaceId, sources]);

  const selectSource = (id: string) => {
    if (id === selectedSourceId) return;
    sourceSwitchRef.current = true;
    setSelectedSourceId(id);
    writeStoredSourceId(spaceId, id);
  };

  const { data: roots } = useQuery({
    queryKey: ["page-tree", spaceId, selectedSourceId, "root"],
    queryFn: () =>
      clientApi<PageTreeNode[]>(
        `/spaces/${spaceId}/pages/tree?source_id=${encodeURIComponent(selectedSourceId!)}`,
      ),
    enabled: !!selectedSourceId,
    staleTime: 60_000,
  });

  const canManage = space?.my_role === "OWNER" || space?.my_role === "EDITOR";
  const base = `/app/workspaces/${workspaceId}/spaces/${spaceId}`;

  const [activePageId, setActivePageId] = useState<string | undefined>(pageId);
  useEffect(() => {
    if (pageId) setActivePageId(pageId);
  }, [pageId]);

  useEffect(() => {
    if (!selectedSourceId || !roots) return;
    if (sourceSwitchRef.current) {
      sourceSwitchRef.current = false;
      if (roots.length) {
        const first = roots[0].id;
        setActivePageId(first);
        router.replace(`${base}/pages/${first}`, { feedback: false });
      } else {
        setActivePageId(undefined);
        router.replace(`${base}/pages`, { feedback: false });
      }
      return;
    }
    if (pageId || !roots.length) return;
    const first = roots[0].id;
    setActivePageId(first);
    router.replace(`${base}/pages/${first}`, { feedback: false });
  }, [pageId, roots, base, router, selectedSourceId]);

  const {
    data: page,
    isLoading: pageLoading,
    isFetching: pageFetching,
  } = useQuery({
    queryKey: ["page", activePageId],
    queryFn: () => clientApi<PageDetail>(`/pages/${activePageId}`),
    enabled: !!activePageId,
    retry: false,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (!page?.source_id || !sources.length) return;
    if (page.source_id === selectedSourceId) return;
    if (!sources.some((s) => s.id === page.source_id)) return;
    setSelectedSourceId(page.source_id);
    writeStoredSourceId(spaceId, page.source_id);
  }, [page?.source_id, page?.id, selectedSourceId, sources, spaceId]);

  useEffect(() => {
    if (!page) return;
    const ancestors = page.ancestors.map((a) => a.id);
    window.dispatchEvent(
      new CustomEvent("kl-expand-page-path", { detail: { ancestors } }),
    );
  }, [page]);

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail as { parentId?: string } | undefined;
      if (detail?.parentId) setCreateParent(detail.parentId);
    };
    window.addEventListener("kl-create-child", handler);
    return () => window.removeEventListener("kl-create-child", handler);
  }, []);

  const selectPage = (id: string) => {
    setActivePageId(id);
    setMobileTree(false);
    setArchivedOpen(false);
  };

  const openPage = (id: string) => {
    selectPage(id);
    router.push(`${base}/pages/${id}`, { feedback: false });
  };

  const pickFromSearch = (id: string) => {
    openPage(id);
    void client
      .fetchQuery({
        queryKey: ["page", id],
        queryFn: () => clientApi<PageDetail>(`/pages/${id}`),
      })
      .then((detail) => {
        window.dispatchEvent(
          new CustomEvent("kl-expand-page-path", {
            detail: { ancestors: detail.ancestors.map((a) => a.id) },
          }),
        );
      })
      .catch(() => undefined);
  };

  const sourceSelector =
    !compact && selectedSourceId ? (
      <div className="border-b border-border px-3 py-2">
        <label className="block text-[11px] font-medium text-muted">
          Source
          <select
            className="input mt-1 w-full text-sm"
            value={selectedSourceId}
            onChange={(e) => selectSource(e.target.value)}
          >
            {sources.map((s) => (
              <option key={s.id} value={s.id}>
                {s.type && s.type !== "LOCAL" ? `${sourceTypeLabel(s.type)} — ${s.name}` : s.name}
              </option>
            ))}
          </select>
        </label>
      </div>
    ) : null;

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-1">
      <aside
        className="relative hidden h-full min-h-0 shrink-0 flex-col overflow-x-hidden border-r border-border bg-surface md:flex"
        style={{ width: treeWidth }}
      >
        <div
          className={`flex border-b border-border ${
            compact ? "flex-col items-center gap-1 px-1 py-2" : "items-center justify-between gap-2 px-3 py-2"
          }`}
        >
          {compact ? null : (
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">{space?.name || "Space"}</p>
            </div>
          )}
          <div className={`flex shrink-0 ${compact ? "flex-col" : "gap-1"}`}>
            {compact ? null : (
              <button type="button" className="icon-button" title="Star space" disabled>
                <Star size={14} />
              </button>
            )}
            {canManage && selectedSourceId ? (
              <button
                type="button"
                className="icon-button"
                title="Add page"
                onClick={() => setCreateParent(null)}
              >
                <Plus size={14} />
              </button>
            ) : null}
            <button
              type="button"
              className="icon-button"
              aria-label={compact ? "Expand page menu" : "Collapse page menu"}
              title={compact ? "Expand page menu" : "Collapse page menu"}
              onClick={toggleTree}
            >
              {compact ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
            </button>
          </div>
        </div>
        {sourceSelector}
        {compact || !selectedSourceId ? null : (
          <div className="border-b border-border p-3">
            <PageTreeSearch spaceId={spaceId} sourceId={selectedSourceId} onPick={pickFromSearch} />
          </div>
        )}
        <div className="relative min-h-0 flex-1">
          <div ref={treeScrollRef} className={`h-full min-h-0 overflow-y-auto ${compact ? "px-1 py-1" : "p-2"}`}>
            {selectedSourceId ? (
              <PageTree
                spaceId={spaceId}
                sourceId={selectedSourceId}
                selectedId={activePageId || null}
                pageHref={(id) => `${base}/pages/${id}`}
                onSelect={selectPage}
                canManage={canManage}
                onCreateChild={(pid) => setCreateParent(pid)}
                compact={compact}
              />
            ) : compact ? null : (
              <div className="rounded-xl border border-dashed border-border p-4 text-sm text-muted">
                {sourcesLoading ? (
                  <p>Loading sources…</p>
                ) : (
                  <>
                    <p>No sources yet. Add a source to browse pages.</p>
                    <Link href={`${base}/sources`} className="mt-3 inline-block text-xs font-medium text-primary hover:underline">
                      Go to Sources
                    </Link>
                  </>
                )}
              </div>
            )}
          </div>
          <button
              type="button"
              aria-label="Resize page tree"
              aria-orientation="vertical"
              aria-valuemin={PAGE_TREE_MIN_WIDTH}
              aria-valuemax={PAGE_TREE_MAX_WIDTH}
              aria-valuenow={treeWidth}
              title="Drag to resize. Double-click to reset."
              className="group absolute inset-y-0 right-0 z-10 flex w-[17px] cursor-col-resize touch-none items-center justify-center overflow-visible"
              onWheel={(e) => {
                treeScrollRef.current?.scrollBy({ top: e.deltaY, left: e.deltaX });
              }}
              onPointerDown={(e) => {
                if (e.button !== 0) return;
                e.preventDefault();
                const handle = e.currentTarget;
                const startX = e.clientX;
                const startW = treeWidthRef.current;
                let latest = startW;
                handle.setPointerCapture(e.pointerId);
                setResizing(true);
                document.body.style.cursor = "col-resize";
                document.body.style.userSelect = "none";

                const onMove = (ev: PointerEvent) => {
                  latest = clampTreeWidth(startW + (ev.clientX - startX));
                  setTreeWidth(latest);
                };
                const onUp = () => {
                  handle.removeEventListener("pointermove", onMove);
                  handle.removeEventListener("pointerup", onUp);
                  handle.removeEventListener("pointercancel", onUp);
                  document.body.style.cursor = "";
                  document.body.style.userSelect = "";
                  setResizing(false);
                  persistTreeWidth(latest);
                };
                handle.addEventListener("pointermove", onMove);
                handle.addEventListener("pointerup", onUp);
                handle.addEventListener("pointercancel", onUp);
              }}
              onDoubleClick={() => persistTreeWidth(PAGE_TREE_DEFAULT_WIDTH)}
              onKeyDown={(e) => {
                if (e.key === "ArrowLeft") {
                  e.preventDefault();
                  persistTreeWidth(treeWidth - 16);
                } else if (e.key === "ArrowRight") {
                  e.preventDefault();
                  persistTreeWidth(treeWidth + 16);
                } else if (e.key === "Home") {
                  e.preventDefault();
                  persistTreeWidth(PAGE_TREE_DEFAULT_WIDTH);
                }
              }}
            >
              <span
                className={`pointer-events-none flex h-9 w-7 items-center justify-center rounded-md border bg-surface shadow-sm transition-opacity ${
                  resizing
                    ? "border-primary text-primary opacity-100"
                    : "border-border text-muted opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100"
                }`}
              >
                <PageTreeResizeGlyph className="h-[18px] w-[18px]" />
              </span>
            </button>
          </div>
          <button
            type="button"
            onClick={() => setArchivedOpen(true)}
            disabled={!selectedSourceId}
            title="Archived pages"
            className={`border-t border-border text-muted hover:text-foreground disabled:opacity-40 ${
              compact ? "grid place-items-center px-1 py-2" : "px-3 py-2.5 text-left text-xs"
            }`}
          >
            {compact ? <Archive size={16} /> : "Archived pages"}
          </button>
        </aside>

      <main
        className={`flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-[var(--background)] ${
          compact ? "p-3 md:p-4" : "p-4 md:p-6"
        }`}
      >
        <div className="mb-3 flex shrink-0 items-center gap-2 md:hidden">
          <button
            type="button"
            className="secondary-button text-xs"
            onClick={() => setMobileTree(true)}
          >
            Pages
          </button>
        </div>

        {!selectedSourceId ? (
          <div className="mx-auto max-w-lg py-16 text-center">
            <h1 className="text-xl font-semibold">Pages</h1>
            <p className="mt-2 text-sm text-muted">
              {sourcesLoading
                ? "Loading sources…"
                : "Add a source to this space, then browse its pages here."}
            </p>
            {!sourcesLoading ? (
              <Link href={`${base}/sources`} className="primary-button mt-4 inline-flex">
                Go to Sources
              </Link>
            ) : null}
          </div>
        ) : !activePageId ? (
          <div className="mx-auto max-w-lg py-16 text-center">
            {roots && roots.length === 0 ? (
              <>
                <h1 className="text-xl font-semibold">Pages</h1>
                <p className="mt-2 text-sm text-muted">
                  No pages in this source yet. Create one or import from Confluence.
                </p>
                {canManage ? (
                  <button
                    type="button"
                    className="primary-button mt-4"
                    onClick={() => setCreateParent(null)}
                  >
                    <Plus size={16} /> Create Page
                  </button>
                ) : null}
              </>
            ) : (
              <p className="text-sm text-muted">Loading pages…</p>
            )}
          </div>
        ) : pageLoading && !page ? (
          <div className="page-loading">Loading page…</div>
        ) : page ? (
          <div
            className={`flex min-h-0 flex-1 flex-col ${
              pageFetching && page.id !== activePageId ? "opacity-70" : ""
            }`}
          >
            <PageContentView
              workspaceId={workspaceId}
              spaceId={spaceId}
              spaceName={space?.name || "Space"}
              page={page}
              onDeleted={() => router.push(`${base}/pages`)}
            />
          </div>
        ) : (
          <div className="error-state">
            Page not found. The page may have been moved, deleted, or you may not have access.
          </div>
        )}
      </main>

      {mobileTree ? (
        <div className="fixed inset-0 z-40 flex md:hidden">
          <button
            type="button"
            className="flex-1 bg-black/40"
            aria-label="Close"
            onClick={() => setMobileTree(false)}
          />
          <aside className="flex h-full w-[85%] max-w-sm flex-col bg-surface p-3 shadow-xl">
            {selectedSourceId ? (
              <>
                <label className="mb-3 block text-[11px] font-medium text-muted">
                  Source
                  <select
                    className="input mt-1 w-full text-sm"
                    value={selectedSourceId}
                    onChange={(e) => selectSource(e.target.value)}
                  >
                    {sources.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.type && s.type !== "LOCAL"
                          ? `${sourceTypeLabel(s.type)} — ${s.name}`
                          : s.name}
                      </option>
                    ))}
                  </select>
                </label>
                <PageTreeSearch spaceId={spaceId} sourceId={selectedSourceId} onPick={pickFromSearch} />
                <div className="mt-3 flex-1 overflow-y-auto">
                  <PageTree
                    spaceId={spaceId}
                    sourceId={selectedSourceId}
                    selectedId={activePageId || null}
                    pageHref={(id) => `${base}/pages/${id}`}
                    onSelect={selectPage}
                    canManage={canManage}
                    onCreateChild={(pid) => {
                      setMobileTree(false);
                      setCreateParent(pid);
                    }}
                  />
                </div>
              </>
            ) : (
              <p className="text-sm text-muted">No sources yet.</p>
            )}
          </aside>
        </div>
      ) : null}

      {selectedSourceId ? (
        <CreatePageDialog
          open={createParent !== undefined}
          parentId={createParent ?? null}
          spaceId={spaceId}
          sourceId={selectedSourceId}
          onClose={() => setCreateParent(undefined)}
          onCreated={(p) => openPage(p.id)}
        />
      ) : null}

      {archivedOpen && selectedSourceId ? (
        <ArchivedPagesPanel
          spaceId={spaceId}
          sourceId={selectedSourceId}
          canManage={space?.my_role === "OWNER"}
          onClose={() => setArchivedOpen(false)}
          onOpen={openPage}
        />
      ) : null}
    </div>
  );
}
