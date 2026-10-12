from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import Conversation
from app.models.audit import AuditLog
from app.models.document import Document, DocumentStatus, DocumentType
from app.models.source import Source
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership, WorkspaceStatus
from app.permissions.service import WORKSPACE_OWNED_LIMIT, PermissionService


class DashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.permissions = PermissionService(db)

    async def summary(self, user: User) -> dict:
        from app.models.space import Space, SpaceMembership, SpaceStatus

        owned = await self.permissions.count_owned_workspaces(user.id)
        # Spaces the user can access via workspace membership or space membership
        ws_ids_result = await self.db.execute(
            select(WorkspaceMembership.workspace_id).where(
                WorkspaceMembership.user_id == user.id,
                WorkspaceMembership.revoked_at.is_(None),
            )
        )
        ws_ids = [row[0] for row in ws_ids_result.all()]
        space_count = 0
        if ws_ids:
            space_count = int(
                (
                    await self.db.execute(
                        select(func.count())
                        .select_from(Space)
                        .where(
                            Space.workspace_id.in_(ws_ids),
                            Space.deleted_at.is_(None),
                            Space.status != SpaceStatus.DELETED,
                        )
                    )
                ).scalar_one()
            )
        # Plus isolated shared spaces (no workspace membership)
        isolated_filters = [
            SpaceMembership.user_id == user.id,
            SpaceMembership.revoked_at.is_(None),
            Space.deleted_at.is_(None),
            Space.status != SpaceStatus.DELETED,
        ]
        if ws_ids:
            isolated_filters.append(Space.workspace_id.notin_(ws_ids))
        isolated = int(
            (
                await self.db.execute(
                    select(func.count())
                    .select_from(Space)
                    .join(
                        SpaceMembership,
                        SpaceMembership.space_id == Space.id,
                    )
                    .where(*isolated_filters)
                )
            ).scalar_one()
        )
        space_ids = await self._accessible_space_ids(user, ws_ids)
        source_count = 0
        document_count = 0
        if space_ids:
            source_count = int(
                (
                    await self.db.execute(
                        select(func.count())
                        .select_from(Source)
                        .where(
                            Source.space_id.in_(space_ids),
                            Source.deleted_at.is_(None),
                        )
                    )
                ).scalar_one()
            )
            document_count = int(
                (
                    await self.db.execute(
                        select(func.count())
                        .select_from(Document)
                        .where(
                            Document.space_id.in_(space_ids),
                            Document.document_type == DocumentType.PAGE,
                            Document.deleted_at.is_(None),
                            Document.status != DocumentStatus.DELETED,
                        )
                    )
                ).scalar_one()
            )
        month_start = datetime.now(UTC).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        conversation_count_month = int(
            (
                await self.db.execute(
                    select(func.count())
                    .select_from(Conversation)
                    .where(
                        Conversation.user_id == user.id,
                        Conversation.created_at >= month_start,
                    )
                )
            ).scalar_one()
        )
        return {
            "owned_workspace_count": owned,
            "workspace_limit": WORKSPACE_OWNED_LIMIT,
            "space_count": space_count + isolated,
            "source_count": source_count,
            "document_count": document_count,
            "conversation_count_month": conversation_count_month,
        }

    async def _accessible_space_ids(self, user: User, ws_ids: list[UUID]) -> list[UUID]:
        from app.models.space import Space, SpaceMembership, SpaceStatus

        ids: set[UUID] = set()
        if ws_ids:
            result = await self.db.execute(
                select(Space.id).where(
                    Space.workspace_id.in_(ws_ids),
                    Space.deleted_at.is_(None),
                    Space.status != SpaceStatus.DELETED,
                )
            )
            ids.update(result.scalars().all())
        isolated_filters = [
            SpaceMembership.user_id == user.id,
            SpaceMembership.revoked_at.is_(None),
            Space.deleted_at.is_(None),
            Space.status != SpaceStatus.DELETED,
        ]
        if ws_ids:
            isolated_filters.append(Space.workspace_id.notin_(ws_ids))
        result = await self.db.execute(
            select(Space.id)
            .join(SpaceMembership, SpaceMembership.space_id == Space.id)
            .where(*isolated_filters)
        )
        ids.update(result.scalars().all())
        return list(ids)

    async def recent_workspaces(
        self, user: User, *, limit: int = 5
    ) -> list[tuple[Workspace, WorkspaceMembership]]:
        result = await self.db.execute(
            select(Workspace, WorkspaceMembership)
            .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
            .where(
                WorkspaceMembership.user_id == user.id,
                WorkspaceMembership.revoked_at.is_(None),
                Workspace.deleted_at.is_(None),
                Workspace.status != WorkspaceStatus.DELETED,
            )
            .order_by(Workspace.updated_at.desc())
            .limit(limit)
        )
        return list(result.all())

    async def recent_activity(self, user: User, *, limit: int = 10) -> list[AuditLog]:
        # Activity in workspaces the user can access
        ws_ids_result = await self.db.execute(
            select(WorkspaceMembership.workspace_id).where(
                WorkspaceMembership.user_id == user.id,
                WorkspaceMembership.revoked_at.is_(None),
            )
        )
        ws_ids = [row[0] for row in ws_ids_result.all()]
        if not ws_ids:
            # Still include theme changes by this user
            result = await self.db.execute(
                select(AuditLog)
                .where(AuditLog.actor_user_id == user.id)
                .order_by(AuditLog.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

        result = await self.db.execute(
            select(AuditLog)
            .where(
                (AuditLog.workspace_id.in_(ws_ids))
                | ((AuditLog.actor_user_id == user.id) & (AuditLog.workspace_id.is_(None)))
            )
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def shared_workspaces(
        self, user: User
    ) -> list[tuple[Workspace, WorkspaceMembership, User | None]]:
        result = await self.db.execute(
            select(Workspace, WorkspaceMembership)
            .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
            .where(
                WorkspaceMembership.user_id == user.id,
                WorkspaceMembership.revoked_at.is_(None),
                Workspace.created_by_user_id != user.id,
                Workspace.deleted_at.is_(None),
                Workspace.status != WorkspaceStatus.DELETED,
            )
            .order_by(Workspace.updated_at.desc())
        )
        rows = list(result.all())
        out: list[tuple[Workspace, WorkspaceMembership, User | None]] = []
        for workspace, membership in rows:
            owner_result = await self.db.execute(
                select(User).where(User.id == workspace.created_by_user_id)
            )
            out.append((workspace, membership, owner_result.scalar_one_or_none()))
        return out

    async def workspace_names(self, ids: list[UUID]) -> dict[UUID, str]:
        if not ids:
            return {}
        result = await self.db.execute(select(Workspace).where(Workspace.id.in_(ids)))
        return {w.id: w.name for w in result.scalars().all()}
