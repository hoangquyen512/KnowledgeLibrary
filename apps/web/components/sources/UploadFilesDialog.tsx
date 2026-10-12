"use client";

import { useQueryClient } from "@tanstack/react-query";
import { FileUp, Loader2, Upload, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ApiError, clientApi } from "@/lib/api";
import {
  acceptForSourceHint,
  inferSourceTypeFromFilename,
  uploadDialogTitle,
  type FileSourceTypeHint,
} from "@/lib/sources";

type UploadSourceResult = {
  source_id: string;
  job_id?: string | null;
  filename: string;
  status: string;
  duplicate?: boolean;
  preview?: {
    sheets?: { name: string; row_count?: number }[];
    [key: string]: unknown;
  };
};

type UploadResponse = {
  sources: UploadSourceResult[];
  errors?: { filename?: string; code?: string; message?: string }[];
};

type PendingDuplicate = {
  file: File;
  sourceType?: FileSourceTypeHint;
};

type SheetPickState = {
  sourceId: string;
  filename: string;
  sheets: { name: string; row_count?: number }[];
  selected: Set<string>;
};

export function UploadFilesDialog({
  open,
  onClose,
  workspaceId: _workspaceId,
  spaceId,
  sourceTypeHint,
  replaceSourceId,
}: {
  open: boolean;
  onClose: () => void;
  workspaceId: string;
  spaceId: string;
  sourceTypeHint?: FileSourceTypeHint;
  /** When set, upload replaces this file source (keeps source id, bumps version). */
  replaceSourceId?: string;
}) {
  const client = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [duplicate, setDuplicate] = useState<PendingDuplicate | null>(null);
  const [sheetPick, setSheetPick] = useState<SheetPickState | null>(null);
  const [importingSheets, setImportingSheets] = useState(false);

  useEffect(() => {
    if (!open) return;
    setFiles([]);
    setDragging(false);
    setUploading(false);
    setDuplicate(null);
    setSheetPick(null);
    setImportingSheets(false);
  }, [open, sourceTypeHint]);

  const accept = acceptForSourceHint(sourceTypeHint);

  const addFiles = (list: FileList | File[]) => {
    const next = Array.from(list);
    if (!next.length) return;
    setFiles((prev) => {
      const names = new Set(prev.map((f) => `${f.name}:${f.size}`));
      const merged = [...prev];
      for (const f of next) {
        const key = `${f.name}:${f.size}`;
        if (!names.has(key)) {
          names.add(key);
          merged.push(f);
        }
      }
      return merged;
    });
  };

  const finishSuccess = () => {
    client.invalidateQueries({ queryKey: ["sources", spaceId] });
    client.invalidateQueries({ queryKey: ["space", spaceId] });
    toast.success("Files uploaded.");
    onClose();
  };

  const maybeSheetPick = (results: UploadSourceResult[]): boolean => {
    const needsSheets = results.find((r) => {
      const sheets = r.preview?.sheets;
      const ready =
        r.status === "UPLOADED" ||
        r.status === "READY_TO_IMPORT" ||
        r.status === "CONNECTED";
      return ready && Array.isArray(sheets) && sheets.length > 0 && !r.job_id;
    });
    if (!needsSheets?.preview?.sheets?.length) return false;
    const sheetNames = needsSheets.preview.sheets.map((s) =>
      typeof s === "string" ? { name: s } : { name: s.name, row_count: s.row_count },
    );
    setSheetPick({
      sourceId: needsSheets.source_id,
      filename: needsSheets.filename,
      sheets: sheetNames,
      selected: new Set(sheetNames.map((s) => s.name)),
    });
    return true;
  };

  const uploadOne = async (file: File, forceNew = false): Promise<UploadResponse> => {
    const sourceType = inferSourceTypeFromFilename(file.name, sourceTypeHint);
    const form = new FormData();
    form.append("file", file);
    if (sourceType) form.append("source_type", sourceType);
    if (forceNew) form.append("force_new", "true");
    if (replaceSourceId) form.append("replace_source_id", replaceSourceId);
    return clientApi<UploadResponse>(`/spaces/${spaceId}/sources/upload`, {
      method: "POST",
      body: form,
    });
  };

  const handleUploadBatch = async (batch: File[], forceNew = false) => {
    setUploading(true);
    const collected: UploadSourceResult[] = [];
    try {
      for (const file of batch) {
        try {
          const resp = await uploadOne(file, forceNew);
          const rows = resp.sources || [];
          const dup =
            rows.some((r) => r.duplicate) ||
            (resp.errors || []).some((e) => e.code === "FILE_DUPLICATE");
          if (dup && !forceNew) {
            setDuplicate({
              file,
              sourceType: inferSourceTypeFromFilename(file.name, sourceTypeHint),
            });
            collected.push(...rows);
            // Keep remaining files for after duplicate resolution
            setFiles((prev) => prev.filter((f) => f !== file));
            setUploading(false);
            return;
          }
          collected.push(...rows);
          for (const err of resp.errors || []) {
            toast.error(err.message || `Failed: ${err.filename || file.name}`);
          }
        } catch (e) {
          if (e instanceof ApiError && e.code === "FILE_DUPLICATE" && !forceNew) {
            setDuplicate({
              file,
              sourceType: inferSourceTypeFromFilename(file.name, sourceTypeHint),
            });
            setFiles((prev) => prev.filter((f) => f !== file));
            setUploading(false);
            return;
          }
          toast.error(e instanceof Error ? e.message : `Failed to upload ${file.name}`);
        }
      }
      setFiles([]);
      setDuplicate(null);
      if (collected.length && maybeSheetPick(collected)) {
        client.invalidateQueries({ queryKey: ["sources", spaceId] });
        setUploading(false);
        return;
      }
      if (collected.length) finishSuccess();
    } finally {
      setUploading(false);
    }
  };

  const startImportWithSheets = async () => {
    if (!sheetPick) return;
    const names = Array.from(sheetPick.selected);
    if (!names.length) {
      toast.error("Select at least one sheet.");
      return;
    }
    setImportingSheets(true);
    try {
      await clientApi(`/sources/${sheetPick.sourceId}/import`, {
        method: "POST",
        body: JSON.stringify({ options: { sheet_names: names } }),
      });
      finishSuccess();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Import failed.");
    } finally {
      setImportingSheets(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
      <section className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-border bg-surface p-5 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">
              {replaceSourceId ? "Replace file" : uploadDialogTitle(sourceTypeHint)}
            </h2>
            <p className="mt-1 text-xs text-muted">
              {replaceSourceId
                ? "Upload a new version. The source identity stays the same; AI indexes are rebuilt."
                : "Each file becomes its own source in this Space."}
            </p>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        {duplicate ? (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/40">
            <p className="text-sm font-medium text-amber-950 dark:text-amber-100">
              This file already exists in this Space.
            </p>
            <p className="mt-1 text-xs text-amber-900/80 dark:text-amber-100/80">
              {duplicate.file.name}
            </p>
            <div className="mt-4 flex flex-wrap justify-end gap-2">
              <button
                type="button"
                className="secondary-button"
                disabled={uploading}
                onClick={() => {
                  setDuplicate(null);
                  if (!files.length) onClose();
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="primary-button"
                disabled={uploading}
                onClick={() => void handleUploadBatch([duplicate.file], true)}
              >
                {uploading ? <Loader2 size={16} className="animate-spin" /> : null}
                Upload as new version
              </button>
            </div>
          </div>
        ) : sheetPick ? (
          <div>
            <p className="text-sm text-muted">
              Select sheets to import from <span className="font-medium text-foreground">{sheetPick.filename}</span>.
            </p>
            <ul className="mt-3 max-h-56 space-y-2 overflow-auto">
              {sheetPick.sheets.map((s) => (
                <li key={s.name}>
                  <label className="flex cursor-pointer items-center gap-2.5 rounded-xl border border-border bg-surface px-3 py-2.5 text-sm hover:bg-surface-muted">
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-primary"
                      checked={sheetPick.selected.has(s.name)}
                      onChange={(e) => {
                        setSheetPick((prev) => {
                          if (!prev) return prev;
                          const next = new Set(prev.selected);
                          if (e.target.checked) next.add(s.name);
                          else next.delete(s.name);
                          return { ...prev, selected: next };
                        });
                      }}
                    />
                    <span className="min-w-0 flex-1 truncate">{s.name}</span>
                    {typeof s.row_count === "number" ? (
                      <span className="text-xs text-muted">{s.row_count} rows</span>
                    ) : null}
                  </label>
                </li>
              ))}
            </ul>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                className="secondary-button"
                disabled={importingSheets}
                onClick={onClose}
              >
                Skip for now
              </button>
              <button
                type="button"
                className="primary-button"
                disabled={importingSheets || sheetPick.selected.size === 0}
                onClick={() => void startImportWithSheets()}
              >
                {importingSheets ? <Loader2 size={16} className="animate-spin" /> : null}
                Import selected sheets
              </button>
            </div>
          </div>
        ) : (
          <>
            <div
              role="button"
              tabIndex={0}
              className={`flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed px-4 py-10 text-center transition ${
                dragging
                  ? "border-primary bg-surface-muted"
                  : "border-border bg-surface-muted/40 hover:bg-surface-muted"
              }`}
              onDragEnter={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={(e) => {
                e.preventDefault();
                setDragging(false);
              }}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files);
              }}
              onClick={() => inputRef.current?.click()}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  inputRef.current?.click();
                }
              }}
            >
              <Upload size={28} className="text-muted" aria-hidden />
              <p className="mt-3 text-sm font-medium">Drag & drop files here</p>
              <p className="mt-1 text-xs text-muted">or click to choose files ({accept})</p>
            </div>
            <input
              ref={inputRef}
              type="file"
              className="hidden"
              accept={accept}
              multiple
              onChange={(e) => {
                if (e.target.files?.length) addFiles(e.target.files);
                e.target.value = "";
              }}
            />

            {files.length > 0 ? (
              <ul className="mt-3 max-h-40 space-y-1.5 overflow-auto">
                {files.map((f) => (
                  <li
                    key={`${f.name}-${f.size}-${f.lastModified}`}
                    className="flex items-center gap-2 rounded-xl border border-border bg-surface px-3 py-2 text-sm"
                  >
                    <FileUp size={14} className="shrink-0 text-muted" />
                    <span className="min-w-0 flex-1 truncate">{f.name}</span>
                    <span className="shrink-0 text-xs text-muted">
                      {(f.size / 1024).toFixed(0)} KB
                    </span>
                    <button
                      type="button"
                      className="icon-button h-7 w-7"
                      aria-label={`Remove ${f.name}`}
                      disabled={uploading}
                      onClick={() =>
                        setFiles((prev) => prev.filter((x) => x !== f))
                      }
                    >
                      <X size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}

            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                className="secondary-button"
                onClick={onClose}
                disabled={uploading}
              >
                Cancel
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled={uploading}
                onClick={() => inputRef.current?.click()}
              >
                Choose files
              </button>
              <button
                type="button"
                className="primary-button"
                disabled={!files.length || uploading}
                onClick={() => void handleUploadBatch(files)}
              >
                {uploading ? <Loader2 size={16} className="animate-spin" /> : null}
                Upload{files.length ? ` (${files.length})` : ""}
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
