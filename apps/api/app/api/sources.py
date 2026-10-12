"""File upload source APIs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_csrf
from app.core.database import get_db
from app.ingestion.files import FileSourceService
from app.ingestion.service import IngestionService
from app.models.user import User
from app.schemas.ingestion import IngestionJobOut
from app.schemas.sources import SourceImportOptions, UploadSourceOut

router = APIRouter(tags=["sources-upload"])


class UploadBatchOut(BaseModel):
    sources: list[UploadSourceOut] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)


@router.post(
    "/spaces/{space_id}/sources/upload",
    response_model=UploadBatchOut,
    status_code=201,
)
async def upload_source_file(
    space_id: UUID,
    file: UploadFile = File(...),
    source_type: str | None = Form(default=None),
    force_new: bool = Form(default=False),
    auto_import: bool = Form(default=True),
    replace_source_id: UUID | None = Form(default=None),
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> UploadBatchOut:
    result = await FileSourceService(db).upload(
        user,
        space_id,
        upload=file,
        expected_source_type=source_type,
        force_new=force_new,
        replace_source_id=replace_source_id,
        auto_import=auto_import,
    )
    row = UploadSourceOut(
        source_id=result["source_id"],
        job_id=result.get("job_id"),
        filename=result["filename"],
        status=result["status"],
        duplicate=bool(result.get("duplicate")),
        message=result.get("message"),
        preview=result.get("preview"),
        warnings=list(result.get("warnings") or []),
    )
    return UploadBatchOut(sources=[row])


@router.post(
    "/sources/{source_id}/import-options",
    response_model=IngestionJobOut,
    status_code=201,
)
async def import_with_options(
    source_id: UUID,
    body: SourceImportOptions,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> IngestionJobOut:
    options = dict(body.options or {})
    if body.sheet_names is not None:
        options["sheet_names"] = body.sheet_names
    svc = IngestionService(db)
    job = await FileSourceService(db).confirm_import(user, source_id, options=options or None)
    source = await svc._get_source(source_id)
    return IngestionJobOut.model_validate(svc.serialize_job(job, source=source))
