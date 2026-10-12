from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SpaceStatus:
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


class SpaceRole:
    OWNER = "OWNER"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"

    RANK = {VIEWER: 1, EDITOR: 2, OWNER: 3}

    @classmethod
    def at_least(cls, role: str, required: str) -> bool:
        return cls.RANK.get(role, 0) >= cls.RANK.get(required, 99)

    @classmethod
    def strongest(cls, *roles: str | None) -> str | None:
        best: str | None = None
        best_rank = 0
        for role in roles:
            if role is None:
                continue
            rank = cls.RANK.get(role, 0)
            if rank > best_rank:
                best = role
                best_rank = rank
        return best


class SpaceMembershipSource:
    CREATED = "CREATED"
    SHARE_LINK = "SHARE_LINK"
    EXPLICIT = "EXPLICIT"


ALLOWED_ICON_KEYS = {
    "folder",
    "book",
    "users",
    "chart",
    "code",
    "megaphone",
    "shield",
    "globe",
    "briefcase",
    "file-text",
}

ALLOWED_ACCENT_KEYS = {
    "blue",
    "green",
    "violet",
    "amber",
    "rose",
    "cyan",
    "slate",
}


class Space(Base):
    __tablename__ = "spaces"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon_key: Mapped[str] = mapped_column(String(64), nullable=False, default="folder")
    accent_key: Mapped[str] = mapped_column(String(32), nullable=False, default="blue")
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=SpaceStatus.ACTIVE)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    memberships: Mapped[list[SpaceMembership]] = relationship(
        "SpaceMembership", back_populates="space"
    )


class SpaceMembership(Base):
    __tablename__ = "space_memberships"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    space_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default=SpaceMembershipSource.EXPLICIT
    )
    granted_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    share_link_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("share_links.id", ondelete="SET NULL"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    space: Mapped[Space] = relationship("Space", back_populates="memberships")


class UserStarredSpace(Base):
    __tablename__ = "user_starred_spaces"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    space_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserRecentSpace(Base):
    __tablename__ = "user_recent_spaces"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    space_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    last_opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
