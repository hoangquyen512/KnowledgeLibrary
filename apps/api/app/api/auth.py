from __future__ import annotations

from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_csrf
from app.auth.session import create_session_token, new_oauth_state
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserOut
from app.users.service import UserService

router = APIRouter(tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
OAUTH_STATE_COOKIE = "kl_oauth_state"
OAUTH_NEXT_COOKIE = "kl_oauth_next"


def _safe_next_path(next_path: str | None) -> str:
    if not next_path:
        return "/app"
    if not next_path.startswith("/") or next_path.startswith("//"):
        return "/app"
    return next_path


def _oauth_configured() -> bool:
    return settings.google_oauth_configured


def _set_session_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    common = {
        "httponly": True,
        "secure": settings.session_cookie_secure,
        "samesite": settings.session_cookie_samesite,
        "max_age": settings.session_ttl_seconds,
        "path": "/",
    }
    response.set_cookie(settings.session_cookie_name, session_token, **common)
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        max_age=settings.session_ttl_seconds,
        path="/",
    )


@router.get("/auth/status")
async def auth_status() -> dict[str, bool]:
    return {"google_configured": settings.google_oauth_configured}


@router.get("/auth/google/login")
async def google_login(request: Request, next: str | None = None) -> RedirectResponse:
    if not _oauth_configured():
        return RedirectResponse(
            f"{settings.app_url}/login?error=oauth_not_configured",
            status_code=status.HTTP_302_FOUND,
        )
    state = new_oauth_state()
    client = AsyncOAuth2Client(
        client_id=settings.google_client_id,
        redirect_uri=settings.google_redirect_uri,
        scope="openid email profile",
    )
    uri, _ = client.create_authorization_url(
        GOOGLE_AUTH_URL,
        state=state,
        access_type="online",
        prompt="select_account",
    )
    response = RedirectResponse(url=uri, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=600,
        path="/",
    )
    response.set_cookie(
        OAUTH_NEXT_COOKIE,
        _safe_next_path(next),
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=600,
        path="/",
    )
    return response


@router.get("/auth/google/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    if error:
        return RedirectResponse(f"{settings.app_url}/login?error=oauth_denied")
    if not code or not state:
        return RedirectResponse(f"{settings.app_url}/login?error=oauth_invalid")
    cookie_state = request.cookies.get(OAUTH_STATE_COOKIE)
    if not cookie_state or cookie_state != state:
        return RedirectResponse(f"{settings.app_url}/login?error=oauth_state")

    if not _oauth_configured():
        return RedirectResponse(f"{settings.app_url}/login?error=oauth_not_configured")

    client = AsyncOAuth2Client(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=settings.google_redirect_uri,
    )
    try:
        await client.fetch_token(
            GOOGLE_TOKEN_URL,
            code=code,
            grant_type="authorization_code",
        )
        resp = await client.get(GOOGLE_USERINFO_URL)
        resp.raise_for_status()
        info = resp.json()
    except Exception:
        return RedirectResponse(f"{settings.app_url}/login?error=oauth_token")

    google_sub = info.get("sub")
    email = info.get("email")
    if not google_sub or not email:
        return RedirectResponse(f"{settings.app_url}/login?error=oauth_profile")

    service = UserService(db)
    try:
        user = await service.upsert_from_google(
            google_sub=google_sub,
            email=email,
            email_verified=bool(info.get("email_verified")),
            display_name=info.get("name"),
            avatar_url=info.get("picture"),
        )
        UserService.assert_active(user)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_403_FORBIDDEN:
            return RedirectResponse(f"{settings.app_url}/login?error=account_suspended")
        raise

    session_token, csrf_token = create_session_token(user.id)
    next_path = _safe_next_path(request.cookies.get(OAUTH_NEXT_COOKIE))
    response = RedirectResponse(
        f"{settings.app_url}{next_path}", status_code=status.HTTP_302_FOUND
    )
    _set_session_cookies(response, session_token, csrf_token)
    response.delete_cookie(OAUTH_STATE_COOKIE, path="/")
    response.delete_cookie(OAUTH_NEXT_COOKIE, path="/")
    return response


@router.post("/auth/logout")
async def logout(
    response: Response,
    _user: User = Depends(require_csrf),
) -> dict[str, str]:
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
