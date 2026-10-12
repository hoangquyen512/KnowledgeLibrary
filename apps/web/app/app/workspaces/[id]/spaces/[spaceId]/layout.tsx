"use client";

import { useParams } from "next/navigation";
import { SpaceTabNav } from "@/components/spaces/SpaceTabNav";

export default function SpaceLayout({ children }: { children: React.ReactNode }) {
  const { id, spaceId } = useParams<{ id: string; spaceId: string }>();

  return (
    <div className="absolute inset-0 flex min-h-0 flex-col overflow-hidden border-t border-border">
      <SpaceTabNav workspaceId={id} spaceId={spaceId} />
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{children}</div>
    </div>
  );
}
