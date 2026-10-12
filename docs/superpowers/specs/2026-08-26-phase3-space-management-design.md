# Phase 3 Design — Space Management + Sharing + UI

**Date:** 2026-08-26  
**Status:** Implementing (user: start immediately; Master Prompt + Phase 3 prompt locked)

## Locked decisions

| Topic | Choice |
|-------|--------|
| Space ≠ Confluence Space | Independent; sources later |
| Type filter | **Skip** (Search + Owner + Status only) |
| Duplicate names | Allowed |
| Effective role | `strongest(workspace_role, space_id role)`; Workspace OWNER ⇒ Space OWNER |
| Revoke share link | Does not revoke existing memberships |
| Overview “Pending Invites” | Show **Share Links** (active count) |
| Storage | Real `0` bytes; no fake GB / no fake limit |
| Brand | Knowledge Library |

## Scope

Full Space CRUD, archive/restore, soft-delete + Trash, star, recent, Space share (reuse `share_links`), Access page, Spaces list UI per mockup, Workspace Overview / Activity / Storage panels.

## Out of scope

Confluence import/ingestion, real documents/sources, permanent purge beyond soft-delete.
