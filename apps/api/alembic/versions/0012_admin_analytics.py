"""Minimal document view analytics for admin top-documents."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_admin_analytics"
down_revision: Union[str, None] = "0011_gemini_verified_model"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_view_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_view_events_document_id", "document_view_events", ["document_id"])
    op.create_index("ix_document_view_events_user_id", "document_view_events", ["user_id"])
    op.create_index("ix_document_view_events_created_at", "document_view_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_document_view_events_created_at", table_name="document_view_events")
    op.drop_index("ix_document_view_events_user_id", table_name="document_view_events")
    op.drop_index("ix_document_view_events_document_id", table_name="document_view_events")
    op.drop_table("document_view_events")
