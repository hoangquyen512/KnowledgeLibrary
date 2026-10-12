"""Persist verified Gemini model on user AI credentials."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_gemini_verified_model"
down_revision: Union[str, None] = "0010_phase9_sync"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_ai_credentials",
        sa.Column("verified_model", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_ai_credentials", "verified_model")
