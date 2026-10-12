# Source Markdown Export for NotebookLM (Design)

**Date:** 2026-09-04  
**Status:** Approved — implementing

## Goal

Per-source download of all ready pages as a `.zip` of `.md` files for NotebookLM import.

## Decisions

- **Packaging:** one `.zip` with one `.md` per page (not a single merged file).
- **Scope:** per Source (button on each source in Space → Sources).
- **Content:** pages only (`READY`, not deleted); YAML frontmatter (`title`, `source`, `external_url`, `path`).
- **Images:** omit binary images; keep alt text / captions as plain markdown notes.
- **Delivery:** sync `GET /api/v1/sources/{source_id}/export.md.zip` streaming zip bytes (same pattern as Studio PPTX export).
- **Auth:** Space `VIEWER+`.
- **Limits:** max 2000 pages; reject with clear error if exceeded.
- **Out of scope (v1):** async jobs, image files in zip, whole-space export, single merged `.md`.

## Pipeline

1. Require space access (VIEWER).
2. Load source + READY PAGE documents for that source.
3. Sort by tree order (`depth`, `position`, `title`).
4. Build path from in-memory parent chain.
5. Convert `raw_content` HTML → markdown (fallback `normalized_content`); strip `img` → alt note.
6. Write `{index}-{safe_title}.md` entries into zip.
7. Return `application/zip` with Content-Disposition attachment.

## UI

Download control opens a dialog to choose **group depth** before fetching:

| Option | Effect |
|--------|--------|
| Each page as its own file (`group_depth=0`) | Lightest files — best for large NotebookLM imports |
| Group by level 1–5 | Deeper pages merge under the ancestor at that depth; lower level = fewer, larger files |

Default remains level 2. APIs:

- Preview counts: `GET /api/v1/sources/{id}/export-preview`
- Download zip: `GET /api/v1/sources/{id}/export.md.zip?group_depth=0..20`
