"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Activity as ActivityIcon,
  ArrowUpRight,
  BookOpen,
  FolderKanban,
  MessageSquare,
  Plus,
  Sparkles,
} from "lucide-react";
import { useState } from "react";
import { clientApi, type Activity, type Dashboard, type Space } from "@/lib/api";
import { BrandMascot } from "@/components/brand";
import { CreateSpaceDialog } from "@/components/spaces/CreateSpaceDialog";
import { SpaceIcon } from "@/components/spaces/SpaceIcon";

const tones = {
  blue: "stat-blue",
  green: "stat-green",
  violet: "stat-violet",
  amber: "stat-amber",
  rose: "stat-rose",
} as const;

export function StatCard({
  label,
  value,
  helper,
  tone = "blue",
  icon: Icon,
}: {
  label: string;
  value: string;
  helper?: string;
  tone?: keyof typeof tones;
  icon: typeof FolderKanban;
}) {
  return (
    <article className="stat-card relative overflow-hidden">
      <span className={`stat-icon absolute right-4 top-4 opacity-80 ${tones[tone]}`}>
        <Icon size={18} />
      </span>
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-2 text-3xl font-semibold tracking-tight">{value}</p>
      {helper ? <p className="mt-1 text-xs text-muted">{helper}</p> : null}
    </article>
  );
}

export function QuickActions({
  onCreate,
  onCreateSpace,
  createDisabled,
}: {
  onCreate: () => void;
  onCreateSpace: () => void;
  createDisabled?: boolean;
}) {
  const upcoming = ["Add Source", "Upload Files", "Sync Confluence", "Ask AI", "Shared Links"];
  return (
    <section className="rounded-2xl border border-border bg-surface p-5">
      <h2 className="font-semibold">Quick Actions</h2>
      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <button
          type="button"
          onClick={onCreate}
          disabled={createDisabled}
          className="quick-action"
          title={createDisabled ? "Workspace limit reached" : undefined}
        >
          <Plus size={18} className="text-primary" />
          Create Workspace
        </button>
        <button type="button" onClick={onCreateSpace} className="quick-action">
          <BookOpen size={18} className="text-emerald-500" />
          Create Space
        </button>
        <Link href="/app/settings/ai" className="quick-action">
          <Sparkles size={18} className="text-amber-500" />
          AI Settings
        </Link>
        {upcoming.map((label) => (
          <button
            key={label}
            type="button"
            disabled
            className="quick-action opacity-60"
            title="Available in next phase"
          >
            {label}
          </button>
        ))}
      </div>
    </section>
  );
}

function activityText(activity: Activity) {
  const action = activity.action.replaceAll("_", " ").toLowerCase();
  return activity.workspace_name ? `${action} · ${activity.workspace_name}` : action;
}

