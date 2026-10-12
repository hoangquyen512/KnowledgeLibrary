from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def log(
        self,
        *,
        action: str,
        resource_type: str,
        actor_user_id: UUID | None = None,
        workspace_id: UUID | None = None,
        resource_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            action=action,
            resource_type=resource_type,
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            resource_id=resource_id,
            metadata_json_sanitized=metadata,
        )
        self.db.add(entry)
        await self.db.flush()
        return entry
