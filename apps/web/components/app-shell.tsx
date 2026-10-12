"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAppRouter, useDisplayPath } from "@/components/navigation-progress";
import { isActivePath } from "@/lib/nav-path";
import { useQuery } from "@tanstack/react-query";
import {
  Bell,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  HelpCircle,
  LayoutDashboard,
  Menu,
  Plus,
  Search,
  Settings,
  Share2,
  Sparkles,
  Star,
  Clock,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  clientApi,
  type Dashboard,
  type MeResponse,
  type Space,
  type SpaceListResponse,
  type Workspace,
} from "@/lib/api";
import { useClickOutside } from "@/lib/use-click-outside";
import { LogoutButton } from "@/components/auth/LogoutButton";
import { CreateWorkspaceDialog } from "@/components/dialogs";
import { CreateSpaceDialog } from "@/components/spaces/CreateSpaceDialog";
import { SpaceIcon } from "@/components/spaces/SpaceIcon";
import { BrandLogo } from "@/components/brand";
import { AppUserProvider } from "@/components/app-user";
import { useAppUser } from "@/components/app-user";

const primaryNav = [
  { href: "/app", label: "Dashboard", icon: LayoutDashboard, exact: true },
  // Ask AI & Studio: space-scoped only (see SpaceTabNav)
  { href: "/app/shared", label: "Shared with me", icon: Share2 },
  { href: "/app/recent", label: "Recent", icon: Clock },
  { href: "/app/starred", label: "Starred", icon: Star },
];

const SIDEBAR_COLLAPSED_KEY = "kl-sidebar-collapsed";

