from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class StudioSourceRefOut(BaseModel):
    document_id: UUID
    chunk_id: UUID | None = None
    title: str
    snippet: str | None = None
    section_heading: str | None = None
    source_url: str | None = None
    space_id: UUID | None = None


class StudioSlideOut(BaseModel):
    id: str
    title: str
    bullets: list[str] = Field(default_factory=list)
    notes: str | None = None
    source_refs: list[StudioSourceRefOut] = Field(default_factory=list)


class StudioMindmapNodeOut(BaseModel):
    id: str
    label: str
    parent_id: str | None = None
    collapsed: bool = False
    source_ref: StudioSourceRefOut | None = None


class StudioPresentationPayload(BaseModel):
    slides: list[StudioSlideOut] = Field(default_factory=list)


class StudioMindmapPayload(BaseModel):
    nodes: list[StudioMindmapNodeOut] = Field(default_factory=list)


class StudioArtifactCreate(BaseModel):
    workspace_id: UUID
    artifact_type: str = Field(pattern="^(PRESENTATION|MINDMAP)$")
    title: str | None = Field(default=None, max_length=255)
    focus_prompt: str | None = Field(default=None, max_length=2000)
    space_ids: list[UUID] = Field(min_length=1)
    document_ids: list[UUID] | None = None


class StudioArtifactUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    slides: list[StudioSlideOut] | None = None
    nodes: list[StudioMindmapNodeOut] | None = None


class StudioRegenerateIn(BaseModel):
    slide_id: str | None = None
    focus_prompt: str | None = Field(default=None, max_length=2000)


class StudioArtifactOut(BaseModel):
    id: UUID
    workspace_id: UUID
    artifact_type: str
    title: str
    status: str
    focus_prompt: str | None = None
    payload_json: dict[str, Any] | None = None
    warning_json: dict[str, Any] | None = None
    progress_percent: float
    stage: str
    error_message: str | None = None
    model_provider: str | None = None
    model_name: str | None = None
    space_ids: list[UUID] = Field(default_factory=list)
    document_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
