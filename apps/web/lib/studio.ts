export type StudioSourceRef = {
  document_id: string;
  chunk_id?: string | null;
  title: string;
  snippet?: string | null;
  section_heading?: string | null;
  source_url?: string | null;
  space_id?: string | null;
};

export type StudioSlide = {
  id: string;
  title: string;
  bullets: string[];
  notes?: string | null;
  source_refs: StudioSourceRef[];
};

export type StudioMindmapNode = {
  id: string;
  label: string;
  parent_id: string | null;
  collapsed: boolean;
  source_ref?: StudioSourceRef | null;
};

export type StudioArtifact = {
  id: string;
  workspace_id: string;
  artifact_type: "PRESENTATION" | "MINDMAP";
  title: string;
  status: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";
  focus_prompt?: string | null;
  payload_json?: {
    slides?: StudioSlide[];
    nodes?: StudioMindmapNode[];
  } | null;
  warning_json?: {
    map_reduce_used?: boolean;
    documents_capped?: boolean;
  } | null;
  progress_percent: number;
  stage: string;
  error_message?: string | null;
  model_provider?: string | null;
  model_name?: string | null;
  space_ids: string[];
  document_ids: string[];
  created_at: string;
  updated_at: string;
};

export function studioPageHref(
  workspaceId: string,
  citation: StudioSourceRef,
  fallbackSpaceId?: string | null,
): string | null {
  const spaceId = citation.space_id || fallbackSpaceId;
  if (!spaceId || !citation.document_id) return null;
  return `/app/workspaces/${workspaceId}/spaces/${spaceId}/pages/${citation.document_id}`;
}

export function isStudioActive(artifact: StudioArtifact | undefined): boolean {
  return artifact?.status === "QUEUED" || artifact?.status === "RUNNING";
}
