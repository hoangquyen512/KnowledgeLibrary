"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, FolderPlus, Settings, Share2 } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ShareDialog } from "@/components/dialogs";
import { EmptyState, RoleBadge } from "@/components/workspaces";
import { clientApi, type SpaceListResponse, type Workspace } from "@/lib/api";

export default function WorkspaceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [shareOpen, setShareOpen] = useState(false);
  const { data: workspace, isLoading, error } = useQuery({
    queryKey: ["workspace", id],
    queryFn: () => clientApi<Workspace>(`/workspaces/${id}`),
  });
  const { data: spaces } = useQuery({
    queryKey: ["spaces", id, "preview"],
    queryFn: () =>
      clientApi<SpaceListResponse>(`/workspaces/${id}/spaces?tab=all&page_size=5`),
  });

  if (isLoading) return <div className="page-loading">Loading workspace…</div>;
  if (error || !workspace) {
    return (
      <div className="error-state">
        This workspace could not be found or you no longer have access.
      </div>
    );
  }

  return (
    <div className="page-shell">
      <Link
        href="/app/workspaces"
        className="inline-flex items-center gap-1 text-sm text-muted hover:text-foreground"
      >
        <ArrowLeft size={16} />
        Workspaces
      </Link>
      <section className="mt-5 flex flex-col gap-4 rounded-2xl border border-border bg-surface p-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="page-title">{workspace.name}</h1>
            <RoleBadge role={workspace.my_role} />
          </div>
          <p className="mt-2 max-w-2xl text-sm text-muted">
            {workspace.description || "No description yet."}
          </p>
        </div>
        <div className="flex gap-2">
          <button type="button" className="secondary-button" onClick={() => setShareOpen(true)}>
            <Share2 size={16} />
            Share
          </button>
          <Link href={`/app/workspaces/${id}/settings`} className="secondary-button">
            <Settings size={16} />
            Settings
          </Link>
        </div>
      </section>

      <section className="mt-6">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h2 className="font-semibold">Spaces</h2>
            <p className="mt-1 text-sm text-muted">
              Organize knowledge inside this workspace.
            </p>
          </div>
          <Link href={`/app/workspaces/${id}/spaces`} className="primary-button">
            <FolderPlus size={16} />
            Manage Spaces
          </Link>
        </div>
        {spaces?.items?.length ? (
          <div className="divide-y divide-border rounded-2xl border border-border bg-surface">
            {spaces.items.map((space) => (
              <Link
                key={space.id}
                href={`/app/workspaces/${id}/spaces/${space.id}/pages`}
                className="flex items-center justify-between p-4 hover:bg-surface-muted/40"
              >
                <div>
                  <p className="font-medium">{space.name}</p>
                  <p className="text-xs text-muted">{space.description || "No description"}</p>
                </div>
                <RoleBadge role={space.my_role} />
              </Link>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No spaces yet"
            description="Create your first Space to organize documents and sources."
            action={
              <Link href={`/app/workspaces/${id}/spaces`} className="primary-button">
                <FolderPlus size={16} />
                Go to Spaces
              </Link>
            }
          />
        )}
      </section>
      <ShareDialog workspace={workspace} open={shareOpen} onOpenChange={setShareOpen} />
    </div>
  );
}
