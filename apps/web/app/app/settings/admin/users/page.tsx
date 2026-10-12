"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { clientApi } from "@/lib/api";

type AdminUser = {
  id: string;
  email: string;
  display_name: string | null;
  status: string;
  is_super_admin: boolean;
  last_login_at: string | null;
  created_at: string;
};

export default function AdminUsersPage() {
  const client = useQueryClient();
  const [q, setQ] = useState("");
  const { data, isLoading } = useQuery({
    queryKey: ["admin-users", q],
    queryFn: () =>
      clientApi<{ items: AdminUser[]; total: number }>(
        `/admin/users${q ? `?q=${encodeURIComponent(q)}` : ""}`,
      ),
  });

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: "ACTIVE" | "SUSPENDED" }) =>
      clientApi<AdminUser>(`/admin/users/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["admin-users"] });
      toast.success("User status updated");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <section className="settings-card space-y-4 p-6 sm:p-8">
      <div>
        <h2 className="text-lg font-semibold">Users</h2>
        <p className="mt-1 text-sm text-muted">Suspend or reactivate accounts. Super Admin only.</p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <input
          className="min-w-[220px] flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm"
          placeholder="Search by email or name…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <span className="text-sm text-muted">{data?.total ?? 0} users</span>
      </div>
      {isLoading ? (
        <p className="text-sm text-muted">Loading users…</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="bg-surface-muted text-xs uppercase text-muted">
              <tr>
                <th className="px-3 py-2">Email</th>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Role</th>
                <th className="px-3 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {(data?.items || []).map((u) => (
                <tr key={u.id} className="border-t border-border">
                  <td className="px-3 py-2 font-medium">{u.email}</td>
                  <td className="px-3 py-2 text-muted">{u.display_name || "—"}</td>
                  <td className="px-3 py-2">{u.status}</td>
                  <td className="px-3 py-2">{u.is_super_admin ? "Super Admin" : "User"}</td>
                  <td className="px-3 py-2">
                    {u.is_super_admin ? (
                      <span className="text-xs text-muted">—</span>
                    ) : u.status === "ACTIVE" ? (
                      <button
                        type="button"
                        className="text-xs font-medium text-red-600 hover:underline"
                        disabled={setStatus.isPending}
                        onClick={() => setStatus.mutate({ id: u.id, status: "SUSPENDED" })}
                      >
                        Suspend
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="text-xs font-medium text-primary hover:underline"
                        disabled={setStatus.isPending}
                        onClick={() => setStatus.mutate({ id: u.id, status: "ACTIVE" })}
                      >
                        Activate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
