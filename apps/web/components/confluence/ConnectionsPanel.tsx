"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Pencil, Plug, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import type { ConfluenceConnection } from "@/lib/confluence";
import { ConnectionFormDialog } from "@/components/confluence/ConnectionFormDialog";
import { clientApi } from "@/lib/api";

export type { ConfluenceConnection };

export function ConnectionsPanel({
  workspaceId,
  canManage,
}: {
  workspaceId: string;
  canManage: boolean;
}) {
  const client = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ConfluenceConnection | null>(null);

  const { data: connections = [], isLoading } = useQuery({
    queryKey: ["confluence-connections", workspaceId],
    queryFn: () =>
      clientApi<ConfluenceConnection[]>(`/workspaces/${workspaceId}/confluence-connections`),
  });

  const test = useMutation({
    mutationFn: (id: string) =>
      clientApi<ConfluenceConnection>(`/confluence-connections/${id}/test`, { method: "POST" }),
    onSuccess: (row) => {
      client.invalidateQueries({ queryKey: ["confluence-connections", workspaceId] });
      toast.success(row.status === "ACTIVE" ? "Connection is active." : "Test finished.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const remove = useMutation({
    mutationFn: (id: string) => clientApi(`/confluence-connections/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["confluence-connections", workspaceId] });
      toast.success("Connection deleted.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <section className="settings-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold">Connections</h2>
          <p className="mt-1 text-sm text-muted">
            Connect Confluence via Direct or Local Agent. Cloud secrets are encrypted and never
            shown again. Edit a connection to refresh an expired cookie or PAT — you cannot delete
            one that still has sources.
          </p>
        </div>
        {canManage ? (
          <button
            type="button"
            className="primary-button"
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            <Plug size={16} /> Add connection
          </button>
        ) : null}
      </div>

      {isLoading ? (
        <p className="mt-4 text-sm text-muted">Loading connections…</p>
      ) : connections.length === 0 ? (
        <p className="mt-4 text-sm text-muted">No Confluence connections yet.</p>
      ) : (
        <ul className="mt-4 divide-y divide-border">
          {connections.map((c) => {
            const inUse = (c.source_count ?? 0) > 0;
            return (
              <li
                key={c.id}
                className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="font-medium">{c.name}</p>
                  <p className="text-xs text-muted">
                    {c.base_url} · {c.connection_mode} · {c.credential_location} · {c.auth_type} · ••••
                    {c.masked_suffix} · {c.status}
                    {inUse ? ` · ${c.source_count} source${c.source_count === 1 ? "" : "s"}` : ""}
                  </p>
                  {c.last_error ? <p className="mt-1 text-xs text-rose-600">{c.last_error}</p> : null}
                </div>
                {canManage ? (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => test.mutate(c.id)}
                      disabled={test.isPending || c.credential_location === "LOCAL_AGENT"}
                      title={
                        c.credential_location === "LOCAL_AGENT"
                          ? "Cloud test unavailable for LOCAL_AGENT credentials"
                          : undefined
                      }
                    >
                      {test.isPending ? <Loader2 size={14} className="animate-spin" /> : null}
                      Test
                    </button>
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => {
                        setEditing(c);
                        setFormOpen(true);
                      }}
                    >
                      <Pencil size={14} />
                      Edit
                    </button>
                    <button
                      type="button"
                      className="icon-button text-rose-600 disabled:opacity-40"
                      disabled={inUse || remove.isPending}
                      title={
                        inUse
                          ? "Cannot delete: this connection still has sources. Edit credentials instead."
                          : "Delete connection"
                      }
                      onClick={() => {
                        if (!inUse) remove.mutate(c.id);
                      }}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}

      <ConnectionFormDialog
        open={formOpen}
        workspaceId={workspaceId}
        connection={editing}
        onClose={() => {
          setFormOpen(false);
          setEditing(null);
        }}
      />
    </section>
  );
}
