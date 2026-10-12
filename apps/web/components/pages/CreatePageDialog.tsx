"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { clientApi } from "@/lib/api";
import type { PageDetail } from "@/lib/pages";

export function CreatePageDialog({
  open,
  onClose,
  spaceId,
  sourceId,
  parentId,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  spaceId: string;
  sourceId: string;
  parentId: string | null;
  onCreated: (page: PageDetail) => void;
}) {
  const client = useQueryClient();
  const [title, setTitle] = useState("");

  const create = useMutation({
    mutationFn: () =>
      clientApi<PageDetail>(`/spaces/${spaceId}/pages`, {
        method: "POST",
        body: JSON.stringify({
          title: title.trim(),
          parent_id: parentId,
          content: "",
          source_id: sourceId,
        }),
      }),
    onSuccess: (page) => {
      client.invalidateQueries({ queryKey: ["page-tree", spaceId, sourceId] });
      toast.success("Page created");
      setTitle("");
      onCreated(page);
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
      <section className="w-full max-w-md rounded-2xl border border-border bg-surface p-5 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Create Page</h2>
          <button type="button" className="icon-button" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <label className="label">
          Page title
          <input
            autoFocus
            className="input mt-1.5"
            value={title}
            maxLength={255}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Untitled"
          />
        </label>
        <p className="mt-2 text-xs text-muted">
          {parentId ? "Will be created as a child page." : "Will be created at the Space root."}
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={!title.trim() || create.isPending}
            onClick={() => create.mutate()}
          >
            Create
          </button>
        </div>
      </section>
    </div>
  );
}
