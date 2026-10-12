"use client";

import Link from "next/link";
import { useDisplayPath } from "@/components/navigation-progress";
import { isActivePath } from "@/lib/nav-path";

const LINKS = [
  { href: "/app/settings/admin", label: "Overview", exact: true },
  { href: "/app/settings/admin/users", label: "Users" },
  { href: "/app/settings/admin/logs", label: "System logs" },
  { href: "/app/settings/admin/usage", label: "AI usage" },
  { href: "/app/settings/admin/documents", label: "Top documents" },
];

export function AdminNav() {
  const path = useDisplayPath();
  return (
    <nav className="mb-5 flex flex-wrap gap-1 border-b border-border" aria-label="Admin sections">
      {LINKS.map((link) => {
        const active = isActivePath(path, link.href, { exact: Boolean(link.exact) });
        return (
          <Link key={link.href} href={link.href} className={`tab-button ${active ? "tab-active" : ""}`}>
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
