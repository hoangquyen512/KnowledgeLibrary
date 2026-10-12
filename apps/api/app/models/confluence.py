from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ConnectionMode:
    DIRECT = "DIRECT"
    LOCAL_AGENT = "LOCAL_AGENT"


class CredentialLocation:
    CLOUD = "CLOUD"
    LOCAL_AGENT = "LOCAL_AGENT"


class ConnectionAuthType:
    PAT = "PAT"
    SESSION_COOKIE = "SESSION_COOKIE"


class ConnectionStatus:
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    INVALID = "INVALID"
    DISABLED = "DISABLED"


class ConfluenceConnection(Base):
    __tablename__ = "confluence_connections"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    connection_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ConnectionMode.DIRECT
    )
    credential_location: Mapped[str] = mapped_column(
        String(32), nullable=False, default=CredentialLocation.CLOUD
    )
    connector_agent_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("connector_agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    auth_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ConnectionAuthType.PAT
    )
    encrypted_credentials: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    masked_suffix: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ConnectionStatus.DRAFT
    )
    detected_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)  # never store secrets here
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
