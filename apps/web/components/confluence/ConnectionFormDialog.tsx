"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import type { ConnectorAgent } from "@/components/confluence/AgentsPanel";
import type { ConfluenceConnection } from "@/lib/confluence";
import { clientApi } from "@/lib/api";

type AuthType = "PAT" | "SESSION_COOKIE";
type ConnectionMode = "DIRECT" | "LOCAL_AGENT";
type CredentialLocation = "CLOUD" | "LOCAL_AGENT";

export function ConnectionFormDialog({
  open,
  workspaceId,
  connection,
  onClose,
  onCreated,
  onSaved,
  embedded = false,
}: {
  open: boolean;
  workspaceId: string;
  connection?: ConfluenceConnection | null;
  onClose: () => void;
  /** After creating a new connection (not edit). Parent can test + continue. */
  onCreated?: (connection: ConfluenceConnection) => void | Promise<void>;
  /** After save when editing (e.g. retry credentials in Add Source). */
  onSaved?: (connection: ConfluenceConnection) => void | Promise<void>;
  /** Render fields only (no modal shell) for embedding in Add Source. */
  embedded?: boolean;
}) {
  const client = useQueryClient();
  const editing = Boolean(connection);
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [authType, setAuthType] = useState<AuthType>("PAT");
  const [username, setUsername] = useState("");
  const [secret, setSecret] = useState("");
  const [connectionMode, setConnectionMode] = useState<ConnectionMode>("DIRECT");
  const [credentialLocation, setCredentialLocation] = useState<CredentialLocation>("CLOUD");
  const [agentId, setAgentId] = useState("");
  const [continuing, setContinuing] = useState(false);

  useEffect(() => {
    if (!open) return;
    setName(connection?.name || "");
    setBaseUrl(connection?.base_url || "");
    setAuthType((connection?.auth_type as AuthType) || "PAT");
    setUsername("");
    setSecret("");
    setConnectionMode((connection?.connection_mode as ConnectionMode) || "DIRECT");
    setCredentialLocation((connection?.credential_location as CredentialLocation) || "CLOUD");
    setAgentId(connection?.connector_agent_id || "");
    setContinuing(false);
  }, [open, connection]);

  const { data: agents = [] } = useQuery({
    queryKey: ["agents", workspaceId],
    queryFn: () => clientApi<ConnectorAgent[]>(`/workspaces/${workspaceId}/agents`),
    enabled: open,
  });

  const save = useMutation({
    mutationFn: () => {
      const payload: Record<string, unknown> = {
        name: name.trim(),
        base_url: baseUrl.trim(),
        auth_type: authType,
        connection_mode: connectionMode,
        credential_location: credentialLocation,
        connector_agent_id: connectionMode === "LOCAL_AGENT" ? agentId || null : null,
      };
      if (credentialLocation === "CLOUD") {
        if (secret.trim()) payload.secret = secret.trim();
        if (authType === "PAT" && username.trim()) payload.username = username.trim();
      }
      if (editing && connection) {
        return clientApi<ConfluenceConnection>(`/confluence-connections/${connection.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      }
      return clientApi<ConfluenceConnection>(`/workspaces/${workspaceId}/confluence-connections`, {
        method: "POST",
        body: JSON.stringify({
          ...payload,
          username: authType === "PAT" && credentialLocation === "CLOUD" ? username.trim() : null,
          secret: credentialLocation === "CLOUD" ? secret.trim() : null,
        }),
      });
    },
    onSuccess: async (row) => {
      client.invalidateQueries({ queryKey: ["confluence-connections", workspaceId] });
      if (!editing && onCreated) {
        setContinuing(true);
        try {
          await onCreated(row);
        } finally {
          setContinuing(false);
        }
        return;
      }
      if (editing && onSaved) {
        setContinuing(true);
        try {
          await onSaved(row);
        } finally {
          setContinuing(false);
        }
        return;
      }
      toast.success(editing ? "Connection updated." : "Connection created.");
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const cloudCreds = credentialLocation === "CLOUD";
  const secretOk = editing
    ? !cloudCreds || !secret.trim() || authType !== "PAT" || Boolean(username.trim())
    : !cloudCreds || (Boolean(secret.trim()) && (authType !== "PAT" || Boolean(username.trim())));
  const busy = save.isPending || continuing;
  const canSubmit =
    name.trim() &&
    baseUrl.trim() &&
    (connectionMode === "DIRECT" || agentId) &&
    secretOk &&
    !busy;

  if (!open) return null;

  const fields = (
    <>
      {editing && !embedded ? (
        <p className="mt-1 text-xs text-muted">
          Sources keep using this connection. Leave PAT/cookie blank to keep the current secret.
          After updating credentials, run Test then Sync.
        </p>
      ) : null}
      {!editing && embedded ? (
        <p className="mt-1 text-xs text-muted">
          Enter Confluence credentials for this source. We will test the connection before you pick a
          space.
        </p>
      ) : null}
      <label className="label mt-4">
        Name
        <input className="input mt-1.5" value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label className="label mt-3">
        Base URL
        <input
          className="input mt-1.5"
          placeholder="https://confluence.company.com"
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
        />
      </label>
      <label className="label mt-3">
        Connection mode
        <select
          className="input mt-1.5"
          value={connectionMode}
          onChange={(e) => {
            const mode = e.target.value as ConnectionMode;
            setConnectionMode(mode);
            if (mode === "DIRECT") setCredentialLocation("CLOUD");
          }}
        >
          <option value="DIRECT">Direct (SaaS → Confluence)</option>
          <option value="LOCAL_AGENT">Local Agent</option>
        </select>
      </label>
      {connectionMode === "LOCAL_AGENT" ? (
        <label className="label mt-3">
          Agent
          <select
            className="input mt-1.5"
            value={agentId}
            onChange={(e) => setAgentId(e.target.value)}
          >
            <option value="">Select agent…</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} ({a.status})
              </option>
            ))}
          </select>
        </label>
      ) : null}
      <label className="label mt-3">
        Credential location
        <select
          className="input mt-1.5"
          value={credentialLocation}
          onChange={(e) => setCredentialLocation(e.target.value as CredentialLocation)}
          disabled={connectionMode === "DIRECT"}
        >
          <option value="CLOUD">Cloud (encrypted in SaaS)</option>
          <option value="LOCAL_AGENT">Local Agent only</option>
        </select>
      </label>
      <label className="label mt-3">
        Auth type
        <select
          className="input mt-1.5"
          value={authType}
          onChange={(e) => setAuthType(e.target.value as AuthType)}
        >
          <option value="PAT">Personal Access Token</option>
          <option value="SESSION_COOKIE">Session cookie (non-prod only)</option>
        </select>
      </label>
      {cloudCreds ? (
        <>
          {authType === "PAT" ? (
            <label className="label mt-3">
              Username / email
              <input
                className="input mt-1.5"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder={editing ? "Required only when replacing PAT" : undefined}
              />
            </label>
          ) : null}
          <label className="label mt-3">
            {authType === "PAT" ? "PAT" : "Cookie header"}
            {authType === "SESSION_COOKIE" ? (
              <>
                <textarea
                  className="input mt-1.5 min-h-28 font-mono text-xs"
                  value={secret}
                  onChange={(e) => setSecret(e.target.value)}
                  placeholder={
                    editing
                      ? `Leave blank to keep ••••${connection?.masked_suffix || ""}`
                      : "JSESSIONID=…; seraph.rememberme=…"
                  }
                />
                <p className="mt-1 text-xs text-muted">
                  Log in to Confluence in the browser, then paste the full Cookie header from
                  DevTools → Application → Cookies (need <code>JSESSIONID</code> and{" "}
                  <code>seraph.rememberme</code>). A session id alone is treated as anonymous.
                </p>
              </>
            ) : (
              <input
                className="input mt-1.5"
                type="password"
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
                placeholder={
                  editing
                    ? `Leave blank to keep ••••${connection?.masked_suffix || ""}`
                    : undefined
                }
              />
            )}
          </label>
        </>
      ) : (
        <p className="mt-3 text-xs text-muted">
          Credentials stay on the agent host. Configure them in the agent environment.
        </p>
      )}
      <div className="mt-5 flex justify-end gap-2">
        <button type="button" className="secondary-button" onClick={onClose} disabled={busy}>
          Cancel
        </button>
        <button
          type="button"
          className="primary-button"
          disabled={!canSubmit}
          onClick={() => save.mutate()}
        >
          {busy ? <Loader2 size={16} className="animate-spin" /> : null}
          {editing && onSaved
            ? "Save & continue"
            : editing
              ? "Save"
              : onCreated
                ? "Save & continue"
                : "Create"}
        </button>
      </div>
    </>
  );

  if (embedded) return <div className="min-w-0">{fields}</div>;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
      <section className="max-h-[90vh] w-full max-w-md overflow-y-auto rounded-2xl border border-border bg-surface p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-lg font-semibold">
            {editing ? "Edit Confluence connection" : "Add Confluence connection"}
          </h3>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>
        {fields}
      </section>
    </div>
  );
}
