# QA Index — Knowledge Library

_Cập nhật: 2026-10-07_

| Feature | BR (ước lượng) | TC | Automation | Lần chạy gần nhất |
|---------|----------------|-----|------------|-------------------|
| ACC-AUTH | 6 | 6 | 6 auto | 2026-10-07 local |
| WRK-WORKSPACE | 6 | (xem phase2 tests) | ~7 integration | 2026-10-07 local |
| SPC-SPACE | 4 | (xem phase3 tests) | ~5 integration | 2026-10-07 local |
| ING-INGESTION | 7 | 6 (+2 planned) | 4 auto upload (cần PG) + unit | 2026-10-07 — upload TC skipped |
| ASK-AI | — | backlog qa/testcases | tests/test_ask_unit.py | — |
| ADMIN | — | backlog | tests/test_admin.py | 2026-10-07 local |

## Regression P0 (xem `knowledge/_environments.md`)

- API: `apps/api/.venv/Scripts/python.exe -m pytest -q`
- Web: `npm test` (12 unit)

## Gaps ưu tiên

1. Confluence/Jira import API integration (mock HTTP)
2. IDOR cross-workspace (security checklist)
3. Playwright E2E cần Google storage state
4. Docker CI local khi cài Docker Desktop

## Chi tiết lần chạy

→ `runs/2026-10-07-local-regression.json`
