"use client";

import {
  Copy,
  ExternalLink,
  Info,
  MoreHorizontal,
  Search,
  Star,
  Archive,
  Pencil,
} from "lucide-react";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useLayoutEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { EditPageDialog } from "@/components/pages/EditPageDialog";
import { MovePageDialog } from "@/components/pages/MovePageDialog";
import { PageAttachmentsPanel } from "@/components/pages/PageAttachmentsPanel";
import { PageDetailsDrawer } from "@/components/pages/PageDetailsDrawer";
import { PageFindBar, usePageFind } from "@/components/pages/PageFindBar";
import { clientApi } from "@/lib/api";
import type { PageDetail } from "@/lib/pages";
import { useClickOutside } from "@/lib/use-click-outside";

function relativeTime(iso: string) {
  const ms = Date.now() - new Date(iso).getTime();
  const m = Math.round(ms / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 48) return `${h} hour${h === 1 ? "" : "s"} ago`;
  const d = Math.round(h / 24);
  return `${d} day${d === 1 ? "" : "s"} ago`;
}

/** Basic XSS guard before rendering imported HTML. */
function sanitizeHtml(html: string): string {
  return html
    .replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, "")
    .replace(/<iframe[\s\S]*?>[\s\S]*?<\/iframe>/gi, "")
    .replace(/\son\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, "")
    .replace(/javascript:/gi, "");
}

