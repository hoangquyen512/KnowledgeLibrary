# AI Knowledge Library — Implementation Plan

> Source of truth: `MASTER_PROMPT_AI_KNOWLEDGE_LIBRARY_CURSOR.md`  
> Method: Architecture → ERD → Phase 0 → Phase N (migration + code + tests + README after each phase)

**Goal:** Build a runnable multi-tenant AI Knowledge Library SaaS (Confluence DC clone + NotebookLM-like Ask AI) as a modular monolith.

**Architecture:** Modular monolith (FastAPI) + Celery workers + Local Connector Agent + Next.js web. PostgreSQL+pgvector, Redis, MinIO.

**Tech Stack:** Next.js / TypeScript / Tailwind / shadcn · FastAPI / SQLAlchemy 2 / Alembic · PostgreSQL+pgvector · Redis+Celery · MinIO · Google OIDC · Gemini per-user · BGE-M3 embeddings

---

## Global Constraints

- Google login only; no anonymous access; no password auth.
- Workspace is tenant boundary; AI query never cross-Workspace.
- Backend is source of truth for RBAC; encrypt secrets at rest.
- No plaintext Confluence/Gemini credentials in logs or API responses.
- All schema via Alembic (no `create_all()` in production).
- UUID for PKs; soft-delete where appropriate; `workspace_id` on tenant data.

---

## Checklist

### Docs (before code)

- [x] `docs/implementation-plan.md` (this file)
- [x] `docs/architecture/system-architecture.md`
- [x] `docs/architecture/erd.md`
- [x] ADR files in `docs/adr/`
- [x] Sequence diagrams (Login, Share, Import Direct/Agent, Ask AI)
- [x] Security checklist

### Phase 0 — Foundation

- [x] Monorepo layout (`apps/web`, `apps/api`, `apps/connector-agent`, `packages/*`, `infra/`)
- [x] Docker Compose: web, api, worker, postgres(pgvector), redis, minio, embedding-service stub
- [x] FastAPI app + `/health` + `/ready`
- [x] Next.js app + basic shell
- [x] Alembic + initial migration (extensions + users foundation tables for Phase 1)
- [x] `.env.example`, README setup
- [x] Unit smoke tests + CI basic
- [x] **Gate:** unit/lint green locally; Compose boot requires Docker (see notes)

### Phase 1 — Google Auth + User

- [x] Google OIDC login/callback/logout
- [x] Secure HttpOnly session cookie + CSRF for mutations
- [x] User auto-provision on first login (`google_sub`)
- [x] `GET /me`, suspended user blocked
- [x] Frontend `/login`, protected `/app` routes
- [x] IDOR/auth tests (unauthenticated → 401, suspended → 403)
- [x] **Gate:** 10 passed / 4 skipped without Postgres; DB integration tests in CI / Compose

### Phase 2 — Workspace + RBAC + Dashboard + Theme

- [x] Workspaces, memberships, max 10 owned quota (transaction-safe)
- [x] PermissionService + multi-owner last-Owner guards
- [x] Workspace Share (create/redeem/revoke) + audit events
- [x] Dashboard aggregation (`GET /dashboard`) with real counts
- [x] Theme LIGHT/DARK/SYSTEM via `user_settings` + `/me/settings`
- [x] App shell Dashboard UI (sidebar/header/responsive)
- [x] Unit + integration tests (DB-backed skip without Postgres)
- [x] Playwright E2E critical scenarios (demo login + Google storage state option)

### Phase 3 — Space + Share

- [x] Spaces, space memberships, share links, redeem/revoke
- [x] Isolated Space visibility / Shared with me foundation
- [x] Starred / Recent / Trash
- [x] Spaces UI (list/grid, overview, activity, storage 0)
- [x] Security tests for share + enumeration (unit/integration; DB-backed skip without Postgres)

### Phase 4 — Confluence Connection

