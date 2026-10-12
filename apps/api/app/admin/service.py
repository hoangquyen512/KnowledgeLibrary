from __future__ import annotations

import time
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy import Date, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.labels import (
    RECENT_ACTIVITY_ACTIONS,
    actor_display,
    format_activity_message,
    sanitize_metadata,
    source_bucket,
    source_bucket_labels,
)
from app.admin.period import (
    DateRange,
    change_percent,
    fill_daily_series,
    resolve_date_range,
    rollup_daily,
)
from app.audit.service import AuditService
from app.core.config import settings
from app.models.ai import AiCredentialStatus, AiUsage, UserAiCredential
from app.models.audit import AuditAction, AuditLog
from app.models.document import (
    Attachment,
    Document,
    DocumentViewEvent,
    IngestionJob,
    IngestionJobError,
    IngestionJobStatus,
)
from app.models.source import Source
from app.models.space import Space, SpaceStatus
from app.models.user import User, UserStatus
from app.models.workspace import Workspace, WorkspaceStatus


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


class AdminService:
    """Platform ops metadata only — no document content access."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.audit = AuditService(db)

    def _dialect(self) -> str:
        bind = self.db.get_bind()
        if bind is not None:
            return bind.dialect.name
        return "postgresql"

    def _local_day(self, col):
        if self._dialect() == "sqlite":
            return func.date(col)
        return cast(col.op("AT TIME ZONE")("Asia/Ho_Chi_Minh"), Date)

    async def _count(self, stmt) -> int:
        return int((await self.db.execute(stmt)).scalar_one() or 0)

    async def _count_created(
        self,
        model,
        start: datetime,
        end: datetime,
        *extra,
    ) -> int:
        return await self._count(
            select(func.count())
            .select_from(model)
            .where(model.created_at >= start, model.created_at <= end, *extra)
        )

    async def _daily_created(
        self,
        model,
        rng: DateRange,
        *extra,
    ) -> dict[date, int]:
        day_expr = self._local_day(model.created_at)
        rows = (
            await self.db.execute(
                select(day_expr.label("day"), func.count().label("n"))
                .where(model.created_at >= rng.start, model.created_at <= rng.end, *extra)
                .group_by(day_expr)
            )
        ).all()
        return {_as_date(row[0]): int(row[1] or 0) for row in rows if row[0] is not None}

    def _kpi(
        self,
        *,
        key: str,
        label: str,
        value: int,
        period_value: int,
        previous_period_value: int,
        sparkline: list[dict[str, object]],
    ) -> dict[str, Any]:
        pct, has = change_percent(period_value, previous_period_value)
        return {
            "key": key,
            "label": label,
            "value": value,
            "period_value": period_value,
            "previous_period_value": previous_period_value,
            "change_percent": pct,
            "has_comparison": has,
            "sparkline": sparkline,
        }

    async def overview(self, rng: DateRange | None = None) -> dict:
        rng = rng or resolve_date_range(None, None)
        user_count = await self._count(select(func.count()).select_from(User))
        active_user_count = await self._count(
            select(func.count()).select_from(User).where(User.status == UserStatus.ACTIVE)
        )
        suspended_user_count = await self._count(
            select(func.count()).select_from(User).where(User.status == UserStatus.SUSPENDED)
        )
        ws_filters = (Workspace.deleted_at.is_(None), Workspace.status != WorkspaceStatus.DELETED)
        space_filters = (Space.deleted_at.is_(None), Space.status != SpaceStatus.DELETED)
        workspace_count = await self._count(
            select(func.count()).select_from(Workspace).where(*ws_filters)
        )
        space_count = await self._count(
            select(func.count()).select_from(Space).where(*space_filters)
        )
        source_count = await self._count(
            select(func.count()).select_from(Source).where(Source.deleted_at.is_(None))
        )
        document_count = await self._count(
            select(func.count()).select_from(Document).where(Document.deleted_at.is_(None))
        )
        running_job_count = await self._count(
            select(func.count())
            .select_from(IngestionJob)
            .where(
                IngestionJob.status.in_(
                    [
                        IngestionJobStatus.QUEUED,
                        IngestionJobStatus.RUNNING,
                        IngestionJobStatus.CANCEL_REQUESTED,
                    ]
                )
            )
        )
        usage_row = (
            await self.db.execute(
                select(
                    func.count(AiUsage.id),
                    func.coalesce(func.sum(AiUsage.input_tokens), 0),
                    func.coalesce(func.sum(AiUsage.output_tokens), 0),
                )
            )
        ).one()

        user_period = await self._count_created(User, rng.start, rng.end)
        user_prev = await self._count_created(User, rng.previous_start, rng.previous_end)
        ws_period = await self._count_created(Workspace, rng.start, rng.end, *ws_filters)
        ws_prev = await self._count_created(
            Workspace, rng.previous_start, rng.previous_end, *ws_filters
        )
        space_period = await self._count_created(Space, rng.start, rng.end, *space_filters)
        space_prev = await self._count_created(
            Space, rng.previous_start, rng.previous_end, *space_filters
        )
        doc_period = await self._count_created(
            Document, rng.start, rng.end, Document.deleted_at.is_(None)
        )
        doc_prev = await self._count_created(
            Document, rng.previous_start, rng.previous_end, Document.deleted_at.is_(None)
        )
        ai_period = await self._count_created(AiUsage, rng.start, rng.end)
        ai_prev = await self._count_created(AiUsage, rng.previous_start, rng.previous_end)

        days = rng.dates()
        kpis = [
            self._kpi(
                key="users",
                label="Total Users",
                value=user_count,
                period_value=user_period,
                previous_period_value=user_prev,
                sparkline=fill_daily_series(days, await self._daily_created(User, rng)),
            ),
            self._kpi(
                key="workspaces",
                label="Workspaces",
                value=workspace_count,
                period_value=ws_period,
                previous_period_value=ws_prev,
                sparkline=fill_daily_series(
                    days, await self._daily_created(Workspace, rng, *ws_filters)
                ),
            ),
            self._kpi(
                key="spaces",
                label="Spaces",
                value=space_count,
                period_value=space_period,
                previous_period_value=space_prev,
                sparkline=fill_daily_series(
                    days, await self._daily_created(Space, rng, *space_filters)
                ),
            ),
            self._kpi(
                key="documents",
                label="Documents",
                value=document_count,
                period_value=doc_period,
                previous_period_value=doc_prev,
                sparkline=fill_daily_series(
                    days, await self._daily_created(Document, rng, Document.deleted_at.is_(None))
                ),
            ),
            self._kpi(
                key="ai_queries",
                label="AI Queries",
                value=int(usage_row[0] or 0),
                period_value=ai_period,
                previous_period_value=ai_prev,
                sparkline=fill_daily_series(days, await self._daily_created(AiUsage, rng)),
            ),
        ]
        return {
            "user_count": user_count,
            "active_user_count": active_user_count,
            "suspended_user_count": suspended_user_count,
            "workspace_count": workspace_count,
            "space_count": space_count,
            "source_count": source_count,
            "document_count": document_count,
            "running_job_count": running_job_count,
            "ai_message_count": int(usage_row[0] or 0),
            "ai_input_tokens": int(usage_row[1] or 0),
            "ai_output_tokens": int(usage_row[2] or 0),
            "timezone": rng.timezone,
            "range_start": rng.start,
            "range_end": rng.end,
            "previous_range_start": rng.previous_start,
            "previous_range_end": rng.previous_end,
            "range_start_date": rng.start_date.isoformat(),
            "range_end_date": rng.end_date.isoformat(),
            "previous_range_start_date": rng.previous_start_date.isoformat(),
            "previous_range_end_date": rng.previous_end_date.isoformat(),
            "kpis": kpis,
        }

    async def activity_series(self, rng: DateRange, granularity: str) -> dict:
        days = rng.dates()
        docs = await self._daily_created(Document, rng, Document.deleted_at.is_(None))
        queries = await self._daily_created(AiUsage, rng)
        users = await self._daily_created(User, rng)
        daily = [
            {
                "date": d.isoformat(),
                "documents": int(docs.get(d, 0)),
                "ai_queries": int(queries.get(d, 0)),
                "users": int(users.get(d, 0)),
            }
            for d in days
        ]
        points = rollup_daily(daily, granularity)
        return {
            "granularity": granularity,
            "timezone": rng.timezone,
            "range_start": rng.start,
            "range_end": rng.end,
            "points": points,
        }

    async def source_distribution(self) -> dict:
        rows = (
            await self.db.execute(
                select(Source.type, func.count())
                .where(Source.deleted_at.is_(None))
                .group_by(Source.type)
            )
        ).all()
        counts: dict[str, int] = {key: 0 for key, _label in source_bucket_labels()}
        for source_type, n in rows:
            bucket = source_bucket(source_type)
            counts[bucket] = counts.get(bucket, 0) + int(n or 0)
        total = sum(counts.values())
        items = []
        for key, label in source_bucket_labels():
            count = counts.get(key, 0)
            percent = round((count / total) * 100, 1) if total else 0.0
            items.append({"key": key, "label": label, "count": count, "percent": percent})
        return {"total": total, "items": items}

    async def ai_usage_summary(self, rng: DateRange, period: str) -> dict:
        row = (
            await self.db.execute(
                select(
                    func.count(AiUsage.id),
                    func.coalesce(func.sum(AiUsage.input_tokens), 0),
                    func.coalesce(func.sum(AiUsage.output_tokens), 0),
                ).where(AiUsage.created_at >= rng.start, AiUsage.created_at <= rng.end)
            )
        ).one()
        input_tokens = int(row[1] or 0)
        output_tokens = int(row[2] or 0)
        return {
            "period": period,
            "timezone": rng.timezone,
            "range_start": rng.start,
            "range_end": rng.end,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "message_count": int(row[0] or 0),
        }

    async def recent_activity(self, *, limit: int = 8) -> dict:
        cap = min(max(limit, 1), 20)
        total = await self._count(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action.in_(RECENT_ACTIVITY_ACTIONS))
        )
        result = await self.db.execute(
            select(AuditLog, User.display_name, User.email)
            .outerjoin(User, User.id == AuditLog.actor_user_id)
            .where(AuditLog.action.in_(RECENT_ACTIVITY_ACTIONS))
            .order_by(AuditLog.created_at.desc())
            .limit(cap)
        )
        items = []
        for log, display_name, email in result.all():
            meta = sanitize_metadata(log.metadata_json_sanitized)
            items.append(
                {
                    "id": log.id,
                    "action": log.action,
                    "message": format_activity_message(log.action, meta),
                    "actor_name": actor_display(display_name, email),
                    "created_at": log.created_at,
                }
            )
        return {"items": items, "total": total}

    async def top_documents(self, *, limit: int = 8) -> dict:
        cap = min(max(limit, 1), 50)
        view_total = await self._count(select(func.count()).select_from(DocumentViewEvent))
        rows = (
            await self.db.execute(
                select(
                    Document.id,
                    Document.title,
                    Document.origin,
                    Workspace.name,
                    Space.name,
                    func.count(DocumentViewEvent.id),
                    func.max(DocumentViewEvent.created_at),
                )
                .join(DocumentViewEvent, DocumentViewEvent.document_id == Document.id)
                .join(Workspace, Workspace.id == Document.workspace_id)
                .join(Space, Space.id == Document.space_id)
                .where(Document.deleted_at.is_(None))
                .group_by(Document.id, Document.title, Document.origin, Workspace.name, Space.name)
                .order_by(
                    func.count(DocumentViewEvent.id).desc(),
                    func.max(DocumentViewEvent.created_at).desc(),
                )
                .limit(cap)
            )
        ).all()
        items = [
            {
                "id": row[0],
                "title": row[1],
                "source_type": row[2] or "OTHER",
                "workspace_name": row[3],
                "space_name": row[4],
                "views": int(row[5] or 0),
                "last_viewed_at": row[6],
            }
            for row in rows
        ]
        return {"views_tracked": True, "items": items if view_total else []}

    async def system_health(self) -> dict:
        items = [
            await self._health_indexing(),
            await self._health_ai_service(),
            await self._health_storage(),
            await self._health_api_latency(),
            await self._health_error_rate(),
        ]
        return {"timezone": "Asia/Ho_Chi_Minh", "items": items}

    async def _health_indexing(self) -> dict:
        try:
            pending = await self._count(
                select(func.count())
                .select_from(Document)
                .where(Document.deleted_at.is_(None), Document.status.in_(["PENDING"]))
            )
            running = await self._count(
                select(func.count())
                .select_from(IngestionJob)
                .where(
                    IngestionJob.status.in_(
                        [IngestionJobStatus.QUEUED, IngestionJobStatus.RUNNING]
                    )
                )
            )
            errors = await self._count(
                select(func.count())
                .select_from(Document)
                .where(Document.deleted_at.is_(None), Document.status == "ERROR")
            )
        except Exception:  # noqa: BLE001
            return {
                "key": "indexing",
                "label": "Document indexing",
                "status": "unknown",
                "detail": "Could not verify indexing status",
                "verified": False,
            }
        if errors and errors >= max(pending, 1):
            status_value = "degraded"
            detail = f"{errors} documents in error"
        elif running or pending:
            status_value = "warning"
            detail = f"Indexing in progress ({pending} pending, {running} jobs)"
        else:
            status_value = "healthy"
            detail = "Up to date"
        return {
            "key": "indexing",
            "label": "Document indexing",
            "status": status_value,
            "detail": detail,
            "verified": True,
        }

    async def _health_ai_service(self) -> dict:
        embedding_ok: bool | None = None
        try:
            url = f"{settings.embedding_service_url.rstrip('/')}/health"
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(url)
                embedding_ok = resp.status_code < 500
        except Exception:  # noqa: BLE001
            embedding_ok = False

        connected = await self._count(
            select(func.count())
            .select_from(UserAiCredential)
            .where(UserAiCredential.status == AiCredentialStatus.CONNECTED)
        )
        invalid = await self._count(
            select(func.count())
            .select_from(UserAiCredential)
            .where(UserAiCredential.status == AiCredentialStatus.INVALID)
        )

        if embedding_ok is False:
            return {
                "key": "ai",
                "label": "AI service",
                "status": "offline" if connected == 0 else "degraded",
                "detail": "Embedding service unreachable",
                "verified": True,
            }
        if embedding_ok and invalid and not connected:
            return {
                "key": "ai",
                "label": "AI service",
                "status": "warning",
                "detail": "Connected keys need revalidation",
                "verified": True,
            }
        if embedding_ok:
            return {
                "key": "ai",
                "label": "AI service",
                "status": "healthy",
                "detail": "Operational",
                "verified": True,
            }
        return {
            "key": "ai",
            "label": "AI service",
            "status": "unknown",
            "detail": "Could not verify AI service",
            "verified": False,
        }

    async def _health_storage(self) -> dict:
        try:
            used = int(
                (
                    await self.db.execute(
                        select(func.coalesce(func.sum(Attachment.size_bytes), 0))
                    )
                ).scalar_one()
                or 0
            )
        except Exception:  # noqa: BLE001
            return {
                "key": "storage",
                "label": "Storage usage",
                "status": "unknown",
                "detail": "Could not verify storage usage",
                "verified": False,
            }
        quota = getattr(settings, "admin_storage_quota_bytes", None)
        percent = round((used / quota) * 100, 1) if quota else None
        if percent is not None and percent >= 95:
            status_value = "degraded"
        elif percent is not None and percent >= 80:
            status_value = "warning"
        else:
            status_value = "healthy"
        detail = _format_bytes(used) if percent is None else f"{percent:.0f}% used"
        return {
            "key": "storage",
            "label": "Storage usage",
            "status": status_value,
            "detail": detail,
            "verified": True,
            "used_bytes": used,
            "used_percent": percent,
        }

    async def _health_api_latency(self) -> dict:
        started = time.perf_counter()
        try:
            await self.db.execute(select(1))
            elapsed_ms = (time.perf_counter() - started) * 1000
        except Exception:  # noqa: BLE001
            return {
                "key": "api_latency",
                "label": "API response time",
                "status": "offline",
                "detail": "Database unreachable",
                "verified": True,
            }
        if elapsed_ms > 2000:
            status_value = "degraded"
        elif elapsed_ms > 500:
            status_value = "warning"
        else:
            status_value = "healthy"
        return {
            "key": "api_latency",
            "label": "API response time",
            "status": status_value,
            "detail": f"{elapsed_ms:.0f} ms",
            "verified": True,
            "value": round(elapsed_ms, 1),
        }

    async def _health_error_rate(self) -> dict:
        window_start = datetime.now(UTC) - timedelta(days=7)
        try:
            total_jobs = await self._count(
                select(func.count())
                .select_from(IngestionJob)
                .where(IngestionJob.created_at >= window_start)
            )
            failed_jobs = await self._count(
                select(func.count())
                .select_from(IngestionJob)
                .where(
                    IngestionJob.created_at >= window_start,
                    IngestionJob.status.in_(
                        [IngestionJobStatus.FAILED, IngestionJobStatus.COMPLETED_WITH_ERRORS]
                    ),
                )
            )
            error_rows = await self._count(
                select(func.count())
                .select_from(IngestionJobError)
                .where(IngestionJobError.created_at >= window_start)
            )
        except Exception:  # noqa: BLE001
            return {
                "key": "error_rate",
                "label": "Error rate (7d)",
                "status": "unknown",
                "detail": "Could not verify error rate",
                "verified": False,
            }
        if total_jobs == 0 and error_rows == 0:
            return {
                "key": "error_rate",
                "label": "Error rate (7d)",
                "status": "unknown",
                "detail": "No ingestion jobs in 7d",
                "verified": True,
            }
        rate = (failed_jobs / total_jobs) if total_jobs else 0.0
        percent = round(rate * 100, 2)
        if percent >= 5:
            status_value = "degraded"
        elif percent >= 1:
            status_value = "warning"
        else:
            status_value = "healthy"
        return {
            "key": "error_rate",
            "label": "Error rate (7d)",
            "status": status_value,
            "detail": f"{percent:.2f}%",
            "verified": True,
            "value": percent,
        }

    async def export_overview(self, rng: DateRange) -> str:
        overview = await self.overview(rng)
        sources = await self.source_distribution()
        usage = await self.ai_usage_summary(rng, "custom")
        lines = [
            "section,metric,value",
            f"range,start,{rng.start_date.isoformat()}",
            f"range,end,{rng.end_date.isoformat()}",
            f"range,timezone,{rng.timezone}",
            f"users,total,{overview['user_count']}",
            f"users,active,{overview['active_user_count']}",
            f"users,suspended,{overview['suspended_user_count']}",
            f"workspaces,total,{overview['workspace_count']}",
            f"spaces,total,{overview['space_count']}",
            f"documents,total,{overview['document_count']}",
            f"ai,queries,{overview['ai_message_count']}",
            f"ai,input_tokens,{usage['input_tokens']}",
            f"ai,output_tokens,{usage['output_tokens']}",
            f"ai,total_tokens,{usage['total_tokens']}",
            f"sources,total,{sources['total']}",
        ]
        for item in sources["items"]:
            lines.append(f"sources,{item['key']},{item['count']}")
        for kpi in overview["kpis"]:
            change = kpi["change_percent"] if kpi["has_comparison"] else ""
            lines.append(f"kpi,{kpi['key']}_period,{kpi['period_value']}")
            lines.append(f"kpi,{kpi['key']}_change_percent,{change}")
        return "\n".join(lines) + "\n"

    async def list_users(
        self, *, q: str | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[User], int]:
        filters = []
        if q:
            term = f"%{q.strip().lower()}%"
            filters.append(
                or_(func.lower(User.email).like(term), func.lower(User.display_name).like(term))
            )
        total = int(
            (
                await self.db.execute(
                    select(func.count()).select_from(User).where(*filters)
                )
            ).scalar_one()
            or 0
        )
        result = await self.db.execute(
            select(User)
            .where(*filters)
            .order_by(User.created_at.desc())
            .limit(min(limit, 100))
            .offset(max(offset, 0))
        )
        return list(result.scalars().all()), total

    async def set_user_status(
        self, actor: User, target_id: UUID, *, status_value: str
    ) -> User:
        if actor.id == target_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "CANNOT_SUSPEND_SELF", "message": "Cannot change your own status."},
            )
        target = await self.db.get(User, target_id)
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "USER_NOT_FOUND", "message": "User not found."},
            )
        if target.is_super_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "CANNOT_MODIFY_ADMIN",
                    "message": "Cannot suspend another Super Admin.",
                },
            )
        if status_value not in {UserStatus.ACTIVE, UserStatus.SUSPENDED}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_STATUS", "message": "Status must be ACTIVE or SUSPENDED."},
            )
        if target.status == status_value:
            return target
        target.status = status_value
        await self.audit.log(
            action=(
                AuditAction.SUSPEND_USER
                if status_value == UserStatus.SUSPENDED
                else AuditAction.UNSUSPEND_USER
            ),
            resource_type="user",
            actor_user_id=actor.id,
            resource_id=target.id,
            metadata={"email": target.email, "status": status_value},
        )
        await self.db.commit()
        await self.db.refresh(target)
        return target

    async def list_audit_logs(
        self,
        *,
        action: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[AuditLog, str | None]], int]:
        filters = []
        if action:
            filters.append(AuditLog.action == action)
        total = int(
            (
                await self.db.execute(
                    select(func.count()).select_from(AuditLog).where(*filters)
                )
            ).scalar_one()
            or 0
        )
        result = await self.db.execute(
            select(AuditLog, User.email)
            .outerjoin(User, User.id == AuditLog.actor_user_id)
            .where(*filters)
            .order_by(AuditLog.created_at.desc())
            .limit(min(limit, 100))
            .offset(max(offset, 0))
        )
        return [(row[0], row[1]) for row in result.all()], total

    async def usage_summary(self, *, limit: int = 50) -> dict:
        rows = (
            await self.db.execute(
                select(
                    AiUsage.user_id,
                    User.email,
                    AiUsage.workspace_id,
                    func.count(AiUsage.id),
                    func.coalesce(func.sum(AiUsage.input_tokens), 0),
                    func.coalesce(func.sum(AiUsage.output_tokens), 0),
                )
                .join(User, User.id == AiUsage.user_id)
                .group_by(AiUsage.user_id, User.email, AiUsage.workspace_id)
                .order_by(func.sum(AiUsage.input_tokens).desc())
                .limit(min(limit, 100))
            )
        ).all()
        items = [
            {
                "user_id": r[0],
                "user_email": r[1],
                "workspace_id": r[2],
                "message_count": int(r[3] or 0),
                "input_tokens": int(r[4] or 0),
                "output_tokens": int(r[5] or 0),
            }
            for r in rows
        ]
        totals = (
            await self.db.execute(
                select(
                    func.count(AiUsage.id),
                    func.coalesce(func.sum(AiUsage.input_tokens), 0),
                    func.coalesce(func.sum(AiUsage.output_tokens), 0),
                )
            )
        ).one()
        return {
            "items": items,
            "total_messages": int(totals[0] or 0),
            "total_input_tokens": int(totals[1] or 0),
            "total_output_tokens": int(totals[2] or 0),
        }


def _format_bytes(n: int) -> str:
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} B used"
            return f"{value:.1f} {unit} used"
        value /= 1024
    return f"{n} B used"
