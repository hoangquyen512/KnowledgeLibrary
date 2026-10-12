from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class WorkspaceDelete(BaseModel):
    confirm_name: str = Field(min_length=1, max_length=100)


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    description: str | None
    created_by_user_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    my_role: str | None = None
    space_count: int = 0
    source_count: int = 0


class MemberRoleUpdate(BaseModel):
    role: str


class MemberOut(BaseModel):
    id: UUID
    user_id: UUID
    role: str
    source: str
    email: str | None = None
    display_name: str | None = None


class ShareLinkCreate(BaseModel):
    role: str
    confirm_owner_role: bool = False


class ShareLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    status: str
    use_count: int
    created_at: datetime
    revoked_at: datetime | None = None
    url: str | None = None
    token: str | None = None


class ShareRedeemOut(BaseModel):
    target_type: str = "WORKSPACE"
    workspace_id: UUID
    space_id: UUID | None = None
    role: str


class DashboardSummaryOut(BaseModel):
    owned_workspace_count: int
    workspace_limit: int
    space_count: int
    source_count: int
    document_count: int
    conversation_count_month: int


class ActivityOut(BaseModel):
    id: UUID
    action: str
    resource_type: str
    workspace_id: UUID | None
    workspace_name: str | None = None
    created_at: datetime
    metadata: dict | None = None


class DashboardOut(BaseModel):
    summary: DashboardSummaryOut
    recent_workspaces: list[WorkspaceOut]
    recent_spaces: list = Field(default_factory=list)
    activity: list[ActivityOut]


class SharedOut(BaseModel):
    shared_workspaces: list[WorkspaceOut]
    shared_spaces: list = Field(default_factory=list)  # SpaceOut payloads from spaces API


class UserSettingsUpdate(BaseModel):
    theme: str | None = None
    locale: str | None = None


class UserSettingsResponse(BaseModel):
    theme: str
    locale: str
    default_model: str | None = None
