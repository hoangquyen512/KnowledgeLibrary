# Sources UI Redesign — Option B (Design)

**Date:** 2026-09-04  
**Status:** Approved (user chose B)

## Goal

Reduce clutter on Space → Sources while keeping master–detail browse.

## Layout

- **Always 2 columns** (never 3). Drop standalone `ImportDetailsPanel` column; fold essentials into the progress card.
- **Left:** source list only — name, type line, status badge, page count. No inline Sync / Edit connection / Download / Delete.
- **Right header:** selected source title + primary actions `Sync` · `Download` · overflow `⋯` (Edit connection, Auto-sync schedule, Delete).
- **Right body:** import progress **or** document browse (existing `DocumentPanel`), never both stacked with a third rail.
- **Page header:** single `Add Source` (remove duplicate in sidebar).

## Behaviors

- VIEWER: can Download; Sync / Edit / Delete remain manage-only.
- Importing source: main panel shows progress; list stays selectable.
- Overflow menu: lightweight custom popover (no new UI library).
