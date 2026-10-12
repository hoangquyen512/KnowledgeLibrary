from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService
from app.confluence.client import ConfluenceClient, ConfluenceClientError, normalize_cookie_header
from app.confluence.ssrf import (
    SsrfBlocked,
    assert_public_url,
    normalize_base_url,
    ssrf_http_exception,
)
from app.core.config import settings
from app.core.security import decrypt_secret, encrypt_secret, mask_secret
from app.ingestion.storage import get_object_storage
from app.models.audit import AuditAction
from app.models.confluence import (
    ConnectionAuthType,
    ConnectionMode,
    ConnectionStatus,
    ConfluenceConnection,
    CredentialLocation,
)
from app.models.document import Attachment, Document, DocumentChunk
from app.models.source import Source, SourceExternalType, SourceStatus, SourceType
from app.models.space import SpaceRole
from app.models.user import User
from app.models.workspace import WorkspaceRole
from app.permissions.service import PermissionService


class ConfluenceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.permissions = PermissionService(db)
        self.audit = AuditService(db)

    def _pack(self, *, username: str | None, secret: str) -> bytes:
        return encrypt_secret(json.dumps({"username": username or "", "secret": secret}))

    def _unpack(self, blob: bytes | None) -> tuple[str | None, str]:
        if not blob:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "CREDENTIALS_NOT_IN_CLOUD",
                    "message": "Credentials are stored on the Local Agent, not in the cloud.",
                },
            )
        data = json.loads(decrypt_secret(blob))
        username = (data.get("username") or "").strip() or None
        secret = (data.get("secret") or "").strip()
        if not secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "CONNECTION_INVALID", "message": "Stored credentials are empty."},
            )
        return username, secret

    def _normalize_secret(self, auth_type: str, secret: str) -> str:
        if auth_type == ConnectionAuthType.SESSION_COOKIE:
            return normalize_cookie_header(secret)
        return secret.strip()

    def _assert_auth_allowed(self, auth_type: str) -> None:
        if auth_type == ConnectionAuthType.SESSION_COOKIE and settings.is_production:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "AUTH_TYPE_FORBIDDEN",
                    "message": "Session cookie auth is not allowed in production. Use PAT.",
                },
            )
        if auth_type not in {ConnectionAuthType.PAT, ConnectionAuthType.SESSION_COOKIE}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_AUTH_TYPE", "message": "Unsupported auth type."},
            )

    def _assert_mode_and_location(
        self, *, connection_mode: str, credential_location: str
    ) -> None:
        if connection_mode not in {ConnectionMode.DIRECT, ConnectionMode.LOCAL_AGENT}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_CONNECTION_MODE", "message": "Unsupported connection mode."},
            )
        if credential_location not in {
            CredentialLocation.CLOUD,
            CredentialLocation.LOCAL_AGENT,
        }:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "INVALID_CREDENTIAL_LOCATION",
                    "message": "Unsupported credential location.",
                },
            )
        if (
            connection_mode == ConnectionMode.DIRECT
            and credential_location == CredentialLocation.LOCAL_AGENT
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "INVALID_MODE_LOCATION",
                    "message": "Direct mode requires CLOUD credentials.",
                },
            )

    async def list_connections(self, user: User, workspace_id: UUID) -> list[ConfluenceConnection]:
        await self.permissions.require_role(workspace_id, user.id, WorkspaceRole.VIEWER)
        result = await self.db.execute(
            select(ConfluenceConnection)
            .where(
                ConfluenceConnection.workspace_id == workspace_id,
                ConfluenceConnection.deleted_at.is_(None),
            )
            .order_by(ConfluenceConnection.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_connection(
        self, user: User, connection_id: UUID, *, min_role: str = WorkspaceRole.VIEWER
    ) -> ConfluenceConnection:
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
        await self.permissions.require_role(conn.workspace_id, user.id, min_role)
        return conn

    async def create_connection(
        self,
        user: User,
        workspace_id: UUID,
        *,
        name: str,
        base_url: str,
        auth_type: str,
        username: str | None,
        secret: str | None,
        connection_mode: str = ConnectionMode.DIRECT,
        credential_location: str = CredentialLocation.CLOUD,
        connector_agent_id: UUID | None = None,
    ) -> ConfluenceConnection:
        await self.permissions.require_role(workspace_id, user.id, WorkspaceRole.OWNER)
        self._assert_mode_and_location(
            connection_mode=connection_mode, credential_location=credential_location
        )
        self._assert_auth_allowed(auth_type)
        if connection_mode == ConnectionMode.LOCAL_AGENT and connector_agent_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "AGENT_REQUIRED",
                    "message": "Select a Local Agent for LOCAL_AGENT connection mode.",
                },
            )
        if connector_agent_id is not None:
            from app.models.agent import ConnectorAgent

            result = await self.db.execute(
                select(ConnectorAgent).where(
                    ConnectorAgent.id == connector_agent_id,
                    ConnectorAgent.workspace_id == workspace_id,
                    ConnectorAgent.revoked_at.is_(None),
                )
            )
            if result.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "AGENT_NOT_FOUND",
                        "message": "Connector agent not found in this workspace.",
                    },
                )

        encrypted: bytes | None = None
        masked = ""
        if credential_location == CredentialLocation.CLOUD:
            if auth_type == ConnectionAuthType.PAT and not (username or "").strip():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "USERNAME_REQUIRED",
                        "message": "Username/email is required for PAT auth.",
                    },
                )
            if not (secret or "").strip():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"code": "SECRET_REQUIRED", "message": "Credential secret is required."},
                )
            secret_clean = self._normalize_secret(auth_type, secret.strip())  # type: ignore[union-attr]
            encrypted = self._pack(
                username=(username or "").strip() or None, secret=secret_clean
            )
            masked = mask_secret(secret_clean)[-4:]
        else:
            masked = "local"

        conn = ConfluenceConnection(
            id=uuid4(),
            workspace_id=workspace_id,
            name=name.strip()[:120],
            base_url=normalize_base_url(base_url),
            connection_mode=connection_mode,
            credential_location=credential_location,
            connector_agent_id=connector_agent_id,
            auth_type=auth_type,
            encrypted_credentials=encrypted,
            masked_suffix=masked,
            status=ConnectionStatus.DRAFT,
            created_by_user_id=user.id,
        )
        self.db.add(conn)
        await self.audit.log(
            action=AuditAction.CREATE_CONFLUENCE_CONNECTION,
            resource_type="confluence_connection",
            actor_user_id=user.id,
            workspace_id=workspace_id,
            resource_id=conn.id,
            metadata={
                "name": conn.name,
                "auth_type": auth_type,
                "connection_mode": connection_mode,
                "credential_location": credential_location,
            },
        )
        await self.db.commit()
        await self.db.refresh(conn)
        return conn

    async def update_connection(
        self,
        user: User,
        connection_id: UUID,
        *,
        name: str | None = None,
        base_url: str | None = None,
        auth_type: str | None = None,
        username: str | None = None,
        secret: str | None = None,
        connection_mode: str | None = None,
        credential_location: str | None = None,
        connector_agent_id: UUID | None = None,
    ) -> ConfluenceConnection:
        conn = await self.get_connection(user, connection_id, min_role=WorkspaceRole.EDITOR)
        mode = connection_mode if connection_mode is not None else conn.connection_mode
        loc = credential_location if credential_location is not None else conn.credential_location
        self._assert_mode_and_location(connection_mode=mode, credential_location=loc)
        if name is not None:
            conn.name = name.strip()[:120]
        if base_url is not None:
            conn.base_url = normalize_base_url(base_url)
        if connection_mode is not None:
            conn.connection_mode = connection_mode
        if credential_location is not None:
            conn.credential_location = credential_location
            if credential_location == CredentialLocation.LOCAL_AGENT:
                conn.encrypted_credentials = None
                conn.masked_suffix = "local"
        if connector_agent_id is not None or (
            mode == ConnectionMode.LOCAL_AGENT and conn.connector_agent_id is None
        ):
            agent_id = connector_agent_id if connector_agent_id is not None else conn.connector_agent_id
            if mode == ConnectionMode.LOCAL_AGENT and agent_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "AGENT_REQUIRED",
                        "message": "Select a Local Agent for LOCAL_AGENT connection mode.",
                    },
                )
            if agent_id is not None:
                from app.models.agent import ConnectorAgent

                result = await self.db.execute(
                    select(ConnectorAgent).where(
                        ConnectorAgent.id == agent_id,
                        ConnectorAgent.workspace_id == conn.workspace_id,
                        ConnectorAgent.revoked_at.is_(None),
                    )
                )
                if result.scalar_one_or_none() is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "code": "AGENT_NOT_FOUND",
                            "message": "Connector agent not found in this workspace.",
                        },
                    )
                conn.connector_agent_id = agent_id
        if mode == ConnectionMode.DIRECT:
            conn.connector_agent_id = None
        if auth_type is not None:
            self._assert_auth_allowed(auth_type)
            conn.auth_type = auth_type
        if secret is not None and secret.strip():
            if conn.credential_location != CredentialLocation.CLOUD:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "CREDENTIALS_NOT_IN_CLOUD",
                        "message": "Cannot store cloud credentials when location is LOCAL_AGENT.",
                    },
                )
            self._assert_auth_allowed(conn.auth_type)
            user_name = username
            if user_name is None and conn.encrypted_credentials:
                existing_user, _ = self._unpack(conn.encrypted_credentials)
                user_name = existing_user
            if conn.auth_type == ConnectionAuthType.PAT and not (user_name or "").strip():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "USERNAME_REQUIRED",
                        "message": "Username/email is required for PAT auth.",
                    },
                )
            secret_clean = self._normalize_secret(conn.auth_type, secret.strip())
            conn.encrypted_credentials = self._pack(
                username=(user_name or "").strip() or None, secret=secret_clean
            )
            conn.masked_suffix = mask_secret(secret_clean)[-4:]
            conn.status = ConnectionStatus.DRAFT
            conn.last_error = None
        await self.audit.log(
            action=AuditAction.UPDATE_CONFLUENCE_CONNECTION,
            resource_type="confluence_connection",
            actor_user_id=user.id,
            workspace_id=conn.workspace_id,
            resource_id=conn.id,
            metadata={"name": conn.name},
        )
        await self.db.commit()
        await self.db.refresh(conn)
        return conn

    async def delete_connection(self, user: User, connection_id: UUID) -> None:
        conn = await self.get_connection(user, connection_id, min_role=WorkspaceRole.OWNER)
        active = await self.db.execute(
            select(Source).where(Source.connection_id == conn.id, Source.deleted_at.is_(None))
        )
        if active.scalars().first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "CONNECTION_IN_USE",
                    "message": "Detach or delete Sources using this connection first.",
                },
            )
        conn.deleted_at = datetime.now(UTC)
        conn.status = ConnectionStatus.DISABLED
        await self.audit.log(
            action=AuditAction.DELETE_CONFLUENCE_CONNECTION,
            resource_type="confluence_connection",
            actor_user_id=user.id,
            workspace_id=conn.workspace_id,
            resource_id=conn.id,
            metadata={"name": conn.name},
        )
        await self.db.commit()

    def _client_for(self, conn: ConfluenceConnection) -> ConfluenceClient:
        try:
            assert_public_url(
                conn.base_url,
                allow_http=not settings.is_production,
                allow_private=not settings.is_production,
            )
        except SsrfBlocked as exc:
            raise ssrf_http_exception(exc) from exc
        username, secret = self._unpack(conn.encrypted_credentials)
        return ConfluenceClient(
            base_url=conn.base_url,
            auth_type=conn.auth_type,
            username=username,
            secret=secret,
        )

    async def test_connection(self, user: User, connection_id: UUID) -> ConfluenceConnection:
        conn = await self.get_connection(user, connection_id, min_role=WorkspaceRole.OWNER)
        if conn.credential_location == CredentialLocation.LOCAL_AGENT or not conn.encrypted_credentials:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "TEST_VIA_AGENT_PENDING",
                    "message": (
                        "Cloud test requires CLOUD credentials. "
                        "Agent-mediated Confluence fetch arrives in Phase 6."
                    ),
                },
            )
        client = self._client_for(conn)
        try:
            result = await client.test()
            conn.status = ConnectionStatus.ACTIVE
            conn.last_error = None
            conn.detected_version = str(result.get("detected") or "ok")[:120]
            conn.last_tested_at = datetime.now(UTC)
        except ConfluenceClientError as exc:
            conn.status = ConnectionStatus.INVALID
            conn.last_error = exc.message[:500]
            conn.last_tested_at = datetime.now(UTC)
            await self.db.commit()
            await self.db.refresh(conn)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "CONNECTION_INVALID", "message": exc.message},
            ) from exc
        await self.audit.log(
            action=AuditAction.TEST_CONFLUENCE_CONNECTION,
            resource_type="confluence_connection",
            actor_user_id=user.id,
            workspace_id=conn.workspace_id,
            resource_id=conn.id,
            metadata={"status": conn.status},
        )
        await self.db.commit()
        await self.db.refresh(conn)
        return conn

    async def browse_spaces(
        self,
        user: User,
        connection_id: UUID,
        *,
        query: str | None = None,
        start: int = 0,
        limit: int = 25,
    ) -> dict:
        conn = await self.get_connection(user, connection_id, min_role=WorkspaceRole.EDITOR)
        if conn.status != ConnectionStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "CONNECTION_NOT_ACTIVE",
                    "message": "Test the connection successfully before browsing.",
                },
            )
        try:
            return await self._client_for(conn).list_spaces(query=query, start=start, limit=limit)
        except ConfluenceClientError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "CONFLUENCE_UNREACHABLE", "message": exc.message},
            ) from exc

    async def browse_pages(
        self,
        user: User,
        connection_id: UUID,
        space_key: str,
        *,
        start: int = 0,
        limit: int = 25,
    ) -> dict:
        conn = await self.get_connection(user, connection_id, min_role=WorkspaceRole.EDITOR)
        if conn.status != ConnectionStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "CONNECTION_NOT_ACTIVE",
                    "message": "Test the connection successfully before browsing.",
                },
            )
        try:
            return await self._client_for(conn).list_pages(
                space_key=space_key, start=start, limit=limit
            )
        except ConfluenceClientError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "CONFLUENCE_UNREACHABLE", "message": exc.message},
            ) from exc

    async def attach_source(
        self,
        user: User,
        space_id: UUID,
        *,
        connection_id: UUID,
        name: str,
        external_type: str,
        external_id: str,
        external_key: str | None,
        external_url: str | None,
        import_scope: str = "SPACE_TREE",
    ) -> Source:
        space, _role = await self.permissions.require_space_access(
            space_id, user.id, SpaceRole.EDITOR
        )
        conn = await self.get_connection(user, connection_id, min_role=WorkspaceRole.EDITOR)
        if conn.workspace_id != space.workspace_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "CONNECTION_WORKSPACE_MISMATCH",
                    "message": "Connection belongs to a different workspace.",
                },
            )
        if conn.status != ConnectionStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "CONNECTION_NOT_ACTIVE",
                    "message": "Connection must be ACTIVE before attaching a Source.",
                },
            )
        if external_type not in {SourceExternalType.SPACE, SourceExternalType.PAGE}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_EXTERNAL_TYPE", "message": "Invalid external type."},
            )
        existing = await self.db.execute(
            select(Source).where(
                Source.space_id == space_id,
                Source.external_id == external_id,
                Source.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "SOURCE_EXISTS",
                    "message": "This Confluence item is already attached to the Space.",
                },
            )
        source = Source(
            id=uuid4(),
            workspace_id=space.workspace_id,
            space_id=space_id,
            type=SourceType.CONFLUENCE,
            name=name.strip()[:200],
            status=SourceStatus.READY_TO_IMPORT,
            connection_id=conn.id,
            external_type=external_type,
            external_id=external_id[:200],
            external_key=external_key,
            external_url=external_url,
            import_scope=import_scope,
            created_by_user_id=user.id,
        )
        self.db.add(source)
        await self.audit.log(
            action=AuditAction.ATTACH_SOURCE,
            resource_type="source",
            actor_user_id=user.id,
            workspace_id=space.workspace_id,
            resource_id=source.id,
            metadata={
                "space_id": str(space_id),
                "external_type": external_type,
                "external_id": external_id,
            },
        )
        await self.db.commit()
        await self.db.refresh(source)
        return source

    async def list_sources(self, user: User, space_id: UUID) -> list[Source]:
        await self.permissions.require_space_access(space_id, user.id, SpaceRole.VIEWER)
        # Cleanup leftovers from older soft-deletes that left pages behind.
        await self._purge_pages_for_deleted_sources(space_id)
        result = await self.db.execute(
            select(Source)
            .where(Source.space_id == space_id, Source.deleted_at.is_(None))
            .order_by(Source.created_at.desc())
        )
        return list(result.scalars().all())

    async def _purge_pages_for_deleted_sources(self, space_id: UUID) -> None:
        deleted_sources = await self.db.execute(
            select(Source.id).where(
                Source.space_id == space_id,
                Source.deleted_at.is_not(None),
            )
        )
        ids = [row[0] for row in deleted_sources.all()]
        if not ids:
            return
        await self.db.execute(delete(DocumentChunk).where(DocumentChunk.source_id.in_(ids)))
        await self.db.execute(delete(Attachment).where(Attachment.source_id.in_(ids)))
        await self.db.execute(delete(Document).where(Document.source_id.in_(ids)))
        await self.db.commit()

    async def delete_source(self, user: User, source_id: UUID) -> None:
        result = await self.db.execute(
            select(Source).where(Source.id == source_id, Source.deleted_at.is_(None))
        )
        source = result.scalar_one_or_none()
        if source is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "SOURCE_NOT_FOUND", "message": "Source not found."},
            )
        await self.permissions.require_space_access(source.space_id, user.id, SpaceRole.EDITOR)
        if source.status == SourceStatus.IMPORTING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "SOURCE_IMPORTING",
                    "message": "Cannot delete a Source while import is running. Cancel the import first.",
                },
            )

        # Soft-delete alone does not cascade — remove all pages/attachments for this source.
        await self.db.execute(delete(DocumentChunk).where(DocumentChunk.source_id == source.id))
        await self.db.execute(delete(Attachment).where(Attachment.source_id == source.id))
        await self.db.execute(delete(Document).where(Document.source_id == source.id))

        # Best-effort object store cleanup (demo disk / S3).
        try:
            prefix = f"workspaces/{source.workspace_id}/sources/{source.id}/"
            get_object_storage().delete_prefix(prefix)
        except Exception:  # noqa: BLE001
            pass

        source.deleted_at = datetime.now(UTC)
        source.status = SourceStatus.DISABLED
        await self.audit.log(
            action=AuditAction.DELETE_SOURCE,
            resource_type="source",
            actor_user_id=user.id,
            workspace_id=source.workspace_id,
            resource_id=source.id,
            metadata={"name": source.name, "purged_pages": True},
        )
        await self.db.commit()
