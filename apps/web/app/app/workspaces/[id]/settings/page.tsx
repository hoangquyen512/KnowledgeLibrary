"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle, Save, Trash2 } from "lucide-react";
import { useParams } from "next/navigation";
import { useAppRouter } from "@/components/navigation-progress";
import { useEffect, useState } from "react";
import { DeleteWorkspaceDialog, ShareDialog } from "@/components/dialogs";
import { AgentsPanel } from "@/components/confluence/AgentsPanel";
import { RoleBadge } from "@/components/workspaces";
import { clientApi, type Member, type Workspace } from "@/lib/api";
import { toast } from "sonner";

export default function WorkspaceSettingsPage() {
  const { id } = useParams<{ id: string }>();
  const router = useAppRouter();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [shareOpen, setShareOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const { data: workspace } = useQuery({
    queryKey: ["workspace", id],
    queryFn: () => clientApi<Workspace>(`/workspaces/${id}`),
  });
  const { data: members = [] } = useQuery({
    queryKey: ["workspace", id, "members"],
    queryFn: () => clientApi<Member[]>(`/workspaces/${id}/members`),
  });

  useEffect(() => {
    if (workspace) {
      setName(workspace.name);
      setDescription(workspace.description || "");
    }
  }, [workspace]);

  const update = useMutation({
    mutationFn: () =>
      clientApi<Workspace>(`/workspaces/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
        }),
      }),
    onSuccess: (next) => {
      queryClient.setQueryData(["workspace", id], next);
      queryClient.invalidateQueries({ queryKey: ["workspaces"] });
      toast.success("Workspace updated.");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const updateRole = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      clientApi<Member>(`/workspaces/${id}/members/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({ role }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspace", id, "members"] }),
    onError: (error: Error) => toast.error(error.message),
  });

  const removeMember = useMutation({
    mutationFn: (userId: string) =>
      clientApi<void>(`/workspaces/${id}/members/${userId}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspace", id, "members"] });
      toast.success("Member removed.");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  if (!workspace) return <div className="page-loading">Loading workspace settings…</div>;
  const owner = workspace.my_role === "OWNER";

  return (
    <div className="page-shell space-y-6">
      <div>
        <p className="eyebrow">Workspace settings</p>
        <h1 className="page-title">{workspace.name}</h1>
      </div>

      <section className="settings-card">
        <h2 className="font-semibold">General</h2>
        <p className="mt-1 text-sm text-muted">Set the workspace name and description.</p>
        <label className="label mt-5">
          Name
          <input
            className="input mt-1.5"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={!owner}
          />
        </label>
        <label className="label mt-4">
          Description
          <textarea
            className="input mt-1.5 resize-none"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={!owner}
          />
        </label>
        {owner ? (
          <button
            className="primary-button mt-5"
            onClick={() => update.mutate()}
            disabled={!name.trim() || update.isPending}
          >
            {update.isPending ? <LoaderCircle size={16} className="animate-spin" /> : null}
            <Save size={16} />
            Save changes
          </button>
        ) : null}
      </section>

      <section className="settings-card">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="font-semibold">Access</h2>
            <p className="mt-1 text-sm text-muted">Manage workspace members and share links.</p>
          </div>
          {owner ? (
            <button className="secondary-button" onClick={() => setShareOpen(true)}>
              Create share link
            </button>
          ) : null}
        </div>
        <div className="mt-4 divide-y divide-border">
          {members.map((member) => (
            <div className="flex items-center gap-3 py-3" key={member.id}>
              <span className="grid h-8 w-8 place-items-center rounded-full bg-surface-muted text-xs font-semibold">
                {(member.display_name || member.email || "?").slice(0, 1).toUpperCase()}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">
                  {member.display_name || member.email || "Unknown user"}
                </p>
                <p className="text-xs text-muted">{member.source.toLowerCase()}</p>
              </div>
              {owner && member.role !== "OWNER" ? (
                <>
                  <select
                    className="input w-28 py-1.5 text-xs"
                    value={member.role}
                    onChange={(e) =>
                      updateRole.mutate({ userId: member.user_id, role: e.target.value })
                    }
                  >
                    <option value="VIEWER">Viewer</option>
                    <option value="EDITOR">Editor</option>
                  </select>
                  <button
                    className="icon-button text-rose-600"
                    onClick={() => removeMember.mutate(member.user_id)}
                  >
                    <Trash2 size={16} />
                  </button>
                </>
              ) : (
                <RoleBadge role={member.role} />
              )}
            </div>
          ))}
        </div>
      </section>

      <AgentsPanel workspaceId={id} canManage={owner} />

      {owner ? (
        <section className="rounded-2xl border border-rose-200 bg-rose-50/40 p-5 dark:border-rose-900 dark:bg-rose-950/20">
          <h2 className="font-semibold text-rose-800 dark:text-rose-200">Danger zone</h2>
          <p className="mt-1 text-sm text-muted">Deleting a workspace is irreversible.</p>
          <button className="danger-button mt-4" onClick={() => setDeleteOpen(true)}>
            <Trash2 size={16} />
            Delete workspace
          </button>
        </section>
      ) : null}

      <ShareDialog workspace={workspace} open={shareOpen} onOpenChange={setShareOpen} />
      <DeleteWorkspaceDialog
        workspace={workspace}
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        onDeleted={() => router.push("/app/workspaces")}
      />
    </div>
  );
}
