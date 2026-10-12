"use client";

import dynamic from "next/dynamic";

const AdminOverviewDashboard = dynamic(
  () =>
    import("@/components/admin/AdminOverview").then((mod) => mod.AdminOverviewDashboard),
  {
    ssr: false,
    loading: () => (
      <div className="space-y-4">
        <div className="h-16 animate-pulse rounded-2xl bg-surface-muted" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-36 animate-pulse rounded-2xl bg-surface-muted" />
          ))}
        </div>
      </div>
    ),
  },
);

export default function AdminOverviewPage() {
  return <AdminOverviewDashboard />;
}
