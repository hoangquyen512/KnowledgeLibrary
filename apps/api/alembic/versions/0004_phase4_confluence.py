"""Phase 4: confluence connections + sources."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_phase4_confluence"
down_revision: Union[str, None] = "0003_phase3_spaces"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "confluence_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("connection_mode", sa.String(length=32), nullable=False, server_default="DIRECT"),
        sa.Column("auth_type", sa.String(length=32), nullable=False, server_default="PAT"),
        sa.Column("encrypted_credentials", sa.LargeBinary(), nullable=False),
        sa.Column("masked_suffix", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("detected_version", sa.String(length=120), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_confluence_connections_workspace_id", "confluence_connections", ["workspace_id"])

    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("space_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False, server_default="CONFLUENCE"),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="READY_TO_IMPORT"),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("external_type", sa.String(length=32), nullable=True),
        sa.Column("external_id", sa.String(length=200), nullable=True),
        sa.Column("external_key", sa.String(length=200), nullable=True),
        sa.Column("external_url", sa.String(length=1000), nullable=True),
        sa.Column("import_scope", sa.String(length=64), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["confluence_connections.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_sources_workspace_id", "sources", ["workspace_id"])
    op.create_index("ix_sources_space_id", "sources", ["space_id"])
    op.create_index("ix_sources_connection_id", "sources", ["connection_id"])


def downgrade() -> None:
    op.drop_index("ix_sources_connection_id", table_name="sources")
    op.drop_index("ix_sources_space_id", table_name="sources")
    op.drop_index("ix_sources_workspace_id", table_name="sources")
    op.drop_table("sources")
    op.drop_index("ix_confluence_connections_workspace_id", table_name="confluence_connections")
    op.drop_table("confluence_connections")
