"use client";

import Link from "next/link";
import { Palette, Sparkles, Trash2, User, UserCog } from "lucide-react";
import { useAppUser } from "@/components/app-user";
import { useDisplayPath } from "@/components/navigation-progress";
import { isActivePath } from "@/lib/nav-path";

const LINKS = [
  { href: "/app/settings/profile", label: "Profile", icon: User },
  { href: "/app/settings/ai", label: "AI Connections", icon: Sparkles },
  { href: "/app/settings/appearance", label: "Appearance", icon: Palette },
  { href: "/app/settings/trash", label: "Trash", icon: Trash2 },
  { href: "/app/settings/admin", label: "Admin", icon: UserCog, adminOnly: true },
] as const;

export function SettingsNav({ isSuperAdmin = false }: { isSuperAdmin?: boolean }) {
  const path = useDisplayPath();
  const user = useAppUser();
  const showAdmin = isSuperAdmin || user.is_super_admin;

  return (
    <nav
      className="relative z-10 mb-6 flex flex-wrap gap-1 border-b border-border"
      aria-label="Settings sections"
    >
      {LINKS.filter((link) => !("adminOnly" in link && link.adminOnly) || showAdmin).map(
        (link) => {
          const exactAdmin = link.href === "/app/settings/admin";
          const active = isActivePath(path, link.href, { exact: !exactAdmin });
          const Icon = link.icon;
          return (
            <Link
              key={link.href}
              href={link.href}
              prefetch={exactAdmin ? false : undefined}
              className={`tab-button inline-flex cursor-pointer items-center gap-1.5 ${active ? "tab-active" : ""}`}
            >
              <Icon size={15} />
              {link.label}
            </Link>
          );
        },
      )}
    </nav>
  );
}
