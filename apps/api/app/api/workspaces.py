from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_csrf
from app.core.database import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.workspace import (
    MemberOut,
    MemberRoleUpdate,
    ShareLinkCreate,
    ShareLinkOut,
    WorkspaceCreate,
    WorkspaceDelete,
    WorkspaceOut,
    WorkspaceUpdate,
)
from app.share.service import ShareService
from app.workspaces.service import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def _workspace_out(workspace: Workspace, role: str | None) -> WorkspaceOut:
    return WorkspaceOut(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        description=workspace.description,
        created_by_user_id=workspace.created_by_user_id,
        status=workspace.status,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        my_role=role,
        space_count=0,
        source_count=0,
    )


@router.get("", response_model=list[WorkspaceOut])
async def list_workspaces(
    filter: str = Query(default="all", pattern="^(all|owned|shared)$"),
    q: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WorkspaceOut]:
    rows = await WorkspaceService(db).list_for_user(user, filter_mode=filter, q=q)
    return [_workspace_out(ws, membership.role) for ws, membership in rows]


@router.post("", response_model=WorkspaceOut, status_code=201)
async def create_workspace(
    body: WorkspaceCreate,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceOut:
    workspace = await WorkspaceService(db).create(
        user, name=body.name, description=body.description
    )
    return _workspace_out(workspace, "OWNER")


@router.get("/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(
    workspace_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceOut:
    workspace, role = await WorkspaceService(db).get_for_user(user, workspace_id)
    return _workspace_out(workspace, role)


@router.patch("/{workspace_id}", response_model=WorkspaceOut)
async def update_workspace(
    workspace_id: UUID,
    body: WorkspaceUpdate,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceOut:
    data = body.model_dump(exclude_unset=True)
    workspace = await WorkspaceService(db).update(
        user,
        workspace_id,
        name=data.get("name"),
        description=data.get("description"),
        update_description="description" in data,
    )
    _, role = await WorkspaceService(db).get_for_user(user, workspace_id)
    return _workspace_out(workspace, role)


@router.delete("/{workspace_id}", status_code=204, response_class=Response)
async def delete_workspace(
    workspace_id: UUID,
    body: WorkspaceDelete,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await WorkspaceService(db).soft_delete(user, workspace_id, confirm_name=body.confirm_name)
    return Response(status_code=204)


@router.get("/{workspace_id}/members", response_model=list[MemberOut])
async def list_members(
    workspace_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MemberOut]:
    memberships = await WorkspaceService(db).list_members(user, workspace_id)
    user_ids = [m.user_id for m in memberships]
    users_result = await db.execute(select(User).where(User.id.in_(user_ids))) if user_ids else None
    users_by_id = {u.id: u for u in (users_result.scalars().all() if users_result else [])}
    return [
        MemberOut(
            id=m.id,
            user_id=m.user_id,
            role=m.role,
            source=m.source,
            email=users_by_id[m.user_id].email if m.user_id in users_by_id else None,
            display_name=users_by_id[m.user_id].display_name if m.user_id in users_by_id else None,
        )
        for m in memberships
    ]


@router.patch("/{workspace_id}/members/{member_user_id}", response_model=MemberOut)
async def change_member_role(
    workspace_id: UUID,
    member_user_id: UUID,
    body: MemberRoleUpdate,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> MemberOut:
    membership = await WorkspaceService(db).change_member_role(
        user, workspace_id, member_user_id, body.role
    )
    member = await db.get(User, member_user_id)
    return MemberOut(
        id=membership.id,
        user_id=membership.user_id,
        role=membership.role,
        source=membership.source,
        email=member.email if member else None,
        display_name=member.display_name if member else None,
    )


@router.delete(
    "/{workspace_id}/members/{member_user_id}",
    status_code=204,
    response_class=Response,
)
async def remove_member(
    workspace_id: UUID,
    member_user_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await WorkspaceService(db).remove_member(user, workspace_id, member_user_id)
    return Response(status_code=204)


@router.get("/{workspace_id}/share-links", response_model=list[ShareLinkOut])
async def list_share_links(
    workspace_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ShareLinkOut]:
    links = await ShareService(db).list_workspace_links(user, workspace_id)
    return [
        ShareLinkOut(
            id=link.id,
            role=link.role,
            status=link.status,
            use_count=link.use_count,
            created_at=link.created_at,
            revoked_at=link.revoked_at,
        )
        for link in links
    ]


@router.post("/{workspace_id}/share-links", response_model=ShareLinkOut, status_code=201)
async def create_share_link(
    workspace_id: UUID,
    body: ShareLinkCreate,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> ShareLinkOut:
    service = ShareService(db)
    link, raw = await service.create_workspace_link(
        user,
        workspace_id,
        role=body.role,
        confirm_owner_role=body.confirm_owner_role,
    )
    return ShareLinkOut(
        id=link.id,
        role=link.role,
        status=link.status,
        use_count=link.use_count,
        created_at=link.created_at,
        revoked_at=link.revoked_at,
        token=raw,
        url=service.public_url(raw),
    )
