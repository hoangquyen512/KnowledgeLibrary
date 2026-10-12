import type { LucideIcon } from "lucide-react";
import {
  File,
  FileSpreadsheet,
  FileText,
  FileType2,
  LayoutTemplate,
  Presentation,
} from "lucide-react";

/** Source types used by multi-source Add Source flows. */
export type KlSourceType =
  | "CONFLUENCE"
  | "JIRA"
  | "FILE_EXCEL"
  | "FILE_CSV"
  | "FILE_WORD"
  | "FILE_POWERPOINT"
  | "FILE_PDF"
  | "FILE_UPLOAD";

export type FileSourceTypeHint =
  | "FILE_EXCEL"
  | "FILE_CSV"
  | "FILE_WORD"
  | "FILE_POWERPOINT"
  | "FILE_PDF";

export type JiraConnection = {
  id: string;
  workspace_id: string;
  name: string;
  base_url: string;
  auth_type: string;
  masked_suffix: string;
  status: string;
  detected_version: string | null;
  last_tested_at: string | null;
  last_error: string | null;
};

export type JiraProject = {
  id: string;
  key: string;
  name: string;
  url?: string | null;
};

export type JiraScope = {
  issues: boolean;
  comments: boolean;
  attachments: boolean;
  description: boolean;
  acceptance_criteria: boolean;
  change_history: boolean;
};

export const DEFAULT_JIRA_SCOPE: JiraScope = {
  issues: true,
  comments: true,
  attachments: true,
  description: true,
  acceptance_criteria: true,
  change_history: false,
};

const FILE_TYPES = new Set<string>([
  "FILE_EXCEL",
  "FILE_CSV",
  "FILE_WORD",
  "FILE_POWERPOINT",
  "FILE_PDF",
  "FILE_UPLOAD",
]);

export function isFileSourceType(type: string | null | undefined): boolean {
  return !!type && FILE_TYPES.has(type);
}

export function isSyncable(type: string | null | undefined): boolean {
  return type === "CONFLUENCE" || type === "JIRA";
}

export function sourceTypeLabel(type: string | null | undefined): string {
  switch (type) {
    case "CONFLUENCE":
      return "Confluence";
    case "JIRA":
      return "Jira";
    case "FILE_EXCEL":
      return "Excel";
    case "FILE_CSV":
      return "CSV";
    case "FILE_WORD":
      return "Word";
    case "FILE_POWERPOINT":
      return "PowerPoint";
    case "FILE_PDF":
      return "PDF";
    case "FILE_UPLOAD":
      return "Upload";
    default:
      return type || "Source";
  }
}

export function sourceTypeIcon(type: string | null | undefined): LucideIcon {
  switch (type) {
    case "CONFLUENCE":
      return LayoutTemplate;
    case "JIRA":
      return FileType2;
    case "FILE_EXCEL":
    case "FILE_CSV":
      return FileSpreadsheet;
    case "FILE_WORD":
      return FileText;
    case "FILE_POWERPOINT":
      return Presentation;
    case "FILE_PDF":
      return File;
    default:
      return File;
  }
}

/** document_count unit label by source type */
export function documentUnit(type: string | null | undefined, count = 0): string {
  const n = count;
  switch (type) {
    case "CONFLUENCE":
      return n === 1 ? "page" : "pages";
    case "JIRA":
      return n === 1 ? "issue" : "issues";
    case "FILE_EXCEL":
    case "FILE_CSV":
      return n === 1 ? "sheet" : "sheets";
    case "FILE_WORD":
    case "FILE_POWERPOINT":
    case "FILE_PDF":
    case "FILE_UPLOAD":
      return n === 1 ? "document" : "documents";
    default:
      return n === 1 ? "item" : "items";
  }
}

/** Accept attribute / extension filters for upload cards */
export function acceptForSourceHint(hint?: FileSourceTypeHint | null): string {
  switch (hint) {
    case "FILE_EXCEL":
    case "FILE_CSV":
      return ".xlsx,.xls,.csv";
    case "FILE_WORD":
      return ".docx";
    case "FILE_POWERPOINT":
      return ".pptx";
    case "FILE_PDF":
      return ".pdf";
    default:
      return ".xlsx,.xls,.csv,.docx,.pptx,.pdf";
  }
}

export function inferSourceTypeFromFilename(
  filename: string,
  hint?: FileSourceTypeHint | null,
): FileSourceTypeHint | undefined {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".csv")) return "FILE_CSV";
  if (lower.endsWith(".xlsx") || lower.endsWith(".xls")) return "FILE_EXCEL";
  if (lower.endsWith(".docx")) return "FILE_WORD";
  if (lower.endsWith(".pptx")) return "FILE_POWERPOINT";
  if (lower.endsWith(".pdf")) return "FILE_PDF";
  if (hint === "FILE_EXCEL" || hint === "FILE_CSV") return hint;
  return hint || undefined;
}

export function uploadDialogTitle(hint?: FileSourceTypeHint | null): string {
  switch (hint) {
    case "FILE_EXCEL":
    case "FILE_CSV":
      return "Upload Excel / CSV";
    case "FILE_WORD":
      return "Upload Word";
    case "FILE_POWERPOINT":
      return "Upload PowerPoint";
    case "FILE_PDF":
      return "Upload PDF";
    default:
      return "Upload files";
  }
}
