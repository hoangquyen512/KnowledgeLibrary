from __future__ import annotations

import asyncio
import json
import re
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.service import AgentService
from app.auth.deps import get_current_user, require_csrf
from app.core.database import get_db
from app.ingestion.documents import (
    get_space_attachment,
    get_space_document,
    list_document_attachments_for_page,
    list_space_documents,
)
from app.ingestion.normalize import (
    replace_confluence_images,
    replace_drawio_macros_with_images,
)
from app.ingestion.service import IngestionService
from app.ingestion.storage import get_object_storage
from app.models.document import Attachment
from app.models.user import User
from app.schemas.confluence import SourceOut, SourceSyncSettingsIn
from app.schemas.ingestion import (
    AgentIngestionPayloadIn,
    AttachmentOut,
    DocumentDetailOut,
    DocumentOut,
    IngestionJobOut,
)

router = APIRouter(tags=["ingestion"])

_SAFE_FILENAME = re.compile(r"[^\w.\-]+", re.UNICODE)


def _content_disposition(filename: str, *, disposition: str = "inline") -> str:
    """RFC 5987 Content-Disposition — ASCII fallback + UTF-8 filename*."""
    raw = (filename or "file").replace('"', "").replace("\r", "").replace("\n", "")
    ascii_name = _SAFE_FILENAME.sub("_", raw).encode("ascii", "ignore").decode("ascii") or "file"
    encoded = quote(raw, safe="")
    return f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"


def _job_out(data: dict) -> IngestionJobOut:
    return IngestionJobOut.model_validate(data)


