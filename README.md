# Knowledge Library

SaaS knowledge library: connect Confluence / Jira and upload Excel, CSV, Word, PowerPoint, and PDF into Workspace/Space structure, preserve hierarchy where it applies, share with RBAC, and Ask AI with grounded citations (NotebookLM-like UX, not NotebookLM backend).

## Brand

Identity mascot: chibi ant (navy–blue–violet), **Q** backpack, magnifying glass — *Explore • Understand • Grow*.

Assets live under `apps/web/public/brand/`. UI should use `@/components/brand` (`BrandLogo`, `BrandMark`, `BrandMascot`, `BrandEmptyState`, `BrandLoading`) instead of ad-hoc logo imports.

Rasterize PNG/ICO/OG from SVG sources:

```bash
cd apps/web
npm run brand:rasterize
```

## Architecture

Modular monolith:

- **Web:** Next.js (TypeScript, Tailwind)
- **API:** FastAPI + SQLAlchemy 2 + Alembic
- **Worker:** Celery + Redis
- **Data:** PostgreSQL + pgvector, MinIO
- **Embeddings:** system-hosted service (stub locally; BGE-M3-compatible contract)
- **Auth:** Google OIDC only (HttpOnly session cookie + CSRF)
- **Private Confluence:** Local Connector Agent (Phase 5 foundation; fetch in Phase 6)

See `docs/architecture/system-architecture.md`, `docs/architecture/erd.md`, `docs/architecture/multi-source-ingestion.md`, and `docs/architecture/multi-source-api.md`.

## Prerequisites

- Docker + Docker Compose
- Google Cloud OAuth client (Web) for login
- Optional: Gemini API key per user (Phase 8)

## Local setup

1. Copy env and generate secrets:

```bash
cp .env.example .env
```

Set at least:

```text
SESSION_SECRET=<random >=32 chars>
APP_ENCRYPTION_KEY=<random >=32 chars>
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
APP_URL=http://localhost:3000
```

In Google Cloud Console, add authorized redirect URI matching `GOOGLE_REDIRECT_URI`.

2. Start stack:

```bash
docker compose up --build
```

Migrations run automatically on API start (`alembic upgrade head`).

3. Open:

- Web: http://localhost:3000
- API health: http://localhost:8000/health
- API docs: http://localhost:8000/docs
- MinIO console: http://localhost:9001 (minioadmin / minioadmin)

## Google OAuth

Scopes: `openid email profile` only.

Identity key in DB is `google_sub` (not email alone).

Suspended users are blocked on authenticated endpoints and redirected on callback.

## Tests

```bash
# API (requires Postgres + Redis reachable via DATABASE_URL / REDIS_URL)
cd apps/api
pip install -r requirements.txt
alembic upgrade head
pytest -q

# Web unit smoke
cd apps/web
npm install
npm test
```

Or via Compose after stack is up:

```bash
docker compose exec api pytest -q
docker compose exec web npm test
```

## Local development (no Docker)

