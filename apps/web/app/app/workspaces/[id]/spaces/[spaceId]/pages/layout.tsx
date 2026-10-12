"use client";

import { useParams } from "next/navigation";
import { SpacePagesShell } from "@/components/pages/SpacePagesShell";

/** Keeps SpacePagesShell mounted across /pages ↔ /pages/[pageId] (avoids remount lag). */
export default function SpacePagesLayout({ children }: { children: React.ReactNode }) {
  const { id, spaceId, pageId } = useParams<{
    id: string;
    spaceId: string;
    pageId?: string;
  }>();
  return (
    <>
      <SpacePagesShell workspaceId={id} spaceId={spaceId} pageId={pageId} />
      {children}
    </>
  );
}
