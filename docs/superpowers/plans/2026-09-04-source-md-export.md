# Source MD Export Implementation Plan

> **For agentic workers:** Implement task-by-task. Steps use checkbox syntax.

**Goal:** Per-source zip download of pages as Markdown for NotebookLM.

**Architecture:** Pure export helpers (`export_md.py`) + IngestionService method + FastAPI StreamingResponse + Download button on source list.

**Tech Stack:** FastAPI, zipfile, BeautifulSoup, Next.js client fetch/blob.

## Global Constraints

- No new dependencies.
- Images omitted (alt text only).
- Max 2000 pages per export.
- VIEWER+ can download.

---

### Task 1: HTML → Markdown + zip builder

**Files:**
- Create `apps/api/app/ingestion/export_md.py`
- Create `apps/api/tests/test_export_md_unit.py`

- [ ] Implement `safe_slug`, `html_to_markdown` (img→alt), `page_markdown`, `build_md_zip`
- [ ] Unit tests for conversion, frontmatter, zip entries, filename uniqueness
- [ ] Run pytest on unit file

### Task 2: API endpoint

**Files:**
- Modify `apps/api/app/ingestion/service.py` (or small method near documents)
- Modify `apps/api/app/api/ingestion.py`

- [ ] `export_source_markdown_zip(user, source_id) -> (bytes, filename)`
- [ ] `GET /sources/{source_id}/export.md.zip`
- [ ] Smoke/unit coverage for empty / over-limit if practical

### Task 3: Frontend button

**Files:**
- Modify `apps/web/components/ingestion/SpaceImportMonitor.tsx`

- [ ] Download button per source
- [ ] fetch blob + toast errors; loading state
