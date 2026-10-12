from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_csrf
from app.core.database import get_db
from app.models.user import User
from app.schemas.space import (
    SpaceCreate,
    SpaceDelete,
    SpaceListOut,
    SpaceOut,
    SpaceOwnerOut,
    SpaceUpdate,
    WorkspaceOverviewOut,
)
from app.schemas.workspace import MemberOut, MemberRoleUpdate, ShareLinkCreate, ShareLinkOut
from app.share.service import ShareService
from app.spaces.service import SpaceService

router = APIRouter(tags=["spaces"])


def _space_out(
    space,
    role: str | None,
    *,
    starred: bool = False,
    owner: User | None = None,
    document_count: int = 0,
    source_count: int = 0,
) -> SpaceOut:
    return SpaceOut(
        id=space.id,
        workspace_id=space.workspace_id,
        name=space.name,
        slug=space.slug,
        description=space.description,
        icon_key=space.icon_key,
        accent_key=space.accent_key,
        created_by_user_id=space.created_by_user_id,
        status=space.status,
        created_at=space.created_at,
        updated_at=space.updated_at,
        archived_at=space.archived_at,
        deleted_at=space.deleted_at,
        my_role=role,
        is_starred=starred,
        document_count=document_count,
        source_count=source_count,
        owner=(
            SpaceOwnerOut(
                id=owner.id, display_name=owner.display_name, email=owner.email
            )
            if owner
            else None
        ),
    )


