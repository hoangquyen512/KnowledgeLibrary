# Multi-source APIs (additions)

Base path: `/api/v1`

## Jira connections

| Method | Path | Notes |
|--------|------|-------|
| GET | `/workspaces/{workspace_id}/jira-connections` | List (no secrets) |
| POST | `/workspaces/{workspace_id}/jira-connections` | Create (PAT/Bearer encrypted) |
| POST | `/jira-connections/{id}/test` | Test + mark ACTIVE |
| GET | `/jira-connections/{id}/projects` | Browse projects after test |
| POST | `/spaces/{space_id}/sources/jira` | Attach project as Source |

Body attach: `{ connection_id, name, project_id, project_key, project_url?, scope? }`

## File upload

| Method | Path | Notes |
|--------|------|-------|
| POST | `/spaces/{space_id}/sources/upload` | `multipart/form-data`: `file`, optional `source_type`, `force_new`, `auto_import` |
| POST | `/sources/{id}/import` | Optional JSON `{ sheet_names, options }` then enqueue job |
| POST | `/sources/{id}/import-options` | Alias for confirm import with options |

Upload response: `{ source_id, job_id, filename, status, duplicate?, preview?, warnings? }`

One uploaded file = one Source. Duplicate checksum in Space returns `duplicate: true` unless `force_new=true`.

## Ask AI scope

`POST .../messages` and search accept optional `source_ids: UUID[]` in addition to `space_ids`.
