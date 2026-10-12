# Phase 5 — Local Connector Agent Foundation (Design)

**Date:** 2026-08-27  
**Status:** Implemented (Approach 1, scope A)

## Decisions

- Agent register via one-time token; heartbeat; jobs next/complete with NOOP/PING only
- Credential location: CLOUD | LOCAL_AGENT (both in UI); no Confluence fetch in Phase 5
- Connection mode: DIRECT | LOCAL_AGENT
- Owner manages tokens/agents; Editor+ can view status
- Agent secret + registration token hashed at rest; raw shown once
- Offline if heartbeat older than 180s

## APIs

**User (session + CSRF on mutations):**
- `POST /workspaces/{id}/agent-registration-tokens`
- `GET /workspaces/{id}/agents`
- `DELETE /agents/{id}`
- `POST /workspaces/{id}/agent-jobs/noop`

**Agent (headers `X-Agent-Id`, `X-Agent-Secret`):**
- `POST /agent/register`
- `POST /agent/heartbeat`
- `GET /agent/jobs/next`
- `POST /agent/jobs/{id}/complete`

## Out of scope

Fetch Confluence, upload payloads, ingest/chunk/embed (Phase 6).
