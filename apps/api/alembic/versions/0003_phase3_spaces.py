"""Phase 3: spaces, memberships, starred, recent."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_phase3_spaces"
down_revision: Union[str, None] = "0002_phase2_workspace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "spaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon_key", sa.String(length=64), nullable=False, server_default="folder"),
        sa.Column("accent_key", sa.String(length=32), nullable=False, server_default="blue"),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_spaces_workspace_id", "spaces", ["workspace_id"])
    op.create_index("ix_spaces_slug", "spaces", ["slug"])
    op.create_index("ix_spaces_created_by_user_id", "spaces", ["created_by_user_id"])
    op.create_index("ix_spaces_workspace_status", "spaces", ["workspace_id", "status"])
    op.create_index("ix_spaces_workspace_updated", "spaces", ["workspace_id", "updated_at"])

    op.create_table(
        "space_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("space_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="EXPLICIT"),
        sa.Column("granted_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("share_link_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["share_link_id"], ["share_links.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_space_memberships_space_id", "space_memberships", ["space_id"])
    op.create_index("ix_space_memberships_user_id", "space_memberships", ["user_id"])
    op.create_index(
        "uq_space_memberships_active",
        "space_memberships",
        ["space_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
        sqlite_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "user_starred_spaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("space_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "space_id", name="uq_user_starred_spaces_user_space"),
    )
    op.create_index("ix_user_starred_spaces_user_id", "user_starred_spaces", ["user_id"])
    op.create_index("ix_user_starred_spaces_space_id", "user_starred_spaces", ["space_id"])

    op.create_table(
        "user_recent_spaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("space_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "last_opened_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "space_id", name="uq_user_recent_spaces_user_space"),
    )
    op.create_index("ix_user_recent_spaces_user_id", "user_recent_spaces", ["user_id"])
    op.create_index(
        "ix_user_recent_spaces_user_opened",
        "user_recent_spaces",
        ["user_id", "last_opened_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_recent_spaces_user_opened", table_name="user_recent_spaces")
    op.drop_index("ix_user_recent_spaces_user_id", table_name="user_recent_spaces")
    op.drop_table("user_recent_spaces")
    op.drop_index("ix_user_starred_spaces_space_id", table_name="user_starred_spaces")
    op.drop_index("ix_user_starred_spaces_user_id", table_name="user_starred_spaces")
    op.drop_table("user_starred_spaces")
    op.drop_index("uq_space_memberships_active", table_name="space_memberships")
    op.drop_index("ix_space_memberships_user_id", table_name="space_memberships")
    op.drop_index("ix_space_memberships_space_id", table_name="space_memberships")
    op.drop_table("space_memberships")
    op.drop_index("ix_spaces_workspace_updated", table_name="spaces")
    op.drop_index("ix_spaces_workspace_status", table_name="spaces")
    op.drop_index("ix_spaces_created_by_user_id", table_name="spaces")
    op.drop_index("ix_spaces_slug", table_name="spaces")
    op.drop_index("ix_spaces_workspace_id", table_name="spaces")
    op.drop_table("spaces")
