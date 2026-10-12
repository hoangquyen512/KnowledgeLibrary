# Page Management (Space) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Confluence-like Page tree + reader + local CRUD inside a Space, reusing `documents` as PAGE.

**Architecture:** Extend `documents` with hierarchy fields (`position`, `depth`, lifecycle, origin); set `parent_id` from Confluence ancestors on import; PageService + tree/search APIs; Space Pages UI (sidebar tree + content). Confluence clones are read-only for content.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Next.js App Router, TanStack Query, Tailwind (existing KL design).

## Global Constraints

- Brand: Knowledge Library; reuse app shell; RBAC via PermissionService
- No fake data; no Confluence write-back; soft delete
- Page UUID is identity; lazy-load tree children
- Light / Dark / System

---

## File map

| Area | Files |
|------|--------|
| Model/migration | `models/document.py`, `alembic/versions/0008_phase7_pages.py`, `demo_schema.py` |
| Ingest hierarchy | `ingestion/service.py`, `confluence/client.py` (agent ancestors later) |
| Page domain | `pages/service.py`, `schemas/page.py`, `api/pages.py` |
| Web | `app/.../pages/page.tsx`, `pages/[pageId]/page.tsx`, `components/pages/*` |

---

## Tasks

### Task 1: Schema
- [ ] Add `position`, `depth`, `origin`, `archived_at`, `deleted_at`; nullable `source_id`
- [ ] `user_starred_pages`, `user_recent_pages`
- [ ] Demo SQLite ALTER patches
- [ ] Unit: model imports

### Task 2: Import hierarchy
- [ ] After store batch, map `ancestors[-1].id` → `parent_id`, set `position`/`depth`/`origin=CONFLUENCE`
- [ ] Test with mocked pages+ancestors

### Task 3: PageService + API
- [ ] Tree (lazy), search, get, create, patch, move, duplicate, archive, restore, soft delete, star, children, ancestors
- [ ] Effective permissions + Confluence read-only content
- [ ] Integration tests security

### Task 4: Pages UI
- [ ] Routes `/spaces/:id/pages` and `/pages/:pageId`
- [ ] SpaceSidebar + PageTree + PageContent + Create/Move/Archive dialogs
- [ ] Deep-link expand ancestors; search debounce

### Task 5: Polish
- [ ] Attachments section, Open in Confluence, Details drawer MVP
- [ ] Responsive drawer tree; dark mode
- [ ] README / implementation-plan note

**MVP cut for first ship:** Tasks 1–4 core (tree view, open page, create/rename/archive local, Confluence read-only). Drag-drop, full editor, version history = follow-up.
