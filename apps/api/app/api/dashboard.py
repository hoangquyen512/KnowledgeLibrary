from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.core.database import get_db
from app.dashboard.service import DashboardService
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.workspace import (
    ActivityOut,
    DashboardOut,
    DashboardSummaryOut,
    SharedOut,
    WorkspaceOut,
)

router = APIRouter(tags=["dashboard"])


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


@router.get("/dashboard", response_model=DashboardOut)
async def get_dashboard(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardOut:
    service = DashboardService(db)
    summary = await service.summary(user)
    recent = await service.recent_workspaces(user, limit=5)
    activity_rows = await service.recent_activity(user, limit=10)
    names = await service.workspace_names(
        [a.workspace_id for a in activity_rows if a.workspace_id]
    )
    return DashboardOut(
        summary=DashboardSummaryOut(**summary),
        recent_workspaces=[_workspace_out(ws, m.role) for ws, m in recent],
        recent_spaces=[],
        activity=[
            ActivityOut(
                id=a.id,
                action=a.action,
                resource_type=a.resource_type,
                workspace_id=a.workspace_id,
                workspace_name=names.get(a.workspace_id) if a.workspace_id else None,
                created_at=a.created_at,
                metadata=a.metadata_json_sanitized,
            )
            for a in activity_rows
        ],
    )


@router.get("/dashboard/summary", response_model=DashboardSummaryOut)
async def get_dashboard_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardSummaryOut:
    summary = await DashboardService(db).summary(user)
    return DashboardSummaryOut(**summary)


@router.get("/shared", response_model=SharedOut)
async def get_shared(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SharedOut:
    from app.schemas.space import SpaceOut
    from app.spaces.service import SpaceService

    rows = await DashboardService(db).shared_workspaces(user)
    space_rows = await SpaceService(db).list_shared_with_me(user)
    return SharedOut(
        shared_workspaces=[_workspace_out(ws, m.role) for ws, m, _owner in rows],
        shared_spaces=[
            SpaceOut(
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
                is_starred=False,
                document_count=0,
                source_count=0,
                owner=None,
            )
            for space, role in space_rows
        ],
    )


@router.get("/activity", response_model=list[ActivityOut])
async def get_activity(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ActivityOut]:
    service = DashboardService(db)
    activity_rows = await service.recent_activity(user, limit=50)
    names = await service.workspace_names(
        [a.workspace_id for a in activity_rows if a.workspace_id]
    )
    return [
        ActivityOut(
            id=a.id,
            action=a.action,
            resource_type=a.resource_type,
            workspace_id=a.workspace_id,
            workspace_name=names.get(a.workspace_id) if a.workspace_id else None,
            created_at=a.created_at,
            metadata=a.metadata_json_sanitized,
        )
        for a in activity_rows
    ]
