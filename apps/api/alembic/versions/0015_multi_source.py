"""Multi-source ingestion: jira connections, source files, source config."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_multi_source"
down_revision: Union[str, None] = "0014_studio_artifacts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jira_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("connection_mode", sa.String(length=32), nullable=False),
        sa.Column("credential_location", sa.String(length=32), nullable=False),
        sa.Column("auth_type", sa.String(length=32), nullable=False),
        sa.Column("encrypted_credentials", sa.LargeBinary(), nullable=True),
        sa.Column("masked_suffix", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("detected_version", sa.String(length=120), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jira_connections_workspace_id", "jira_connections", ["workspace_id"])

    op.add_column("sources", sa.Column("jira_connection_id", sa.Uuid(), nullable=True))
    op.add_column("sources", sa.Column("config_json", sa.JSON(), nullable=True))
    op.add_column("sources", sa.Column("metadata_json", sa.JSON(), nullable=True))
    op.add_column("sources", sa.Column("error_code", sa.String(length=64), nullable=True))
    op.add_column("sources", sa.Column("error_message", sa.Text(), nullable=True))
    op.create_index("ix_sources_jira_connection_id", "sources", ["jira_connection_id"])
    op.create_foreign_key(
        "fk_sources_jira_connection_id",
        "sources",
        "jira_connections",
        ["jira_connection_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "source_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("space_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(length=1000), nullable=False),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("display_name", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=200), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_files_source_id", "source_files", ["source_id"])
    op.create_index("ix_source_files_workspace_id", "source_files", ["workspace_id"])
    op.create_index("ix_source_files_space_id", "source_files", ["space_id"])
    op.create_index("ix_source_files_checksum_sha256", "source_files", ["checksum_sha256"])


def downgrade() -> None:
    op.drop_index("ix_source_files_checksum_sha256", table_name="source_files")
    op.drop_index("ix_source_files_space_id", table_name="source_files")
    op.drop_index("ix_source_files_workspace_id", table_name="source_files")
    op.drop_index("ix_source_files_source_id", table_name="source_files")
    op.drop_table("source_files")

    op.drop_constraint("fk_sources_jira_connection_id", "sources", type_="foreignkey")
    op.drop_index("ix_sources_jira_connection_id", table_name="sources")
    op.drop_column("sources", "error_message")
    op.drop_column("sources", "error_code")
    op.drop_column("sources", "metadata_json")
    op.drop_column("sources", "config_json")
    op.drop_column("sources", "jira_connection_id")

    op.drop_index("ix_jira_connections_workspace_id", table_name="jira_connections")
    op.drop_table("jira_connections")
