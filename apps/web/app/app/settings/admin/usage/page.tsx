"use client";

import { useQuery } from "@tanstack/react-query";
import { clientApi } from "@/lib/api";

type UsageRow = {
  user_email: string;
  workspace_id: string;
  message_count: number;
  input_tokens: number;
  output_tokens: number;
};

export default function AdminUsagePage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-usage"],
    queryFn: () =>
      clientApi<{
        items: UsageRow[];
        total_messages: number;
        total_input_tokens: number;
        total_output_tokens: number;
      }>("/admin/usage"),
  });

  return (
    <section className="settings-card space-y-4 p-6 sm:p-8">
      <div>
        <h2 className="text-lg font-semibold">AI usage</h2>
        <p className="mt-1 text-sm text-muted">Aggregated token usage only — API keys are never shown.</p>
      </div>
      {isLoading ? (
        <p className="text-sm text-muted">Loading AI usage…</p>
      ) : error ? (
        <p className="text-sm text-rose-600">Could not load AI usage.</p>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-border bg-surface-muted p-4">
              <p className="text-xs text-muted">Total AI calls</p>
              <p className="mt-1 text-xl font-semibold">{data?.total_messages ?? 0}</p>
            </div>
            <div className="rounded-xl border border-border bg-surface-muted p-4">
              <p className="text-xs text-muted">Input tokens</p>
              <p className="mt-1 text-xl font-semibold tabular-nums">
                {(data?.total_input_tokens ?? 0).toLocaleString()}
              </p>
            </div>
            <div className="rounded-xl border border-border bg-surface-muted p-4">
              <p className="text-xs text-muted">Output tokens</p>
              <p className="mt-1 text-xl font-semibold tabular-nums">
                {(data?.total_output_tokens ?? 0).toLocaleString()}
              </p>
            </div>
          </div>
          <div className="overflow-x-auto rounded-xl border border-border">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="bg-surface-muted text-xs uppercase text-muted">
                <tr>
                  <th className="px-3 py-2">User</th>
                  <th className="px-3 py-2">Workspace</th>
                  <th className="px-3 py-2">Calls</th>
                  <th className="px-3 py-2">Tokens in</th>
                  <th className="px-3 py-2">Tokens out</th>
                </tr>
              </thead>
              <tbody>
                {(data?.items || []).map((row, i) => (
                  <tr key={`${row.user_email}-${row.workspace_id}-${i}`} className="border-t border-border">
                    <td className="px-3 py-2">{row.user_email}</td>
                    <td className="max-w-[140px] truncate px-3 py-2 font-mono text-xs text-muted">
                      {row.workspace_id}
                    </td>
                    <td className="px-3 py-2">{row.message_count}</td>
                    <td className="px-3 py-2 tabular-nums">{row.input_tokens.toLocaleString()}</td>
                    <td className="px-3 py-2 tabular-nums">{row.output_tokens.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
