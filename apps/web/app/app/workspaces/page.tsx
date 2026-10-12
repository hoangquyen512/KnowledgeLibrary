"use client";

import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { CreateWorkspaceDialog } from "@/components/dialogs";
import { WorkspaceList } from "@/components/workspaces";
import { BrandLoading } from "@/components/brand";
import { useAppUser } from "@/components/app-user";
import { clientApi, type Dashboard, type Workspace } from "@/lib/api";

type Filter = "owned" | "shared" | "all";
const labels: Record<Filter, string> = { owned: "Owned", shared: "Shared", all: "All" };

export default function WorkspacesPage() {
  const user = useAppUser();
  const [filter, setFilter] = useState<Filter>("all");
  const [createOpen, setCreateOpen] = useState(false);
  const { data: workspaces = [], isLoading } = useQuery({
    queryKey: ["workspaces", filter, user.id],
    queryFn: () => clientApi<Workspace[]>(`/workspaces?filter=${filter}`),
  });
  const { data: dashboard } = useQuery({
    queryKey: ["dashboard", user.id],
    queryFn: () => clientApi<Dashboard>("/dashboard"),
  });
  return <div className="page-shell"><div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><p className="eyebrow">Library</p><h1 className="page-title">Workspaces</h1><p className="mt-1 text-sm text-muted">Organize sources and collaboration by team or project.</p></div><button className="primary-button" onClick={() => setCreateOpen(true)}><Plus size={17} />New workspace</button></div>
    <div className="mt-7 flex gap-1 border-b border-border">{(Object.keys(labels) as Filter[]).map((item) => <button key={item} onClick={() => setFilter(item)} className={`tab-button ${filter === item ? "tab-active" : ""}`}>{labels[item]}</button>)}</div>
    <div className="mt-5">{isLoading ? <BrandLoading label="Loading workspaces…" /> : <WorkspaceList workspaces={workspaces} emptyTitle={`No ${labels[filter].toLowerCase()} workspaces`} emptyDescription={filter === "shared" ? "Workspaces shared with you will appear here." : "Create a workspace to start bringing your knowledge together."} action={<button className="primary-button" onClick={() => setCreateOpen(true)}><Plus size={17} />Create workspace</button>} />}</div>
    <CreateWorkspaceDialog open={createOpen} onOpenChange={setCreateOpen} workspaceLimit={dashboard?.summary.workspace_limit} ownedCount={dashboard?.summary.owned_workspace_count} />
  </div>;
}
