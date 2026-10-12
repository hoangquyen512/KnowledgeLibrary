"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { WorkspaceList, EmptyState } from "@/components/workspaces";
import { RoleBadge } from "@/components/workspaces";
import { clientApi, type Space, type Workspace } from "@/lib/api";

export default function SharedPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["shared"],
    queryFn: () =>
      clientApi<{ shared_workspaces: Workspace[]; shared_spaces: Space[] }>("/shared"),
  });
  const spaces = data?.shared_spaces || [];

  return (
    <div className="page-shell">
      <p className="eyebrow">Collaboration</p>
      <h1 className="page-title">Shared with me</h1>
      <p className="mt-1 text-sm text-muted">
        Workspaces and spaces other people have invited you to.
      </p>

      <section className="mt-7">
        <h2 className="mb-3 font-semibold">Workspaces</h2>
        {isLoading ? (
          <div className="page-loading">Loading shared workspaces…</div>
        ) : (
          <WorkspaceList
            workspaces={data?.shared_workspaces || []}
            emptyTitle="Nothing shared yet"
            emptyDescription="When someone shares a workspace with you, it will appear here."
          />
        )}
      </section>

      <section className="mt-8">
        <h2 className="mb-3 font-semibold">Spaces</h2>
        {isLoading ? (
          <div className="page-loading">Loading shared spaces…</div>
        ) : spaces.length === 0 ? (
          <EmptyState
            title="No shared spaces"
            description="When someone shares a Space with you via link, it will appear here."
          />
        ) : (
          <div className="divide-y divide-border rounded-2xl border border-border bg-surface">
            {spaces.map((space) => (
              <Link
                key={space.id}
                href={`/app/workspaces/${space.workspace_id}/spaces/${space.id}/pages`}
                className="flex items-center justify-between gap-3 p-4 hover:bg-surface-muted/40"
              >
                <div>
                  <p className="font-medium">{space.name}</p>
                  <p className="text-xs text-muted">
                    {space.description || "Shared Space access"} · Updated{" "}
                    {new Date(space.updated_at).toLocaleString()}
                  </p>
                </div>
                <RoleBadge role={space.my_role} />
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
