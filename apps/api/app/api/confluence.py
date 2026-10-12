from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_csrf
from app.confluence.service import ConfluenceService
from app.core.database import get_db
from app.models.user import User
from app.schemas.confluence import (
    ConnectionCreate,
    ConnectionOut,
    ConnectionUpdate,
    SourceAttach,
    SourceOut,
)

router = APIRouter(tags=["confluence"])


@router.get(
    "/workspaces/{workspace_id}/confluence-connections",
    response_model=list[ConnectionOut],
)
async def list_connections(
    workspace_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConnectionOut]:
    rows = await ConfluenceService(db).list_connections(user, workspace_id)
    ids = [r.id for r in rows]
    counts: dict[UUID, int] = {}
    if ids:
        from sqlalchemy import func, select

        from app.models.source import Source

        count_rows = await db.execute(
            select(Source.connection_id, func.count())
            .where(Source.connection_id.in_(ids), Source.deleted_at.is_(None))
            .group_by(Source.connection_id)
        )
        counts = {cid: int(n) for cid, n in count_rows.all() if cid is not None}
    out: list[ConnectionOut] = []
    for r in rows:
        data = ConnectionOut.model_validate(r)
        data.source_count = counts.get(r.id, 0)
        out.append(data)
    return out


@router.post(
    "/workspaces/{workspace_id}/confluence-connections",
    response_model=ConnectionOut,
    status_code=201,
)
async def create_connection(
    workspace_id: UUID,
    body: ConnectionCreate,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> ConnectionOut:
    conn = await ConfluenceService(db).create_connection(
        user,
        workspace_id,
        name=body.name,
        base_url=body.base_url,
        auth_type=body.auth_type,
        username=body.username,
        secret=body.secret,
        connection_mode=body.connection_mode,
        credential_location=body.credential_location,
        connector_agent_id=body.connector_agent_id,
    )
    return ConnectionOut.model_validate(conn)


@router.get("/confluence-connections/{connection_id}", response_model=ConnectionOut)
async def get_connection(
    connection_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectionOut:
    conn = await ConfluenceService(db).get_connection(user, connection_id)
    return ConnectionOut.model_validate(conn)


@router.patch("/confluence-connections/{connection_id}", response_model=ConnectionOut)
async def update_connection(
    connection_id: UUID,
    body: ConnectionUpdate,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> ConnectionOut:
    conn = await ConfluenceService(db).update_connection(
        user,
        connection_id,
        name=body.name,
        base_url=body.base_url,
        auth_type=body.auth_type,
        username=body.username,
        secret=body.secret,
        connection_mode=body.connection_mode,
        credential_location=body.credential_location,
        connector_agent_id=body.connector_agent_id,
    )
    return ConnectionOut.model_validate(conn)


@router.delete("/confluence-connections/{connection_id}", status_code=204, response_class=Response)
async def delete_connection(
    connection_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await ConfluenceService(db).delete_connection(user, connection_id)
    return Response(status_code=204)


@router.post("/confluence-connections/{connection_id}/test", response_model=ConnectionOut)
async def test_connection(
    connection_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> ConnectionOut:
    conn = await ConfluenceService(db).test_connection(user, connection_id)
    return ConnectionOut.model_validate(conn)


@router.get("/confluence-connections/{connection_id}/spaces")
async def browse_spaces(
    connection_id: UUID,
    q: str | None = None,
    start: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await ConfluenceService(db).browse_spaces(
        user, connection_id, query=q, start=start, limit=limit
    )


@router.get("/confluence-connections/{connection_id}/spaces/{space_key}/pages")
async def browse_pages(
    connection_id: UUID,
    space_key: str,
    start: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await ConfluenceService(db).browse_pages(
        user, connection_id, space_key, start=start, limit=limit
    )


@router.get("/spaces/{space_id}/sources", response_model=list[SourceOut])
async def list_sources(
    space_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SourceOut]:
    from sqlalchemy import func, select

    from app.models.document import Attachment, Document, IngestionJob

    rows = await ConfluenceService(db).list_sources(user, space_id)
    out: list[SourceOut] = []
    for r in rows:
        job = (
            await db.execute(
                select(IngestionJob)
                .where(IngestionJob.source_id == r.id)
                .order_by(IngestionJob.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        doc_count = int(
            (
                await db.execute(
                    select(func.count()).select_from(Document).where(Document.source_id == r.id)
                )
            ).scalar_one()
            or 0
        )
        att_count = int(
            (
                await db.execute(
                    select(func.count()).select_from(Attachment).where(Attachment.source_id == r.id)
                )
            ).scalar_one()
            or 0
        )
        data = SourceOut.model_validate(r)
        data.latest_job_id = job.id if job else None
        data.document_count = doc_count
        data.attachment_count = att_count
        if r.last_sync_status == "FAILED":
            sync_job = job
            if not sync_job or sync_job.job_type != "SYNC" or not sync_job.message:
                sync_job = (
                    await db.execute(
                        select(IngestionJob)
                        .where(
                            IngestionJob.source_id == r.id,
                            IngestionJob.job_type == "SYNC",
                            IngestionJob.status == "FAILED",
                        )
                        .order_by(IngestionJob.created_at.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
            if sync_job and sync_job.message:
                data.last_sync_error = sync_job.message
        out.append(data)
    return out


@router.post("/spaces/{space_id}/sources", response_model=SourceOut, status_code=201)
async def attach_source(
    space_id: UUID,
    body: SourceAttach,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> SourceOut:
    source = await ConfluenceService(db).attach_source(
        user,
        space_id,
        connection_id=body.connection_id,
        name=body.name,
        external_type=body.external_type,
        external_id=body.external_id,
        external_key=body.external_key,
        external_url=body.external_url,
        import_scope=body.import_scope,
    )
    return SourceOut.model_validate(source)


@router.delete("/sources/{source_id}", status_code=204, response_class=Response)
async def delete_source(
    source_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await ConfluenceService(db).delete_source(user, source_id)
    return Response(status_code=204)
