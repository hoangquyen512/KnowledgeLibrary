"""Read-only document queries — no IngestionService / object storage dependency."""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import INDEXABLE_DOCUMENT_TYPES, Attachment, Document
from app.models.source import Source
from app.models.space import SpaceRole
from app.models.user import User
from app.permissions.service import PermissionService


async def list_space_documents(
    db: AsyncSession,
    user: User,
    space_id: UUID,
    *,
    source_id: UUID | None = None,
) -> list[Document]:
    permissions = PermissionService(db)
    await permissions.require_space_access(space_id, user.id, SpaceRole.VIEWER)
    filters = [
        Document.space_id == space_id,
        Document.document_type.in_(INDEXABLE_DOCUMENT_TYPES),
        Document.deleted_at.is_(None),
        or_(Document.source_id.is_(None), Source.deleted_at.is_(None)),
    ]
    if source_id is not None:
        filters.append(Document.source_id == source_id)
    result = await db.execute(
        select(Document)
        .outerjoin(Source, Source.id == Document.source_id)
        .where(*filters)
        .order_by(Document.title.asc())
    )
    return list(result.scalars().all())


async def get_space_document(db: AsyncSession, user: User, document_id: UUID) -> Document:
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DOCUMENT_NOT_FOUND", "message": "Document not found."},
        )
    permissions = PermissionService(db)
    await permissions.require_space_access(doc.space_id, user.id, SpaceRole.VIEWER)
    return doc


async def get_space_attachment(db: AsyncSession, user: User, attachment_id: UUID) -> Attachment:
    result = await db.execute(select(Attachment).where(Attachment.id == attachment_id))
    att = result.scalar_one_or_none()
    if att is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ATTACHMENT_NOT_FOUND", "message": "Attachment not found."},
        )
    permissions = PermissionService(db)
    await permissions.require_space_access(att.space_id, user.id, SpaceRole.VIEWER)
    return att


async def list_document_attachments_for_page(
    db: AsyncSession, user: User, document_id: UUID
) -> list[Attachment]:
    doc = await get_space_document(db, user, document_id)
    result = await db.execute(
        select(Attachment).where(Attachment.document_id == doc.id).order_by(Attachment.filename)
    )
    return list(result.scalars().all())
