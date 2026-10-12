---
id: ING-INGESTION
title: File upload & Ingestion
status: active
source: README Phase 6, apps/api/app/ingestion/*
updated: 2026-10-07
depends_on: WRK-WORKSPACE, SPC-SPACE
---

# ING-INGESTION — Upload & Import

## Vai trò

- EDITOR+ trên space: upload file, trigger import
- VIEWER: không upload

## Business rules

- BR-ING-01: Upload qua `POST /spaces/{id}/sources/upload` (multipart).
- BR-ING-02: Validate loại file; từ chối executable (.exe).
- BR-ING-03: Dedup checksum trong cùng space → `duplicate: true` trừ khi `force_new`.
- BR-ING-04: `auto_import=true` (mặc định) enqueue job IMPORT sau upload.
- BR-ING-05: `auto_import=false` → gọi `POST /sources/{id}/import` để chạy job.
- BR-ING-06: Job terminal: COMPLETED | COMPLETED_WITH_ERRORS | FAILED | CANCELLED.
- BR-ING-07: Confluence/Jira import qua connection riêng (ngoài phạm vi TC upload).

## Dữ liệu test

- CSV mẫu: `ID,Title,Status` + 2 dòng (fixture `QA_CSV` trong test code).
- Prefix workspace: `QA-ING-{hex}`.

## Open questions

- Excel cần confirm sheet: UI/API flow cần TC riêng P2.

## Change log

| Date | Change |
|------|--------|
| 2026-10-07 | Thêm BR upload; automation TC-ING-UPLOAD-001..004 |
