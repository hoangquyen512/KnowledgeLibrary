from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_csrf
from app.core.database import get_db
from app.ingestion.normalize import (
    replace_confluence_images,
    replace_drawio_macros_with_images,
)
from app.models.document import Attachment
from app.models.user import User
from app.pages.service import PageService, classify_search_match
from app.schemas.page import (
    PageCreate,
    PageDetailOut,
    PageMove,
    PageOut,
    PagePathItem,
    PageSearchHit,
    PageTreeNodeOut,
    PageUpdate,
)

router = APIRouter(tags=["pages"])


async def _attachment_filename_map(db: AsyncSession, document_id: UUID) -> dict[str, str]:
    result = await db.execute(select(Attachment).where(Attachment.document_id == document_id))
    fmap: dict[str, str] = {}
    for att in result.scalars().all():
        fmap[att.filename] = str(att.id)
        fmap[att.filename.lower()] = str(att.id)
    return fmap


async def _page_out(svc: PageService, user: User, page, role: str, *, detail: bool = False):
    child_count = await svc._child_count(page.id, page.space_id, source_id=page.source_id)
    ancs = await svc.ancestors(page)
    caps = svc.capabilities(page, role)
    starred = await svc.is_starred(user, page.id)
    base = {
        "id": page.id,
        "workspace_id": page.workspace_id,
        "space_id": page.space_id,
        "source_id": page.source_id,
        "parent_id": page.parent_id,
        "title": page.title,
        "status": page.status,
        "origin": page.origin,
        "position": page.position,
        "depth": page.depth,
        "external_id": page.external_id,
        "external_version": page.external_version,
        "external_url": page.external_url,
        "has_children": child_count > 0,
        "child_count": child_count,
        "is_starred": starred,
        "created_at": page.created_at,
        "updated_at": page.updated_at,
        "permissions": caps,
        "ancestors": [PagePathItem(id=a.id, title=a.title) for a in ancs],
    }
    if detail:
        raw = page.raw_content or ""
        needs_images = "ac:image" in raw.lower() or "ri:attachment" in raw.lower()
        needs_drawio = (
            "drawio" in raw.lower()
            and "structured-macro" in raw.lower()
            and "kl-drawio-preview" not in raw
        )
        if needs_images or needs_drawio:
            fmap = await _attachment_filename_map(svc.db, page.id)
            if fmap:
                if needs_images:
                    raw = replace_confluence_images(raw, filename_to_attachment_id=fmap)
                if needs_drawio:
                    raw = replace_drawio_macros_with_images(raw, filename_to_attachment_id=fmap)
        return PageDetailOut(
            **base,
            raw_content=raw,
            normalized_content=page.normalized_content,
        )
    return PageOut(**base)


@router.get("/spaces/{space_id}/pages/tree", response_model=list[PageTreeNodeOut])
async def page_tree(
    space_id: UUID,
    parent_id: UUID | None = None,
    source_id: UUID | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PageTreeNodeOut]:
    svc = PageService(db)
    nodes = await svc.tree(user, space_id, parent_id=parent_id, source_id=source_id)
    out: list[PageTreeNodeOut] = []
    for n in nodes:
        cc = await svc._child_count(n.id, space_id, source_id=source_id)
        out.append(
            PageTreeNodeOut(
                id=n.id,
                title=n.title,
                has_children=cc > 0,
                child_count=cc,
                status=n.status,
                origin=n.origin,
                parent_id=n.parent_id,
                position=n.position,
                depth=n.depth,
            )
        )
    return out


@router.get("/spaces/{space_id}/pages/search", response_model=list[PageSearchHit])
async def search_pages(
    space_id: UUID,
    q: str = Query(min_length=1),
    source_id: UUID | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PageSearchHit]:
    svc = PageService(db)
    rows = await svc.search(user, space_id, q, source_id=source_id)
    hits: list[PageSearchHit] = []
    for row in rows:
        path = await svc.path_titles(row)
        match_field, snippet = classify_search_match(row, q)
        hits.append(
            PageSearchHit(
                id=row.id,
                title=row.title,
                path=path,
                status=row.status,
                origin=row.origin,
                match_field=match_field,
                snippet=snippet,
            )
        )
    return hits


@router.get("/spaces/{space_id}/pages/archived", response_model=list[PageTreeNodeOut])
async def archived_pages(
    space_id: UUID,
    source_id: UUID | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PageTreeNodeOut]:
    svc = PageService(db)
    rows = await svc.list_archived(user, space_id, source_id=source_id)
    return [
        PageTreeNodeOut(
            id=r.id,
            title=r.title,
            has_children=False,
            child_count=0,
            status=r.status,
            origin=r.origin,
            parent_id=r.parent_id,
            position=r.position,
            depth=r.depth,
        )
        for r in rows
    ]


