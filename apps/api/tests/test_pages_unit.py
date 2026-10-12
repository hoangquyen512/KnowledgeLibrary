"""Unit tests for PageService capabilities and hierarchy helpers (no DB)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.models.document import DocumentOrigin, DocumentStatus
from app.models.space import SpaceRole
from app.pages.service import (
    PageService,
    build_search_snippet,
    classify_search_match,
    plain_text_from_html,
)
from app.schemas.page import PageCreate


def _page(**kwargs):
    base = {
        "id": uuid4(),
        "origin": DocumentOrigin.LOCAL,
        "status": DocumentStatus.READY,
        "archived_at": None,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_local_editor_can_edit() -> None:
    svc = PageService(db=None)  # type: ignore[arg-type]
    caps = svc.capabilities(_page(), SpaceRole.EDITOR)
    assert caps.can_view
    assert caps.can_edit
    assert caps.can_move
    assert caps.can_create_child
    assert not caps.can_archive
    assert not caps.can_delete
    assert not caps.can_sync


def test_confluence_page_read_only_content() -> None:
    svc = PageService(db=None)  # type: ignore[arg-type]
    caps = svc.capabilities(
        _page(origin=DocumentOrigin.CONFLUENCE),
        SpaceRole.EDITOR,
    )
    assert caps.can_view
    assert not caps.can_edit
    assert caps.can_move
    assert caps.can_sync
    assert caps.can_create_child


def test_viewer_limited() -> None:
    svc = PageService(db=None)  # type: ignore[arg-type]
    caps = svc.capabilities(_page(), SpaceRole.VIEWER)
    assert caps.can_view
    assert not caps.can_edit
    assert not caps.can_move
    assert not caps.can_archive
    assert not caps.can_delete
    assert not caps.can_create_child


def test_owner_can_archive_delete() -> None:
    svc = PageService(db=None)  # type: ignore[arg-type]
    caps = svc.capabilities(_page(), SpaceRole.OWNER)
    assert caps.can_edit
    assert caps.can_archive
    assert caps.can_delete


def test_archived_blocks_edit_move() -> None:
    svc = PageService(db=None)  # type: ignore[arg-type]
    caps = svc.capabilities(
        _page(status=DocumentStatus.ARCHIVED, archived_at=object()),
        SpaceRole.OWNER,
    )
    assert not caps.can_edit
    assert not caps.can_move
    assert not caps.can_create_child


def test_plain_text_strips_tags() -> None:
    assert plain_text_from_html("<p>Hello <b>world</b></p>") == "Hello world"


def test_build_search_snippet_around_match() -> None:
    html = "<p>" + ("x" * 80) + "invoice error" + ("y" * 80) + "</p>"
    snippet = build_search_snippet(html, "invoice", radius=20)
    assert snippet is not None
    assert "invoice" in snippet.lower()
    assert snippet.startswith("…")
    assert snippet.endswith("…")


def test_classify_prefers_title_match() -> None:
    page = _page(title="Invoice Guide", normalized_content="<p>Other text</p>", raw_content=None)
    field, snippet = classify_search_match(page, "invoice")
    assert field == "title"
    assert snippet is None


def test_classify_content_match_returns_snippet() -> None:
    page = _page(
        title="Backlog",
        normalized_content="<p>Vui lòng chọn các hóa đơn có cùng bên bán.</p>",
        raw_content=None,
    )
    field, snippet = classify_search_match(page, "hóa đơn")
    assert field == "content"
    assert snippet is not None
    assert "hóa đơn" in snippet


def test_page_create_accepts_source_id() -> None:
    sid = uuid4()
    body = PageCreate(title="Hello", source_id=sid)
    assert body.source_id == sid
    assert PageCreate(title="Root").source_id is None
