"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Calendar,
  Check,
  Clock,
  Crown,
  Database,
  Mail,
  Pencil,
  Shield,
  Users,
} from "lucide-react";
import { LogoutButton } from "@/components/auth/LogoutButton";
import { clientApi, type MeResponse, type Workspace } from "@/lib/api";

function formatWhen(iso: string | null | undefined, withTime: boolean): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  if (!withTime) {
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    }).format(date);
  }
  const datePart = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
  const timePart = new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  }).format(date);
  return `${datePart} - ${timePart}`;
}

function titleCaseRole(role: string | null | undefined): string {
  if (!role) return "Member";
  return role.charAt(0) + role.slice(1).toLowerCase();
}

function GoogleMark() {
  return (
    <svg width="14" height="14" viewBox="0 0 18 18" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62Z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.71H.96v2.33A9 9 0 0 0 9 18Z"
      />
      <path
        fill="#FBBC05"
        d="M3.97 10.71A5.41 5.41 0 0 1 3.69 9c0-.59.1-1.17.26-1.71V4.96H.96A9 9 0 0 0 0 9c0 1.45.35 2.82.96 4.04l3.01-2.33Z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.96L3.97 7.3C4.68 5.16 6.66 3.58 9 3.58Z"
      />
    </svg>
  );
}

export default function ProfileSettingsPage() {
  const { data: user } = useQuery({
    queryKey: ["me"],
    queryFn: () => clientApi<MeResponse>("/me"),
  });
  const { data: workspaces = [] } = useQuery({
    queryKey: ["workspaces", "settings-profile"],
    queryFn: () => clientApi<Workspace[]>("/workspaces?filter=all"),
  });

  const workspace =
    workspaces.find((item) => item.my_role === "OWNER") || workspaces[0] || null;
  const workspaceRole = titleCaseRole(workspace?.my_role);
  const roleLabel = user?.is_super_admin ? "Super Admin" : workspaceRole;
  const initial = (user?.display_name || user?.email || "?").slice(0, 1).toUpperCase();
  const spaceCount = workspaces.reduce((sum, item) => sum + (item.space_count || 0), 0);
  const isActive = (user?.status || "ACTIVE") === "ACTIVE";

  return (
    <section className="settings-card p-6 sm:p-8">
      <div className="flex items-center gap-3">
        {user?.avatar_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={user.avatar_url}
            alt=""
            className="h-12 w-12 rounded-full object-cover"
          />
        ) : (
          <span className="grid h-12 w-12 place-items-center rounded-full bg-blue-100 text-base font-bold text-blue-700 dark:bg-blue-950 dark:text-blue-200">
            {initial}
          </span>
        )}
        <div>
          <h2 className="text-lg font-semibold">Profile</h2>
          <p className="text-sm text-muted">Your account details and preferences.</p>
        </div>
      </div>

      <div className="mt-8 grid gap-10 lg:grid-cols-2">
        <div>
          <h3 className="text-sm font-semibold">Profile information</h3>
          <div className="mt-4 space-y-4">
            <label className="block text-sm">
              <span className="text-muted">Display name</span>
              <span className="relative mt-1 block">
                <input
                  className="input pr-10"
                  value={user?.display_name || ""}
                  readOnly
                  aria-readonly="true"
                />
                <Pencil size={15} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-muted" />
              </span>
            </label>
            <label className="block text-sm">
              <span className="text-muted">Email</span>
              <span className="relative mt-1 block">
                <Mail size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
                <input
                  className="input px-9 pr-10"
                  value={user?.email || ""}
                  readOnly
                  aria-readonly="true"
                />
                <Pencil size={15} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-muted" />
              </span>
            </label>
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="text-muted">Verification</span>
              {user?.email_verified ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                  <Check size={12} />
                  Verified
                </span>
              ) : (
                <span className="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                  Not verified
                </span>
              )}
            </div>
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="text-muted">Role</span>
              <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700 dark:bg-blue-950 dark:text-blue-300">
                <Shield size={12} />
                {roleLabel}
              </span>
            </div>
          </div>
          <p className="mt-6 flex items-center gap-2 text-xs text-muted">
            <GoogleMark />
            Profile editing is managed through Google sign-in.
          </p>
        </div>

        <div>
          <h3 className="text-sm font-semibold">Account status</h3>
          <div
            className={`mt-4 rounded-xl border px-4 py-3 ${
              isActive
                ? "border-emerald-200 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950/40"
                : "border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/40"
            }`}
          >
            <p
              className={`flex items-center gap-2 text-sm font-semibold ${
                isActive ? "text-emerald-800 dark:text-emerald-200" : "text-amber-800 dark:text-amber-200"
              }`}
            >
              <Check size={16} />
              {user?.status || "ACTIVE"}
            </p>
            <p className={`mt-1 text-xs ${isActive ? "text-emerald-700 dark:text-emerald-300" : "text-amber-700"}`}>
              {isActive
                ? "Your account is active and in good standing."
                : "Your account is not currently active."}
            </p>
          </div>
          <ul className="mt-4 space-y-3 text-sm">
            <StatusRow
              icon={Clock}
              label="Last sign-in"
              value={formatWhen(user?.last_login_at, true)}
            />
            <StatusRow
              icon={Calendar}
              label="Account created"
              value={formatWhen(user?.created_at, false)}
            />
            <StatusRow icon={Crown} label="Workspace role" value={workspaceRole} />
            <StatusRow
              icon={Database}
              label="Data access"
              value={workspace?.my_role === "OWNER" || user?.is_super_admin ? "All spaces" : "Assigned spaces"}
            />
            <StatusRow
              icon={Users}
              label="Accessible spaces"
              value={`${spaceCount} space${spaceCount === 1 ? "" : "s"}`}
            />
          </ul>
          <LogoutButton
            variant="danger"
            className="mt-6 w-full"
            label="Sign out everywhere"
          />
          <p className="mt-2 text-center text-xs text-muted">
            This will sign you out from all devices.
          </p>
        </div>
      </div>
    </section>
  );
}

function StatusRow({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Clock;
  label: string;
  value: string;
}) {
  return (
    <li className="flex items-center justify-between gap-3">
      <span className="inline-flex items-center gap-2 text-muted">
        <Icon size={15} />
        {label}
      </span>
      <span className="font-medium">{value}</span>
    </li>
  );
}
