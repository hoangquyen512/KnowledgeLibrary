"""Phase 7: page hierarchy fields + starred/recent pages."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_phase7_pages"
down_revision: Union[str, None] = "0007_phase6_job_progress"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("position", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("documents", sa.Column("depth", sa.Integer(), nullable=False, server_default="0"))
    op.add_column(
        "documents",
        sa.Column("origin", sa.String(length=32), nullable=False, server_default="CONFLUENCE"),
    )
    op.add_column("documents", sa.Column("created_by_user_id", sa.Uuid(), nullable=True))
    op.add_column("documents", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_documents_parent_id", "documents", ["parent_id"])
    op.create_index(
        "ix_documents_space_parent_status_pos",
        "documents",
        ["space_id", "parent_id", "status", "position"],
    )
    op.create_foreign_key(
        "fk_documents_created_by_user_id",
        "documents",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "user_starred_pages",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "page_id"),
    )
    op.create_table(
        "user_recent_pages",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column(
            "last_opened_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "page_id"),
    )


def downgrade() -> None:
    op.drop_table("user_recent_pages")
    op.drop_table("user_starred_pages")
    op.drop_constraint("fk_documents_created_by_user_id", "documents", type_="foreignkey")
    op.drop_index("ix_documents_space_parent_status_pos", table_name="documents")
    op.drop_index("ix_documents_parent_id", table_name="documents")
    op.drop_column("documents", "deleted_at")
    op.drop_column("documents", "archived_at")
    op.drop_column("documents", "created_by_user_id")
    op.drop_column("documents", "origin")
    op.drop_column("documents", "depth")
    op.drop_column("documents", "position")
