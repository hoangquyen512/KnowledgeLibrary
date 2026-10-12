# Ask AI UI Redesign — Design

**Date:** 2026-08-27  
**Status:** Approved (Approach 2 — full-stack structured response)  
**Visual reference:** Ask AI mockup (two-column Library QA)

## Decisions (locked)

| Topic | Choice |
|---|---|
| Approach | Structured JSON from LLM + FE section cards; markdown fallback |
| UI language | English core labels; answer content may be Vietnamese |
| Routing | Keep `/app/ask`; deep-link via `?workspaceId=&spaceId=&conversationId=` |
| MVP extras | Stop (abort SSE display), Copy, Regenerate, Rename/Delete conversation |
| Out of MVP | Source side drawer, search-in-conversation, full i18n framework, nested workspace routes |
| Unchanged | RAG retrieval, permission checks, Gemini key storage |

## Goals

Transform Ask AI from a plaintext chatbot into a knowledge-analysis tool:

1. Clear workspace + space scope
2. Structured answer: Quick summary → Key changes → Highlights → Sources
3. Clickable citations → correct Page
4. Conversation history, sticky composer, empty/error/loading, light/dark

## Architecture

```
User → AskAI page (components/ask-ai/*)
     → POST /conversations/:id/messages (SSE)
     → AskService.ask → RetrievalService → LlmProvider.generate (JSON)
     → validate citations ⊆ retrieved hits
     → persist Message.metadata_json.structured + counts
     → SSE: meta → token(s) → structured → citations → done
```

### Structured answer schema

```json
{
  "answer_type": "SUMMARY|LIST|COMPARE|ANALYSIS|GENERAL|NO_SOURCE",
  "summary": ["short bullet", "..."],
  "key_changes": [
    { "title": "...", "description": "...", "citation_indices": [1] }
  ],
  "highlights": [
    { "text": "...", "citation_indices": [1] }
  ],
  "compare": null,
  "caveat": null,
  "markdown": "optional prose fallback"
}
```

- Providers (Mock + Gemini) produce this JSON.
- `content` on Message stores a readable markdown/plaintext fallback for legacy clients.
- Invalid/missing structure → FE renders `content` as markdown-ish text.
- Citation indices must exist in retrieved sources; FE only renders validated citations from API.

### Message / SSE meta

Backend returns (and stores):

- `retrieved_chunk_count`
- `unique_document_count`
- `structured` (nullable)
- `space_ids` snapshot on USER messages
- `mode` — FE shows “Library QA”; `DEV MOCK` badge only when `NODE_ENV !== 'production'`

### API additions

- `PATCH /conversations/{id}` — rename title
- `DELETE /conversations/{id}` — soft-archive (`status=ARCHIVED`)
- `MessageOut` extended with `structured`, `retrieved_chunk_count`, `unique_document_count`, `space_ids`

### Frontend structure

Route stays `apps/web/app/app/ask/page.tsx` (thin shell). Components under `apps/web/components/ask-ai/`:

- Sidebar: `AskAISidebar`, `WorkspaceSelector`, `SpaceScopeSelector`, `ConversationList`, `NewChatButton`, mode card
- Main: `AskAIHeader`, `SuggestedQuestions`, `UserQuestionBubble`, `AIResponseCard` (+ sections), `ChatComposer`
- States: `AskAIEmptyState`, `AskAIErrorState`, `StreamingIndicator`

Citation click → `/app/workspaces/{ws}/spaces/{space}/pages/{documentId}` (existing permissioned page route).

## Error / empty mapping

| Condition | UI |
|---|---|
| No space selected | Banner + composer disabled |
| No Gemini (prod preference) | Keep Mock in non-prod; show Connect CTA when disconnected *and* mock disabled — otherwise Library QA |
| Empty retrieval | `answer_type=NO_SOURCE` structured empty state |
| Quota / Gemini 429 | Friendly card → AI Settings |
| Weak evidence | `caveat` + partial structured answer |

## Non-goals

- Change RBAC / citation URL bypass
- Source preview drawer
- Virtualized chat history (unless list > 50 becomes slow)
- Changing app shell navigation IA beyond Ask AI page

## Acceptance

Matches visual reference layout; structured sections when backend provides them; citations open correct pages; no production MOCK badge; critical unit tests pass.
