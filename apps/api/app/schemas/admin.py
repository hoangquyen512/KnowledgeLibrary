from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AdminSparkPoint(BaseModel):
    date: str
    value: int


class AdminKpiOut(BaseModel):
    key: str
    label: str
    value: int
    period_value: int
    previous_period_value: int
    change_percent: float | None = None
    has_comparison: bool = False
    sparkline: list[AdminSparkPoint] = Field(default_factory=list)


class AdminOverviewOut(BaseModel):
    user_count: int
    active_user_count: int
    suspended_user_count: int
    workspace_count: int
    space_count: int
    source_count: int
    document_count: int
    running_job_count: int
    ai_message_count: int
    ai_input_tokens: int
    ai_output_tokens: int
    timezone: str
    range_start: datetime
    range_end: datetime
    previous_range_start: datetime
    previous_range_end: datetime
    range_start_date: str
    range_end_date: str
    previous_range_start_date: str
    previous_range_end_date: str
    kpis: list[AdminKpiOut] = Field(default_factory=list)


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str | None
    status: str
    is_super_admin: bool
    last_login_at: datetime | None
    created_at: datetime


class AdminUserListOut(BaseModel):
    items: list[AdminUserOut]
    total: int


class AdminUserStatusIn(BaseModel):
    status: str = Field(pattern="^(ACTIVE|SUSPENDED)$")


class AdminAuditLogOut(BaseModel):
    id: UUID
    action: str
    resource_type: str
    resource_id: UUID | None
    workspace_id: UUID | None
    actor_user_id: UUID | None
    actor_email: str | None
    metadata: dict | None = None
    created_at: datetime


class AdminAuditLogListOut(BaseModel):
    items: list[AdminAuditLogOut]
    total: int


class AdminUsageRowOut(BaseModel):
    user_id: UUID
    user_email: str
    workspace_id: UUID
    message_count: int
    input_tokens: int
    output_tokens: int


class AdminUsageOut(BaseModel):
    items: list[AdminUsageRowOut]
    total_messages: int
    total_input_tokens: int
    total_output_tokens: int


class AdminActivityPointOut(BaseModel):
    date: str
    documents: int
    ai_queries: int
    users: int


class AdminActivitySeriesOut(BaseModel):
    granularity: str
    timezone: str
    range_start: datetime
    range_end: datetime
    points: list[AdminActivityPointOut]


class AdminSourceSliceOut(BaseModel):
    key: str
    label: str
    count: int
    percent: float


class AdminSourceDistributionOut(BaseModel):
    total: int
    items: list[AdminSourceSliceOut]


class AdminAiUsageSummaryOut(BaseModel):
    period: str
    timezone: str
    range_start: datetime
    range_end: datetime
    input_tokens: int
    output_tokens: int
    total_tokens: int
    message_count: int


class AdminRecentActivityItemOut(BaseModel):
    id: UUID
    action: str
    message: str
    actor_name: str | None
    created_at: datetime


class AdminRecentActivityOut(BaseModel):
    items: list[AdminRecentActivityItemOut]
    total: int


class AdminTopDocumentOut(BaseModel):
    id: UUID
    title: str
    source_type: str
    workspace_name: str
    space_name: str
    views: int
    last_viewed_at: datetime | None


class AdminTopDocumentsOut(BaseModel):
    views_tracked: bool
    items: list[AdminTopDocumentOut]


class AdminHealthItemOut(BaseModel):
    key: str
    label: str
    status: str
    detail: str
    verified: bool
    used_bytes: int | None = None
    used_percent: float | None = None
    value: float | None = None


class AdminSystemHealthOut(BaseModel):
    timezone: str
    items: list[AdminHealthItemOut]
