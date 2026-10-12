from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService
from app.models.audit import AuditAction
from app.models.user import User
from app.models.workspace import (
    MembershipSource,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
    WorkspaceStatus,
)
from app.permissions.service import WORKSPACE_OWNED_LIMIT, PermissionService

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    base = _SLUG_RE.sub("-", name.strip().lower()).strip("-") or "workspace"
    return f"{base[:80]}-{secrets.token_hex(3)}"


class WorkspaceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.permissions = PermissionService(db)
        self.audit = AuditService(db)

    async def create(self, user: User, *, name: str, description: str | None) -> Workspace:
        cleaned = name.strip()
        if not cleaned:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": "Workspace name is required.",
                },
            )
        if len(cleaned) > 100:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": "Workspace name must be at most 100 characters.",
                },
            )
        if description is not None and len(description) > 500:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": "Description must be at most 500 characters.",
                },
            )

        owned = await self.permissions.count_owned_workspaces(user.id)
        if owned >= WORKSPACE_OWNED_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "WORKSPACE_LIMIT_REACHED",
                    "message": (
                        "Bạn đã đạt giới hạn 10 Workspace. "
                        "Hãy xóa một Workspace trước khi tạo mới."
                    ),
                },
            )

        workspace = Workspace(
            id=uuid4(),
            name=cleaned,
            slug=slugify(cleaned),
            description=(description.strip() if description else None) or None,
            created_by_user_id=user.id,
            status=WorkspaceStatus.ACTIVE,
        )
        self.db.add(workspace)
        await self.db.flush()
        membership = WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceRole.OWNER,
            source=MembershipSource.CREATED,
            granted_by_user_id=user.id,
        )
        self.db.add(membership)
        await self.audit.log(
            action=AuditAction.CREATE_WORKSPACE,
            resource_type="workspace",
            actor_user_id=user.id,
            workspace_id=workspace.id,
            resource_id=workspace.id,
            metadata={"name": workspace.name},
        )
        await self.db.commit()
        await self.db.refresh(workspace)
        return workspace

    async def list_for_user(
        self,
        user: User,
        *,
        filter_mode: str = "all",
        q: str | None = None,
    ) -> list[tuple[Workspace, WorkspaceMembership]]:
        stmt = (
            select(Workspace, WorkspaceMembership)
            .join(
                WorkspaceMembership,
                WorkspaceMembership.workspace_id == Workspace.id,
            )
            .where(
                WorkspaceMembership.user_id == user.id,
                WorkspaceMembership.revoked_at.is_(None),
                Workspace.deleted_at.is_(None),
                Workspace.status != WorkspaceStatus.DELETED,
            )
            .order_by(Workspace.updated_at.desc())
        )
        if filter_mode == "owned":
            stmt = stmt.where(Workspace.created_by_user_id == user.id)
        elif filter_mode == "shared":
            stmt = stmt.where(Workspace.created_by_user_id != user.id)
        if q:
            like = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(Workspace.name.ilike(like), Workspace.description.ilike(like))
            )
        result = await self.db.execute(stmt)
        return list(result.all())

    async def get_for_user(self, user: User, workspace_id: UUID) -> tuple[Workspace, str]:
        workspace = await self.permissions.require_workspace(workspace_id)
        role = await self.permissions.require_role(workspace_id, user.id, WorkspaceRole.VIEWER)
        return workspace, role

    async def update(
        self,
        user: User,
        workspace_id: UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        update_description: bool = False,
    ) -> Workspace:
        workspace = await self.permissions.require_workspace(workspace_id)
        await self.permissions.require_role(workspace_id, user.id, WorkspaceRole.OWNER)
        if name is not None:
            cleaned = name.strip()
            if not cleaned:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "VALIDATION_ERROR",
                        "message": "Workspace name is required.",
                    },
                )
            if len(cleaned) > 100:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "VALIDATION_ERROR",
                        "message": "Workspace name must be at most 100 characters.",
                    },
                )
            workspace.name = cleaned
        if update_description:
            if description is not None and len(description) > 500:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "VALIDATION_ERROR",
                        "message": "Description must be at most 500 characters.",
                    },
                )
            workspace.description = (description.strip() if description else None) or None
        await self.audit.log(
            action=AuditAction.UPDATE_WORKSPACE,
            resource_type="workspace",
            actor_user_id=user.id,
            workspace_id=workspace.id,
            resource_id=workspace.id,
            metadata={"name": workspace.name},
        )
        await self.db.commit()
        await self.db.refresh(workspace)
        return workspace

    async def soft_delete(self, user: User, workspace_id: UUID, *, confirm_name: str) -> None:
        workspace = await self.permissions.require_workspace(workspace_id)
        await self.permissions.require_role(workspace_id, user.id, WorkspaceRole.OWNER)
        if confirm_name.strip() != workspace.name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "CONFIRM_NAME_MISMATCH",
                    "message": "Typed name does not match the Workspace name.",
                },
            )
        workspace.status = WorkspaceStatus.DELETED
        workspace.deleted_at = datetime.now(UTC)
        await self.audit.log(
            action=AuditAction.DELETE_WORKSPACE,
            resource_type="workspace",
            actor_user_id=user.id,
            workspace_id=workspace.id,
            resource_id=workspace.id,
            metadata={"name": workspace.name},
        )
        await self.db.commit()

    async def list_members(self, user: User, workspace_id: UUID) -> list[WorkspaceMembership]:
        await self.permissions.require_workspace(workspace_id)
        await self.permissions.require_role(workspace_id, user.id, WorkspaceRole.VIEWER)
        result = await self.db.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.revoked_at.is_(None),
            )
            .order_by(WorkspaceMembership.created_at.asc())
        )
        return list(result.scalars().all())

    async def change_member_role(
        self,
        actor: User,
        workspace_id: UUID,
        member_user_id: UUID,
        new_role: str,
    ) -> WorkspaceMembership:
        if new_role not in {
            WorkspaceRole.OWNER,
            WorkspaceRole.EDITOR,
            WorkspaceRole.VIEWER,
        }:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "VALIDATION_ERROR", "message": "Invalid role."},
            )
        await self.permissions.require_workspace(workspace_id)
        await self.permissions.require_role(workspace_id, actor.id, WorkspaceRole.OWNER)
        membership = await self.permissions.get_membership(workspace_id, member_user_id)
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "MEMBER_NOT_FOUND", "message": "Member not found."},
            )
        if membership.role == WorkspaceRole.OWNER and new_role != WorkspaceRole.OWNER:
            owners = await self.permissions.count_active_owners(workspace_id)
            if owners <= 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "LAST_OWNER",
                        "message": "Cannot remove or downgrade the last Owner.",
                    },
                )
        old_role = membership.role
        membership.role = new_role
        action = (
            AuditAction.ADD_OWNER
            if new_role == WorkspaceRole.OWNER
            else AuditAction.CHANGE_ROLE
        )
        await self.audit.log(
            action=action,
            resource_type="workspace_membership",
            actor_user_id=actor.id,
            workspace_id=workspace_id,
            resource_id=membership.id,
            metadata={"user_id": str(member_user_id), "from": old_role, "to": new_role},
        )
        await self.db.commit()
        await self.db.refresh(membership)
        return membership

    async def remove_member(
        self, actor: User, workspace_id: UUID, member_user_id: UUID
    ) -> None:
        await self.permissions.require_workspace(workspace_id)
        await self.permissions.require_role(workspace_id, actor.id, WorkspaceRole.OWNER)
        membership = await self.permissions.get_membership(workspace_id, member_user_id)
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "MEMBER_NOT_FOUND", "message": "Member not found."},
            )
        if membership.role == WorkspaceRole.OWNER:
            owners = await self.permissions.count_active_owners(workspace_id)
            if owners <= 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "LAST_OWNER",
                        "message": "Cannot remove or downgrade the last Owner.",
                    },
                )
        membership.revoked_at = datetime.now(UTC)
        await self.audit.log(
            action=AuditAction.REMOVE_MEMBER,
            resource_type="workspace_membership",
            actor_user_id=actor.id,
            workspace_id=workspace_id,
            resource_id=membership.id,
            metadata={"user_id": str(member_user_id), "role": membership.role},
        )
        await self.db.commit()
