# Pages Source Filter Implementation Plan

> **For agentic workers:** Implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Scope Space → Pages to one selected source (persisted per space), with server-side filtering on tree/search/archived and create attaching to that source.

**Architecture:** Add optional `source_id` to page list APIs and create body; Pages shell loads sources, remembers selection in localStorage, passes `sourceId` into tree/search/archived/create.

**Tech Stack:** FastAPI + SQLAlchemy (API), Next.js React Query (web)

## Global Constraints

- Always exactly one selected source (no “All”).
- Remember via `kl-page-source:{spaceId}`.
- Deep link to a page switches selector to that page’s `source_id`.

---

### Task 1: API — filter + create source_id — DONE

### Task 2: Web — selector + wire consumers — DONE

### Task 3: Verify — DONE (`test_pages_unit.py` 10 passed)
