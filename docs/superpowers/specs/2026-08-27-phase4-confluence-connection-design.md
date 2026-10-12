# Phase 4 — Confluence Connection + Browse (Design)

**Date:** 2026-08-27  
**Status:** Approved for implementation (Approach 1, scope B)

## Decisions

- Direct Confluence connection only (Local Agent stub UI → Phase 5)
- Auth: **PAT** primary; **SESSION_COOKIE** allowed only when `APP_ENV != production`
- Manage connections: **Workspace Owner only**
- Browse + attach Source: Workspace Editor+ / Space Editor+
- Browse Confluence spaces (+ shallow pages); **no ingestion** (Phase 6)
- Real HTTP test (no runtime mock); tests use httpx mock
- Credentials encrypted at rest; API never returns raw secrets

## Data model

See brainstorming §1: `confluence_connections`, `sources`.

## API / SSRF / UI

See brainstorming §2–§3.

## Out of scope

Ingestion, sync, HTML sanitize pipeline, Local Agent runtime, embeddings.
