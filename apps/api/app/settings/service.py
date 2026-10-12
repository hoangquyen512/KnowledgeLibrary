from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService
from app.models.audit import AuditAction
from app.models.user import User, UserSettings

ALLOWED_THEMES = {"LIGHT", "DARK", "SYSTEM"}


class SettingsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.audit = AuditService(db)

    async def get_or_create(self, user: User) -> UserSettings:
        result = await self.db.execute(select(UserSettings).where(UserSettings.user_id == user.id))
        settings = result.scalar_one_or_none()
        if settings is None:
            settings = UserSettings(user_id=user.id, theme="SYSTEM")
            self.db.add(settings)
            await self.db.commit()
            await self.db.refresh(settings)
        else:
            # Normalize legacy lowercase values on read
            if settings.theme and settings.theme.upper() in ALLOWED_THEMES:
                if settings.theme != settings.theme.upper():
                    settings.theme = settings.theme.upper()
                    await self.db.commit()
                    await self.db.refresh(settings)
        return settings

    async def update_theme(self, user: User, theme: str) -> UserSettings:
        normalized = theme.upper()
        if normalized not in ALLOWED_THEMES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": "theme must be LIGHT, DARK, or SYSTEM.",
                },
            )
        settings = await self.get_or_create(user)
        settings.theme = normalized
        await self.audit.log(
            action=AuditAction.CHANGE_THEME,
            resource_type="user_settings",
            actor_user_id=user.id,
            resource_id=settings.id,
            metadata={"theme": normalized},
        )
        await self.db.commit()
        await self.db.refresh(settings)
        return settings
