import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { fetchMe } from "@/lib/api";
import { ShareRedeemer } from "@/components/share-redeemer";

export default async function SharePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const cookieStore = await cookies();
  const cookieHeader = cookieStore.getAll().map((cookie) => `${cookie.name}=${cookie.value}`).join("; ");
  const me = await fetchMe(cookieHeader);
  if (!me) redirect(`/login?next=${encodeURIComponent(`/share/${token}`)}`);
  return <ShareRedeemer token={token} />;
}
