import { redirect } from "next/navigation";

export default function LegacyTrashPage() {
  redirect("/app/settings/trash");
}
