"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ConnectionFormDialog } from "@/components/confluence/ConnectionFormDialog";
import type { ConfluenceConnection } from "@/lib/confluence";
import { clientApi } from "@/lib/api";

type CfSpace = { key: string; name: string; id?: string; url?: string };

export function AddSourceDialog({
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
  const [phase, setPhase] = useState<"connect" | "browse">("connect");
  const [connectionId, setConnectionId] = useState("");
  const [draftConnection, setDraftConnection] = useState<ConfluenceConnection | null>(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<CfSpace | null>(null);

  useEffect(() => {
    if (!open) return;
    setPhase("connect");
    setConnectionId("");
    setDraftConnection(null);
    setQuery("");
    setSelected(null);
  }, [open]);

  const { data: spaces, isFetching } = useQuery({
    queryKey: ["cf-spaces", connectionId],
    queryFn: () =>
      clientApi<{ items: CfSpace[] }>(
        `/confluence-connections/${connectionId}/spaces?limit=50`,
      ),
    enabled: open && phase === "browse" && !!connectionId,
  });

  const filtered = (spaces?.items || []).filter((s) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return (
      (s.name || "").toLowerCase().includes(q) || (s.key || "").toLowerCase().includes(q)
    );
  });

  const attach = useMutation({
    mutationFn: () => {
      if (!selected || !connectionId) throw new Error("Select a Confluence space");
      return clientApi(`/spaces/${spaceId}/sources`, {
        method: "POST",
        body: JSON.stringify({
          connection_id: connectionId,
          name: selected.name,
          external_type: "SPACE",
          external_id: selected.id || selected.key,
          external_key: selected.key,
          external_url: selected.url || null,
          import_scope: "SPACE_TREE",
        }),
      });
    },
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["sources", spaceId] });
      client.invalidateQueries({ queryKey: ["confluence-connections", workspaceId] });
      toast.success("Source attached — ready to import.");
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const advanceAfterTest = async (conn: ConfluenceConnection) => {
    const toastId = toast.loading("Testing connection…");
    try {
      const tested = await clientApi<ConfluenceConnection>(
        `/confluence-connections/${conn.id}/test`,
        { method: "POST" },
      );
      client.invalidateQueries({ queryKey: ["confluence-connections", workspaceId] });
      setDraftConnection(tested);
      if (tested.status !== "ACTIVE") {
        throw new Error(tested.last_error || "Connection test failed. Check credentials and try again.");
      }
      setConnectionId(conn.id);
      setSelected(null);
      setQuery("");
      setPhase("browse");
      toast.success("Connection active. Choose a Confluence space.", { id: toastId });
    } catch (e) {
      setDraftConnection(conn);
      toast.error(e instanceof Error ? e.message : "Connection test failed.", { id: toastId });
    }
  };

  const handleCreated = async (conn: ConfluenceConnection) => {
    setDraftConnection(conn);
    await advanceAfterTest(conn);
  };

  if (!open) return null;

  const step = phase === "connect" ? 1 : 2;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
      <section className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-border bg-surface p-5 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Add Confluence Source</h2>
            <p className="mt-1 text-xs text-muted">
              Step {step} of 2 — {phase === "connect" ? "Connection" : "Choose space"}
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
            <ConnectionFormDialog
              open
              embedded
              workspaceId={workspaceId}
              connection={draftConnection}
              onClose={onClose}
              onCreated={handleCreated}
              onSaved={advanceAfterTest}
            />
          </>
        ) : (
          <>
            <p className="text-sm text-muted">
              Pick the Confluence space to import into this Knowledge Library space.
            </p>
            <label className="label mt-3">
              Search spaces
              <input
                className="input mt-1.5"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Filter by name or key"
              />
            </label>
            <div className="mt-3 max-h-56 overflow-auto rounded-xl border border-border">
              {isFetching ? (
                <p className="p-3 text-sm text-muted">Loading…</p>
              ) : filtered.length === 0 ? (
                <p className="p-3 text-sm text-muted">No spaces found.</p>
              ) : (
                filtered.map((s) => (
                  <button
                    key={s.key}
                    type="button"
                    className={`flex w-full flex-col px-3 py-2 text-left text-sm hover:bg-surface-muted ${
                      selected?.key === s.key ? "bg-surface-muted" : ""
                    }`}
                    onClick={() => setSelected(s)}
                  >
                    <span className="font-medium">{s.name}</span>
                    <span className="text-xs text-muted">{s.key}</span>
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
                disabled={!selected || attach.isPending}
                onClick={() => attach.mutate()}
              >
                {attach.isPending ? <Loader2 size={16} className="animate-spin" /> : null}
                Attach Source
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
