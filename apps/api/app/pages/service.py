from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService
from app.models.audit import AuditAction
from app.models.document import (
    Document,
    DocumentOrigin,
    DocumentStatus,
    DocumentType,
    DocumentViewEvent,
    UserRecentPage,
    UserStarredPage,
)
from app.models.source import Source, SourceStatus, SourceType
from app.models.space import SpaceRole
from app.models.user import User
from app.permissions.service import PermissionService
from app.schemas.page import PagePermissions


ACTIVE_STATUSES = {DocumentStatus.READY, DocumentStatus.DRAFT, DocumentStatus.PENDING}
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def plain_text_from_html(value: str | None) -> str:
    if not value:
        return ""
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", value)).strip()


def build_search_snippet(text: str | None, term: str, *, radius: int = 72) -> str | None:
    plain = plain_text_from_html(text)
    needle = (term or "").strip()
    if not plain or not needle:
        return None
    idx = plain.lower().find(needle.lower())
    if idx < 0:
        return None
    start = max(0, idx - radius)
    end = min(len(plain), idx + len(needle) + radius)
    snippet = plain[start:end].strip()
    if start > 0:
        snippet = f"…{snippet}"
    if end < len(plain):
        snippet = f"{snippet}…"
    return snippet


def classify_search_match(page: Document, term: str) -> tuple[str, str | None]:
    needle = (term or "").strip().lower()
    if needle and needle in (page.title or "").lower():
        return "title", None
    content = page.normalized_content or page.raw_content
    snippet = build_search_snippet(content, term)
    if snippet:
        return "content", snippet
    # Fallback if LIKE matched but snippet extraction failed (e.g. odd whitespace).
    if content and needle in plain_text_from_html(content).lower():
        return "content", plain_text_from_html(content)[:140] or None
    return "title", None


