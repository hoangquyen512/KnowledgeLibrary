from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base


class AuditAction:
    CREATE_WORKSPACE = "CREATE_WORKSPACE"
    UPDATE_WORKSPACE = "UPDATE_WORKSPACE"
    DELETE_WORKSPACE = "DELETE_WORKSPACE"
    SHARE_WORKSPACE = "SHARE_WORKSPACE"
    REDEEM_SHARE_LINK = "REDEEM_SHARE_LINK"
    REVOKE_SHARE_LINK = "REVOKE_SHARE_LINK"
    ADD_OWNER = "ADD_OWNER"
    CHANGE_ROLE = "CHANGE_ROLE"
    REMOVE_MEMBER = "REMOVE_MEMBER"
    CHANGE_THEME = "CHANGE_THEME"
    CREATE_SPACE = "CREATE_SPACE"
    UPDATE_SPACE = "UPDATE_SPACE"
    ARCHIVE_SPACE = "ARCHIVE_SPACE"
    RESTORE_SPACE = "RESTORE_SPACE"
    DELETE_SPACE = "DELETE_SPACE"
    STAR_SPACE = "STAR_SPACE"
    UNSTAR_SPACE = "UNSTAR_SPACE"
    SHARE_SPACE = "SHARE_SPACE"
    CHANGE_SPACE_ROLE = "CHANGE_SPACE_ROLE"
    REMOVE_SPACE_MEMBER = "REMOVE_SPACE_MEMBER"
    ADD_SPACE_OWNER = "ADD_SPACE_OWNER"
    CREATE_CONFLUENCE_CONNECTION = "CREATE_CONFLUENCE_CONNECTION"
    UPDATE_CONFLUENCE_CONNECTION = "UPDATE_CONFLUENCE_CONNECTION"
    DELETE_CONFLUENCE_CONNECTION = "DELETE_CONFLUENCE_CONNECTION"
    TEST_CONFLUENCE_CONNECTION = "TEST_CONFLUENCE_CONNECTION"
    ATTACH_SOURCE = "ATTACH_SOURCE"
    DELETE_SOURCE = "DELETE_SOURCE"
    CREATE_AGENT_REGISTRATION_TOKEN = "CREATE_AGENT_REGISTRATION_TOKEN"
    REGISTER_AGENT = "REGISTER_AGENT"
    REVOKE_AGENT = "REVOKE_AGENT"
    START_INGESTION = "START_INGESTION"
    CREATE_PAGE = "CREATE_PAGE"
    UPDATE_PAGE = "UPDATE_PAGE"
    RENAME_PAGE = "RENAME_PAGE"
    MOVE_PAGE = "MOVE_PAGE"
    DUPLICATE_PAGE = "DUPLICATE_PAGE"
    ARCHIVE_PAGE = "ARCHIVE_PAGE"
    RESTORE_PAGE = "RESTORE_PAGE"
    DELETE_PAGE = "DELETE_PAGE"
    STAR_PAGE = "STAR_PAGE"
    UNSTAR_PAGE = "UNSTAR_PAGE"
    SUSPEND_USER = "SUSPEND_USER"
    UNSUSPEND_USER = "UNSUSPEND_USER"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    metadata_json_sanitized: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
