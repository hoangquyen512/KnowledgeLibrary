"use client";

import { Suspense } from "react";
import { useParams } from "next/navigation";
import { AskAIWorkspace } from "@/components/ask-ai";

export default function SpaceAskPage() {
  return (
    <Suspense fallback={<p className="p-6 text-sm text-muted">Loading Ask AI…</p>}>
      <SpaceAskInner />
    </Suspense>
  );
}

function SpaceAskInner() {
  const { id, spaceId } = useParams<{ id: string; spaceId: string }>();

  return (
    <AskAIWorkspace
      embedded
      lockScope
      initialWorkspaceId={id}
      initialSpaceId={spaceId}
    />
  );
}
