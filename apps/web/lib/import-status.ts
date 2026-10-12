export type ImportJobStatus =
  | "QUEUED"
  | "RUNNING"
  | "CANCEL_REQUESTED"
  | "COMPLETED"
  | "COMPLETED_WITH_ERRORS"
  | "FAILED"
  | "CANCELLED";

export type JobStageStatus = "pending" | "in_progress" | "completed" | "failed" | "skipped";

export type JobStats = {
  total_pages: number;
  processed_pages: number;
  total_attachments: number;
  processed_attachments: number;
  total_diagrams: number;
  processed_diagrams: number;
  failed_items: number;
};

export type ImportJob = {
  id: string;
  workspace_id: string;
  space_id: string;
  source_id: string;
  status?: ImportJobStatus | string | null;
  progress_percent?: number | null;
  stage: string;
  message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at?: string | null;
  source?: { id: string; name: string; type: string; import_scope?: string | null };
  stats?: JobStats | null;
  stages?: { key: string; label: string; status: JobStageStatus | string }[];
  current_items?: { name: string; status: string; type?: string; at?: string | null }[];
  eta_seconds?: number | null;
  cancel_requested?: boolean;
  started_by_name?: string | null;
  import_mode?: string | null;
  destination_name?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  job_type?: string;
  sync_stats?: {
    added?: number;
    updated?: number;
    removed?: number;
    unchanged?: number;
    failed?: number;
  } | null;
};

export type SourceRow = {
  id: string;
  name: string;
  status: string;
  type?: string;
  connection_id?: string | null;
  jira_connection_id?: string | null;
  external_key: string | null;
  external_type: string | null;
  import_scope?: string | null;
  latest_job_id?: string | null;
  document_count?: number;
  attachment_count?: number;
  sync_enabled?: boolean;
  sync_interval?: string;
  last_sync_at?: string | null;
  last_sync_status?: string | null;
  last_sync_summary?: {
    added?: number;
    updated?: number;
    removed?: number;
    unchanged?: number;
    failed?: number;
  } | null;
  last_sync_error?: string | null;
  next_sync_at?: string | null;
};

const ACTIVE = new Set([
  "QUEUED",
  "RUNNING",
  "CANCEL_REQUESTED",
  "IMPORTING",
  "SCANNING",
  "PARSING",
  "INDEXING",
]);

/** Coerce API/optimistic progress into a finite 0–100 value (avoids NaN%). */
export function safeProgressPercent(value: unknown): number {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(100, n));
}

export function isJobActive(status: string | null | undefined) {
  if (!status) return false;
  return ACTIVE.has(status) || status === "IMPORTING";
}

export function isSourceImporting(status: string | null | undefined) {
  return (
    status === "IMPORTING" ||
    status === "PARSING" ||
    status === "INDEXING" ||
    status === "SCANNING"
  );
}

function unknownBadge(status: string | null | undefined): {
  label: string;
  shortLabel: string;
  className: string;
} {
  const safe = (status || "Unknown").trim() || "Unknown";
  return {
    label: safe,
    shortLabel: safe.slice(0, 8),
    className: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
  };
}

export function mapSourceBadge(status: string | null | undefined): {
  label: string;
  shortLabel?: string;
  className: string;
} {
  switch (status) {
    case "IMPORTING":
    case "PARSING":
    case "INDEXING":
    case "SCANNING":
      return {
        label:
          status === "PARSING"
            ? "Parsing"
            : status === "INDEXING"
              ? "Indexing"
              : status === "SCANNING"
                ? "Scanning"
                : "Importing",
        shortLabel:
          status === "PARSING"
            ? "PARSE"
            : status === "INDEXING"
              ? "INDEX"
              : status === "SCANNING"
                ? "SCAN"
                : "RUN",
        className: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
      };
    case "READY":
    case "SYNCED":
    case "INDEXED":
      return {
        label: status === "INDEXED" ? "Indexed" : status === "SYNCED" ? "Synced" : "Synced",
        shortLabel: "OK",
        className: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
      };
    case "UPLOADED":
      return {
        label: "Uploaded",
        shortLabel: "UP",
        className: "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-200",
      };
    case "READY_TO_IMPORT":
    case "CONNECTED":
      return {
        label: "Ready",
        shortLabel: "READY",
        className: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
      };
    case "ERROR":
    case "FAILED":
      return {
        label: "Failed",
        shortLabel: "ERR",
        className: "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-200",
      };
    case "NEEDS_ATTENTION":
      return {
        label: "Needs attention",
        shortLabel: "ATTN",
        className: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
      };
    case "DISABLED":
      return {
        label: "Disabled",
        shortLabel: "OFF",
        className: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
      };
    default:
      return unknownBadge(status);
  }
}

export function mapJobBadge(status: string | null | undefined): {
  label: string;
  shortLabel?: string;
  className: string;
} {
  switch (status) {
    case "QUEUED":
      return {
        label: "Queued",
        shortLabel: "QUEUE",
        className: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
      };
    case "RUNNING":
      return {
        label: "Importing",
        shortLabel: "RUN",
        className: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
      };
    case "CANCEL_REQUESTED":
      return {
        label: "Stopping",
        shortLabel: "STOP",
        className: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
      };
    case "COMPLETED":
      return {
        label: "Completed",
        shortLabel: "DONE",
        className: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
      };
    case "COMPLETED_WITH_ERRORS":
      return {
        label: "Completed with errors",
        shortLabel: "PARTIAL",
        className: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
      };
    case "FAILED":
      return {
        label: "Failed",
        shortLabel: "FAIL",
        className: "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-200",
      };
    case "CANCELLED":
      return {
        label: "Canceled",
        shortLabel: "CANCEL",
        className: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
      };
    default:
      return unknownBadge(status);
  }
}

