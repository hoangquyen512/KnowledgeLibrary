"""Jira connections and Jira source attach APIs."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_csrf
from app.core.database import get_db
from app.jira.service import JiraService
from app.models.user import User
from app.schemas.confluence import SourceOut
from app.schemas.sources import JiraConnectionCreate, JiraConnectionOut, JiraSourceAttach

router = APIRouter(tags=["jira"])


@router.get(
    "/workspaces/{workspace_id}/jira-connections",
    response_model=list[JiraConnectionOut],
)
async def list_jira_connections(
    workspace_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[JiraConnectionOut]:
    rows = await JiraService(db).list_connections(user, workspace_id)
    from sqlalchemy import func, select

    from app.models.source import Source

    ids = [r.id for r in rows]
    counts: dict[UUID, int] = {}
    if ids:
        count_rows = await db.execute(
            select(Source.jira_connection_id, func.count())
            .where(Source.jira_connection_id.in_(ids), Source.deleted_at.is_(None))
            .group_by(Source.jira_connection_id)
        )
        counts = {cid: int(n) for cid, n in count_rows.all() if cid is not None}
    out: list[JiraConnectionOut] = []
    for r in rows:
        data = JiraConnectionOut.model_validate(r)
        data.source_count = counts.get(r.id, 0)
        out.append(data)
    return out


@router.post(
    "/workspaces/{workspace_id}/jira-connections",
    response_model=JiraConnectionOut,
    status_code=201,
)
async def create_jira_connection(
    workspace_id: UUID,
    body: JiraConnectionCreate,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> JiraConnectionOut:
    conn = await JiraService(db).create_connection(
        user,
        workspace_id,
        name=body.name,
        base_url=body.base_url,
        auth_type=body.auth_type,
        username=body.username,
        secret=body.secret,
    )
    return JiraConnectionOut.model_validate(conn)


@router.post("/jira-connections/{connection_id}/test", response_model=JiraConnectionOut)
async def test_jira_connection(
    connection_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> JiraConnectionOut:
    conn = await JiraService(db).test_connection(user, connection_id)
    return JiraConnectionOut.model_validate(conn)


@router.get("/jira-connections/{connection_id}/projects")
async def list_jira_projects(
    connection_id: UUID,
    q: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    items = await JiraService(db).list_projects(user, connection_id, query=q)
    return {"items": items}


@router.post(
    "/spaces/{space_id}/sources/jira",
    response_model=SourceOut,
    status_code=201,
)
async def attach_jira_source(
    space_id: UUID,
    body: JiraSourceAttach,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> SourceOut:
    source = await JiraService(db).attach_source(
        user,
        space_id,
        connection_id=body.connection_id,
        name=body.name,
        project_id=body.project_id,
        project_key=body.project_key,
        project_url=body.project_url,
        scope=body.scope,
    )
    return SourceOut.model_validate(source)
