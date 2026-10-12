"use client";

import Link from "next/link";
import {
  Download,
  FilePlus2,
  FolderPlus,
  Layers,
  Link2,
  Share2,
  Sparkles,
  UserPlus,
  type LucideIcon,
} from "lucide-react";
import { relativeTime } from "@/lib/admin-format";
import type { AdminRecentActivity } from "@/lib/admin-types";
import { AdminPanelEmpty, AdminPanelError } from "./AdminMetricCard";

const ACTION_ICON: Record<string, { icon: LucideIcon; tile: string }> = {
  CREATE_SPACE: { icon: Layers, tile: "bg-violet-100 text-violet-600 dark:bg-violet-950/80 dark:text-violet-300" },
  UPDATE_SPACE: { icon: Layers, tile: "bg-violet-100 text-violet-600 dark:bg-violet-950/80 dark:text-violet-300" },
  CREATE_WORKSPACE: { icon: FolderPlus, tile: "bg-blue-100 text-blue-600 dark:bg-blue-950/80 dark:text-blue-300" },
  ATTACH_SOURCE: { icon: Link2, tile: "bg-sky-100 text-sky-600 dark:bg-sky-950/80 dark:text-sky-300" },
  CREATE_CONFLUENCE_CONNECTION: { icon: Link2, tile: "bg-sky-100 text-sky-600 dark:bg-sky-950/80 dark:text-sky-300" },
  START_INGESTION: { icon: Download, tile: "bg-amber-100 text-amber-600 dark:bg-amber-950/80 dark:text-amber-300" },
  SHARE_SPACE: { icon: Share2, tile: "bg-emerald-100 text-emerald-600 dark:bg-emerald-950/80 dark:text-emerald-300" },
  SHARE_WORKSPACE: { icon: Share2, tile: "bg-emerald-100 text-emerald-600 dark:bg-emerald-950/80 dark:text-emerald-300" },
  REDEEM_SHARE_LINK: { icon: Share2, tile: "bg-emerald-100 text-emerald-600 dark:bg-emerald-950/80 dark:text-emerald-300" },
  CREATE_PAGE: { icon: FilePlus2, tile: "bg-orange-100 text-orange-600 dark:bg-orange-950/80 dark:text-orange-300" },
  CREATE_USER: { icon: UserPlus, tile: "bg-blue-100 text-blue-600 dark:bg-blue-950/80 dark:text-blue-300" },
  ASK_AI: { icon: Sparkles, tile: "bg-cyan-100 text-cyan-600 dark:bg-cyan-950/80 dark:text-cyan-300" },
};

export function RecentAdminActivity({
  data,
  isError,
}: {
  data?: AdminRecentActivity;
  isError?: boolean;
}) {
  return (
    <section className="admin-panel flex min-h-[340px] flex-col p-5">
      <header className="mb-3 flex items-center justify-between">
        <h3 className="text-base font-semibold">Recent Activity</h3>
        <Link href="/app/settings/admin/logs" className="text-sm font-medium text-primary hover:underline">
          View all
        </Link>
      </header>
      {isError ? (
        <AdminPanelError message="Could not load recent activity." />
      ) : !data ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-12 animate-pulse rounded-xl bg-surface-muted" />
          ))}
        </div>
      ) : data.items.length === 0 ? (
        <AdminPanelEmpty message="No recent admin activity." />
      ) : (
        <ul className="divide-y divide-border">
          {data.items.map((item) => {
            const visual = ACTION_ICON[item.action] || ACTION_ICON.CREATE_WORKSPACE;
            const Icon = visual.icon;
            return (
              <li key={item.id} className="flex gap-3 py-3 first:pt-1">
                <span className={`mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-full ${visual.tile}`}>
                  <Icon size={16} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium leading-5">{item.message}</p>
                  <p className="mt-0.5 text-xs text-muted">
                    {item.actor_name ? `by ${item.actor_name} · ` : ""}
                    {relativeTime(item.created_at)}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
