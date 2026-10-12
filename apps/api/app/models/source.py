from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base


class SourceType:
    CONFLUENCE = "CONFLUENCE"
    JIRA = "JIRA"
    FILE_EXCEL = "FILE_EXCEL"
    FILE_CSV = "FILE_CSV"
    FILE_WORD = "FILE_WORD"
    FILE_POWERPOINT = "FILE_POWERPOINT"
    FILE_PDF = "FILE_PDF"
    # Legacy / scaffold aliases
    FILE_UPLOAD = "FILE_UPLOAD"
    LOCAL = "LOCAL"
    # Future-ready (not built yet)
    GOOGLE_DRIVE = "GOOGLE_DRIVE"
    SHAREPOINT = "SHAREPOINT"
    WEB = "WEB"


FILE_SOURCE_TYPES = frozenset(
    {
        SourceType.FILE_EXCEL,
        SourceType.FILE_CSV,
        SourceType.FILE_WORD,
        SourceType.FILE_POWERPOINT,
        SourceType.FILE_PDF,
        SourceType.FILE_UPLOAD,
    }
)

SYNCABLE_SOURCE_TYPES = frozenset({SourceType.CONFLUENCE, SourceType.JIRA})


class SourceStatus:
    READY_TO_IMPORT = "READY_TO_IMPORT"
    CONNECTED = "CONNECTED"
    UPLOADED = "UPLOADED"
    IMPORTING = "IMPORTING"
    PARSING = "PARSING"
    INDEXING = "INDEXING"
    READY = "READY"
    SYNCED = "SYNCED"
    INDEXED = "INDEXED"
    ERROR = "ERROR"
    FAILED = "FAILED"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"
    DISABLED = "DISABLED"


class SourceExternalType:
    SPACE = "SPACE"
    PAGE = "PAGE"
    PROJECT = "PROJECT"
    FILE = "FILE"


class SyncInterval:
    OFF = "OFF"
    HOURLY = "HOURLY"
    DAILY = "DAILY"


class SyncStatus:
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    space_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False, default=SourceType.CONFLUENCE)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=SourceStatus.READY_TO_IMPORT
    )
    connection_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("confluence_connections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    jira_connection_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("jira_connections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    external_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    external_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    import_scope: Mapped[str | None] = mapped_column(String(64), nullable=True)
    config_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sync_interval: Mapped[str] = mapped_column(
        String(16), nullable=False, default=SyncInterval.OFF
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_sync_summary: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    next_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
