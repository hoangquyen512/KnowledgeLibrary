"use client";

import { useMutation } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import { useAppRouter } from "@/components/navigation-progress";
import { useEffect } from "react";
import { clientApi, type ShareRedeemResult } from "@/lib/api";
import { BrandLoading } from "@/components/brand";

export function ShareRedeemer({ token }: { token: string }) {
  const router = useAppRouter();
  const mutation = useMutation({
    mutationFn: () =>
      clientApi<ShareRedeemResult>(`/share/${encodeURIComponent(token)}/redeem`, {
        method: "POST",
      }),
    onSuccess: (result) => {
      if (result.target_type === "SPACE" && result.space_id) {
        router.replace(
          `/app/workspaces/${result.workspace_id}/spaces/${result.space_id}/pages`,
          { feedback: true },
        );
      } else {
        router.replace(`/app/workspaces/${result.workspace_id}`, { feedback: true });
      }
    },
  });
  useEffect(() => {
    mutation.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="grid min-h-screen place-items-center p-6">
      <section className="w-full max-w-md rounded-2xl border border-border bg-surface p-7 text-center shadow-lg">
        {mutation.isPending ? (
          <BrandLoading label="Joining…" className="min-h-0 border-0 bg-transparent p-0" />
        ) : null}
        {mutation.isSuccess ? (
          <>
            <CheckCircle2 className="mx-auto text-emerald-600" size={28} />
            <p className="mt-4 text-sm text-muted">Redirecting…</p>
          </>
        ) : null}
        {mutation.isError ? (
          <>
            <h1 className="text-lg font-semibold">Invitation unavailable</h1>
            <p className="mt-2 text-sm text-muted">{mutation.error.message}</p>
            <button
              type="button"
              onClick={() => router.push("/app/shared")}
              className="primary-button mt-5"
            >
              Open shared
            </button>
          </>
        ) : null}
      </section>
    </main>
  );
}
