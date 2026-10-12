"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { DashboardView } from "@/components/dashboard";
import { CreateWorkspaceDialog } from "@/components/dialogs";
import { useAppUser } from "@/components/app-user";
import { clientApi, type Dashboard } from "@/lib/api";

export default function AppHomePage() {
  const user = useAppUser();
  const [createOpen, setCreateOpen] = useState(false);
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard", user.id],
    queryFn: () => clientApi<Dashboard>("/dashboard"),
  });
  if (isLoading) return <div className="page-loading">Loading your library…</div>;
  if (error || !data) return <div className="error-state">We could not load your dashboard. Refresh the page to try again.</div>;
  return <><DashboardView dashboard={data} onCreate={() => setCreateOpen(true)} /><CreateWorkspaceDialog open={createOpen} onOpenChange={setCreateOpen} workspaceLimit={data.summary.workspace_limit} ownedCount={data.summary.owned_workspace_count} /></>;
}
