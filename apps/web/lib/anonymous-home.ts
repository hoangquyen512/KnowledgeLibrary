import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { fetchMe } from "@/lib/api";
import { safeNextPath } from "@/lib/auth-public";

export async function redirectAnonymousHomeToLogin(params?: { error?: string; next?: string }) {
  const nextPath = safeNextPath(params?.next);
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((cookie) => `${cookie.name}=${cookie.value}`)
    .join("; ");
  const me = await fetchMe(cookieHeader);
  if (me) redirect(nextPath);

  const query = new URLSearchParams();
  if (params?.error) query.set("error", params.error);
  if (params?.next) query.set("next", params.next);
  const suffix = query.toString();
  redirect(suffix ? `/login?${suffix}` : "/login");
}
