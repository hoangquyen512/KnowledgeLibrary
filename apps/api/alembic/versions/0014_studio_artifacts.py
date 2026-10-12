"""Studio artifacts: presentations and mindmaps."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_studio_artifacts"
down_revision: Union[str, None] = "0013_ask_notebooklm"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "studio_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("focus_prompt", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("warning_json", sa.JSON(), nullable=True),
        sa.Column("progress_percent", sa.Float(), nullable=False, server_default="0"),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("model_provider", sa.String(length=32), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_studio_artifacts_user_id", "studio_artifacts", ["user_id"])
    op.create_index("ix_studio_artifacts_workspace_id", "studio_artifacts", ["workspace_id"])

    op.create_table(
        "studio_artifact_sources",
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("space_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["studio_artifacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("artifact_id", "space_id", "document_id"),
    )


def downgrade() -> None:
    op.drop_table("studio_artifact_sources")
    op.drop_index("ix_studio_artifacts_workspace_id", table_name="studio_artifacts")
    op.drop_index("ix_studio_artifacts_user_id", table_name="studio_artifacts")
    op.drop_table("studio_artifacts")
