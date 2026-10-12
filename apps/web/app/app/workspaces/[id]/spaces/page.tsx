"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  BookOpen,
  Briefcase,
  Code2,
  FileText,
  Folder,
  Globe,
  LayoutGrid,
  List,
  Megaphone,
  Plus,
  Search,
  Share2,
  Shield,
  Star,
  Users,
  BarChart3,
  LoaderCircle,
  X,
} from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  clientApi,
  type Activity,
  type Space,
  type SpaceListResponse,
  type Workspace,
  type WorkspaceOverview,
} from "@/lib/api";
import { RoleBadge } from "@/components/workspaces";
import { BrandEmptyState, BrandLoading } from "@/components/brand";

const ICONS = {
  folder: Folder,
  book: BookOpen,
  users: Users,
  chart: BarChart3,
  code: Code2,
  megaphone: Megaphone,
  shield: Shield,
  globe: Globe,
  briefcase: Briefcase,
  "file-text": FileText,
} as const;

const ACCENTS = ["blue", "green", "violet", "amber", "rose", "cyan", "slate"] as const;

function SpaceIcon({ iconKey, accent }: { iconKey: string; accent: string }) {
  const Icon = ICONS[iconKey as keyof typeof ICONS] || Folder;
  return (
    <span className={`stat-icon stat-${accent === "cyan" ? "blue" : accent === "slate" ? "blue" : accent}`}>
      <Icon size={16} />
    </span>
  );
}

function CreateSpaceDialog({
  open,
  onClose,
  workspaceId,
}: {
  open: boolean;
  onClose: () => void;
  workspaceId: string;
}) {
  const client = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [iconKey, setIconKey] = useState("folder");
  const [accentKey, setAccentKey] = useState("blue");
  const mutation = useMutation({
    mutationFn: () =>
      clientApi<Space>(`/workspaces/${workspaceId}/spaces`, {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
          icon_key: iconKey,
          accent_key: accentKey,
        }),
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["spaces", workspaceId] });
      client.invalidateQueries({ queryKey: ["workspace-overview", workspaceId] });
      toast.success("Space created");
      setName("");
      setDescription("");
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
      <section className="w-full max-w-md rounded-2xl border border-border bg-surface p-5 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Create Space</h2>
          <button type="button" className="icon-button" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <label className="label">
          Space name *
          <input
            className="input mt-1.5"
            value={name}
            maxLength={100}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. DMS - Company Knowledge"
          />
        </label>
        <label className="label mt-3">
          Description
          <textarea
            className="input mt-1.5 resize-none"
            rows={3}
            maxLength={500}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        <p className="label mt-3">Icon</p>
        <div className="mt-1.5 flex flex-wrap gap-2">
          {Object.keys(ICONS).map((key) => (
            <button
              key={key}
              type="button"
              className={`rounded-lg border p-2 ${iconKey === key ? "border-primary" : "border-border"}`}
              onClick={() => setIconKey(key)}
            >
              <SpaceIcon iconKey={key} accent={accentKey} />
            </button>
          ))}
        </div>
        <p className="label mt-3">Color</p>
        <div className="mt-1.5 flex flex-wrap gap-2">
          {ACCENTS.map((a) => (
            <button
              key={a}
              type="button"
              className={`h-7 w-7 rounded-full border ${accentKey === a ? "border-primary ring-2 ring-primary/30" : "border-border"}`}
              style={{ background: `var(--accent-${a}, #93c5fd)` }}
              onClick={() => setAccentKey(a)}
              aria-label={a}
            />
          ))}
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={!name.trim() || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending && <LoaderCircle className="animate-spin" size={16} />}
            Create Space
          </button>
        </div>
      </section>
    </div>
  );
}

