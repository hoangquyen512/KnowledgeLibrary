from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.models.ai import AiUsage
from app.models.audit import AuditAction, AuditLog
from app.models.document import (
    Document,
    DocumentOrigin,
    DocumentStatus,
    DocumentViewEvent,
)
from app.models.source import Source, SourceStatus, SourceType
from app.models.user import User
from app.spaces.service import SpaceService
from app.workspaces.service import WorkspaceService
from tests.conftest import auth_cookies

NEW_ADMIN_PATHS = [
    "/api/v1/admin/overview",
    "/api/v1/admin/activity-series",
    "/api/v1/admin/source-distribution",
    "/api/v1/admin/ai-usage",
    "/api/v1/admin/recent-activity",
    "/api/v1/admin/top-documents",
    "/api/v1/admin/system-health",
    "/api/v1/admin/export",
]


@pytest.mark.asyncio
async def test_admin_requires_super_admin(db_client: AsyncClient, active_user: User) -> None:
    cookies = auth_cookies(active_user)
    resp = await db_client.get("/api/v1/admin/overview", cookies=cookies)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ADMIN_REQUIRED"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", NEW_ADMIN_PATHS)
async def test_new_admin_endpoints_require_super_admin(
    db_client: AsyncClient, active_user: User, path: str
) -> None:
    cookies = auth_cookies(active_user)
    resp = await db_client.get(path, cookies=cookies)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ADMIN_REQUIRED"


