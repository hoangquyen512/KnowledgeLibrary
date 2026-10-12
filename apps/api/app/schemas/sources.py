from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class JiraConnectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    base_url: str = Field(min_length=1, max_length=500)
    auth_type: str = Field(default="PAT", pattern="^(PAT|BEARER|BASIC)$")
    username: str | None = Field(default=None, max_length=320)
    secret: str | None = Field(default=None, max_length=65536)


class JiraConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    base_url: str
    connection_mode: str
    credential_location: str
    auth_type: str
    masked_suffix: str
    status: str
    detected_version: str | None
    last_tested_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    source_count: int = 0


class JiraSourceAttach(BaseModel):
    connection_id: UUID
    name: str = Field(min_length=1, max_length=200)
    project_id: str = Field(min_length=1, max_length=200)
    project_key: str = Field(min_length=1, max_length=200)
    project_url: str | None = Field(default=None, max_length=1000)
    scope: dict[str, bool] | None = None


class SourceImportOptions(BaseModel):
    options: dict[str, Any] | None = None
    sheet_names: list[str] | None = None


class UploadSourceOut(BaseModel):
    source_id: UUID | str
    job_id: UUID | str | None = None
    filename: str
    status: str
    duplicate: bool = False
    message: str | None = None
    preview: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
