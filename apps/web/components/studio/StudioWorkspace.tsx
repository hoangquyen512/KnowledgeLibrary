"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Save, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { SourceRefPanel } from "./SourceRefPanel";
import { StudioInputPanel } from "./StudioInputPanel";
import { StudioTopBar, StudioPageHeader } from "./StudioHeader";
import { StudioPreviewPanel } from "./StudioPreviewPanel";
import { StudioStepper } from "./StudioStepper";
import { studio } from "./strings";
import { clientApi, type Space, type SpaceListResponse, type Workspace } from "@/lib/api";
import type { PageTreeNode } from "@/lib/pages";
import {
  isStudioActive,
  type StudioArtifact,
  type StudioMindmapNode,
  type StudioSlide,
  type StudioSourceRef,
} from "@/lib/studio";

const DRAFT_KEY = "studio-draft-v1";

type StudioDraft = {
  workspaceId: string;
  filterType: "PRESENTATION" | "MINDMAP";
  selectedSpaces: string[];
  selectedDocs: string[];
  focusPrompt: string;
  step: 1 | 2 | 3;
};

export type StudioWorkspaceProps = {
  initialWorkspaceId?: string;
  initialSpaceId?: string;
  initialType?: "PRESENTATION" | "MINDMAP";
  initialArtifactId?: string | null;
  /** Fit inside Space shell (no page negative margins). */
  embedded?: boolean;
  /** Keep workspace fixed; prefer initialSpaceId selected. */
  lockScope?: boolean;
  /** Sync query string on /app/studio. Disabled when embedded. */
  syncUrl?: boolean;
};

