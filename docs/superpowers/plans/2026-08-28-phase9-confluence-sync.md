# Phase 9 Confluence Sync Implementation Plan

> **For agentic workers:** Execute task-by-task with tests between tasks.

**Goal:** Delta sync Confluence Sources with manual + scheduled sync and status UI.

**Architecture:** SCAN→DIFF→FETCH changed pages only→UPSERT→re-index chunks. New `SYNC` job type; sync settings on `sources`; demo scheduler loop.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Next.js, existing ingestion pipeline.

## Global Constraints

- Workspace tenant boundary; Editor+ for sync mutations.
- Import (full wipe) unchanged.
- Demo: SQLite + asyncio scheduler; no Celery required.

---

### Task 1: Schema + models

**Files:**
- Create: `apps/api/alembic/versions/0010_phase9_sync.py`
- Modify: `apps/api/app/models/source.py`, `apps/api/app/models/document.py`
- Modify: `apps/api/app/core/demo_schema.py`

- [ ] Add `IngestionJobType.SYNC`
- [ ] Add source sync columns
- [ ] Alembic migration + SQLite demo patches

### Task 2: Sync diff + Confluence version in list

**Files:**
- Create: `apps/api/app/ingestion/sync.py`
- Modify: `apps/api/app/confluence/client.py` (`_normalize_page_results` includes version)
- Create: `apps/api/tests/test_sync_unit.py`

### Task 3: IngestionService sync job

**Files:**
- Modify: `apps/api/app/ingestion/service.py` — `start_sync`, `run_sync_job`, `_upsert_page`, dispatch in `run_ingestion_job`
- Modify: `apps/api/app/ingestion/progress.py` — sync stats helpers

### Task 4: API + schemas

**Files:**
- Modify: `apps/api/app/api/ingestion.py`
- Modify: `apps/api/app/schemas/confluence.py`
- Modify: `apps/api/app/api/confluence.py` (SourceOut enrichment)

### Task 5: Scheduler + agent scan

**Files:**
- Create: `apps/api/app/ingestion/scheduler.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/connector-agent/agent/main.py` — `scan_only`, `page_ids`

### Task 6: Web UI

**Files:**
- Modify: `apps/web/lib/import-status.ts`
- Create: `apps/web/components/ingestion/SourceSyncPanel.tsx`
- Modify: `apps/web/components/ingestion/SpaceImportMonitor.tsx`, `ImportProgressPanel.tsx`

### Task 7: Docs

- Modify: `docs/implementation-plan.md`, `README.md`
