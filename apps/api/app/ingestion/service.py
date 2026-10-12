from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.audit.service import AuditService
from app.confluence.client import ConfluenceClient, ConfluenceClientError, normalize_ancestors
from app.confluence.ssrf import SsrfBlocked, assert_public_url, ssrf_http_exception
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import decrypt_secret
from app.ingestion.embeddings import embed_texts
from app.ingestion.export_md import (
    MAX_EXPORT_PAGES,
    ExportPage,
    build_md_zip,
    preview_export_file_counts,
    safe_slug,
)
from app.ingestion.normalize import (
    HeadingChunkPiece,
    build_embed_prefix,
    build_embed_text,
    chunk_html_by_headings,
    chunk_text,
    content_checksum,
    html_to_text,
    is_drawio_filename,
    replace_confluence_images,
    replace_drawio_macros_with_images,
    rewrite_attachment_urls,
    sanitize_html,
)
from app.ingestion.progress import (
    complete_all_stages,
    empty_progress,
    estimate_eta_seconds,
    mark_stage,
    push_current_item,
    set_stage_status,
)
from app.ingestion.storage import get_object_storage, safe_object_filename
from app.ingestion.sync import SyncPlan, compute_next_sync_at, compute_sync_plan
from app.models.agent import ConnectorJob, JobStatus, JobType
from app.models.audit import AuditAction
from app.models.confluence import (
    ConnectionMode,
    ConfluenceConnection,
    CredentialLocation,
)
from app.models.document import (
    INDEXABLE_DOCUMENT_TYPES,
    Attachment,
    Document,
    DocumentChunk,
    DocumentOrigin,
    DocumentStatus,
    DocumentType,
    IngestionJob,
    IngestionJobError,
    IngestionJobStatus,
    IngestionJobType,
    IngestionStage,
)
from app.models.source import (
    FILE_SOURCE_TYPES,
    SYNCABLE_SOURCE_TYPES,
    Source,
    SourceExternalType,
    SourceStatus,
    SourceType,
    SyncInterval,
    SyncStatus,
)
from app.models.space import Space, SpaceRole
from app.models.user import User
from app.models.workspace import WorkspaceRole
from app.permissions.service import PermissionService
import json

logger = logging.getLogger(__name__)

# Avoid holding multi-GB of attachments in RAM (root cause of "hang" on large spaces).
MAX_ATTACHMENT_BYTES = 40 * 1024 * 1024
# Limit parallel Confluence downloads per page.
ATTACHMENT_FETCH_CONCURRENCY = 4
# Don't commit progress JSON on every tiny step (SQLite/OneDrive thrash).
PROGRESS_MIN_INTERVAL_SEC = 1.5


class IngestionCancelled(Exception):
    pass



def _map_confluence_error_code(exc: ConfluenceClientError) -> str:
    if getattr(exc, "code", None):
        return str(exc.code)
    msg = (exc.message or "").lower()
    if "anonymous" in msg or "session" in msg:
        return "CONFLUENCE_SESSION_EXPIRED"
    if exc.status_code in {401, 403}:
        return "CONFLUENCE_AUTH_FAILED"
    if exc.status_code in {301, 302, 303, 307, 308}:
        return "CONFLUENCE_SESSION_EXPIRED"
    if exc.status_code == 404:
        return "SOURCE_NOT_FOUND"
    return "IMPORT_FAILED"


class IngestionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.permissions = PermissionService(db)
        self.audit = AuditService(db)
        self._last_progress_mono: float = 0.0

    @classmethod
    def reader(cls, db: AsyncSession) -> IngestionService:
        """Read-only helper — skips __init__ so stale bytecode cannot break job/document reads."""
        svc = cls.__new__(cls)
        svc.db = db
        svc.permissions = PermissionService(db)
        svc.audit = AuditService(db)
        svc._last_progress_mono = 0.0
        return svc

    async def start_import(
        self,
        user: User,
        source_id: UUID,
        *,
        options: dict[str, Any] | None = None,
    ) -> IngestionJob:
        source = await self._get_source(source_id)
        await self.permissions.require_space_access(source.space_id, user.id, SpaceRole.EDITOR)
        if source.status == SourceStatus.IMPORTING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "IMPORT_IN_PROGRESS", "message": "Import already running."},
            )

        if options:
            cfg = dict(source.config_json or {})
            cfg["import_options"] = {**(cfg.get("import_options") or {}), **options}
            source.config_json = cfg
            flag_modified(source, "config_json")

        if source.type == SourceType.CONFLUENCE:
            return await self._start_confluence_import(user, source)
        if source.type == SourceType.JIRA:
            return await self._start_jira_import(user, source)
        if source.type in FILE_SOURCE_TYPES:
            return await self._start_file_import(user, source)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "UNSUPPORTED_SOURCE", "message": f"Cannot import source type {source.type}."},
        )

    async def _start_confluence_import(self, user: User, source: Source) -> IngestionJob:
        if not source.connection_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "NO_CONNECTION", "message": "Source has no connection."},
            )
        conn = await self._get_connection(source.connection_id)

        job = IngestionJob(
            id=uuid4(),
            workspace_id=source.workspace_id,
            space_id=source.space_id,
            source_id=source.id,
            job_type=IngestionJobType.IMPORT,
            status=IngestionJobStatus.QUEUED,
            stage=IngestionStage.QUEUED,
            progress_percent=0.0,
            requested_by_user_id=user.id,
            connector_agent_id=conn.connector_agent_id,
            progress_json=empty_progress(source_type=source.type),
        )
        space = await self.db.get(Space, source.space_id)
        prog = job.progress_json or empty_progress(source_type=source.type)
        prog["started_by_name"] = user.display_name or user.email
        prog["import_mode"] = source.import_scope or "SPACE_TREE"
        prog["destination_name"] = space.name if space else None
        prog["source_type"] = source.type
        prog["source_name"] = source.name
        mark_stage(prog, "CONNECTING")
        job.progress_json = prog
        flag_modified(job, "progress_json")
        source.status = SourceStatus.IMPORTING
        self.db.add(job)
        await self.audit.log(
            action=AuditAction.START_INGESTION,
            resource_type="ingestion_job",
            actor_user_id=user.id,
            workspace_id=source.workspace_id,
            resource_id=job.id,
            metadata={"source_id": str(source.id)},
        )
        await self.db.commit()
        await self.db.refresh(job)

        if conn.connection_mode == ConnectionMode.LOCAL_AGENT:
            await self._enqueue_agent_fetch(job, source, conn)
        else:
            await self._dispatch_direct(job.id)

        return job

    async def _start_jira_import(self, user: User, source: Source) -> IngestionJob:
        if not source.jira_connection_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "NO_CONNECTION", "message": "Source has no Jira connection."},
            )
        return await self._enqueue_typed_job(user, source, job_type=IngestionJobType.IMPORT)

    async def _start_file_import(self, user: User, source: Source) -> IngestionJob:
        return await self._enqueue_typed_job(user, source, job_type=IngestionJobType.IMPORT)

    async def _enqueue_typed_job(
        self,
        user: User,
        source: Source,
        *,
        job_type: str,
    ) -> IngestionJob:
        from app.ingestion.progress import progress_for_source

        job = IngestionJob(
            id=uuid4(),
            workspace_id=source.workspace_id,
            space_id=source.space_id,
            source_id=source.id,
            job_type=job_type,
            status=IngestionJobStatus.QUEUED,
            stage=IngestionStage.QUEUED,
            progress_percent=0.0,
            requested_by_user_id=user.id,
            progress_json=progress_for_source(source.type),
        )
        space = await self.db.get(Space, source.space_id)
        prog = job.progress_json or progress_for_source(source.type)
        prog["started_by_name"] = user.display_name or user.email
        prog["import_mode"] = source.import_scope or source.type
        prog["destination_name"] = space.name if space else None
        prog["source_type"] = source.type
        prog["source_name"] = source.name
        stages = prog.get("stages") or []
        if stages:
            mark_stage(prog, stages[0]["key"])
        job.progress_json = prog
        flag_modified(job, "progress_json")
        source.status = SourceStatus.IMPORTING
        source.error_code = None
        source.error_message = None
        self.db.add(job)
        await self.audit.log(
            action=AuditAction.START_INGESTION,
            resource_type="ingestion_job",
            actor_user_id=user.id,
            workspace_id=source.workspace_id,
            resource_id=job.id,
            metadata={"source_id": str(source.id), "source_type": source.type},
        )
        await self.db.commit()
        await self.db.refresh(job)
        await self._dispatch_direct(job.id)
        return job

    async def start_import_legacy_confluence(self, user: User, source_id: UUID) -> IngestionJob:
        """Deprecated shim — use start_import."""
        return await self.start_import(user, source_id)

    async def start_sync(
        self,
        user: User,
        source_id: UUID,
        *,
        triggered_by: str = "USER",
    ) -> IngestionJob:
        source = await self._get_source(source_id)
        await self.permissions.require_space_access(source.space_id, user.id, SpaceRole.EDITOR)
        if source.type not in SYNCABLE_SOURCE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "NOT_SYNCABLE",
                    "message": "This source type does not support sync. Upload a new version instead.",
                },
            )
        if source.status not in {SourceStatus.READY, SourceStatus.SYNCED, SourceStatus.INDEXED}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "SOURCE_NOT_READY",
                    "message": "Run a full import before syncing.",
                },
            )
        if source.status == SourceStatus.IMPORTING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "SYNC_IN_PROGRESS", "message": "Sync already running."},
            )
        if source.type == SourceType.JIRA:
            return await self._enqueue_typed_job(user, source, job_type=IngestionJobType.SYNC)
        if not source.connection_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "NO_CONNECTION", "message": "Source has no connection."},
            )
        conn = await self._get_connection(source.connection_id)

        job = IngestionJob(
            id=uuid4(),
            workspace_id=source.workspace_id,
            space_id=source.space_id,
            source_id=source.id,
            job_type=IngestionJobType.SYNC,
            status=IngestionJobStatus.QUEUED,
            stage=IngestionStage.QUEUED,
            progress_percent=0.0,
            requested_by_user_id=user.id,
            connector_agent_id=conn.connector_agent_id,
            progress_json=empty_progress(source_type=source.type),
        )
        space = await self.db.get(Space, source.space_id)
        prog = job.progress_json or empty_progress()
        prog["started_by_name"] = user.display_name or user.email
        prog["import_mode"] = source.import_scope or "SPACE_TREE"
        prog["destination_name"] = space.name if space else None
        prog["source_type"] = source.type
        prog["source_name"] = source.name
        prog["sync_trigger"] = triggered_by
        prog["sync_stats"] = {
            "added": 0,
            "updated": 0,
            "removed": 0,
            "unchanged": 0,
            "failed": 0,
        }
        mark_stage(prog, "CONNECTING")
        job.progress_json = prog
        flag_modified(job, "progress_json")
        source.status = SourceStatus.IMPORTING
        self.db.add(job)
        await self.audit.log(
            action=AuditAction.START_INGESTION,
            resource_type="ingestion_job",
            actor_user_id=user.id,
            workspace_id=source.workspace_id,
            resource_id=job.id,
            metadata={"job_type": IngestionJobType.SYNC, "source_id": str(source.id)},
        )
        await self.db.commit()
        await self.db.refresh(job)

        if conn.connection_mode == ConnectionMode.LOCAL_AGENT:
            await self._enqueue_agent_fetch(job, source, conn, scan_only=True)
        else:
            await self._dispatch_direct(job.id)

        return job

    async def update_sync_settings(
        self,
        user: User,
        source_id: UUID,
        *,
        sync_enabled: bool,
        sync_interval: str,
    ) -> Source:
        source = await self._get_source(source_id)
        await self.permissions.require_space_access(source.space_id, user.id, SpaceRole.EDITOR)
        if sync_interval not in {
            SyncInterval.OFF,
            SyncInterval.HOURLY,
            SyncInterval.DAILY,
        }:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_INTERVAL", "message": "Invalid sync interval."},
            )
        source.sync_enabled = sync_enabled and sync_interval != SyncInterval.OFF
        source.sync_interval = sync_interval if source.sync_enabled else SyncInterval.OFF
        if source.sync_enabled:
            source.next_sync_at = compute_next_sync_at(source.sync_interval)
        else:
            source.next_sync_at = None
        await self.db.commit()
        await self.db.refresh(source)
        return source

    async def _dispatch_direct(self, job_id: UUID) -> None:
        # Pytest/ASGITransport: await inline so the job shares the request event loop
        # (create_task + AsyncSessionLocal often hits "attached to a different loop").
        if settings.app_env == "test":
            await run_ingestion_job(job_id)
            # Worker used a separate session; drop cached QUEUED rows on this session.
            self.db.expire_all()
            return
        # Demo/dev: run in API process (start.cmd does not start a Celery worker).
        if settings.demo_mode or settings.app_env == "development":
            asyncio.create_task(run_ingestion_job(job_id))
            return
        try:
            from app.worker import run_ingestion_job_task

            run_ingestion_job_task.delay(str(job_id))
        except Exception:  # noqa: BLE001
            logger.warning("Celery unavailable; running ingestion inline")
            asyncio.create_task(run_ingestion_job(job_id))

    async def _enqueue_agent_fetch(
        self,
        job: IngestionJob,
        source: Source,
        conn: ConfluenceConnection,
        *,
        scan_only: bool = False,
        page_ids: list[str] | None = None,
    ) -> None:
        if not conn.connector_agent_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "AGENT_REQUIRED",
                    "message": "LOCAL_AGENT connection needs a registered agent.",
                },
            )
        payload = {
            "ingestion_job_id": str(job.id),
            "source_id": str(source.id),
            "base_url": conn.base_url,
            "auth_type": conn.auth_type,
            "credential_location": conn.credential_location,
            "external_type": source.external_type,
            "external_id": source.external_id,
            "external_key": source.external_key,
            "import_scope": source.import_scope,
            "job_type": job.job_type,
            "scan_only": scan_only,
        }
        if page_ids:
            payload["page_ids"] = page_ids
        if conn.credential_location == CredentialLocation.CLOUD and conn.encrypted_credentials:
            raw = json.loads(decrypt_secret(conn.encrypted_credentials))
            payload["username"] = raw.get("username") or ""
            payload["secret"] = raw.get("secret") or ""
        agent_job = ConnectorJob(
            id=uuid4(),
            workspace_id=job.workspace_id,
            agent_id=conn.connector_agent_id,
            job_type=JobType.FETCH_CONFLUENCE,
            status=JobStatus.QUEUED,
            payload_json=payload,
        )
        self.db.add(agent_job)
        job.stage = IngestionStage.SCANNING
        job.message = "Waiting for Local Agent to fetch Confluence"
        await self.db.commit()

    async def get_job(self, user: User, job_id: UUID) -> IngestionJob:
        result = await self.db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
        job = result.scalar_one_or_none()
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "JOB_NOT_FOUND", "message": "Ingestion job not found."},
            )
        await self.permissions.require_space_access(job.space_id, user.id, SpaceRole.VIEWER)
        return job

    async def get_latest_job_for_source(self, user: User, source_id: UUID) -> IngestionJob | None:
        source = await self._get_source(source_id)
        await self.permissions.require_space_access(source.space_id, user.id, SpaceRole.VIEWER)
        result = await self.db.execute(
            select(IngestionJob)
            .where(IngestionJob.source_id == source_id)
            .order_by(IngestionJob.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def cancel_job(self, user: User, job_id: UUID) -> IngestionJob:
        await self.permissions.require_space_access(
            (await self.get_job(user, job_id)).space_id, user.id, SpaceRole.EDITOR
        )

        last_exc: Exception | None = None
        for attempt in range(8):
            try:
                # Fresh load each attempt — avoid stale identity-map after rollback/lock.
                job = await self.get_job(user, job_id)
                if job.status in {
                    IngestionJobStatus.COMPLETED,
                    IngestionJobStatus.COMPLETED_WITH_ERRORS,
                    IngestionJobStatus.FAILED,
                    IngestionJobStatus.CANCELLED,
                }:
                    # Already finished (including a prior successful cancel).
                    return job

                source = await self._get_source(job.source_id)
                # Always force-finish: soft CANCEL_REQUESTED left the UI stuck while the
                # worker was blocked in long indexing/embed calls (and SQLite write locks
                # made a second cancel fail).
                await self._finish_cancelled(job, source)
                await self.db.refresh(job)
                return job
            except HTTPException:
                raise
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                msg = str(exc).lower()
                if "locked" in msg or "busy" in msg:
                    logger.warning(
                        "Cancel job %s hit DB lock (attempt %s/8): %s",
                        job_id,
                        attempt + 1,
                        exc,
                    )
                    try:
                        await self.db.rollback()
                    except Exception:  # noqa: BLE001
                        pass
                    await asyncio.sleep(0.15 * (attempt + 1))
                    continue
                raise

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "CANCEL_BUSY",
                "message": "Could not cancel while import is writing. Try again in a moment.",
            },
        ) from last_exc

    async def _raise_if_cancelled(self, job: IngestionJob) -> None:
        """Read cancel state from DB (not stale identity-map) and abort if needed."""
        result = await self.db.execute(
            select(IngestionJob.status, IngestionJob.progress_json).where(IngestionJob.id == job.id)
        )
        row = result.one_or_none()
        if row is None:
            return
        status_val, prog = row[0], row[1] or {}
        if status_val in {
            IngestionJobStatus.CANCEL_REQUESTED,
            IngestionJobStatus.CANCELLED,
        } or bool(prog.get("cancel_requested")):
            job.status = status_val
            raise IngestionCancelled()

    _TERMINAL_JOB_STATUSES = frozenset(
        {
            IngestionJobStatus.COMPLETED,
            IngestionJobStatus.COMPLETED_WITH_ERRORS,
            IngestionJobStatus.FAILED,
            IngestionJobStatus.CANCELLED,
        }
    )

    def serialize_job(
        self,
        job: IngestionJob,
        *,
        source: Source | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        prog = job.progress_json or empty_progress()
        stats = prog.get("stats") or {}
        return {
            "id": job.id,
            "workspace_id": job.workspace_id,
            "space_id": job.space_id,
            "source_id": job.source_id,
            "job_type": job.job_type,
            "status": job.status,
            "progress_percent": job.progress_percent,
            "stage": job.stage,
            "message": job.message,
            "connector_agent_id": job.connector_agent_id,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "source": (
                {
                    "id": source.id,
                    "name": source.name,
                    "type": source.type,
                    "import_scope": source.import_scope,
                }
                if source
                else {
                    "id": job.source_id,
                    "name": prog.get("source_name") or "Source",
                    "type": prog.get("source_type") or "CONFLUENCE",
                    "import_scope": prog.get("import_mode"),
                }
            ),
            "stats": {
                "total_pages": int(stats.get("total_pages") or 0),
                "processed_pages": int(stats.get("processed_pages") or 0),
                "total_attachments": int(stats.get("total_attachments") or 0),
                "processed_attachments": int(stats.get("processed_attachments") or 0),
                "total_diagrams": int(stats.get("total_diagrams") or 0),
                "processed_diagrams": int(stats.get("processed_diagrams") or 0),
                "failed_items": int(stats.get("failed_items") or 0),
            },
            "stages": prog.get("stages") or [],
            "current_items": prog.get("current_items") or [],
            "eta_seconds": prog.get("eta_seconds"),
            "cancel_requested": bool(prog.get("cancel_requested")),
            "started_by_name": prog.get("started_by_name"),
            "import_mode": prog.get("import_mode"),
            "destination_name": prog.get("destination_name"),
            "error_code": error_code,
            "error_message": error_message or (
                job.message if job.status == IngestionJobStatus.FAILED else None
            ),
            "sync_stats": prog.get("sync_stats"),
        }

    async def job_detail(self, user: User, job_id: UUID) -> dict[str, Any]:
        job = await self.get_job(user, job_id)
        source = await self._get_source(job.source_id)
        err_code = None
        err_msg = None
        if job.status == IngestionJobStatus.FAILED:
            result = await self.db.execute(
                select(IngestionJobError)
                .where(IngestionJobError.job_id == job.id)
                .order_by(IngestionJobError.created_at.desc())
                .limit(1)
            )
            err = result.scalar_one_or_none()
            if err:
                err_code = err.error_code
                err_msg = err.error_message_sanitized
        payload = self.serialize_job(job, source=source, error_code=err_code, error_message=err_msg)
        # Repair empty stats for finished jobs (older runs lost progress_json updates).
        if job.status in {
            IngestionJobStatus.COMPLETED,
            IngestionJobStatus.COMPLETED_WITH_ERRORS,
        }:
            stats = payload.get("stats") or {}
            if int(stats.get("processed_pages") or 0) == 0 and int(stats.get("total_pages") or 0) == 0:
                docs_count = int(
                    (
                        await self.db.execute(
                            select(func.count())
                            .select_from(Document)
                            .where(Document.source_id == source.id)
                        )
                    ).scalar_one()
                    or 0
                )
                atts_count = int(
                    (
                        await self.db.execute(
                            select(func.count())
                            .select_from(Attachment)
                            .where(Attachment.source_id == source.id)
                        )
                    ).scalar_one()
                    or 0
                )
                err_count = int(
                    (
                        await self.db.execute(
                            select(func.count())
                            .select_from(IngestionJobError)
                            .where(IngestionJobError.job_id == job.id)
                        )
                    ).scalar_one()
                    or 0
                )
                payload["stats"] = {
                    **stats,
                    "total_pages": docs_count,
                    "processed_pages": docs_count,
                    "total_attachments": max(int(stats.get("total_attachments") or 0), atts_count),
                    "processed_attachments": atts_count,
                    "failed_items": max(int(stats.get("failed_items") or 0), err_count),
                }
                # If no real failures and docs exist, treat as successful for UI.
                if err_count == 0 and docs_count > 0:
                    payload["status"] = IngestionJobStatus.COMPLETED
                elif err_count > 0 and docs_count > 0:
                    payload["status"] = IngestionJobStatus.COMPLETED_WITH_ERRORS
        return payload

    async def list_documents(
        self,
        user: User,
        space_id: UUID,
        *,
        source_id: UUID | None = None,
    ) -> list[Document]:
        await self.permissions.require_space_access(space_id, user.id, SpaceRole.VIEWER)
        filters = [
            Document.space_id == space_id,
            Document.document_type.in_(INDEXABLE_DOCUMENT_TYPES),
            Document.deleted_at.is_(None),
            or_(Document.source_id.is_(None), Source.deleted_at.is_(None)),
        ]
        if source_id is not None:
            filters.append(Document.source_id == source_id)
        result = await self.db.execute(
            select(Document)
            .outerjoin(Source, Source.id == Document.source_id)
            .where(*filters)
            .order_by(Document.title.asc())
        )
        return list(result.scalars().all())

    async def get_document(self, user: User, document_id: UUID) -> Document:
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "DOCUMENT_NOT_FOUND", "message": "Document not found."},
            )
        await self.permissions.require_space_access(doc.space_id, user.id, SpaceRole.VIEWER)
        return doc

    async def list_attachments_for_document(
        self, user: User, document_id: UUID
    ) -> list[Attachment]:
        doc = await self.get_document(user, document_id)
        result = await self.db.execute(
            select(Attachment).where(Attachment.document_id == doc.id).order_by(Attachment.filename)
        )
        return list(result.scalars().all())

    async def get_attachment(self, user: User, attachment_id: UUID) -> Attachment:
        result = await self.db.execute(select(Attachment).where(Attachment.id == attachment_id))
        att = result.scalar_one_or_none()
        if att is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ATTACHMENT_NOT_FOUND", "message": "Attachment not found."},
            )
        await self.permissions.require_space_access(att.space_id, user.id, SpaceRole.VIEWER)
        return att

    async def export_source_markdown_zip(
        self,
        user: User,
        source_id: UUID,
        *,
        group_depth: int = 2,
    ) -> tuple[bytes, str]:
        """Build a NotebookLM-ready zip of Markdown pages for one Source.

        ``group_depth``: 0 = one file per page; 1–20 = bundle under that tree level
        (lower = fewer/larger files). Default 2.
        """
        source = await self._get_source(source_id)
        await self.permissions.require_space_access(source.space_id, user.id, SpaceRole.VIEWER)

        depth = int(group_depth)
        if depth < 0 or depth > 20:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "INVALID_GROUP_DEPTH",
                    "message": "group_depth must be between 0 and 20 (0 = one file per page).",
                },
            )

        pages = await self._export_pages_for_source(source)
        data = build_md_zip(pages, source_name=source.name, group_depth=depth)
        suffix = "page" if depth <= 0 else f"L{depth}"
        filename = f"{safe_slug(source.name, fallback='source')}-export-{suffix}.zip"
        return data, filename

    async def preview_export_markdown(
        self, user: User, source_id: UUID
    ) -> dict[str, Any]:
        """Return how many zip entries each group_depth would create."""
        source = await self._get_source(source_id)
        await self.permissions.require_space_access(source.space_id, user.id, SpaceRole.VIEWER)
        pages = await self._export_pages_for_source(source)
        return {
            "source_id": str(source.id),
            "document_count": len(pages),
            "file_counts": preview_export_file_counts(pages),
        }

    async def _export_pages_for_source(self, source: Source) -> list[ExportPage]:
        result = await self.db.execute(
            select(Document).where(
                Document.source_id == source.id,
                Document.document_type.in_(
                    {
                        DocumentType.PAGE,
                        DocumentType.JIRA_ISSUE,
                        DocumentType.SHEET,
                        DocumentType.FILE,
                        DocumentType.PRESENTATION,
                    }
                ),
                Document.status == DocumentStatus.READY,
                Document.deleted_at.is_(None),
            )
        )
        docs = list(result.scalars().all())
        if not docs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "NO_PAGES_TO_EXPORT",
                    "message": "No ready documents to export for this source.",
                },
            )
        if len(docs) > MAX_EXPORT_PAGES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={
                    "code": "EXPORT_TOO_LARGE",
                    "message": (
                        f"Source has {len(docs)} documents; export is limited to "
                        f"{MAX_EXPORT_PAGES}."
                    ),
                },
            )
        return [
            ExportPage(
                id=doc.id,
                title=doc.title,
                external_url=doc.external_url,
                parent_id=doc.parent_id,
                depth=int(doc.depth or 0),
                position=int(doc.position or 0),
                raw_content=doc.raw_content,
                normalized_content=doc.normalized_content,
            )
            for doc in docs
        ]

    async def count_documents(self, space_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Document).where(Document.space_id == space_id)
        )
        return int(result.scalar_one() or 0)

    async def ingest_agent_payload(
        self,
        *,
        agent_id: UUID,
        ingestion_job_id: UUID,
        pages: list[dict[str, Any]],
        scan: bool = False,
    ) -> IngestionJob:
        result = await self.db.execute(
            select(IngestionJob).where(IngestionJob.id == ingestion_job_id)
        )
        job = result.scalar_one_or_none()
        if job is None or job.connector_agent_id != agent_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "JOB_NOT_FOUND", "message": "Ingestion job not found for agent."},
            )
        if scan or (
            job.job_type == IngestionJobType.SYNC
            and pages
            and not any(p.get("body_storage") or p.get("attachments") for p in pages)
        ):
            await self._apply_agent_sync_scan(job, pages)
            return job
        if job.job_type == IngestionJobType.SYNC:
            await self._process_sync_pages(job, pages)
        else:
            await self._process_fetched_pages(job, pages)
        return job

    async def _get_source(self, source_id: UUID) -> Source:
        result = await self.db.execute(
            select(Source).where(Source.id == source_id, Source.deleted_at.is_(None))
        )
        source = result.scalar_one_or_none()
        if source is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "SOURCE_NOT_FOUND", "message": "Source not found."},
            )
        return source

    async def _get_connection(self, connection_id: UUID) -> ConfluenceConnection:
        result = await self.db.execute(
            select(ConfluenceConnection).where(
                ConfluenceConnection.id == connection_id,
                ConfluenceConnection.deleted_at.is_(None),
            )
        )
        conn = result.scalar_one_or_none()
        if conn is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "CONNECTION_NOT_FOUND", "message": "Connection not found."},
            )
        return conn

    async def _set_progress(
        self,
        job: IngestionJob,
        *,
        stage: str,
        percent: float,
        message: str | None = None,
        status_value: str | None = None,
        ui_stage: str | None = None,
        stats: dict[str, Any] | None = None,
        current_item: dict[str, str] | None = None,
        force: bool = False,
        eta_processed: int | None = None,
        eta_total: int | None = None,
    ) -> None:
        import time

        await self._raise_if_cancelled(job)

        now = time.monotonic()
        if (
            not force
            and self._last_progress_mono
            and (now - self._last_progress_mono) < PROGRESS_MIN_INTERVAL_SEC
            and status_value is None
            and ui_stage is None
        ):
            return

        # Reload latest progress_json so we never wipe cancel_requested from another session
        await self.db.refresh(job)
        if job.status in self._TERMINAL_JOB_STATUSES:
            if job.status in {
                IngestionJobStatus.CANCEL_REQUESTED,
                IngestionJobStatus.CANCELLED,
            } or bool((job.progress_json or {}).get("cancel_requested")):
                raise IngestionCancelled()
            return
        await self._raise_if_cancelled(job)
        prog = dict(job.progress_json or empty_progress())

        job.stage = stage
        job.progress_percent = round(min(100.0, max(0.0, percent)), 1)
        if message is not None:
            job.message = message[:500]
        # Never clobber CANCEL_REQUESTED / CANCELLED / other terminal states
        if status_value and job.status not in {
            IngestionJobStatus.CANCEL_REQUESTED,
            IngestionJobStatus.CANCELLED,
            *self._TERMINAL_JOB_STATUSES,
        }:
            job.status = status_value
        if status_value == IngestionJobStatus.RUNNING and job.started_at is None:
            job.started_at = datetime.now(UTC)
        if ui_stage:
            mark_stage(prog, ui_stage)
        if stats:
            prog.setdefault("stats", {}).update(stats)
        if current_item:
            push_current_item(
                prog,
                name=current_item.get("name") or "Item",
                item_status=current_item.get("status") or "importing",
                item_type=current_item.get("type") or "PAGE",
            )
        st = prog.get("stats") or {}
        total = eta_total if eta_total is not None else int(st.get("total_pages") or 0)
        processed = (
            eta_processed if eta_processed is not None else int(st.get("processed_pages") or 0)
        )
        prog["eta_seconds"] = estimate_eta_seconds(
            processed=processed, total=total, started_at=job.started_at
        )
        # Preserve cancel flag if set concurrently
        if job.status == IngestionJobStatus.CANCEL_REQUESTED:
            prog["cancel_requested"] = True
        job.progress_json = prog
        flag_modified(job, "progress_json")

        # Final race check: another session may have force-cancelled while we built progress.
        result = await self.db.execute(
            select(IngestionJob.status).where(IngestionJob.id == job.id)
        )
        latest_status = result.scalar_one_or_none()
        if latest_status in self._TERMINAL_JOB_STATUSES:
            await self.db.rollback()
            if latest_status == IngestionJobStatus.CANCELLED:
                raise IngestionCancelled()
            return

        await self.db.commit()
        await self.db.refresh(job)
        self._last_progress_mono = time.monotonic()

    async def _finish_cancelled(self, job: IngestionJob, source: Source) -> None:
        await self.db.refresh(job)
        if job.status == IngestionJobStatus.CANCELLED and job.completed_at is not None:
            return
        job.status = IngestionJobStatus.CANCELLED
        job.stage = IngestionStage.DONE
        job.message = "Import was canceled."
        job.completed_at = datetime.now(UTC)
        job.progress_percent = float(job.progress_percent or 0)
        prog = dict(job.progress_json or empty_progress())
        prog["cancel_requested"] = True
        set_stage_status(prog, "FINALIZING", "skipped")
        job.progress_json = prog
        flag_modified(job, "progress_json")
        docs = await self.db.execute(
            select(func.count()).select_from(Document).where(Document.source_id == source.id)
        )
        source.status = (
            SourceStatus.READY if int(docs.scalar_one() or 0) > 0 else SourceStatus.READY_TO_IMPORT
        )
        await self.db.commit()

    async def _add_error(
        self,
        job: IngestionJob,
        *,
        code: str,
        message: str,
        external_item_id: str | None = None,
        item_type: str | None = None,
        retryable: bool = True,
    ) -> None:
        # Do not overwrite cancel state with a stale in-memory job row
        try:
            await self._raise_if_cancelled(job)
        except IngestionCancelled:
            raise
        await self.db.refresh(job)
        self.db.add(
            IngestionJobError(
                id=uuid4(),
                job_id=job.id,
                external_item_id=external_item_id,
                item_type=item_type,
                error_code=code,
                error_message_sanitized=message[:1000],
                retryable=retryable,
            )
        )
        prog = dict(job.progress_json or empty_progress())
        stats = dict(prog.get("stats") or {})
        stats["failed_items"] = int(stats.get("failed_items") or 0) + 1
        prog["stats"] = stats
        if job.status == IngestionJobStatus.CANCEL_REQUESTED:
            prog["cancel_requested"] = True
        job.progress_json = prog
        flag_modified(job, "progress_json")
        await self.db.commit()
        await self.db.refresh(job)

    def _client_from_connection(self, conn: ConfluenceConnection) -> ConfluenceClient:
        try:
            assert_public_url(
                conn.base_url,
                allow_http=not settings.is_production,
                allow_private=not settings.is_production,
            )
        except SsrfBlocked as exc:
            raise ssrf_http_exception(exc) from exc
        if not conn.encrypted_credentials:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "CREDENTIALS_NOT_IN_CLOUD",
                    "message": "Direct ingest requires CLOUD credentials.",
                },
            )
        data = json.loads(decrypt_secret(conn.encrypted_credentials))
        return ConfluenceClient(
            base_url=conn.base_url,
            auth_type=conn.auth_type,
            username=(data.get("username") or "").strip() or None,
            secret=(data.get("secret") or "").strip(),
        )

    async def run_direct_job(self, job_id: UUID) -> None:
        """Fetch+store page-by-page (never hold all attachment bytes in memory)."""
        result = await self.db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
        job = result.scalar_one_or_none()
        if job is None:
            return
        source = await self._get_source(job.source_id)
        conn = await self._get_connection(source.connection_id)  # type: ignore[arg-type]
        try:
            await self._set_progress(
                job,
                stage=IngestionStage.SCANNING,
                percent=3,
                message="Connecting…",
                status_value=IngestionJobStatus.RUNNING,
                ui_stage="CONNECTING",
                force=True,
            )
            client = self._client_from_connection(conn)
            async with client:
                await client.test()
                await self._set_progress(
                    job,
                    stage=IngestionStage.SCANNING,
                    percent=8,
                    message="Reading page tree…",
                    ui_stage="SCANNING",
                    force=True,
                )
                page_refs = await self._discover_pages(client, source)
                total_pages = len(page_refs)

                # Clear previous import for this source before streaming store.
                await self.db.execute(
                    delete(DocumentChunk).where(DocumentChunk.source_id == source.id)
                )
                await self.db.execute(delete(Attachment).where(Attachment.source_id == source.id))
                await self.db.execute(delete(Document).where(Document.source_id == source.id))
                await self.db.commit()

                await self._set_progress(
                    job,
                    stage=IngestionStage.FETCHING,
                    percent=10,
                    message=f"Found {total_pages} page(s)",
                    ui_stage="IMPORTING_PAGES",
                    stats={
                        "total_pages": total_pages,
                        "processed_pages": 0,
                        "total_attachments": 0,
                        "processed_attachments": 0,
                        "total_diagrams": 0,
                        "processed_diagrams": 0,
                        "failed_items": 0,
                    },
                    force=True,
                )

                pages_meta: list[dict[str, Any]] = []
                processed_pages = 0
                total_atts = 0
                processed_atts = 0
                total_diagrams = 0
                processed_diagrams = 0
                error_count = 0

                for i, ref in enumerate(page_refs):
                    title = str(ref.get("title") or ref.get("id") or "Page")
                    pct = 10 + (70 * i / max(total_pages, 1))
                    await self._set_progress(
                        job,
                        stage=IngestionStage.FETCHING,
                        percent=pct,
                        message=f"Importing page {i + 1}/{total_pages}",
                        ui_stage="IMPORTING_PAGES",
                        current_item={"name": title, "status": "importing", "type": "PAGE"},
                        stats={
                            "processed_pages": processed_pages,
                            "total_pages": total_pages,
                            "total_attachments": total_atts,
                            "processed_attachments": processed_atts,
                            "total_diagrams": total_diagrams,
                            "processed_diagrams": processed_diagrams,
                        },
                        force=(i % 3 == 0),
                    )
                    try:
                        await self._raise_if_cancelled(job)
                        page = await client.get_page(str(ref["id"]))
                        pages_meta.append(
                            {
                                "id": page.get("id"),
                                "title": page.get("title"),
                                "ancestors": page.get("ancestors") or [],
                            }
                        )
                        attachments_meta = await client.list_attachments(str(ref["id"]))
                        total_atts += len(attachments_meta)
                        page_diagrams = sum(
                            1
                            for a in attachments_meta
                            if is_drawio_filename(a.get("title") or "", a.get("media_type"))
                        )
                        total_diagrams += page_diagrams

                        downloaded: list[dict[str, Any]] = []
                        sem = asyncio.Semaphore(ATTACHMENT_FETCH_CONCURRENCY)

                        async def _one(
                            att: dict[str, Any],
                        ) -> dict[str, Any] | Exception | None:
                            fname = att.get("title") or "file"
                            declared = int(att.get("file_size") or 0)
                            if declared and declared > MAX_ATTACHMENT_BYTES:
                                return ConfluenceClientError(
                                    f"Skipped {fname}: exceeds "
                                    f"{MAX_ATTACHMENT_BYTES // (1024 * 1024)}MB limit",
                                    code="ATTACHMENT_TOO_LARGE",
                                )
                            path = att.get("download_path") or ""
                            if not path:
                                return None
                            async with sem:
                                try:
                                    data, ctype = await client.download_attachment(path)
                                except ConfluenceClientError as exc:
                                    return exc
                                except Exception as exc:  # noqa: BLE001
                                    return ConfluenceClientError(str(exc)[:500])
                            if len(data) > MAX_ATTACHMENT_BYTES:
                                return ConfluenceClientError(
                                    f"Skipped {fname}: downloaded size exceeds limit",
                                    code="ATTACHMENT_TOO_LARGE",
                                )
                            media = att.get("media_type") or ctype
                            return {
                                "id": att["id"],
                                "filename": fname,
                                "media_type": media,
                                "data": data,
                                "size_bytes": len(data),
                                "is_drawio": is_drawio_filename(fname, media),
                            }

                        batch_size = 8
                        for start in range(0, len(attachments_meta), batch_size):
                            await self._raise_if_cancelled(job)
                            batch = attachments_meta[start : start + batch_size]
                            results = await asyncio.gather(*[_one(a) for a in batch])
                            for att_meta, item in zip(batch, results, strict=False):
                                if item is None:
                                    continue
                                if isinstance(item, Exception):
                                    error_count += 1
                                    msg = getattr(item, "message", None) or str(item)
                                    code = (
                                        getattr(item, "code", None) or "ATTACHMENT_FETCH_FAILED"
                                    )
                                    await self._add_error(
                                        job,
                                        code=str(code),
                                        message=str(msg)[:500],
                                        external_item_id=str(att_meta.get("id")),
                                        item_type="ATTACHMENT",
                                    )
                                    continue
                                downloaded.append(item)

                            await self._set_progress(
                                job,
                                stage=IngestionStage.FETCHING,
                                percent=pct,
                                message=f"Page {i + 1}/{total_pages}: attachments…",
                                ui_stage="IMPORTING_ATTACHMENTS"
                                if attachments_meta
                                else "IMPORTING_PAGES",
                                current_item={
                                    "name": title,
                                    "status": "importing",
                                    "type": "PAGE",
                                },
                                stats={
                                    "total_pages": total_pages,
                                    "processed_pages": processed_pages,
                                    "total_attachments": total_atts,
                                    "processed_attachments": processed_atts + len(downloaded),
                                    "total_diagrams": total_diagrams,
                                    "processed_diagrams": processed_diagrams
                                    + sum(1 for d in downloaded if d.get("is_drawio")),
                                },
                            )

                        page["attachments"] = downloaded
                        doc, att_ok, diag_ok, att_failed = await self._store_page(
                            job, source, page, commit=True
                        )
                        page["attachments"] = []
                        downloaded.clear()
                        _ = doc
                        processed_atts += att_ok
                        processed_diagrams += diag_ok
                        error_count += att_failed
                        processed_pages += 1
                        logger.info(
                            "Ingestion %s: stored page %s/%s (%s) atts=%s",
                            job_id,
                            processed_pages,
                            total_pages,
                            title[:80],
                            att_ok,
                        )
                    except IngestionCancelled:
                        raise
                    except ConfluenceClientError as exc:
                        error_count += 1
                        await self._add_error(
                            job,
                            code="PAGE_FETCH_FAILED",
                            message=exc.message,
                            external_item_id=str(ref.get("id")),
                            item_type="PAGE",
                        )
                    except Exception as exc:  # noqa: BLE001
                        error_count += 1
                        logger.exception("Store failed for page %s", ref.get("id"))
                        await self._add_error(
                            job,
                            code="STORE_FAILED",
                            message=str(exc)[:500],
                            external_item_id=str(ref.get("id")),
                            item_type="PAGE",
                        )

                    await self._set_progress(
                        job,
                        stage=IngestionStage.FETCHING,
                        percent=10 + (70 * (i + 1) / max(total_pages, 1)),
                        message=f"Imported {processed_pages}/{total_pages} pages",
                        ui_stage="IMPORTING_PAGES",
                        current_item={"name": title, "status": "imported", "type": "PAGE"},
                        stats={
                            "processed_pages": processed_pages,
                            "total_pages": total_pages,
                            "total_attachments": total_atts,
                            "processed_attachments": processed_atts,
                            "total_diagrams": total_diagrams,
                            "processed_diagrams": processed_diagrams,
                            "failed_items": error_count,
                        },
                        force=True,
                    )

                await self._link_hierarchy_from_pages(source, pages_meta)

                await self._set_progress(
                    job,
                    stage=IngestionStage.CHUNKING,
                    percent=88,
                    message="Indexing for AI…",
                    ui_stage="INDEXING",
                    force=True,
                )
                await self._chunk_and_embed_source(source, job=job)
                await self._finalize_job_stats(
                    job,
                    source,
                    total_pages=total_pages,
                    total_atts=total_atts,
                    total_diagrams=total_diagrams,
                )
        except IngestionCancelled:
            await self._finish_cancelled(job, source)
        except ConfluenceClientError as exc:
            code = _map_confluence_error_code(exc)
            message = exc.message
            if code == "SOURCE_NOT_FOUND":
                message = (
                    "The Confluence space could not be found or you don't have access. "
                    "Check the space key and connection."
                )
            await self._add_error(
                job,
                code=code,
                message=message,
                retryable=code
                in {
                    "CONFLUENCE_SESSION_EXPIRED",
                    "CONFLUENCE_AUTH_FAILED",
                    "SOURCE_NOT_FOUND",
                },
            )
            job.status = IngestionJobStatus.FAILED
            job.stage = IngestionStage.DONE
            job.message = message[:500]
            job.completed_at = datetime.now(UTC)
            source.status = SourceStatus.ERROR
            await self.db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Ingestion job %s failed", job_id)
            await self._add_error(
                job,
                code="IMPORT_FAILED",
                message=str(exc)[:1000],
                retryable=True,
            )
            job.status = IngestionJobStatus.FAILED
            job.stage = IngestionStage.DONE
            job.message = str(exc)[:500]
            job.completed_at = datetime.now(UTC)
            source.status = SourceStatus.ERROR
            await self.db.commit()

    async def _load_local_versions(self, source_id: UUID) -> dict[str, str | None]:
        result = await self.db.execute(
            select(Document.external_id, Document.external_version).where(
                Document.source_id == source_id,
                Document.deleted_at.is_(None),
                Document.document_type == DocumentType.PAGE,
            )
        )
        return {str(row[0]): row[1] for row in result.all()}

    async def _soft_delete_pages(
        self, source: Source, external_ids: list[str]
    ) -> int:
        if not external_ids:
            return 0
        now = datetime.now(UTC)
        result = await self.db.execute(
            select(Document).where(
                Document.source_id == source.id,
                Document.external_id.in_(external_ids),
                Document.deleted_at.is_(None),
            )
        )
        count = 0
        for doc in result.scalars().all():
            doc.deleted_at = now
            await self.db.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == doc.id)
            )
            count += 1
        await self.db.commit()
        return count

    async def _apply_agent_sync_scan(
        self, job: IngestionJob, remote_pages: list[dict[str, Any]]
    ) -> None:
        source = await self._get_source(job.source_id)
        conn = await self._get_connection(source.connection_id)  # type: ignore[arg-type]
        local = await self._load_local_versions(source.id)
        plan = compute_sync_plan(remote_pages, local)
        prog = dict(job.progress_json or empty_progress())
        prog["sync_stats"] = plan.as_summary()
        prog["sync_plan"] = {
            "added": plan.added,
            "updated": plan.updated,
            "removed": plan.removed,
            "unchanged": plan.unchanged,
        }
        job.progress_json = prog
        flag_modified(job, "progress_json")
        await self._set_progress(
            job,
            stage=IngestionStage.SCANNING,
            percent=25,
            message=(
                f"Scan complete — {len(plan.to_fetch)} to update, "
                f"{len(plan.removed)} removed, {len(plan.unchanged)} unchanged"
            ),
            ui_stage="SCANNING",
            force=True,
        )
        await self._soft_delete_pages(source, plan.removed)
        if not plan.to_fetch:
            await self._finish_sync_job(job, source, plan, error_count=0)
            return
        await self._enqueue_agent_fetch(
            job, source, conn, scan_only=False, page_ids=plan.to_fetch
        )

    async def _process_sync_pages(
        self, job: IngestionJob, pages: list[dict[str, Any]]
    ) -> None:
        source = await self._get_source(job.source_id)
        changed_ids: list[UUID] = []
        pages_meta: list[dict[str, Any]] = []
        error_count = 0
        total = len(pages)
        for i, page in enumerate(pages):
            ext_id = str(page.get("id") or "")
            title = str(page.get("title") or ext_id or "Page")
            try:
                await self._set_progress(
                    job,
                    stage=IngestionStage.STORING,
                    percent=40 + (40 * i / max(total, 1)),
                    message=f"Syncing {i + 1}/{total}",
                    ui_stage="IMPORTING_PAGES",
                    current_item={"name": title, "status": "importing", "type": "PAGE"},
                )
                doc, _, _, att_failed = await self._store_page(
                    job, source, page, commit=True, upsert=True
                )
                changed_ids.append(doc.id)
                pages_meta.append(
                    {
                        "id": page.get("id"),
                        "title": page.get("title"),
                        "ancestors": page.get("ancestors") or [],
                    }
                )
                error_count += att_failed
            except Exception as exc:  # noqa: BLE001
                error_count += 1
                await self._add_error(
                    job,
                    code="STORE_FAILED",
                    message=str(exc)[:500],
                    external_item_id=ext_id,
                    item_type="PAGE",
                )
        if pages_meta:
            await self._link_hierarchy_from_pages(source, pages_meta)
        await self._set_progress(
            job,
            stage=IngestionStage.CHUNKING,
            percent=88,
            message="Re-indexing changed pages…",
            ui_stage="INDEXING",
            force=True,
        )
        if changed_ids:
            await self._chunk_and_embed_documents(source, changed_ids, job=job)
        prog = dict(job.progress_json or empty_progress())
        raw_plan = prog.get("sync_plan") or {}
        plan = SyncPlan(
            added=list(raw_plan.get("added") or []),
            updated=list(raw_plan.get("updated") or []),
            removed=list(raw_plan.get("removed") or []),
            unchanged=list(raw_plan.get("unchanged") or []),
        )
        await self._finish_sync_job(job, source, plan, error_count=error_count)

    async def run_sync_job(self, job_id: UUID) -> None:
        result = await self.db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
        job = result.scalar_one_or_none()
        if job is None:
            return
        source = await self._get_source(job.source_id)
        conn = await self._get_connection(source.connection_id)  # type: ignore[arg-type]
        try:
            await self._set_progress(
                job,
                stage=IngestionStage.SCANNING,
                percent=5,
                message="Scanning Confluence for changes…",
                status_value=IngestionJobStatus.RUNNING,
                ui_stage="SCANNING",
                force=True,
            )
            client = self._client_from_connection(conn)
            async with client:
                await client.test()
                remote_pages = await self._discover_pages(client, source)
                for ref in remote_pages:
                    if ref.get("id") and not ref.get("version"):
                        page = await client.get_page(str(ref["id"]))
                        ref["version"] = page.get("version")
                local = await self._load_local_versions(source.id)
                plan = compute_sync_plan(remote_pages, local)
                prog = dict(job.progress_json or empty_progress())
                prog["sync_stats"] = plan.as_summary()
                prog["sync_plan"] = {
                    "added": plan.added,
                    "updated": plan.updated,
                    "removed": plan.removed,
                    "unchanged": plan.unchanged,
                }
                job.progress_json = prog
                flag_modified(job, "progress_json")
                await self._set_progress(
                    job,
                    stage=IngestionStage.SCANNING,
                    percent=20,
                    message=(
                        f"{len(plan.to_fetch)} to sync, {len(plan.removed)} removed, "
                        f"{len(plan.unchanged)} unchanged"
                    ),
                    ui_stage="SCANNING",
                    force=True,
                )
                await self._soft_delete_pages(source, plan.removed)
                await self._link_hierarchy_from_pages(source, remote_pages)
                if not plan.to_fetch:
                    await self._finish_sync_job(job, source, plan, error_count=0)
                    return

                await self._set_progress(
                    job,
                    stage=IngestionStage.FETCHING,
                    percent=30,
                    message=f"Fetching {len(plan.to_fetch)} changed page(s)…",
                    ui_stage="IMPORTING_PAGES",
                    stats={"total_pages": len(plan.to_fetch), "processed_pages": 0},
                    force=True,
                )
                fetch_ids = set(plan.to_fetch)
                changed_ids: list[UUID] = []
                pages_meta: list[dict[str, Any]] = []
                error_count = 0
                processed = 0
                for i, ref in enumerate(remote_pages):
                    ext_id = str(ref.get("id") or "")
                    if ext_id not in fetch_ids:
                        continue
                    title = str(ref.get("title") or ext_id)
                    try:
                        await self._raise_if_cancelled(job)
                        page = await client.get_page(ext_id)
                        attachments_meta = await client.list_attachments(ext_id)
                        downloaded: list[dict[str, Any]] = []
                        for att in attachments_meta:
                            try:
                                raw, ctype = await client.download_attachment(
                                    att["download_path"]
                                )
                                if len(raw) > MAX_ATTACHMENT_BYTES:
                                    continue
                                drawio = is_drawio_filename(
                                    att.get("title") or "", att.get("media_type")
                                )
                                downloaded.append(
                                    {
                                        "id": att["id"],
                                        "filename": att["title"],
                                        "media_type": att.get("media_type") or ctype,
                                        "data": raw,
                                        "size_bytes": len(raw),
                                        "is_drawio": drawio,
                                    }
                                )
                            except Exception as exc:  # noqa: BLE001
                                error_count += 1
                                await self._add_error(
                                    job,
                                    code="ATTACHMENT_FETCH_FAILED",
                                    message=str(exc)[:500],
                                    external_item_id=str(att.get("id")),
                                    item_type="ATTACHMENT",
                                )
                        page["attachments"] = downloaded
                        doc, _, _, att_failed = await self._store_page(
                            job, source, page, commit=True, upsert=True
                        )
                        changed_ids.append(doc.id)
                        pages_meta.append(
                            {
                                "id": page.get("id"),
                                "title": page.get("title"),
                                "ancestors": page.get("ancestors") or [],
                            }
                        )
                        error_count += att_failed
                        processed += 1
                        await self._set_progress(
                            job,
                            stage=IngestionStage.FETCHING,
                            percent=30 + (50 * processed / max(len(plan.to_fetch), 1)),
                            message=f"Synced {processed}/{len(plan.to_fetch)}",
                            ui_stage="IMPORTING_PAGES",
                            stats={
                                "total_pages": len(plan.to_fetch),
                                "processed_pages": processed,
                            },
                            force=True,
                        )
                    except IngestionCancelled:
                        raise
                    except Exception as exc:  # noqa: BLE001
                        error_count += 1
                        await self._add_error(
                            job,
                            code="PAGE_FETCH_FAILED",
                            message=str(exc)[:500],
                            external_item_id=ext_id,
                            item_type="PAGE",
                        )

                if pages_meta:
                    merged = {str(p.get("id")): p for p in remote_pages if p.get("id")}
                    for p in pages_meta:
                        if p.get("id") is not None:
                            merged[str(p.get("id"))] = p
                    await self._link_hierarchy_from_pages(source, list(merged.values()))
                await self._set_progress(
                    job,
                    stage=IngestionStage.CHUNKING,
                    percent=88,
                    message="Re-indexing changed pages…",
                    ui_stage="INDEXING",
                    force=True,
                )
                if changed_ids:
                    await self._chunk_and_embed_documents(source, changed_ids, job=job)
                await self._finish_sync_job(job, source, plan, error_count=error_count)
        except IngestionCancelled:
            await self._finish_cancelled(job, source)
        except ConfluenceClientError as exc:
            code = _map_confluence_error_code(exc)
            await self._add_error(job, code=code, message=exc.message, retryable=True)
            job.status = IngestionJobStatus.FAILED
            job.message = exc.message[:500]
            job.completed_at = datetime.now(UTC)
            source.status = SourceStatus.READY
            source.last_sync_at = datetime.now(UTC)
            source.last_sync_status = SyncStatus.FAILED
            source.last_sync_summary = {
                "added": 0,
                "updated": 0,
                "removed": 0,
                "unchanged": 0,
                "failed": 1,
            }
            await self.db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Sync job %s failed", job_id)
            await self._add_error(
                job, code="SYNC_FAILED", message=str(exc)[:1000], retryable=True
            )
            job.status = IngestionJobStatus.FAILED
            job.message = str(exc)[:500]
            job.completed_at = datetime.now(UTC)
            source.status = SourceStatus.READY
            source.last_sync_at = datetime.now(UTC)
            source.last_sync_status = SyncStatus.FAILED
            source.last_sync_summary = {
                "added": 0,
                "updated": 0,
                "removed": 0,
                "unchanged": 0,
                "failed": 1,
            }
            await self.db.commit()

    async def _finish_sync_job(
        self,
        job: IngestionJob,
        source: Source,
        plan: SyncPlan,
        *,
        error_count: int,
    ) -> None:
        summary = plan.as_summary()
        summary["failed"] = error_count
        prog = dict(job.progress_json or empty_progress())
        prog["sync_stats"] = summary
        mark_stage(prog, "FINALIZING")
        complete_all_stages(prog)
        job.progress_json = prog
        flag_modified(job, "progress_json")
        job.status = (
            IngestionJobStatus.COMPLETED_WITH_ERRORS
            if error_count
            else IngestionJobStatus.COMPLETED
        )
        job.stage = IngestionStage.DONE
        job.progress_percent = 100.0
        job.message = (
            f"Sync finished — +{summary['added']} ~{summary['updated']} "
            f"-{summary['removed']} ({summary['unchanged']} unchanged)"
        )
        job.completed_at = datetime.now(UTC)
        now = datetime.now(UTC)
        source.status = SourceStatus.READY
        source.last_sync_at = now
        source.last_sync_summary = summary
        source.last_sync_status = (
            SyncStatus.PARTIAL if error_count else SyncStatus.SUCCESS
        )
        if source.sync_enabled and source.sync_interval != SyncInterval.OFF:
            source.next_sync_at = compute_next_sync_at(source.sync_interval, from_time=now)
        else:
            source.next_sync_at = None
        await self.db.commit()

    async def _discover_pages(
        self, client: ConfluenceClient, source: Source
    ) -> list[dict[str, Any]]:
        if source.external_type == SourceExternalType.PAGE:
            return [{"id": source.external_id, "title": source.name}]
        space_key = (source.external_key or "").strip() or None
        space_id = (source.external_id or "").strip() or None
        if not space_key and not space_id:
            raise ConfluenceClientError(
                "Confluence space key is missing.",
                status_code=404,
                code="SOURCE_NOT_FOUND",
            )
        return await client.list_all_pages_in_space(
            str(space_key or space_id),
            space_id=space_id if space_key and space_id and space_key != space_id else None,
        )

    async def _process_fetched_pages(
        self, job: IngestionJob, pages: list[dict[str, Any]]
    ) -> None:
        source = await self._get_source(job.source_id)
        total_pages = len(pages)
        total_atts = sum(len(p.get("attachments") or []) for p in pages)
        total_diagrams = sum(
            1
            for p in pages
            for a in (p.get("attachments") or [])
            if a.get("is_drawio")
            or is_drawio_filename(a.get("filename") or "", a.get("media_type"))
        )
        await self._set_progress(
            job,
            stage=IngestionStage.STORING,
            percent=65,
            message="Storing documents & attachments",
            ui_stage="IMPORTING_ATTACHMENTS",
            stats={
                "total_pages": total_pages,
                "processed_pages": 0,
                "total_attachments": total_atts,
                "processed_attachments": 0,
                "total_diagrams": total_diagrams,
                "processed_diagrams": 0,
            },
        )
        await self.db.execute(delete(DocumentChunk).where(DocumentChunk.source_id == source.id))
        await self.db.execute(delete(Attachment).where(Attachment.source_id == source.id))
        await self.db.execute(delete(Document).where(Document.source_id == source.id))
        await self.db.commit()

        error_count = 0
        stored_atts = 0
        stored_diagrams = 0
        for i, page in enumerate(pages):
            title = str(page.get("title") or page.get("id") or "Page")
            try:
                await self._set_progress(
                    job,
                    stage=IngestionStage.STORING,
                    percent=65 + (15 * i / max(total_pages, 1)),
                    message=f"Storing {i + 1}/{total_pages}",
                    ui_stage="IMPORTING_ATTACHMENTS",
                    current_item={"name": title, "status": "importing", "type": "PAGE"},
                    stats={"processed_pages": i},
                )
                doc, att_ok, diag_ok, att_failed = await self._store_page(job, source, page)
                stored_atts += att_ok
                stored_diagrams += diag_ok
                error_count += att_failed
                await self._set_progress(
                    job,
                    stage=IngestionStage.STORING,
                    percent=65 + (15 * (i + 1) / max(total_pages, 1)),
                    message=f"Stored {i + 1}/{total_pages}",
                    current_item={"name": title, "status": "imported", "type": "PAGE"},
                    stats={
                        "processed_pages": i + 1,
                        "processed_attachments": stored_atts,
                        "processed_diagrams": stored_diagrams,
                        "failed_items": int(
                            ((job.progress_json or {}).get("stats") or {}).get("failed_items") or 0
                        ),
                    },
                )
                _ = doc
            except IngestionCancelled:
                raise
            except Exception as exc:  # noqa: BLE001
                error_count += 1
                await self._add_error(
                    job,
                    code="STORE_FAILED",
                    message=str(exc)[:500],
                    external_item_id=str(page.get("id")),
                    item_type="PAGE",
                )

        await self._link_hierarchy_from_pages(source, pages)

        await self._set_progress(
            job,
            stage=IngestionStage.CHUNKING,
            percent=85,
            message="Indexing for AI…",
            ui_stage="INDEXING",
            force=True,
        )
        await self._chunk_and_embed_source(source, job=job)
        await self._finalize_job_stats(
            job,
            source,
            total_pages=total_pages,
            total_atts=total_atts,
            total_diagrams=total_diagrams,
        )

    async def _finalize_job_stats(
        self,
        job: IngestionJob,
        source: Source,
        *,
        total_pages: int,
        total_atts: int,
        total_diagrams: int,
    ) -> None:
        err_result = await self.db.execute(
            select(func.count())
            .select_from(IngestionJobError)
            .where(IngestionJobError.job_id == job.id)
        )
        total_errors = int(err_result.scalar_one() or 0)

        docs_count = int(
            (
                await self.db.execute(
                    select(func.count()).select_from(Document).where(Document.source_id == source.id)
                )
            ).scalar_one()
            or 0
        )
        atts_count = int(
            (
                await self.db.execute(
                    select(func.count())
                    .select_from(Attachment)
                    .where(Attachment.source_id == source.id)
                )
            ).scalar_one()
            or 0
        )
        diagrams_count = int(
            (
                await self.db.execute(
                    select(func.count())
                    .select_from(Attachment)
                    .where(Attachment.source_id == source.id, Attachment.is_drawio.is_(True))
                )
            ).scalar_one()
            or 0
        )

        prog = dict(job.progress_json or empty_progress())
        stats = dict(prog.get("stats") or {})
        stats["total_pages"] = max(int(stats.get("total_pages") or 0), total_pages, docs_count)
        stats["processed_pages"] = max(int(stats.get("processed_pages") or 0), docs_count)
        stats["total_attachments"] = max(int(stats.get("total_attachments") or 0), total_atts)
        stats["processed_attachments"] = max(
            int(stats.get("processed_attachments") or 0), atts_count
        )
        stats["total_diagrams"] = max(int(stats.get("total_diagrams") or 0), total_diagrams)
        stats["processed_diagrams"] = max(
            int(stats.get("processed_diagrams") or 0), diagrams_count
        )
        stats["failed_items"] = max(int(stats.get("failed_items") or 0), total_errors)
        prog["stats"] = stats
        mark_stage(prog, "FINALIZING")
        complete_all_stages(prog)
        job.progress_json = prog
        flag_modified(job, "progress_json")
        job.status = (
            IngestionJobStatus.COMPLETED_WITH_ERRORS
            if total_errors
            else IngestionJobStatus.COMPLETED
        )
        job.stage = IngestionStage.DONE
        job.progress_percent = 100.0
        job.message = (
            f"Import finished with {total_errors} issue(s)"
            if total_errors
            else "Import finished"
        )
        job.completed_at = datetime.now(UTC)
        source.status = SourceStatus.READY if docs_count > 0 else (
            SourceStatus.ERROR if total_errors else SourceStatus.READY_TO_IMPORT
        )
        await self.db.commit()

    async def _store_page(
        self,
        job: IngestionJob,
        source: Source,
        page: dict[str, Any],
        *,
        commit: bool = True,
        upsert: bool = False,
    ) -> tuple[Document, int, int, int]:
        raw_html = page.get("body_storage") or page.get("body_html") or ""
        sanitized = sanitize_html(raw_html)
        attachments_in = page.get("attachments") or []
        filename_map: dict[str, str] = {}
        ext_id = str(page.get("id"))
        doc: Document | None = None
        if upsert:
            existing = await self.db.execute(
                select(Document).where(
                    Document.source_id == source.id,
                    Document.external_id == ext_id,
                )
            )
            doc = existing.scalar_one_or_none()
            if doc is not None:
                doc.deleted_at = None
                await self.db.execute(
                    delete(Attachment).where(Attachment.document_id == doc.id)
                )
                await self.db.execute(
                    delete(DocumentChunk).where(DocumentChunk.document_id == doc.id)
                )
        if doc is None:
            doc = Document(
                id=uuid4(),
                workspace_id=source.workspace_id,
                space_id=source.space_id,
                source_id=source.id,
                external_id=ext_id,
                document_type=DocumentType.PAGE,
                title=(page.get("title") or "Untitled")[:500],
                status=DocumentStatus.PENDING,
                origin=DocumentOrigin.CONFLUENCE,
                raw_content=raw_html,
                external_version=page.get("version"),
                external_url=page.get("url"),
            )
            self.db.add(doc)
        else:
            doc.title = (page.get("title") or "Untitled")[:500]
            doc.status = DocumentStatus.PENDING
            doc.raw_content = raw_html
            doc.external_version = page.get("version")
            doc.external_url = page.get("url")
        await self.db.flush()

        stored_atts = 0
        stored_diagrams = 0
        failed_atts = 0
        for att in attachments_in:
            try:
                if att.get("data") is not None:
                    data = att["data"] if isinstance(att["data"], (bytes, bytearray)) else b""
                else:
                    raw_b64 = att.get("data_b64") or ""
                    data = base64.b64decode(raw_b64) if raw_b64 else b""
                filename = (att.get("filename") or "file")[:500]
                media_type = att.get("media_type") or "application/octet-stream"
                drawio = bool(att.get("is_drawio")) or is_drawio_filename(filename, media_type)
                if drawio and "xml" not in media_type and not media_type.endswith("drawio"):
                    media_type = "application/vnd.jgraph.mxfile"
                checksum = hashlib.sha256(data).hexdigest() if data else None
                att_id = str(att.get("id") or uuid4())
                # Short leaf — id + extension only (avoids Windows MAX_PATH).
                ext = Path(filename).suffix[:20] if Path(filename).suffix else ""
                leaf = f"{att_id}{ext}" if att_id else safe_object_filename(filename)
                key = (
                    f"workspaces/{source.workspace_id}/sources/{source.id}/"
                    f"docs/{doc.id}/attachments/{leaf}"
                )
                if data:
                    get_object_storage().put_bytes(key, data, content_type=media_type)
                attachment = Attachment(
                    id=uuid4(),
                    workspace_id=source.workspace_id,
                    space_id=source.space_id,
                    source_id=source.id,
                    document_id=doc.id,
                    external_id=att_id,
                    filename=filename,
                    media_type=media_type,
                    size_bytes=int(att.get("size_bytes") or len(data)),
                    checksum_sha256=checksum,
                    object_key=key,
                    is_drawio=drawio,
                )
                self.db.add(attachment)
                await self.db.flush()
                filename_map[filename] = str(attachment.id)
                filename_map[filename.lower()] = str(attachment.id)
                stored_atts += 1
                if drawio:
                    stored_diagrams += 1
            except Exception as exc:  # noqa: BLE001
                failed_atts += 1
                await self._add_error(
                    job,
                    code="ATTACHMENT_STORE_FAILED",
                    message=str(exc)[:500],
                    external_item_id=str(att.get("id")),
                    item_type="ATTACHMENT",
                )

        rewritten = rewrite_attachment_urls(sanitized, filename_to_attachment_id=filename_map)
        rewritten = replace_confluence_images(rewritten, filename_to_attachment_id=filename_map)
        rewritten = replace_drawio_macros_with_images(
            rewritten, filename_to_attachment_id=filename_map
        )
        text = html_to_text(rewritten)
        doc.raw_content = rewritten
        doc.normalized_content = text
        doc.content_checksum = content_checksum(text)
        doc.status = DocumentStatus.READY
        if commit:
            await self.db.commit()
        return doc, stored_atts, stored_diagrams, failed_atts

    async def _link_hierarchy_from_pages(
        self, source: Source, pages: list[dict[str, Any]]
    ) -> None:
        """Map Confluence ancestors → parent_id / depth / sibling position.

        Pages missing from ``pages`` keep their current parent (delta sync must
        not flatten the rest of the tree).
        """
        result = await self.db.execute(
            select(Document).where(
                Document.source_id == source.id,
                Document.document_type == DocumentType.PAGE,
                Document.deleted_at.is_(None),
            )
        )
        docs = list(result.scalars().all())
        by_external = {str(d.external_id): d for d in docs if d.external_id}
        page_by_ext = {str(p.get("id")): p for p in pages if p.get("id") is not None}

        siblings: dict[UUID | None, list[Document]] = {}
        for doc in docs:
            page = page_by_ext.get(str(doc.external_id or ""))
            if page is None or "ancestors" not in page:
                siblings.setdefault(doc.parent_id, []).append(doc)
                continue
            ancestors = normalize_ancestors(page.get("ancestors"))
            parent_ext = ancestors[-1]["id"] if ancestors else None
            if parent_ext and parent_ext == str(doc.external_id):
                parent_ext = ancestors[-2]["id"] if len(ancestors) > 1 else None
            parent = by_external.get(parent_ext) if parent_ext else None
            doc.parent_id = parent.id if parent else None
            doc.depth = len(ancestors)
            doc.origin = DocumentOrigin.CONFLUENCE
            siblings.setdefault(doc.parent_id, []).append(doc)

        for children in siblings.values():
            for idx, child in enumerate(children):
                child.position = idx

        await self.db.commit()

    async def _chunk_and_embed_documents(
        self,
        source: Source,
        document_ids: list[UUID],
        *,
        job: IngestionJob | None = None,
    ) -> None:
        if not document_ids:
            return
        result = await self.db.execute(
            select(Document).where(
                Document.source_id == source.id,
                Document.id.in_(document_ids),
                Document.deleted_at.is_(None),
            )
        )
        docs = list(result.scalars().all())
        await self._index_documents(source, docs, job=job)

    def _chunk_pieces_for_document(self, doc: Document, source: Source) -> list[HeadingChunkPiece]:
        page_title = doc.title or "Untitled"
        html = (doc.raw_content or "").strip()
        if html:
            pieces = chunk_html_by_headings(html, page_title=page_title)
            if pieces:
                return pieces
        text = (doc.normalized_content or "").strip()
        if not text:
            return []
        return [
            HeadingChunkPiece(
                content=piece,
                section_heading=page_title,
                heading_path=page_title,
                parent_section=text[:4000],
            )
            for piece in chunk_text(text)
        ]

    async def _persist_chunks_for_document(self, source: Source, doc: Document) -> None:
        pieces = self._chunk_pieces_for_document(doc, source)
        if not pieces:
            return
        page_title = doc.title or "Untitled"
        space_key = source.external_key or source.external_id
        source_url = doc.external_url
        embed_inputs = [
            build_embed_text(
                page_title=page_title,
                section_heading=piece.section_heading,
                space_key=space_key,
                content=piece.content,
            )
            for piece in pieces
        ]
        vectors = await embed_texts(embed_inputs)
        for idx, (piece, vector) in enumerate(zip(pieces, vectors, strict=False)):
            prefix = build_embed_prefix(
                page_title=page_title,
                section_heading=piece.section_heading,
                space_key=space_key,
            )
            self.db.add(
                DocumentChunk(
                    id=uuid4(),
                    workspace_id=source.workspace_id,
                    space_id=source.space_id,
                    source_id=source.id,
                    document_id=doc.id,
                    chunk_index=idx,
                    heading_path=piece.heading_path[:500],
                    content=piece.content,
                    token_count=max(1, len(piece.content.split())),
                    content_hash=hashlib.sha256(piece.content.encode("utf-8")).hexdigest(),
                    embedding=vector,
                    metadata_json={
                        "page_title": page_title,
                        "section_heading": piece.section_heading,
                        "source_url": source_url,
                        "space_key": space_key,
                        "parent_section": piece.parent_section,
                        "embed_prefix": prefix,
                    },
                )
            )

    async def _index_documents(
        self,
        source: Source,
        docs: list[Document],
        *,
        job: IngestionJob | None = None,
    ) -> None:
        total = len(docs)
        if total == 0:
            return
        for i, doc in enumerate(docs):
            if job is not None:
                await self._raise_if_cancelled(job)
            title = doc.title or "Untitled"
            try:
                await self.db.execute(
                    delete(DocumentChunk).where(DocumentChunk.document_id == doc.id)
                )
                await self._persist_chunks_for_document(source, doc)
                await self.db.commit()
            except IngestionCancelled:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.exception("Indexing failed for document %s", doc.id)
                await self.db.rollback()
                if job is not None:
                    await self._add_error(
                        job,
                        code="INDEX_FAILED",
                        message=str(exc)[:500],
                        external_item_id=doc.external_id,
                        item_type="PAGE",
                    )
                continue

            done = i + 1
            if job is not None and (done == 1 or done == total or done % 5 == 0):
                percent = 88 + (10 * done / max(total, 1))
                await self._set_progress(
                    job,
                    stage=IngestionStage.CHUNKING,
                    percent=min(97.5, percent),
                    message=f"Indexing {done}/{total} pages…",
                    ui_stage="INDEXING",
                    current_item={
                        "name": title,
                        "status": "imported" if done == total else "importing",
                        "type": "PAGE",
                    },
                    force=done == total or done == 1,
                    eta_processed=done,
                    eta_total=total,
                )

    async def _chunk_and_embed_source(
        self, source: Source, *, job: IngestionJob | None = None
    ) -> None:
        result = await self.db.execute(
            select(Document).where(
                Document.source_id == source.id,
                Document.deleted_at.is_(None),
            )
        )
        docs = list(result.scalars().all())
        await self._index_documents(source, docs, job=job)

    async def _persist_chunk_hints(
        self,
        source: Source,
        doc: Document,
        hints: list[Any],
    ) -> None:
        from app.ingestion.parsers import ChunkHint

        page_title = doc.title or "Untitled"
        space_key = source.external_key or source.external_id
        source_url = doc.external_url
        typed_hints: list[ChunkHint] = []
        for h in hints:
            if isinstance(h, ChunkHint):
                typed_hints.append(h)
            elif isinstance(h, dict):
                typed_hints.append(
                    ChunkHint(
                        text=str(h.get("text") or ""),
                        position=int(h.get("position") or 0),
                        metadata=dict(h.get("metadata") or {}),
                    )
                )
        if not typed_hints:
            return
        embed_inputs = [
            build_embed_text(
                page_title=page_title,
                section_heading=str(
                    (h.metadata or {}).get("citation_label")
                    or (h.metadata or {}).get("heading_path")
                    or page_title
                ),
                space_key=space_key,
                content=h.text,
            )
            for h in typed_hints
        ]
        vectors = await embed_texts(embed_inputs)
        for idx, (hint, vector) in enumerate(zip(typed_hints, vectors, strict=False)):
            meta = dict(hint.metadata or {})
            section = str(
                meta.get("citation_label")
                or meta.get("heading_path")
                or meta.get("slide_title")
                or page_title
            )
            prefix = build_embed_prefix(
                page_title=page_title,
                section_heading=section,
                space_key=space_key,
            )
            self.db.add(
                DocumentChunk(
                    id=uuid4(),
                    workspace_id=source.workspace_id,
                    space_id=source.space_id,
                    source_id=source.id,
                    document_id=doc.id,
                    chunk_index=idx,
                    heading_path=section[:500],
                    content=hint.text,
                    token_count=max(1, len(hint.text.split())),
                    content_hash=hashlib.sha256(hint.text.encode("utf-8")).hexdigest(),
                    embedding=vector,
                    metadata_json={
                        "page_title": page_title,
                        "section_heading": section,
                        "source_url": source_url,
                        "space_key": space_key,
                        "embed_prefix": prefix,
                        "source_type": source.type,
                        **meta,
                    },
                )
            )

    async def run_file_job(self, job_id: UUID) -> None:
        result = await self.db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
        job = result.scalar_one_or_none()
        if job is None:
            return
        source = await self._get_source(job.source_id)
        try:
            from app.ingestion.parsers import ensure_parsers_loaded, get_parser
            from app.models.source_file import SourceFile

            await self._set_progress(
                job,
                stage=IngestionStage.NORMALIZING,
                percent=5,
                message="Reading uploaded file…",
                status_value=IngestionJobStatus.RUNNING,
                ui_stage="READING",
                force=True,
            )
            sf_result = await self.db.execute(
                select(SourceFile).where(
                    SourceFile.source_id == source.id,
                    SourceFile.is_active.is_(True),
                ).order_by(SourceFile.version.desc())
            )
            sf = sf_result.scalars().first()
            if sf is None:
                raise RuntimeError("Uploaded file metadata not found.")
            storage = get_object_storage()
            data = storage.get_bytes(sf.storage_key)
            ensure_parsers_loaded()
            parser = get_parser(source.type)
            options = (source.config_json or {}).get("import_options") or {}
            await self._set_progress(
                job,
                stage=IngestionStage.NORMALIZING,
                percent=25,
                message="Parsing…",
                ui_stage="PARSING",
                force=True,
            )
            parsed = parser.parse(data, filename=sf.display_name or source.name, options=options)
            if parsed.error_code and not parsed.documents:
                raise RuntimeError(parsed.error_message or parsed.error_code)

            await self.db.execute(delete(DocumentChunk).where(DocumentChunk.source_id == source.id))
            await self.db.execute(delete(Document).where(Document.source_id == source.id))
            await self.db.commit()

            docs: list[Document] = []
            for i, nd in enumerate(parsed.documents):
                doc = Document(
                    id=uuid4(),
                    workspace_id=source.workspace_id,
                    space_id=source.space_id,
                    source_id=source.id,
                    external_id=nd.external_id[:200],
                    document_type=nd.document_type,
                    title=nd.title[:500],
                    status=DocumentStatus.READY,
                    position=i,
                    depth=0,
                    origin=DocumentOrigin.FILE_UPLOAD,
                    raw_content=None,
                    normalized_content=nd.normalized_text,
                    content_checksum=hashlib.sha256(
                        nd.normalized_text.encode("utf-8")
                    ).hexdigest(),
                    external_version=nd.external_version,
                    external_url=nd.external_url,
                    created_by_user_id=source.created_by_user_id,
                )
                self.db.add(doc)
                docs.append(doc)
                await self.db.flush()
                await self.db.execute(
                    delete(DocumentChunk).where(DocumentChunk.document_id == doc.id)
                )
                if nd.chunk_hints:
                    await self._persist_chunk_hints(source, doc, nd.chunk_hints)
                else:
                    await self._persist_chunks_for_document(source, doc)
                await self._set_progress(
                    job,
                    stage=IngestionStage.CHUNKING,
                    percent=40 + (50 * (i + 1) / max(len(parsed.documents), 1)),
                    message=f"Indexing {i + 1}/{len(parsed.documents)}…",
                    ui_stage="INDEXING",
                    current_item={
                        "name": doc.title,
                        "status": "importing",
                        "type": "FILE",
                    },
                    stats={
                        "total_pages": len(parsed.documents),
                        "processed_pages": i + 1,
                    },
                    force=True,
                )
            await self.db.commit()

            cfg = dict(source.config_json or {})
            cfg["preview"] = parsed.preview
            source.config_json = cfg
            flag_modified(source, "config_json")
            source.status = SourceStatus.INDEXED
            source.last_sync_at = datetime.now(UTC)
            source.last_sync_status = SyncStatus.SUCCESS
            complete_all_stages(job.progress_json or {})
            job.status = IngestionJobStatus.COMPLETED
            job.stage = IngestionStage.DONE
            job.progress_percent = 100
            job.completed_at = datetime.now(UTC)
            job.message = f"Indexed {len(docs)} document(s)."
            flag_modified(job, "progress_json")
            await self.db.commit()
        except IngestionCancelled:
            source.status = SourceStatus.NEEDS_ATTENTION
            job.status = IngestionJobStatus.CANCELLED
            await self.db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("File ingestion failed for job %s", job_id)
            source.status = SourceStatus.FAILED
            source.error_code = "FILE_INGEST_FAILED"
            source.error_message = str(exc)[:500]
            job.status = IngestionJobStatus.FAILED
            job.error_code = getattr(exc, "code", None) or "FILE_INGEST_FAILED"
            job.error_message = str(exc)[:500]
            job.completed_at = datetime.now(UTC)
            await self.db.commit()

    async def run_jira_job(self, job_id: UUID) -> None:
        await self._run_jira_import(job_id, incremental=False)

    async def run_jira_sync_job(self, job_id: UUID) -> None:
        await self._run_jira_import(job_id, incremental=True)

    async def _run_jira_import(self, job_id: UUID, *, incremental: bool) -> None:
        result = await self.db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
        job = result.scalar_one_or_none()
        if job is None:
            return
        source = await self._get_source(job.source_id)
        try:
            from app.jira.client import JiraClient, JiraClientError
            from app.jira.normalize import normalize_jira_issue
            from app.models.jira import JiraConnection

            conn_result = await self.db.execute(
                select(JiraConnection).where(JiraConnection.id == source.jira_connection_id)
            )
            conn = conn_result.scalar_one_or_none()
            if conn is None or not conn.encrypted_credentials:
                raise RuntimeError("Jira connection missing credentials.")
            creds = json.loads(decrypt_secret(conn.encrypted_credentials))
            client = JiraClient(
                base_url=conn.base_url,
                auth_type=conn.auth_type,
                username=(creds.get("username") or "").strip() or None,
                secret=(creds.get("secret") or "").strip(),
            )
            await self._set_progress(
                job,
                stage=IngestionStage.FETCHING,
                percent=5,
                message="Connecting to Jira…",
                status_value=IngestionJobStatus.RUNNING,
                ui_stage="CONNECTING",
                force=True,
            )
            await client.test_connection()
            scope = ((source.config_json or {}).get("scope")) or {}
            include = {
                "comments": bool(scope.get("comments", True)),
                "attachments": bool(scope.get("attachments", True)),
                "description": bool(scope.get("description", True)),
                "acceptance_criteria": bool(scope.get("acceptance_criteria", True)),
                "change_history": bool(scope.get("change_history", False)),
            }
            updated_after = None
            if incremental and source.last_sync_at:
                updated_after = source.last_sync_at.strftime("%Y-%m-%d %H:%M")

            await self._set_progress(
                job,
                stage=IngestionStage.FETCHING,
                percent=15,
                message="Fetching issues…",
                ui_stage="FETCHING",
                force=True,
            )

            if not incremental:
                await self.db.execute(
                    delete(DocumentChunk).where(DocumentChunk.source_id == source.id)
                )
                await self.db.execute(delete(Document).where(Document.source_id == source.id))
                await self.db.commit()

            existing_by_ext: dict[str, Document] = {}
            if incremental:
                existing = await self.db.execute(
                    select(Document).where(
                        Document.source_id == source.id,
                        Document.deleted_at.is_(None),
                    )
                )
                existing_by_ext = {d.external_id: d for d in existing.scalars().all()}

            processed = 0
            failed = 0
            project_key = source.external_key or ""
            async for issue in client.iter_project_issues(
                project_key=project_key,
                updated_after=updated_after,
                include_changelog=include.get("change_history", False),
            ):
                await self._raise_if_cancelled(job)
                try:
                    nd = normalize_jira_issue(
                        issue, base_url=conn.base_url, include=include
                    )
                    ext_id = nd.external_id
                    doc = existing_by_ext.get(ext_id)
                    if doc is None:
                        doc = Document(
                            id=uuid4(),
                            workspace_id=source.workspace_id,
                            space_id=source.space_id,
                            source_id=source.id,
                            external_id=ext_id[:200],
                            document_type=DocumentType.JIRA_ISSUE,
                            title=nd.title[:500],
                            status=DocumentStatus.READY,
                            position=processed,
                            depth=0,
                            origin=DocumentOrigin.JIRA,
                            created_by_user_id=source.created_by_user_id,
                        )
                        self.db.add(doc)
                        existing_by_ext[ext_id] = doc
                    doc.title = nd.title[:500]
                    doc.normalized_content = nd.normalized_text
                    doc.raw_content = None
                    doc.content_checksum = hashlib.sha256(
                        nd.normalized_text.encode("utf-8")
                    ).hexdigest()
                    doc.external_url = nd.external_url
                    doc.external_version = nd.external_version
                    doc.status = DocumentStatus.READY
                    doc.origin = DocumentOrigin.JIRA
                    await self.db.flush()
                    await self.db.execute(
                        delete(DocumentChunk).where(DocumentChunk.document_id == doc.id)
                    )
                    await self._persist_chunk_hints(source, doc, nd.chunk_hints)
                    processed += 1
                    if processed % 10 == 0:
                        await self.db.commit()
                        await self._set_progress(
                            job,
                            stage=IngestionStage.CHUNKING,
                            percent=min(90, 20 + processed * 0.05),
                            message=f"Indexed {processed} issue(s)…",
                            ui_stage="INDEXING",
                            current_item={
                                "name": nd.title,
                                "status": "importing",
                                "type": "ISSUE",
                            },
                            stats={"processed_pages": processed, "failed_items": failed},
                        )
                except Exception as item_exc:  # noqa: BLE001
                    failed += 1
                    logger.warning("Jira issue failed: %s", item_exc)
                    await self._add_error(
                        job,
                        code="JIRA_ISSUE_FAILED",
                        message=str(item_exc)[:500],
                        external_item_id=str(issue.get("key") or ""),
                        item_type="ISSUE",
                    )

            await self.db.commit()
            source.status = SourceStatus.SYNCED if incremental else SourceStatus.READY
            source.last_sync_at = datetime.now(UTC)
            source.last_sync_status = (
                SyncStatus.PARTIAL if failed else SyncStatus.SUCCESS
            )
            source.last_sync_summary = {
                "added": processed,
                "updated": 0,
                "removed": 0,
                "unchanged": 0,
                "failed": failed,
            }
            complete_all_stages(job.progress_json or {})
            job.status = (
                IngestionJobStatus.COMPLETED_WITH_ERRORS
                if failed
                else IngestionJobStatus.COMPLETED
            )
            job.stage = IngestionStage.DONE
            job.progress_percent = 100
            job.completed_at = datetime.now(UTC)
            job.message = f"Imported {processed} issue(s)."
            flag_modified(job, "progress_json")
            await self.db.commit()
        except IngestionCancelled:
            source.status = SourceStatus.NEEDS_ATTENTION
            job.status = IngestionJobStatus.CANCELLED
            await self.db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Jira ingestion failed for job %s", job_id)
            code = getattr(exc, "code", None) or "JIRA_IMPORT_FAILED"
            if isinstance(exc, Exception) and "JiraClientError" in type(exc).__name__:
                code = getattr(exc, "code", None) or "JIRA_AUTH_FAILED"
            source.status = SourceStatus.FAILED
            source.error_code = str(code)[:64]
            source.error_message = str(getattr(exc, "message", exc))[:500]
            job.status = IngestionJobStatus.FAILED
            job.error_code = str(code)[:64]
            job.error_message = str(getattr(exc, "message", exc))[:500]
            job.completed_at = datetime.now(UTC)
            await self.db.commit()


async def run_ingestion_job(job_id: UUID) -> None:
    async with AsyncSessionLocal() as db:
        svc = IngestionService(db)
        result = await db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
        job = result.scalar_one_or_none()
        if job is None:
            return
        source = await svc._get_source(job.source_id)
        if source.type == SourceType.JIRA:
            if job.job_type == IngestionJobType.SYNC:
                await svc.run_jira_sync_job(job_id)
            else:
                await svc.run_jira_job(job_id)
        elif source.type in FILE_SOURCE_TYPES:
            await svc.run_file_job(job_id)
        elif job.job_type == IngestionJobType.SYNC:
            await svc.run_sync_job(job_id)
        else:
            await svc.run_direct_job(job_id)
