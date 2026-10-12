from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.space import Space, SpaceMembership, SpaceRole, SpaceStatus
from app.models.workspace import Workspace, WorkspaceMembership, WorkspaceRole, WorkspaceStatus

WORKSPACE_OWNED_LIMIT = 10


class PermissionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_membership(
        self, workspace_id: UUID, user_id: UUID
    ) -> WorkspaceMembership | None:
        result = await self.db.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.revoked_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_role(self, workspace_id: UUID, user_id: UUID) -> str | None:
        membership = await self.get_membership(workspace_id, user_id)
        return membership.role if membership else None

    async def require_workspace(self, workspace_id: UUID) -> Workspace:
        result = await self.db.execute(
            select(Workspace).where(
                Workspace.id == workspace_id,
                Workspace.deleted_at.is_(None),
                Workspace.status != WorkspaceStatus.DELETED,
            )
        )
        workspace = result.scalar_one_or_none()
        if workspace is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "WORKSPACE_NOT_FOUND", "message": "Workspace not found."},
            )
        return workspace

    async def require_role(self, workspace_id: UUID, user_id: UUID, minimum: str) -> str:
        role = await self.get_role(workspace_id, user_id)
        if role is None or not WorkspaceRole.at_least(role, minimum):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "WORKSPACE_ACCESS_DENIED",
                    "message": "You do not have permission to perform this action.",
                },
            )
        return role

    async def can_view_workspace(self, workspace_id: UUID, user_id: UUID) -> bool:
        role = await self.get_role(workspace_id, user_id)
        return role is not None

    async def can_edit_workspace(self, workspace_id: UUID, user_id: UUID) -> bool:
        role = await self.get_role(workspace_id, user_id)
        return bool(role and WorkspaceRole.at_least(role, WorkspaceRole.EDITOR))

    async def can_manage_workspace_access(self, workspace_id: UUID, user_id: UUID) -> bool:
        role = await self.get_role(workspace_id, user_id)
        return role == WorkspaceRole.OWNER

    async def can_delete_workspace(self, workspace_id: UUID, user_id: UUID) -> bool:
        return await self.can_manage_workspace_access(workspace_id, user_id)

    async def can_create_space(self, workspace_id: UUID, user_id: UUID) -> bool:
        return await self.can_edit_workspace(workspace_id, user_id)

    async def count_active_owners(self, workspace_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(WorkspaceMembership)
            .where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.role == WorkspaceRole.OWNER,
                WorkspaceMembership.revoked_at.is_(None),
            )
        )
        return int(result.scalar_one())

    async def count_owned_workspaces(self, user_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(Workspace)
            .where(
                Workspace.created_by_user_id == user_id,
                Workspace.deleted_at.is_(None),
                Workspace.status != WorkspaceStatus.DELETED,
            )
        )
        return int(result.scalar_one())

    async def get_space_membership(
        self, space_id: UUID, user_id: UUID
    ) -> SpaceMembership | None:
        result = await self.db.execute(
            select(SpaceMembership).where(
                SpaceMembership.space_id == space_id,
                SpaceMembership.user_id == user_id,
                SpaceMembership.revoked_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def require_space(
        self, space_id: UUID, *, allow_deleted: bool = False
    ) -> Space:
        result = await self.db.execute(select(Space).where(Space.id == space_id))
        space = result.scalar_one_or_none()
        if space is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "SPACE_NOT_FOUND", "message": "Space not found."},
            )
        if not allow_deleted and (
            space.deleted_at is not None or space.status == SpaceStatus.DELETED
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "SPACE_NOT_FOUND", "message": "Space not found."},
            )
        return space

    async def get_effective_space_role(self, space: Space, user_id: UUID) -> str | None:
        ws_role = await self.get_role(space.workspace_id, user_id)
        # Workspace OWNER is effective Owner on every Space in the workspace
        if ws_role == WorkspaceRole.OWNER:
            return SpaceRole.OWNER
        membership = await self.get_space_membership(space.id, user_id)
        space_role = membership.role if membership else None
        # Map workspace EDITOR/VIEWER into space ranks
        mapped_ws = None
        if ws_role == WorkspaceRole.EDITOR:
            mapped_ws = SpaceRole.EDITOR
        elif ws_role == WorkspaceRole.VIEWER:
            mapped_ws = SpaceRole.VIEWER
        return SpaceRole.strongest(mapped_ws, space_role)

    async def require_space_access(
        self, space_id: UUID, user_id: UUID, minimum: str, *, allow_deleted: bool = False
    ) -> tuple[Space, str]:
        space = await self.require_space(space_id, allow_deleted=allow_deleted)
        role = await self.get_effective_space_role(space, user_id)
        if role is None or not SpaceRole.at_least(role, minimum):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "SPACE_ACCESS_DENIED",
                    "message": "You don't have access to this Space.",
                },
            )
        return space, role

    async def count_active_space_owners(self, space_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(SpaceMembership)
            .where(
                SpaceMembership.space_id == space_id,
                SpaceMembership.role == SpaceRole.OWNER,
                SpaceMembership.revoked_at.is_(None),
            )
        )
        return int(result.scalar_one())

    async def has_workspace_browse(self, workspace_id: UUID, user_id: UUID) -> bool:
        return await self.can_view_workspace(workspace_id, user_id)