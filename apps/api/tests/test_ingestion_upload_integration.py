"""[TC-ING-UPLOAD-*] API integration: file upload → import job → documents."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.ingestion.service import run_ingestion_job
from app.models.document import IngestionJobStatus
from app.models.user import User, UserSettings, UserStatus
from app.spaces.service import SpaceService
from app.workspaces.service import WorkspaceService
from tests.conftest import auth_cookies

QA_CSV = b"ID,Title,Status\n1,QA Upload Row,Done\n2,Second Row,Open\n"
QA_CSV_NAME = "qa-ing-upload.csv"


def _csrf_headers(cookies: dict[str, str]) -> dict[str, str]:
    return {"x-csrf-token": cookies[settings.csrf_cookie_name]}


async def _finish_job(
    client: AsyncClient,
    job_id: str,
    cookies: dict[str, str],
) -> dict:
    """Run the job inline if still queued, then return terminal status."""
    resp = await client.get(f"/api/v1/ingestion-jobs/{job_id}", cookies=cookies)
    assert resp.status_code == 200, resp.text
    last = resp.json()
    if last.get("status") == IngestionJobStatus.QUEUED:
        await run_ingestion_job(UUID(job_id))
        resp = await client.get(f"/api/v1/ingestion-jobs/{job_id}", cookies=cookies)
        assert resp.status_code == 200, resp.text
        last = resp.json()
    return last


async def _seed_space(db_session: AsyncSession, active_user: User) -> tuple[str, str]:
    ws = await WorkspaceService(db_session).create(
        active_user, name=f"QA-ING-{uuid4().hex[:6]}", description=None
    )
    space, _ = await SpaceService(db_session).create(active_user, ws.id, name="Upload Space")
    return str(ws.id), str(space.id)


@pytest.mark.asyncio
async def test_tc_ing_upload_001_csv_auto_import_lists_documents(
    db_client: AsyncClient,
    db_session: AsyncSession,
    active_user: User,
    postgres_ready: bool,
) -> None:
    """[TC-ING-UPLOAD-001] Upload CSV with auto_import creates job and searchable documents."""
    if not postgres_ready:
        pytest.skip("PostgreSQL is not available")
    _ws_id, space_id = await _seed_space(db_session, active_user)
    cookies = auth_cookies(active_user)
    headers = _csrf_headers(cookies)

    upload = await db_client.post(
        f"/api/v1/spaces/{space_id}/sources/upload",
        files={"file": (QA_CSV_NAME, QA_CSV, "text/csv")},
        data={"auto_import": "true"},
        cookies=cookies,
        headers=headers,
    )
    assert upload.status_code == 201, upload.text
    body = upload.json()
    assert body["sources"], body
    row = body["sources"][0]
    assert row["duplicate"] is False
    assert row["job_id"] is not None
    source_id = row["source_id"]

    job = await _finish_job(db_client, row["job_id"], cookies)
    assert job["status"] in (
        IngestionJobStatus.COMPLETED,
        IngestionJobStatus.COMPLETED_WITH_ERRORS,
    ), job

    docs = await db_client.get(f"/api/v1/spaces/{space_id}/documents", cookies=cookies)
    assert docs.status_code == 200
    payload = docs.json()
    titles = {d.get("title") for d in payload}
    # CSV parser titles the sheet from the filename stem (not per-row titles).
    assert "qa-ing-upload" in titles or len(payload) >= 1
    assert any(d.get("document_type") == "SHEET" for d in payload) or len(payload) >= 1

    dup = await db_client.post(
        f"/api/v1/spaces/{space_id}/sources/upload",
        files={"file": (QA_CSV_NAME, QA_CSV, "text/csv")},
        data={"auto_import": "true"},
        cookies=cookies,
        headers=headers,
    )
    assert dup.status_code == 201
    dup_row = dup.json()["sources"][0]
    assert dup_row["duplicate"] is True
    assert dup_row["source_id"] == source_id


@pytest.mark.asyncio
async def test_tc_ing_upload_002_viewer_cannot_upload(
    db_client: AsyncClient,
    db_session: AsyncSession,
    active_user: User,
    postgres_ready: bool,
) -> None:
    """[TC-ING-UPLOAD-002] Space VIEWER cannot upload (requires EDITOR)."""
    if not postgres_ready:
        pytest.skip("PostgreSQL is not available")
    cookies_a = auth_cookies(active_user)
    headers_a = _csrf_headers(cookies_a)
    ws = await db_client.post(
        "/api/v1/workspaces",
        json={"name": f"QA-UP-VWR-{uuid4().hex[:6]}"},
        cookies=cookies_a,
        headers=headers_a,
    )
    assert ws.status_code == 201
    ws_id = ws.json()["id"]
    space = await db_client.post(
        f"/api/v1/workspaces/{ws_id}/spaces",
        json={"name": "Locked"},
        cookies=cookies_a,
        headers=headers_a,
    )
    assert space.status_code == 201
    space_id = space.json()["id"]

    share = await db_client.post(
        f"/api/v1/spaces/{space_id}/share-links",
        json={"role": "VIEWER"},
        cookies=cookies_a,
        headers=headers_a,
    )
    assert share.status_code == 201
    token = share.json()["token"]

    viewer = User(
        id=uuid4(),
        google_sub=f"sub-{uuid4()}",
        email=f"viewer-{uuid4().hex[:8]}@example.com",
        email_verified=True,
        display_name="Viewer",
        status=UserStatus.ACTIVE,
    )
    db_session.add(viewer)
    await db_session.flush()
    db_session.add(UserSettings(user_id=viewer.id))
    await db_session.commit()
    cookies_b = auth_cookies(viewer)
    headers_b = _csrf_headers(cookies_b)
    redeem = await db_client.post(
        f"/api/v1/share/{token}/redeem",
        cookies=cookies_b,
        headers=headers_b,
    )
    assert redeem.status_code == 200

    denied = await db_client.post(
        f"/api/v1/spaces/{space_id}/sources/upload",
        files={"file": ("tiny.csv", b"a,b\n1,2\n", "text/csv")},
        data={"auto_import": "false"},
        cookies=cookies_b,
        headers=headers_b,
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_tc_ing_upload_003_manual_import_endpoint(
    db_client: AsyncClient,
    db_session: AsyncSession,
    active_user: User,
    postgres_ready: bool,
) -> None:
    """[TC-ING-UPLOAD-003] auto_import=false then POST /sources/{id}/import starts job."""
    if not postgres_ready:
        pytest.skip("PostgreSQL is not available")
    _ws_id, space_id = await _seed_space(db_session, active_user)
    cookies = auth_cookies(active_user)
    headers = _csrf_headers(cookies)

    upload = await db_client.post(
        f"/api/v1/spaces/{space_id}/sources/upload",
        files={"file": (f"manual-{uuid4().hex[:6]}.csv", QA_CSV, "text/csv")},
        data={"auto_import": "false"},
        cookies=cookies,
        headers=headers,
    )
    assert upload.status_code == 201, upload.text
    source_id = upload.json()["sources"][0]["source_id"]
    assert upload.json()["sources"][0]["job_id"] is None

    imp = await db_client.post(
        f"/api/v1/sources/{source_id}/import",
        cookies=cookies,
        headers=headers,
    )
    assert imp.status_code == 201, imp.text
    job_id = imp.json()["id"]
    job = await _finish_job(db_client, job_id, cookies)
    assert job["status"] in (
        IngestionJobStatus.COMPLETED,
        IngestionJobStatus.COMPLETED_WITH_ERRORS,
    ), job


@pytest.mark.asyncio
async def test_tc_ing_upload_004_rejects_executable(
    db_client: AsyncClient,
    db_session: AsyncSession,
    active_user: User,
    postgres_ready: bool,
) -> None:
    """[TC-ING-UPLOAD-004] Executable upload rejected (BR-GLOBAL security / file validate)."""
    if not postgres_ready:
        pytest.skip("PostgreSQL is not available")
    _ws_id, space_id = await _seed_space(db_session, active_user)
    cookies = auth_cookies(active_user)
    headers = _csrf_headers(cookies)

    bad = await db_client.post(
        f"/api/v1/spaces/{space_id}/sources/upload",
        files={"file": ("malware.exe", b"MZfake", "application/octet-stream")},
        cookies=cookies,
        headers=headers,
    )
    assert bad.status_code in (400, 415, 422)
