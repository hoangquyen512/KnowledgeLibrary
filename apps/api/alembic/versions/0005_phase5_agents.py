"""Phase 5: connector agents, registration tokens, jobs; connection LOCAL_AGENT fields."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_phase5_agents"
down_revision: Union[str, None] = "0004_phase4_confluence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "connector_agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("agent_key_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("version", sa.String(length=64), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("agent_key_hash"),
    )
    op.create_index("ix_connector_agents_workspace_id", "connector_agents", ["workspace_id"])
    op.create_index("ix_connector_agents_agent_key_hash", "connector_agents", ["agent_key_hash"])

    op.create_table(
        "agent_registration_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_agent_id"], ["connector_agents.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_agent_registration_tokens_workspace_id",
        "agent_registration_tokens",
        ["workspace_id"],
    )
    op.create_index(
        "ix_agent_registration_tokens_token_hash",
        "agent_registration_tokens",
        ["token_hash"],
    )

    op.create_table(
        "connector_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_type", sa.String(length=32), nullable=False, server_default="NOOP"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="QUEUED"),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("leased_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["agent_id"], ["connector_agents.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_connector_jobs_workspace_id", "connector_jobs", ["workspace_id"])
    op.create_index("ix_connector_jobs_agent_id", "connector_jobs", ["agent_id"])

    op.add_column(
        "confluence_connections",
        sa.Column(
            "credential_location",
            sa.String(length=32),
            nullable=False,
            server_default="CLOUD",
        ),
    )
    op.add_column(
        "confluence_connections",
        sa.Column("connector_agent_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_confluence_connections_connector_agent_id",
        "confluence_connections",
        "connector_agents",
        ["connector_agent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column(
        "confluence_connections",
        "encrypted_credentials",
        existing_type=sa.LargeBinary(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "confluence_connections",
        "encrypted_credentials",
        existing_type=sa.LargeBinary(),
        nullable=False,
    )
    op.drop_constraint(
        "fk_confluence_connections_connector_agent_id",
        "confluence_connections",
        type_="foreignkey",
    )
    op.drop_column("confluence_connections", "connector_agent_id")
    op.drop_column("confluence_connections", "credential_location")
    op.drop_index("ix_connector_jobs_agent_id", table_name="connector_jobs")
    op.drop_index("ix_connector_jobs_workspace_id", table_name="connector_jobs")
    op.drop_table("connector_jobs")
    op.drop_index(
        "ix_agent_registration_tokens_token_hash", table_name="agent_registration_tokens"
    )
    op.drop_index(
        "ix_agent_registration_tokens_workspace_id", table_name="agent_registration_tokens"
    )
    op.drop_table("agent_registration_tokens")
    op.drop_index("ix_connector_agents_agent_key_hash", table_name="connector_agents")
    op.drop_index("ix_connector_agents_workspace_id", table_name="connector_agents")
    op.drop_table("connector_agents")
