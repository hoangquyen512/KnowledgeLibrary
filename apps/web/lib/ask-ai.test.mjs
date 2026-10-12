import assert from "node:assert/strict";
import test from "node:test";

/** Mirrors apps/web/lib/ask-ai.ts pure helpers for CI without a TS loader. */

function citationPageHref(workspaceId, citation, fallbackSpaceId) {
  const spaceId = citation.space_id || fallbackSpaceId;
  if (!workspaceId || !spaceId || !citation.document_id) return null;
  return `/app/workspaces/${workspaceId}/spaces/${spaceId}/pages/${citation.document_id}`;
}

function filterValidCitationIndices(indices, citations) {
  if (!indices?.length) return [];
  const valid = new Set(citations.map((c) => c.citation_index));
  const seen = new Set();
  const out = [];
  for (const i of indices) {
    if (!valid.has(i) || seen.has(i)) continue;
    seen.add(i);
    out.push(i);
  }
  return out;
}

function formatAnswerMeta(chunkCount, docCount) {
  if (chunkCount == null || docCount == null) return null;
  const chunks = chunkCount === 1 ? "1 snippet" : `${chunkCount} snippets`;
  const docs = docCount === 1 ? "1 document" : `${docCount} documents`;
  return `Based on ${chunks} from ${docs}`;
}

function hasStructuredSections(structured) {
  if (!structured) return false;
  return Boolean(
    (structured.summary && structured.summary.length) ||
      (structured.key_changes && structured.key_changes.length) ||
      (structured.highlights && structured.highlights.length) ||
      structured.markdown ||
      structured.answer_type === "NO_SOURCE",
  );
}

function startOfDay(d) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

function groupConversations(conversations, now = new Date()) {
  const today = startOfDay(now);
  const yesterday = today - 86_400_000;
  const weekAgo = today - 7 * 86_400_000;
  const buckets = { today: [], yesterday: [], week: [], older: [] };
  for (const c of conversations) {
    const t = startOfDay(new Date(c.updated_at || c.created_at));
    if (t >= today) buckets.today.push(c);
    else if (t >= yesterday) buckets.yesterday.push(c);
    else if (t >= weekAgo) buckets.week.push(c);
    else buckets.older.push(c);
  }
  const groups = [];
  if (buckets.today.length) groups.push({ key: "today", label: "Today", items: buckets.today });
  if (buckets.yesterday.length) {
    groups.push({ key: "yesterday", label: "Yesterday", items: buckets.yesterday });
  }
  if (buckets.week.length) groups.push({ key: "week", label: "Previous 7 days", items: buckets.week });
  if (buckets.older.length) groups.push({ key: "older", label: "Older", items: buckets.older });
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

test("citationPageHref builds deep link", () => {
  assert.equal(
    citationPageHref("ws1", {
      document_id: "d1",
      space_id: "sp1",
    }),
    "/app/workspaces/ws1/spaces/sp1/pages/d1",
  );
});

test("filterValidCitationIndices drops unknown indices", () => {
  const citations = [{ citation_index: 1 }, { citation_index: 2 }];
  assert.deepEqual(filterValidCitationIndices([1, 2, 2, 99], citations), [1, 2]);
});

test("formatAnswerMeta uses backend counts", () => {
  assert.equal(formatAnswerMeta(8, 5), "Based on 8 snippets from 5 documents");
  assert.equal(formatAnswerMeta(null, 5), null);
});

test("hasStructuredSections detects summary and NO_SOURCE", () => {
  assert.equal(hasStructuredSections(null), false);
  assert.equal(hasStructuredSections({ summary: ["a"] }), true);
  assert.equal(hasStructuredSections({ answer_type: "NO_SOURCE" }), true);
});

test("groupConversations collapses to Today/Recent", () => {
  const now = new Date("2026-08-27T12:00:00");
  const groups = groupConversations(
    [
      {
        id: "1",
        title: "Today chat",
        created_at: "2026-08-27T09:00:00",
        updated_at: "2026-08-27T09:00:00",
      },
      {
        id: "2",
        title: "Old chat",
        created_at: "2026-08-20T09:00:00",
        updated_at: "2026-08-20T09:00:00",
      },
    ],
    now,
  );
  assert.equal(groups[0].label, "Today");
  assert.equal(groups[1].label, "Recent");
});

function toPlainText(value) {
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
  return text.trim();
}

test("toPlainText strips markdown markers", () => {
  assert.equal(toPlainText("### Heading\n**bold** and `code`"), "Heading\nbold and code");
  assert.equal(toPlainText("`GetSalesPriceList`"), "GetSalesPriceList");
});