export function PageBreadcrumb({
  workspaceId,
  workspaceName,
  spaceId,
  spaceName,
  page,
}: {
  workspaceId: string;
  workspaceName?: string;
  spaceId: string;
  spaceName: string;
  page: PageDetail;
}) {
  const crumbs = [
    { href: `/app/workspaces/${workspaceId}`, label: workspaceName || "Workspace" },
    { href: `/app/workspaces/${workspaceId}/spaces/${spaceId}`, label: spaceName },
    ...page.ancestors.map((a) => ({
      href: `/app/workspaces/${workspaceId}/spaces/${spaceId}/pages/${a.id}`,
      label: a.title,
    })),
    { href: null as string | null, label: page.title },
  ];
  const shown =
    crumbs.length > 4
      ? [
          crumbs[0],
          crumbs[1],
          { href: null, label: "…" },
          crumbs[crumbs.length - 2],
          crumbs[crumbs.length - 1],
        ]
      : crumbs;

  return (
    <nav className="flex flex-wrap items-center gap-1 text-xs text-muted">
      {shown.map((c, i) => (
        <span key={`${c.label}-${i}`} className="inline-flex items-center gap-1">
          {i > 0 ? <span className="opacity-50">›</span> : null}
          {c.href ? (
            <Link href={c.href} className="hover:text-foreground">
              {c.label}
            </Link>
          ) : (
            <span className={i === shown.length - 1 ? "text-foreground" : ""}>{c.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}

export function PageContentView({
  workspaceId,
  spaceId,
  spaceName,
  page,
  onDeleted,
}: {
  workspaceId: string;
  spaceId: string;
  spaceName: string;
  page: PageDetail;
  onDeleted?: () => void;
}) {
  const client = useQueryClient();
  const [menuOpen, setMenuOpen] = useState(false);
  const [moveOpen, setMoveOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [renameOpen, setRenameOpen] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [renameTitle, setRenameTitle] = useState(page.title);
  const contentRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  useClickOutside(menuRef, menuOpen, () => setMenuOpen(false));
  const p = page.permissions;

  const html = page.raw_content || page.normalized_content || "";
  const isHtml = /<[a-z][\s\S]*>/i.test(html);
  const confluenceUrl =
    page.external_url && page.external_url.startsWith("http") ? page.external_url : null;
  const contentKey = `${page.id}:${page.updated_at}:${html.length}`;

  // Imperative HTML so React state updates (find bar) do not wipe <mark> highlights.
  useLayoutEffect(() => {
    const root = contentRef.current;
    if (!root) return;
    if (!html) {
      root.innerHTML = `<p class="text-sm text-muted">This page has no content yet.</p>`;
      return;
    }
    if (isHtml) {
      root.innerHTML = sanitizeHtml(html);
    } else {
      root.textContent = html;
    }
  }, [contentKey, html, isHtml]);

  const find = usePageFind(contentRef, contentKey);

  const star = useMutation({
    mutationFn: () =>
      clientApi(`/pages/${page.id}/star`, { method: page.is_starred ? "DELETE" : "POST" }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["page", page.id] });
      toast.success(page.is_starred ? "Unstarred" : "Starred");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const archive = useMutation({
    mutationFn: () => clientApi(`/pages/${page.id}/archive`, { method: "POST" }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["page-tree", spaceId] });
      toast.success("Page archived");
      onDeleted?.();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const remove = useMutation({
    mutationFn: () => clientApi(`/pages/${page.id}`, { method: "DELETE" }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["page-tree", spaceId] });
      toast.success("Page deleted");
      onDeleted?.();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const duplicate = useMutation({
    mutationFn: () => clientApi<PageDetail>(`/pages/${page.id}/duplicate`, { method: "POST" }),
    onSuccess: (created) => {
      client.invalidateQueries({ queryKey: ["page-tree", spaceId] });
      toast.success("Page duplicated");
      window.location.href = `/app/workspaces/${workspaceId}/spaces/${spaceId}/pages/${created.id}`;
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const rename = useMutation({
    mutationFn: () =>
      clientApi(`/pages/${page.id}`, {
        method: "PATCH",
        body: JSON.stringify({ title: renameTitle.trim() }),
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["page", page.id] });
      client.invalidateQueries({ queryKey: ["page-tree", spaceId] });
      setRenameOpen(false);
      toast.success("Renamed");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const copyLink = async () => {
    const url = `${window.location.origin}/app/workspaces/${workspaceId}/spaces/${spaceId}/pages/${page.id}`;
    await navigator.clipboard.writeText(url);
    toast.success("Link copied");
  };

  return (
    <article className="flex min-h-0 min-w-0 flex-1 flex-col">
      <PageFindBar
        open={find.open}
        draft={find.draft}
        onDraftChange={find.onDraftChange}
        committed={find.committed}
        matchCount={find.matchCount}
        activeIndex={find.activeIndex}
        go={find.go}
        onEnter={find.onEnter}
        close={find.close}
        inputRef={find.inputRef}
      />

      <div className="min-h-0 flex-1 overflow-y-auto">
      <PageBreadcrumb
        workspaceId={workspaceId}
        spaceId={spaceId}
        spaceName={spaceName}
        page={page}
      />

      <header className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-3xl font-semibold tracking-tight">{page.title}</h1>
          <p className="mt-2 text-sm text-muted">
            Updated {relativeTime(page.updated_at)}
            {page.external_version ? ` · Version ${page.external_version}` : ""}
            {page.origin === "CONFLUENCE"
              ? " · Source: Confluence"
              : " · Created in Knowledge Library"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="secondary-button"
            title="Find in page (Ctrl+F)"
            onClick={find.openFind}
          >
            <Search size={16} />
            <span className="hidden sm:inline">Find</span>
          </button>
          <button
            type="button"
            className="secondary-button"
            title="Page details"
            onClick={() => setDetailsOpen(true)}
          >
            <Info size={16} />
          </button>
          <button type="button" className="secondary-button" onClick={() => star.mutate()}>
            <Star
              size={16}
              className={page.is_starred ? "fill-amber-400 text-amber-400" : ""}
            />
          </button>
          <button type="button" className="secondary-button" onClick={() => void copyLink()}>
            <Copy size={16} />
          </button>
          <div className="relative" ref={menuRef}>
            <button
              type="button"
              className="secondary-button"
              aria-expanded={menuOpen}
              aria-haspopup="menu"
              onClick={() => setMenuOpen((v) => !v)}
            >
              <MoreHorizontal size={16} />
            </button>
            {menuOpen ? (
              <div className="absolute right-0 z-20 mt-1 w-52 rounded-xl border border-border bg-surface py-1 shadow-lg">
                {p.can_create_child ? (
                  <button
                    type="button"
                    className="flex w-full px-3 py-2 text-left text-sm hover:bg-surface-muted"
                    onClick={() => {
                      setMenuOpen(false);
                      window.dispatchEvent(
                        new CustomEvent("kl-create-child", { detail: { parentId: page.id } }),
                      );
                    }}
                  >
                    Create child page
                  </button>
                ) : null}
                {p.can_move ? (
                  <>
                    <button
                      type="button"
                      className="flex w-full px-3 py-2 text-left text-sm hover:bg-surface-muted"
                      onClick={() => {
                        setMenuOpen(false);
                        setRenameTitle(page.title);
                        setRenameOpen(true);
                      }}
                    >
                      Rename
                    </button>
                    <button
                      type="button"
                      className="flex w-full px-3 py-2 text-left text-sm hover:bg-surface-muted"
                      onClick={() => {
                        setMenuOpen(false);
                        setMoveOpen(true);
                      }}
                    >
                      Move page
                    </button>
                    <button
                      type="button"
                      className="flex w-full px-3 py-2 text-left text-sm hover:bg-surface-muted"
                      onClick={() => {
                        setMenuOpen(false);
                        duplicate.mutate();
                      }}
                    >
                      Duplicate
                    </button>
                  </>
                ) : null}
                <button
                  type="button"
                  className="flex w-full px-3 py-2 text-left text-sm hover:bg-surface-muted"
                  onClick={() => {
                    setMenuOpen(false);
                    void copyLink();
                  }}
                >
                  Copy link
                </button>
                {confluenceUrl ? (
                  <a
                    className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-surface-muted"
                    href={confluenceUrl}
                    target="_blank"
                    rel="noreferrer"
                    onClick={() => setMenuOpen(false)}
                  >
                    <ExternalLink size={14} /> Open in Confluence
                  </a>
                ) : null}
                {p.can_archive ? (
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-surface-muted"
                    onClick={() => {
                      setMenuOpen(false);
                      if (confirm("Archive this page and its children?")) archive.mutate();
                    }}
                  >
                    <Archive size={14} /> Archive
                  </button>
                ) : null}
                {p.can_delete ? (
                  <button
                    type="button"
                    className="flex w-full px-3 py-2 text-left text-sm text-rose-600 hover:bg-surface-muted"
                    onClick={() => {
                      setMenuOpen(false);
                      if (confirm(`Delete "${page.title}" and its children?`)) remove.mutate();
                    }}
                  >
                    Delete
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>
          {p.can_edit ? (
            <button type="button" className="primary-button" onClick={() => setEditOpen(true)}>
              <Pencil size={16} /> Edit
            </button>
          ) : page.origin === "CONFLUENCE" ? (
            confluenceUrl ? (
              <a
                href={confluenceUrl}
                target="_blank"
                rel="noreferrer"
                className="secondary-button"
              >
                <ExternalLink size={16} /> Open in Confluence
              </a>
            ) : (
              <span className="rounded-lg border border-border px-3 py-2 text-xs text-muted">
                Read-only
              </span>
            )
          ) : null}
        </div>
      </header>

      <div
        ref={contentRef}
        className={
          isHtml
            ? "page-html prose-page mt-6 w-full max-w-none overflow-x-auto pb-8 text-sm leading-relaxed text-foreground [&_a]:text-primary [&_code]:rounded [&_code]:bg-surface-muted [&_code]:px-1 [&_h1]:mb-3 [&_h1]:mt-6 [&_h1]:text-xl [&_h1]:font-semibold [&_h2]:mb-2 [&_h2]:mt-5 [&_h2]:text-lg [&_h2]:font-semibold [&_img]:my-4 [&_img]:max-h-[560px] [&_img]:w-auto [&_img]:max-w-full [&_img]:rounded-lg [&_img]:border [&_img]:border-border [&_img]:bg-white [&_img]:object-contain [&_li]:my-0.5 [&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-2 [&_pre]:my-3 [&_pre]:overflow-x-auto [&_pre]:rounded-xl [&_pre]:bg-surface-muted [&_pre]:p-3 [&_table]:my-3 [&_table]:w-full [&_table]:min-w-full [&_table]:border-collapse [&_table]:text-left [&_td]:border [&_td]:border-border [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:border-border [&_th]:bg-surface-muted [&_th]:px-2 [&_th]:py-1 [&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-5"
            : "prose-page mt-6 w-full max-w-none whitespace-pre-wrap pb-8 text-sm leading-relaxed"
        }
      />
      <PageAttachmentsPanel pageId={page.id} />
      </div>

      <PageDetailsDrawer
        open={detailsOpen}
        onClose={() => setDetailsOpen(false)}
        page={page}
        spaceName={spaceName}
      />

      <MovePageDialog
        open={moveOpen}
        onClose={() => setMoveOpen(false)}
        spaceId={spaceId}
        pageId={page.id}
        pageTitle={page.title}
        onMoved={() => {
          client.invalidateQueries({ queryKey: ["page", page.id] });
          client.invalidateQueries({ queryKey: ["page-tree", spaceId] });
          toast.success("Page moved");
        }}
      />
      <EditPageDialog open={editOpen} onClose={() => setEditOpen(false)} page={page} />

      {renameOpen ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
          <section className="w-full max-w-md rounded-2xl border border-border bg-surface p-5 shadow-2xl">
            <h2 className="text-lg font-semibold">Rename page</h2>
            <input
              className="input mt-3"
              value={renameTitle}
              maxLength={255}
              onChange={(e) => setRenameTitle(e.target.value)}
              autoFocus
            />
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" className="secondary-button" onClick={() => setRenameOpen(false)}>
                Cancel
              </button>
              <button
                type="button"
                className="primary-button"
                disabled={!renameTitle.trim() || rename.isPending}
                onClick={() => rename.mutate()}
              >
                Save
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </article>
  );
}
