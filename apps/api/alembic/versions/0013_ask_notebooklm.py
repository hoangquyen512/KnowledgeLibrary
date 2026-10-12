"""Phase 13: Ask AI NotebookLM — chunk FTS + citation enrichment."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_ask_notebooklm"
down_revision: Union[str, None] = "0012_admin_analytics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        op.add_column("citations", sa.Column("section_heading", sa.String(length=500), nullable=True))
        op.add_column("citations", sa.Column("source_url", sa.String(length=1000), nullable=True))
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.add_column("citations", sa.Column("section_heading", sa.String(length=500), nullable=True))
    op.add_column("citations", sa.Column("source_url", sa.String(length=1000), nullable=True))
    op.execute(
        """
        ALTER TABLE document_chunks
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
          to_tsvector(
            'simple',
            coalesce(heading_path, '') || ' ' || coalesce(content, '')
          )
        ) STORED
        """
    )
    op.create_index(
        "ix_document_chunks_search_vector",
        "document_chunks",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_index("ix_document_chunks_search_vector", table_name="document_chunks")
        op.drop_column("document_chunks", "search_vector")
    op.drop_column("citations", "source_url")
    op.drop_column("citations", "section_heading")
