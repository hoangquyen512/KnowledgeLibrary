"use client";

import { useQuery } from "@tanstack/react-query";
import { FolderPlus } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { AddSourceDialog } from "@/components/confluence/AddSourceDialog";
import { SpaceImportMonitor } from "@/components/ingestion/SpaceImportMonitor";
import {
  AddJiraSourceDialog,
  AddSourcePickerDialog,
  UploadFilesDialog,
  type AddSourceKind,
} from "@/components/sources";
import { clientApi, type Space } from "@/lib/api";
import type { FileSourceTypeHint } from "@/lib/sources";

export default function SpaceSourcesPage() {
  const { id, spaceId } = useParams<{ id: string; spaceId: string }>();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [confluenceOpen, setConfluenceOpen] = useState(false);
  const [jiraOpen, setJiraOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadHint, setUploadHint] = useState<FileSourceTypeHint | undefined>();

  const { data: space, isLoading, error } = useQuery({
    queryKey: ["space", spaceId],
    queryFn: () => clientApi<Space>(`/spaces/${spaceId}`),
  });

  if (isLoading) return <div className="page-loading p-6">Loading sources…</div>;
  if (error || !space) {
    return <div className="error-state m-6">You don&apos;t have access to this Space.</div>;
  }

  const canAdd = space.my_role !== "VIEWER" && space.status !== "ARCHIVED";

  const openPicker = () => setPickerOpen(true);

  const onSelectKind = (kind: AddSourceKind, hint?: FileSourceTypeHint) => {
    setPickerOpen(false);
    if (kind === "CONFLUENCE") {
      setConfluenceOpen(true);
      return;
    }
    if (kind === "JIRA") {
      setJiraOpen(true);
      return;
    }
    setUploadHint(hint || (kind as FileSourceTypeHint));
    setUploadOpen(true);
  };

  return (
    <div className="h-full min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">Sources</h1>
          <p className="mt-1 text-sm text-muted">
            Connect Confluence or Jira, or upload Excel, Word, PowerPoint, and PDF files. Import and
            sync from here.
          </p>
        </div>
        <button
          type="button"
          className="secondary-button"
          onClick={openPicker}
          disabled={!canAdd}
        >
          <FolderPlus size={16} /> Add Source
        </button>
      </div>

      <SpaceImportMonitor
        workspaceId={id}
        spaceId={spaceId}
        spaceName={space.name}
        canManage={canAdd}
        onAddSource={openPicker}
      />

      <AddSourcePickerDialog
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={onSelectKind}
      />
      <AddSourceDialog
        open={confluenceOpen}
        onClose={() => setConfluenceOpen(false)}
        workspaceId={id}
        spaceId={spaceId}
      />
      <AddJiraSourceDialog
        open={jiraOpen}
        onClose={() => setJiraOpen(false)}
        workspaceId={id}
        spaceId={spaceId}
      />
      <UploadFilesDialog
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        workspaceId={id}
        spaceId={spaceId}
        sourceTypeHint={uploadHint}
      />
    </div>
  );
}
