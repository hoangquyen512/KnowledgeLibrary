# Multi-source ingestion

## Pipeline

```text
SourceConnector / Upload
  → Parser (registry by SourceType)
  → NormalizedDocument (+ ChunkHint metadata)
  → IngestionJob (background)
  → Embedder → DocumentChunk index
  → Ask AI / Studio retrieval
```

## Source types

| Type | Connector | Sync | Documents |
|------|-----------|------|-----------|
| CONFLUENCE | Confluence DC (Direct / Local Agent) | Manual + scheduled | Pages + attachments |
| JIRA | Jira DC PAT/Bearer | Manual (+ auto-ready) | One doc per issue |
| FILE_EXCEL | Multipart upload → MinIO | Replace/version | One doc per sheet |
| FILE_CSV | Multipart upload → MinIO | Replace/version | One sheet-like doc |
| FILE_WORD | Multipart upload → MinIO | Replace/version | One doc, heading chunks |
| FILE_POWERPOINT | Multipart upload → MinIO | Replace/version | One doc, slide chunks |
| FILE_PDF | Multipart upload → MinIO | Replace/version | One doc, page chunks |

## Parser registry

`app.ingestion.parsers` — `register_parser` / `get_parser(source_type)`.

Do not scatter `if source_type == ...` across services; route jobs in `IngestionService` then call the registry.

## APIs

- `POST /spaces/{spaceId}/sources` — Confluence attach (existing)
- `POST /spaces/{spaceId}/sources/jira` — Jira project attach
- `POST /spaces/{spaceId}/sources/upload` — multipart file (one file = one Source)
- `POST /sources/{id}/import` — optional JSON `{ sheet_names, options }`
- `POST /sources/{id}/sync` — Confluence / Jira only
- Workspace Jira: `.../jira-connections`, `.../test`, `.../projects`

## Security

- Credentials: Fernet encrypt; masked UI; never logged.
- Files: SHA-256 checksum, MIME + signature checks, size cap (`MAX_UPLOAD_BYTES` / `settings.max_upload_bytes`), random object keys in MinIO/S3 (no binary in Postgres).
- RBAC: Editor+ to add/upload/sync; Viewer query only within Space membership.
