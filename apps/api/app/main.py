from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import api_router
from app.core.config import settings
from app.core.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import RequestIdMiddleware
from app.core.rate_limit import RateLimitMiddleware
from app.ingestion.scheduler import start_sync_scheduler, stop_sync_scheduler

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.app_env != "test":
        settings.require_runtime_secrets()
        from app.ingestion.storage import get_object_storage

        get_object_storage()  # fail fast if storage module is broken
        if settings.demo_mode and settings.database_url.startswith("sqlite"):
            from sqlalchemy import create_engine, event, text

            from app.core.database import configure_sqlite_connection, is_sqlite_url, sqlite_connect_args
            from app.core.demo_schema import ensure_sqlite_demo_schema

            sync_url = settings.database_url.replace("sqlite+aiosqlite", "sqlite", 1)
            sync_engine = create_engine(
                sync_url,
                connect_args=sqlite_connect_args() if is_sqlite_url(sync_url) else {},
            )

            @event.listens_for(sync_engine, "connect")
            def _configure_sync_sqlite(dbapi_connection, _connection_record) -> None:
                if is_sqlite_url(sync_url):
                    configure_sqlite_connection(dbapi_connection)

            with sync_engine.begin() as conn:
                ensure_sqlite_demo_schema(conn)
                if is_sqlite_url(sync_url):
                    conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
            sync_engine.dispose()
        start_sync_scheduler()
    try:
        yield
    finally:
        if settings.app_env != "test":
            stop_sync_scheduler()


app = FastAPI(
    title="AI Knowledge Library API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(api_router, prefix="/api/v1")
# Convenience aliases matching master prompt paths
app.include_router(api_router)
