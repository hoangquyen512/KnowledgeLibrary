from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import safe_load_session_token
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.users.service import UserService


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHENTICATED", "message": "Authentication required."},
        )
    payload = safe_load_session_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "SESSION_INVALID", "message": "Session is invalid or expired."},
        )
    user = await UserService(db).get_by_id(UUID(payload.user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHENTICATED", "message": "Authentication required."},
        )
    UserService.assert_active(user)
    request.state.csrf_token = payload.csrf_token
    return user


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    payload = safe_load_session_token(token)
    if payload is None:
        return None
    user = await UserService(db).get_by_id(UUID(payload.user_id))
    if user is None:
        return None
    if user.status != "ACTIVE":
        return None
    request.state.csrf_token = payload.csrf_token
    return user


async def require_super_admin(
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ADMIN_REQUIRED", "message": "Super Admin access required."},
        )
    return user


def require_csrf(request: Request, user: User = Depends(get_current_user)) -> User:
    """Validate CSRF header for cookie-authenticated mutations."""
    header = request.headers.get("x-csrf-token")
    expected = getattr(request.state, "csrf_token", None)
    if not header or not expected or header != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "CSRF_FAILED", "message": "CSRF validation failed."},
        )
    return user
