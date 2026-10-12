"use client";

import Link from "next/link";
import { FileText, Globe, HardDrive, Upload } from "lucide-react";
import { formatFullDate, formatNumber } from "@/lib/admin-format";
import type { AdminTopDocuments } from "@/lib/admin-types";
import { AdminPanelEmpty, AdminPanelError } from "./AdminMetricCard";

function sourceVisual(sourceType: string) {
  const type = sourceType.toUpperCase();
  if (type.includes("CONFLUENCE")) {
    return { label: "Confluence", icon: Globe, className: "text-blue-600 dark:text-blue-300" };
  }
  if (type.includes("UPLOAD") || type.includes("FILE")) {
    return { label: "Upload", icon: Upload, className: "text-amber-600 dark:text-amber-300" };
  }
  if (type.includes("DRIVE")) {
    return { label: "Google Drive", icon: HardDrive, className: "text-emerald-600 dark:text-emerald-300" };
  }
  return { label: type === "LOCAL" ? "Local" : sourceType, icon: FileText, className: "text-muted" };
}

export function TopDocumentsTable({
  data,
  isError,
  showViewAll = true,
}: {
  data?: AdminTopDocuments;
  isError?: boolean;
  showViewAll?: boolean;
}) {
  return (
    <section className="admin-panel flex min-h-[340px] flex-col overflow-hidden p-5">
      <header className="mb-3 flex items-center justify-between">
        <h3 className="text-base font-semibold">Top Documents</h3>
        {showViewAll ? (
          <Link href="/app/settings/admin/documents" className="text-sm font-medium text-primary hover:underline">
            View all
          </Link>
        ) : (
          <span />
        )}
      </header>
      {isError ? (
        <AdminPanelError message="Could not load top documents." />
      ) : !data ? (
        <div className="h-56 animate-pulse rounded-xl bg-surface-muted" />
      ) : data.items.length === 0 ? (
        <AdminPanelEmpty message="No document views recorded yet. Counts start from new page opens." />
      ) : (
        <div className="-mx-2 overflow-x-auto">
          <table className="w-full min-w-[520px] text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-2 py-2 font-medium">Document</th>
                <th className="px-2 py-2 font-medium">Workspace / Space</th>
                <th className="px-2 py-2 font-medium">Views</th>
                <th className="px-2 py-2 font-medium">Last viewed</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => {
                const src = sourceVisual(row.source_type);
                const Icon = src.icon;
                return (
                  <tr key={row.id} className="border-t border-border">
                    <td className="px-2 py-3">
                      <div className="flex items-start gap-2">
                        <Icon size={16} className={`mt-0.5 shrink-0 ${src.className}`} />
                        <div className="min-w-0">
                          <p className="truncate font-medium">{row.title}</p>
                          <p className="text-xs text-muted">{src.label}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-2 py-3 text-muted">
                      {row.workspace_name} / {row.space_name}
                    </td>
                    <td className="px-2 py-3 tabular-nums">{formatNumber(row.views)}</td>
                    <td className="px-2 py-3 text-muted">{formatFullDate(row.last_viewed_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
