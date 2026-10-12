"use client";

import { Suspense } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { StudioWorkspace } from "@/components/studio";

export default function SpaceStudioPage() {
  return (
    <Suspense fallback={<p className="p-6 text-sm text-muted">Loading Studio…</p>}>
      <SpaceStudioInner />
    </Suspense>
  );
}

function SpaceStudioInner() {
  const { id, spaceId } = useParams<{ id: string; spaceId: string }>();
  const searchParams = useSearchParams();
  const type = searchParams.get("type") === "mindmap" ? "MINDMAP" : "PRESENTATION";

  return (
    <StudioWorkspace
      embedded
      lockScope
      initialWorkspaceId={id}
      initialSpaceId={spaceId}
      initialType={type}
    />
  );
}
