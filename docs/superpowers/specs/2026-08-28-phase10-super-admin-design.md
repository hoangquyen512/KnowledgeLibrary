# Phase 10 — Super Admin (Design)

**Status:** Approved (MVP)  
**Date:** 2026-08-28

## Goals

Platform operators (`is_super_admin`) can manage users and view system metadata **without** browsing document content.

## Scope (MVP)

1. **Overview** — aggregate counts: users, workspaces, spaces, sources, documents, running jobs, AI token usage.
2. **User management** — list/search users; suspend / activate (not self, not other super admins).
3. **System logs** — read-only `audit_logs` with actor email.
4. **AI usage** — aggregated `ai_usage` by user + workspace (tokens only).

## API (`/api/v1/admin/*`)

All routes require `require_super_admin`.

| Method | Path | Notes |
|--------|------|-------|
| GET | `/overview` | Platform stats |
| GET | `/users` | `?q=&limit=&offset=` |
| PATCH | `/users/{id}/status` | `{status: ACTIVE\|SUSPENDED}` + CSRF |
| GET | `/audit-logs` | `?action=&limit=&offset=` |
| GET | `/usage` | AI usage aggregates |

## UI

- `/app/admin` — overview
- `/app/admin/users` — suspend/activate
- `/app/admin/logs` — audit table
- `/app/admin/usage` — token usage

Sidebar Admin section links when `me.is_super_admin`.

## Security

- No document/page/content endpoints in admin module.
- Suspend writes `SUSPEND_USER` / `UNSUSPEND_USER` audit events.
- Super admin seeded via `SEED_SUPER_ADMIN_EMAIL` on first Google login.

## Non-goals

- Billing ledger / invoices
- Impersonation
- Workspace-level admin console
