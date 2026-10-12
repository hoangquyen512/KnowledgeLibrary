"""Jira connection + project source attachment."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService
from app.confluence.ssrf import SsrfBlocked, assert_public_url, normalize_base_url, ssrf_http_exception
from app.core.config import settings
from app.core.security import decrypt_secret, encrypt_secret, mask_secret
from app.jira.client import JiraClient, JiraClientError
from app.models.audit import AuditAction
from app.models.confluence import ConnectionAuthType, ConnectionMode, ConnectionStatus, CredentialLocation
from app.models.jira import JiraConnection
from app.models.source import Source, SourceExternalType, SourceStatus, SourceType
from app.models.space import SpaceRole
from app.models.user import User
from app.models.workspace import WorkspaceRole
from app.permissions.service import PermissionService


class JiraService:
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
                    "message": "Credentials are not stored for this connection.",
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

    def _client(self, conn: JiraConnection) -> JiraClient:
        username, secret = self._unpack(conn.encrypted_credentials)
        return JiraClient(
            base_url=conn.base_url,
            auth_type=conn.auth_type,
            username=username,
            secret=secret,
        )

    async def list_connections(self, user: User, workspace_id: UUID) -> list[JiraConnection]:
        await self.permissions.require_role(workspace_id, user.id, WorkspaceRole.VIEWER)
        result = await self.db.execute(
            select(JiraConnection).where(
                JiraConnection.workspace_id == workspace_id,
                JiraConnection.deleted_at.is_(None),
            ).order_by(JiraConnection.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_connection(
        self, user: User, connection_id: UUID, *, min_role: str = WorkspaceRole.VIEWER
    ) -> JiraConnection:
        result = await self.db.execute(
            select(JiraConnection).where(
                JiraConnection.id == connection_id,
                JiraConnection.deleted_at.is_(None),
            )
        )
        conn = result.scalar_one_or_none()
        if conn is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Jira connection not found."},
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
        auth_type: str = ConnectionAuthType.PAT,
        username: str | None = None,
        secret: str | None = None,
    ) -> JiraConnection:
        await self.permissions.require_role(workspace_id, user.id, WorkspaceRole.EDITOR)
        if auth_type not in {ConnectionAuthType.PAT, "BEARER", "BASIC"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_AUTH_TYPE", "message": "Supported: PAT, BEARER."},
            )
        if not (secret or "").strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "SECRET_REQUIRED", "message": "Token is required."},
            )
        try:
            assert_public_url(
                normalize_base_url(base_url),
                allow_http=not settings.is_production,
                allow_private=not settings.is_production,
            )
        except SsrfBlocked as exc:
            raise ssrf_http_exception(exc) from exc

        secret_clean = secret.strip()  # type: ignore[union-attr]
        conn = JiraConnection(
            id=uuid4(),
            workspace_id=workspace_id,
            name=name.strip()[:120],
            base_url=normalize_base_url(base_url),
            connection_mode=ConnectionMode.DIRECT,
            credential_location=CredentialLocation.CLOUD,
            auth_type=auth_type if auth_type != "BEARER" else ConnectionAuthType.PAT,
            encrypted_credentials=self._pack(username=username, secret=secret_clean),
            masked_suffix=mask_secret(secret_clean)[-4:],
            status=ConnectionStatus.DRAFT,
            created_by_user_id=user.id,
        )
        self.db.add(conn)
        await self.audit.log(
            action=AuditAction.ATTACH_SOURCE,
            resource_type="jira_connection",
            actor_user_id=user.id,
            workspace_id=workspace_id,
            resource_id=conn.id,
            metadata={"name": conn.name, "auth_type": conn.auth_type},
        )
        await self.db.commit()
        await self.db.refresh(conn)
        return conn

    async def test_connection(self, user: User, connection_id: UUID) -> JiraConnection:
        conn = await self.get_connection(user, connection_id, min_role=WorkspaceRole.EDITOR)
        try:
            assert_public_url(
                conn.base_url,
                allow_http=not settings.is_production,
                allow_private=not settings.is_production,
            )
            info = await self._client(conn).test_connection()
            conn.status = ConnectionStatus.ACTIVE
            conn.detected_version = str(info.get("version") or "")[:120]
            conn.last_error = None
            conn.last_tested_at = datetime.now(UTC)
        except (JiraClientError, SsrfBlocked) as exc:
            conn.status = ConnectionStatus.INVALID
            conn.last_error = getattr(exc, "message", str(exc))[:500]
            conn.last_tested_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(conn)
        return conn

    async def list_projects(
        self, user: User, connection_id: UUID, *, query: str | None = None
    ) -> list[dict[str, Any]]:
        conn = await self.get_connection(user, connection_id, min_role=WorkspaceRole.EDITOR)
        if conn.status != ConnectionStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "CONNECTION_INACTIVE", "message": "Test the connection first."},
            )
        try:
            return await self._client(conn).list_projects(query=query)
        except JiraClientError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": exc.code or "JIRA_API_ERROR", "message": exc.message},
            ) from exc

    async def attach_source(
        self,
        user: User,
        space_id: UUID,
        *,
        connection_id: UUID,
        name: str,
        project_id: str,
        project_key: str,
        project_url: str | None = None,
        scope: dict[str, bool] | None = None,
    ) -> Source:
        space, _role = await self.permissions.require_space_access(
            space_id, user.id, SpaceRole.EDITOR
        )
        conn = await self.get_connection(user, connection_id, min_role=WorkspaceRole.EDITOR)
        if space.workspace_id != conn.workspace_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "WORKSPACE_MISMATCH", "message": "Connection is in another workspace."},
            )
        default_scope = {
            "issues": True,
            "comments": True,
            "attachments": True,
            "description": True,
            "acceptance_criteria": True,
            "change_history": False,
        }
        if scope:
            default_scope.update({k: bool(v) for k, v in scope.items()})

        source = Source(
            id=uuid4(),
            workspace_id=space.workspace_id,
            space_id=space_id,
            type=SourceType.JIRA,
            name=name.strip()[:200],
            status=SourceStatus.READY_TO_IMPORT,
            jira_connection_id=conn.id,
            external_type=SourceExternalType.PROJECT,
            external_id=project_id,
            external_key=project_key,
            external_url=project_url,
            import_scope="PROJECT_ISSUES",
            config_json={"scope": default_scope},
            created_by_user_id=user.id,
        )
        self.db.add(source)
        await self.audit.log(
            action=AuditAction.ATTACH_SOURCE,
            resource_type="source",
            actor_user_id=user.id,
            workspace_id=space.workspace_id,
            resource_id=source.id,
            metadata={"name": source.name, "type": SourceType.JIRA, "project_key": project_key},
        )
        await self.db.commit()
        await self.db.refresh(source)
        return source