export function formatEta(seconds: number | null | undefined): string {
  if (seconds == null || seconds <= 0) return "Calculating…";
  if (seconds < 60) return `${seconds}s`;
  const m = Math.round(seconds / 60);
  return `${m} min`;
}

export function formatDuration(started: string | null, ended: string | null): string {
  if (!started || !ended) return "—";
  const ms = new Date(ended).getTime() - new Date(started).getTime();
  if (ms < 0) return "—";
  const sec = Math.floor(ms / 1000);
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  if (m <= 0) return `${s}s`;
  return `${m} min ${s.toString().padStart(2, "0")} sec`;
}

export function mapErrorMessage(code: string | null | undefined, fallback?: string | null): string {
  switch (code) {
    case "CONFLUENCE_AUTH_FAILED":
      return "Confluence authentication failed.";
    case "CONFLUENCE_SESSION_EXPIRED":
      return "Your Confluence session has expired. Update the connection cookie/PAT, then sync again.";
    case "CONFLUENCE_ACCESS_DENIED":
      return "You don't have permission to access this content.";
    case "CONNECTOR_OFFLINE":
      return "The local connector is offline.";
    case "SOURCE_NOT_FOUND":
      return "The Confluence space could not be found or you don't have access. Check the space key and connection.";
    case "IMPORT_CANCELED":
    case "IMPORT_CANCELLED":
      return "Import was canceled.";
    case "JIRA_AUTH_FAILED":
      return "Jira authentication failed. Check the token and try again.";
    case "JIRA_ACCESS_DENIED":
      return "You don't have permission to access this Jira project.";
    case "JIRA_PROJECT_NOT_FOUND":
      return "The Jira project could not be found or is not accessible.";
    case "JIRA_API_ERROR":
      return "Jira returned an error. Check the connection and try again.";
    case "CONNECTION_INACTIVE":
      return "Test the connection first before continuing.";
    case "FILE_DUPLICATE":
      return "This file already exists in this Space.";
    case "FILE_TOO_LARGE":
      return "This file exceeds the maximum upload size.";
    case "UNSUPPORTED_FILE_TYPE":
      return "This file type is not supported.";
    case "FILE_CORRUPTED":
      return "The file appears corrupted or empty.";
    case "EXCEL_PARSE_FAILED":
      return "We couldn't parse this spreadsheet. Check the file format and try again.";
    case "OCR_REQUIRED":
      return "This PDF needs OCR before it can be indexed.";
    case "PDF_PARSE_FAILED":
      return "We couldn't extract text from this PDF.";
    case "WORD_PARSE_FAILED":
      return "We couldn't parse this Word document.";
    case "PPT_PARSE_FAILED":
    case "POWERPOINT_PARSE_FAILED":
      return "We couldn't parse this PowerPoint file.";
    default: {
      const text = fallback || "";
      if (/anonymous/i.test(text) || /session (invalid|expired|has expired)/i.test(text)) {
        return "Your Confluence session has expired. Update the connection cookie/PAT, then sync again.";
      }
      if (/HTTP\s*404/i.test(text) || /not found or is not accessible/i.test(text)) {
        return "The Confluence space could not be found or you don't have access. Check the space key and connection.";
      }
      return text || "We couldn't complete the import.";
    }
  }
}

export function importTitle(
  sourceType?: string | null,
  jobType?: string | null,
): { title: string; subtitle: string } {
  const isSync = jobType === "SYNC";

  if (sourceType === "JIRA") {
    return isSync
      ? {
          title: "Syncing from Jira",
          subtitle: "Applying issue changes — only updated items are fetched.",
        }
      : {
          title: "Importing from Jira",
          subtitle: "Syncing issues, comments, and attachments into this Space.",
        };
  }

  if (sourceType === "FILE_EXCEL" || sourceType === "FILE_CSV") {
    return {
      title: isSync ? "Re-indexing spreadsheet" : "Indexing spreadsheet",
      subtitle: "Parsing sheets and preparing rows for search.",
    };
  }
  if (sourceType === "FILE_WORD") {
    return {
      title: isSync ? "Re-indexing Word document" : "Indexing Word document",
      subtitle: "Extracting text and structure from the document.",
    };
  }
  if (sourceType === "FILE_POWERPOINT") {
    return {
      title: isSync ? "Re-indexing PowerPoint" : "Indexing PowerPoint",
      subtitle: "Extracting slides and notes into this Space.",
    };
  }
  if (sourceType === "FILE_PDF") {
    return {
      title: isSync ? "Re-indexing PDF" : "Indexing PDF",
      subtitle: "Extracting text and preparing pages for search.",
    };
  }
  if (sourceType === "FILE_UPLOAD") {
    return { title: "Importing uploaded files", subtitle: "Processing files into this Space." };
  }

  if (isSync) {
    return {
      title: "Syncing from Confluence",
      subtitle: "Applying changes — only updated pages are fetched.",
    };
  }
  return {
    title: "Importing from Confluence",
    subtitle: "Syncing pages, attachments, and diagrams into this Space.",
  };
}
