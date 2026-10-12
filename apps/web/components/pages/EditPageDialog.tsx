"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { clientApi } from "@/lib/api";
import type { PageDetail } from "@/lib/pages";

export function EditPageDialog({
  open,
  onClose,
  page,
}: {
  open: boolean;
  onClose: () => void;
  page: PageDetail;
}) {
  const client = useQueryClient();
  const [title, setTitle] = useState(page.title);
  const [content, setContent] = useState(page.raw_content || page.normalized_content || "");

  useEffect(() => {
    if (open) {
      setTitle(page.title);
      setContent(page.raw_content || page.normalized_content || "");
    }
  }, [open, page]);

  const save = useMutation({
    mutationFn: () =>
      clientApi<PageDetail>(`/pages/${page.id}`, {
        method: "PATCH",
        body: JSON.stringify({ title: title.trim(), content }),
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["page", page.id] });
      client.invalidateQueries({ queryKey: ["page-tree", page.space_id] });
      toast.success("Saved");
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
      <section className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-2xl border border-border bg-surface p-5 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Edit Page</h2>
          <button type="button" className="icon-button" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <label className="label">
          Title
          <input
            className="input mt-1.5"
            value={title}
            maxLength={255}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <label className="label mt-3 flex min-h-0 flex-1 flex-col">
          Content
          <textarea
            className="input mt-1.5 min-h-[240px] flex-1 font-mono text-sm"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Markdown or HTML…"
          />
        </label>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={!title.trim() || save.isPending}
            onClick={() => save.mutate()}
          >
            {save.isPending ? "Saving…" : "Save"}
          </button>
        </div>
      </section>
    </div>
  );
}
