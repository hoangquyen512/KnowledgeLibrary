"use client";

import { useQuery } from "@tanstack/react-query";
import { TopDocumentsTable } from "@/components/admin/TopDocumentsTable";
import { clientApi } from "@/lib/api";
import type { AdminTopDocuments } from "@/lib/admin-types";

export default function AdminDocumentsPage() {
  const { data, isError } = useQuery({
    queryKey: ["admin-top-documents-all"],
    queryFn: () => clientApi<AdminTopDocuments>("/admin/top-documents?limit=50"),
  });

  return (
    <section className="space-y-4">
      <div className="settings-card p-6 sm:p-8">
        <h2 className="text-lg font-semibold">Top documents</h2>
        <p className="mt-1 text-sm text-muted">
          Ranked by recorded page views. Historical views before tracking started are not estimated.
        </p>
      </div>
      <TopDocumentsTable data={data} isError={isError} showViewAll={false} />
    </section>
  );
}
