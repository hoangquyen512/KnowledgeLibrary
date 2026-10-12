"""Unit tests for Confluence page-list fallbacks."""
from __future__ import annotations

import pytest

from app.confluence.client import ConfluenceClient, ConfluenceClientError


@pytest.mark.asyncio
async def test_list_pages_falls_back_from_space_content_404(monkeypatch: pytest.MonkeyPatch) -> None:
    client = ConfluenceClient(
        base_url="https://example.invalid",
        auth_type="SESSION_COOKIE",
        username=None,
        secret="JSESSIONID=abc",
    )
    calls: list[str] = []

    async def fake_get(path: str, params: dict | None = None):
        calls.append(path)
        if path.endswith("/content/page"):
            raise ConfluenceClientError("missing", status_code=404, code="SOURCE_NOT_FOUND")
        if path == "/rest/api/content":
            return {
                "results": [{"id": "1", "title": "Home", "type": "page", "_links": {}}],
                "start": 0,
                "limit": 25,
                "size": 1,
            }
        raise AssertionError(path)

    monkeypatch.setattr(client, "_get", fake_get)
    out = await client.list_pages(space_key="EDUS")
    assert out["size"] == 1
    assert out["items"][0]["id"] == "1"
    assert calls[0].endswith("/content/page")


@pytest.mark.asyncio
async def test_list_all_pages_skips_get_space_and_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    client = ConfluenceClient(
        base_url="https://example.invalid",
        auth_type="SESSION_COOKIE",
        username=None,
        secret="JSESSIONID=abc",
    )

    async def fake_list_pages(*, space_key: str, start: int = 0, limit: int = 25):
        assert space_key == "EPV"
        return {
            "items": [{"id": "9", "title": "Home", "type": "page", "url": None, "version": "1"}],
            "start": 0,
            "limit": 25,
            "size": 1,
        }

    async def boom_get_space(_key: str):
        raise AssertionError("get_space should not gate listing")

    monkeypatch.setattr(client, "list_pages", fake_list_pages)
    monkeypatch.setattr(client, "get_space", boom_get_space)
    out = await client.list_all_pages_in_space("EPV")
    assert len(out) == 1
    assert out[0]["id"] == "9"


@pytest.mark.asyncio
async def test_list_all_pages_falls_back_to_space_id(monkeypatch: pytest.MonkeyPatch) -> None:
    client = ConfluenceClient(
        base_url="https://example.invalid",
        auth_type="SESSION_COOKIE",
        username=None,
        secret="JSESSIONID=abc",
    )
    tried: list[str] = []

    async def fake_list_pages(*, space_key: str, start: int = 0, limit: int = 25):
        tried.append(space_key)
        if space_key == "EPV":
            raise ConfluenceClientError("missing", status_code=404, code="SOURCE_NOT_FOUND")
        return {
            "items": [{"id": "2", "title": "A", "type": "page", "url": None, "version": "1"}],
            "start": 0,
            "limit": 25,
            "size": 1,
        }

    monkeypatch.setattr(client, "list_pages", fake_list_pages)
    out = await client.list_all_pages_in_space("EPV", space_id="2260995")
    assert tried == ["EPV", "2260995"]
    assert out[0]["id"] == "2"
