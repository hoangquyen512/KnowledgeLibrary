"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { clientApi, type Space } from "@/lib/api";
import { RoleBadge } from "@/components/workspaces";

export default function StarredPage() {
  const { data = [], isLoading } = useQuery({
    queryKey: ["/me/starred-spaces"],
    queryFn: () => clientApi<Space[]>("/me/starred-spaces"),
  });
  return (
    <div className="page-shell">
      <h1 className="page-title">Starred</h1>
      {isLoading ? (
        <div className="page-loading mt-6">Loading…</div>
      ) : data.length === 0 ? (
        <div className="empty-state mt-6">Star Spaces to find them quickly here.</div>
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
