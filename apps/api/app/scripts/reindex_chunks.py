"""Re-index document chunks with heading-aware chunking (manual CLI)."""

from __future__ import annotations

import argparse
import asyncio
import logging
from uuid import UUID

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.ingestion.service import IngestionService
from app.models.document import Document
from app.models.source import Source

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def reindex_source(source_id: UUID) -> int:
    async with AsyncSessionLocal() as db:
        svc = IngestionService(db)
        result = await db.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one_or_none()
        if source is None:
            raise SystemExit(f"Source not found: {source_id}")
        docs = await db.execute(
            select(Document.id).where(
                Document.source_id == source.id,
                Document.deleted_at.is_(None),
            )
        )
        doc_ids = list(docs.scalars().all())
        logger.info("Re-indexing %s documents for source %s", len(doc_ids), source_id)
        await svc._chunk_and_embed_documents(source, doc_ids)
        return len(doc_ids)


async def reindex_workspace(workspace_id: UUID) -> int:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Source.id).where(
                Source.workspace_id == workspace_id,
                Source.deleted_at.is_(None),
            )
        )
        source_ids = list(result.scalars().all())
    total = 0
    for sid in source_ids:
        total += await reindex_source(sid)
    return total


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-index chunks with heading-aware strategy (does not run automatically)."
    )
    parser.add_argument("--source-id", type=UUID, help="Re-index one Confluence/source")
    parser.add_argument("--workspace-id", type=UUID, help="Re-index all sources in a workspace")
    args = parser.parse_args()
    if not args.source_id and not args.workspace_id:
        parser.error("Provide --source-id or --workspace-id")
    if args.source_id:
        count = asyncio.run(reindex_source(args.source_id))
        logger.info("Done. Re-indexed %s documents.", count)
    else:
        count = asyncio.run(reindex_workspace(args.workspace_id))
        logger.info("Done. Re-indexed %s documents across workspace.", count)


if __name__ == "__main__":
    main()
