import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { fetchMe } from "@/lib/api";

export default async function ProtectedAppLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore.getAll().map((cookie) => `${cookie.name}=${cookie.value}`).join("; ");
  const me = await fetchMe(cookieHeader);
  if (!me) redirect("/login");
  return <AppShell user={me}>{children}</AppShell>;
}
