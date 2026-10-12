from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConnectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    base_url: str = Field(min_length=1, max_length=500)
    auth_type: str = Field(default="PAT", pattern="^(PAT|SESSION_COOKIE)$")
    username: str | None = Field(default=None, max_length=320)
    secret: str | None = Field(default=None, max_length=65536)
    connection_mode: str = Field(default="DIRECT", pattern="^(DIRECT|LOCAL_AGENT)$")
    credential_location: str = Field(default="CLOUD", pattern="^(CLOUD|LOCAL_AGENT)$")
    connector_agent_id: UUID | None = None


class ConnectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    base_url: str | None = Field(default=None, min_length=1, max_length=500)
    auth_type: str | None = Field(default=None, pattern="^(PAT|SESSION_COOKIE)$")
    username: str | None = Field(default=None, max_length=320)
    secret: str | None = Field(default=None, min_length=1, max_length=65536)
    connection_mode: str | None = Field(default=None, pattern="^(DIRECT|LOCAL_AGENT)$")
    credential_location: str | None = Field(default=None, pattern="^(CLOUD|LOCAL_AGENT)$")
    connector_agent_id: UUID | None = None


class ConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    base_url: str
    connection_mode: str
    credential_location: str
    connector_agent_id: UUID | None
    auth_type: str
    masked_suffix: str
    status: str
    detected_version: str | None
    last_tested_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    source_count: int = 0


class SourceAttach(BaseModel):
    connection_id: UUID
    name: str = Field(min_length=1, max_length=200)
    external_type: str = Field(pattern="^(SPACE|PAGE)$")
    external_id: str = Field(min_length=1, max_length=200)
    external_key: str | None = Field(default=None, max_length=200)
    external_url: str | None = Field(default=None, max_length=1000)
    import_scope: str = Field(default="SPACE_TREE", max_length=64)


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    space_id: UUID
    type: str
    name: str
    status: str
    connection_id: UUID | None
    jira_connection_id: UUID | None = None
    external_type: str | None
    external_id: str | None
    external_key: str | None
    external_url: str | None
    import_scope: str | None
    config_json: dict | None = None
    metadata_json: dict | None = None
    error_code: str | None = None
    error_message: str | None = None
    sync_enabled: bool = False
    sync_interval: str = "OFF"
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    last_sync_summary: dict[str, int] | None = None
    last_sync_error: str | None = None
    next_sync_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    latest_job_id: UUID | None = None
    document_count: int = 0
    attachment_count: int = 0


class SourceSyncSettingsIn(BaseModel):
    sync_enabled: bool
    sync_interval: str = Field(default="OFF", pattern="^(OFF|HOURLY|DAILY)$")
