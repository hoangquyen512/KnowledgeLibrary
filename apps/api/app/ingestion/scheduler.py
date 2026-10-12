"""Background Confluence sync scheduler (demo: asyncio loop in API lifespan)."""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.ingestion.service import IngestionService
from app.models.source import Source, SourceStatus, SyncInterval
from app.models.user import User

logger = logging.getLogger(__name__)

_scheduler_task: asyncio.Task | None = None


async def run_due_syncs() -> None:
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Source).where(
                Source.deleted_at.is_(None),
                Source.status == SourceStatus.READY,
                Source.sync_enabled.is_(True),
                Source.sync_interval != SyncInterval.OFF,
                Source.next_sync_at.is_not(None),
                Source.next_sync_at <= now,
            )
        )
        sources = list(result.scalars().all())
        if not sources:
            return
        svc = IngestionService(db)
        for source in sources:
            user = await db.get(User, source.created_by_user_id)
            if user is None:
                continue
            try:
                logger.info("Scheduled sync for source %s", source.id)
                await svc.start_sync(user, source.id, triggered_by="SCHEDULE")
            except Exception:  # noqa: BLE001
                logger.exception("Scheduled sync failed for source %s", source.id)


async def _scheduler_loop() -> None:
    while True:
        try:
            await run_due_syncs()
        except Exception:  # noqa: BLE001
            logger.exception("Sync scheduler tick failed")
        await asyncio.sleep(60)


def start_sync_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task is not None and not _scheduler_task.done():
        return
    _scheduler_task = asyncio.create_task(_scheduler_loop())


def stop_sync_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task is not None:
        _scheduler_task.cancel()
        _scheduler_task = None
