from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class JobStatsOut(BaseModel):
    total_pages: int = 0
    processed_pages: int = 0
    total_attachments: int = 0
    processed_attachments: int = 0
    total_diagrams: int = 0
    processed_diagrams: int = 0
    failed_items: int = 0


class JobStageOut(BaseModel):
    key: str
    label: str
    status: str


class JobCurrentItemOut(BaseModel):
    name: str
    status: str
    type: str = "PAGE"
    at: str | None = None


class JobSourceOut(BaseModel):
    id: UUID
    name: str
    type: str
    import_scope: str | None = None


class IngestionJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    space_id: UUID
    source_id: UUID
    job_type: str
    status: str
    progress_percent: float
    stage: str
    message: str | None
    connector_agent_id: UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime | None = None
    # Enriched monitoring fields
    source: JobSourceOut | None = None
    stats: JobStatsOut | None = None
    stages: list[JobStageOut] = Field(default_factory=list)
    current_items: list[JobCurrentItemOut] = Field(default_factory=list)
    eta_seconds: int | None = None
    cancel_requested: bool = False
    started_by_name: str | None = None
    import_mode: str | None = None
    destination_name: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    sync_stats: dict[str, int] | None = None


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    space_id: UUID
    source_id: UUID | None
    external_id: str
    document_type: str
    title: str
    status: str
    external_url: str | None
    content_checksum: str | None
    created_at: datetime
    updated_at: datetime


class DocumentDetailOut(DocumentOut):
    normalized_content: str | None
    raw_content: str | None


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    filename: str
    media_type: str
    size_bytes: int
    is_drawio: bool
    checksum_sha256: str | None
    created_at: datetime


class AgentIngestionPayloadIn(BaseModel):
    ingestion_job_id: UUID
    pages: list[dict[str, Any]] = Field(default_factory=list)
    scan: bool = False
