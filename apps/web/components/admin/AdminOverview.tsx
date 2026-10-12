"use client";

import { useQuery } from "@tanstack/react-query";
import { Download, FileText, FolderKanban, Layers, TrendingUp, Users } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { ActivityChart } from "@/components/admin/ActivityChart";
import { AdminDateRangePicker } from "@/components/admin/AdminDateRangePicker";
import { AdminMetricCard, AdminMetricCardSkeleton, AdminPanelError } from "@/components/admin/AdminMetricCard";
import { AIUsageChart } from "@/components/admin/AIUsageChart";
import { RecentAdminActivity } from "@/components/admin/RecentAdminActivity";
import { SourceDistributionChart } from "@/components/admin/SourceDistributionChart";
import { SystemHealthPanel } from "@/components/admin/SystemHealthPanel";
import { TopDocumentsTable } from "@/components/admin/TopDocumentsTable";
import { clientApi } from "@/lib/api";
import { defaultAdminRange, formatRangeLabel, queryRange } from "@/lib/admin-format";
import type {
  AdminActivitySeries,
  AdminAiPeriod,
  AdminAiUsage,
  AdminGranularity,
  AdminOverview,
  AdminRecentActivity,
  AdminSourceDistribution,
  AdminSystemHealth,
  AdminTopDocuments,
} from "@/lib/admin-types";

const KPI_META = [
  { key: "users", icon: Users, tone: "blue" as const },
  { key: "workspaces", icon: FolderKanban, tone: "green" as const },
  { key: "spaces", icon: Layers, tone: "violet" as const },
  { key: "documents", icon: FileText, tone: "amber" as const },
  { key: "ai_queries", icon: TrendingUp, tone: "cyan" as const },
];

export function AdminOverviewDashboard() {
  const initial = defaultAdminRange();
  const [range, setRange] = useState(initial);
  const [granularity, setGranularity] = useState<AdminGranularity>("daily");
  const [aiPeriod, setAiPeriod] = useState<AdminAiPeriod>("this_week");
  const rangeQs = queryRange(range.from, range.to);

  const overview = useQuery({
    queryKey: ["admin-overview", range.from, range.to],
    queryFn: () => clientApi<AdminOverview>(`/admin/overview?${rangeQs}`),
  });
  const activity = useQuery({
    queryKey: ["admin-activity", range.from, range.to, granularity],
    queryFn: () =>
      clientApi<AdminActivitySeries>(`/admin/activity-series?${rangeQs}&granularity=${granularity}`),
  });
  const sources = useQuery({
    queryKey: ["admin-sources"],
    queryFn: () => clientApi<AdminSourceDistribution>("/admin/source-distribution"),
  });
  const aiUsage = useQuery({
    queryKey: ["admin-ai-usage-chart", aiPeriod, range.from, range.to],
    queryFn: () => {
      const extra = aiPeriod === "custom" ? `&${rangeQs}` : "";
      return clientApi<AdminAiUsage>(`/admin/ai-usage?period=${aiPeriod}${extra}`);
    },
  });
  const recent = useQuery({
    queryKey: ["admin-recent-activity"],
    queryFn: () => clientApi<AdminRecentActivity>("/admin/recent-activity?limit=8"),
  });
  const topDocs = useQuery({
    queryKey: ["admin-top-documents"],
    queryFn: () => clientApi<AdminTopDocuments>("/admin/top-documents?limit=8"),
  });
  const health = useQuery({
    queryKey: ["admin-system-health"],
    queryFn: () => clientApi<AdminSystemHealth>("/admin/system-health"),
  });

  async function onExport() {
    try {
      const response = await fetch(`/api/v1/admin/export?${rangeQs}`, { credentials: "include" });
      if (!response.ok) throw new Error("Export failed");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `admin-overview-${range.from}-${range.to}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Could not export admin overview.");
    }
  }

  const comparisonLabel = overview.data
    ? formatRangeLabel(overview.data.previous_range_start_date, overview.data.previous_range_end_date)
    : "";

  return (
    <div className="space-y-5">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Admin Overview</h2>
          <p className="mt-1 text-sm text-muted">
            Real-time overview of platform usage and system activity.
          </p>
          <p className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
            <Link href="/app/settings/admin/users" className="hover:text-primary hover:underline">
              Users
            </Link>
            <Link href="/app/settings/admin/logs" className="hover:text-primary hover:underline">
              System logs
            </Link>
            <Link href="/app/settings/admin/usage" className="hover:text-primary hover:underline">
              AI usage
            </Link>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <AdminDateRangePicker from={range.from} to={range.to} onChange={setRange} />
          <button type="button" className="secondary-button" onClick={onExport}>
            <Download size={16} />
            Export
          </button>
        </div>
      </header>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {overview.isError ? (
          <div className="admin-panel sm:col-span-2 xl:col-span-5">
            <AdminPanelError message="Could not load KPI metrics." />
          </div>
        ) : overview.isLoading || !overview.data ? (
          KPI_META.map((item) => <AdminMetricCardSkeleton key={item.key} />)
        ) : (
          KPI_META.map((meta) => {
            const kpi = overview.data.kpis.find((k) => k.key === meta.key);
            if (!kpi) return null;
            return (
              <AdminMetricCard
                key={meta.key}
                kpi={kpi}
                icon={meta.icon}
                tone={meta.tone}
                comparisonLabel={comparisonLabel}
              />
            );
          })
        )}
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-4">
        <div className="xl:col-span-2">
          <ActivityChart
            data={activity.data}
            granularity={granularity}
            onGranularityChange={setGranularity}
            isError={activity.isError}
          />
        </div>
        <SourceDistributionChart data={sources.data} isError={sources.isError} />
        <AIUsageChart
          data={aiUsage.data}
          period={aiPeriod}
          onPeriodChange={setAiPeriod}
          isError={aiUsage.isError}
        />
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <RecentAdminActivity data={recent.data} isError={recent.isError} />
        <TopDocumentsTable data={topDocs.data} isError={topDocs.isError} />
        <SystemHealthPanel data={health.data} isError={health.isError} />
      </section>

      <p className="flex justify-end gap-3 text-xs text-muted">
        <span>All times are in UTC+7</span>
        <span>v0.1.0</span>
      </p>
    </div>
  );
}
