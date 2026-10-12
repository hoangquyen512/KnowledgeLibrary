from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PagePermissions(BaseModel):
    can_view: bool = True
    can_edit: bool = False
    can_move: bool = False
    can_archive: bool = False
    can_delete: bool = False
    can_sync: bool = False
    can_create_child: bool = False


class PageTreeNodeOut(BaseModel):
    id: UUID
    title: str
    has_children: bool
    child_count: int = 0
    status: str
    origin: str
    parent_id: UUID | None = None
    position: int = 0
    depth: int = 0


class PagePathItem(BaseModel):
    id: UUID
    title: str


class PageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    space_id: UUID
    source_id: UUID | None = None
    parent_id: UUID | None = None
    title: str
    status: str
    origin: str
    position: int = 0
    depth: int = 0
    external_id: str | None = None
    external_version: str | None = None
    external_url: str | None = None
    has_children: bool = False
    child_count: int = 0
    is_starred: bool = False
    created_at: datetime
    updated_at: datetime
    permissions: PagePermissions
    ancestors: list[PagePathItem] = Field(default_factory=list)


class PageDetailOut(PageOut):
    raw_content: str | None = None
    normalized_content: str | None = None


class PageCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    parent_id: UUID | None = None
    content: str | None = None
    source_id: UUID | None = None


class PageUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = None
    parent_id: UUID | None = None


class PageMove(BaseModel):
    parent_id: UUID | None = None
    position: int | None = Field(default=None, ge=0)


class PageSearchHit(BaseModel):
    id: UUID
    title: str
    path: list[str]
    status: str
    origin: str
    match_field: str = "title"
    snippet: str | None = None
