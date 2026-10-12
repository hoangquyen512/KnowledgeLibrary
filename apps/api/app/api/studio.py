from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_csrf
from app.core.database import get_db
from app.models.user import User
from app.schemas.studio import (
    StudioArtifactCreate,
    StudioArtifactOut,
    StudioArtifactUpdate,
    StudioRegenerateIn,
)
from app.studio.service import StudioService, run_studio_generation

router = APIRouter(tags=["studio"])


def _artifact_out(artifact, space_ids: list[UUID], document_ids: list[UUID]) -> StudioArtifactOut:
    return StudioArtifactOut(
        id=artifact.id,
        workspace_id=artifact.workspace_id,
        artifact_type=artifact.artifact_type,
        title=artifact.title,
        status=artifact.status,
        focus_prompt=artifact.focus_prompt,
        payload_json=artifact.payload_json,
        warning_json=artifact.warning_json,
        progress_percent=artifact.progress_percent,
        stage=artifact.stage,
        error_message=artifact.error_message,
        model_provider=artifact.model_provider,
        model_name=artifact.model_name,
        space_ids=space_ids,
        document_ids=document_ids,
        created_at=artifact.created_at,
        updated_at=artifact.updated_at,
    )


async def _out_with_sources(svc: StudioService, artifact) -> StudioArtifactOut:
    space_ids, document_ids = await svc.artifact_source_ids(artifact.id)
    return _artifact_out(artifact, space_ids, document_ids)


@router.post("/studio/artifacts", response_model=StudioArtifactOut, status_code=202)
async def create_studio_artifact(
    body: StudioArtifactCreate,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> StudioArtifactOut:
    svc = StudioService(db)
    artifact = await svc.create_artifact(
        user,
        workspace_id=body.workspace_id,
        artifact_type=body.artifact_type,
        title=body.title,
        focus_prompt=body.focus_prompt,
        space_ids=body.space_ids,
        document_ids=body.document_ids,
    )
    background_tasks.add_task(run_studio_generation, artifact.id)
    return await _out_with_sources(svc, artifact)


@router.get("/studio/artifacts", response_model=list[StudioArtifactOut])
async def list_studio_artifacts(
    workspace_id: UUID,
    artifact_type: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[StudioArtifactOut]:
    svc = StudioService(db)
    items = await svc.list_artifacts(user, workspace_id, artifact_type=artifact_type)
    out: list[StudioArtifactOut] = []
    for item in items:
        out.append(await _out_with_sources(svc, item))
    return out


@router.get("/studio/artifacts/{artifact_id}", response_model=StudioArtifactOut)
async def get_studio_artifact(
    artifact_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudioArtifactOut:
    svc = StudioService(db)
    artifact = await svc.get_artifact(user, artifact_id)
    return await _out_with_sources(svc, artifact)


@router.patch("/studio/artifacts/{artifact_id}", response_model=StudioArtifactOut)
async def patch_studio_artifact(
    artifact_id: UUID,
    body: StudioArtifactUpdate,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> StudioArtifactOut:
    svc = StudioService(db)
    slides = [s.model_dump(mode="json") for s in body.slides] if body.slides else None
    nodes = [n.model_dump(mode="json") for n in body.nodes] if body.nodes else None
    artifact = await svc.update_artifact(
        user,
        artifact_id,
        title=body.title,
        slides=slides,
        nodes=nodes,
    )
    return await _out_with_sources(svc, artifact)


@router.post("/studio/artifacts/{artifact_id}/regenerate", response_model=StudioArtifactOut, status_code=202)
async def regenerate_studio_artifact(
    artifact_id: UUID,
    background_tasks: BackgroundTasks,
    body: StudioRegenerateIn | None = None,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> StudioArtifactOut:
    svc = StudioService(db)
    slide_id = body.slide_id if body else None
    focus_prompt = body.focus_prompt if body else None
    artifact = await svc.schedule_regenerate(
        user, artifact_id, slide_id=slide_id, focus_prompt=focus_prompt
    )
    background_tasks.add_task(run_studio_generation, artifact_id, slide_id=slide_id)
    return await _out_with_sources(svc, artifact)


@router.delete("/studio/artifacts/{artifact_id}", status_code=204)
async def delete_studio_artifact(
    artifact_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await StudioService(db).delete_artifact(user, artifact_id)
    return Response(status_code=204)


@router.get("/studio/artifacts/{artifact_id}/export.pptx")
async def export_studio_pptx(
    artifact_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    data, filename = await StudioService(db).export_pptx(user, artifact_id)
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