@router.get("/workspaces/{workspace_id}/spaces", response_model=SpaceListOut)
async def list_spaces(
    workspace_id: UUID,
    tab: str = Query(default="all", pattern="^(all|mine|shared|archived)$"),
    q: str | None = None,
    owner: str | None = None,
    status: str | None = Query(default=None),
    sort: str = Query(default="updated_at", pattern="^(updated_at|name)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SpaceListOut:
    rows, total, counts = await SpaceService(db).list_for_workspace(
        user,
        workspace_id,
        tab=tab,
        q=q,
        owner=owner,
        status_filter=status,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )
    return SpaceListOut(
        items=[
            _space_out(space, role, starred=starred, owner=owner_user)
            for space, role, starred, owner_user in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        counts=counts,
    )


@router.post("/workspaces/{workspace_id}/spaces", response_model=SpaceOut, status_code=201)
async def create_space(
    workspace_id: UUID,
    body: SpaceCreate,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> SpaceOut:
    space, role = await SpaceService(db).create(
        user,
        workspace_id,
        name=body.name,
        description=body.description,
        icon_key=body.icon_key,
        accent_key=body.accent_key,
    )
    return _space_out(space, role, starred=False)


@router.get("/workspaces/{workspace_id}/activity")
async def workspace_activity(
    workspace_id: UUID,
    limit: int = Query(default=5, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    from app.dashboard.service import DashboardService

    rows = await SpaceService(db).workspace_activity(user, workspace_id, limit=limit)
    names = await DashboardService(db).workspace_names(
        [a.workspace_id for a in rows if a.workspace_id]
    )
    return [
        {
            "id": str(a.id),
            "action": a.action,
            "resource_type": a.resource_type,
            "workspace_id": str(a.workspace_id) if a.workspace_id else None,
            "workspace_name": names.get(a.workspace_id) if a.workspace_id else None,
            "created_at": a.created_at.isoformat(),
            "metadata": a.metadata_json_sanitized,
        }
        for a in rows
    ]


@router.get("/workspaces/{workspace_id}/overview", response_model=WorkspaceOverviewOut)
async def workspace_overview(
    workspace_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceOverviewOut:
    data = await SpaceService(db).overview(user, workspace_id)
    return WorkspaceOverviewOut(**data)


@router.get("/spaces/{space_id}", response_model=SpaceOut)
async def get_space(
    space_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SpaceOut:
    from sqlalchemy import func, select

    from app.models.document import Document
    from app.models.source import Source

    space, role, starred = await SpaceService(db).get(user, space_id)
    owner = await db.get(User, space.created_by_user_id)
    doc_count = int(
        (
            await db.execute(
                select(func.count()).select_from(Document).where(Document.space_id == space_id)
            )
        ).scalar_one()
        or 0
    )
    source_count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Source)
                .where(Source.space_id == space_id, Source.deleted_at.is_(None))
            )
        ).scalar_one()
        or 0
    )
    return _space_out(
        space,
        role,
        starred=starred,
        owner=owner,
        document_count=doc_count,
        source_count=source_count,
    )


@router.patch("/spaces/{space_id}", response_model=SpaceOut)
async def update_space(
    space_id: UUID,
    body: SpaceUpdate,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> SpaceOut:
    data = body.model_dump(exclude_unset=True)
    space, role = await SpaceService(db).update(
        user,
        space_id,
        name=data.get("name"),
        description=data.get("description"),
        update_description="description" in data,
        icon_key=data.get("icon_key"),
        accent_key=data.get("accent_key"),
    )
    return _space_out(space, role)


@router.delete("/spaces/{space_id}", status_code=204, response_class=Response)
async def delete_space(
    space_id: UUID,
    body: SpaceDelete,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await SpaceService(db).soft_delete(user, space_id, confirm_name=body.confirm_name)
    return Response(status_code=204)


@router.post("/spaces/{space_id}/delete", status_code=204, response_class=Response)
async def delete_space_post(
    space_id: UUID,
    body: SpaceDelete,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """POST variant — some proxies/clients drop DELETE request bodies."""
    await SpaceService(db).soft_delete(user, space_id, confirm_name=body.confirm_name)
    return Response(status_code=204)


@router.post("/spaces/{space_id}/archive", response_model=SpaceOut)
async def archive_space(
    space_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> SpaceOut:
    space = await SpaceService(db).archive(user, space_id)
    role = (await SpaceService(db).permissions.get_effective_space_role(space, user.id)) or "OWNER"
    return _space_out(space, role)


@router.post("/spaces/{space_id}/restore", response_model=SpaceOut)
async def restore_space(
    space_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> SpaceOut:
    space = await SpaceService(db).restore(user, space_id)
    role = (await SpaceService(db).permissions.get_effective_space_role(space, user.id)) or "OWNER"
    return _space_out(space, role)


@router.post("/spaces/{space_id}/star", status_code=204, response_class=Response)
async def star_space(
    space_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await SpaceService(db).star(user, space_id)
    return Response(status_code=204)


@router.delete("/spaces/{space_id}/star", status_code=204, response_class=Response)
async def unstar_space(
    space_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await SpaceService(db).unstar(user, space_id)
    return Response(status_code=204)


@router.get("/me/starred-spaces", response_model=list[SpaceOut])
async def starred_spaces(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SpaceOut]:
    rows = await SpaceService(db).list_starred(user)
    return [_space_out(space, role, starred=True) for space, role in rows]


@router.get("/me/recent-spaces", response_model=list[SpaceOut])
async def recent_spaces(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SpaceOut]:
    rows = await SpaceService(db).list_recent(user)
    return [_space_out(space, role) for space, role in rows]


@router.get("/me/trash-spaces", response_model=list[SpaceOut])
async def trash_spaces(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SpaceOut]:
    rows = await SpaceService(db).list_trash(user)
    return [_space_out(space, role) for space, role in rows]


@router.get("/spaces/{space_id}/members", response_model=list[MemberOut])
async def list_space_members(
    space_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MemberOut]:
    memberships = await SpaceService(db).list_members(user, space_id)
    user_ids = [m.user_id for m in memberships]
    users = {}
    if user_ids:
        result = await db.execute(select(User).where(User.id.in_(user_ids)))
        users = {u.id: u for u in result.scalars().all()}
    return [
        MemberOut(
            id=m.id,
            user_id=m.user_id,
            role=m.role,
            source=m.source,
            email=users[m.user_id].email if m.user_id in users else None,
            display_name=users[m.user_id].display_name if m.user_id in users else None,
        )
        for m in memberships
    ]


@router.patch("/spaces/{space_id}/members/{member_user_id}", response_model=MemberOut)
async def change_space_member_role(
    space_id: UUID,
    member_user_id: UUID,
    body: MemberRoleUpdate,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> MemberOut:
    membership = await SpaceService(db).change_member_role(
        user, space_id, member_user_id, body.role
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
    "/spaces/{space_id}/members/{member_user_id}",
    status_code=204,
    response_class=Response,
)
async def remove_space_member(
    space_id: UUID,
    member_user_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await SpaceService(db).remove_member(user, space_id, member_user_id)
    return Response(status_code=204)


@router.get("/spaces/{space_id}/share-links", response_model=list[ShareLinkOut])
async def list_space_share_links(
    space_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ShareLinkOut]:
    links = await ShareService(db).list_space_links(user, space_id)
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


@router.post("/spaces/{space_id}/share-links", response_model=ShareLinkOut, status_code=201)
async def create_space_share_link(
    space_id: UUID,
    body: ShareLinkCreate,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> ShareLinkOut:
    service = ShareService(db)
    link, raw = await service.create_space_link(
        user,
        space_id,
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
