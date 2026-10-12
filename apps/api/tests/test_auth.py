import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.security import decrypt_secret, encrypt_secret, mask_secret
from app.models.user import User
from tests.conftest import auth_cookies


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/me")
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.asyncio
async def test_me_returns_user(db_client: AsyncClient, active_user: User) -> None:
    cookies = auth_cookies(active_user)
    resp = await db_client.get("/api/v1/me", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == active_user.email
    assert data["id"] == str(active_user.id)
    assert "encrypted_secret" not in data


@pytest.mark.asyncio
async def test_suspended_user_blocked(db_client: AsyncClient, suspended_user: User) -> None:
    cookies = auth_cookies(suspended_user)
    resp = await db_client.get("/api/v1/me", cookies=cookies)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ACCOUNT_SUSPENDED"


@pytest.mark.asyncio
async def test_logout_requires_csrf(db_client: AsyncClient, active_user: User) -> None:
    cookies = auth_cookies(active_user)
    resp = await db_client.post("/api/v1/auth/logout", cookies=cookies)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CSRF_FAILED"


@pytest.mark.asyncio
async def test_logout_ok(db_client: AsyncClient, active_user: User) -> None:
    cookies = auth_cookies(active_user)
    resp = await db_client.post(
        "/api/v1/auth/logout",
        cookies=cookies,
        headers={"X-CSRF-Token": cookies[settings.csrf_cookie_name]},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_google_login_unconfigured(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "google_client_id", "")
    monkeypatch.setattr(settings, "google_client_secret", "")
    resp = await client.get("/api/v1/auth/google/login", follow_redirects=False)
    assert resp.status_code == 302
    assert "oauth_not_configured" in resp.headers.get("location", "")


def test_encrypt_roundtrip() -> None:
    token = encrypt_secret("super-secret-key")
    assert decrypt_secret(token) == "super-secret-key"
    assert mask_secret("abcd1234XYZ").endswith("XYZ")
