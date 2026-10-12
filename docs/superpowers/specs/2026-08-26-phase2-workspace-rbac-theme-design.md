# Phase 2 Design — Workspace + RBAC + Dashboard UI + Theme

**Date:** 2026-08-26  
**Status:** Approved (user: Approach 1, Share=A full Workspace share, Theme enum=A uppercase)

## Goals

Authenticated users can manage Workspaces (≤10 owned), RBAC, share Workspace links, use Dashboard with real data, and persist Light/Dark/System theme server-side.

## Decisions

| Topic | Decision |
|-------|----------|
| Implementation order | Backend → App Shell/tokens → Dashboard → Share → Tests |
| Workspace Share | Full in Phase 2; Space share deferred to Phase 3 |
| Theme values | `LIGHT` \| `DARK` \| `SYSTEM` (migrate `system` → `SYSTEM`) |
| Quota | Max 10 non-deleted workspaces where `created_by_user_id = user` |
| Soft-delete | Set `deleted_at` + status; memberships remain for audit |
| Fake data | Never in production paths; counts are real (0 until later phases) |

## Backend

- Tables: `workspaces`, `workspace_memberships`, `share_links`, `share_link_redemptions`, `audit_logs`
- Services: `PermissionService`, `WorkspaceService`, `ShareService`, `DashboardService`, `SettingsService`, `AuditService`
- APIs under `/api/v1` as specified in brainstorm §1
- OAuth/demo login preserve `next` / share token return path

## Frontend

- App shell (sidebar/header/main), semantic tokens, `next-themes` + server settings
- Routes under `/app/*`, share redeem `/share/:token`
- TanStack Query for data; Lucide icons; no monolithic Dashboard

## Out of scope

Space CRUD production, Confluence, Gemini Ask AI, Admin modules, fake AI usage metrics
