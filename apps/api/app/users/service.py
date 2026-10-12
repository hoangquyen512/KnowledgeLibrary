from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.user import User, UserSettings, UserStatus

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self.db.execute(
            select(User).options(selectinload(User.settings)).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_google_sub(self, google_sub: str) -> User | None:
        result = await self.db.execute(select(User).where(User.google_sub == google_sub))
        return result.scalar_one_or_none()

    async def upsert_from_google(
        self,
        *,
        google_sub: str,
        email: str,
        email_verified: bool,
        display_name: str | None,
        avatar_url: str | None,
    ) -> User:
        user = await self.get_by_google_sub(google_sub)
        now = datetime.now(UTC)
        if user is None:
            user = User(
                google_sub=google_sub,
                email=email.lower(),
                email_verified=email_verified,
                display_name=display_name,
                avatar_url=avatar_url,
                status=UserStatus.ACTIVE,
                is_super_admin=self._email_is_seed_super_admin(email),
                last_login_at=now,
            )
            self.db.add(user)
            await self.db.flush()
            self.db.add(UserSettings(user_id=user.id))
        else:
            if user.status == UserStatus.DELETED:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "ACCOUNT_DELETED",
                        "message": "This account has been deleted.",
                    },
                )
            user.email = email.lower()
            user.email_verified = email_verified
            user.display_name = display_name
            user.avatar_url = avatar_url
            user.last_login_at = now
            if self._email_is_seed_super_admin(email):
                user.is_super_admin = True
        await self._commit_with_sqlite_retry()
        await self.db.refresh(user)
        return user

    async def _commit_with_sqlite_retry(self, *, attempts: int = 5) -> None:
        for attempt in range(attempts):
            try:
                await self.db.commit()
                return
            except OperationalError as exc:
                if "database is locked" not in str(exc).lower() or attempt >= attempts - 1:
                    raise
                logger.warning("SQLite locked during commit; retry %s/%s", attempt + 1, attempts)
                await self.db.rollback()
                await asyncio.sleep(0.15 * (attempt + 1))

    @staticmethod
    def _email_is_seed_super_admin(email: str) -> bool:
        seed = (settings.seed_super_admin_email or "").strip()
        return bool(seed and email.lower() == seed.lower())

    @staticmethod
    def assert_active(user: User) -> None:
        if user.status == UserStatus.SUSPENDED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "ACCOUNT_SUSPENDED",
                    "message": "Your account has been suspended.",
                },
            )
        if user.status == UserStatus.DELETED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "ACCOUNT_DELETED",
                    "message": "This account has been deleted.",
                },
            )