Requires **Google OAuth** (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` in `apps/api/.env`) and a database (PostgreSQL recommended).

```powershell
.\start.cmd
```

Then open http://localhost:3000/login and sign in with Google.

- API: http://localhost:8000/health
- Docs: http://localhost:8000/docs

`.\start.cmd` preserves existing `apps/api/.env` values — it does not overwrite your secrets.

For API unit tests without Docker:

```bash
# API unit tests (DB-backed cases skip if Postgres is down)
cd apps/api
# with uv: uv venv && uv pip install -r requirements.txt
pytest -q
ruff check app tests

# Web
cd apps/web
npm install && npm test && npx tsc --noEmit
```

Full stack acceptance (`docker compose up --build`, migrations, `/ready`) requires Docker + Compose.

| Phase | Status |
|-------|--------|
| Architecture / ERD / ADRs | Done |
| Phase 0 Foundation | Done (Compose, health, migrations, CI) |
| Phase 1 Google Auth + User | Done (OIDC, session, `/me`, protected `/app`) |
| Phase 2 Workspace + RBAC + Theme | Done (workspaces, share, dashboard UI, Light/Dark/System) |
| Phase 3 Space Management + Share | Done (spaces, star/recent/trash, Spaces UI, isolated share) |
| Phase 4 Confluence Connection | Done (Direct connection, PAT + non-prod cookie, browse, attach Source; no ingest) |
| Phase 5 Connector Agent | Done (register/heartbeat/NOOP jobs; Confluence fetch = Phase 6) |
| Phase 6 Ingestion | Done (Direct+Agent import, attachments/images/draw.io, chunk/embed, Space UI) |
| Phase 7 Page Management | Done (lazy page tree, search, CRUD/move/archive, Confluence read-only, deep links) |
| Phase 8 Ask AI + Search | Done (FTS search, Ask AI + citations, Gemini, ⌘K) |
| Phase 9 Confluence Sync | Done (delta sync, schedule, sync status UI) |
| Phase 10 Super Admin | Done (overview, users, logs, AI usage) |

Track progress in `docs/implementation-plan.md`.

### Phase 2 highlights

- Create / rename / soft-delete Workspace (max **10 owned**; shared does not count)
- Multi-owner RBAC (`OWNER` / `EDITOR` / `VIEWER`) via `PermissionService`
- Workspace share links (hash-at-rest, redeem after login, revoke)
- Dashboard with real summary counts (Spaces/Sources/Docs/Conversations stay `0` until later phases)
- Theme preference `LIGHT` | `DARK` | `SYSTEM` stored in `user_settings`
- Web app shell: sidebar, header, workspaces/shared/settings pages

Design / plan notes:

- `docs/superpowers/specs/2026-08-26-phase2-workspace-rbac-theme-design.md`
- `docs/superpowers/plans/2026-08-26-phase2-workspace-rbac-theme.md`

## Security notes

- Never commit `.env` or real secrets.
- Gemini/Confluence credentials are encrypted server-side (later phases); never returned by API.
- Share tokens are hashed at rest; raw token shown only on create.
- See `docs/security-checklist.md`.

## Connector Agent

1. In Workspace Settings → **Local Connector Agents**, create a registration token (Owner).
2. Run the agent:

```bash
cd apps/connector-agent
set REGISTRATION_TOKEN=...   # Windows PowerShell: $env:REGISTRATION_TOKEN="..."
set SaaS_API_URL=http://localhost:8000
python -m agent.main
```

Or via Compose:

```bash
docker compose --profile agent up connector-agent
```

Agent stores `agent_id` / secret in `.agent_state.json` (gitignored). Supports heartbeat, NOOP/PING, and **FETCH_CONFLUENCE** (upload pages + attachments to SaaS). For LOCAL_AGENT credentials set `CONFLUENCE_USERNAME` + `CONFLUENCE_PAT` (or cookie secret).

## Ingestion (Phase 6)

1. Attach an ACTIVE Confluence connection as a Source on a Space.
2. Click **Import** on the Source.
3. Direct mode fetches from API; Local Agent mode leases `FETCH_CONFLUENCE`.
4. Pages, images, and draw.io files are stored; Space shows documents + draw.io viewer.

Local dev (`start.cmd`) may use local disk under `apps/api/data/object-store/` and an in-process runner (no Celery required). Run Alembic migrations after schema changes.

## Pages (Phase 7)

- Route: `/app/workspaces/:workspaceId/spaces/:spaceId/pages` and `.../pages/:pageId`
- Lazy-loaded page tree (`GET /spaces/{id}/pages/tree`), title search, breadcrumbs, star
- Local pages: create / rename / edit / move / duplicate / archive / restore / soft-delete
- Confluence clones: hierarchy from import ancestors, content **read-only**, Open in Confluence
- Existing imports from before hierarchy linking stay flat until you **re-import** the Source

Plan: `docs/superpowers/plans/2026-08-27-page-management.md`

## Ask AI + Search (Phase 8)

- Sidebar **Ask AI** → `/app/ask` (query: `workspaceId`, `spaceId`, `conversationId`)
- Two-column Library QA UI: space scope, conversation history, structured answers (summary / key changes / highlights / sources)
- Citations deep-link to the page viewer; clickable `[n]` badges validated against retrieved sources
- Settings → AI: connect your **Gemini API key** (encrypted). Ask AI requires a connected Gemini key — answers are generated by Google Gemini using retrieved library content.
- Rename / delete conversations; Stop / Copy / Regenerate on answers

Design / plan:

- `docs/superpowers/specs/2026-08-27-phase8-ask-ai-search-design.md`
- `docs/superpowers/plans/2026-08-27-phase8-ask-ai-search.md`
- `docs/superpowers/specs/2026-08-27-ask-ai-ui-redesign-design.md`
- `docs/superpowers/plans/2026-08-27-ask-ai-ui-redesign.md`

## Confluence Sync (Phase 9)

- After a Source is **READY**, use **Sync now** to fetch only changed pages (Confluence `version` vs stored `external_version`)
- Removed pages are soft-deleted; new/changed pages are upserted and re-indexed for Ask AI
- **Auto sync**: Off / Hourly / Daily per Source (scheduler runs in API process when enabled)
- Sync progress reuses the import monitor; summary shows +added / ~updated / -removed counts

Design / plan:

- `docs/superpowers/specs/2026-08-28-phase9-confluence-sync-design.md`
- `docs/superpowers/plans/2026-08-28-phase9-confluence-sync.md`

## Super Admin (Phase 10)

- Settings → **Admin** tab (only when `is_super_admin`)
- `/app/settings/admin` — platform counts (users, workspaces, documents, jobs, AI tokens)
- `/app/settings/admin/users` — search, suspend / activate users
- `/app/settings/admin/logs` — system audit log (no document bodies)
- `/app/settings/admin/usage` — AI token usage by user + workspace

Set `SEED_SUPER_ADMIN_EMAIL` in `apps/api/.env`; first Google login with that email becomes Super Admin.

Design: `docs/superpowers/specs/2026-08-28-phase10-super-admin-design.md`

## Production checklist (high level)

- Real `APP_ENCRYPTION_KEY` via KMS/envelope encryption
- `SESSION_COOKIE_SECURE=true`, HTTPS, CSRF
- Managed Postgres/Redis/S3
- SSRF allowlists / Local Agent for private Confluence
- Rate limits and observability
