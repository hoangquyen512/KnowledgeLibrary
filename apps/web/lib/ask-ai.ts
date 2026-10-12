export type AskCitation = {
  id: string;
  document_id: string;
  chunk_id: string;
  citation_index: number;
  snippet: string | null;
  title?: string | null;
  space_id?: string | null;
  section_heading?: string | null;
  source_url?: string | null;
};

export type NotebookLMSource = {
  id: number;
  page_title: string;
  section_heading?: string;
  source_url?: string | null;
  quoted_snippet?: string;
};

export type AskKeyChange = {
  title: string;
  description?: string;
  citation_indices: number[];
};

export type AskHighlight = {
  text: string;
  citation_indices: number[];
};

export type AskStructured = {
  format?: string;
  answer_type?: string;
  answer?: string;
  sources?: NotebookLMSource[];
  summary?: string[];
  key_changes?: AskKeyChange[];
  highlights?: AskHighlight[];
  compare?: Record<string, unknown> | null;
  caveat?: string | null;
  markdown?: string | null;
};

export type AskConversation = {
  id: string;
  workspace_id: string;
  title: string;
  status: string;
  space_ids: string[];
  created_at: string;
  updated_at: string;
};

export type AskMessage = {
  id: string;
  conversation_id: string;
  role: string;
  content: string;
  model_provider?: string | null;
  model_name?: string | null;
  created_at: string;
  citations: AskCitation[];
  structured?: AskStructured | null;
  retrieved_chunk_count?: number | null;
  unique_document_count?: number | null;
  space_ids?: string[];
};

export type AskStreamMeta = {
  mode?: string;
  provider?: string;
  user_message_id?: string;
  assistant_message_id?: string;
  retrieved_chunk_count?: number;
  unique_document_count?: number;
};

export type AskStreamResult = {
  citations: AskCitation[];
  mode: string;
  structured: AskStructured | null;
  meta: AskStreamMeta;
  text: string;
};

