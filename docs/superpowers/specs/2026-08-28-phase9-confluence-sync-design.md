# Phase 9 — Confluence Sync / Delta (Design)

**Status:** Approved (Full Phase 9 scope)  
**Date:** 2026-08-28

## Problem

Phase 6 import always wipes and re-fetches all pages. Large Spaces are slow; Confluence edits are not reflected until a full re-import.

## Goals

1. **Delta sync** — detect new/changed/removed pages via Confluence `version` vs stored `external_version`.
2. **Manual sync** — "Sync now" on a READY Source.
3. **Scheduled sync** — per-Source interval: OFF | HOURLY | DAILY.
4. **Sync status UI** — last sync time, summary (added/updated/removed/unchanged), errors.
5. **Direct + Local Agent** — Direct scans on SaaS; Agent uses scan-then-fetch with `page_ids` filter.

## Non-goals

- Super Admin (Phase 10)
- Billing / multi-model picker
- Real-time webhooks from Confluence
- Cross-workspace sync

## Data model

### `sources` (new columns)

| Column | Type | Notes |
|--------|------|-------|
| `sync_enabled` | bool | default false |
| `sync_interval` | string | OFF \| HOURLY \| DAILY |
| `last_sync_at` | timestamptz | nullable |
| `last_sync_status` | string | SUCCESS \| PARTIAL \| FAILED \| null |
| `last_sync_summary` | json | `{added, updated, removed, unchanged, failed}` |
| `next_sync_at` | timestamptz | nullable, computed after sync |

### `ingestion_jobs.job_type`

Add `SYNC` alongside `IMPORT` | `REINDEX`.

Progress JSON adds `sync_stats` and optional `sync_phase` (`scan` | `fetch`).

## Sync algorithm

1. **SCAN** — list remote pages `{id, title, version}` (lightweight).
2. **DIFF** — compare with local `documents` for `source_id` where `deleted_at IS NULL`.
   - `added`: remote id not in local
   - `updated`: same id, different version (or missing version → fetch)
   - `removed`: local id not in remote → soft-delete (`deleted_at`)
   - `unchanged`: same version
3. **FETCH** — full page + attachments only for `added` + `updated`.
4. **UPSERT** — update existing doc in place (replace attachments/chunks for that doc).
5. **HIERARCHY** — re-link ancestors from fetched metadata.
6. **INDEX** — chunk + embed only changed document ids.
7. **FINISH** — update `source.last_sync_*`, compute `next_sync_at`.

Import (`job_type=IMPORT`) behavior unchanged (full wipe).

## API

| Method | Path | Role |
|--------|------|------|
| POST | `/sources/{id}/sync` | Editor+, starts SYNC job |
| PATCH | `/sources/{id}/sync-settings` | Editor+, `{sync_enabled, sync_interval}` |

`SourceOut` enriched with sync fields.

## Scheduler

- Demo: asyncio loop in API lifespan, polls every 60s for `sync_enabled AND next_sync_at <= now AND status=READY`.
- Production: Celery beat (same query).
- Scheduled jobs use `requested_by_user_id = source.created_by_user_id`.

## Agent mode

1. Connector job payload: `{..., scan_only: true}` → agent returns page list (id, title, version) only.
2. SaaS diffs, enqueues second job `{..., page_ids: [...]}` for changed pages only.
3. Removals applied on SaaS after fetch completes.

## UI

Space import monitor (READY source):

- **Sync now** button
- Sync settings: enable toggle + interval dropdown
- Last sync: relative time + badge + summary counts
- Reuse import progress panel for SYNC jobs (copy: "Syncing…")

## Security

- Same RBAC as import (Editor+ to sync, Viewer sees status).
- Workspace boundary unchanged.
- No credential exposure in sync summary.

## Testing

- Unit: `compute_sync_plan` diff logic
- Unit: version included in Confluence page list normalization
- Integration: sync job on demo DB with mocked client (optional)
