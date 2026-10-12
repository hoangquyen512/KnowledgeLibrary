from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SpaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    icon_key: str | None = "folder"
    accent_key: str | None = "blue"


class SpaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    icon_key: str | None = None
    accent_key: str | None = None


class SpaceDelete(BaseModel):
    confirm_name: str = Field(min_length=1, max_length=100)


class SpaceOwnerOut(BaseModel):
    id: UUID
    display_name: str | None = None
    email: str | None = None


class SpaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    slug: str
    description: str | None
    icon_key: str
    accent_key: str
    created_by_user_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    deleted_at: datetime | None = None
    my_role: str | None = None
    is_starred: bool = False
    document_count: int = 0
    source_count: int = 0
    owner: SpaceOwnerOut | None = None


class SpaceListOut(BaseModel):
    items: list[SpaceOut]
    total: int
    page: int
    page_size: int
    counts: dict[str, int]


class WorkspaceOverviewOut(BaseModel):
    space_count: int
    document_count: int
    source_count: int
    storage_bytes: int
    member_count: int
    active_share_link_count: int
