# ADR 002: Space–Source Abstraction

## Context

App Space is not identical to Confluence Space. Sources include Confluence, Jira, and file uploads (Excel/CSV/Word/PowerPoint/PDF).

## Decision

`Space` organizes knowledge; `Source` abstracts origin. Supported types:

- `CONFLUENCE`, `JIRA`
- `FILE_EXCEL`, `FILE_CSV`, `FILE_WORD`, `FILE_POWERPOINT`, `FILE_PDF`
- `LOCAL` (editor-created pages)
- Future-ready: `GOOGLE_DRIVE`, `SHAREPOINT`, `WEB`

Documents/chunks belong to a Source within a Space/Workspace. Ingestion uses a parser/connector registry (`app.ingestion.parsers`) rather than hardcoding type branches in UI.

Ask AI / Studio retrieval is Space-scoped with optional `source_ids` filter. Citations carry location metadata (page/issue key/sheet rows/slide/page number).

## Alternatives

- Map 1:1 App Space = Confluence Space — too rigid.
- Flatten all docs under Workspace — poor UX and permission granularity.

## Consequences

Import/sync attach to Sources. Sync applies to Confluence/Jira only; files use replace/version. Permission is Space-level; Source operations require Editor+.
