import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { AdminNav } from "@/components/admin/AdminNav";
import { fetchMe } from "@/lib/api";

export default async function SettingsAdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ");
  const me = await fetchMe(cookieHeader);
  if (!me) redirect("/login");
  if (!me.is_super_admin) redirect("/app/settings/profile");
  return (
    <>
      <AdminNav />
      {children}
    </>
  );
}