function ShareSpaceDialog({
  space,
  open,
  onClose,
}: {
  space: Space;
  open: boolean;
  onClose: () => void;
}) {
  const [role, setRole] = useState("VIEWER");
  const [confirmOwner, setConfirmOwner] = useState(false);
  const [url, setUrl] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: () =>
      clientApi<{ url?: string; token?: string }>(`/spaces/${space.id}/share-links`, {
        method: "POST",
        body: JSON.stringify({
          role,
          confirm_owner_role: role === "OWNER" ? confirmOwner : false,
        }),
      }),
    onSuccess: (data) => {
      setUrl(data.url || null);
      toast.success("Share link created");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
      <section className="w-full max-w-md rounded-2xl border border-border bg-surface p-5">
        <h2 className="text-lg font-semibold">Share &quot;{space.name}&quot;</h2>
        <label className="label mt-4">
          Access role
          <select className="input mt-1.5" value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="VIEWER">Viewer</option>
            <option value="EDITOR">Editor</option>
            <option value="OWNER">Owner</option>
          </select>
        </label>
        {role === "OWNER" ? (
          <label className="mt-3 flex gap-2 text-sm text-muted">
            <input
              type="checkbox"
              checked={confirmOwner}
              onChange={(e) => setConfirmOwner(e.target.checked)}
            />
            Owner access gives full control of this Space. Are you sure?
          </label>
        ) : null}
        {url ? (
          <div className="mt-3 flex gap-2">
            <input className="input min-w-0" readOnly value={url} />
            <button
              type="button"
              className="secondary-button"
              onClick={() => {
                void navigator.clipboard.writeText(url);
                toast.success("Link copied");
              }}
            >
              Copy
            </button>
          </div>
        ) : null}
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose}>
            Close
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={mutation.isPending || (role === "OWNER" && !confirmOwner)}
            onClick={() => mutation.mutate()}
          >
            Create Share Link
          </button>
        </div>
      </section>
    </div>
  );
}

