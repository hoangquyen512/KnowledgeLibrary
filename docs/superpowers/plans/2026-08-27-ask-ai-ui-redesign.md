# Ask AI UI Redesign Implementation Plan

> **For agentic workers:** Execute task-by-task. Steps use checkbox syntax.

**Goal:** Redesign Ask AI into a two-column knowledge-analysis UI with structured answers, citations, and conversation management — without changing RAG permissions or Gemini credential storage.

**Architecture:** LLM returns structured JSON; AskService stores it in `metadata_json`; SSE exposes meta + structured + citations; FE renders section cards with markdown fallback. Route remains `/app/ask` with `conversationId` query.

**Tech Stack:** FastAPI, SQLAlchemy, Next.js 15, TanStack Query, Tailwind, lucide-react

## Global Constraints

- English UI labels; answer body may be Vietnamese
- No production `Mode: MOCK` badge (`DEV MOCK` only in non-production)
- Do not weaken permission checks on citation open
- Do not add source side drawer in this plan
- Keep `/app/ask` route; use query params for deep links

---

### Task 1: Structured LLM schema + providers

**Files:**
- Modify: `apps/api/app/rag/providers.py`
- Test: `apps/api/tests/test_ask_unit.py` (extend) or `apps/api/tests/test_ask_structured_unit.py`

**Produces:** `LlmResult.structured`, `parse_structured_answer()`, Mock/Gemini JSON prompts

- [ ] Add dataclass fields / parse helpers for structured answer
- [ ] MockGemini returns structured summary/key_changes/highlights (no “(Demo answer)” in structured fields; optional `markdown` may omit demo label for cleaner UI)
- [ ] Gemini prompt requests JSON-only schema; parse + validate citation indices
- [ ] Unit tests: parse valid JSON, strip invalid citations, no-source shape

---

### Task 2: AskService + MessageOut + SSE

**Files:**
- Modify: `apps/api/app/ask/service.py`
- Modify: `apps/api/app/schemas/ask.py`
- Modify: `apps/api/app/api/ask.py`

**Produces:** Persist structured + counts; SSE `meta` includes counts; `MessageOut.structured`

- [ ] Store user `space_ids` in user message `metadata_json`
- [ ] Store assistant `structured`, `retrieved_chunk_count`, `unique_document_count`
- [ ] Extend `MessageOut` / list_messages mapping
- [ ] SSE: meta → tokens (from fallback text) → structured → citations → done

---

### Task 3: Rename / Delete conversation APIs

**Files:**
- Modify: `apps/api/app/ask/service.py`
- Modify: `apps/api/app/api/ask.py`
- Modify: `apps/api/app/schemas/ask.py`

- [ ] `PATCH /conversations/{id}` body `{ title }`
- [ ] `DELETE /conversations/{id}` soft-archive
- [ ] Unit/service tests for ownership checks

---

### Task 4: FE strings + types + SSE client

**Files:**
- Create: `apps/web/lib/ask-ai.ts` (types, SSE helper, citation href, grouping)
- Create: `apps/web/components/ask-ai/strings.ts`

---

### Task 5: Sidebar components

**Files:**
- Create under `apps/web/components/ask-ai/`: `AskAISidebar.tsx`, `WorkspaceSelector.tsx`, `SpaceScopeSelector.tsx`, `ConversationList.tsx`, `NewChatButton.tsx`

---

### Task 6: Answer + composer components

**Files:**
- Create: `AIResponseCard.tsx`, section components, `CitationBadge.tsx`, `SourceReferences.tsx`, `UserQuestionBubble.tsx`, `ChatComposer.tsx`, `AskAIHeader.tsx`, `SuggestedQuestions.tsx`, empty/error/streaming states

---

### Task 7: Wire `/app/ask` page

**Files:**
- Modify: `apps/web/app/app/ask/page.tsx`
- Modify links that open Ask AI if needed (`app-shell`, `SpacePagesShell`) to pass `conversationId` when relevant

---

### Task 8: Tests + docs

- [ ] API unit tests for structured parse + rename/delete
- [ ] FE unit test for citation mapping / meta display (`lib/ask-ai` helpers via node:test)
- [ ] Update README Ask AI section briefly
