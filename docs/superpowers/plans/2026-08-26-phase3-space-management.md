# Phase 3 Space Management Implementation Plan

> Inline execution in this session.

**Goal:** Deliver Space CRUD, RBAC, share, starred/recent/trash, and Spaces UI matching Knowledge Library mockup with real data only.

**Architecture:** Extend PermissionService for effective Space roles → SpaceService/Share → APIs → Next.js Spaces page + panels.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic `0003_phase3_spaces`, TanStack Query, Lucide, existing theme tokens.

## Tasks

### Task 1: Models + migration
- [x] spaces, space_memberships, user_starred_spaces, user_recent_spaces
- [x] share_links already supports SPACE target

### Task 2: Permission + Space services + APIs
- [x] effective role, isolated share visibility
- [x] CRUD, archive/restore, star/recent, share redeem SPACE

### Task 3: Tests
- [x] unit + integration (DB-backed skip without Postgres)

### Task 4: Frontend Spaces UI
- [x] list/tabs/filters/list-grid, dialogs, overview panels
- [x] routes: spaces, detail, settings, access, recent, starred, trash
- [x] sidebar workspace selector + Create Space

### Task 5: Docs
- [x] README + implementation-plan

**Status:** Phase 3 complete for DoD (E2E Playwright CI still pending Postgres environment).