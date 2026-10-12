from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService
from app.core.config import settings
from app.models.audit import AuditAction
from app.models.share import ShareLink, ShareLinkRedemption, ShareLinkStatus, ShareTargetType
from app.models.space import SpaceMembership, SpaceMembershipSource, SpaceRole
from app.models.user import User
from app.models.workspace import MembershipSource, WorkspaceMembership, WorkspaceRole
from app.permissions.service import PermissionService


def hash_share_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_share_token() -> str:
    return secrets.token_urlsafe(32)


class ShareService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.permissions = PermissionService(db)
        self.audit = AuditService(db)

    async def create_workspace_link(
        self,
        user: User,
        workspace_id: UUID,
        *,
        role: str,
        confirm_owner_role: bool = False,
    ) -> tuple[ShareLink, str]:
        if role not in {WorkspaceRole.OWNER, WorkspaceRole.EDITOR, WorkspaceRole.VIEWER}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "VALIDATION_ERROR", "message": "Invalid share role."},
            )
        await self.permissions.require_workspace(workspace_id)
        await self.permissions.require_role(workspace_id, user.id, WorkspaceRole.OWNER)
        if role == WorkspaceRole.OWNER and not confirm_owner_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "OWNER_SHARE_CONFIRM_REQUIRED",
                    "message": (
                        "Owner access gives full control of this Workspace, "
                        "including managing Spaces, access and deletion. "
                        "Confirm to create this link."
                    ),
                },
            )
        raw = generate_share_token()
        link = ShareLink(
            id=uuid4(),
            token_hash=hash_share_token(raw),
            target_type=ShareTargetType.WORKSPACE,
            workspace_id=workspace_id,
            role=role,
            created_by_user_id=user.id,
            status=ShareLinkStatus.ACTIVE,
        )
        self.db.add(link)
        await self.audit.log(
            action=AuditAction.SHARE_WORKSPACE,
            resource_type="share_link",
            actor_user_id=user.id,
            workspace_id=workspace_id,
            resource_id=link.id,
            metadata={"role": role},
        )
        await self.db.commit()
        await self.db.refresh(link)
        return link, raw

    async def create_space_link(
        self,
        user: User,
        space_id: UUID,
        *,
        role: str,
        confirm_owner_role: bool = False,
    ) -> tuple[ShareLink, str]:
        if role not in {SpaceRole.OWNER, SpaceRole.EDITOR, SpaceRole.VIEWER}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "VALIDATION_ERROR", "message": "Invalid share role."},
            )
        space, _ = await self.permissions.require_space_access(
            space_id, user.id, SpaceRole.OWNER
        )
        if role == SpaceRole.OWNER and not confirm_owner_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "OWNER_SHARE_CONFIRM_REQUIRED",
                    "message": (
                        "Owner access gives full control of this Space, "
                        "including managing access and deletion. Confirm to create this link."
                    ),
                },
            )
        raw = generate_share_token()
        link = ShareLink(
            id=uuid4(),
            token_hash=hash_share_token(raw),
            target_type=ShareTargetType.SPACE,
            workspace_id=space.workspace_id,
            space_id=space.id,
            role=role,
            created_by_user_id=user.id,
            status=ShareLinkStatus.ACTIVE,
        )
        self.db.add(link)
        await self.audit.log(
            action=AuditAction.SHARE_SPACE,
            resource_type="share_link",
            actor_user_id=user.id,
            workspace_id=space.workspace_id,
            resource_id=link.id,
            metadata={"role": role, "space_id": str(space.id)},
        )
        await self.db.commit()
        await self.db.refresh(link)
        return link, raw

    def public_url(self, raw_token: str) -> str:
        return f"{settings.app_url}/share/{raw_token}"

    async def list_workspace_links(self, user: User, workspace_id: UUID) -> list[ShareLink]:
        await self.permissions.require_workspace(workspace_id)
        await self.permissions.require_role(workspace_id, user.id, WorkspaceRole.OWNER)
        result = await self.db.execute(
            select(ShareLink)
            .where(
                ShareLink.workspace_id == workspace_id,
                ShareLink.target_type == ShareTargetType.WORKSPACE,
            )
            .order_by(ShareLink.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_space_links(self, user: User, space_id: UUID) -> list[ShareLink]:
        space, _ = await self.permissions.require_space_access(
            space_id, user.id, SpaceRole.OWNER
        )
        result = await self.db.execute(
            select(ShareLink)
            .where(
                ShareLink.space_id == space.id,
                ShareLink.target_type == ShareTargetType.SPACE,
            )
            .order_by(ShareLink.created_at.desc())
        )
        return list(result.scalars().all())

    async def revoke(self, user: User, link_id: UUID) -> None:
        result = await self.db.execute(select(ShareLink).where(ShareLink.id == link_id))
        link = result.scalar_one_or_none()
        if link is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "SHARE_LINK_NOT_FOUND", "message": "Share link not found."},
            )
        if link.target_type == ShareTargetType.SPACE and link.space_id:
            await self.permissions.require_space_access(
                link.space_id, user.id, SpaceRole.OWNER
            )
        elif link.workspace_id:
            await self.permissions.require_role(link.workspace_id, user.id, WorkspaceRole.OWNER)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "SHARE_LINK_NOT_FOUND", "message": "Share link not found."},
            )
        link.status = ShareLinkStatus.REVOKED
        link.revoked_at = datetime.now(UTC)
        await self.audit.log(
            action=AuditAction.REVOKE_SHARE_LINK,
            resource_type="share_link",
            actor_user_id=user.id,
            workspace_id=link.workspace_id,
            resource_id=link.id,
            metadata={},
        )
        await self.db.commit()

    async def redeem(
        self,
        user: User,
        raw_token: str,
        *,
        ip_hash: str | None = None,
        user_agent_hash: str | None = None,
    ) -> dict:
        token_hash = hash_share_token(raw_token)
        result = await self.db.execute(select(ShareLink).where(ShareLink.token_hash == token_hash))
        link = result.scalar_one_or_none()
        if link is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "SHARE_LINK_NOT_FOUND", "message": "Share link not found."},
            )
        if link.status != ShareLinkStatus.ACTIVE or link.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail={
                    "code": "SHARE_LINK_REVOKED",
                    "message": "This share link is invalid or has been revoked.",
                },
            )
        if link.expires_at and link.expires_at < datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail={"code": "SHARE_LINK_EXPIRED", "message": "Share link has expired."},
            )
        if link.max_uses is not None and link.use_count >= link.max_uses:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail={"code": "SHARE_LINK_EXHAUSTED", "message": "Share link use limit reached."},
            )

        if link.target_type == ShareTargetType.WORKSPACE and link.workspace_id:
            workspace = await self.permissions.require_workspace(link.workspace_id)
            membership = await self.permissions.get_membership(workspace.id, user.id)
            if membership is None:
                self.db.add(
                    WorkspaceMembership(
                        workspace_id=workspace.id,
                        user_id=user.id,
                        role=link.role,
                        source=MembershipSource.SHARE_LINK,
                        granted_by_user_id=link.created_by_user_id,
                    )
                )
            elif WorkspaceRole.RANK.get(link.role, 0) > WorkspaceRole.RANK.get(
                membership.role, 0
            ):
                membership.role = link.role
            link.use_count += 1
            self.db.add(
                ShareLinkRedemption(
                    share_link_id=link.id,
                    user_id=user.id,
                    ip_hash=ip_hash,
                    user_agent_hash=user_agent_hash,
                )
            )
            await self.audit.log(
                action=AuditAction.REDEEM_SHARE_LINK,
                resource_type="share_link",
                actor_user_id=user.id,
                workspace_id=workspace.id,
                resource_id=link.id,
                metadata={"role": link.role, "target": "WORKSPACE"},
            )
            await self.db.commit()
            role = (await self.permissions.get_role(workspace.id, user.id)) or link.role
            return {
                "target_type": "WORKSPACE",
                "workspace_id": workspace.id,
                "space_id": None,
                "role": role,
            }

        if link.target_type == ShareTargetType.SPACE and link.space_id:
            space = await self.permissions.require_space(link.space_id)
            membership = await self.permissions.get_space_membership(space.id, user.id)
            if membership is None:
                self.db.add(
                    SpaceMembership(
                        space_id=space.id,
                        user_id=user.id,
                        role=link.role,
                        source=SpaceMembershipSource.SHARE_LINK,
                        granted_by_user_id=link.created_by_user_id,
                        share_link_id=link.id,
                    )
                )
            elif SpaceRole.RANK.get(link.role, 0) > SpaceRole.RANK.get(membership.role, 0):
                membership.role = link.role
            link.use_count += 1
            self.db.add(
                ShareLinkRedemption(
                    share_link_id=link.id,
                    user_id=user.id,
                    ip_hash=ip_hash,
                    user_agent_hash=user_agent_hash,
                )
            )
            await self.audit.log(
                action=AuditAction.REDEEM_SHARE_LINK,
                resource_type="share_link",
                actor_user_id=user.id,
                workspace_id=space.workspace_id,
                resource_id=link.id,
                metadata={"role": link.role, "target": "SPACE"},
            )
            await self.db.commit()
            role = (
                await self.permissions.get_effective_space_role(space, user.id)
            ) or link.role
            return {
                "target_type": "SPACE",
                "workspace_id": space.workspace_id,
                "space_id": space.id,
                "role": role,
            }

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "UNSUPPORTED_SHARE", "message": "Unsupported share target."},
        )
