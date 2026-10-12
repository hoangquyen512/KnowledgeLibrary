# Môi trường kiểm thử

## Stack local (khuyến nghị)

- Docker Compose: postgres (pgvector), redis, minio, api, web, worker (tùy profile)
- Hoặc `.\start.cmd` + Postgres/SQLite demo

## Lệnh regression

### API (Windows — dùng venv có sẵn)

```powershell
cd apps\api
.\.venv\Scripts\python.exe -m pytest -q --tb=line
.\.venv\Scripts\python.exe -m pytest -q --tb=line --junitxml=..\..\qa\runs\junit-api.xml
```

Biến môi trường test (mặc định trong `tests/conftest.py`):

- `APP_ENV=test`
- `DATABASE_URL=postgresql+asyncpg://knowledge:knowledge@localhost:5432/knowledge`
- `REDIS_URL=redis://localhost:6379/0`

Nếu Postgres không chạy: ~31 test DB **skip**.

### Web unit

```powershell
cd apps\web
npm test
npx tsc --noEmit
```

### Playwright E2E (Google thật)

```powershell
$env:PLAYWRIGHT_E2E="1"
$env:PLAYWRIGHT_AUTH_STATE="e2e\.auth\user.json"
npx playwright test e2e/
```

### Docker (khi có Docker CLI)

```powershell
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api pytest -q
docker compose exec web npm test
```

**Ghi chú máy dev 2026-10-07:** Docker CLI và `python` global chưa PATH; dùng `apps\api\.venv\Scripts\python.exe`.

## Dữ liệu seed

- Pytest tự tạo user/workspace/space qua fixtures và prefix `QA-*`.
- E2E Playwright tạo `E2E WS {timestamp}` — cần dọn thủ công.
- **Không** chạy regression trên production; không commit `.env`.
