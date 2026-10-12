"use client";

import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useState } from "react";
import { clientApi } from "@/lib/api";
import type { PageTreeNode } from "@/lib/pages";

function TreePick({
  spaceId,
  excludeId,
  selected,
  onSelect,
}: {
  spaceId: string;
  excludeId: string;
  selected: string | null;
  onSelect: (id: string | null) => void;
}) {
  const { data: roots = [] } = useQuery({
    queryKey: ["page-tree", spaceId, "root", "move"],
    queryFn: () => clientApi<PageTreeNode[]>(`/spaces/${spaceId}/pages/tree`),
  });
  const [expanded, setExpanded] = useState<Record<string, PageTreeNode[]>>({});

  const load = async (id: string) => {
    if (expanded[id]) return;
    const kids = await clientApi<PageTreeNode[]>(
      `/spaces/${spaceId}/pages/tree?parent_id=${id}`,
    );
    setExpanded((m) => ({ ...m, [id]: kids }));
  };

  const render = (nodes: PageTreeNode[], depth: number) => (
    <ul className={depth ? "ml-3 border-l border-border pl-2" : "space-y-0.5"}>
      {nodes
        .filter((n) => n.id !== excludeId)
        .map((n) => (
          <li key={n.id}>
            <div className="flex items-center gap-1">
              {n.has_children ? (
                <button
                  type="button"
                  className="text-xs text-muted"
                  onClick={() => void load(n.id)}
                >
                  {expanded[n.id] ? "▼" : "▶"}
                </button>
              ) : (
                <span className="inline-block w-4" />
              )}
              <button
                type="button"
                className={`flex-1 truncate rounded-lg px-2 py-1.5 text-left text-sm ${
                  selected === n.id ? "bg-blue-50 text-primary dark:bg-blue-950/40" : "hover:bg-surface-muted"
                }`}
                onClick={() => onSelect(n.id)}
              >
                {n.title}
              </button>
            </div>
            {expanded[n.id] ? render(expanded[n.id], depth + 1) : null}
          </li>
        ))}
    </ul>
  );

  return (
    <div className="max-h-64 overflow-y-auto rounded-xl border border-border p-2">
      <button
        type="button"
        className={`mb-1 w-full rounded-lg px-2 py-1.5 text-left text-sm ${
          selected === null ? "bg-blue-50 text-primary dark:bg-blue-950/40" : "hover:bg-surface-muted"
        }`}
        onClick={() => onSelect(null)}
      >
        Space root
      </button>
      {render(roots, 0)}
    </div>
  );
}

export function MovePageDialog({
  open,
  onClose,
  spaceId,
  pageId,
  pageTitle,
  onMoved,
}: {
  open: boolean;
  onClose: () => void;
  spaceId: string;
  pageId: string;
  pageTitle: string;
  onMoved: () => void;
}) {
  const [parentId, setParentId] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const submit = async () => {
    setPending(true);
    setError(null);
    try {
      await clientApi(`/pages/${pageId}/move`, {
        method: "POST",
        body: JSON.stringify({ parent_id: parentId }),
      });
      onMoved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Move failed");
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
      <section className="w-full max-w-md rounded-2xl border border-border bg-surface p-5 shadow-2xl">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Move page</h2>
          <button type="button" className="icon-button" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <p className="mb-3 text-sm text-muted">
          Move <span className="font-medium text-foreground">&quot;{pageTitle}&quot;</span> to a new
          parent.
        </p>
        <TreePick
          spaceId={spaceId}
          excludeId={pageId}
          selected={parentId}
          onSelect={setParentId}
        />
        {error ? <p className="mt-2 text-sm text-rose-600">{error}</p> : null}
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="primary-button" disabled={pending} onClick={() => void submit()}>
            Move
          </button>
        </div>
      </section>
    </div>
  );
}
