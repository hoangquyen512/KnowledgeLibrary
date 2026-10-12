from __future__ import annotations

from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.labels import sanitize_metadata
from app.admin.period import resolve_date_range
from app.admin.service import AdminService
from app.auth.deps import require_csrf, require_super_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.admin import (
    AdminActivitySeriesOut,
    AdminAiUsageSummaryOut,
    AdminAuditLogListOut,
    AdminAuditLogOut,
    AdminOverviewOut,
    AdminRecentActivityOut,
    AdminSourceDistributionOut,
    AdminSystemHealthOut,
    AdminTopDocumentsOut,
    AdminUsageOut,
    AdminUsageRowOut,
    AdminUserListOut,
    AdminUserOut,
    AdminUserStatusIn,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _range(
    from_date: date | None,
    to_date: date | None,
):
    return resolve_date_range(from_date, to_date)


@router.get("/overview", response_model=AdminOverviewOut)
async def admin_overview(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    _admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminOverviewOut:
    data = await AdminService(db).overview(_range(from_date, to_date))
    return AdminOverviewOut.model_validate(data)


@router.get("/activity-series", response_model=AdminActivitySeriesOut)
async def admin_activity_series(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    granularity: str = Query(default="daily", pattern="^(daily|weekly|monthly)$"),
    _admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminActivitySeriesOut:
    data = await AdminService(db).activity_series(_range(from_date, to_date), granularity)
    return AdminActivitySeriesOut.model_validate(data)


@router.get("/source-distribution", response_model=AdminSourceDistributionOut)
async def admin_source_distribution(
    _admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminSourceDistributionOut:
    data = await AdminService(db).source_distribution()
    return AdminSourceDistributionOut.model_validate(data)


@router.get("/ai-usage", response_model=AdminAiUsageSummaryOut)
async def admin_ai_usage_chart(
    period: str = Query(default="this_week", pattern="^(today|this_week|this_month|custom)$"),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    _admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminAiUsageSummaryOut:
    today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
    if period == "today":
        rng = resolve_date_range(today, today)
    elif period == "this_month":
        rng = resolve_date_range(today.replace(day=1), today)
    elif period == "custom":
        rng = resolve_date_range(from_date, to_date)
    else:
        rng = resolve_date_range(None, None)
    data = await AdminService(db).ai_usage_summary(rng, period)
    return AdminAiUsageSummaryOut.model_validate(data)


@router.get("/recent-activity", response_model=AdminRecentActivityOut)
async def admin_recent_activity(
    limit: int = Query(default=8, ge=1, le=20),
    _admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminRecentActivityOut:
    data = await AdminService(db).recent_activity(limit=limit)
    return AdminRecentActivityOut.model_validate(data)


@router.get("/top-documents", response_model=AdminTopDocumentsOut)
async def admin_top_documents(
    limit: int = Query(default=8, ge=1, le=50),
    _admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminTopDocumentsOut:
    data = await AdminService(db).top_documents(limit=limit)
    return AdminTopDocumentsOut.model_validate(data)


@router.get("/system-health", response_model=AdminSystemHealthOut)
async def admin_system_health(
    _admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminSystemHealthOut:
    data = await AdminService(db).system_health()
    return AdminSystemHealthOut.model_validate(data)


@router.get("/export")
async def admin_export(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    _admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    rng = _range(from_date, to_date)
    csv_body = await AdminService(db).export_overview(rng)
    filename = f"admin-overview-{rng.start_date.isoformat()}-{rng.end_date.isoformat()}.csv"
    return StreamingResponse(
        iter([csv_body]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/users", response_model=AdminUserListOut)
async def admin_list_users(
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUserListOut:
    users, total = await AdminService(db).list_users(q=q, limit=limit, offset=offset)
    return AdminUserListOut(
        items=[AdminUserOut.model_validate(u) for u in users],
        total=total,
    )


@router.patch("/users/{user_id}/status", response_model=AdminUserOut)
async def admin_set_user_status(
    user_id: UUID,
    body: AdminUserStatusIn,
    admin: User = Depends(require_super_admin),
    _csrf: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> AdminUserOut:
    user = await AdminService(db).set_user_status(
        admin, user_id, status_value=body.status
    )
    return AdminUserOut.model_validate(user)


@router.get("/audit-logs", response_model=AdminAuditLogListOut)
async def admin_audit_logs(
    action: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminAuditLogListOut:
    rows, total = await AdminService(db).list_audit_logs(
        action=action, limit=limit, offset=offset
    )
    return AdminAuditLogListOut(
        items=[
            AdminAuditLogOut(
                id=log.id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                workspace_id=log.workspace_id,
                actor_user_id=log.actor_user_id,
                actor_email=email,
                metadata=sanitize_metadata(log.metadata_json_sanitized),
                created_at=log.created_at,
            )
            for log, email in rows
        ],
        total=total,
    )


@router.get("/usage", response_model=AdminUsageOut)
async def admin_usage(
    limit: int = Query(default=50, ge=1, le=100),
    _admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUsageOut:
    data = await AdminService(db).usage_summary(limit=limit)
    return AdminUsageOut(
        items=[AdminUsageRowOut.model_validate(r) for r in data["items"]],
        total_messages=data["total_messages"],
        total_input_tokens=data["total_input_tokens"],
        total_output_tokens=data["total_output_tokens"],
    )
