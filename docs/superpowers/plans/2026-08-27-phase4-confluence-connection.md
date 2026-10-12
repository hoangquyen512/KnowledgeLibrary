# Phase 4 Confluence Connection Implementation Plan

> **For agentic workers:** Implement task-by-task. Checkboxes track progress.

**Goal:** Direct Confluence connections (PAT + non-prod cookie), SSRF-safe test/browse, attach Sources to Spaces without ingestion.

**Architecture:** ConnectionService + ConfluenceClient + SSRF guard; Sources scaffold under Space; Owner-managed credentials encrypted with existing Fernet helpers.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic `0004`, httpx, Next.js TanStack Query

## Global Constraints

- No plaintext secrets in API/logs
- No fake Confluence import success
- Do not break Phase 0–3
- Cookie auth forbidden in production

## File map

- `apps/api/app/models/confluence.py`, `source.py`
- `apps/api/alembic/versions/0004_phase4_confluence.py`
- `apps/api/app/confluence/{ssrf,client,service}.py`
- `apps/api/app/api/confluence.py`
- `apps/api/tests/test_ssrf_unit.py`, `test_confluence_phase4.py`
- Web: workspace settings Connections + Space Add Source wizard

### Task 1: Models + migration + SSRF unit tests
- [x] Done

### Task 2: Client + Connection/Source service + APIs
- [x] Done

### Task 3: Web UI + docs
- [x] Connections panel + Add Source dialog + README/plan

### Task 4: Verify tests / update README + implementation-plan
- [x] SSRF unit tests pass; app imports OK
- [ ] Live Test Connection against user Confluence URL (await credentials)
