from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings


class Base(DeclarativeBase):
    pass


SQLITE_BUSY_TIMEOUT_MS = 60_000


def is_sqlite_url(url: str) -> bool:
    return url.startswith("sqlite")


def sqlite_connect_args() -> dict:
    return {"timeout": SQLITE_BUSY_TIMEOUT_MS / 1000}


def configure_sqlite_connection(dbapi_connection) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def _engine_kwargs() -> dict:
    kwargs: dict = {"pool_pre_ping": True}
    if is_sqlite_url(settings.database_url):
        # SQLite file locks are per-connection; pooling causes "database is locked".
        kwargs["poolclass"] = NullPool
        kwargs["connect_args"] = sqlite_connect_args()
    return kwargs


engine = create_async_engine(settings.database_url, **_engine_kwargs())


@event.listens_for(engine.sync_engine, "connect")
def _configure_sqlite(dbapi_connection, _connection_record) -> None:
    if not is_sqlite_url(settings.database_url):
        return
    configure_sqlite_connection(dbapi_connection)


AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
