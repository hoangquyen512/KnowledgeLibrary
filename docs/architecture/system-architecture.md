# System Architecture — AI Knowledge Library

## 1. Goals

- Multi-tenant SaaS knowledge library with Workspace as tenant boundary.
- Clone/structure Confluence Data Center content into App Spaces while preserving page hierarchy.
- NotebookLM-like Ask AI over selected Spaces with grounded citations.
- Support private/intranet Confluence via Local Connector Agent (outbound-only).
- Per-user Gemini credentials for LLM generation; system-hosted embeddings for indexing.

## 2. Constraints

- Google OIDC only; no anonymous content access.
- AI retrieval/generation never crosses Workspace.
- Backend enforces all authorization; frontend only hides UI.
- Secrets encrypted at rest; never returned by API or logged.
- Modular monolith (not premature microservices).
- SSRF protection for Confluence URLs in Direct mode; prefer Local Agent for private networks.

## 3. Context diagram

```text
Google Identity ──► Users
Users ──► Web (Next.js) ──► API (FastAPI)
API ──► PostgreSQL+pgvector / Redis / MinIO / Workers
API ◄── Local Connector Agent (company network) ──► Confluence DC
API ──► Jira DC (PAT / Bearer, encrypted credentials)
API ──► MinIO (uploaded Excel/CSV/Word/PPT/PDF originals)
API ──► Gemini (per-user key) for generation
Workers ──► Embedding service (system-hosted) for index
```

Parsers are registered per `SourceType` (`FILE_EXCEL`, `FILE_CSV`, `FILE_WORD`, `FILE_POWERPOINT`, `FILE_PDF`, plus Confluence/Jira normalizers). See [multi-source-ingestion.md](./multi-source-ingestion.md).

## 4. Component diagram

```text
┌─────────────────────────────────────────────────────────────┐
│ SaaS Cloud                                                  │
│  Next.js Web  →  FastAPI Modular Monolith                   │
│    auth | users | workspaces | spaces | sharing             │
│    connectors | sources | documents | ingestion             │
│    retrieval | ai | conversations | admin                   │
│         │                                                   │
│         ├── PostgreSQL + pgvector (data + vectors + FTS)    │
│         ├── Redis (broker, rate limit, job progress)        │
│         ├── MinIO/S3 (raw + attachments)                    │
│         ├── Celery workers (scan/fetch/normalize/embed)     │
│         └── Embedding service (BGE-M3 or adapter)           │
│  Connector Gateway ◄── outbound TLS ── Local Agent          │
└─────────────────────────────────────────────────────────────┘
```

## 5. Deployment (local)

Docker Compose services:

| Service | Role |
|---------|------|
| `web` | Next.js frontend |
| `api` | FastAPI HTTP + SSE |
| `worker` | Celery workers |
| `postgres` | PostgreSQL 16 + pgvector |
| `redis` | Broker / cache / rate limit |
| `minio` | S3-compatible object storage |
| `embedding-service` | Embedding HTTP stub/service |
| `connector-agent` | Optional demo agent |

Production: CDN/WAF → LB → Web + API; managed Postgres/Redis/S3; worker pool; KMS for envelope encryption; agents outbound-only from customer networks.

## 6. Authentication

1. User hits `/login` → redirect to Google OIDC (`openid email profile`).
2. Callback validates `state`/`nonce`, upserts User by `google_sub`.
3. Server creates session; sets HttpOnly Secure SameSite cookie.
4. Mutations require CSRF token.
5. Suspended users rejected on session load and protected endpoints.
6. Share links require Google login before redeem.

## 7. RBAC

Roles: `OWNER` | `EDITOR` | `VIEWER` at Workspace and Space.

Effective Space role = strongest(workspace_role, space_role) when both exist.

If user has only Space membership:

- Access that Space resources only.
- No Workspace list/tree/settings.
- Appear under “Shared with me”.

Super Admin: system metadata/ops only; **no** implicit document browse.

PermissionService is the single authorization authority used by all services.

## 8. Data flow — Confluence ingestion

```text
Create Source → Job QUEUED
  → SCAN / DISCOVER hierarchy
  → FETCH pages + attachments (Direct or via Agent)
  → STORE raw (MinIO) + NORMALIZE
  → CHUNK → EMBED → INDEX FTS + pgvector
  → COMPLETE / COMPLETED_WITH_ERRORS / FAILED
```

Progress via Redis + SSE (`GET /jobs/{id}/events`).

## 9. RAG / Ask AI

```text
Auth → Workspace boundary → Space permission
  → Hybrid retrieval (FTS + vector) with tenant filters
  → RRF fusion → rerank → context budget
  → Gemini (user key) with citation-grounded prompt
  → Validate citation IDs against retrieved chunks
  → Persist message + citations → stream to client
```

## 10. Gemini

- Stored encrypted per user; API returns mask + status only.
- Onboarding when Ask AI without credential.
- Invalid key → status INVALID, force reconnect.
- Usage recorded in `ai_usage` (observability, not billing ledger).

## 11. Connector Agent

- Register with one-time token → agent_id + secret.
- Heartbeat; pull jobs; fetch Confluence internally; upload encrypted payload.
- Credential location: `CLOUD` or `LOCAL_AGENT`.
- Docker image; versioned; restart/resume aware.

## 12. Security highlights

- Tenant isolation helpers: `require_workspace_access`, `require_space_access`.
- IDOR tests mandatory (cross-workspace, isolated space, conversations, revoked share).
- Envelope encryption for secrets (dev: env master key; prod: KMS).
- SSRF blocks for Direct mode (private/metadata IPs unless enterprise allowlist).
- Sanitize Confluence HTML; never render scripts/handlers.
- Redis rate limits on login, redeem, analyze, chat, search, admin.
- Structured logs with `request_id`; never log secrets or raw docs by default.

## 13. Scale strategy

MVP: single Postgres+pgvector, worker pool, local embedding.  
Later: chunk partition by workspace, dedicated vector DB, more workers, K8s — without splitting into many microservices prematurely.

## 14. Related docs

- ERD: `docs/architecture/erd.md`
- ADRs: `docs/adr/`
- Sequences: `docs/architecture/sequences.md`
- Security checklist: `docs/security-checklist.md`
- Implementation plan: `docs/implementation-plan.md`
