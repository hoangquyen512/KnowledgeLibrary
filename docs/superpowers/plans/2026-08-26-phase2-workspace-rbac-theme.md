# Phase 2 Workspace + RBAC + Theme Implementation Plan

> **For agentic workers:** Use inline execution in this session. Checkbox tasks track progress.

**Goal:** Deliver Workspace management, RBAC, Workspace share, Dashboard UI, and Light/Dark/System theme with server persistence.

**Architecture:** Vertical slices — Alembic models → Permission/Workspace/Share/Dashboard/Settings services → FastAPI routers → Next.js app shell + pages → tests.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Next.js 15, Tailwind semantic tokens, next-themes, TanStack Query, Lucide, Playwright (critical E2E).

## Global Constraints

- Max 10 owned workspaces by `created_by_user_id` (non-deleted)
- Shared memberships do not count toward quota
- Theme: `LIGHT` | `DARK` | `SYSTEM`; server is source of truth
- Backend RBAC is authoritative; no fake production dashboard data
- Soft-delete workspaces; never leave workspace without an Owner
- Preserve Phase 1 Google/demo auth

## File map

**API create:** `models/workspace.py`, `models/share.py`, `models/audit.py`, `permissions/service.py`, `workspaces/*`, `share/*`, `dashboard/*`, `settings/*`, `alembic/versions/0002_phase2_workspace.py`, tests

**Web create:** `components/layout/*`, `components/dashboard/*`, `components/workspace/*`, `components/theme/*`, `lib/query*`, `app/app/layout.tsx`, pages under `/app/*`, `/share/[token]`

## Tasks

### Task 1: Models + migration + theme normalize
- [ ] Models + Alembic `0002`
- [ ] UserSettings default `SYSTEM`; data migrate lowercase → uppercase
- [ ] Unit tests for theme enum + workspace model constraints

### Task 2: Permission + Workspace services
- [ ] Failing tests: quota, creator Owner, last Owner
- [ ] Implement PermissionService + WorkspaceService
- [ ] CRUD API routers

### Task 3: Settings + Dashboard + Audit
- [ ] GET/PATCH `/me/settings`
- [ ] GET `/dashboard`, `/activity`, `/shared`
- [ ] Tests for theme update + summary counts

### Task 4: Workspace Share
- [ ] ShareService create/redeem/revoke
- [ ] Login `next` redirect preserve
- [ ] Integration tests share + viewer cannot edit

### Task 5: Frontend theme + shell
- [ ] Design tokens, ThemeProvider, appearance settings
- [ ] AppSidebar, AppHeader, UserMenu, responsive drawer

### Task 6: Dashboard + workspace pages
- [ ] Dashboard real data + empty states + skeletons
- [ ] Workspaces list/detail/settings, Create/Delete/Share dialogs

### Task 7: Verify + docs
- [ ] API pytest, web smoke, Playwright critical
- [ ] Update README + implementation-plan Phase 2
