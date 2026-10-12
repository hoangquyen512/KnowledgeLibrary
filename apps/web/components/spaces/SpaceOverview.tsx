"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Database,
  Eye,
  FileText,
  FolderOpen,
  FolderPlus,
  LayoutTemplate,
  MessageSquare,
  Network,
  RefreshCw,
  Settings,
  Share2,
  Sparkles,
  Star,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { AddSourceDialog } from "@/components/confluence/AddSourceDialog";
import { SpaceIcon } from "@/components/spaces/SpaceIcon";
import { RoleBadge } from "@/components/workspaces";
import { relativeTime, formatNumber } from "@/lib/admin-format";
import { clientApi, type Activity as ActivityRow, type Member, type Space } from "@/lib/api";
import { mapSourceBadge, type SourceRow } from "@/lib/import-status";
import type { PageTreeNode } from "@/lib/pages";

const SOURCE_COLORS = ["#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444", "#06b6d4"];

function sourceTypeLabel(s: SourceRow) {
  return s.external_type || s.type || "Source";
}

function syncStatusBadge(s: SourceRow) {
  if (s.status === "IMPORTING") return mapSourceBadge("IMPORTING");
  if (s.last_sync_status === "FAILED" || s.status === "FAILED") {
    return { label: "Needs attention", className: "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-200" };
  }
  if (s.status === "READY" || s.last_sync_status === "SUCCESS" || s.last_sync_status === "OK") {
    return { label: "Synced", className: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-200" };
  }
  return mapSourceBadge(s.status);
}

function activityLabel(a: ActivityRow) {
  const meta = a.metadata || {};
  const title = typeof meta.title === "string" ? meta.title : null;
  const name = typeof meta.name === "string" ? meta.name : null;
  const target = title || name;
  const action = a.action.replace(/_/g, " ").toLowerCase();
  if (target) return `${action}: ${target}`;
  return action.charAt(0).toUpperCase() + action.slice(1);
}

function DonutChart({
  segments,
  totalLabel,
  totalValue,
}: {
  segments: { label: string; value: number; color: string }[];
  totalLabel: string;
  totalValue: number;
}) {
  const sum = segments.reduce((a, s) => a + s.value, 0) || 1;
  const r = 42;
  const c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div className="flex items-center gap-4">
      <div className="relative h-28 w-28 shrink-0">
        <svg viewBox="0 0 100 100" className="-rotate-90 h-full w-full">
          <circle cx="50" cy="50" r={r} fill="none" stroke="currentColor" className="text-border" strokeWidth="12" />
          {segments.map((seg) => {
            const len = (seg.value / sum) * c;
            const el = (
              <circle
                key={seg.label}
                cx="50"
                cy="50"
                r={r}
                fill="none"
                stroke={seg.color}
                strokeWidth="12"
                strokeDasharray={`${len} ${c - len}`}
                strokeDashoffset={-offset}
                strokeLinecap="butt"
              />
            );
            offset += len;
            return el;
          })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <p className="text-[10px] text-muted">{totalLabel}</p>
          <p className="text-sm font-semibold tabular-nums">{formatNumber(totalValue)}</p>
        </div>
      </div>
      <ul className="min-w-0 space-y-1.5 text-xs">
        {segments.map((seg) => (
          <li key={seg.label} className="flex items-center gap-2">
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: seg.color }} />
            <span className="truncate text-muted">{seg.label}</span>
            <span className="ml-auto font-medium tabular-nums">
              {Math.round((seg.value / sum) * 100)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function GrowthSparkline({ points }: { points: number[] }) {
  const max = Math.max(...points, 1);
  const min = Math.min(...points, 0);
  const span = max - min || 1;
  const w = 220;
  const h = 72;
  const coords = points.map((p, i) => {
    const x = (i / Math.max(points.length - 1, 1)) * w;
    const y = h - ((p - min) / span) * (h - 8) - 4;
    return `${x},${y}`;
  });
  const line = coords.join(" ");
  const area = `0,${h} ${line} ${w},${h}`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-20 w-full" preserveAspectRatio="none">
      <defs>
        <linearGradient id="growthFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <polygon points={area} fill="url(#growthFill)" />
      <polyline points={line} fill="none" stroke="#3b82f6" strokeWidth="2" />
    </svg>
  );
}

function MetricCard({
  label,
  value,
  helper,
  icon: Icon,
  tone,
}: {
  label: string;
  value: string;
  helper?: string;
  icon: typeof FileText;
  tone: string;
}) {
  return (
    <article className="rounded-2xl border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium text-muted">{label}</p>
        <span className={`stat-icon ${tone}`}>
          <Icon size={14} />
        </span>
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
      {helper ? <p className="mt-1 text-[11px] text-muted">{helper}</p> : null}
    </article>
  );
}

export function SpaceOverview({
  workspaceId,
  spaceId,
}: {
  workspaceId: string;
  spaceId: string;
}) {
  const client = useQueryClient();
  const [addSourceOpen, setAddSourceOpen] = useState(false);
  const base = `/app/workspaces/${workspaceId}/spaces/${spaceId}`;

  const { data: space, isLoading, error } = useQuery({
    queryKey: ["space", spaceId],
    queryFn: () => clientApi<Space>(`/spaces/${spaceId}`),
    refetchInterval: 15_000,
  });

  const { data: sources = [] } = useQuery({
    queryKey: ["sources", spaceId],
    queryFn: () => clientApi<SourceRow[]>(`/spaces/${spaceId}/sources`),
    enabled: !!spaceId,
  });

  const { data: members = [] } = useQuery({
    queryKey: ["space-members", spaceId],
    queryFn: () => clientApi<Member[]>(`/spaces/${spaceId}/members`),
    enabled: !!spaceId,
  });

  const { data: pageTree = [] } = useQuery({
    queryKey: ["page-tree", spaceId, "root"],
    queryFn: () => clientApi<PageTreeNode[]>(`/spaces/${spaceId}/pages/tree`),
    enabled: !!spaceId,
  });

  const { data: activity = [] } = useQuery({
    queryKey: ["workspace-activity", workspaceId, "space-overview"],
    queryFn: () =>
      clientApi<ActivityRow[]>(`/workspaces/${workspaceId}/activity?limit=8`),
    enabled: !!workspaceId,
  });

  const starMutation = useMutation({
    mutationFn: () =>
      clientApi(`/spaces/${spaceId}/star`, {
        method: space?.is_starred ? "DELETE" : "POST",
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["space", spaceId] });
      toast.success(space?.is_starred ? "Removed from Starred" : "Added to Starred");
    },
  });

  const syncAll = useMutation({
    mutationFn: async () => {
      const syncable = sources.filter((s) => s.status === "READY" || s.sync_enabled);
      if (!syncable.length) throw new Error("No sources ready to sync");
      await Promise.all(
        syncable.map((s) => clientApi(`/sources/${s.id}/sync`, { method: "POST" })),
      );
    },
    onSuccess: () => {
      toast.success("Sync started");
      client.invalidateQueries({ queryKey: ["sources", spaceId] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const metrics = useMemo(() => {
    const pages = space?.document_count ?? 0;
    const attachments = sources.reduce((n, s) => n + (s.attachment_count || 0), 0);
    const activeSources = sources.filter(
      (s) => s.status === "READY" || s.status === "IMPORTING",
    ).length;
    const lastSync = sources
      .map((s) => s.last_sync_at)
      .filter(Boolean)
      .sort()
      .at(-1) as string | undefined;
    const editors = members.filter((m) => m.role === "OWNER" || m.role === "EDITOR").length;
    return { pages, attachments, activeSources, lastSync, editors };
  }, [space, sources, members]);

  const sourceMix = useMemo(() => {
    const map = new Map<string, number>();
    for (const s of sources) {
      const key = sourceTypeLabel(s);
      map.set(key, (map.get(key) || 0) + Math.max(s.document_count || 0, 1));
    }
    const entries = [...map.entries()].sort((a, b) => b[1] - a[1]);
    if (!entries.length) {
      return [{ label: "No sources", value: 1, color: "#94a3b8" }];
    }
    return entries.map(([label, value], i) => ({
      label,
      value,
      color: SOURCE_COLORS[i % SOURCE_COLORS.length],
    }));
  }, [sources]);

  const growthPoints = useMemo(() => {
    const n = Math.max(metrics.pages, 1);
    return Array.from({ length: 12 }, (_, i) => Math.round((n * (i + 1)) / 12));
  }, [metrics.pages]);

  if (isLoading) return <div className="page-loading p-6">Loading overview…</div>;
  if (error || !space) {
    return <div className="error-state m-6">You don&apos;t have access to this Space.</div>;
  }

  const canAdd = space.my_role !== "VIEWER" && space.status !== "ARCHIVED";
  const topPages = pageTree.slice(0, 6);

  return (
    <div className="h-full min-h-0 flex-1 overflow-y-auto bg-[var(--background)] p-4 sm:p-6">
      {/* Header */}
      <header className="rounded-2xl border border-border bg-surface p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex min-w-0 gap-4">
            <SpaceIcon iconKey={space.icon_key} accent={space.accent_key} size={28} className="!h-14 !w-14" />
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl font-semibold tracking-tight">{space.name}</h1>
                <RoleBadge role={space.my_role} />
                <span
                  className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                    space.status === "ARCHIVED"
                      ? "bg-surface-muted text-muted"
                      : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-200"
                  }`}
                >
                  {space.status === "ARCHIVED" ? "Archived" : "Active"}
                </span>
              </div>
              <p className="mt-2 max-w-2xl text-sm text-muted">
                {space.description || "No description yet. Add one in Settings."}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="secondary-button" onClick={() => starMutation.mutate()}>
              <Star
                size={16}
                className={space.is_starred ? "fill-amber-400 text-amber-400" : ""}
              />
              Star
            </button>
            {space.my_role === "OWNER" ? (
              <Link href={`${base}/access`} className="secondary-button">
                <Share2 size={16} /> Share / Access
              </Link>
            ) : null}
            <Link href={`${base}/settings`} className="secondary-button">
              <Settings size={16} /> Settings
            </Link>
            <button
              type="button"
              className="primary-button"
              onClick={() => setAddSourceOpen(true)}
              disabled={!canAdd}
            >
              <FolderPlus size={16} /> Add Source
            </button>
          </div>
        </div>
      </header>

      {/* Metrics */}
      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <MetricCard
          label="Pages"
          value={formatNumber(metrics.pages)}
          helper={`${pageTree.length} top-level`}
          icon={FileText}
          tone="stat-blue"
        />
        <MetricCard
          label="Attachments"
          value={formatNumber(metrics.attachments)}
          helper="Across sources"
          icon={FolderOpen}
          tone="stat-green"
        />
        <MetricCard
          label="Sources"
          value={formatNumber(sources.length)}
          helper={`${metrics.activeSources} active`}
          icon={Database}
          tone="stat-violet"
        />
        <MetricCard
          label="Last Sync"
          value={metrics.lastSync ? relativeTime(metrics.lastSync) : "Never"}
          helper={metrics.lastSync ? new Date(metrics.lastSync).toLocaleString() : "No sync yet"}
          icon={RefreshCw}
          tone="stat-blue"
        />
        <MetricCard
          label="Members"
          value={formatNumber(members.length)}
          helper={`${metrics.editors} editors`}
          icon={Users}
          tone="stat-amber"
        />
        <MetricCard
          label="Ask AI"
          value="—"
          helper="Open Ask AI for this space"
          icon={MessageSquare}
          tone="stat-violet"
        />
      </div>

      {/* Coverage + Quick actions */}
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <section className="rounded-2xl border border-border bg-surface p-5 lg:col-span-2">
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-semibold">Knowledge coverage</h2>
            <span className="text-xs text-muted">Indexed content</span>
          </div>
          <div className="mt-4 grid gap-6 md:grid-cols-2">
            <div>
              <p className="mb-2 text-xs font-medium text-muted">Source mix</p>
              <DonutChart
                segments={sourceMix}
                totalLabel="Pages"
                totalValue={metrics.pages || sources.length}
              />
            </div>
            <div>
              <p className="mb-2 text-xs font-medium text-muted">Content growth</p>
              <GrowthSparkline points={growthPoints} />
              <p className="mt-1 text-[11px] text-muted">Projection based on current page count</p>
            </div>
          </div>
        </section>

        <section className="rounded-2xl border border-border bg-surface p-5">
          <h2 className="font-semibold">Quick actions</h2>
          <div className="mt-4 flex flex-col gap-2">
            <Link
              href={`${base}/ask`}
              className="flex items-center gap-2 rounded-xl border border-violet-200 bg-gradient-to-r from-violet-50 to-blue-50 px-3 py-2.5 text-sm font-semibold text-violet-800 transition hover:border-violet-300 dark:border-violet-900/50 dark:from-violet-950/40 dark:to-blue-950/30 dark:text-violet-100"
            >
              <Sparkles size={16} /> Ask AI
            </Link>
            <div className="grid grid-cols-2 gap-2">
              <Link href={`${base}/pages`} className="secondary-button justify-center text-xs">
                <FileText size={14} /> Open Pages
              </Link>
              <button
                type="button"
                className="secondary-button justify-center text-xs"
                disabled={!canAdd || syncAll.isPending || sources.length === 0}
                onClick={() => syncAll.mutate()}
              >
                <RefreshCw size={14} /> Sync Sources
              </button>
              <Link
                href={`${base}/studio`}
                className="secondary-button justify-center text-xs"
              >
                <LayoutTemplate size={14} /> Presentation
              </Link>
              <Link
                href={`${base}/studio?type=mindmap`}
                className="secondary-button justify-center text-xs"
              >
                <Network size={14} /> Mind Map
              </Link>
            </div>
          </div>
        </section>
      </div>

      {/* Sources / Top pages / Activity */}
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <section className="rounded-2xl border border-border bg-surface p-5">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Sources</h2>
            <Link href={`${base}/sources`} className="text-xs font-medium text-primary hover:underline">
              View all
            </Link>
          </div>
          <ul className="mt-3 divide-y divide-border">
            {sources.length === 0 ? (
              <li className="py-6 text-center text-sm text-muted">No sources yet</li>
            ) : (
              sources.slice(0, 5).map((s) => {
                const badge = syncStatusBadge(s);
                return (
                  <li key={s.id} className="flex items-start gap-3 py-3">
                    <span className="stat-icon stat-violet mt-0.5">
                      <Database size={14} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{s.name}</p>
                      <p className="text-[11px] text-muted">
                        {formatNumber(s.document_count || 0)} pages
                        {s.attachment_count
                          ? ` · ${formatNumber(s.attachment_count)} attachments`
                          : ""}
                      </p>
                    </div>
                    <div className="text-right">
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${badge.className}`}>
                        {badge.label}
                      </span>
                      <p className="mt-1 text-[10px] text-muted">
                        {s.last_sync_at ? relativeTime(s.last_sync_at) : "—"}
                      </p>
                    </div>
                  </li>
                );
              })
            )}
          </ul>
          {canAdd ? (
            <button
              type="button"
              className="mt-2 text-xs font-medium text-primary hover:underline"
              onClick={() => setAddSourceOpen(true)}
            >
              + Add Source
            </button>
          ) : null}
        </section>

        <section className="rounded-2xl border border-border bg-surface p-5">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Top pages</h2>
            <Link href={`${base}/pages`} className="text-xs font-medium text-primary hover:underline">
              View all
            </Link>
          </div>
          <ul className="mt-3 divide-y divide-border">
            {topPages.length === 0 ? (
              <li className="py-6 text-center text-sm text-muted">No pages yet</li>
            ) : (
              topPages.map((p) => (
                <li key={p.id}>
                  <Link
                    href={`${base}/pages/${p.id}`}
                    className="flex items-center gap-3 py-3 transition hover:bg-surface-muted/50"
                  >
                    <span className="stat-icon stat-blue">
                      <FileText size={14} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{p.title}</p>
                      <p className="text-[11px] text-muted">
                        {p.child_count ? `${p.child_count} children` : "Page"}
                      </p>
                    </div>
                    <span className="flex items-center gap-1 text-[11px] text-muted">
                      <Eye size={12} />
                      {p.has_children ? p.child_count : "—"}
                    </span>
                  </Link>
                </li>
              ))
            )}
          </ul>
        </section>

        <section className="rounded-2xl border border-border bg-surface p-5">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Recent activity</h2>
          </div>
          <ul className="mt-3 space-y-3">
            {activity.length === 0 ? (
              <li className="py-6 text-center text-sm text-muted">No recent activity</li>
            ) : (
              activity.slice(0, 6).map((a) => (
                <li key={a.id} className="flex gap-3">
                  <span className="stat-icon stat-amber mt-0.5">
                    <Activity size={14} />
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm leading-snug">{activityLabel(a)}</p>
                    <p className="mt-0.5 text-[11px] text-muted">{relativeTime(a.created_at)}</p>
                  </div>
                </li>
              ))
            )}
          </ul>
        </section>
      </div>

      {/* Ask AI + Page structure */}
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <section className="relative overflow-hidden rounded-2xl border border-border bg-surface p-5 lg:col-span-1">
          <span className="rounded-full bg-violet-50 px-2 py-0.5 text-[10px] font-semibold text-violet-700 dark:bg-violet-950/40 dark:text-violet-200">
            AI Generated
          </span>
          <p className="mt-3 text-sm leading-relaxed text-muted">
            {space.description
              ? `Summary of ${space.name}: ${space.description}`
              : `${space.name} currently has ${formatNumber(metrics.pages)} pages across ${sources.length} source${sources.length === 1 ? "" : "s"}. Ask AI to explore this knowledge base.`}
          </p>
          <div className="pointer-events-none absolute -bottom-4 -right-4 opacity-20">
            <Sparkles size={88} className="text-violet-500" />
          </div>
          <Link
            href={`${base}/ask`}
            className="primary-button relative mt-5 w-full justify-center text-xs"
          >
            Ask AI about this space
          </Link>
        </section>

        <section className="rounded-2xl border border-border bg-surface p-5 lg:col-span-2">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Page structure</h2>
            <Link href={`${base}/pages`} className="text-xs font-medium text-primary hover:underline">
              Open Pages
            </Link>
          </div>
          <div className="mt-4 overflow-x-auto">
            {pageTree.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted">No page tree yet</p>
            ) : (
              <ul className="flex min-w-max gap-3 pb-2">
                <li className="rounded-xl border border-primary/30 bg-blue-50/60 px-3 py-2 text-sm font-semibold dark:bg-blue-950/30">
                  {space.name}
                </li>
                {pageTree.slice(0, 8).map((node) => (
                  <li key={node.id} className="flex items-start gap-2">
                    <span className="mt-3 h-px w-4 bg-border" />
                    <Link
                      href={`${base}/pages/${node.id}`}
                      className="rounded-xl border border-border bg-surface-muted/40 px-3 py-2 text-sm transition hover:border-primary/40 hover:bg-surface"
                    >
                      <span className="font-medium">{node.title}</span>
                      {node.child_count > 0 ? (
                        <span className="mt-0.5 block text-[11px] text-muted">
                          {node.child_count} pages
                        </span>
                      ) : null}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>

      <AddSourceDialog
        open={addSourceOpen}
        onClose={() => setAddSourceOpen(false)}
        workspaceId={workspaceId}
        spaceId={spaceId}
      />
    </div>
  );
}
