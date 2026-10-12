"""Apply demo SQLite patches and optionally re-index chunks for Ask AI."""

from __future__ import annotations

import argparse
import asyncio
import logging
from uuid import UUID

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.core.demo_schema import ensure_sqlite_demo_schema
from app.ingestion.service import IngestionService
from app.models.source import Source
from app.models.workspace import Workspace

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def apply_schema_patches() -> None:
    if not settings.database_url.startswith("sqlite"):
        logger.info("Non-SQLite database — use: uv run alembic upgrade head")
        return
    async with engine.begin() as conn:
        await conn.run_sync(ensure_sqlite_demo_schema)
    logger.info("SQLite demo schema patches applied.")


async def list_targets() -> None:
    async with AsyncSessionLocal() as db:
        workspaces = list((await db.execute(select(Workspace.id, Workspace.name))).all())
        sources = list(
            (
                await db.execute(
                    select(Source.id, Source.name, Source.workspace_id, Source.external_key).where(
                        Source.deleted_at.is_(None)
                    )
                )
            ).all()
        )
    logger.info("Workspaces (%s):", len(workspaces))
    for wid, name in workspaces:
        logger.info("  %s  %s", wid, name)
    logger.info("Sources (%s):", len(sources))
    for sid, name, wid, key in sources:
        logger.info("  %s  [%s] workspace=%s  key=%s", sid, name, wid, key or "-")


async def reindex_source(source_id: UUID) -> int:
    async with AsyncSessionLocal() as db:
        svc = IngestionService(db)
        result = await db.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one_or_none()
        if source is None:
            raise SystemExit(f"Source not found: {source_id}")
        from app.models.document import Document

        docs = list(
            (
                await db.execute(
                    select(Document.id).where(
                        Document.source_id == source.id,
                        Document.deleted_at.is_(None),
                    )
                )
            ).scalars().all()
        )
        logger.info("Re-indexing %s documents for source %s (%s)", len(docs), source.name, source_id)
        await svc._chunk_and_embed_documents(source, docs)
        return len(docs)


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


async def reindex_all() -> int:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Source.id).where(Source.deleted_at.is_(None)))
        source_ids = list(result.scalars().all())
    total = 0
    for sid in source_ids:
        total += await reindex_source(sid)
    return total


async def main_async(args: argparse.Namespace) -> None:
    if args.schema_only or not (args.source_id or args.workspace_id or args.all):
        await apply_schema_patches()
    if args.list:
        await list_targets()
        return
    if args.source_id:
        count = await reindex_source(args.source_id)
        logger.info("Done — re-indexed %s documents.", count)
    elif args.workspace_id:
        count = await reindex_workspace(args.workspace_id)
        logger.info("Done — re-indexed %s documents in workspace.", count)
    elif args.all:
        await apply_schema_patches()
        count = await reindex_all()
        logger.info("Done — re-indexed %s documents across all sources.", count)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask AI migration helper (schema + re-index).")
    parser.add_argument("--list", action="store_true", help="List workspaces and sources")
    parser.add_argument("--schema-only", action="store_true", help="Only apply SQLite schema patches")
    parser.add_argument("--all", action="store_true", help="Re-index every source")
    parser.add_argument("--source-id", type=UUID)
    parser.add_argument("--workspace-id", type=UUID)
    args = parser.parse_args()
    if not any([args.list, args.schema_only, args.all, args.source_id, args.workspace_id]):
        parser.print_help()
        return
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
