import { cookies } from "next/headers";
import { SettingsNav } from "@/components/settings/SettingsNav";
import { fetchMe } from "@/lib/api";

export default async function SettingsLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ");
  const me = await fetchMe(cookieHeader);

  return (
    <div className="page-shell">
      <h1 className="page-title">Settings</h1>
      <p className="mt-1 text-sm text-muted">
        Manage your profile, AI connections, trash, and preferences.
      </p>
      <div className="mt-6">
        <SettingsNav isSuperAdmin={Boolean(me?.is_super_admin)} />
      </div>
      {children}
    </div>
  );
}

