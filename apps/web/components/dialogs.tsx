"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Copy, LoaderCircle, Trash2, X } from "lucide-react";
import { useState } from "react";
import { clientApi, type ShareLink, type Workspace } from "@/lib/api";
import { toast } from "sonner";

function Dialog({ open, title, children, onClose }: { open: boolean; title: string; children: React.ReactNode; onClose: () => void }) {
  if (!open) return null;
  return <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4"><section role="dialog" aria-modal="true" className="w-full max-w-md rounded-2xl border border-border bg-surface p-5 shadow-2xl">
    <div className="mb-5 flex items-center justify-between"><h2 className="text-lg font-semibold">{title}</h2><button className="icon-button" onClick={onClose}><X size={18} /></button></div>{children}
  </section></div>;
}

export function CreateWorkspaceDialog({ open, onOpenChange, workspaceLimit, ownedCount }: { open: boolean; onOpenChange: (open: boolean) => void; workspaceLimit?: number; ownedCount?: number }) {
  const client = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const atLimit = workspaceLimit !== undefined && ownedCount !== undefined && ownedCount >= workspaceLimit;
  const mutation = useMutation({
    mutationFn: () => clientApi<Workspace>("/workspaces", { method: "POST", body: JSON.stringify({ name: name.trim(), description: description.trim() || null }) }),
    onSuccess: () => { client.invalidateQueries({ queryKey: ["workspaces"] }); client.invalidateQueries({ queryKey: ["dashboard"] }); toast.success("Workspace created."); setName(""); setDescription(""); onOpenChange(false); },
    onError: (error: Error) => toast.error(error.message),
  });
  return <Dialog open={open} title="Create workspace" onClose={() => onOpenChange(false)}>
    {atLimit ? <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-100">Bạn đã đạt giới hạn 10 Workspace. Hãy xóa một Workspace trước khi tạo mới.</p> : <>
      <label className="label">Name<input autoFocus value={name} onChange={(e) => setName(e.target.value)} maxLength={100} className="input mt-1.5" placeholder="e.g. Product knowledge" /></label>
      <label className="label mt-4">Description <span className="font-normal text-muted">(optional)</span><textarea value={description} onChange={(e) => setDescription(e.target.value)} maxLength={500} rows={3} className="input mt-1.5 resize-none" placeholder="What will this workspace contain?" /></label>
      <div className="mt-5 flex justify-end gap-2"><button className="secondary-button" onClick={() => onOpenChange(false)}>Cancel</button><button className="primary-button" disabled={!name.trim() || mutation.isPending} onClick={() => mutation.mutate()}>{mutation.isPending && <LoaderCircle className="animate-spin" size={16} />}Create workspace</button></div>
    </>}
  </Dialog>;
}

export function ShareDialog({ workspace, open, onOpenChange }: { workspace: Workspace; open: boolean; onOpenChange: (open: boolean) => void }) {
  const [role, setRole] = useState("VIEWER");
  const [confirmOwner, setConfirmOwner] = useState(false);
  const [link, setLink] = useState<ShareLink | null>(null);
  const mutation = useMutation({
    mutationFn: () =>
      clientApi<ShareLink>(`/workspaces/${workspace.id}/share-links`, {
        method: "POST",
        body: JSON.stringify({
          role,
          confirm_owner_role: role === "OWNER" ? confirmOwner : false,
        }),
      }),
    onSuccess: (data) => {
      setLink(data);
      toast.success("Share link created.");
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const copy = async () => {
    if (link?.url) {
      await navigator.clipboard.writeText(link.url);
      toast.success("Share link copied.");
    }
  };
  return (
    <Dialog open={open} title={`Share ${workspace.name}`} onClose={() => onOpenChange(false)}>
      <p className="text-sm text-muted">
        Multi-use link. Recipients must sign in with Google. Link does not expire until revoked.
      </p>
      <label className="label mt-4">
        Access role
        <select
          className="input mt-1.5"
          value={role}
          onChange={(e) => {
            setRole(e.target.value);
            setConfirmOwner(false);
            setLink(null);
          }}
        >
          <option value="VIEWER">Viewer</option>
          <option value="EDITOR">Editor</option>
          <option value="OWNER">Owner</option>
        </select>
      </label>
      {role === "OWNER" ? (
        <label className="mt-3 flex items-start gap-2 text-sm text-muted">
          <input
            type="checkbox"
            className="mt-1"
            checked={confirmOwner}
            onChange={(e) => setConfirmOwner(e.target.checked)}
          />
          <span>
            Owner access gives full control of this Workspace, including managing Spaces, access and
            deletion. Are you sure you want to create this link?
          </span>
        </label>
      ) : null}
      {link?.url ? (
        <div className="mt-4 flex gap-2">
          <input readOnly value={link.url} className="input min-w-0" />
          <button type="button" className="secondary-button" onClick={copy}>
            <Copy size={16} />
            Copy
          </button>
        </div>
      ) : null}
      <div className="mt-5 flex justify-end">
        <button
          type="button"
          className="primary-button"
          disabled={mutation.isPending || (role === "OWNER" && !confirmOwner)}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending && <LoaderCircle className="animate-spin" size={16} />}
          Create link
        </button>
      </div>
    </Dialog>
  );
}

export function DeleteWorkspaceDialog({ workspace, open, onOpenChange, onDeleted }: { workspace: Workspace; open: boolean; onOpenChange: (open: boolean) => void; onDeleted?: () => void }) {
  const [confirmation, setConfirmation] = useState("");
  const mutation = useMutation({
    mutationFn: () => clientApi<void>(`/workspaces/${workspace.id}`, { method: "DELETE", body: JSON.stringify({ confirm_name: confirmation }) }),
    onSuccess: () => { toast.success("Workspace deleted."); onOpenChange(false); onDeleted?.(); },
    onError: (error: Error) => toast.error(error.message),
  });
  return <Dialog open={open} title="Delete Workspace?" onClose={() => onOpenChange(false)}>
    <p className="text-sm text-muted">
      Workspace &quot;{workspace.name}&quot; and all of its Spaces, Sources, documents and AI indexes
      will be scheduled for deletion. This action may not be immediately reversible.
    </p>
    <p className="mt-3 text-sm text-muted">Type the Workspace name to confirm.</p>
    <input autoFocus value={confirmation} onChange={(e) => setConfirmation(e.target.value)} className="input mt-4" placeholder={workspace.name} />
    <div className="mt-5 flex justify-end gap-2"><button className="secondary-button" onClick={() => onOpenChange(false)}>Cancel</button><button className="danger-button" disabled={confirmation !== workspace.name || mutation.isPending} onClick={() => mutation.mutate()}><Trash2 size={16} />Delete Workspace</button></div>
  </Dialog>;
}