@pytest.mark.asyncio
async def test_admin_overview_ok(db_client, db_session, active_user: User) -> None:
    active_user.is_super_admin = True
    await db_session.commit()
    cookies = auth_cookies(active_user)
    resp = await db_client.get("/api/v1/admin/overview", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert "user_count" in data
    assert "document_count" in data
    assert "kpis" in data
    assert len(data["kpis"]) == 5
    assert all("has_comparison" in kpi for kpi in data["kpis"])
    assert "raw_content" not in str(data)
    assert "encrypted_api_key" not in str(data)
    assert data["timezone"] == "Asia/Ho_Chi_Minh"


@pytest.mark.asyncio
async def test_admin_cannot_suspend_self(db_client, db_session, active_user: User) -> None:
    active_user.is_super_admin = True
    await db_session.commit()
    cookies = auth_cookies(active_user)
    resp = await db_client.patch(
        f"/api/v1/admin/users/{active_user.id}/status",
        cookies=cookies,
        headers={"X-CSRF-Token": cookies[settings.csrf_cookie_name]},
        json={"status": "SUSPENDED"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "CANNOT_SUSPEND_SELF"


@pytest.mark.asyncio
async def test_admin_dashboard_aggregates(
    db_client: AsyncClient, db_session, active_user: User
) -> None:
    active_user.is_super_admin = True
    await db_session.commit()
    cookies = auth_cookies(active_user)

    ws = await WorkspaceService(db_session).create(
        active_user, name=f"FINVIET-{uuid4().hex[:6]}", description=None
    )
    space, _ = await SpaceService(db_session).create(active_user, ws.id, name="Product")
    source = Source(
        workspace_id=ws.id,
        space_id=space.id,
        type=SourceType.CONFLUENCE,
        name="Confluence Space",
        status=SourceStatus.READY,
        created_by_user_id=active_user.id,
    )
    db_session.add(source)
    await db_session.flush()
    page = Document(
        workspace_id=ws.id,
        space_id=space.id,
        source_id=source.id,
        external_id=f"ext-{uuid4()}",
        title="Product Requirements v2.0",
        status=DocumentStatus.READY,
        origin=DocumentOrigin.CONFLUENCE,
        raw_content="<p>secret body</p>",
        created_by_user_id=active_user.id,
    )
    db_session.add(page)
    db_session.add(
        AiUsage(
            user_id=active_user.id,
            workspace_id=ws.id,
            provider="GEMINI",
            input_tokens=84,
            output_tokens=3538,
        )
    )
    await db_session.commit()
    await db_session.refresh(page)
    now = datetime.now(UTC)
    db_session.add(
        DocumentViewEvent(document_id=page.id, user_id=active_user.id, created_at=now)
    )
    db_session.add(
        DocumentViewEvent(document_id=page.id, user_id=active_user.id, created_at=now)
    )
    await db_session.commit()

    series = await db_client.get("/api/v1/admin/activity-series?granularity=daily", cookies=cookies)
    assert series.status_code == 200
    body = series.json()
    assert body["granularity"] == "daily"
    assert len(body["points"]) == 7
    assert body["points"][-1]["documents"] >= 1
    assert body["points"][-1]["ai_queries"] >= 1
    assert "raw_content" not in str(body)

    sources = await db_client.get("/api/v1/admin/source-distribution", cookies=cookies)
    assert sources.status_code == 200
    dist = sources.json()
    assert dist["total"] >= 1
    keys = [item["key"] for item in dist["items"]]
    assert keys == ["confluence", "google_drive", "upload", "web", "other"]
    confluence = next(item for item in dist["items"] if item["key"] == "confluence")
    assert confluence["count"] >= 1

    usage = await db_client.get("/api/v1/admin/ai-usage?period=this_week", cookies=cookies)
    assert usage.status_code == 200
    usage_body = usage.json()
    assert usage_body["input_tokens"] >= 84
    assert usage_body["output_tokens"] >= 3538
    assert usage_body["total_tokens"] == usage_body["input_tokens"] + usage_body["output_tokens"]
    assert "api_key" not in str(usage_body)

    recent = await db_client.get("/api/v1/admin/recent-activity", cookies=cookies)
    assert recent.status_code == 200
    recent_body = recent.json()
    assert recent_body["total"] >= 1
    assert any("space" in item["message"].lower() for item in recent_body["items"])
    assert all("raw_content" not in item["message"] for item in recent_body["items"])

    top = await db_client.get("/api/v1/admin/top-documents", cookies=cookies)
    assert top.status_code == 200
    top_body = top.json()
    assert top_body["views_tracked"] is True
    assert top_body["items"]
    first = top_body["items"][0]
    assert first["title"] == "Product Requirements v2.0"
    assert first["views"] >= 2
    assert first["workspace_name"].startswith("FINVIET")
    assert "raw_content" not in first
    assert "<p>secret body</p>" not in str(top_body)

    health = await db_client.get("/api/v1/admin/system-health", cookies=cookies)
    assert health.status_code == 200
    health_body = health.json()
    keys = [item["key"] for item in health_body["items"]]
    assert keys == ["indexing", "ai", "storage", "api_latency", "error_rate"]
    for item in health_body["items"]:
        assert item["status"] in {"healthy", "warning", "degraded", "offline", "unknown"}
        assert "verified" in item
        if item["status"] == "healthy":
            assert item["verified"] is True

    export = await db_client.get("/api/v1/admin/export", cookies=cookies)
    assert export.status_code == 200
    assert "text/csv" in export.headers["content-type"]
    csv_text = export.text
    assert "users,total" in csv_text
    assert "sources,confluence" in csv_text
    assert "secret body" not in csv_text
    assert "api_key" not in csv_text


@pytest.mark.asyncio
async def test_unviewed_document_is_not_in_top_documents(
    db_client: AsyncClient, db_session, active_user: User
) -> None:
    active_user.is_super_admin = True
    await db_session.commit()
    cookies = auth_cookies(active_user)
    ws = await WorkspaceService(db_session).create(
        active_user, name=f"Quiet-{uuid4().hex[:6]}", description=None
    )
    space, _ = await SpaceService(db_session).create(active_user, ws.id, name="Quiet Space")
    title = f"Unviewed page {uuid4().hex[:8]}"
    db_session.add(
        Document(
            workspace_id=ws.id,
            space_id=space.id,
            external_id=f"ext-{uuid4()}",
            title=title,
            status=DocumentStatus.READY,
            origin=DocumentOrigin.LOCAL,
            created_by_user_id=active_user.id,
        )
    )
    await db_session.commit()
    resp = await db_client.get("/api/v1/admin/top-documents", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["views_tracked"] is True
    assert all(item["title"] != title for item in data["items"])


@pytest.mark.asyncio
async def test_recent_activity_strips_secret_metadata(
    db_client: AsyncClient, db_session, active_user: User
) -> None:
    active_user.is_super_admin = True
    db_session.add(
        AuditLog(
            action=AuditAction.CREATE_SPACE,
            resource_type="space",
            actor_user_id=active_user.id,
            metadata_json_sanitized={
                "name": "Sales Playbook",
                "api_key": "should-not-leak",
                "raw_content": "nope",
            },
        )
    )
    await db_session.commit()
    cookies = auth_cookies(active_user)
    resp = await db_client.get("/api/v1/admin/recent-activity", cookies=cookies)
    assert resp.status_code == 200
    payload = str(resp.json())
    assert "Sales Playbook" in payload
    assert "should-not-leak" not in payload
    assert "nope" not in payload
