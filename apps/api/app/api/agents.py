from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.service import DEFAULT_HEARTBEAT_INTERVAL, AgentService
from app.auth.deps import get_current_user, require_csrf
from app.core.database import get_db
from app.models.user import User
from app.schemas.agent import (
    AgentHeartbeatIn,
    AgentHeartbeatOut,
    AgentOut,
    AgentRegisterIn,
    AgentRegisterOut,
    EnqueueNoopIn,
    EnqueueNoopOut,
    JobCompleteIn,
    JobOut,
    RegistrationTokenCreateOut,
)

router = APIRouter(tags=["agents"])


def _agent_auth(
    x_agent_id: UUID = Header(..., alias="X-Agent-Id"),
    x_agent_secret: str = Header(..., alias="X-Agent-Secret"),
) -> tuple[UUID, str]:
    return x_agent_id, x_agent_secret


@router.post(
    "/workspaces/{workspace_id}/agent-registration-tokens",
    response_model=RegistrationTokenCreateOut,
    status_code=201,
)
async def create_registration_token(
    workspace_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> RegistrationTokenCreateOut:
    row, raw = await AgentService(db).create_registration_token(user, workspace_id)
    return RegistrationTokenCreateOut(
        id=row.id,
        workspace_id=row.workspace_id,
        expires_at=row.expires_at,
        registration_token=raw,
    )


@router.get("/workspaces/{workspace_id}/agents", response_model=list[AgentOut])
async def list_agents(
    workspace_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AgentOut]:
    rows = await AgentService(db).list_agents(user, workspace_id)
    return [AgentOut.model_validate(r) for r in rows]


@router.delete("/agents/{agent_id}", status_code=204, response_class=Response)
async def revoke_agent(
    agent_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await AgentService(db).revoke_agent(user, agent_id)
    return Response(status_code=204)


@router.post(
    "/workspaces/{workspace_id}/agent-jobs/noop",
    response_model=EnqueueNoopOut,
    status_code=201,
)
async def enqueue_noop(
    workspace_id: UUID,
    body: EnqueueNoopIn,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> EnqueueNoopOut:
    job = await AgentService(db).enqueue_noop(user, workspace_id, agent_id=body.agent_id)
    return EnqueueNoopOut.model_validate(job)


@router.post("/agent/register", response_model=AgentRegisterOut, status_code=201)
async def register_agent(
    body: AgentRegisterIn,
    db: AsyncSession = Depends(get_db),
) -> AgentRegisterOut:
    agent, secret = await AgentService(db).register(
        registration_token=body.registration_token,
        name=body.name,
        version=body.version,
        metadata=body.metadata,
    )
    return AgentRegisterOut(
        agent_id=agent.id,
        agent_secret=secret,
        workspace_id=agent.workspace_id,
        heartbeat_interval_seconds=DEFAULT_HEARTBEAT_INTERVAL,
    )


@router.post("/agent/heartbeat", response_model=AgentHeartbeatOut)
async def agent_heartbeat(
    body: AgentHeartbeatIn,
    auth: tuple[UUID, str] = Depends(_agent_auth),
    db: AsyncSession = Depends(get_db),
) -> AgentHeartbeatOut:
    agent_id, secret = auth
    svc = AgentService(db)
    agent = await svc.authenticate_agent(agent_id, secret)
    data = await svc.heartbeat(agent, version=body.version, metadata=body.metadata)
    return AgentHeartbeatOut(**data)


@router.get("/agent/jobs/next", response_model=JobOut | None)
async def agent_jobs_next(
    auth: tuple[UUID, str] = Depends(_agent_auth),
    db: AsyncSession = Depends(get_db),
) -> JobOut | None:
    agent_id, secret = auth
    svc = AgentService(db)
    agent = await svc.authenticate_agent(agent_id, secret)
    job = await svc.next_job(agent)
    if job is None:
        return None
    return JobOut.model_validate(job)


@router.post("/agent/jobs/{job_id}/complete", response_model=JobOut)
async def agent_job_complete(
    job_id: UUID,
    body: JobCompleteIn,
    auth: tuple[UUID, str] = Depends(_agent_auth),
    db: AsyncSession = Depends(get_db),
) -> JobOut:
    agent_id, secret = auth
    svc = AgentService(db)
    agent = await svc.authenticate_agent(agent_id, secret)
    job = await svc.complete_job(
        agent,
        job_id,
        job_status=body.status,
        result=body.result,
        error_message=body.error_message,
    )
    return JobOut.model_validate(job)
