# Phase 6 — Confluence Ingestion (Design)

**Date:** 2026-08-27  
**Status:** Implemented (Approach 1 — unified pipeline + adapters)

## Decisions

- Full path: SCAN → FETCH → STORE → NORMALIZE → CHUNK → EMBED → INDEX
- Direct + Local Agent fetch/upload (`FETCH_CONFLUENCE` + `POST /agent/ingestion-payloads`)
- Pages + attachments binary (images + draw.io full fidelity, MIME preserved)
- Rewrite inline image URLs to `/api/v1/attachments/{id}/content` (web proxies via `/api/proxy-attachment/{id}`)
- Draw.io: store raw + Space UI viewer (diagrams.net iframe) + download
- Demo (`start.cmd`) E2E: local disk storage, in-process asyncio runner, SQLite; embeddings JSON arrays (embedding stub or zeros)

## Out of scope

Ask AI / hybrid search UI (Phase 7+), sync/delta schedules, Super Admin.
