# Pages — Source Filter (Design)

**Date:** 2026-09-04  
**Status:** Approved (Approach A; remember last source; always one source; full scope)

## Goal

On Space → Pages, always view pages scoped to one selected source. Persist the choice per space. Tree, search, archived list, and create page all respect the selection.

## Decisions

| Topic | Choice |
|-------|--------|
| Default | Remember last source in `localStorage` keyed by space id |
| First visit / stale id | Select first source from `GET /spaces/{id}/sources` |
| “All sources” | Not offered |
| Scope | Tree + search + archived + create (`source_id`) |
| Filtering | Server-side (`source_id` query / body) |

## UI

- Place a source `<select>` (or existing select styling) in the Pages left sidebar, above page search.
- Show source name; optional type hint if space has mixed types.
- Compact tree: hide selector or show abbreviated control; expand restores full selector.
- Mobile tree drawer: same selector at top.
- Empty sources: message + CTA to Space → Sources (no tree).
- On source change: clear expanded/children cache for that space view; navigate to first root page of the new source (or empty state if none).

## API

### Read filters

- `GET /spaces/{space_id}/pages/tree?source_id=&parent_id=`
- `GET /spaces/{space_id}/pages/search?q=&source_id=`
- `GET /spaces/{space_id}/pages/archived?source_id=`

Rules:

- `source_id` **required** for these list endpoints when used from Pages UI (API may reject missing with 400, or treat missing as legacy “all” for backward compat — prefer **required** for clarity).
- Validate source belongs to space and is not soft-deleted; else 404.
- Child counts / `has_children` counted only within the same `source_id`.
- When `parent_id` is set, parent must belong to the same source (or 404).

### Create

- `PageCreate` adds optional `source_id`.
- If `parent_id` set: page inherits parent’s `source_id` (request `source_id` must match parent if provided).
- If root: `source_id` required; must be an active source in the space.
- Stop always forcing `get_or_create_local_source` when caller supplies a valid `source_id`. Keep local-source helper as fallback only when `source_id` omitted (legacy).

## Frontend wiring

- `SpacePagesShell`: load sources; resolve selected id from storage; pass `sourceId` to `PageTree`, `PageTreeSearch`, `ArchivedPagesPanel`, `CreatePageDialog`.
- Query keys include `sourceId` (`page-tree`, `page-archived`, search).
- Storage key: `kl-page-source:{spaceId}`.

## Edge cases

- Selected source deleted → fall back to first remaining source; rewrite storage.
- Open deep link `/pages/{pageId}` whose page’s `source_id` ≠ selected → switch selector to that page’s source (so content + tree stay consistent).
- No pages in source → empty state; Create still allowed if role permits.

## Out of scope

- Multi-select / “All sources”
- Moving pages across sources
- Changing Confluence sync semantics beyond attaching local creates to the chosen source id
