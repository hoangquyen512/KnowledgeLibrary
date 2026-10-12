from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RegistrationTokenCreateOut(BaseModel):
    id: UUID
    workspace_id: UUID
    expires_at: datetime
    registration_token: str
    message: str = "Store this token now. It will not be shown again."


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    status: str
    version: str | None
    last_heartbeat_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AgentRegisterIn(BaseModel):
    registration_token: str = Field(min_length=8, max_length=200)
    name: str = Field(default="Connector Agent", min_length=1, max_length=120)
    version: str | None = Field(default=None, max_length=64)
    metadata: dict[str, Any] | None = None


class AgentRegisterOut(BaseModel):
    agent_id: UUID
    agent_secret: str
    workspace_id: UUID
    heartbeat_interval_seconds: int = 30
    message: str = "Store agent_secret now. It will not be shown again."


class AgentHeartbeatIn(BaseModel):
    version: str | None = Field(default=None, max_length=64)
    metadata: dict[str, Any] | None = None


class AgentHeartbeatOut(BaseModel):
    ok: bool
    server_time: str
    next_heartbeat_seconds: int
    workspace_id: str


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    agent_id: UUID | None
    job_type: str
    status: str
    payload_json: dict[str, Any] | None
    created_at: datetime


class JobCompleteIn(BaseModel):
    status: str = Field(pattern="^(SUCCEEDED|FAILED)$")
    result: dict[str, Any] | None = None
    error_message: str | None = Field(default=None, max_length=500)


class EnqueueNoopIn(BaseModel):
    agent_id: UUID | None = None


class EnqueueNoopOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    agent_id: UUID | None
    job_type: str
    status: str
    created_at: datetime
