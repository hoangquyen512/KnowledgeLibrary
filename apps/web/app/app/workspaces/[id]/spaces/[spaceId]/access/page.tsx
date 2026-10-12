"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { clientApi, type Member, type ShareLink, type Space } from "@/lib/api";

export default function SpaceAccessPage() {
  const { spaceId } = useParams<{ id: string; spaceId: string }>();
  const client = useQueryClient();
  const [role, setRole] = useState("VIEWER");
  const [confirmOwner, setConfirmOwner] = useState(false);
  const [createdUrl, setCreatedUrl] = useState<string | null>(null);

  const { data: space } = useQuery({
    queryKey: ["space", spaceId],
    queryFn: () => clientApi<Space>(`/spaces/${spaceId}`),
  });
  const { data: members = [] } = useQuery({
    queryKey: ["space-members", spaceId],
    queryFn: () => clientApi<Member[]>(`/spaces/${spaceId}/members`),
  });
  const { data: links = [] } = useQuery({
    queryKey: ["space-share-links", spaceId],
    queryFn: () => clientApi<ShareLink[]>(`/spaces/${spaceId}/share-links`),
  });

  const createLink = useMutation({
    mutationFn: () =>
      clientApi<ShareLink>(`/spaces/${spaceId}/share-links`, {
        method: "POST",
        body: JSON.stringify({
          role,
          confirm_owner_role: role === "OWNER" ? confirmOwner : false,
        }),
      }),
    onSuccess: (data) => {
      setCreatedUrl(data.url || null);
      client.invalidateQueries({ queryKey: ["space-share-links", spaceId] });
      toast.success("Share link created");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const revoke = useMutation({
    mutationFn: (linkId: string) =>
      clientApi(`/share-links/${linkId}`, { method: "DELETE" }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["space-share-links", spaceId] });
      toast.success("Link revoked");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (!space) return <div className="page-loading">Loading…</div>;
  if (space.my_role !== "OWNER") {
    return <div className="error-state">Only Space Owners can manage access.</div>;
  }

  return (
    <div className="h-full min-h-0 flex-1 space-y-6 overflow-y-auto p-4 sm:p-6">
      <h1 className="page-title">Access — {space.name}</h1>

      <section className="settings-card">
        <h2 className="font-semibold">Members</h2>
        <div className="mt-3 divide-y divide-border">
          {members.map((m) => (
            <div key={m.id} className="flex items-center justify-between py-3 text-sm">
              <div>
                <p className="font-medium">{m.display_name || m.email}</p>
                <p className="text-xs text-muted">
                  {m.email} · {m.source}
                </p>
              </div>
              <span className="text-muted">{m.role}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="settings-card space-y-3">
        <h2 className="font-semibold">Create share link</h2>
        <select className="input" value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="VIEWER">Viewer</option>
          <option value="EDITOR">Editor</option>
          <option value="OWNER">Owner</option>
        </select>
        {role === "OWNER" ? (
          <label className="flex gap-2 text-sm text-muted">
            <input
              type="checkbox"
              checked={confirmOwner}
              onChange={(e) => setConfirmOwner(e.target.checked)}
            />
            Owner access gives full control of this Space. Are you sure?
          </label>
        ) : null}
        {createdUrl ? (
          <input className="input" readOnly value={createdUrl} />
        ) : null}
        <button
          type="button"
          className="primary-button"
          disabled={role === "OWNER" && !confirmOwner}
          onClick={() => createLink.mutate()}
        >
          Create Share Link
        </button>
      </section>

      <section className="settings-card">
        <h2 className="font-semibold">Share Links</h2>
        <div className="mt-3 divide-y divide-border text-sm">
          {links.map((link) => (
            <div key={link.id} className="flex items-center justify-between py-3">
              <div>
                <p>
                  {link.role} · {link.status} · used {link.use_count}
                </p>
                <p className="text-xs text-muted">
                  {new Date(link.created_at).toLocaleString()}
                </p>
              </div>
              {link.status === "ACTIVE" ? (
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => revoke.mutate(link.id)}
                >
                  Revoke
                </button>
              ) : null}
            </div>
          ))}
          {links.length === 0 ? <p className="py-3 text-muted">No share links yet.</p> : null}
        </div>
      </section>
    </div>
  );
}
