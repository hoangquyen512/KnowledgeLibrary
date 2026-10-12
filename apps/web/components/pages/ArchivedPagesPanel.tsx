"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, X } from "lucide-react";
import { toast } from "sonner";
import { clientApi } from "@/lib/api";
import type { PageTreeNode } from "@/lib/pages";

export function ArchivedPagesPanel({
  spaceId,
  sourceId,
  canManage,
  onClose,
  onOpen,
}: {
  spaceId: string;
  sourceId: string;
  canManage: boolean;
  onClose: () => void;
  onOpen: (id: string) => void;
}) {
  const client = useQueryClient();
  const { data: rows = [], isLoading } = useQuery({
    queryKey: ["page-archived", spaceId, sourceId],
    queryFn: () =>
      clientApi<PageTreeNode[]>(
        `/spaces/${spaceId}/pages/archived?source_id=${encodeURIComponent(sourceId)}`,
      ),
    enabled: !!sourceId,
  });

  const restore = useMutation({
    mutationFn: (id: string) => clientApi(`/pages/${id}/restore`, { method: "POST" }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["page-archived", spaceId, sourceId] });
      client.invalidateQueries({ queryKey: ["page-tree", spaceId, sourceId] });
      toast.success("Page restored");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const remove = useMutation({
    mutationFn: (id: string) => clientApi(`/pages/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["page-archived", spaceId, sourceId] });
      toast.success("Page deleted");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40">
      <aside className="flex h-full w-full max-w-md flex-col border-l border-border bg-surface shadow-2xl">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="font-semibold">Archived pages</h2>
          <button type="button" className="icon-button" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-3">
          {isLoading ? (
            <p className="text-sm text-muted">Loading…</p>
          ) : rows.length === 0 ? (
            <p className="text-sm text-muted">No archived pages.</p>
          ) : (
            <ul className="space-y-1">
              {rows.map((r) => (
                <li
                  key={r.id}
                  className="flex items-center gap-2 rounded-xl border border-border px-3 py-2"
                >
                  <button
                    type="button"
                    className="min-w-0 flex-1 truncate text-left text-sm hover:text-primary"
                    onClick={() => onOpen(r.id)}
                  >
                    {r.title}
                  </button>
                  {canManage ? (
                    <>
                      <button
                        type="button"
                        className="icon-button"
                        title="Restore"
                        onClick={() => restore.mutate(r.id)}
                      >
                        <RotateCcw size={14} />
                      </button>
                      <button
                        type="button"
                        className="text-xs text-rose-600"
                        onClick={() => {
                          if (confirm(`Permanently delete "${r.title}"?`)) remove.mutate(r.id);
                        }}
                      >
                        Delete
                      </button>
                    </>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </div>
  );
}