export function StudioWorkspace({
  initialWorkspaceId = "",
  initialSpaceId,
  initialType = "PRESENTATION",
  initialArtifactId = null,
  embedded = false,
  lockScope = false,
  syncUrl: syncUrlEnabled,
}: StudioWorkspaceProps) {
  const allowUrlSync = syncUrlEnabled ?? !embedded;
  const client = useQueryClient();
  const router = useRouter();

  const { data: workspaces = [] } = useQuery({
    queryKey: ["workspaces", "studio"],
    queryFn: () => clientApi<Workspace[]>("/workspaces?filter=all"),
  });

  const [workspaceId, setWorkspaceId] = useState(initialWorkspaceId);
  const effectiveWs = workspaceId || workspaces[0]?.id || "";

  const [filterType, setFilterType] = useState<"PRESENTATION" | "MINDMAP">(initialType);
  const [wizardStep, setWizardStep] = useState<1 | 2 | 3>(1);
  const [selectedId, setSelectedId] = useState<string | null>(initialArtifactId);
  const [selectedSpaces, setSelectedSpaces] = useState<string[]>(() =>
    initialSpaceId ? [initialSpaceId] : [],
  );
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [focusPrompt, setFocusPrompt] = useState("");
  const [selectedSource, setSelectedSource] = useState<StudioSourceRef | null>(null);
  const [localSlides, setLocalSlides] = useState<StudioSlide[] | null>(null);
  const [localNodes, setLocalNodes] = useState<StudioMindmapNode[] | null>(null);

  useEffect(() => {
    if (initialWorkspaceId) setWorkspaceId(initialWorkspaceId);
  }, [initialWorkspaceId]);

  useEffect(() => {
    if (!initialSpaceId) return;
    setSelectedSpaces((prev) => (prev.includes(initialSpaceId) ? prev : [...prev, initialSpaceId]));
  }, [initialSpaceId]);

  const { data: cred } = useQuery({
    queryKey: ["ai-credentials"],
    queryFn: () =>
      clientApi<{ status: string; mode: string; default_model?: string | null }>(
        "/me/ai-credentials",
      ),
  });
  const geminiConnected = cred?.status === "CONNECTED" && cred?.mode === "GEMINI";

  const { data: spacesData } = useQuery({
    queryKey: ["spaces", "studio", effectiveWs],
    queryFn: () =>
      clientApi<SpaceListResponse>(`/workspaces/${effectiveWs}/spaces?tab=all&page_size=100`),
    enabled: !!effectiveWs,
  });
  const spaces: Space[] = spacesData?.items ?? [];

  useEffect(() => {
    if (!selectedSpaces.length && spaces.length === 1) {
      setSelectedSpaces([spaces[0].id]);
    }
  }, [spaces, selectedSpaces.length]);

  const pageTrees = useQuery({
    queryKey: ["studio-page-trees", selectedSpaces.join(",")],
    queryFn: async () => {
      const out: Record<string, PageTreeNode[]> = {};
      for (const sid of selectedSpaces) {
        out[sid] = await clientApi<PageTreeNode[]>(`/spaces/${sid}/pages/tree`);
      }
      return out;
    },
    enabled: selectedSpaces.length > 0,
  });

  const { data: artifacts = [], refetch: refetchList } = useQuery({
    queryKey: ["studio-artifacts", effectiveWs, filterType],
    queryFn: () =>
      clientApi<StudioArtifact[]>(
        `/studio/artifacts?workspace_id=${effectiveWs}&artifact_type=${filterType}`,
      ),
    enabled: !!effectiveWs,
  });

  const { data: artifact, refetch: refetchArtifact } = useQuery({
    queryKey: ["studio-artifact", selectedId],
    queryFn: () => clientApi<StudioArtifact>(`/studio/artifacts/${selectedId}`),
    enabled: !!selectedId,
    refetchInterval: (q) => (isStudioActive(q.state.data) ? 1500 : false),
  });

  useEffect(() => {
    if (!artifact) return;
    setFocusPrompt(artifact.focus_prompt || "");
    if (isStudioActive(artifact) || artifact.status === "COMPLETED" || artifact.status === "FAILED") {
      setWizardStep(3);
    }
  }, [artifact?.id, artifact?.focus_prompt, artifact?.status]);

  useEffect(() => {
    if (!artifact || artifact.status !== "COMPLETED") return;
    if (artifact.artifact_type === "PRESENTATION") {
      setLocalSlides(artifact.payload_json?.slides || []);
    } else {
      setLocalNodes(artifact.payload_json?.nodes || []);
    }
  }, [artifact?.id, artifact?.status, artifact?.payload_json, artifact?.artifact_type]);

  useEffect(() => {
    if (artifact?.status === "COMPLETED") {
      refetchList();
    }
  }, [artifact?.status, refetchList]);

  const syncUrl = (patch: { artifactId?: string | null; type?: string }) => {
    if (!allowUrlSync) return;
    const params = new URLSearchParams();
    if (effectiveWs) params.set("workspaceId", effectiveWs);
    if (initialSpaceId) params.set("spaceId", initialSpaceId);
    if (patch.artifactId) params.set("artifactId", patch.artifactId);
    if (patch.type) params.set("type", patch.type === "MINDMAP" ? "mindmap" : "presentation");
    router.replace(`/app/studio?${params.toString()}`, { scroll: false });
  };

  const createArtifact = useMutation({
    mutationFn: (artifactType: "PRESENTATION" | "MINDMAP") =>
      clientApi<StudioArtifact>("/studio/artifacts", {
        method: "POST",
        body: JSON.stringify({
          workspace_id: effectiveWs,
          artifact_type: artifactType,
          focus_prompt: focusPrompt.trim() || null,
          space_ids: selectedSpaces,
          document_ids: selectedDocs.length ? selectedDocs : null,
        }),
      }),
    onSuccess: (a) => {
      setSelectedId(a.id);
      setWizardStep(3);
      syncUrl({ artifactId: a.id, type: a.artifact_type });
      client.invalidateQueries({ queryKey: ["studio-artifacts", effectiveWs] });
      toast.success(studio.generating);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const saveArtifact = useMutation({
    mutationFn: () => {
      if (!selectedId) throw new Error("No artifact");
      const body =
        filterType === "PRESENTATION"
          ? { slides: localSlides || [] }
          : { nodes: localNodes || [] };
      return clientApi<StudioArtifact>(`/studio/artifacts/${selectedId}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
    },
    onSuccess: () => {
      toast.success(studio.saved);
      refetchArtifact();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const regenerate = useMutation({
    mutationFn: (slideId?: string) =>
      clientApi<StudioArtifact>(`/studio/artifacts/${selectedId}/regenerate`, {
        method: "POST",
        body: JSON.stringify({
          slide_id: slideId || null,
          focus_prompt: focusPrompt.trim() || null,
        }),
      }),
    onSuccess: () => {
      refetchArtifact();
      toast.success(studio.generating);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const removeArtifact = useMutation({
    mutationFn: (id: string) => clientApi<void>(`/studio/artifacts/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      setSelectedId(null);
      setWizardStep(1);
      syncUrl({ artifactId: null });
      client.invalidateQueries({ queryKey: ["studio-artifacts", effectiveWs] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const fallbackSpaceId = selectedSpaces[0] || artifact?.space_ids[0] || null;

  const allPageIds = useMemo(() => {
    const ids: string[] = [];
    const trees = pageTrees.data || {};
    for (const nodes of Object.values(trees)) {
      for (const n of nodes) ids.push(n.id);
    }
    return ids;
  }, [pageTrees.data]);

  const exportPptx = async () => {
    if (!selectedId) return;
    const resp = await fetch(`/api/v1/studio/artifacts/${selectedId}/export.pptx`, {
      credentials: "include",
    });
    if (!resp.ok) {
      toast.error("Export failed");
      return;
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${artifact?.title || "presentation"}.pptx`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const toggleMindmapCollapse = (nodeId: string) => {
    setLocalNodes((prev) =>
      (prev || []).map((n) => (n.id === nodeId ? { ...n, collapsed: !n.collapsed } : n)),
    );
  };

  const canCreate =
    geminiConnected && !!effectiveWs && selectedSpaces.length > 0 && !createArtifact.isPending;

  const modelName = artifact?.model_name || cred?.default_model || "gemini-1.5-flash";

  const saveDraft = useCallback(() => {
    const draft: StudioDraft = {
      workspaceId: effectiveWs,
      filterType,
      selectedSpaces,
      selectedDocs,
      focusPrompt,
      step: wizardStep,
    };
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
      toast.success(studio.draftSaved);
    } catch {
      toast.error("Could not save draft");
    }
  }, [effectiveWs, filterType, selectedSpaces, selectedDocs, focusPrompt, wizardStep]);

  useEffect(() => {
    if (embedded || lockScope) return;
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      if (!raw || selectedId) return;
      const draft = JSON.parse(raw) as StudioDraft;
      if (draft.workspaceId) setWorkspaceId(draft.workspaceId);
      if (draft.filterType) setFilterType(draft.filterType);
      if (draft.selectedSpaces?.length) setSelectedSpaces(draft.selectedSpaces);
      if (draft.selectedDocs?.length) setSelectedDocs(draft.selectedDocs);
      if (draft.focusPrompt) setFocusPrompt(draft.focusPrompt);
      if (draft.step) setWizardStep(draft.step);
    } catch {
      /* ignore corrupt draft */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCreate = () => {
    if (!canCreate) return;
    if (wizardStep < 2) {
      setWizardStep(2);
      return;
    }
    createArtifact.mutate(filterType);
  };

  const inputStep: 1 | 2 = wizardStep === 1 ? 1 : 2;

  return (
    <div
      className={`flex min-h-0 flex-col overflow-hidden bg-background ${
        embedded ? "h-full" : "absolute inset-0"
      }`}
    >
      <StudioTopBar
        filterType={filterType}
        onFilterType={(t) => {
          setFilterType(t);
          setSelectedId(null);
          setWizardStep(1);
          syncUrl({ type: t, artifactId: null });
        }}
        artifacts={artifacts}
        onSelectArtifact={(id) => {
          setSelectedId(id);
          syncUrl({ artifactId: id });
          const item = artifacts.find((a) => a.id === id);
          if (item) {
            setFocusPrompt(item.focus_prompt || "");
            setFilterType(item.artifact_type);
          }
        }}
      />

      <StudioPageHeader
        filterType={filterType}
        onSaveDraft={saveDraft}
        onCreate={handleCreate}
        createDisabled={!canCreate}
        createPending={createArtifact.isPending}
      />

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <aside className="flex min-h-0 w-full shrink-0 flex-col overflow-hidden border-b border-border bg-surface lg:w-[360px] lg:max-w-[40%] lg:border-b-0 lg:border-r xl:w-[400px]">
          <StudioStepper current={wizardStep} />
          {wizardStep === 3 && artifact ? (
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4">
              <h2 className="text-sm font-semibold text-foreground">{artifact.title}</h2>
              {artifact.focus_prompt ? (
                <p className="mt-2 text-xs text-muted">
                  <span className="font-medium text-foreground">{studio.focusSavedLabel}:</span>{" "}
                  {artifact.focus_prompt}
                </p>
              ) : null}
              <div className="mt-4 flex flex-wrap gap-2">
                {artifact.status === "COMPLETED" ? (
                  <>
                    <button
                      type="button"
                      className="secondary-button h-8 px-2 text-xs"
                      onClick={() => saveArtifact.mutate()}
                      disabled={saveArtifact.isPending}
                    >
                      <Save size={14} />
                      {studio.save}
                    </button>
                    <button
                      type="button"
                      className="secondary-button h-8 px-2 text-xs"
                      onClick={() => regenerate.mutate(undefined)}
                    >
                      <RefreshCw size={14} />
                      {studio.regenerateAll}
                    </button>
                    {artifact.artifact_type === "PRESENTATION" ? (
                      <button
                        type="button"
                        className="secondary-button h-8 px-2 text-xs"
                        onClick={() => void exportPptx()}
                      >
                        {studio.exportPptx}
                      </button>
                    ) : null}
                  </>
                ) : null}
                <button
                  type="button"
                  className="secondary-button h-8 px-2 text-xs text-red-600"
                  onClick={() => {
                    if (window.confirm(studio.deleteConfirm)) {
                      removeArtifact.mutate(artifact.id);
                    }
                  }}
                >
                  <Trash2 size={14} />
                  {studio.delete}
                </button>
              </div>
              <button
                type="button"
                className="secondary-button mt-4 text-xs"
                onClick={() => {
                  setSelectedId(null);
                  setWizardStep(1);
                  syncUrl({ artifactId: null });
                }}
              >
                {studio.back}
              </button>
            </div>
          ) : (
            <StudioInputPanel
              step={inputStep}
              filterType={filterType}
              workspaces={workspaces}
              workspaceId={effectiveWs}
              onWorkspaceChange={(id) => {
                if (lockScope) return;
                setWorkspaceId(id);
                setSelectedId(null);
                setWizardStep(1);
              }}
              spaces={spaces}
              selectedSpaces={selectedSpaces}
              onToggleSpace={(id) =>
                setSelectedSpaces((prev) =>
                  prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
                )
              }
              pageTrees={pageTrees.data}
              selectedDocs={selectedDocs}
              onToggleDoc={(id) =>
                setSelectedDocs((prev) =>
                  prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
                )
              }
              onSelectAllDocs={() => setSelectedDocs(allPageIds)}
              onClearDocs={() => setSelectedDocs([])}
              focusPrompt={focusPrompt}
              onFocusChange={setFocusPrompt}
              onNext={() => setWizardStep(2)}
              onBack={() => setWizardStep(1)}
              onGenerate={() => createArtifact.mutate(filterType)}
              canProceed={canCreate}
              geminiConnected={!!geminiConnected}
              lockWorkspace={lockScope}
            />
          )}
        </aside>

        <div className="flex min-h-0 min-w-0 flex-1 overflow-hidden">
          <StudioPreviewPanel
            filterType={filterType}
            focusPrompt={focusPrompt}
            artifact={selectedId ? artifact : null}
            localSlides={localSlides}
            localNodes={localNodes}
            workspaceId={effectiveWs}
            fallbackSpaceId={fallbackSpaceId}
            modelName={modelName}
            onChangeSlides={setLocalSlides}
            onChangeNodes={setLocalNodes}
            onRegenerateSlide={(id) => regenerate.mutate(id)}
            onSelectSource={setSelectedSource}
            onToggleCollapse={toggleMindmapCollapse}
          />

          {selectedSource ? (
            <div className="hidden w-80 shrink-0 overflow-y-auto border-l border-border bg-surface p-4 lg:block">
              <SourceRefPanel
                source={selectedSource}
                workspaceId={effectiveWs}
                fallbackSpaceId={fallbackSpaceId}
                onClose={() => setSelectedSource(null)}
              />
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
