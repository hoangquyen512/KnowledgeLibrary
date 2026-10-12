"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { clientApi, type Space } from "@/lib/api";
import { RoleBadge } from "@/components/workspaces";

function SpaceListPage({
  title,
  endpoint,
  empty,
}: {
  title: string;
  endpoint: string;
  empty: string;
}) {
  const { data = [], isLoading } = useQuery({
    queryKey: [endpoint],
    queryFn: () => clientApi<Space[]>(endpoint),
  });
  return (
    <div className="page-shell">
      <h1 className="page-title">{title}</h1>
      {isLoading ? (
        <div className="page-loading mt-6">Loading…</div>
      ) : data.length === 0 ? (
        <div className="empty-state mt-6">{empty}</div>
      ) : (
        <div className="mt-6 divide-y divide-border rounded-2xl border border-border bg-surface">
          {data.map((space) => (
            <Link
              key={space.id}
              href={`/app/workspaces/${space.workspace_id}/spaces/${space.id}/pages`}
              className="flex items-center justify-between gap-3 p-4 hover:bg-surface-muted/40"
            >
              <div>
                <p className="font-medium">{space.name}</p>
                <p className="text-xs text-muted">{space.description || "No description"}</p>
              </div>
              <RoleBadge role={space.my_role} />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export default function RecentPage() {
  return (
    <SpaceListPage
      title="Recent"
      endpoint="/me/recent-spaces"
      empty="Spaces you open will appear here."
    />
  );
}
