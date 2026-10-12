from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService
from app.models.audit import AuditAction
from app.models.share import ShareLink, ShareLinkStatus
from app.models.space import (
    ALLOWED_ACCENT_KEYS,
    ALLOWED_ICON_KEYS,
    Space,
    SpaceMembership,
    SpaceMembershipSource,
    SpaceRole,
    SpaceStatus,
    UserRecentSpace,
    UserStarredSpace,
)
from app.models.user import User
from app.models.workspace import WorkspaceMembership, WorkspaceRole
from app.permissions.service import PermissionService
from app.workspaces.service import slugify


class SpaceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.permissions = PermissionService(db)
        self.audit = AuditService(db)

    def _validate_name(self, name: str) -> str:
        cleaned = name.strip()
        if not cleaned:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "VALIDATION_ERROR", "message": "Space name is required."},
            )
        if len(cleaned) > 100:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": "Space name must be at most 100 characters.",
                },
            )
        return cleaned

    def _normalize_icon_accent(
        self, icon_key: str | None, accent_key: str | None
    ) -> tuple[str, str]:
        icon = (icon_key or "folder").strip().lower()
        accent = (accent_key or "blue").strip().lower()
        if icon not in ALLOWED_ICON_KEYS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "VALIDATION_ERROR", "message": "Invalid icon_key."},
            )
        if accent not in ALLOWED_ACCENT_KEYS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "VALIDATION_ERROR", "message": "Invalid accent_key."},
            )
        return icon, accent

    async def create(
        self,
        user: User,
        workspace_id: UUID,
        *,
        name: str,
        description: str | None = None,
        icon_key: str | None = None,
        accent_key: str | None = None,
    ) -> tuple[Space, str]:
        await self.permissions.require_workspace(workspace_id)
        if not await self.permissions.can_create_space(workspace_id, user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "SPACE_EDIT_DENIED",
                    "message": "You do not have permission to create a Space.",
                },
            )
        cleaned = self._validate_name(name)
        if description is not None and len(description) > 500:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": "Description must be at most 500 characters.",
                },
            )
        icon, accent = self._normalize_icon_accent(icon_key, accent_key)
        space = Space(
            id=uuid4(),
            workspace_id=workspace_id,
            name=cleaned,
            slug=slugify(cleaned),
            description=(description.strip() if description else None) or None,
            icon_key=icon,
            accent_key=accent,
            created_by_user_id=user.id,
            status=SpaceStatus.ACTIVE,
        )
        self.db.add(space)
        await self.db.flush()
        self.db.add(
            SpaceMembership(
                space_id=space.id,
                user_id=user.id,
                role=SpaceRole.OWNER,
                source=SpaceMembershipSource.CREATED,
                granted_by_user_id=user.id,
            )
        )
        await self.audit.log(
            action=AuditAction.CREATE_SPACE,
            resource_type="space",
            actor_user_id=user.id,
            workspace_id=workspace_id,
            resource_id=space.id,
            metadata={"name": space.name},
        )
        await self.db.commit()
        await self.db.refresh(space)
        role = await self.permissions.get_effective_space_role(space, user.id) or SpaceRole.OWNER
        return space, role

    async def list_for_workspace(
        self,
        user: User,
        workspace_id: UUID,
        *,
        tab: str = "all",
        q: str | None = None,
        owner: str | None = None,
        status_filter: str | None = None,
        sort: str = "updated_at",
        order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[tuple[Space, str, bool, User | None]], int, dict[str, int]]:
        await self.permissions.require_workspace(workspace_id)
        if not await self.permissions.has_workspace_browse(workspace_id, user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "WORKSPACE_ACCESS_DENIED",
                    "message": "You do not have access to browse this Workspace.",
                },
            )

        async def _count(extra) -> int:
            stmt = select(func.count()).select_from(Space).where(
                Space.workspace_id == workspace_id, *extra
            )
            return int((await self.db.execute(stmt)).scalar_one())

        counts = {
            "all": await _count(
                [Space.deleted_at.is_(None), Space.status != SpaceStatus.DELETED]
            ),
            "archived": await _count(
                [
                    Space.deleted_at.is_(None),
                    Space.status == SpaceStatus.ARCHIVED,
                ]
            ),
        }

        # My Spaces = effective OWNER — approximate via space membership OWNER or ws OWNER
        ws_role = await self.permissions.get_role(workspace_id, user.id)
        if ws_role == WorkspaceRole.OWNER:
            counts["mine"] = counts["all"]
        else:
            mine_q = (
                select(func.count())
                .select_from(Space)
                .join(
                    SpaceMembership,
                    and_(
                        SpaceMembership.space_id == Space.id,
                        SpaceMembership.user_id == user.id,
                        SpaceMembership.role == SpaceRole.OWNER,
                        SpaceMembership.revoked_at.is_(None),
                    ),
                )
                .where(
                    Space.workspace_id == workspace_id,
                    Space.deleted_at.is_(None),
                    Space.status != SpaceStatus.DELETED,
                )
            )
            counts["mine"] = int((await self.db.execute(mine_q)).scalar_one())

        # Shared with me inside workspace: space membership without being ws-wide owner equiv
        shared_q = (
            select(func.count())
            .select_from(Space)
            .join(
                SpaceMembership,
                and_(
                    SpaceMembership.space_id == Space.id,
                    SpaceMembership.user_id == user.id,
                    SpaceMembership.revoked_at.is_(None),
                ),
            )
            .where(
                Space.workspace_id == workspace_id,
                Space.deleted_at.is_(None),
                Space.status != SpaceStatus.DELETED,
                Space.created_by_user_id != user.id,
            )
        )
        counts["shared"] = int((await self.db.execute(shared_q)).scalar_one())

        filters = [Space.workspace_id == workspace_id]
        if tab == "archived":
            filters.extend([Space.deleted_at.is_(None), Space.status == SpaceStatus.ARCHIVED])
        elif tab == "mine":
            filters.extend([Space.deleted_at.is_(None), Space.status != SpaceStatus.DELETED])
            if ws_role != WorkspaceRole.OWNER:
                filters.append(
                    Space.id.in_(
                        select(SpaceMembership.space_id).where(
                            SpaceMembership.user_id == user.id,
                            SpaceMembership.role == SpaceRole.OWNER,
                            SpaceMembership.revoked_at.is_(None),
                        )
                    )
                )
        elif tab == "shared":
            filters.extend(
                [
                    Space.deleted_at.is_(None),
                    Space.status != SpaceStatus.DELETED,
                    Space.created_by_user_id != user.id,
                    Space.id.in_(
                        select(SpaceMembership.space_id).where(
                            SpaceMembership.user_id == user.id,
                            SpaceMembership.revoked_at.is_(None),
                        )
                    ),
                ]
            )
        else:
            filters.extend([Space.deleted_at.is_(None), Space.status != SpaceStatus.DELETED])
            if status_filter == "active":
                filters.append(Space.status == SpaceStatus.ACTIVE)
            elif status_filter == "archived":
                filters.append(Space.status == SpaceStatus.ARCHIVED)

        if q and q.strip():
            like = f"%{q.strip()}%"
            filters.append(or_(Space.name.ilike(like), Space.description.ilike(like)))

        if owner == "me":
            filters.append(Space.created_by_user_id == user.id)
        elif owner and owner != "all":
            try:
                owner_id = UUID(owner)
                filters.append(Space.created_by_user_id == owner_id)
            except ValueError:
                pass

        sort_col = Space.name if sort == "name" else Space.updated_at
        ordering = sort_col.asc() if order == "asc" else sort_col.desc()

        total = int(
            (
                await self.db.execute(select(func.count()).select_from(Space).where(*filters))
            ).scalar_one()
        )
        page = max(1, page)
        page_size = min(max(1, page_size), 100)
        result = await self.db.execute(
            select(Space)
            .where(*filters)
            .order_by(ordering)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        spaces = list(result.scalars().all())

        starred_ids: set[UUID] = set()
        if spaces:
            star_result = await self.db.execute(
                select(UserStarredSpace.space_id).where(
                    UserStarredSpace.user_id == user.id,
                    UserStarredSpace.space_id.in_([s.id for s in spaces]),
                )
            )
            starred_ids = set(star_result.scalars().all())

        owners: dict[UUID, User] = {}
        owner_ids = {s.created_by_user_id for s in spaces}
        if owner_ids:
            owners_result = await self.db.execute(select(User).where(User.id.in_(owner_ids)))
            owners = {u.id: u for u in owners_result.scalars().all()}

        rows: list[tuple[Space, str, bool, User | None]] = []
        for space in spaces:
            role = (
                await self.permissions.get_effective_space_role(space, user.id)
                or SpaceRole.VIEWER
            )
            rows.append(
                (space, role, space.id in starred_ids, owners.get(space.created_by_user_id))
            )
        return rows, total, counts

    async def get(self, user: User, space_id: UUID) -> tuple[Space, str, bool]:
        space, role = await self.permissions.require_space_access(
            space_id, user.id, SpaceRole.VIEWER
        )
        await self.touch_recent(user, space.id)
        starred = await self.db.execute(
            select(UserStarredSpace).where(
                UserStarredSpace.user_id == user.id, UserStarredSpace.space_id == space.id
            )
        )
        return space, role, starred.scalar_one_or_none() is not None

    async def update(
        self,
        user: User,
        space_id: UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        update_description: bool = False,
        icon_key: str | None = None,
        accent_key: str | None = None,
    ) -> tuple[Space, str]:
        space, role = await self.permissions.require_space_access(
            space_id, user.id, SpaceRole.EDITOR
        )
        if space.status == SpaceStatus.ARCHIVED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "SPACE_ARCHIVED",
                    "message": "Archived Spaces are read-only.",
                },
            )
        if name is not None:
            space.name = self._validate_name(name)
        if update_description:
            if description is not None and len(description) > 500:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "VALIDATION_ERROR",
                        "message": "Description must be at most 500 characters.",
                    },
                )
            space.description = (description.strip() if description else None) or None
        if icon_key is not None or accent_key is not None:
            icon, accent = self._normalize_icon_accent(
                icon_key or space.icon_key, accent_key or space.accent_key
            )
            space.icon_key = icon
            space.accent_key = accent
        await self.audit.log(
            action=AuditAction.UPDATE_SPACE,
            resource_type="space",
            actor_user_id=user.id,
            workspace_id=space.workspace_id,
            resource_id=space.id,
            metadata={"name": space.name},
        )
        await self.db.commit()
        await self.db.refresh(space)
        return space, role

    async def archive(self, user: User, space_id: UUID) -> Space:
        space, _ = await self.permissions.require_space_access(
            space_id, user.id, SpaceRole.OWNER
        )
        space.status = SpaceStatus.ARCHIVED
        space.archived_at = datetime.now(UTC)
        await self.audit.log(
            action=AuditAction.ARCHIVE_SPACE,
            resource_type="space",
            actor_user_id=user.id,
            workspace_id=space.workspace_id,
            resource_id=space.id,
            metadata={"name": space.name},
        )
        await self.db.commit()
        await self.db.refresh(space)
        return space

    async def restore(self, user: User, space_id: UUID) -> Space:
        space, _ = await self.permissions.require_space_access(
            space_id, user.id, SpaceRole.OWNER, allow_deleted=True
        )
        if space.status == SpaceStatus.DELETED or space.deleted_at is not None:
            space.status = SpaceStatus.ACTIVE
            space.deleted_at = None
            space.archived_at = None
        else:
            space.status = SpaceStatus.ACTIVE
            space.archived_at = None
        await self.audit.log(
            action=AuditAction.RESTORE_SPACE,
            resource_type="space",
            actor_user_id=user.id,
            workspace_id=space.workspace_id,
            resource_id=space.id,
            metadata={"name": space.name},
        )
        await self.db.commit()
        await self.db.refresh(space)
        return space

    async def soft_delete(self, user: User, space_id: UUID, *, confirm_name: str) -> None:
        space, _ = await self.permissions.require_space_access(
            space_id, user.id, SpaceRole.OWNER
        )
        if confirm_name.strip() != space.name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "CONFIRM_NAME_MISMATCH",
                    "message": "Typed name does not match the Space name.",
                },
            )
        space.status = SpaceStatus.DELETED
        space.deleted_at = datetime.now(UTC)
        await self.audit.log(
            action=AuditAction.DELETE_SPACE,
            resource_type="space",
            actor_user_id=user.id,
            workspace_id=space.workspace_id,
            resource_id=space.id,
            metadata={"name": space.name},
        )
        await self.db.commit()

    async def star(self, user: User, space_id: UUID) -> None:
        space, _ = await self.permissions.require_space_access(
            space_id, user.id, SpaceRole.VIEWER
        )
        existing = await self.db.execute(
            select(UserStarredSpace).where(
                UserStarredSpace.user_id == user.id, UserStarredSpace.space_id == space.id
            )
        )
        if existing.scalar_one_or_none() is None:
            self.db.add(UserStarredSpace(user_id=user.id, space_id=space.id))
            await self.db.commit()

    async def unstar(self, user: User, space_id: UUID) -> None:
        await self.permissions.require_space_access(space_id, user.id, SpaceRole.VIEWER)
        result = await self.db.execute(
            select(UserStarredSpace).where(
                UserStarredSpace.user_id == user.id, UserStarredSpace.space_id == space_id
            )
        )
        row = result.scalar_one_or_none()
        if row:
            await self.db.delete(row)
            await self.db.commit()

    async def touch_recent(self, user: User, space_id: UUID) -> None:
        result = await self.db.execute(
            select(UserRecentSpace).where(
                UserRecentSpace.user_id == user.id, UserRecentSpace.space_id == space_id
            )
        )
        row = result.scalar_one_or_none()
        now = datetime.now(UTC)
        if row is None:
            self.db.add(
                UserRecentSpace(user_id=user.id, space_id=space_id, last_opened_at=now)
            )
        else:
            row.last_opened_at = now
        await self.db.commit()

    async def list_starred(self, user: User) -> list[tuple[Space, str]]:
        result = await self.db.execute(
            select(Space, UserStarredSpace)
            .join(UserStarredSpace, UserStarredSpace.space_id == Space.id)
            .where(
                UserStarredSpace.user_id == user.id,
                Space.deleted_at.is_(None),
                Space.status != SpaceStatus.DELETED,
            )
            .order_by(UserStarredSpace.created_at.desc())
        )
        out: list[tuple[Space, str]] = []
        for space, _star in result.all():
            role = await self.permissions.get_effective_space_role(space, user.id)
            if role:
                out.append((space, role))
        return out

    async def list_recent(self, user: User, *, limit: int = 20) -> list[tuple[Space, str]]:
        result = await self.db.execute(
            select(Space, UserRecentSpace)
            .join(UserRecentSpace, UserRecentSpace.space_id == Space.id)
            .where(
                UserRecentSpace.user_id == user.id,
                Space.deleted_at.is_(None),
                Space.status != SpaceStatus.DELETED,
            )
            .order_by(UserRecentSpace.last_opened_at.desc())
            .limit(limit)
        )
        out: list[tuple[Space, str]] = []
        for space, _recent in result.all():
            role = await self.permissions.get_effective_space_role(space, user.id)
            if role:
                out.append((space, role))
        return out

    async def list_trash(self, user: User) -> list[tuple[Space, str]]:
        # Spaces user owns (effective) that are deleted
        result = await self.db.execute(
            select(Space).where(
                Space.deleted_at.is_not(None),
                Space.status == SpaceStatus.DELETED,
            )
            .order_by(Space.deleted_at.desc())
        )
        out: list[tuple[Space, str]] = []
        for space in result.scalars().all():
            role = await self.permissions.get_effective_space_role(space, user.id)
            if role == SpaceRole.OWNER:
                out.append((space, role))
        return out

    async def list_shared_with_me(self, user: User) -> list[tuple[Space, str]]:
        """Spaces shared via membership without workspace browse access (isolated)."""
        result = await self.db.execute(
            select(Space, SpaceMembership)
            .join(
                SpaceMembership,
                and_(
                    SpaceMembership.space_id == Space.id,
                    SpaceMembership.user_id == user.id,
                    SpaceMembership.revoked_at.is_(None),
                ),
            )
            .where(
                Space.deleted_at.is_(None),
                Space.status != SpaceStatus.DELETED,
            )
            .order_by(Space.updated_at.desc())
        )
        out: list[tuple[Space, str]] = []
        for space, membership in result.all():
            if await self.permissions.has_workspace_browse(space.workspace_id, user.id):
                continue
            out.append((space, membership.role))
        return out

    async def workspace_activity(
        self, user: User, workspace_id: UUID, *, limit: int = 5
    ) -> list:
        from app.models.audit import AuditLog

        await self.permissions.require_role(workspace_id, user.id, WorkspaceRole.VIEWER)
        result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.workspace_id == workspace_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def overview(self, user: User, workspace_id: UUID) -> dict:
        from app.models.document import Document
        from app.models.source import Source

        await self.permissions.require_role(workspace_id, user.id, WorkspaceRole.VIEWER)
        space_count = int(
            (
                await self.db.execute(
                    select(func.count())
                    .select_from(Space)
                    .where(
                        Space.workspace_id == workspace_id,
                        Space.deleted_at.is_(None),
                        Space.status != SpaceStatus.DELETED,
                    )
                )
            ).scalar_one()
        )
        document_count = int(
            (
                await self.db.execute(
                    select(func.count())
                    .select_from(Document)
                    .where(Document.workspace_id == workspace_id)
                )
            ).scalar_one()
        )
        source_count = int(
            (
                await self.db.execute(
                    select(func.count())
                    .select_from(Source)
                    .where(
                        Source.workspace_id == workspace_id,
                        Source.deleted_at.is_(None),
                    )
                )
            ).scalar_one()
        )
        member_count = int(
            (
                await self.db.execute(
                    select(func.count())
                    .select_from(WorkspaceMembership)
                    .where(
                        WorkspaceMembership.workspace_id == workspace_id,
                        WorkspaceMembership.revoked_at.is_(None),
                    )
                )
            ).scalar_one()
        )
        share_count = int(
            (
                await self.db.execute(
                    select(func.count())
                    .select_from(ShareLink)
                    .where(
                        ShareLink.workspace_id == workspace_id,
                        ShareLink.status == ShareLinkStatus.ACTIVE,
                        ShareLink.revoked_at.is_(None),
                    )
                )
            ).scalar_one()
        )
        return {
            "space_count": space_count,
            "document_count": document_count,
            "source_count": source_count,
            "storage_bytes": 0,
            "member_count": member_count,
            "active_share_link_count": share_count,
        }

    async def list_members(self, user: User, space_id: UUID) -> list[SpaceMembership]:
        await self.permissions.require_space_access(space_id, user.id, SpaceRole.VIEWER)
        result = await self.db.execute(
            select(SpaceMembership)
            .where(
                SpaceMembership.space_id == space_id,
                SpaceMembership.revoked_at.is_(None),
            )
            .order_by(SpaceMembership.created_at.asc())
        )
        return list(result.scalars().all())

    async def change_member_role(
        self, actor: User, space_id: UUID, member_user_id: UUID, new_role: str
    ) -> SpaceMembership:
        if new_role not in {SpaceRole.OWNER, SpaceRole.EDITOR, SpaceRole.VIEWER}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "VALIDATION_ERROR", "message": "Invalid role."},
            )
        space, _ = await self.permissions.require_space_access(
            space_id, actor.id, SpaceRole.OWNER
        )
        membership = await self.permissions.get_space_membership(space_id, member_user_id)
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "MEMBER_NOT_FOUND", "message": "Member not found."},
            )
        if membership.role == SpaceRole.OWNER and new_role != SpaceRole.OWNER:
            if await self.permissions.count_active_space_owners(space_id) <= 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "SPACE_REQUIRES_OWNER",
                        "message": "Space phải có ít nhất một Owner.",
                    },
                )
        old = membership.role
        membership.role = new_role
        action = (
            AuditAction.ADD_SPACE_OWNER
            if new_role == SpaceRole.OWNER
            else AuditAction.CHANGE_SPACE_ROLE
        )
        await self.audit.log(
            action=action,
            resource_type="space_membership",
            actor_user_id=actor.id,
            workspace_id=space.workspace_id,
            resource_id=membership.id,
            metadata={"from": old, "to": new_role, "user_id": str(member_user_id)},
        )
        await self.db.commit()
        await self.db.refresh(membership)
        return membership

    async def remove_member(self, actor: User, space_id: UUID, member_user_id: UUID) -> None:
        space, _ = await self.permissions.require_space_access(
            space_id, actor.id, SpaceRole.OWNER
        )
        membership = await self.permissions.get_space_membership(space_id, member_user_id)
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "MEMBER_NOT_FOUND", "message": "Member not found."},
            )
        if membership.role == SpaceRole.OWNER:
            if await self.permissions.count_active_space_owners(space_id) <= 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "SPACE_REQUIRES_OWNER",
                        "message": "Space phải có ít nhất một Owner.",
                    },
                )
        membership.revoked_at = datetime.now(UTC)
        await self.audit.log(
            action=AuditAction.REMOVE_SPACE_MEMBER,
            resource_type="space_membership",
            actor_user_id=actor.id,
            workspace_id=space.workspace_id,
            resource_id=membership.id,
            metadata={"user_id": str(member_user_id)},
        )
        await self.db.commit()
