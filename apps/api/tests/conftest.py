from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-at-least-32-chars!!")
os.environ.setdefault("APP_ENCRYPTION_KEY", "test-encryption-key-32bytes-long!!")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://knowledge:knowledge@localhost:5432/knowledge",
    ),
)
os.environ.setdefault(
    "DATABASE_URL_SYNC",
    os.environ.get(
        "TEST_DATABASE_URL_SYNC",
        "postgresql://knowledge:knowledge@localhost:5432/knowledge",
    ),
)
os.environ.setdefault("REDIS_URL", os.environ.get("REDIS_URL", "redis://localhost:6379/0"))

from app.auth.session import create_session_token  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402, F401
    AuditLog,
    ShareLink,
    ShareLinkRedemption,
    Space,
    SpaceMembership,
    StudioArtifact,
    StudioArtifactSource,
    User,
    UserRecentSpace,
    UserSettings,
    UserStarredSpace,
    UserStatus,
    Workspace,
    WorkspaceMembership,
)


async def _db_available() -> bool:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture
async def postgres_ready() -> bool:
    return await _db_available()


@pytest_asyncio.fixture
async def db_session(postgres_ready: bool) -> AsyncGenerator[AsyncSession, None]:
    if not postgres_ready:
        pytest.skip("PostgreSQL is not available (start docker compose postgres)")
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    # Ensure Phase 2/3 tables exist (Alembic in CI; create_all for local/demo DBs).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def active_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid4(),
        google_sub=f"sub-{uuid4()}",
        email=f"user-{uuid4().hex[:8]}@example.com",
        email_verified=True,
        display_name="Test User",
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserSettings(user_id=user.id))
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def suspended_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid4(),
        google_sub=f"sub-{uuid4()}",
        email=f"suspended-{uuid4().hex[:8]}@example.com",
        email_verified=True,
        display_name="Suspended",
        status=UserStatus.SUSPENDED,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserSettings(user_id=user.id))
    await db_session.commit()
    await db_session.refresh(user)
    return user


def auth_cookies(user: User) -> dict[str, str]:
    token, csrf = create_session_token(user.id)
    return {
        settings.session_cookie_name: token,
        settings.csrf_cookie_name: csrf,
    }
