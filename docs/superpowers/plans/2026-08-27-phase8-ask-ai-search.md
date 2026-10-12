# Phase 8 Ask AI + Hybrid Search Implementation Plan

> **For agentic workers:** Implement task-by-task. Steps use checkbox syntax.

**Goal:** Ship workspace/space hybrid search and Ask AI with citations; demo uses Mock Gemini + FTS; prod uses per-user Gemini.

**Architecture:** RetrievalService → LlmProvider (Mock|Gemini) → citation validator → SSE. UI: AI settings, `/app/ask`, ⌘K, Space Ask.

**Tech Stack:** FastAPI, SQLAlchemy, Next.js, React Query, Fernet encryption, httpx (Gemini).

## Global Constraints

- Workspace tenant boundary; space RBAC on every query
- Never return/log plaintext Gemini keys
- Citations ⊆ retrieved chunks only
- Demo runs without Gemini key

## Tasks

- [x] Design doc
- [ ] Migration 0009 + models
- [ ] Retrieval + citation + Mock/Gemini
- [ ] API routes
- [ ] Web UI
- [ ] Tests + README / implementation-plan
