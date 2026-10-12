from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService
from app.models.agent import (
    AgentRegistrationToken,
    AgentStatus,
    ConnectorAgent,
    ConnectorJob,
    JobStatus,
    JobType,
    RegistrationTokenStatus,
)
from app.models.audit import AuditAction
from app.models.user import User
from app.models.workspace import WorkspaceRole
from app.permissions.service import PermissionService

HEARTBEAT_OFFLINE_SECONDS = 180
REGISTRATION_TOKEN_TTL_HOURS = 24
JOB_LEASE_SECONDS = 120
DEFAULT_HEARTBEAT_INTERVAL = 30


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_raw_token() -> str:
    return secrets.token_urlsafe(32)


class AgentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.permissions = PermissionService(db)
        self.audit = AuditService(db)

    def _effective_status(self, agent: ConnectorAgent) -> str:
        if agent.status == AgentStatus.REVOKED or agent.revoked_at is not None:
            return AgentStatus.REVOKED
        if agent.last_heartbeat_at is None:
            return AgentStatus.PENDING if agent.status == AgentStatus.PENDING else AgentStatus.OFFLINE
        age = (datetime.now(UTC) - agent.last_heartbeat_at).total_seconds()
        if age > HEARTBEAT_OFFLINE_SECONDS:
            return AgentStatus.OFFLINE
        return AgentStatus.ONLINE

    async def create_registration_token(
        self, user: User, workspace_id: UUID
    ) -> tuple[AgentRegistrationToken, str]:
        await self.permissions.require_role(workspace_id, user.id, WorkspaceRole.OWNER)
        raw = generate_raw_token()
        row = AgentRegistrationToken(
            id=uuid4(),
            workspace_id=workspace_id,
            token_hash=hash_token(raw),
            status=RegistrationTokenStatus.ACTIVE,
            expires_at=datetime.now(UTC) + timedelta(hours=REGISTRATION_TOKEN_TTL_HOURS),
            created_by_user_id=user.id,
        )
        self.db.add(row)
        await self.audit.log(
            action=AuditAction.CREATE_AGENT_REGISTRATION_TOKEN,
            resource_type="agent_registration_token",
            actor_user_id=user.id,
            workspace_id=workspace_id,
            resource_id=row.id,
            metadata={},
        )
        await self.db.commit()
        await self.db.refresh(row)
        return row, raw

    async def list_agents(self, user: User, workspace_id: UUID) -> list[ConnectorAgent]:
        await self.permissions.require_role(workspace_id, user.id, WorkspaceRole.VIEWER)
        result = await self.db.execute(
            select(ConnectorAgent)
            .where(
                ConnectorAgent.workspace_id == workspace_id,
                ConnectorAgent.revoked_at.is_(None),
            )
            .order_by(ConnectorAgent.created_at.desc())
        )
        agents = list(result.scalars().all())
        for agent in agents:
            effective = self._effective_status(agent)
            if agent.status != AgentStatus.REVOKED and agent.status != effective:
                agent.status = effective
        await self.db.commit()
        return agents

    async def revoke_agent(self, user: User, agent_id: UUID) -> None:
        result = await self.db.execute(
            select(ConnectorAgent).where(ConnectorAgent.id == agent_id)
        )
        agent = result.scalar_one_or_none()
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "AGENT_NOT_FOUND", "message": "Agent not found."},
            )
        await self.permissions.require_role(agent.workspace_id, user.id, WorkspaceRole.OWNER)
        agent.status = AgentStatus.REVOKED
        agent.revoked_at = datetime.now(UTC)
        await self.audit.log(
            action=AuditAction.REVOKE_AGENT,
            resource_type="connector_agent",
            actor_user_id=user.id,
            workspace_id=agent.workspace_id,
            resource_id=agent.id,
            metadata={"name": agent.name},
        )
        await self.db.commit()

    async def enqueue_noop(
        self, user: User, workspace_id: UUID, *, agent_id: UUID | None = None
    ) -> ConnectorJob:
        await self.permissions.require_role(workspace_id, user.id, WorkspaceRole.OWNER)
        if agent_id:
            agent = await self._get_agent(agent_id)
            if agent.workspace_id != workspace_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "AGENT_WORKSPACE_MISMATCH",
                        "message": "Agent belongs to another workspace.",
                    },
                )
        job = ConnectorJob(
            id=uuid4(),
            workspace_id=workspace_id,
            agent_id=agent_id,
            job_type=JobType.NOOP,
            status=JobStatus.QUEUED,
            payload_json={"message": "ping"},
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def _get_agent(self, agent_id: UUID) -> ConnectorAgent:
        result = await self.db.execute(
            select(ConnectorAgent).where(ConnectorAgent.id == agent_id)
        )
        agent = result.scalar_one_or_none()
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "AGENT_NOT_FOUND", "message": "Agent not found."},
            )
        return agent

    async def register(
        self,
        *,
        registration_token: str,
        name: str,
        version: str | None,
        metadata: dict[str, Any] | None,
    ) -> tuple[ConnectorAgent, str]:
        token_hash = hash_token(registration_token.strip())
        result = await self.db.execute(
            select(AgentRegistrationToken).where(AgentRegistrationToken.token_hash == token_hash)
        )
        token = result.scalar_one_or_none()
        if token is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "REGISTRATION_TOKEN_INVALID",
                    "message": "Registration token is invalid.",
                },
            )
        now = datetime.now(UTC)
        if token.status != RegistrationTokenStatus.ACTIVE or token.used_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "REGISTRATION_TOKEN_USED",
                    "message": "Registration token already used or revoked.",
                },
            )
        if token.expires_at <= now:
            token.status = RegistrationTokenStatus.EXPIRED
            await self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "REGISTRATION_TOKEN_EXPIRED",
                    "message": "Registration token has expired.",
                },
            )

        raw_secret = generate_raw_token()
        agent = ConnectorAgent(
            id=uuid4(),
            workspace_id=token.workspace_id,
            name=(name or "Connector Agent").strip()[:120],
            agent_key_hash=hash_token(raw_secret),
            status=AgentStatus.ONLINE,
            version=(version or "")[:64] or None,
            last_heartbeat_at=now,
            metadata_json=metadata,
            created_by_user_id=token.created_by_user_id,
        )
        self.db.add(agent)
        await self.db.flush()
        token.status = RegistrationTokenStatus.USED
        token.used_at = now
        token.created_agent_id = agent.id
        await self.audit.log(
            action=AuditAction.REGISTER_AGENT,
            resource_type="connector_agent",
            actor_user_id=token.created_by_user_id,
            workspace_id=token.workspace_id,
            resource_id=agent.id,
            metadata={"name": agent.name, "version": agent.version},
        )
        await self.db.commit()
        await self.db.refresh(agent)
        return agent, raw_secret

    async def authenticate_agent(self, agent_id: UUID, agent_secret: str) -> ConnectorAgent:
        agent = await self._get_agent(agent_id)
        if agent.revoked_at is not None or agent.status == AgentStatus.REVOKED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "AGENT_REVOKED", "message": "Agent has been revoked."},
            )
        if agent.agent_key_hash != hash_token(agent_secret):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "AGENT_AUTH_FAILED", "message": "Invalid agent credentials."},
            )
        return agent

    async def heartbeat(
        self,
        agent: ConnectorAgent,
        *,
        version: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        agent.last_heartbeat_at = now
        agent.status = AgentStatus.ONLINE
        if version:
            agent.version = version[:64]
        if metadata is not None:
            agent.metadata_json = metadata
        await self.db.commit()
        return {
            "ok": True,
            "server_time": now.isoformat(),
            "next_heartbeat_seconds": DEFAULT_HEARTBEAT_INTERVAL,
            "workspace_id": str(agent.workspace_id),
        }

    async def next_job(self, agent: ConnectorAgent) -> ConnectorJob | None:
        now = datetime.now(UTC)
        # Prefer jobs targeted at this agent, else unassigned workspace jobs
        result = await self.db.execute(
            select(ConnectorJob)
            .where(
                ConnectorJob.workspace_id == agent.workspace_id,
                ConnectorJob.status == JobStatus.QUEUED,
                or_(ConnectorJob.agent_id == agent.id, ConnectorJob.agent_id.is_(None)),
            )
            .order_by(ConnectorJob.created_at.asc())
            .limit(1)
        )
        job = result.scalar_one_or_none()
        if job is None:
            return None
        job.status = JobStatus.LEASED
        job.agent_id = agent.id
        job.leased_at = now
        job.lease_expires_at = now + timedelta(seconds=JOB_LEASE_SECONDS)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def complete_job(
        self,
        agent: ConnectorAgent,
        job_id: UUID,
        *,
        job_status: str,
        result: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> ConnectorJob:
        result_q = await self.db.execute(select(ConnectorJob).where(ConnectorJob.id == job_id))
        job = result_q.scalar_one_or_none()
        if job is None or job.workspace_id != agent.workspace_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "JOB_NOT_FOUND", "message": "Job not found."},
            )
        if job.agent_id and job.agent_id != agent.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "JOB_ACCESS_DENIED", "message": "Job leased by another agent."},
            )
        if job_status not in {JobStatus.SUCCEEDED, JobStatus.FAILED}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_JOB_STATUS", "message": "Invalid completion status."},
            )
        job.status = job_status
        job.result_json = result
        job.error_message = (error_message or "")[:500] or None
        job.completed_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(job)
        return job
