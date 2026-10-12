from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    locale: str
    theme: str
    default_model: str | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str = Field(min_length=3, max_length=320)
    email_verified: bool
    display_name: str | None = None
    avatar_url: str | None = None
    status: str
    is_super_admin: bool
    last_login_at: datetime | None = None
    created_at: datetime | None = None
    settings: UserSettingsOut | None = None
