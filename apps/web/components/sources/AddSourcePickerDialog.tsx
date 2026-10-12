"use client";

import {
  ChevronRight,
  File,
  FileSpreadsheet,
  FileText,
  FileType2,
  LayoutTemplate,
  Presentation,
  X,
} from "lucide-react";
import type { FileSourceTypeHint } from "@/lib/sources";

export type AddSourceKind =
  | "CONFLUENCE"
  | "JIRA"
  | "FILE_EXCEL"
  | "FILE_WORD"
  | "FILE_POWERPOINT"
  | "FILE_PDF";

type PickerCard = {
  kind: AddSourceKind;
  title: string;
  description: string;
  icon: typeof LayoutTemplate;
  /** Hint passed to upload dialog (Excel card covers CSV too). */
  uploadHint?: FileSourceTypeHint;
};

const CARDS: PickerCard[] = [
  {
    kind: "CONFLUENCE",
    title: "Confluence",
    description: "Connect Confluence Data Center.",
    icon: LayoutTemplate,
  },
  {
    kind: "JIRA",
    title: "Jira",
    description: "Import Jira projects, issues and related information.",
    icon: FileType2,
  },
  {
    kind: "FILE_EXCEL",
    title: "Excel / CSV",
    description: "Upload structured spreadsheet data.",
    icon: FileSpreadsheet,
    uploadHint: "FILE_EXCEL",
  },
  {
    kind: "FILE_WORD",
    title: "Word",
    description: "Upload Word documents.",
    icon: FileText,
    uploadHint: "FILE_WORD",
  },
  {
    kind: "FILE_POWERPOINT",
    title: "PowerPoint",
    description: "Upload presentation files.",
    icon: Presentation,
    uploadHint: "FILE_POWERPOINT",
  },
  {
    kind: "FILE_PDF",
    title: "PDF",
    description: "Upload PDF documents.",
    icon: File,
    uploadHint: "FILE_PDF",
  },
];

export function AddSourcePickerDialog({
  open,
  onClose,
  onSelect,
}: {
  open: boolean;
  onClose: () => void;
  onSelect: (kind: AddSourceKind, uploadHint?: FileSourceTypeHint) => void;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-source-picker-title"
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-border bg-surface p-5 shadow-2xl"
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 id="add-source-picker-title" className="text-lg font-semibold">
              Add Source
            </h2>
            <p className="mt-1 text-sm text-muted">Choose where your knowledge comes from.</p>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <ul className="space-y-2">
          {CARDS.map((card) => {
            const Icon = card.icon;
            return (
              <li key={card.kind}>
                <button
                  type="button"
                  className="flex w-full items-center gap-3 rounded-2xl border border-border bg-surface px-3.5 py-3 text-left transition hover:bg-surface-muted"
                  onClick={() => onSelect(card.kind, card.uploadHint)}
                >
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-surface-muted text-foreground">
                    <Icon size={18} aria-hidden />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-semibold">{card.title}</span>
                    <span className="mt-0.5 block text-xs text-muted">{card.description}</span>
                  </span>
                  <ChevronRight size={16} className="shrink-0 text-muted" aria-hidden />
                </button>
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}
