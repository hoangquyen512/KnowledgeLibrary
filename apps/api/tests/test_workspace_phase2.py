from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserSettings, UserStatus
from app.permissions.service import WORKSPACE_OWNED_LIMIT
from app.settings.service import ALLOWED_THEMES, SettingsService
from app.workspaces.service import WorkspaceService
from tests.conftest import auth_cookies


@pytest.mark.asyncio
async def test_theme_enum_and_update(db_session: AsyncSession, active_user: User) -> None:
    service = SettingsService(db_session)
    settings = await service.get_or_create(active_user)
    assert settings.theme.upper() in ALLOWED_THEMES
    updated = await service.update_theme(active_user, "dark")
    assert updated.theme == "DARK"
    updated = await service.update_theme(active_user, "SYSTEM")
    assert updated.theme == "SYSTEM"


@pytest.mark.asyncio
async def test_create_workspace_makes_owner(
    db_session: AsyncSession, active_user: User
) -> None:
    ws = await WorkspaceService(db_session).create(active_user, name="Acme", description=None)
    assert ws.name == "Acme"
    role_rows = await WorkspaceService(db_session).list_for_user(active_user)
    assert any(m.role == "OWNER" and w.id == ws.id for w, m in role_rows)


@pytest.mark.asyncio
async def test_workspace_quota_blocks_11th(
    db_session: AsyncSession, active_user: User
) -> None:
    service = WorkspaceService(db_session)
    for i in range(WORKSPACE_OWNED_LIMIT):
        await service.create(active_user, name=f"WS {i}", description=None)
    with pytest.raises(Exception) as exc:
        await service.create(active_user, name="Overflow", description=None)
    assert getattr(exc.value, "status_code", None) == 409


@pytest.mark.asyncio
async def test_shared_workspace_does_not_count_quota(
    db_session: AsyncSession, active_user: User
) -> None:
    other = User(
        id=uuid4(),
        google_sub=f"sub-{uuid4()}",
        email=f"other-{uuid4().hex[:8]}@example.com",
        email_verified=True,
        display_name="Other",
        status=UserStatus.ACTIVE,
    )
    db_session.add(other)
    await db_session.flush()
    db_session.add(UserSettings(user_id=other.id))
    await db_session.commit()

    owner_service = WorkspaceService(db_session)
    for i in range(WORKSPACE_OWNED_LIMIT):
        await owner_service.create(active_user, name=f"Mine {i}", description=None)

    shared = await owner_service.create(other, name="Shared WS", description=None)
    from app.models.workspace import MembershipSource, WorkspaceMembership, WorkspaceRole

    db_session.add(
        WorkspaceMembership(
            workspace_id=shared.id,
            user_id=active_user.id,
            role=WorkspaceRole.VIEWER,
            source=MembershipSource.SHARE_LINK,
            granted_by_user_id=other.id,
        )
    )
    await db_session.commit()

    # Still at quota for owned; shared does not free a slot but also shouldn't inflate
    from app.permissions.service import PermissionService

    owned = await PermissionService(db_session).count_owned_workspaces(active_user.id)
    assert owned == WORKSPACE_OWNED_LIMIT


@pytest.mark.asyncio
async def test_cannot_remove_last_owner(
    db_session: AsyncSession, active_user: User
) -> None:
    service = WorkspaceService(db_session)
    ws = await service.create(active_user, name="Solo", description=None)
    with pytest.raises(Exception) as exc:
        await service.remove_member(active_user, ws.id, active_user.id)
    assert getattr(exc.value, "status_code", None) == 409


@pytest.mark.asyncio
async def test_api_create_and_theme(
    db_client: AsyncClient, active_user: User, postgres_ready: bool
) -> None:
    if not postgres_ready:
        pytest.skip("PostgreSQL is not available")
    cookies = auth_cookies(active_user)
    csrf = cookies[list(cookies.keys())[1]]
    headers = {"x-csrf-token": csrf}

    create = await db_client.post(
        "/api/v1/workspaces",
        json={"name": "API Workspace", "description": "hi"},
        cookies=cookies,
        headers=headers,
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["my_role"] == "OWNER"

    dash = await db_client.get("/api/v1/dashboard", cookies=cookies)
    assert dash.status_code == 200
    assert dash.json()["summary"]["owned_workspace_count"] >= 1

    theme = await db_client.patch(
        "/api/v1/me/settings",
        json={"theme": "DARK"},
        cookies=cookies,
        headers=headers,
    )
    assert theme.status_code == 200
    assert theme.json()["theme"] == "DARK"

    settings = await db_client.get("/api/v1/me/settings", cookies=cookies)
    assert settings.status_code == 200
    assert settings.json()["theme"] == "DARK"


@pytest.mark.asyncio
async def test_share_redeem_viewer_cannot_update(
    db_client: AsyncClient,
    db_session: AsyncSession,
    active_user: User,
    postgres_ready: bool,
) -> None:
    if not postgres_ready:
        pytest.skip("PostgreSQL is not available")

    cookies_a = auth_cookies(active_user)
    csrf_a = cookies_a[list(cookies_a.keys())[1]]
    headers_a = {"x-csrf-token": csrf_a}

    create = await db_client.post(
        "/api/v1/workspaces",
        json={"name": "Share Me"},
        cookies=cookies_a,
        headers=headers_a,
    )
    assert create.status_code == 201
    ws_id = create.json()["id"]

    share = await db_client.post(
        f"/api/v1/workspaces/{ws_id}/share-links",
        json={"role": "VIEWER"},
        cookies=cookies_a,
        headers=headers_a,
    )
    assert share.status_code == 201
    token = share.json()["token"]
    assert token

    user_b = User(
        id=uuid4(),
        google_sub=f"sub-{uuid4()}",
        email=f"b-{uuid4().hex[:8]}@example.com",
        email_verified=True,
        display_name="User B",
        status=UserStatus.ACTIVE,
    )
    db_session.add(user_b)
    await db_session.flush()
    db_session.add(UserSettings(user_id=user_b.id))
    await db_session.commit()

    cookies_b = auth_cookies(user_b)
    csrf_b = cookies_b[list(cookies_b.keys())[1]]
    headers_b = {"x-csrf-token": csrf_b}

    redeem = await db_client.post(
        f"/api/v1/share/{token}/redeem",
        cookies=cookies_b,
        headers=headers_b,
    )
    assert redeem.status_code == 200
    assert redeem.json()["role"] == "VIEWER"

    update = await db_client.patch(
        f"/api/v1/workspaces/{ws_id}",
        json={"name": "Hacked"},
        cookies=cookies_b,
        headers=headers_b,
    )
    assert update.status_code == 403
