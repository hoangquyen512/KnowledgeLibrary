"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ApiError, clientApi } from "@/lib/api";
import {
  DEFAULT_JIRA_SCOPE,
  type JiraConnection,
  type JiraProject,
  type JiraScope,
} from "@/lib/sources";

type Phase = "connect" | "project" | "scope";

const SCOPE_FIELDS: { key: keyof JiraScope; label: string }[] = [
  { key: "issues", label: "Issues" },
  { key: "comments", label: "Comments" },
  { key: "attachments", label: "Attachments" },
  { key: "description", label: "Description" },
  { key: "acceptance_criteria", label: "Acceptance Criteria" },
  { key: "change_history", label: "Change history" },
];

export function AddJiraSourceDialog({
  open,
  onClose,
  workspaceId,
  spaceId,
}: {
  open: boolean;
  onClose: () => void;
  workspaceId: string;
  spaceId: string;
}) {
  const client = useQueryClient();
  const [phase, setPhase] = useState<Phase>("connect");
  const [mode, setMode] = useState<"existing" | "new">("new");
  const [connectionId, setConnectionId] = useState("");
  const [draftConnection, setDraftConnection] = useState<JiraConnection | null>(null);
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [username, setUsername] = useState("");
  const [secret, setSecret] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<JiraProject | null>(null);
  const [scope, setScope] = useState<JiraScope>({ ...DEFAULT_JIRA_SCOPE });
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setPhase("connect");
    setMode("new");
    setConnectionId("");
    setDraftConnection(null);
    setName("");
    setBaseUrl("");
    setUsername("");
    setSecret("");
    setQuery("");
    setSelected(null);
    setScope({ ...DEFAULT_JIRA_SCOPE });
    setTesting(false);
  }, [open]);

  const { data: connections = [], isFetching: loadingConnections } = useQuery({
    queryKey: ["jira-connections", workspaceId],
    queryFn: () => clientApi<JiraConnection[]>(`/workspaces/${workspaceId}/jira-connections`),
    enabled: open,
  });

  const { data: projects, isFetching: loadingProjects } = useQuery({
    queryKey: ["jira-projects", connectionId],
    queryFn: () =>
      clientApi<{ items?: JiraProject[] } | JiraProject[]>(
        `/jira-connections/${connectionId}/projects`,
      ),
    enabled: open && phase !== "connect" && !!connectionId,
  });

  const projectItems: JiraProject[] = Array.isArray(projects)
    ? projects
    : projects?.items || [];

  const filtered = projectItems.filter((p) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return (
      (p.name || "").toLowerCase().includes(q) || (p.key || "").toLowerCase().includes(q)
    );
  });

  const advanceAfterTest = async (conn: JiraConnection) => {
    setTesting(true);
    const toastId = toast.loading("Testing connection…");
    try {
      const tested = await clientApi<JiraConnection>(`/jira-connections/${conn.id}/test`, {
        method: "POST",
      });
      client.invalidateQueries({ queryKey: ["jira-connections", workspaceId] });
      setDraftConnection(tested);
      if (tested.status !== "ACTIVE") {
        throw new Error(tested.last_error || "Connection test failed. Check credentials and try again.");
      }
      setConnectionId(conn.id);
      setSelected(null);
      setQuery("");
      setPhase("project");
      toast.success("Connection active. Choose a Jira project.", { id: toastId });
    } catch (e) {
      setDraftConnection(conn);
      toast.error(e instanceof Error ? e.message : "Connection test failed.", { id: toastId });
    } finally {
      setTesting(false);
    }
  };

  const createConnection = useMutation({
    mutationFn: () =>
      clientApi<JiraConnection>(`/workspaces/${workspaceId}/jira-connections`, {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          base_url: baseUrl.trim(),
          auth_type: "PAT",
          username: username.trim() || undefined,
          secret: secret.trim(),
        }),
      }),
    onSuccess: async (conn) => {
      // Clear secret immediately — never keep raw token in UI after save.
      setSecret("");
      setDraftConnection(conn);
      client.invalidateQueries({ queryKey: ["jira-connections", workspaceId] });
      await advanceAfterTest(conn);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const attach = useMutation({
    mutationFn: () => {
      if (!selected || !connectionId) throw new Error("Select a Jira project");
      return clientApi(`/spaces/${spaceId}/sources/jira`, {
        method: "POST",
        body: JSON.stringify({
          connection_id: connectionId,
          name: selected.name,
          project_id: selected.id,
          project_key: selected.key,
          project_url: selected.url || null,
          scope,
        }),
      });
    },
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["sources", spaceId] });
      client.invalidateQueries({ queryKey: ["jira-connections", workspaceId] });
      toast.success("Jira source attached — ready to import.");
      onClose();
    },
    onError: (e: Error) => {
      const msg =
        e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Attach failed.";
      toast.error(msg);
    },
  });

  if (!open) return null;

  const step = phase === "connect" ? 1 : phase === "project" ? 2 : 3;
  const stepLabel =
    phase === "connect" ? "Connection" : phase === "project" ? "Choose project" : "Configure scope";
  const busy = createConnection.isPending || testing || attach.isPending;
  const canCreate =
    name.trim() && baseUrl.trim() && secret.trim() && !createConnection.isPending && !testing;
  const canUseExisting = !!connectionId && !testing;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
      <section className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-border bg-surface p-5 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Add Jira Source</h2>
            <p className="mt-1 text-xs text-muted">
              Step {step} of 3 — {stepLabel}
            </p>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        {phase === "connect" ? (
          <>
            {draftConnection && draftConnection.status !== "ACTIVE" ? (
              <p className="mb-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
                Test failed{draftConnection.last_error ? `: ${draftConnection.last_error}` : ""}.
                Update credentials and continue.
              </p>
            ) : null}

            {connections.length > 0 ? (
              <div className="mb-3 flex gap-2">
                <button
                  type="button"
                  className={`secondary-button h-8 px-2.5 text-xs ${mode === "existing" ? "ring-1 ring-primary" : ""}`}
                  onClick={() => setMode("existing")}
                >
                  Use existing
                </button>
                <button
                  type="button"
                  className={`secondary-button h-8 px-2.5 text-xs ${mode === "new" ? "ring-1 ring-primary" : ""}`}
                  onClick={() => setMode("new")}
                >
                  New connection
                </button>
              </div>
            ) : null}

            {mode === "existing" && connections.length > 0 ? (
              <>
                <label className="label">
                  Connection
                  <select
                    className="input mt-1.5"
                    value={connectionId}
                    onChange={(e) => setConnectionId(e.target.value)}
                    disabled={loadingConnections || busy}
                  >
                    <option value="">Select connection…</option>
                    {connections.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} (••••{c.masked_suffix || ""}) — {c.status}
                      </option>
                    ))}
                  </select>
                </label>
                <p className="mt-2 text-xs text-muted">
                  Token is stored encrypted. Only a masked suffix is shown.
                </p>
                <div className="mt-5 flex justify-end gap-2">
                  <button type="button" className="secondary-button" onClick={onClose} disabled={busy}>
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="primary-button"
                    disabled={!canUseExisting}
                    onClick={() => {
                      const conn = connections.find((c) => c.id === connectionId);
                      if (conn) void advanceAfterTest(conn);
                    }}
                  >
                    {testing ? <Loader2 size={16} className="animate-spin" /> : null}
                    Test & continue
                  </button>
                </div>
              </>
            ) : (
              <>
                <p className="text-xs text-muted">
                  Enter Jira credentials. We test the connection before you pick a project. The token
                  is never shown again after save.
                </p>
                <label className="label mt-3">
                  Connection name
                  <input
                    className="input mt-1.5"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Company Jira"
                  />
                </label>
                <label className="label mt-3">
                  Base URL
                  <input
                    className="input mt-1.5"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    placeholder="https://jira.company.com"
                  />
                </label>
                <label className="label mt-3">
                  Auth type
                  <select className="input mt-1.5" value="PAT" disabled>
                    <option value="PAT">Personal Access Token</option>
                  </select>
                </label>
                <label className="label mt-3">
                  Username <span className="font-normal text-muted">(optional)</span>
                  <input
                    className="input mt-1.5"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    autoComplete="username"
                  />
                </label>
                <label className="label mt-3">
                  Token / secret
                  <input
                    className="input mt-1.5"
                    type="password"
                    value={secret}
                    onChange={(e) => setSecret(e.target.value)}
                    autoComplete="new-password"
                  />
                </label>
                <div className="mt-5 flex justify-end gap-2">
                  <button type="button" className="secondary-button" onClick={onClose} disabled={busy}>
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="primary-button"
                    disabled={!canCreate}
                    onClick={() => createConnection.mutate()}
                  >
                    {busy ? <Loader2 size={16} className="animate-spin" /> : null}
                    Save & continue
                  </button>
                </div>
              </>
            )}
          </>
        ) : null}

        {phase === "project" ? (
          <>
            <p className="text-sm text-muted">
              Pick the Jira project to import into this Knowledge Library space.
            </p>
            <label className="label mt-3">
              Search projects
              <input
                className="input mt-1.5"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Filter by name or key"
              />
            </label>
            <div className="mt-3 max-h-56 overflow-auto rounded-xl border border-border">
              {loadingProjects ? (
                <p className="p-3 text-sm text-muted">Loading…</p>
              ) : filtered.length === 0 ? (
                <p className="p-3 text-sm text-muted">No projects found.</p>
              ) : (
                filtered.map((p) => (
                  <button
                    key={p.id || p.key}
                    type="button"
                    className={`flex w-full flex-col px-3 py-2 text-left text-sm hover:bg-surface-muted ${
                      selected?.key === p.key ? "bg-surface-muted" : ""
                    }`}
                    onClick={() => setSelected(p)}
                  >
                    <span className="font-medium">{p.name}</span>
                    <span className="text-xs text-muted">{p.key}</span>
                  </button>
                ))
              )}
            </div>
            {selected ? (
              <div className="mt-3 rounded-xl border border-border bg-surface-muted px-3 py-2 text-sm">
                <span className="text-muted">Selected: </span>
                <span className="font-medium">{selected.name}</span>
                <span className="text-muted"> ({selected.key})</span>
              </div>
            ) : null}
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                className="secondary-button"
                onClick={() => {
                  setPhase("connect");
                  setSelected(null);
                }}
              >
                Back
              </button>
              <button
                type="button"
                className="primary-button"
                disabled={!selected}
                onClick={() => setPhase("scope")}
              >
                Continue
              </button>
            </div>
          </>
        ) : null}

        {phase === "scope" ? (
          <>
            <p className="text-sm text-muted">Choose what to import from {selected?.name}.</p>
            <ul className="mt-3 space-y-2">
              {SCOPE_FIELDS.map((field) => (
                <li key={field.key}>
                  <label className="flex cursor-pointer items-center gap-2.5 rounded-xl border border-border bg-surface px-3 py-2.5 text-sm hover:bg-surface-muted">
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-primary"
                      checked={scope[field.key]}
                      onChange={(e) =>
                        setScope((prev) => ({ ...prev, [field.key]: e.target.checked }))
                      }
                    />
                    <span>{field.label}</span>
                  </label>
                </li>
              ))}
            </ul>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setPhase("project")}
                disabled={attach.isPending}
              >
                Back
              </button>
              <button
                type="button"
                className="primary-button"
                disabled={!selected || !scope.issues || attach.isPending}
                onClick={() => attach.mutate()}
              >
                {attach.isPending ? <Loader2 size={16} className="animate-spin" /> : null}
                Attach Source
              </button>
            </div>
          </>
        ) : null}
      </section>
    </div>
  );
}
