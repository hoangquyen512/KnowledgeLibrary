# Phase 8 — Hybrid Search + Ask AI (Design)

**Date:** 2026-08-27  
**Status:** Implementing (Approach 1 — vertical slice)

## Decisions

- Shared pipeline: `RetrievalService` (FTS/ILIKE + optional vector) → `LlmProvider` (`MockGemini` | `Gemini`) → citation validate → SSE
- Demo: auto Mock when no Gemini key (or `AI_PROVIDER=mock`); answers grounded in top chunks
- Prod: per-user encrypted Gemini key; invalid → status INVALID
- UI: Settings → AI · `/app/ask` (workspace, multi-space) · ⌘K hybrid search · Space Ask panel
- Citations must ⊆ retrieved chunk IDs; click → page viewer deep link
- SQLite/demo: no pgvector required; FTS via `LIKE` on chunks + titles

## Out of scope

Confluence sync/delta, Super Admin, billing, multi-model picker, answer editing.