@router.post("/sources/{source_id}/import", response_model=IngestionJobOut, status_code=201)
async def start_import(
    source_id: UUID,
    request: Request,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> IngestionJobOut:
    options = None
    # Optional JSON body for sheet selection etc.
    try:
        body = await request.json()
        if isinstance(body, dict):
            options = dict(body.get("options") or {})
            if body.get("sheet_names") is not None:
                options["sheet_names"] = body["sheet_names"]
            if not options:
                options = None
    except Exception:  # noqa: BLE001
        options = None
    svc = IngestionService(db)
    job = await svc.start_import(user, source_id, options=options)
    source = await svc._get_source(source_id)
    return _job_out(svc.serialize_job(job, source=source))


@router.post("/sources/{source_id}/sync", response_model=IngestionJobOut, status_code=201)
async def start_sync(
    source_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> IngestionJobOut:
    svc = IngestionService(db)
    job = await svc.start_sync(user, source_id)
    source = await svc._get_source(source_id)
    return _job_out(svc.serialize_job(job, source=source))


@router.get("/sources/{source_id}/export-preview")
async def preview_export_markdown(
    source_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return document count and file counts per group_depth (0–5)."""
    return await IngestionService(db).preview_export_markdown(user, source_id)


@router.get("/sources/{source_id}/export.md.preview")
async def preview_export_markdown_legacy(
    source_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Legacy alias — prefer ``/export-preview``."""
    return await IngestionService(db).preview_export_markdown(user, source_id)


@router.get("/sources/{source_id}/export.md.zip")
async def export_source_markdown_zip(
    source_id: UUID,
    group_depth: int = Query(
        default=2,
        ge=0,
        le=20,
        description="0 = one file per page; 1–20 = bundle under that tree level (lower = larger files).",
    ),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    data, filename = await IngestionService(db).export_source_markdown_zip(
        user, source_id, group_depth=group_depth
    )
    return StreamingResponse(
        iter([data]),
        media_type="application/zip",
        headers={
            "Content-Disposition": _content_disposition(filename, disposition="attachment"),
            "Content-Length": str(len(data)),
        },
    )


@router.patch("/sources/{source_id}/sync-settings", response_model=SourceOut)
async def update_sync_settings(
    source_id: UUID,
    body: SourceSyncSettingsIn,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> SourceOut:
    svc = IngestionService(db)
    source = await svc.update_sync_settings(
        user,
        source_id,
        sync_enabled=body.sync_enabled,
        sync_interval=body.sync_interval,
    )
    return SourceOut.model_validate(source)


@router.get("/sources/{source_id}/ingestion-jobs/latest", response_model=IngestionJobOut | None)
async def latest_job_for_source(
    source_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IngestionJobOut | None:
    svc = IngestionService.reader(db)
    job = await svc.get_latest_job_for_source(user, source_id)
    if job is None:
        return None
    return _job_out(await svc.job_detail(user, job.id))


@router.get("/ingestion-jobs/{job_id}", response_model=IngestionJobOut)
@router.get("/jobs/{job_id}", response_model=IngestionJobOut)
async def get_ingestion_job(
    job_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IngestionJobOut:
    return _job_out(await IngestionService.reader(db).job_detail(user, job_id))


@router.post("/ingestion-jobs/{job_id}/cancel", response_model=IngestionJobOut)
@router.post("/jobs/{job_id}/cancel", response_model=IngestionJobOut)
async def cancel_ingestion_job(
    job_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> IngestionJobOut:
    svc = IngestionService(db)
    job = await svc.cancel_job(user, job_id)
    return _job_out(await svc.job_detail(user, job.id))


@router.get("/ingestion-jobs/{job_id}/events")
@router.get("/jobs/{job_id}/events")
async def ingestion_job_events(
    job_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    svc = IngestionService.reader(db)
    await svc.get_job(user, job_id)

    async def event_stream():
        last_payload = ""
        terminal = {
            "COMPLETED",
            "COMPLETED_WITH_ERRORS",
            "FAILED",
            "CANCELLED",
        }
        while True:
            if await request.is_disconnected():
                break
            detail = await IngestionService.reader(db).job_detail(user, job_id)
            payload = json.dumps(detail, default=str)
            if payload != last_payload:
                last_payload = payload
                yield f"event: job_progress\ndata: {payload}\n\n"
            if detail.get("status") in terminal:
                yield f"event: job_completed\ndata: {payload}\n\n"
                break
            await asyncio.sleep(1.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/spaces/{space_id}/documents", response_model=list[DocumentOut])
async def list_documents(
    space_id: UUID,
    source_id: UUID | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentOut]:
    rows = await list_space_documents(db, user, space_id, source_id=source_id)
    return [DocumentOut.model_validate(r) for r in rows]


@router.get("/documents/{document_id}", response_model=DocumentDetailOut)
async def get_document(
    document_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentDetailOut:
    doc = await get_space_document(db, user, document_id)
    out = DocumentDetailOut.model_validate(doc)
    raw = out.raw_content or ""
    needs_images = "ac:image" in raw.lower() or "ri:attachment" in raw.lower()
    needs_drawio = "drawio" in raw.lower()
    if needs_images or needs_drawio:
        result = await db.execute(select(Attachment).where(Attachment.document_id == document_id))
        fmap: dict[str, str] = {}
        for att in result.scalars().all():
            fmap[att.filename] = str(att.id)
            fmap[att.filename.lower()] = str(att.id)
        if fmap:
            if needs_images:
                raw = replace_confluence_images(raw, filename_to_attachment_id=fmap)
            if needs_drawio:
                raw = replace_drawio_macros_with_images(
                    raw, filename_to_attachment_id=fmap
                )
            out.raw_content = raw
    return out


@router.get("/documents/{document_id}/attachments", response_model=list[AttachmentOut])
async def list_document_attachments(
    document_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AttachmentOut]:
    rows = await list_document_attachments_for_page(db, user, document_id)
    return [AttachmentOut.model_validate(r) for r in rows]


@router.get("/attachments/{attachment_id}/content")
async def get_attachment_content(
    attachment_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    att = await get_space_attachment(db, user, attachment_id)
    try:
        data = get_object_storage().get_bytes(att.object_key)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ATTACHMENT_FILE_MISSING",
                "message": "Attachment file is missing from storage. Re-import the Source.",
            },
        ) from None
    headers = {
        "Content-Disposition": _content_disposition(att.filename),
        "Cache-Control": "private, max-age=3600",
    }
    return Response(content=data, media_type=att.media_type or "application/octet-stream", headers=headers)


@router.post("/agent/ingestion-payloads", response_model=IngestionJobOut)
async def agent_ingestion_payload(
    body: AgentIngestionPayloadIn,
    x_agent_id: UUID = Header(..., alias="X-Agent-Id"),
    x_agent_secret: str = Header(..., alias="X-Agent-Secret"),
    db: AsyncSession = Depends(get_db),
) -> IngestionJobOut:
    agent = await AgentService(db).authenticate_agent(x_agent_id, x_agent_secret)
    svc = IngestionService(db)
    job = await svc.ingest_agent_payload(
        agent_id=agent.id,
        ingestion_job_id=body.ingestion_job_id,
        pages=body.pages,
        scan=body.scan,
    )
    source = await svc._get_source(job.source_id)
    return _job_out(svc.serialize_job(job, source=source))
