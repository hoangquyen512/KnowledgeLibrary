"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Loader2, Radio, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { clientApi } from "@/lib/api";

export type ConnectorAgent = {
  id: string;
  workspace_id: string;
  name: string;
  status: string;
  version: string | null;
  last_heartbeat_at: string | null;
  created_at: string;
};

type RegistrationTokenOut = {
  id: string;
  workspace_id: string;
  expires_at: string;
  registration_token: string;
  message: string;
};

export function AgentsPanel({
  workspaceId,
  canManage,
}: {
  workspaceId: string;
  canManage: boolean;
}) {
  const client = useQueryClient();
  const [tokenOnce, setTokenOnce] = useState<string | null>(null);

  const { data: agents = [], isLoading } = useQuery({
    queryKey: ["agents", workspaceId],
    queryFn: () => clientApi<ConnectorAgent[]>(`/workspaces/${workspaceId}/agents`),
    refetchInterval: 15_000,
  });

  const createToken = useMutation({
    mutationFn: () =>
      clientApi<RegistrationTokenOut>(`/workspaces/${workspaceId}/agent-registration-tokens`, {
        method: "POST",
      }),
    onSuccess: (row) => {
      setTokenOnce(row.registration_token);
      toast.success("Registration token created. Copy it now.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const revoke = useMutation({
    mutationFn: (id: string) => clientApi(`/agents/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["agents", workspaceId] });
      toast.success("Agent revoked.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const enqueueNoop = useMutation({
    mutationFn: (agentId: string) =>
      clientApi(`/workspaces/${workspaceId}/agent-jobs/noop`, {
        method: "POST",
        body: JSON.stringify({ agent_id: agentId }),
      }),
    onSuccess: () => toast.success("NOOP job queued."),
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <section className="settings-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold">Local Connector Agents</h2>
          <p className="mt-1 text-sm text-muted">
            Register an outbound agent with a one-time token. Heartbeat keeps status ONLINE.
            Confluence fetch via agent lands in Phase 6.
          </p>
        </div>
        {canManage ? (
          <button
            type="button"
            className="primary-button"
            onClick={() => createToken.mutate()}
            disabled={createToken.isPending}
          >
            {createToken.isPending ? <Loader2 size={16} className="animate-spin" /> : <Radio size={16} />}
            New registration token
          </button>
        ) : null}
      </div>

      {tokenOnce ? (
        <div className="mt-4 rounded-xl border border-amber-300 bg-amber-50/80 p-3 text-sm dark:border-amber-800 dark:bg-amber-950/30">
          <p className="font-medium">Registration token (shown once)</p>
          <code className="mt-2 block break-all text-xs">{tokenOnce}</code>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              className="secondary-button"
              onClick={async () => {
                await navigator.clipboard.writeText(tokenOnce);
                toast.success("Copied.");
              }}
            >
              <Copy size={14} /> Copy
            </button>
            <button type="button" className="secondary-button" onClick={() => setTokenOnce(null)}>
              Dismiss
            </button>
          </div>
          <p className="mt-2 text-xs text-muted">
            Run:{" "}
            <code className="text-[11px]">
              REGISTRATION_TOKEN=… SaaS_API_URL=http://localhost:8000 python -m agent.main
            </code>
          </p>
        </div>
      ) : null}

      {isLoading ? (
        <p className="mt-4 text-sm text-muted">Loading agents…</p>
      ) : agents.length === 0 ? (
        <p className="mt-4 text-sm text-muted">No agents registered yet.</p>
      ) : (
        <ul className="mt-4 divide-y divide-border">
          {agents.map((a) => (
            <li
              key={a.id}
              className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between"
            >
              <div>
                <p className="font-medium">{a.name}</p>
                <p className="text-xs text-muted">
                  {a.status}
                  {a.version ? ` · v${a.version}` : ""}
                  {a.last_heartbeat_at
                    ? ` · heartbeat ${new Date(a.last_heartbeat_at).toLocaleString()}`
                    : " · no heartbeat yet"}
                </p>
              </div>
              {canManage ? (
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => enqueueNoop.mutate(a.id)}
                    disabled={enqueueNoop.isPending}
                  >
                    Ping (NOOP)
                  </button>
                  <button
                    type="button"
                    className="icon-button text-rose-600"
                    onClick={() => revoke.mutate(a.id)}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
