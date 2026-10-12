"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Global Studio is temporarily disabled — use Studio inside a Space. */
export default function StudioRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/app");
  }, [router]);
  return (
    <p className="p-6 text-sm text-muted">Studio is available inside a Space. Redirecting…</p>
  );
}