export function AppSidebar({
  open,
  onClose,
  collapsed,
  onToggleCollapsed,
}: {
  open: boolean;
  onClose: () => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
}) {
  const user = useAppUser();
  const pathname = usePathname();
  const displayPath = useDisplayPath();
  const router = useAppRouter();
  const [createOpen, setCreateOpen] = useState(false);
  const [createSpaceOpen, setCreateSpaceOpen] = useState(false);
  const [wsMenuOpen, setWsMenuOpen] = useState(false);
  const wsMenuRef = useRef<HTMLDivElement>(null);
  useClickOutside(wsMenuRef, wsMenuOpen, () => setWsMenuOpen(false));
  const { data: dashboard } = useQuery({
    queryKey: ["dashboard", user.id],
    queryFn: () => clientApi<Dashboard>("/dashboard"),
    staleTime: 30_000,
  });
  const { data: workspaces = [], isPending: workspacesPending } = useQuery({
    queryKey: ["workspaces", "sidebar", user.id],
    queryFn: () => clientApi<Workspace[]>("/workspaces?filter=all"),
  });
  const pathWorkspaceId = useMemo(() => {
    const match = pathname.match(/^\/app\/workspaces\/([^/]+)/);
    return match?.[1] && match[1] !== "undefined" ? match[1] : null;
  }, [pathname]);
  const currentSpaceId = useMemo(() => {
    const match = pathname.match(/^\/app\/workspaces\/[^/]+\/spaces\/([^/]+)/);
    return match?.[1] || null;
  }, [pathname]);
  const currentWorkspaceId = pathWorkspaceId || workspaces[0]?.id || null;
  const currentWorkspace = workspaces.find((w) => w.id === currentWorkspaceId) || null;
  const { data: spacesData, isPending: spacesPending } = useQuery({
    queryKey: ["spaces", "sidebar", currentWorkspaceId],
    queryFn: () =>
      clientApi<SpaceListResponse>(
        `/workspaces/${currentWorkspaceId}/spaces?tab=all&page_size=50`,
      ),
    enabled: Boolean(currentWorkspaceId),
    staleTime: 30_000,
  });
  const spaces: Space[] = spacesData?.items ?? [];
  const atLimit =
    (dashboard?.summary.owned_workspace_count ?? 0) >=
    (dashboard?.summary.workspace_limit ?? 10);

  return (
    <>
      {open ? (
        <button
          aria-label="Close navigation"
          className="fixed inset-0 z-30 bg-black/30 lg:hidden"
          onClick={onClose}
        />
      ) : null}
      <aside
        className={`app-sidebar ${collapsed ? "app-sidebar-collapsed" : ""} ${
          open ? "translate-x-0" : "-translate-x-full"
        } lg:translate-x-0`}
      >
        {collapsed ? (
          <div className="hidden h-full flex-col items-center gap-3 py-4 lg:flex">
            <Link href="/app" title="Knowledge Library" onClick={onClose}>
              <BrandLogo variant="mark" showWordmark={false} priority />
            </Link>
            <button
              type="button"
              className="icon-button"
              aria-label="Expand sidebar"
              title="Expand sidebar"
              onClick={onToggleCollapsed}
            >
              <ChevronRight size={18} />
            </button>
          </div>
        ) : null}

        <div className={collapsed ? "flex h-full flex-col lg:hidden" : "flex h-full flex-col"}>
          <div className="flex items-center justify-between px-3 py-4">
            <Link
              href="/app"
              className="flex items-center gap-2.5 px-2 font-semibold tracking-tight"
              title="Knowledge Library"
            >
              <BrandLogo variant="mark" priority />
            </Link>
            <div className="flex items-center gap-1">
              <button
                type="button"
                className="icon-button hidden lg:grid"
                aria-label="Collapse sidebar"
                title="Collapse sidebar"
                onClick={onToggleCollapsed}
              >
                <ChevronLeft size={18} />
              </button>
              <button className="icon-button lg:hidden" onClick={onClose}>
                <X size={18} />
              </button>
            </div>
          </div>

          <div className="relative px-3 pb-2" ref={wsMenuRef}>
            <button
              type="button"
              className="flex w-full items-center justify-between rounded-xl border border-border bg-surface-muted px-3 py-2.5 text-left"
              aria-expanded={wsMenuOpen}
              onClick={() => setWsMenuOpen((v) => !v)}
            >
              <span>
                <span className="block text-sm font-semibold">
                  {currentWorkspace?.name || "Select workspace"}
                </span>
                <span className="text-xs text-muted">
                  {currentWorkspace?.my_role
                    ? currentWorkspace.my_role.charAt(0) +
                      currentWorkspace.my_role.slice(1).toLowerCase()
                    : "Switch workspace"}
                </span>
              </span>
              <ChevronDown size={16} className="text-muted" />
            </button>
            {wsMenuOpen ? (
              <div className="absolute z-40 mt-2 max-h-72 w-[calc(100%-1.5rem)] overflow-auto rounded-xl border border-border bg-surface p-1 shadow-xl">
                <p className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">
                  Switch Workspace
                </p>
                {workspaces.map((ws) => (
                  <button
                    key={ws.id}
                    type="button"
                    className="menu-link w-full text-left"
                    onClick={() => {
                      setWsMenuOpen(false);
                      onClose();
                      router.push(`/app/workspaces/${ws.id}/spaces`);
                    }}
                  >
                    {ws.name}
                  </button>
                ))}
                <div className="my-1 border-t border-border" />
                <button
                  type="button"
                  className="menu-link w-full text-left"
                  disabled={atLimit}
                  onClick={() => {
                    setWsMenuOpen(false);
                    setCreateOpen(true);
                  }}
                >
                  Create Workspace
                </button>
                {currentWorkspaceId ? (
                  <Link
                    href={`/app/workspaces/${currentWorkspaceId}/settings`}
                    className="menu-link block"
                    onClick={() => {
                      setWsMenuOpen(false);
                      onClose();
                    }}
                  >
                    Workspace Settings
                  </Link>
                ) : null}
              </div>
            ) : null}
          </div>

          <nav className="mt-4 space-y-1 px-3">
            {primaryNav.map(({ href, label, icon: Icon, exact }) => {
              const active = isActivePath(displayPath, href, { exact: Boolean(exact) });
              return (
                <Link
                  key={href}
                  href={href}
                  onClick={onClose}
                  className={`nav-link ${active ? "nav-link-active" : ""}`}
                >
                  <Icon size={18} />
                  {label}
                </Link>
              );
            })}
          </nav>

          <div className="mt-5 flex min-h-0 flex-1 flex-col px-3">
            <div className="flex items-center justify-between px-3">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">
                Spaces
              </p>
              <button
                type="button"
                className="grid h-6 w-6 place-items-center rounded-md text-muted transition hover:bg-surface-muted hover:text-foreground"
                aria-label="Create space"
                title="Create space"
                onClick={() => setCreateSpaceOpen(true)}
              >
                <Plus size={14} />
              </button>
            </div>
            <div className="mt-1 min-h-0 flex-1 space-y-0.5 overflow-y-auto">
              {!currentWorkspaceId ? (
                <p className="px-3 py-2 text-xs text-muted">
                  {workspacesPending ? "Loading…" : "Select a workspace to see spaces."}
                </p>
              ) : spacesPending && !spacesData ? (
                <p className="px-3 py-2 text-xs text-muted">Loading spaces…</p>
              ) : spaces.length === 0 ? (
                <p className="px-3 py-2 text-xs text-muted">No spaces yet.</p>
              ) : (
                spaces.map((space) => {
                  const href = `/app/workspaces/${space.workspace_id}/spaces/${space.id}/pages`;
                  const active = currentSpaceId === space.id;
                  return (
                    <Link
                      key={space.id}
                      href={href}
                      onClick={onClose}
                      className={`flex items-center gap-2.5 rounded-xl px-2.5 py-2 text-sm transition ${
                        active
                          ? "bg-primary text-primary-foreground"
                          : "text-foreground hover:bg-surface-muted"
                      }`}
                    >
                      <SpaceIcon
                        iconKey={space.icon_key}
                        accent={active ? "blue" : space.accent_key}
                        size={14}
                        className={`!h-7 !w-7 !rounded-lg ${
                          active ? "!bg-primary-foreground/20 !text-primary-foreground" : ""
                        }`}
                      />
                      <span className="min-w-0 flex-1 truncate font-medium">{space.name}</span>
                    </Link>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </aside>
      <CreateWorkspaceDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        workspaceLimit={dashboard?.summary.workspace_limit}
        ownedCount={dashboard?.summary.owned_workspace_count}
      />
      <CreateSpaceDialog
        open={createSpaceOpen}
        onClose={() => setCreateSpaceOpen(false)}
        workspaceId={currentWorkspaceId}
      />
    </>
  );
}

export function GlobalSearch() {
  const user = useAppUser();
  const router = useAppRouter();
  const path = usePathname();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useClickOutside(ref, open, () => setOpen(false));

  const { data: workspaces = [] } = useQuery({
    queryKey: ["workspaces", "search-bar", user.id],
    queryFn: () => clientApi<Workspace[]>("/workspaces?filter=all"),
  });
  const pathWorkspaceId = useMemo(() => {
    const match = path.match(/^\/app\/workspaces\/([^/]+)/);
    return match?.[1] && match[1] !== "undefined" ? match[1] : null;
  }, [path]);
  const pathSpaceId = useMemo(() => {
    const match = path.match(/^\/app\/workspaces\/[^/]+\/spaces\/([^/]+)/);
    return match?.[1] || null;
  }, [path]);
  const workspaceId = pathWorkspaceId || workspaces[0]?.id || null;

  type Hit = {
    document_id: string;
    space_id: string;
    title: string;
    snippet: string;
  };

  const { data: hits = [], isFetching } = useQuery({
    queryKey: ["hybrid-search", workspaceId, query],
    queryFn: () =>
      clientApi<Hit[]>(
        `/workspaces/${workspaceId}/search?q=${encodeURIComponent(query)}&limit=12`,
      ),
    enabled: !!workspaceId && query.trim().length > 1,
  });

  const { data: spacesData } = useQuery({
    queryKey: ["spaces", "search-ask", workspaceId],
    queryFn: () =>
      clientApi<SpaceListResponse>(`/workspaces/${workspaceId}/spaces?tab=all&page_size=20`),
    enabled: !!workspaceId && !pathSpaceId,
    staleTime: 60_000,
  });
  const askSpaceId = pathSpaceId || hits[0]?.space_id || spacesData?.items?.[0]?.id || null;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(true);
        ref.current?.querySelector("input")?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="relative hidden w-full max-w-lg md:block" ref={ref}>
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={17} />
      <input
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder="Search across your spaces..."
        className="input pl-9 pr-16"
        aria-label="Global search"
      />
      <kbd className="absolute right-3 top-1/2 -translate-y-1/2 rounded border border-border px-1.5 py-0.5 text-[10px] text-muted">
        ⌘ K
      </kbd>
      {open && query.trim().length > 1 ? (
        <div className="absolute z-30 mt-2 max-h-80 w-full overflow-auto rounded-xl border border-border bg-surface shadow-xl">
          {!workspaceId ? (
            <p className="px-3 py-3 text-sm text-muted">Select a workspace first.</p>
          ) : isFetching ? (
            <p className="px-3 py-3 text-sm text-muted">Searching…</p>
          ) : hits.length ? (
            hits.map((hit) => (
              <button
                key={`${hit.document_id}-${hit.snippet.slice(0, 24)}`}
                type="button"
                className="flex w-full flex-col px-3 py-2.5 text-left text-sm hover:bg-surface-muted"
                onClick={() => {
                  setQuery("");
                  setOpen(false);
                  router.push(
                    `/app/workspaces/${workspaceId}/spaces/${hit.space_id}/pages/${hit.document_id}`,
                  );
                }}
              >
                <span className="font-medium">{hit.title}</span>
                <span className="line-clamp-2 text-xs text-muted">{hit.snippet}</span>
              </button>
            ))
          ) : (
            <p className="px-3 py-3 text-sm text-muted">No matching pages or chunks.</p>
          )}
          {workspaceId && askSpaceId ? (
            <button
              type="button"
              className="flex w-full items-center gap-2 border-t border-border px-3 py-2.5 text-left text-sm text-primary hover:bg-surface-muted"
              onClick={() => {
                setOpen(false);
                router.push(
                  `/app/workspaces/${workspaceId}/spaces/${askSpaceId}/ask?q=${encodeURIComponent(query.trim())}`,
                );
              }}
            >
              <Sparkles size={14} /> Ask AI about “{query.trim()}”
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function UserMenu({ user }: { user: MeResponse }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useClickOutside(ref, open, () => setOpen(false));

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-surface-muted"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="grid h-7 w-7 place-items-center rounded-full bg-blue-100 text-xs font-bold text-blue-700 dark:bg-blue-950 dark:text-blue-200">
          {(user.display_name || user.email).slice(0, 1).toUpperCase()}
        </span>
        <span className="hidden max-w-28 truncate sm:block">
          {user.display_name || user.email}
        </span>
        <ChevronDown size={15} />
      </button>
      {open ? (
        <div
          className="absolute right-0 z-30 mt-2 w-60 rounded-xl border border-border bg-surface p-2 shadow-xl"
          role="menu"
        >
          <p className="px-2 py-2 text-xs text-muted">{user.email}</p>
          <div className="border-t border-border pt-1">
            <LogoutButton />
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function AppHeader({ user, onMenu }: { user: MeResponse; onMenu: () => void }) {
  const path = useDisplayPath();
  const title = path.includes("/spaces/") && path.includes("/ask")
    ? "Ask AI"
    : path.includes("/spaces/") && path.includes("/studio")
      ? "Studio"
      : path.startsWith("/app/workspaces")
        ? "Workspaces"
        : path.startsWith("/app/shared")
          ? "Shared with me"
          : path.startsWith("/app/recent")
            ? "Recent"
            : path.startsWith("/app/starred")
              ? "Starred"
              : path.startsWith("/app/settings")
                ? "Settings"
                : "Dashboard";

  return (
    <header className="app-header">
      <button className="icon-button lg:hidden" aria-label="Open navigation" onClick={onMenu}>
        <Menu size={20} />
      </button>
      <h1 className="hidden text-lg font-semibold tracking-tight sm:block">{title}</h1>
      <GlobalSearch />
      <div className="ml-auto flex items-center gap-1 sm:gap-2">
        <Link
          href="/app/settings/profile"
          className={`icon-button ${path.startsWith("/app/settings") ? "bg-surface-muted text-primary" : ""}`}
          aria-label="Settings"
          title="Settings"
        >
          <Settings size={18} />
        </Link>
        <button type="button" className="icon-button hidden sm:grid" aria-label="Help" title="Help">
          <HelpCircle size={18} />
        </button>
        <button
          type="button"
          className="icon-button relative hidden sm:grid"
          aria-label="Notifications"
          title="Coming soon"
        >
          <Bell size={18} />
        </button>
        <UserMenu user={user} />
      </div>
    </header>
  );
}

export function AppShell({ user, children }: { user: MeResponse; children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1");
    } catch {
      /* ignore */
    }
  }, []);

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(SIDEBAR_COLLAPSED_KEY, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  };

  return (
    <AppUserProvider user={user}>
      <div className="h-full overflow-hidden">
        <AppSidebar
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          collapsed={collapsed}
          onToggleCollapsed={toggleCollapsed}
        />
        <div
          className={`app-main ${collapsed ? "app-main-collapsed" : "app-main-expanded"}`}
        >
          <AppHeader user={user} onMenu={() => setSidebarOpen(true)} />
          <main className="relative min-h-0 w-full min-w-0 flex-1 overflow-y-auto p-4 sm:p-6">
            {children}
          </main>
        </div>
      </div>
    </AppUserProvider>
  );
}
