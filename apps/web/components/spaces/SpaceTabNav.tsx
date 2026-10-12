"use client";

import {
  FileText,
  FolderOpen,
  LayoutDashboard,
  Network,
  Settings,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

export function SpaceTabNav({
  workspaceId,
  spaceId,
}: {
  workspaceId: string;
  spaceId: string;
}) {
  const pathname = usePathname();
  const base = `/app/workspaces/${workspaceId}/spaces/${spaceId}`;

  const tabs = [
    { key: "overview", href: base, label: "Overview", icon: LayoutDashboard },
    { key: "pages", href: `${base}/pages`, label: "Pages", icon: FileText },
    { key: "sources", href: `${base}/sources`, label: "Sources", icon: FolderOpen },
    { key: "ask", href: `${base}/ask`, label: "Ask AI", icon: Sparkles },
    { key: "studio", href: `${base}/studio`, label: "Studio", icon: Network },
    { key: "settings", href: `${base}/settings`, label: "Settings", icon: Settings },
  ] as const;

  const activeKey = (() => {
    if (pathname.includes("/pages")) return "pages";
    if (pathname.includes("/sources")) return "sources";
    if (pathname.includes("/ask")) return "ask";
    if (pathname.includes("/studio")) return "studio";
    if (pathname.includes("/settings") || pathname.includes("/access")) return "settings";
    return "overview";
  })();

  return (
    <nav className="flex shrink-0 items-center gap-1 overflow-x-auto border-b border-border bg-surface px-3 sm:px-4">
      {tabs.map((item) => {
        const active = activeKey === item.key;
        return (
          <Link
            key={item.key}
            href={item.href}
            className={`tab-button flex items-center gap-1.5 whitespace-nowrap ${
              active ? "tab-active" : ""
            }`}
          >
            <item.icon size={15} />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