export function RecentActivity({ activity }: { activity: Activity[] }) {
  return (
    <section className="rounded-2xl border border-border bg-surface p-5">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Recent Activity</h2>
        <Link href="/app/shared" className="text-sm font-medium text-primary hover:underline">
          View all →
        </Link>
      </div>
      {activity.length ? (
        <div className="mt-3 divide-y divide-border">
          {activity.slice(0, 8).map((item) => (
            <div className="flex gap-3 py-3" key={item.id}>
              <span className="mt-0.5 rounded-lg bg-surface-muted p-2 text-muted">
                <ActivityIcon size={15} />
              </span>
              <div>
                <p className="text-sm capitalize">{activityText(item)}</p>
                <p className="mt-0.5 text-xs text-muted">
                  {new Intl.DateTimeFormat(undefined, {
                    dateStyle: "medium",
                    timeStyle: "short",
                  }).format(new Date(item.created_at))}
                </p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted">
          Activity will appear here when you create or share workspaces.
        </p>
      )}
    </section>
  );
}

function RecentSpacesSection({ onCreateSpace }: { onCreateSpace: () => void }) {
  const { data: spaces = [], isLoading } = useQuery({
    queryKey: ["recent-spaces"],
    queryFn: () => clientApi<Space[]>("/me/recent-spaces"),
  });

  return (
    <section className="rounded-2xl border border-border bg-surface p-5">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Recent Spaces</h2>
        <Link href="/app/recent" className="text-sm font-medium text-primary hover:underline">
          View all →
        </Link>
      </div>
      {isLoading ? (
        <p className="mt-4 text-sm text-muted">Loading spaces…</p>
      ) : spaces.length ? (
        <div className="mt-3 divide-y divide-border">
          {spaces.slice(0, 8).map((space) => (
            <Link
              key={space.id}
              href={`/app/workspaces/${space.workspace_id}/spaces/${space.id}/pages`}
              className="flex items-center justify-between gap-3 py-3"
            >
              <div className="flex min-w-0 items-center gap-3">
                <SpaceIcon iconKey={space.icon_key} accent={space.accent_key} size={16} />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{space.name}</p>
                  <p className="truncate text-xs text-muted">
                    {space.description || `${space.document_count} documents`}
                  </p>
                </div>
              </div>
              <span className="shrink-0 text-xs text-muted">{space.document_count} docs</span>
            </Link>
          ))}
        </div>
      ) : (
        <div className="empty-state mt-4 min-h-40">
          <p className="font-medium">No spaces yet</p>
          <p className="mt-1 max-w-sm text-sm text-muted">
            Create your first Space to organize your knowledge.
          </p>
          <button type="button" onClick={onCreateSpace} className="secondary-button mt-4">
            <Plus size={16} />
            Create Space
          </button>
        </div>
      )}
    </section>
  );
}

export function DashboardView({
  dashboard,
  onCreate,
}: {
  dashboard: Dashboard;
  onCreate: () => void;
}) {
  const [createSpaceOpen, setCreateSpaceOpen] = useState(false);
  const { summary } = dashboard;
  const remaining = Math.max(0, summary.workspace_limit - summary.owned_workspace_count);
  const atLimit = summary.owned_workspace_count >= summary.workspace_limit;
  const isEmpty = dashboard.recent_workspaces.length === 0;

  if (isEmpty) {
    return (
      <div className="flex w-full min-h-[60vh] flex-col items-center justify-center text-center">
        <BrandMascot mood="full" size={140} className="h-[140px] w-[140px] object-contain" />
        <h1 className="mt-6 text-3xl font-semibold tracking-tight">Welcome to Knowledge Library</h1>
        <p className="mt-3 max-w-md text-sm text-muted">
          Create your first Workspace to organize your company knowledge.
        </p>
        <button type="button" onClick={onCreate} className="primary-button mt-6">
          <Plus size={17} />
          Create Workspace
        </button>
      </div>
    );
  }

  return (
    <div className="page-shell space-y-6">
      <section className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="eyebrow">Overview</p>
          <h1 className="page-title">Dashboard</h1>
          <p className="mt-1 text-sm text-muted">
            Your workspaces, activity, and knowledge at a glance.
          </p>
        </div>
        <button type="button" onClick={onCreate} disabled={atLimit} className="primary-button">
          <Plus size={17} />
          Create Workspace
        </button>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard
          label="Workspaces"
          value={`${summary.owned_workspace_count} / ${summary.workspace_limit}`}
          helper={
            remaining > 0
              ? `You can create ${remaining} more.`
              : "Bạn đã đạt giới hạn 10 Workspace."
          }
          tone="blue"
          icon={FolderKanban}
        />
        <StatCard
          label="Spaces"
          value={String(summary.space_count)}
          helper="Across all workspaces."
          tone="green"
          icon={BookOpen}
        />
        <StatCard
          label="Sources"
          value={String(summary.source_count)}
          helper="Confluence, Files, Web."
          tone="violet"
          icon={ArrowUpRight}
        />
        <StatCard
          label="Documents"
          value={String(summary.document_count)}
          helper="Indexed & ready."
          tone="amber"
          icon={BookOpen}
        />
        <StatCard
          label="Conversations"
          value={String(summary.conversation_count_month)}
          helper="This month."
          tone="rose"
          icon={MessageSquare}
        />
      </section>

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <section className="rounded-2xl border border-border bg-surface p-5">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Workspaces</h2>
            <Link href="/app/workspaces" className="text-sm font-medium text-primary hover:underline">
              View all →
            </Link>
          </div>
          <div className="mt-3 divide-y divide-border">
            {dashboard.recent_workspaces.map((workspace) => (
              <Link
                href={`/app/workspaces/${workspace.id}`}
                className="flex items-center justify-between gap-3 py-3"
                key={workspace.id}
              >
                <div className="flex min-w-0 items-center gap-3">
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-blue-50 text-sm font-semibold text-primary dark:bg-blue-950">
                    {workspace.name.slice(0, 2).toUpperCase()}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{workspace.name}</p>
                    <p className="truncate text-xs text-muted">
                      {workspace.description || "Updated recently"}
                    </p>
                  </div>
                </div>
                <span className={`role-badge role-${(workspace.my_role || "viewer").toLowerCase()}`}>
                  {workspace.my_role || "Viewer"}
                </span>
              </Link>
            ))}
          </div>
          <button
            type="button"
            onClick={onCreate}
            disabled={atLimit}
            className="secondary-button mt-4 w-full"
          >
            <Plus size={16} />
            Create Workspace
          </button>
        </section>
        <div className="space-y-6">
          <QuickActions
            onCreate={onCreate}
            onCreateSpace={() => setCreateSpaceOpen(true)}
            createDisabled={atLimit}
          />
          <RecentActivity activity={dashboard.activity} />
        </div>
      </div>

      <RecentSpacesSection onCreateSpace={() => setCreateSpaceOpen(true)} />
      <CreateSpaceDialog open={createSpaceOpen} onClose={() => setCreateSpaceOpen(false)} />
    </div>
  );
}
