"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Global Ask AI is temporarily disabled — use Ask AI inside a Space. */
export default function AskRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/app");
  }, [router]);
  return <p className="p-6 text-sm text-muted">Ask AI is available inside a Space. Redirecting…</p>;
}
