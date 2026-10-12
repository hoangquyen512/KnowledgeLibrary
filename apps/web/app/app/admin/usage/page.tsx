import { redirect } from "next/navigation";

export default function LegacyAdminUsagePage() {
  redirect("/app/settings/admin/usage");
}
