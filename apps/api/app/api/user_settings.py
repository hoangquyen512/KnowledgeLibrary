from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_csrf
from app.core.database import get_db
from app.models.user import User
from app.schemas.workspace import UserSettingsResponse, UserSettingsUpdate
from app.settings.service import SettingsService

router = APIRouter(tags=["settings"])


@router.get("/me/settings", response_model=UserSettingsResponse)
async def get_my_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserSettingsResponse:
    settings = await SettingsService(db).get_or_create(user)
    return UserSettingsResponse(
        theme=settings.theme,
        locale=settings.locale,
        default_model=settings.default_model,
    )


@router.patch("/me/settings", response_model=UserSettingsResponse)
async def patch_my_settings(
    body: UserSettingsUpdate,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> UserSettingsResponse:
    service = SettingsService(db)
    settings = await service.get_or_create(user)
    if body.theme is not None:
        settings = await service.update_theme(user, body.theme)
    if body.locale is not None:
        settings.locale = body.locale[:16]
        await db.commit()
        await db.refresh(settings)
    return UserSettingsResponse(
        theme=settings.theme,
        locale=settings.locale,
        default_model=settings.default_model,
    )