- [x] Direct Confluence connections (encrypted PAT; session cookie non-prod only)
- [x] SSRF guards + Test Connection
- [x] Browse Confluence spaces/pages (read-only)
- [x] Attach Source to Space (`READY_TO_IMPORT`, no ingest)
- [x] Workspace Settings → Connections UI
- [x] Full Add Source browse wizard polish / Playwright E2E (step wizard; E2E via demo login)

### Phase 5 — Local Connector Agent Foundation

- [x] Registration tokens + agent register (hashed secrets)
- [x] Heartbeat + ONLINE/OFFLINE
- [x] Job lease next/complete (NOOP/PING only)
- [x] Connection modes DIRECT | LOCAL_AGENT + credential CLOUD | LOCAL_AGENT
- [x] Workspace Settings → Agents UI + agent binary
- [x] Agent-mediated Confluence fetch (Phase 6)

### Phase 6 — Confluence Ingestion

- [x] Import job pipeline (SCAN→FETCH→STORE→NORMALIZE→CHUNK→EMBED)
- [x] Direct + Local Agent (`FETCH_CONFLUENCE` + ingestion payload)
- [x] Pages + attachments (images + draw.io raw) to object store (MinIO / local demo)
- [x] Rewrite inline image URLs; draw.io viewer in Space UI
- [x] Demo `start.cmd` E2E via adapters (inline runner + local disk)
- [x] Import Monitoring UI (3-panel progress, stages, cancel, SSE/poll)
- [x] Hybrid search / Ask AI (Phase 8+)
- [x] Page management in Space (Phase 7: tree, search, CRUD, Confluence read-only)

### Phase 7 Page Management

- [x] Lazy page tree + search APIs on `documents` (`document_type=PAGE`)
- [x] Hierarchy from Confluence ancestors on import
- [x] UI: `/app/workspaces/:id/spaces/:spaceId/pages[/:pageId]`
- [x] Local edit; Confluence pages read-only + Open in Confluence
- [x] Attachments panel + page details drawer on viewer

### Phase 8 — Hybrid Search + Ask AI

- [x] Per-user Gemini credential (encrypted) + Mock provider for demo
- [x] Hybrid search FTS on chunks/titles (workspace + space scope)
- [x] Conversations + messages + citations
- [x] UI: Settings → AI, `/app/ask`, ⌘K search, Space Ask link
- [x] Vector/RRF fusion when embeddings are non-zero (bonus)
- [x] Playwright E2E Ask AI (demo login smoke)

### Phase 9–11

- [x] Phase 9 Confluence delta sync (manual + scheduled, sync status UI)
- [x] Phase 10 Super Admin (platform overview, users, audit logs, AI usage)

---

## Phase status

| Phase | Status | Notes |
|-------|--------|-------|
| Docs / Architecture / ERD | Done | ADRs + sequences + security checklist |
| Phase 0 | Done | Compose files ready; local unit/lint verified without Docker |
| Phase 1 | Done | OIDC/session/me/protected UI; DB-backed tests skip without Postgres |
| Phase 2 | Done | Workspace/RBAC/Share/Theme/Dashboard UI |
| Phase 3 | Done (E2E CI pending) | Space CRUD/share/star/recent + Spaces UI |
| Phase 4 | Done (E2E / real Confluence test pending your URL) | Connection + browse + Source attach |
| Phase 5 | Done (foundation) | Register/heartbeat/NOOP; fetch = Phase 6 |
| Phase 6 | Done (MVP) | Import Direct+Agent; attachments/draw.io; demo E2E |
| Phase 7 | Done (MVP) | Page tree/search/CRUD; Confluence read-only; deep links |
| Phase 8 | Done (MVP) | Search + Ask AI + citations; Mock Gemini demo |
| Phase 9 | Done (MVP) | Delta sync + schedule + sync status UI |
| Phase 10 | Done (MVP) | Super Admin console (metadata only) |

---

## How to verify after each phase

```bash
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api pytest -q
# optional: web lint
docker compose exec web npm test --if-present
curl -f http://localhost:8000/health
```
