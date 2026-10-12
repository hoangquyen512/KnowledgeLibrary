"use client";

import { useQuery } from "@tanstack/react-query";
import { Download, Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { clientApi } from "@/lib/api";

export type ExportGroupDepth = 0 | 1 | 2 | 3 | 4 | 5;

type ExportPreview = {
  source_id: string;
  document_count: number;
  file_counts: Record<string, number>;
};

const OPTIONS: {
  value: ExportGroupDepth;
  title: string;
  hint: string;
}[] = [
  {
    value: 0,
    title: "Mỗi trang một file",
    hint: "Nhẹ nhất — phù hợp NotebookLM khi source lớn hoặc cây sâu.",
  },
  {
    value: 1,
    title: "Gộp theo cấp 1",
    hint: "Gộp các trang con dưới root level 1. File lớn hơn.",
  },
  {
    value: 2,
    title: "Gộp theo cấp 2",
    hint: "Mặc định — cân bằng giữa số file và kích thước.",
  },
  {
    value: 3,
    title: "Gộp theo cấp 3",
    hint: "Ít gộp hơn cấp 2 — file nhỏ hơn, nhiều file hơn.",
  },
  {
    value: 4,
    title: "Gộp theo cấp 4",
    hint: "Gần như tách theo nhánh sâu trong cây trang.",
  },
  {
    value: 5,
    title: "Gộp theo cấp 5",
    hint: "Gần với mỗi trang một file nếu cây không sâu hơn 5.",
  },
];

function formatFileCount(n: number | undefined): string {
  if (n == null || !Number.isFinite(n)) return "…";
  if (n === 1) return "1 file";
  return `${n.toLocaleString()} files`;
}

export function ExportMdDialog({
  open,
  sourceId,
  sourceName,
  pending,
  onClose,
  onConfirm,
}: {
  open: boolean;
  sourceId?: string | null;
  sourceName: string;
  pending?: boolean;
  onClose: () => void;
  onConfirm: (groupDepth: ExportGroupDepth) => void;
}) {
  const [depth, setDepth] = useState<ExportGroupDepth>(2);

  const { data: preview, isFetching, isError } = useQuery({
    queryKey: ["export-md-preview", sourceId],
    queryFn: () =>
      clientApi<ExportPreview>(`/sources/${sourceId}/export-preview`),
    enabled: open && !!sourceId,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (!open) return;
    setDepth(2);
  }, [open, sourceId, sourceName]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
      <section className="max-h-[90vh] w-full max-w-md overflow-y-auto rounded-2xl border border-border bg-surface p-5 shadow-2xl">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Download Markdown</h2>
            <p className="mt-1 text-sm text-muted">
              Chọn cấp gộp cho{" "}
              <span className="font-medium text-foreground">{sourceName || "source"}</span>. Cấp
              thấp hơn → ít file nhưng nặng hơn; cấp cao / mỗi trang → nhẹ hơn cho NotebookLM.
            </p>
            {preview ? (
              <p className="mt-1.5 text-xs text-muted">
                {preview.document_count.toLocaleString()} document
                {preview.document_count === 1 ? "" : "s"} sẵn sàng export
                {isFetching ? " · updating…" : ""}
              </p>
            ) : isFetching ? (
              <p className="mt-1.5 text-xs text-muted">Đang tính số file…</p>
            ) : isError ? (
              <p className="mt-1.5 text-xs text-rose-600 dark:text-rose-300">
                Không lấy được số file preview (API chưa có route hoặc cần reload). Vẫn có
                thể Download bình thường.
              </p>
            ) : null}
          </div>
          <button
            type="button"
            className="icon-button shrink-0"
            onClick={onClose}
            aria-label="Close"
            disabled={pending}
          >
            <X size={18} />
          </button>
        </div>

        <fieldset className="space-y-2" disabled={pending}>
          <legend className="sr-only">Group depth</legend>
          {OPTIONS.map((opt) => {
            const selected = depth === opt.value;
            const count = preview?.file_counts?.[String(opt.value)];
            return (
              <label
                key={opt.value}
                className={`flex cursor-pointer gap-3 rounded-xl border px-3 py-2.5 transition-colors ${
                  selected
                    ? "border-emerald-600/50 bg-emerald-50 dark:border-emerald-500/40 dark:bg-emerald-950/30"
                    : "border-border hover:bg-muted/40"
                }`}
              >
                <input
                  type="radio"
                  name="export-group-depth"
                  className="mt-1"
                  checked={selected}
                  onChange={() => setDepth(opt.value)}
                />
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="text-sm font-medium">{opt.title}</span>
                    <span className="shrink-0 text-xs font-medium tabular-nums text-muted">
                      {formatFileCount(count)}
                    </span>
                  </span>
                  <span className="mt-0.5 block text-xs text-muted">{opt.hint}</span>
                  {count != null ? (
                    <span className="mt-1 block text-xs text-muted">
                      Tạo ra {formatFileCount(count)} trong zip
                      {preview && count < preview.document_count
                        ? ` (gộp từ ${preview.document_count.toLocaleString()} documents)`
                        : ""}
                      .
                    </span>
                  ) : null}
                </span>
              </label>
            );
          })}
        </fieldset>

        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose} disabled={pending}>
            Cancel
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={pending}
            onClick={() => onConfirm(depth)}
          >
            {pending ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
            Download
            {preview?.file_counts?.[String(depth)] != null
              ? ` · ${formatFileCount(preview.file_counts[String(depth)])}`
              : ""}
          </button>
        </div>
      </section>
    </div>
  );
}
