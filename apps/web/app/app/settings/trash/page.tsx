"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { clientApi, type Space } from "@/lib/api";
import { RoleBadge } from "@/components/workspaces";

export default function SettingsTrashPage() {
  const client = useQueryClient();
  const { data = [], isLoading } = useQuery({
    queryKey: ["/me/trash-spaces"],
    queryFn: () => clientApi<Space[]>("/me/trash-spaces"),
  });
  const restore = useMutation({
    mutationFn: (spaceId: string) =>
      clientApi(`/spaces/${spaceId}/restore`, { method: "POST" }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["/me/trash-spaces"] });
      toast.success("Space restored");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <section className="settings-card p-6 sm:p-8">
      <h2 className="text-lg font-semibold">Trash</h2>
      <p className="mt-1 text-sm text-muted">Deleted spaces you can restore.</p>
      {isLoading ? (
        <div className="page-loading mt-6">Loading…</div>
      ) : data.length === 0 ? (
        <div className="empty-state mt-6">Deleted Spaces will appear here.</div>
      ) : (
        <div className="mt-6 divide-y divide-border rounded-xl border border-border">
          {data.map((space) => (
            <div key={space.id} className="flex items-center justify-between gap-3 p-4">
              <div>
                <p className="font-medium">{space.name}</p>
                <p className="text-xs text-muted">
                  Deleted{" "}
                  {space.deleted_at
                    ? new Date(space.deleted_at).toLocaleString()
                    : "recently"}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <RoleBadge role={space.my_role} />
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => restore.mutate(space.id)}
                >
                  Restore
                </button>
                <Link
                  href={`/app/workspaces/${space.workspace_id}/spaces`}
                  className="text-sm text-primary"
                >
                  Open workspace
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
