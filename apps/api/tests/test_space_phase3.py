from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.space import SpaceRole
from app.models.user import User, UserSettings, UserStatus
from app.models.workspace import WorkspaceRole
from app.permissions.service import PermissionService
from app.spaces.service import SpaceService
from app.workspaces.service import WorkspaceService
from tests.conftest import auth_cookies


@pytest.mark.asyncio
async def test_create_space_makes_owner(db_session: AsyncSession, active_user: User) -> None:
    ws = await WorkspaceService(db_session).create(active_user, name="WS", description=None)
    space, role = await SpaceService(db_session).create(
        active_user, ws.id, name="DMS", description="docs"
    )
    assert role == SpaceRole.OWNER
    assert space.name == "DMS"


@pytest.mark.asyncio
async def test_workspace_owner_is_effective_space_owner(
    db_session: AsyncSession, active_user: User
) -> None:
    ws = await WorkspaceService(db_session).create(active_user, name="WS2", description=None)
    space, _ = await SpaceService(db_session).create(active_user, ws.id, name="Team")
    role = await PermissionService(db_session).get_effective_space_role(space, active_user.id)
    assert role == SpaceRole.OWNER
    assert WorkspaceRole.OWNER == "OWNER"


@pytest.mark.asyncio
async def test_cannot_remove_last_space_owner(
    db_session: AsyncSession, active_user: User
) -> None:
    ws = await WorkspaceService(db_session).create(active_user, name="WS3", description=None)
    space, _ = await SpaceService(db_session).create(active_user, ws.id, name="Solo")
    with pytest.raises(Exception) as exc:
        await SpaceService(db_session).remove_member(active_user, space.id, active_user.id)
    assert getattr(exc.value, "status_code", None) == 409


@pytest.mark.asyncio
async def test_viewer_cannot_update_space(
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

    ws = await db_client.post(
        "/api/v1/workspaces",
        json={"name": "Share Space WS"},
        cookies=cookies_a,
        headers=headers_a,
    )
    assert ws.status_code == 201
    ws_id = ws.json()["id"]
    space = await db_client.post(
        f"/api/v1/workspaces/{ws_id}/spaces",
        json={"name": "Product"},
        cookies=cookies_a,
        headers=headers_a,
    )
    assert space.status_code == 201, space.text
    space_id = space.json()["id"]

    share = await db_client.post(
        f"/api/v1/spaces/{space_id}/share-links",
        json={"role": "VIEWER"},
        cookies=cookies_a,
        headers=headers_a,
    )
    assert share.status_code == 201
    token = share.json()["token"]

    user_b = User(
        id=uuid4(),
        google_sub=f"sub-{uuid4()}",
        email=f"viewer-{uuid4().hex[:8]}@example.com",
        email_verified=True,
        display_name="Viewer",
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
    assert redeem.json()["target_type"] == "SPACE"
    assert redeem.json()["space_id"] == space_id

    # Isolated: cannot browse workspace spaces
    listing = await db_client.get(f"/api/v1/workspaces/{ws_id}/spaces", cookies=cookies_b)
    assert listing.status_code == 403

    update = await db_client.patch(
        f"/api/v1/spaces/{space_id}",
        json={"name": "Hacked"},
        cookies=cookies_b,
        headers=headers_b,
    )
    assert update.status_code == 403


@pytest.mark.asyncio
async def test_star_and_recent(db_session: AsyncSession, active_user: User) -> None:
    ws = await WorkspaceService(db_session).create(active_user, name="WS4", description=None)
    space, _ = await SpaceService(db_session).create(active_user, ws.id, name="StarMe")
    await SpaceService(db_session).star(active_user, space.id)
    starred = await SpaceService(db_session).list_starred(active_user)
    assert any(s.id == space.id for s, _ in starred)
    await SpaceService(db_session).get(active_user, space.id)
    recent = await SpaceService(db_session).list_recent(active_user)
    assert any(s.id == space.id for s, _ in recent)
