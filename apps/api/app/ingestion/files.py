"""File upload sources: store blob, preview, enqueue import."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService
from app.core.config import settings
from app.ingestion.file_validate import (
    DEFAULT_MAX_UPLOAD_BYTES,
    sha256_bytes,
    validate_upload,
)
from app.ingestion.parsers import ensure_parsers_loaded, get_parser
from app.ingestion.storage import get_object_storage
from app.models.audit import AuditAction
from app.models.source import FILE_SOURCE_TYPES, Source, SourceExternalType, SourceStatus, SourceType
from app.models.source_file import SourceFile
from app.models.space import SpaceRole
from app.models.user import User
from app.permissions.service import PermissionService


def _max_upload_bytes() -> int:
    configured = getattr(settings, "max_upload_bytes", None)
    if isinstance(configured, int) and configured > 0:
        return configured
    return DEFAULT_MAX_UPLOAD_BYTES


class FileSourceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.permissions = PermissionService(db)
        self.audit = AuditService(db)

    async def upload(
        self,
        user: User,
        space_id: UUID,
        *,
        upload: UploadFile,
        expected_source_type: str | None = None,
        force_new: bool = False,
        replace_source_id: UUID | None = None,
        import_options: dict[str, Any] | None = None,
        auto_import: bool = True,
    ) -> dict[str, Any]:
        space, _ = await self.permissions.require_space_access(
            space_id, user.id, SpaceRole.EDITOR
        )
        raw = await upload.read()
        source_type, safe_name = validate_upload(
            filename=upload.filename or "file",
            content_type=upload.content_type,
            data=raw,
            expected_source_type=expected_source_type,
            max_bytes=_max_upload_bytes(),
        )
        checksum = sha256_bytes(raw)

        replace_source: Source | None = None
        if replace_source_id is not None:
            result = await self.db.execute(
                select(Source).where(
                    Source.id == replace_source_id,
                    Source.space_id == space_id,
                    Source.deleted_at.is_(None),
                )
            )
            replace_source = result.scalar_one_or_none()
            if replace_source is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "NOT_FOUND", "message": "Source to replace not found."},
                )
            if replace_source.type not in FILE_SOURCE_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "NOT_FILE_SOURCE",
                        "message": "Only file sources support Replace.",
                    },
                )

        # Dedup within space (active sources only) — skip when explicitly replacing a source
        existing = await self.db.execute(
            select(SourceFile, Source)
            .join(Source, Source.id == SourceFile.source_id)
            .where(
                SourceFile.space_id == space_id,
                SourceFile.checksum_sha256 == checksum,
                SourceFile.is_active.is_(True),
                Source.deleted_at.is_(None),
            )
            .limit(1)
        )
        dup_row = existing.first()
        if dup_row is not None and not force_new and replace_source is None:
            _sf, src = dup_row
            return {
                "source_id": str(src.id),
                "job_id": None,
                "filename": safe_name,
                "status": src.status,
                "duplicate": True,
                "message": "This file already exists in this Space.",
            }

        ensure_parsers_loaded()
        parser = get_parser(source_type)
        preview_result = parser.parse(raw, filename=safe_name, options=import_options)
        if preview_result.error_code and not preview_result.documents and source_type != SourceType.FILE_EXCEL:
            if preview_result.error_code == "OCR_REQUIRED":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "OCR_REQUIRED",
                        "message": preview_result.error_message or "OCR required.",
                    },
                )

        storage = get_object_storage()
        version = 1
        source: Source

        if replace_source is not None or (dup_row is not None and force_new):
            if replace_source is not None:
                old_src = replace_source
            else:
                _old_sf, old_src = dup_row  # type: ignore[misc]
            # Deactivate prior active file versions for this source
            prior = await self.db.execute(
                select(SourceFile).where(
                    SourceFile.source_id == old_src.id,
                    SourceFile.is_active.is_(True),
                )
            )
            max_ver = 0
            for old_sf in prior.scalars().all():
                old_sf.is_active = False
                max_ver = max(max_ver, int(old_sf.version or 1))
            version = max_ver + 1
            source_id = old_src.id
            storage_key = (
                f"workspaces/{space.workspace_id}/sources/{source_id}/original/"
                f"{uuid4().hex}_{safe_name}"
            )
            storage.put_bytes(
                storage_key, raw, content_type=upload.content_type or "application/octet-stream"
            )
            old_src.name = safe_name[:200]
            old_src.type = source_type
            old_src.status = SourceStatus.UPLOADED
            old_src.error_code = None
            old_src.error_message = None
            old_src.external_id = checksum[:32]
            old_src.external_key = safe_name
            old_src.config_json = {
                "import_options": import_options or {},
                "preview": preview_result.preview,
            }
            old_src.metadata_json = {
                "filename": safe_name,
                "mime_type": upload.content_type,
                "size_bytes": len(raw),
                "checksum": checksum,
            }
            source = old_src
        else:
            source_id = uuid4()
            storage_key = (
                f"workspaces/{space.workspace_id}/sources/{source_id}/original/"
                f"{uuid4().hex}_{safe_name}"
            )
            storage.put_bytes(
                storage_key, raw, content_type=upload.content_type or "application/octet-stream"
            )
            source = Source(
                id=source_id,
                workspace_id=space.workspace_id,
                space_id=space_id,
                type=source_type,
                name=safe_name[:200],
                status=SourceStatus.UPLOADED,
                external_type=SourceExternalType.FILE,
                external_id=checksum[:32],
                external_key=safe_name,
                import_scope="FILE",
                config_json={
                    "import_options": import_options or {},
                    "preview": preview_result.preview,
                },
                metadata_json={
                    "filename": safe_name,
                    "mime_type": upload.content_type,
                    "size_bytes": len(raw),
                    "checksum": checksum,
                },
                created_by_user_id=user.id,
            )
            self.db.add(source)

        sf = SourceFile(
            id=uuid4(),
            source_id=source_id,
            workspace_id=space.workspace_id,
            space_id=space_id,
            storage_key=storage_key,
            original_filename=safe_name,
            display_name=safe_name,
            mime_type=upload.content_type or "application/octet-stream",
            size_bytes=len(raw),
            checksum_sha256=checksum,
            version=version,
            is_active=True,
            created_by_user_id=user.id,
        )
        self.db.add(sf)
        await self.audit.log(
            action=AuditAction.ATTACH_SOURCE,
            resource_type="source",
            actor_user_id=user.id,
            workspace_id=space.workspace_id,
            resource_id=source_id,
            metadata={
                "name": safe_name,
                "type": source_type,
                "size_bytes": len(raw),
                "replaced": replace_source is not None,
                "version": version,
            },
        )
        await self.db.commit()
        await self.db.refresh(source)

        needs_sheet_confirm = (
            source_type == SourceType.FILE_EXCEL
            and not (import_options or {}).get("sheet_names")
        )

        job_id = None
        if auto_import and not needs_sheet_confirm:
            from app.ingestion.service import IngestionService

            job = await IngestionService(self.db).start_import(
                user, source.id, options=import_options
            )
            job_id = str(job.id)

        return {
            "source_id": str(source.id),
            "job_id": job_id,
            "filename": safe_name,
            "status": source.status,
            "duplicate": False,
            "preview": preview_result.preview,
            "warnings": preview_result.warnings,
        }

    async def confirm_import(
        self,
        user: User,
        source_id: UUID,
        *,
        options: dict[str, Any] | None = None,
    ):
        from app.ingestion.service import IngestionService

        result = await self.db.execute(
            select(Source).where(Source.id == source_id, Source.deleted_at.is_(None))
        )
        source = result.scalar_one_or_none()
        if source is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Source not found."},
            )
        if source.type not in FILE_SOURCE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "NOT_FILE_SOURCE", "message": "Source is not a file upload."},
            )
        if options:
            cfg = dict(source.config_json or {})
            cfg["import_options"] = {**(cfg.get("import_options") or {}), **options}
            source.config_json = cfg
            await self.db.commit()
        return await IngestionService(self.db).start_import(user, source_id, options=options)
