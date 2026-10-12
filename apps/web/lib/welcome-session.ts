import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { fetchMe } from "@/lib/api";
import {
  getGoogleAuthStatus,
  oauthErrorMessage,
  safeNextPath,
  type WelcomeAuthProps,
} from "@/lib/auth-public";

export async function requireAnonymousWelcome(params?: {
  error?: string;
  next?: string;
}): Promise<WelcomeAuthProps> {
  const nextPath = safeNextPath(params?.next);
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((cookie) => `${cookie.name}=${cookie.value}`)
    .join("; ");
  const me = await fetchMe(cookieHeader);
  if (me) redirect(nextPath);

  const status = await getGoogleAuthStatus();
  return {
    googleConfigured: status.google_configured,
    authStatusOk: status.ok,
    error: oauthErrorMessage(params?.error),
    nextPath,
  };
}
