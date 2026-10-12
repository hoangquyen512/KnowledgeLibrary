from fastapi import APIRouter, Depends

from redis.asyncio import Redis

from sqlalchemy import text

from sqlalchemy.ext.asyncio import AsyncSession



from app.core.config import settings

from app.core.database import get_db



router = APIRouter(tags=["health"])





@router.get("/health")

async def health() -> dict[str, str]:

    return {"status": "ok", "api_revision": "studio-2026-08-28"}





@router.get("/ready")

async def ready(db: AsyncSession = Depends(get_db)) -> dict[str, object]:

    checks: dict[str, str] = {}

    try:

        await db.execute(text("SELECT 1"))

        checks["database"] = "ok"

    except Exception:

        checks["database"] = "error"



    try:

        redis = Redis.from_url(settings.redis_url, decode_responses=True)

        pong = await redis.ping()

        await redis.aclose()

        checks["redis"] = "ok" if pong else "error"

    except Exception:

        checks["redis"] = "error"



    ok = all(v == "ok" for v in checks.values())

    return {

        "status": "ok" if ok else "degraded",

        "checks": checks,

    }

