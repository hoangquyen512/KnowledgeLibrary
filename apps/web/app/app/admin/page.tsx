import { redirect } from "next/navigation";

export default function LegacyAdminOverviewPage() {
  redirect("/app/settings/admin");
}
