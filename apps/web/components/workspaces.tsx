"use client";

import Link from "next/link";
import { MoreHorizontal, Settings, Share2 } from "lucide-react";
import { useState } from "react";
import type { Workspace } from "@/lib/api";
import { ShareDialog } from "@/components/dialogs";
import { BrandEmptyState } from "@/components/brand";

export function RoleBadge({ role }: { role: string | null }) {
  const value = role?.toLowerCase() || "member";
  return <span className={`role-badge role-${value}`}>{value}</span>;
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return <BrandEmptyState mood="full" title={title} description={description} action={action} />;
}

export function WorkspaceRow({ workspace }: { workspace: Workspace }) {
  const [shareOpen, setShareOpen] = useState(false);
  return (
    <>
      <div className="workspace-row">
        <Link href={`/app/workspaces/${workspace.id}`} className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="truncate font-semibold">{workspace.name}</h3>
            <RoleBadge role={workspace.my_role} />
          </div>
          <p className="mt-1 line-clamp-1 text-sm text-muted">
            {workspace.description || "No description yet."}
          </p>
        </Link>
        <div className="hidden items-center gap-5 text-xs text-muted sm:flex">
          <span>{workspace.space_count} spaces</span>
          <span>{workspace.source_count} sources</span>
        </div>
        <div className="flex gap-1">
          <button
            className="icon-button"
            aria-label="Share workspace"
            onClick={() => setShareOpen(true)}
          >
            <Share2 size={17} />
          </button>
          <Link
            className="icon-button"
            aria-label="Workspace settings"
            href={`/app/workspaces/${workspace.id}/settings`}
          >
            <Settings size={17} />
          </Link>
          <button className="icon-button" aria-label="More workspace actions">
            <MoreHorizontal size={17} />
          </button>
        </div>
      </div>
      <ShareDialog workspace={workspace} open={shareOpen} onOpenChange={setShareOpen} />
    </>
  );
}

export function WorkspaceList({
  workspaces,
  emptyTitle = "No workspaces yet",
  emptyDescription = "Create a workspace to organize knowledge, collaborators, and connected sources.",
  action,
}: {
  workspaces: Workspace[];
  emptyTitle?: string;
  emptyDescription?: string;
  action?: React.ReactNode;
}) {
  if (!workspaces.length) {
    return <EmptyState title={emptyTitle} description={emptyDescription} action={action} />;
  }
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-surface">
      {workspaces.map((workspace) => (
        <WorkspaceRow workspace={workspace} key={workspace.id} />
      ))}
    </div>
  );
}