export function toPlainText(value: string | null | undefined): string {
  if (!value) return "";
  let text = String(value);
  text = text.replace(/```[\s\S]*?```/g, " ");
  text = text.replace(/`([^`]+)`/g, "$1");
  text = text.replace(/!\[([^\]]*)\]\([^)]+\)/g, "$1");
  text = text.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
  text = text.replace(/^\s{0,3}#{1,6}\s*/gm, "");
  text = text.replace(/(\*\*|__)(.*?)\1/g, "$2");
  text = text.replace(/(\*|_)(.*?)\1/g, "$2");
  text = text.replace(/<\/?[^>]+>/g, "");
  text = text.replace(/[ \t]+\n/g, "\n");
  text = text.replace(/\n{3,}/g, "\n\n");
  return text.trim();
}

export function citationPageHref(
  workspaceId: string,
  citation: AskCitation,
  fallbackSpaceId?: string | null,
): string | null {
  const spaceId = citation.space_id || fallbackSpaceId;
  if (!workspaceId || !spaceId || !citation.document_id) return null;
  return `/app/workspaces/${workspaceId}/spaces/${spaceId}/pages/${citation.document_id}`;
}

export function citationByIndex(citations: AskCitation[]): Map<number, AskCitation> {
  const map = new Map<number, AskCitation>();
  for (const c of citations) {
    if (!map.has(c.citation_index)) map.set(c.citation_index, c);
  }
  return map;
}

export function filterValidCitationIndices(
  indices: number[] | undefined,
  citations: AskCitation[],
): number[] {
  if (!indices?.length) return [];
  const valid = new Set(citations.map((c) => c.citation_index));
  const seen = new Set<number>();
  const out: number[] = [];
  for (const i of indices) {
    if (!valid.has(i) || seen.has(i)) continue;
    seen.add(i);
    out.push(i);
  }
  return out;
}

export function formatAnswerMeta(chunkCount?: number | null, docCount?: number | null): string | null {
  if (chunkCount == null || docCount == null) return null;
  const chunks = chunkCount === 1 ? "1 snippet" : `${chunkCount} snippets`;
  const docs = docCount === 1 ? "1 document" : `${docCount} documents`;
  return `Based on ${chunks} from ${docs}`;
}

export type ConversationGroup = {
  key: string;
  label: string;
  items: AskConversation[];
};

function startOfDay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

export function groupConversations(
  conversations: AskConversation[],
  now = new Date(),
): ConversationGroup[] {
  const today = startOfDay(now);
  const yesterday = today - 86_400_000;
  const weekAgo = today - 7 * 86_400_000;

  const buckets: Record<string, AskConversation[]> = {
    today: [],
    yesterday: [],
    week: [],
    older: [],
  };

  for (const c of conversations) {
    const t = startOfDay(new Date(c.updated_at || c.created_at));
    if (t >= today) buckets.today.push(c);
    else if (t >= yesterday) buckets.yesterday.push(c);
    else if (t >= weekAgo) buckets.week.push(c);
    else buckets.older.push(c);
  }

  const groups: ConversationGroup[] = [];
  if (buckets.today.length) groups.push({ key: "today", label: "Today", items: buckets.today });
  if (buckets.yesterday.length) {
    groups.push({ key: "yesterday", label: "Yesterday", items: buckets.yesterday });
  }
  if (buckets.week.length) {
    groups.push({ key: "week", label: "Previous 7 days", items: buckets.week });
  }
  if (buckets.older.length) groups.push({ key: "older", label: "Older", items: buckets.older });

  // Spec-friendly collapse: if only today + rest, label rest as Recent
  if (groups.length === 2 && groups[0].key === "today") {
    return [
      groups[0],
      {
        key: "recent",
        label: "Recent",
        items: [...buckets.yesterday, ...buckets.week, ...buckets.older],
      },
    ];
  }
  return groups;
}

export function formatConversationTime(iso: string, now = new Date()): string {
  const d = new Date(iso);
  const today = startOfDay(now);
  const t = startOfDay(d);
  if (t >= today) {
    return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString(undefined, { day: "2-digit", month: "2-digit" });
}

export function isNotebookLMAnswer(structured?: AskStructured | null): boolean {
  return Boolean(structured?.answer && (structured.format === "notebooklm" || structured.sources));
}

export function hasStructuredSections(structured?: AskStructured | null): boolean {
  if (isNotebookLMAnswer(structured)) return true;
  if (!structured) return false;
  return Boolean(
    (structured.summary && structured.summary.length) ||
      (structured.key_changes && structured.key_changes.length) ||
      (structured.highlights && structured.highlights.length) ||
      structured.markdown ||
      structured.answer_type === "NO_SOURCE",
  );
}

export async function postMessageSse(
  conversationId: string,
  content: string,
  options: {
    spaceIds?: string[];
    csrf?: string;
    signal?: AbortSignal;
    onToken?: (t: string) => void;
    onMeta?: (m: AskStreamMeta) => void;
    onStructured?: (s: AskStructured) => void;
  } = {},
): Promise<AskStreamResult> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (options.csrf) headers["X-CSRF-Token"] = options.csrf;

  const res = await fetch(`/api/v1/conversations/${conversationId}/messages`, {
    method: "POST",
    credentials: "include",
    headers,
    signal: options.signal,
    body: JSON.stringify({
      content,
      ...(options.spaceIds?.length ? { space_ids: options.spaceIds } : {}),
    }),
  });

  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => null);
    const err = new Error(
      body?.error?.message || body?.detail?.message || body?.detail?.code || "Ask failed",
    ) as Error & { status?: number; code?: string };
    err.status = res.status;
    err.code = body?.detail?.code || body?.error?.code;
    throw err;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let citations: AskCitation[] = [];
  let mode = "GEMINI";
  let event = "message";
  let structured: AskStructured | null = null;
  let meta: AskStreamMeta = {};
  let text = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n");
    buffer = parts.pop() || "";
    for (const line of parts) {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        const raw = line.slice(5).trim();
        if (!raw) continue;
        try {
          const data = JSON.parse(raw);
          if (event === "token" && data.text) {
            text += data.text;
            options.onToken?.(data.text);
          }
          if (event === "meta") {
            meta = data;
            if (data.mode) mode = data.mode;
            options.onMeta?.(data);
          }
          if (event === "structured" && data.structured) {
            structured = data.structured;
            options.onStructured?.(data.structured);
          }
          if (event === "citations" && Array.isArray(data.citations)) {
            citations = data.citations;
          }
        } catch {
          /* ignore partial */
        }
      }
    }
  }

  return { citations, mode, structured, meta, text };
}
