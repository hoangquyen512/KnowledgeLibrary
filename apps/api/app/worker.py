from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "knowledge_library",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(name="health.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="ingestion.run_job")
def run_ingestion_job_task(job_id: str) -> str:
    import asyncio
    from uuid import UUID

    from app.ingestion.service import run_ingestion_job

    asyncio.run(run_ingestion_job(UUID(job_id)))
    return "ok"
