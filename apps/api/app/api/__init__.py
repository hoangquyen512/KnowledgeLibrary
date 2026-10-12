from fastapi import APIRouter

from app.api import (
    admin,
    agents,
    ask,
    auth,
    confluence,
    dashboard,
    health,
    ingestion,
    jira,
    pages,
    share,
    sources,
    spaces,
    studio,
    user_settings,
    workspaces,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(user_settings.router)
api_router.include_router(dashboard.router)
api_router.include_router(workspaces.router)
api_router.include_router(spaces.router)
api_router.include_router(share.router)
api_router.include_router(confluence.router)
api_router.include_router(jira.router)
api_router.include_router(sources.router)
api_router.include_router(agents.router)
api_router.include_router(ingestion.router)
api_router.include_router(pages.router)
api_router.include_router(ask.router)
api_router.include_router(studio.router)
api_router.include_router(admin.router)