class PageService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.permissions = PermissionService(db)
        self.audit = AuditService(db)

    async def require_page(
        self, user: User, page_id: UUID, minimum: str = SpaceRole.VIEWER
    ) -> tuple[Document, str]:
        result = await self.db.execute(
            select(Document).where(Document.id == page_id, Document.document_type == DocumentType.PAGE)
        )
        page = result.scalar_one_or_none()
        if page is None or page.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PAGE_NOT_FOUND", "message": "Page not found."},
            )
        _space, role = await self.permissions.require_space_access(
            page.space_id, user.id, minimum
        )
        return page, role

    async def require_source(self, space_id: UUID, source_id: UUID) -> Source:
        result = await self.db.execute(
            select(Source).where(
                Source.id == source_id,
                Source.space_id == space_id,
                Source.deleted_at.is_(None),
            )
        )
        source = result.scalar_one_or_none()
        if source is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "SOURCE_NOT_FOUND", "message": "Source not found."},
            )
        return source

    def capabilities(self, page: Document, role: str) -> PagePermissions:
        is_owner = role == SpaceRole.OWNER
        is_editor = role in {SpaceRole.OWNER, SpaceRole.EDITOR}
        confluence = page.origin == DocumentOrigin.CONFLUENCE
        archived = page.status == DocumentStatus.ARCHIVED or page.archived_at is not None
        return PagePermissions(
            can_view=True,
            can_edit=is_editor and not confluence and not archived,
            can_move=is_editor and not archived,
            can_archive=is_owner and not archived,
            can_delete=is_owner,
            can_sync=is_editor and confluence,
            can_create_child=is_editor and not archived,
        )

    async def _child_count(
        self,
        parent_id: UUID | None,
        space_id: UUID,
        *,
        source_id: UUID | None = None,
    ) -> int:
        q = (
            select(func.count())
            .select_from(Document)
            .outerjoin(Source, Source.id == Document.source_id)
            .where(
                Document.space_id == space_id,
                Document.document_type == DocumentType.PAGE,
                Document.deleted_at.is_(None),
                Document.status.in_(ACTIVE_STATUSES),
                or_(Document.source_id.is_(None), Source.deleted_at.is_(None)),
            )
        )
        if source_id is not None:
            q = q.where(Document.source_id == source_id)
        if parent_id is None:
            q = q.where(Document.parent_id.is_(None))
        else:
            q = q.where(Document.parent_id == parent_id)
        return int((await self.db.execute(q)).scalar_one() or 0)

    async def tree(
        self,
        user: User,
        space_id: UUID,
        *,
        parent_id: UUID | None = None,
        source_id: UUID | None = None,
    ) -> list[Document]:
        await self.permissions.require_space_access(space_id, user.id, SpaceRole.VIEWER)
        if source_id is not None:
            await self.require_source(space_id, source_id)
        q = (
            select(Document)
            .outerjoin(Source, Source.id == Document.source_id)
            .where(
                Document.space_id == space_id,
                Document.document_type == DocumentType.PAGE,
                Document.deleted_at.is_(None),
                Document.status.in_(ACTIVE_STATUSES),
                or_(Document.source_id.is_(None), Source.deleted_at.is_(None)),
            )
            .order_by(Document.position.asc(), Document.title.asc())
        )
        if source_id is not None:
            q = q.where(Document.source_id == source_id)
        if parent_id is None:
            q = q.where(Document.parent_id.is_(None))
        else:
            # Ensure parent is in same space
            parent, _ = await self.require_page(user, parent_id, SpaceRole.VIEWER)
            if parent.space_id != space_id:
                raise HTTPException(status_code=404, detail={"code": "PAGE_NOT_FOUND", "message": "Page not found."})
            if source_id is not None and parent.source_id != source_id:
                raise HTTPException(status_code=404, detail={"code": "PAGE_NOT_FOUND", "message": "Page not found."})
            q = q.where(Document.parent_id == parent_id)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def search(
        self,
        user: User,
        space_id: UUID,
        q: str,
        *,
        limit: int = 30,
        source_id: UUID | None = None,
    ) -> list[Document]:
        await self.permissions.require_space_access(space_id, user.id, SpaceRole.VIEWER)
        if source_id is not None:
            await self.require_source(space_id, source_id)
        term = (q or "").strip()
        if len(term) < 2:
            return []
        # Escape LIKE wildcards so user input is matched literally (SQLite-friendly).
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        title_match = Document.title.like(pattern, escape="\\")
        content_match = or_(
            Document.normalized_content.like(pattern, escape="\\"),
            Document.raw_content.like(pattern, escape="\\"),
        )
        filters = [
            Document.space_id == space_id,
            Document.document_type == DocumentType.PAGE,
            Document.deleted_at.is_(None),
            Document.status.in_(ACTIVE_STATUSES),
            or_(title_match, content_match),
            or_(Document.source_id.is_(None), Source.deleted_at.is_(None)),
        ]
        if source_id is not None:
            filters.append(Document.source_id == source_id)
        result = await self.db.execute(
            select(Document)
            .outerjoin(Source, Source.id == Document.source_id)
            .where(*filters)
            .order_by(case((title_match, 0), else_=1), Document.title.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def ancestors(self, page: Document) -> list[Document]:
        chain: list[Document] = []
        current_id = page.parent_id
        seen: set[UUID] = set()
        while current_id and current_id not in seen:
            seen.add(current_id)
            result = await self.db.execute(select(Document).where(Document.id == current_id))
            parent = result.scalar_one_or_none()
            if parent is None:
                break
            chain.append(parent)
            current_id = parent.parent_id
        chain.reverse()
        return chain

    async def path_titles(self, page: Document) -> list[str]:
        ancs = await self.ancestors(page)
        return [a.title for a in ancs] + [page.title]

    async def touch_recent(self, user: User, page: Document) -> None:
        result = await self.db.execute(
            select(UserRecentPage).where(
                UserRecentPage.user_id == user.id, UserRecentPage.page_id == page.id
            )
        )
        row = result.scalar_one_or_none()
        now = datetime.now(UTC)
        if row is None:
            self.db.add(UserRecentPage(user_id=user.id, page_id=page.id, last_opened_at=now))
        else:
            row.last_opened_at = now
        self.db.add(DocumentViewEvent(document_id=page.id, user_id=user.id, created_at=now))
        await self.db.commit()

    async def is_starred(self, user: User, page_id: UUID) -> bool:
        result = await self.db.execute(
            select(UserStarredPage).where(
                UserStarredPage.user_id == user.id, UserStarredPage.page_id == page_id
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_or_create_local_source(self, space_id: UUID, user: User) -> Source:
        space, _ = await self.permissions.require_space_access(
            space_id, user.id, SpaceRole.EDITOR
        )
        result = await self.db.execute(
            select(Source).where(
                Source.space_id == space_id,
                Source.type == SourceType.LOCAL,
                Source.deleted_at.is_(None),
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        source = Source(
            id=uuid4(),
            workspace_id=space.workspace_id,
            space_id=space_id,
            type=SourceType.LOCAL,
            name="Local pages",
            status=SourceStatus.READY,
            connection_id=None,
            external_type=None,
            external_id=f"local-{space_id}",
            created_by_user_id=user.id,
        )
        self.db.add(source)
        await self.db.commit()
        await self.db.refresh(source)
        return source

    async def create(
        self,
        user: User,
        space_id: UUID,
        *,
        title: str,
        parent_id: UUID | None,
        content: str | None,
        source_id: UUID | None = None,
    ) -> Document:
        space, role = await self.permissions.require_space_access(
            space_id, user.id, SpaceRole.EDITOR
        )
        parent = None
        depth = 0
        if parent_id:
            parent, _ = await self.require_page(user, parent_id, SpaceRole.EDITOR)
            if parent.space_id != space_id:
                raise HTTPException(status_code=400, detail={"code": "INVALID_PARENT", "message": "Parent must be in the same Space."})
            depth = parent.depth + 1
            if source_id is not None and parent.source_id is not None and source_id != parent.source_id:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "SOURCE_MISMATCH",
                        "message": "source_id must match the parent page source.",
                    },
                )
            resolved_source_id = parent.source_id or source_id
            if resolved_source_id is None:
                source = await self.get_or_create_local_source(space_id, user)
                resolved_source_id = source.id
            else:
                await self.require_source(space_id, resolved_source_id)
        elif source_id is not None:
            await self.require_source(space_id, source_id)
            resolved_source_id = source_id
        else:
            source = await self.get_or_create_local_source(space_id, user)
            resolved_source_id = source.id
        pos = await self._child_count(parent_id, space_id, source_id=resolved_source_id)
        page = Document(
            id=uuid4(),
            workspace_id=space.workspace_id,
            space_id=space_id,
            source_id=resolved_source_id,
            parent_id=parent_id,
            external_id=f"local-{uuid4()}",
            document_type=DocumentType.PAGE,
            title=title.strip()[:255],
            status=DocumentStatus.READY,
            origin=DocumentOrigin.LOCAL,
            position=pos,
            depth=depth,
            raw_content=content or "",
            normalized_content=content or "",
            created_by_user_id=user.id,
        )
        self.db.add(page)
        await self.audit.log(
            action=AuditAction.CREATE_PAGE,
            resource_type="page",
            actor_user_id=user.id,
            workspace_id=space.workspace_id,
            resource_id=page.id,
            metadata={"title": page.title, "parent_id": str(parent_id) if parent_id else None},
        )
        await self.db.commit()
        await self.db.refresh(page)
        return page

    async def update(
        self,
        user: User,
        page_id: UUID,
        *,
        title: str | None = None,
        content: str | None = None,
    ) -> Document:
        page, role = await self.require_page(user, page_id, SpaceRole.EDITOR)
        caps = self.capabilities(page, role)
        if title is not None:
            page.title = title.strip()[:255]
            await self.audit.log(
                action=AuditAction.RENAME_PAGE,
                resource_type="page",
                actor_user_id=user.id,
                workspace_id=page.workspace_id,
                resource_id=page.id,
                metadata={"title": page.title},
            )
        if content is not None:
            if not caps.can_edit:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "PAGE_READ_ONLY",
                        "message": "Confluence pages are read-only. Open in Confluence to edit.",
                    },
                )
            page.raw_content = content
            page.normalized_content = content
            await self.audit.log(
                action=AuditAction.UPDATE_PAGE,
                resource_type="page",
                actor_user_id=user.id,
                workspace_id=page.workspace_id,
                resource_id=page.id,
                metadata={},
            )
        await self.db.commit()
        await self.db.refresh(page)
        return page

    async def move(
        self, user: User, page_id: UUID, *, parent_id: UUID | None, position: int | None
    ) -> Document:
        page, _ = await self.require_page(user, page_id, SpaceRole.EDITOR)
        if parent_id == page.id:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_MOVE", "message": "Cannot move a page under itself."},
            )
        new_depth = 0
        if parent_id:
            parent, _ = await self.require_page(user, parent_id, SpaceRole.EDITOR)
            if parent.space_id != page.space_id:
                raise HTTPException(
                    status_code=422,
                    detail={"code": "INVALID_MOVE", "message": "Parent must be in the same Space."},
                )
            # Prevent cycles
            cursor = parent
            seen = {page.id}
            while cursor:
                if cursor.id in seen:
                    raise HTTPException(
                        status_code=422,
                        detail={"code": "INVALID_MOVE", "message": "Cannot move into a descendant."},
                    )
                seen.add(cursor.id)
                if cursor.parent_id is None:
                    break
                result = await self.db.execute(select(Document).where(Document.id == cursor.parent_id))
                cursor = result.scalar_one_or_none()
            new_depth = parent.depth + 1
        page.parent_id = parent_id
        page.depth = new_depth
        if position is not None:
            page.position = position
        else:
            page.position = await self._child_count(
                parent_id, page.space_id, source_id=page.source_id
            )
        await self.audit.log(
            action=AuditAction.MOVE_PAGE,
            resource_type="page",
            actor_user_id=user.id,
            workspace_id=page.workspace_id,
            resource_id=page.id,
            metadata={"parent_id": str(parent_id) if parent_id else None},
        )
        await self.db.commit()
        await self.db.refresh(page)
        return page

    async def duplicate(self, user: User, page_id: UUID) -> Document:
        page, _ = await self.require_page(user, page_id, SpaceRole.EDITOR)
        return await self.create(
            user,
            page.space_id,
            title=f"{page.title} (Copy)"[:255],
            parent_id=page.parent_id,
            content=page.raw_content if page.origin == DocumentOrigin.LOCAL else page.normalized_content,
        )

    async def archive(self, user: User, page_id: UUID) -> Document:
        page, _ = await self.require_page(user, page_id, SpaceRole.OWNER)
        await self._archive_subtree(page)
        await self.audit.log(
            action=AuditAction.ARCHIVE_PAGE,
            resource_type="page",
            actor_user_id=user.id,
            workspace_id=page.workspace_id,
            resource_id=page.id,
            metadata={"title": page.title},
        )
        await self.db.commit()
        await self.db.refresh(page)
        return page

    async def _archive_subtree(self, page: Document) -> None:
        page.status = DocumentStatus.ARCHIVED
        page.archived_at = datetime.now(UTC)
        result = await self.db.execute(
            select(Document).where(
                Document.parent_id == page.id,
                Document.deleted_at.is_(None),
            )
        )
        for child in result.scalars().all():
            await self._archive_subtree(child)

    async def restore(self, user: User, page_id: UUID) -> Document:
        page, _ = await self.require_page(user, page_id, SpaceRole.OWNER)
        # Parent may be deleted/archived → root
        if page.parent_id:
            result = await self.db.execute(select(Document).where(Document.id == page.parent_id))
            parent = result.scalar_one_or_none()
            if (
                parent is None
                or parent.deleted_at is not None
                or parent.status == DocumentStatus.ARCHIVED
            ):
                page.parent_id = None
                page.depth = 0
        await self._restore_subtree(page)
        await self.audit.log(
            action=AuditAction.RESTORE_PAGE,
            resource_type="page",
            actor_user_id=user.id,
            workspace_id=page.workspace_id,
            resource_id=page.id,
            metadata={"title": page.title},
        )
        await self.db.commit()
        await self.db.refresh(page)
        return page

    async def _restore_subtree(self, page: Document) -> None:
        page.status = DocumentStatus.READY
        page.archived_at = None
        result = await self.db.execute(
            select(Document).where(
                Document.parent_id == page.id,
                Document.deleted_at.is_(None),
                Document.status == DocumentStatus.ARCHIVED,
            )
        )
        for child in result.scalars().all():
            await self._restore_subtree(child)

    async def soft_delete(self, user: User, page_id: UUID) -> None:
        page, _ = await self.require_page(user, page_id, SpaceRole.OWNER)
        await self._soft_delete_subtree(page)
        await self.audit.log(
            action=AuditAction.DELETE_PAGE,
            resource_type="page",
            actor_user_id=user.id,
            workspace_id=page.workspace_id,
            resource_id=page.id,
            metadata={"title": page.title},
        )
        await self.db.commit()

    async def _soft_delete_subtree(self, page: Document) -> None:
        page.status = DocumentStatus.DELETED
        page.deleted_at = datetime.now(UTC)
        result = await self.db.execute(
            select(Document).where(Document.parent_id == page.id, Document.deleted_at.is_(None))
        )
        for child in result.scalars().all():
            await self._soft_delete_subtree(child)

    async def list_archived(
        self,
        user: User,
        space_id: UUID,
        *,
        source_id: UUID | None = None,
    ) -> list[Document]:
        await self.permissions.require_space_access(space_id, user.id, SpaceRole.VIEWER)
        if source_id is not None:
            await self.require_source(space_id, source_id)
        q = select(Document).where(
            Document.space_id == space_id,
            Document.document_type == DocumentType.PAGE,
            Document.deleted_at.is_(None),
            Document.status == DocumentStatus.ARCHIVED,
        )
        if source_id is not None:
            q = q.where(Document.source_id == source_id)
        result = await self.db.execute(q.order_by(Document.title.asc()))
        return list(result.scalars().all())

    async def star(self, user: User, page_id: UUID) -> None:
        page, _ = await self.require_page(user, page_id, SpaceRole.VIEWER)
        existing = await self.db.execute(
            select(UserStarredPage).where(
                UserStarredPage.user_id == user.id, UserStarredPage.page_id == page.id
            )
        )
        if existing.scalar_one_or_none() is None:
            self.db.add(UserStarredPage(user_id=user.id, page_id=page.id))
            await self.audit.log(
                action=AuditAction.STAR_PAGE,
                resource_type="page",
                actor_user_id=user.id,
                workspace_id=page.workspace_id,
                resource_id=page.id,
                metadata={},
            )
            await self.db.commit()

    async def unstar(self, user: User, page_id: UUID) -> None:
        page, _ = await self.require_page(user, page_id, SpaceRole.VIEWER)
        result = await self.db.execute(
            select(UserStarredPage).where(
                UserStarredPage.user_id == user.id, UserStarredPage.page_id == page.id
            )
        )
        row = result.scalar_one_or_none()
        if row:
            await self.db.delete(row)
            await self.audit.log(
                action=AuditAction.UNSTAR_PAGE,
                resource_type="page",
                actor_user_id=user.id,
                workspace_id=page.workspace_id,
                resource_id=page.id,
                metadata={},
            )
            await self.db.commit()
