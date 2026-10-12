"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil } from "lucide-react";
import { useParams } from "next/navigation";
import { useAppRouter } from "@/components/navigation-progress";
import { useState } from "react";
import { toast } from "sonner";
import { ConnectionFormDialog } from "@/components/confluence/ConnectionFormDialog";
import type { ConfluenceConnection } from "@/lib/confluence";
import { clientApi, type Space } from "@/lib/api";
import type { SourceRow } from "@/lib/import-status";

export default function SpaceSettingsPage() {
  const { id, spaceId } = useParams<{ id: string; spaceId: string }>();
  const router = useAppRouter();
  const client = useQueryClient();
  const { data: space } = useQuery({
    queryKey: ["space", spaceId],
    queryFn: () => clientApi<Space>(`/spaces/${spaceId}`),
  });
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [confirm, setConfirm] = useState("");
  const [editConnection, setEditConnection] = useState<ConfluenceConnection | null>(null);

  const loaded = !!space;
  const formName = name || space?.name || "";
  const formDesc = description || space?.description || "";

  const { data: sources = [] } = useQuery({
    queryKey: ["sources", spaceId],
    queryFn: () => clientApi<SourceRow[]>(`/spaces/${spaceId}/sources`),
    enabled: Boolean(spaceId),
  });
  const { data: connections = [] } = useQuery({
    queryKey: ["confluence-connections", id],
    queryFn: () =>
      clientApi<ConfluenceConnection[]>(`/workspaces/${id}/confluence-connections`),
    enabled: Boolean(id),
  });
  const usedConnectionIds = new Set(
    sources.map((s) => s.connection_id).filter((cid): cid is string => Boolean(cid)),
  );
  const spaceConnections = connections.filter((c) => usedConnectionIds.has(c.id));

  const save = useMutation({
    mutationFn: () =>
      clientApi(`/spaces/${spaceId}`, {
        method: "PATCH",
        body: JSON.stringify({ name: formName, description: formDesc || null }),
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["space", spaceId] });
      toast.success("Space updated");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const archive = useMutation({
    mutationFn: () => clientApi(`/spaces/${spaceId}/archive`, { method: "POST" }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["space", spaceId] });
      toast.success("Space archived");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const restore = useMutation({
    mutationFn: () => clientApi(`/spaces/${spaceId}/restore`, { method: "POST" }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["space", spaceId] });
      toast.success("Space restored");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const remove = useMutation({
    mutationFn: () =>
      clientApi(`/spaces/${spaceId}/delete`, {
        method: "POST",
        body: JSON.stringify({ confirm_name: confirm.trim() }),
      }),
    onSuccess: () => {
      toast.success("Space deleted");
      router.push(`/app/workspaces/${id}/spaces`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (!loaded) return <div className="page-loading">Loading…</div>;

  const canEdit = space.my_role === "OWNER" || space.my_role === "EDITOR";
  const isOwner = space.my_role === "OWNER";

  return (
    <div className="h-full min-h-0 flex-1 space-y-6 overflow-y-auto p-4 sm:p-6">
      <h1 className="page-title">Space Settings</h1>

      <section className="settings-card space-y-3">
        <h2 className="font-semibold">General</h2>
        <label className="label">
          Space name
          <input
            className="input mt-1.5"
            defaultValue={space.name}
            disabled={!canEdit || space.status === "ARCHIVED"}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label className="label">
          Description
          <textarea
            className="input mt-1.5 resize-none"
            rows={3}
            defaultValue={space.description || ""}
            disabled={!canEdit || space.status === "ARCHIVED"}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        {canEdit ? (
          <button type="button" className="primary-button" onClick={() => save.mutate()}>
            Save
          </button>
        ) : null}
      </section>

      {canEdit ? (
        <section className="settings-card space-y-3">
          <h2 className="font-semibold">Confluence credentials</h2>
          <p className="text-sm text-muted">
            Edit credentials for Confluence sources in this Space. New sources are added from
            Sources → Add Source (connection is created there).
          </p>
          {spaceConnections.length === 0 ? (
            <p className="text-sm text-muted">No Confluence connection attached yet.</p>
          ) : (
            <ul className="divide-y divide-border">
              {spaceConnections.map((c) => (
                <li key={c.id} className="flex items-start justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <p className="font-medium">{c.name}</p>
                    <p className="text-xs text-muted">
                      {c.base_url} · {c.auth_type} · {c.status}
                    </p>
                    {c.last_error ? (
                      <p className="mt-1 text-xs text-rose-600">{c.last_error}</p>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    className="secondary-button shrink-0"
                    onClick={() => setEditConnection(c)}
                  >
                    <Pencil size={14} />
                    Edit
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}

      {isOwner ? (
        <section className="settings-card space-y-3">
          <h2 className="font-semibold">Danger Zone</h2>
          {space.status === "ARCHIVED" ? (
            <button type="button" className="secondary-button" onClick={() => restore.mutate()}>
              Restore Space
            </button>
          ) : (
            <button type="button" className="secondary-button" onClick={() => archive.mutate()}>
              Archive Space
            </button>
          )}
          <p className="text-sm text-muted">
            Delete Space &quot;{space.name}&quot; and all sources, documents and AI indexes will be
            scheduled for deletion.
          </p>
          <input
            className="input"
            placeholder={space.name}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
          <button
            type="button"
            className="danger-button"
            disabled={confirm.trim() !== space.name || remove.isPending}
            onClick={() => remove.mutate()}
          >
            Delete Space
          </button>
        </section>
      ) : null}

      <ConnectionFormDialog
        open={!!editConnection}
        workspaceId={id}
        connection={editConnection}
        onClose={() => setEditConnection(null)}
      />
    </div>
  );
}
