---
feature: ING-INGESTION
updated: 2026-10-07
---

# Test cases — ING-INGESTION (upload)

| TC-ID | BR | Priority | Type | Automation | test_file |
|-------|-----|----------|------|------------|-----------|
| TC-ING-UPLOAD-001 | BR-ING-01,04,03,06 | P0 | API integration | auto | tests/test_ingestion_upload_integration.py::test_tc_ing_upload_001_* |
| TC-ING-UPLOAD-002 | BR-ING-01 (EDITOR) | P0 | API integration | auto | tests/test_ingestion_upload_integration.py::test_tc_ing_upload_002_* |
| TC-ING-UPLOAD-003 | BR-ING-05 | P1 | API integration | auto | tests/test_ingestion_upload_integration.py::test_tc_ing_upload_003_* |
| TC-ING-UPLOAD-004 | BR-ING-02 | P0 | API integration | auto | tests/test_ingestion_upload_integration.py::test_tc_ing_upload_004_* |
| TC-ING-IMPORT-001 | BR-ING-07 | P1 | API | planned | Confluence mock — backlog |
| TC-ING-SYNC-001 | Phase 9 | P2 | Unit | auto | tests/test_sync_unit.py |

## Scenario TC-ING-UPLOAD-001

- **Given** user EDITOR+ trên space trống
- **When** upload CSV `auto_import=true`
- **Then** 201, `job_id` có giá trị; job COMPLETED*; documents ≥ 1; upload lần 2 cùng file → `duplicate: true`

## Scenario TC-ING-UPLOAD-002

- **Given** user VIEWER qua space share link
- **When** POST upload
- **Then** HTTP 403
