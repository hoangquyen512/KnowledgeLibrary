import { redirect } from "next/navigation";

export default function LegacyAdminUsersPage() {
  redirect("/app/settings/admin/users");
}
