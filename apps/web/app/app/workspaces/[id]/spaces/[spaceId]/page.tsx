"use client";

import { useParams } from "next/navigation";
import { SpaceOverview } from "@/components/spaces/SpaceOverview";

export default function SpaceDetailPage() {
  const { id, spaceId } = useParams<{ id: string; spaceId: string }>();
  return <SpaceOverview workspaceId={id} spaceId={spaceId} />;
}