@router.post("/spaces/{space_id}/pages", response_model=PageDetailOut, status_code=201)
async def create_page(
    space_id: UUID,
    body: PageCreate,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> PageDetailOut:
    svc = PageService(db)
    page = await svc.create(
        user,
        space_id,
        title=body.title,
        parent_id=body.parent_id,
        content=body.content,
        source_id=body.source_id,
    )
    _, role = await svc.require_page(user, page.id)
    return await _page_out(svc, user, page, role, detail=True)  # type: ignore[return-value]


@router.get("/pages/{page_id}", response_model=PageDetailOut)
async def get_page(
    page_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PageDetailOut:
    svc = PageService(db)
    page, role = await svc.require_page(user, page_id)
    out = await _page_out(svc, user, page, role, detail=True)
    # Touch after building response payload so rewrite work isn't delayed by recent write.
    try:
        await svc.touch_recent(user, page)
    except Exception:  # noqa: BLE001
        pass
    return out  # type: ignore[return-value]


@router.get("/pages/{page_id}/children", response_model=list[PageTreeNodeOut])
async def page_children(
    page_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PageTreeNodeOut]:
    svc = PageService(db)
    page, _ = await svc.require_page(user, page_id)
    return await page_tree(
        page.space_id,
        parent_id=page.id,
        source_id=page.source_id,
        user=user,
        db=db,
    )


@router.get("/pages/{page_id}/ancestors", response_model=list[PagePathItem])
async def page_ancestors(
    page_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PagePathItem]:
    svc = PageService(db)
    page, _ = await svc.require_page(user, page_id)
    ancs = await svc.ancestors(page)
    return [PagePathItem(id=a.id, title=a.title) for a in ancs]


@router.patch("/pages/{page_id}", response_model=PageDetailOut)
async def update_page(
    page_id: UUID,
    body: PageUpdate,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> PageDetailOut:
    svc = PageService(db)
    page = await svc.update(user, page_id, title=body.title, content=body.content)
    if body.parent_id is not None or (body.model_dump(exclude_unset=True).get("parent_id", "x") != "x"):
        # parent_id handled via move endpoint primarily
        pass
    _, role = await svc.require_page(user, page.id)
    return await _page_out(svc, user, page, role, detail=True)  # type: ignore[return-value]


@router.post("/pages/{page_id}/move", response_model=PageOut)
async def move_page(
    page_id: UUID,
    body: PageMove,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> PageOut:
    svc = PageService(db)
    page = await svc.move(user, page_id, parent_id=body.parent_id, position=body.position)
    _, role = await svc.require_page(user, page.id)
    return await _page_out(svc, user, page, role)  # type: ignore[return-value]


@router.post("/pages/{page_id}/duplicate", response_model=PageDetailOut, status_code=201)
async def duplicate_page(
    page_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> PageDetailOut:
    svc = PageService(db)
    page = await svc.duplicate(user, page_id)
    _, role = await svc.require_page(user, page.id)
    return await _page_out(svc, user, page, role, detail=True)  # type: ignore[return-value]


@router.post("/pages/{page_id}/archive", response_model=PageOut)
async def archive_page(
    page_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> PageOut:
    svc = PageService(db)
    page = await svc.archive(user, page_id)
    _, role = await svc.require_page(user, page.id)
    return await _page_out(svc, user, page, role)  # type: ignore[return-value]


@router.post("/pages/{page_id}/restore", response_model=PageOut)
async def restore_page(
    page_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> PageOut:
    svc = PageService(db)
    page = await svc.restore(user, page_id)
    _, role = await svc.require_page(user, page.id)
    return await _page_out(svc, user, page, role)  # type: ignore[return-value]


@router.delete("/pages/{page_id}", status_code=204, response_class=Response)
async def delete_page(
    page_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await PageService(db).soft_delete(user, page_id)
    return Response(status_code=204)


@router.post("/pages/{page_id}/star", status_code=204, response_class=Response)
async def star_page(
    page_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await PageService(db).star(user, page_id)
    return Response(status_code=204)


@router.delete("/pages/{page_id}/star", status_code=204, response_class=Response)
async def unstar_page(
    page_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await PageService(db).unstar(user, page_id)
    return Response(status_code=204)
