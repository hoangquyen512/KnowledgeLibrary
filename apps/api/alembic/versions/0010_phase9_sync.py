"""Phase 9: Confluence delta sync — source settings + SYNC job type."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_phase9_sync"
down_revision: Union[str, None] = "0009_phase8_ask_ai"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column("sync_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "sources",
        sa.Column("sync_interval", sa.String(length=16), nullable=False, server_default="OFF"),
    )
    op.add_column("sources", sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "sources",
        sa.Column("last_sync_status", sa.String(length=32), nullable=True),
    )
    op.add_column("sources", sa.Column("last_sync_summary", sa.JSON(), nullable=True))
    op.add_column("sources", sa.Column("next_sync_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "next_sync_at")
    op.drop_column("sources", "last_sync_summary")
    op.drop_column("sources", "last_sync_status")
    op.drop_column("sources", "last_sync_at")
    op.drop_column("sources", "sync_interval")
    op.drop_column("sources", "sync_enabled")
