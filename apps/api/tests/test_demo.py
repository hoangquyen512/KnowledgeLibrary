import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_auth_status(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "google_configured" in data
    assert isinstance(data["google_configured"], bool)


@pytest.mark.asyncio
async def test_demo_login_removed(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/demo/login", follow_redirects=False)
    assert resp.status_code == 404
