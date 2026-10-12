from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AiCredentialOut(BaseModel):
    provider: str
    status: str
    key_mask: str | None = None
    mode: str
    last_validated_at: datetime | None = None
    verified_model: str | None = None


class AiCredentialTestIn(BaseModel):
    api_key: str | None = Field(default=None, max_length=512)
    preferred_model: str | None = Field(default=None, max_length=128)


class AiCredentialTestOut(BaseModel):
    ok: bool
    models_listed: int = 0
    sample_models: list[str] = Field(default_factory=list)
    available_models: list[str] = Field(default_factory=list)
    verified_model: str | None = None
    preferred_model: str | None = None
    list_error: str | None = None


class AiModelsOut(BaseModel):
    models: list[str] = Field(default_factory=list)
    default_model: str | None = None


class AiCredentialIn(BaseModel):
    api_key: str | None = Field(default=None, max_length=512)
    test_only: bool = False
    verified_model: str | None = Field(default=None, max_length=128)


class SearchHitOut(BaseModel):
    chunk_id: UUID
    document_id: UUID
    space_id: UUID
    title: str
    snippet: str
    score: float


class SearchRequest(BaseModel):
    q: str = Field(min_length=2, max_length=500)
    space_ids: list[UUID] | None = None
    source_ids: list[UUID] | None = None
    limit: int = Field(default=12, ge=1, le=50)


class ConversationCreate(BaseModel):
    title: str | None = None
    space_ids: list[UUID] = Field(min_length=1)


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class ConversationOut(BaseModel):
    id: UUID
    workspace_id: UUID
    title: str
    status: str
    space_ids: list[UUID] = []
    created_at: datetime
    updated_at: datetime


class CitationOut(BaseModel):
    id: UUID
    document_id: UUID
    chunk_id: UUID
    citation_index: int
    snippet: str | None = None
    title: str | None = None
    space_id: UUID | None = None
    section_heading: str | None = None
    source_url: str | None = None


class MessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    model_provider: str | None = None
    model_name: str | None = None
    created_at: datetime
    citations: list[CitationOut] = []
    structured: dict[str, Any] | None = None
    retrieved_chunk_count: int | None = None
    unique_document_count: int | None = None
    space_ids: list[UUID] = []


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    space_ids: list[UUID] | None = None
    source_ids: list[UUID] | None = None