export default function WorkspaceSpacesPage() {
  const { id } = useParams<{ id: string }>();
  const client = useQueryClient();
  const [tab, setTab] = useState("all");
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [owner, setOwner] = useState("all");
  const [status, setStatus] = useState("");
  const [view, setView] = useState<"list" | "grid">(() =>
    typeof window !== "undefined" && localStorage.getItem("kl-space-view") === "grid"
      ? "grid"
      : "list",
  );
  const [createOpen, setCreateOpen] = useState(false);
  const [createMenu, setCreateMenu] = useState(false);
  const [confluenceOpen, setConfluenceOpen] = useState(false);
  const [shareSpace, setShareSpace] = useState<Space | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 300);
    return () => clearTimeout(t);
  }, [q]);

  const queryKey = useMemo(
    () => ["spaces", id, tab, debouncedQ, owner, status],
    [id, tab, debouncedQ, owner, status],
  );

  const { data: workspace } = useQuery({
    queryKey: ["workspace", id],
    queryFn: () => clientApi<Workspace>(`/workspaces/${id}`),
  });
  const { data, isLoading, error } = useQuery({
    queryKey,
    queryFn: () => {
      const params = new URLSearchParams({ tab, page: "1", page_size: "20" });
      if (debouncedQ) params.set("q", debouncedQ);
      if (owner !== "all") params.set("owner", owner);
      if (status) params.set("status", status);
      return clientApi<SpaceListResponse>(`/workspaces/${id}/spaces?${params}`);
    },
  });
  const { data: overview } = useQuery({
    queryKey: ["workspace-overview", id],
    queryFn: () => clientApi<WorkspaceOverview>(`/workspaces/${id}/overview`),
  });
  const { data: activity = [] } = useQuery({
    queryKey: ["workspace-activity", id],
    queryFn: () => clientApi<Activity[]>(`/workspaces/${id}/activity?limit=5`),
  });

  const starMutation = useMutation({
    mutationFn: ({ spaceId, starred }: { spaceId: string; starred: boolean }) =>
      clientApi(`/spaces/${spaceId}/star`, { method: starred ? "DELETE" : "POST" }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["spaces", id] }),
  });

  const counts = data?.counts || { all: 0, mine: 0, shared: 0, archived: 0 };
  const items = data?.items || [];

  return (
    <div className="page-shell">
      <p className="text-sm text-muted">
        <Link href="/app/workspaces" className="hover:text-foreground">
          Workspaces
        </Link>
        {" > "}
        <Link href={`/app/workspaces/${id}`} className="hover:text-foreground">
          {workspace?.name || "…"}
        </Link>
        {" > "}
        <span className="text-foreground">Spaces</span>
      </p>

      <div className="mt-4 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="page-title flex items-center gap-2">
            <Folder className="text-violet-500" size={28} /> Spaces
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            Organize your knowledge into spaces to make it easy to find, share and collaborate.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="secondary-button" onClick={() => setConfluenceOpen(true)}>
            Import from Confluence
          </button>
          <div className="relative">
            <button
              type="button"
              className="primary-button"
              onClick={() => setCreateMenu((v) => !v)}
            >
              <Plus size={16} /> Create Space
            </button>
            {createMenu ? (
              <div className="absolute right-0 z-20 mt-2 w-56 rounded-xl border border-border bg-surface p-1 shadow-xl">
                <button
                  type="button"
                  className="menu-link w-full text-left"
                  onClick={() => {
                    setCreateMenu(false);
                    setCreateOpen(true);
                  }}
                >
                  Blank Space
                </button>
                <button type="button" disabled className="menu-link w-full text-left opacity-50">
                  From Confluence · Coming soon
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_320px]">
        <div>
          <div className="flex gap-1 overflow-x-auto border-b border-border">
            {(
              [
                ["all", "All Spaces", counts.all],
                ["mine", "My Spaces", counts.mine],
                ["shared", "Shared with me", counts.shared],
                ["archived", "Archived", counts.archived],
              ] as const
            ).map(([key, label, count]) => (
              <button
                key={key}
                type="button"
                className={`tab-button whitespace-nowrap ${tab === key ? "tab-active" : ""}`}
                onClick={() => setTab(key)}
              >
                {label} ({count ?? 0})
              </button>
            ))}
          </div>

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative min-w-0 flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={16} />
              <input
                className="input pl-9"
                placeholder="Search spaces..."
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
            </div>
            <select className="input w-auto" value={owner} onChange={(e) => setOwner(e.target.value)}>
              <option value="all">All owners</option>
              <option value="me">Me</option>
            </select>
            <select
              className="input w-auto"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="">All status</option>
              <option value="active">Active</option>
              <option value="archived">Archived</option>
            </select>
            <div className="flex rounded-lg border border-border p-1">
              <button
                type="button"
                className={`rounded-md p-1.5 ${view === "list" ? "bg-surface-muted text-primary" : "text-muted"}`}
                onClick={() => {
                  setView("list");
                  localStorage.setItem("kl-space-view", "list");
                }}
              >
                <List size={16} />
              </button>
              <button
                type="button"
                className={`rounded-md p-1.5 ${view === "grid" ? "bg-surface-muted text-primary" : "text-muted"}`}
                onClick={() => {
                  setView("grid");
                  localStorage.setItem("kl-space-view", "grid");
                }}
              >
                <LayoutGrid size={16} />
              </button>
            </div>
          </div>

          {isLoading ? (
            <BrandLoading label="Loading spaces…" className="mt-6" />
          ) : error ? (
            <div className="error-state mt-6">Unable to load Spaces</div>
          ) : items.length === 0 ? (
            <BrandEmptyState
              className="mt-6"
              mood="search"
              title="No Spaces yet"
              description="Create your first Space to organize documents, Confluence pages and AI knowledge."
              action={
                <button type="button" className="primary-button" onClick={() => setCreateOpen(true)}>
                  <Plus size={16} /> Create Space
                </button>
              }
            />
          ) : view === "list" ? (
            <div className="mt-4 overflow-hidden rounded-2xl border border-border bg-surface">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border bg-surface-muted/50 text-xs text-muted">
                  <tr>
                    <th className="px-4 py-3 font-medium">Space</th>
                    <th className="px-4 py-3 font-medium">Owner</th>
                    <th className="px-4 py-3 font-medium">Documents</th>
                    <th className="px-4 py-3 font-medium">Sources</th>
                    <th className="px-4 py-3 font-medium">Updated</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {items.map((space) => (
                    <tr key={space.id} className="border-b border-border last:border-0 hover:bg-surface-muted/40">
                      <td className="px-4 py-3">
                        <Link
                          href={`/app/workspaces/${id}/spaces/${space.id}/pages`}
                          className="flex items-start gap-3 text-left"
                        >
                          <SpaceIcon iconKey={space.icon_key} accent={space.accent_key} />
                          <span>
                            <span className="inline-flex items-center gap-1 font-medium">
                              {space.name}
                              {space.is_starred ? (
                                <Star size={12} className="fill-amber-400 text-amber-400" />
                              ) : null}
                            </span>
                            <span className="mt-0.5 block text-xs text-muted">
                              {space.description || "No description"}
                            </span>
                          </span>
                        </Link>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span>{space.owner?.display_name || space.owner?.email || "—"}</span>
                          <RoleBadge role={space.my_role} />
                        </div>
                      </td>
                      <td className="px-4 py-3">{space.document_count}</td>
                      <td className="px-4 py-3">{space.source_count}</td>
                      <td className="px-4 py-3 text-muted">
                        {new Intl.DateTimeFormat(undefined, {
                          dateStyle: "medium",
                        }).format(new Date(space.updated_at))}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex justify-end gap-1">
                          <button
                            type="button"
                            className="icon-button"
                            title={space.is_starred ? "Unstar" : "Star"}
                            onClick={() =>
                              starMutation.mutate({
                                spaceId: space.id,
                                starred: space.is_starred,
                              })
                            }
                          >
                            <Star
                              size={16}
                              className={space.is_starred ? "fill-amber-400 text-amber-400" : ""}
                            />
                          </button>
                          {space.my_role === "OWNER" ? (
                            <button
                              type="button"
                              className="icon-button"
                              onClick={() => setShareSpace(space)}
                            >
                              <Share2 size={16} />
                            </button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="border-t border-border px-4 py-3 text-xs text-muted">
                Showing 1 to {items.length} of {data?.total ?? 0} spaces
              </p>
            </div>
          ) : (
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {items.map((space) => (
                <Link
                  key={space.id}
                  href={`/app/workspaces/${id}/spaces/${space.id}/pages`}
                  className="rounded-2xl border border-border bg-surface p-4 text-left hover:border-primary/40"
                >
                  <div className="flex items-start justify-between">
                    <SpaceIcon iconKey={space.icon_key} accent={space.accent_key} />
                    {space.is_starred ? (
                      <Star size={14} className="fill-amber-400 text-amber-400" />
                    ) : null}
                  </div>
                  <p className="mt-3 font-medium">{space.name}</p>
                  <p className="mt-1 line-clamp-2 text-xs text-muted">
                    {space.description || "No description"}
                  </p>
                  <p className="mt-3 text-xs text-muted">
                    {space.document_count} Documents · {space.source_count} Sources
                  </p>
                </Link>
              ))}
            </div>
          )}
        </div>

        <aside className="space-y-4">
          <section className="rounded-2xl border border-border bg-surface p-4">
            <h2 className="font-semibold">Workspace Overview</h2>
            <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
              {[
                ["Spaces", overview?.space_count ?? 0],
                ["Documents", overview?.document_count ?? 0],
                ["Sources", overview?.source_count ?? 0],
                ["Storage", `${overview?.storage_bytes ?? 0} B`],
                ["Members", overview?.member_count ?? 0],
                ["Share Links", overview?.active_share_link_count ?? 0],
              ].map(([label, value]) => (
                <div key={String(label)} className="rounded-xl bg-surface-muted px-3 py-2">
                  <p className="text-xs text-muted">{label}</p>
                  <p className="mt-0.5 font-semibold">{value}</p>
                </div>
              ))}
            </div>
          </section>
          <section className="rounded-2xl border border-border bg-surface p-4">
            <h2 className="font-semibold">Recent Activity</h2>
            {activity.length === 0 ? (
              <p className="mt-3 text-sm text-muted">No activity yet.</p>
            ) : (
              <ul className="mt-3 space-y-3 text-sm">
                {activity.slice(0, 5).map((item) => (
                  <li key={item.id}>
                    <p className="capitalize">
                      {item.action.replaceAll("_", " ").toLowerCase()}
                    </p>
                    <p className="text-xs text-muted">
                      {item.workspace_name || "Workspace"} ·{" "}
                      {new Intl.DateTimeFormat(undefined, {
                        dateStyle: "medium",
                      }).format(new Date(item.created_at))}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section className="rounded-2xl border border-border bg-surface p-4">
            <h2 className="font-semibold">Storage Usage</h2>
            <p className="mt-3 text-2xl font-semibold">
              {overview?.storage_bytes ?? 0} B
            </p>
            <p className="mt-1 text-xs text-muted">
              Documents, source files and attachments will appear here after ingestion.
            </p>
          </section>
        </aside>
      </div>

      <CreateSpaceDialog open={createOpen} onClose={() => setCreateOpen(false)} workspaceId={id} />
      {shareSpace ? (
        <ShareSpaceDialog
          space={shareSpace}
          open={!!shareSpace}
          onClose={() => setShareSpace(null)}
        />
      ) : null}
      {confluenceOpen ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
          <section className="w-full max-w-md rounded-2xl border border-border bg-surface p-5">
            <h2 className="text-lg font-semibold">Confluence integration</h2>
            <p className="mt-2 text-sm text-muted">
              Confluence integration is not configured yet. You&apos;ll be able to connect Confluence
              Data Center in the next phase.
            </p>
            <button
              type="button"
              className="primary-button mt-5"
              onClick={() => setConfluenceOpen(false)}
            >
              Close
            </button>
          </section>
        </div>
      ) : null}
    </div>
  );
}
