from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decrypt_secret, encrypt_secret, mask_secret
from app.models.ai import (
    AiCredentialStatus,
    AiUsage,
    Citation,
    Conversation,
    ConversationSpace,
    ConversationStatus,
    Message,
    MessageRole,
    UserAiCredential,
)
from app.models.space import SpaceRole
from app.models.user import User
from app.models.workspace import WorkspaceRole
from app.permissions.service import PermissionService
from app.rag.providers import GeminiProvider, LlmResult
from app.rag.retrieval import RetrievalHit, RetrievalService


class AskService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.permissions = PermissionService(db)
        self.retrieval = RetrievalService(db)

    async def get_credential(self, user: User) -> UserAiCredential | None:
        result = await self.db.execute(
            select(UserAiCredential).where(
                UserAiCredential.user_id == user.id,
                UserAiCredential.provider == "GEMINI",
            )
        )
        return result.scalar_one_or_none()

    async def credential_status(self, user: User) -> dict:
        cred = await self.get_credential(user)
        if cred is None or cred.status == AiCredentialStatus.DISCONNECTED:
            return {
                "provider": "GEMINI",
                "status": AiCredentialStatus.DISCONNECTED,
                "key_mask": None,
                "mode": "DISCONNECTED",
                "last_validated_at": None,
                "verified_model": None,
            }
        mode = "GEMINI" if cred.status == AiCredentialStatus.CONNECTED else "DISCONNECTED"
        verified_model = cred.verified_model
        if not verified_model and cred.encrypted_api_key and cred.status == AiCredentialStatus.CONNECTED:
            try:
                from app.rag.gemini_models import get_verified_model

                verified_model = get_verified_model(decrypt_secret(cred.encrypted_api_key))
            except Exception:  # noqa: BLE001
                verified_model = None
        return {
            "provider": "GEMINI",
            "status": cred.status,
            "key_mask": cred.key_mask,
            "mode": mode,
            "last_validated_at": cred.last_validated_at,
            "verified_model": verified_model,
        }

    async def save_gemini_key(
        self,
        user: User,
        api_key: str,
        *,
        verified_model: str | None = None,
    ) -> dict:
        key = (api_key or "").strip()
        if len(key) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_API_KEY", "message": "API key looks too short."},
            )
        ok, ping_model = await self._ping_gemini(key)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "GEMINI_KEY_INVALID",
                    "message": (
                        "Gemini API key could not generate a response. "
                        "Use a Google AI Studio key with access to Gemini 3.x Flash models."
                    ),
                },
            )

        cred = await self.get_credential(user)
        if cred is None:
            cred = UserAiCredential(id=uuid4(), user_id=user.id, provider="GEMINI")
            self.db.add(cred)
        cred.encrypted_api_key = encrypt_secret(key)
        cred.key_mask = mask_secret(key)
        cred.verified_model = ping_model or verified_model
        cred.status = AiCredentialStatus.CONNECTED
        cred.last_validated_at = datetime.now(UTC)
        await self.db.commit()
        data = await self.credential_status(user)
        resolved_model = ping_model or verified_model
        if resolved_model:
            data["verified_model"] = resolved_model
        return data

    async def test_gemini_key(
        self,
        user: User,
        api_key: str | None,
    ) -> dict:
        from app.rag.gemini_models import diagnose_gemini_api

        key = (api_key or "").strip()
        cred = await self.get_credential(user)
        if not key:
            if not cred or not cred.encrypted_api_key:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "GEMINI_NOT_CONNECTED",
                        "message": "Paste an API key or save one before testing.",
                    },
                )
            key = decrypt_secret(cred.encrypted_api_key).strip()
        elif len(key) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_API_KEY", "message": "API key looks too short."},
            )

        diag = await diagnose_gemini_api(key)
        if not diag.get("ok"):
            models = diag.get("available_models") or diag.get("sample_models") or []
            hint = f" Available: {', '.join(models[:8])}." if models else ""
            test_error = diag.get("test_error")
            detail_msg = (
                test_error
                or diag.get("list_error")
                or f"No working Gemini model found ({diag.get('models_listed', 0)} listed)."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "GEMINI_KEY_INVALID",
                    "message": detail_msg + hint,
                },
            )

        verified = diag.get("verified_model")
        validated_at = cred.last_validated_at if cred else None

        return {
            "provider": "GEMINI",
            "status": cred.status if cred else AiCredentialStatus.CONNECTED,
            "key_mask": mask_secret(key) if api_key else (cred.key_mask if cred else None),
            "mode": "GEMINI",
            "last_validated_at": validated_at,
            "verified_model": verified,
        }

    async def list_gemini_models_for_user(
        self,
        user: User,
        api_key: str | None = None,
    ) -> dict:
        from app.rag.gemini_models import list_gemini_models, pick_gemini_model, resolve_gemini_models

        key = (api_key or "").strip()
        cred = await self.get_credential(user)
        if not key:
            if not cred or not cred.encrypted_api_key:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "GEMINI_NOT_CONNECTED",
                        "message": "Paste an API key or save one before listing models.",
                    },
                )
            key = decrypt_secret(cred.encrypted_api_key).strip()
        elif len(key) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_API_KEY", "message": "API key looks too short."},
            )

        try:
            models = await resolve_gemini_models(key)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "GEMINI_MODEL_LIST_FAILED",
                    "message": f"Could not list Gemini models: {exc}"[:200],
                },
            ) from exc

        default_model = (
            cred.verified_model
            if cred and cred.verified_model and cred.verified_model in models
            else pick_gemini_model(models)
        )
        return {"models": models, "default_model": default_model}

    async def disconnect_gemini(self, user: User) -> dict:
        cred = await self.get_credential(user)
        if cred:
            cred.encrypted_api_key = None
            cred.key_mask = None
            cred.verified_model = None
            cred.status = AiCredentialStatus.DISCONNECTED
            cred.last_validated_at = None
            await self.db.commit()
        return await self.credential_status(user)

    async def _ping_gemini(self, api_key: str) -> tuple[bool, str | None]:
        from app.rag.gemini_models import ping_gemini_api

        return await ping_gemini_api(api_key, preferred_model=settings.gemini_model)

    @staticmethod
    def _is_gemini_model_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        return "404" in msg or "not found" in msg or "no longer available" in msg

    @staticmethod
    def _gemini_http_exception(exc: RuntimeError) -> HTTPException:
        msg = str(exc).lower()
        if "quota" in msg or "429" in msg:
            return HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "GEMINI_QUOTA",
                    "message": "Gemini quota is exhausted for this API key.",
                },
            )
        if AskService._is_gemini_model_error(exc):
            return HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "code": "GEMINI_MODEL_UNAVAILABLE",
                    "message": (
                        "Gemini model is unavailable. Open Settings → AI, click "
                        "Test connection, then save your API key again."
                    ),
                },
            )
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "GEMINI_ERROR",
                "message": str(exc)[:300],
            },
        )

    async def resolve_provider(self, user: User) -> tuple[GeminiProvider, str]:
        cred = await self.get_credential(user)
        if cred and cred.status == AiCredentialStatus.CONNECTED and cred.encrypted_api_key:
            try:
                api_key = decrypt_secret(cred.encrypted_api_key)
                preferred = cred.verified_model or settings.gemini_model
                return GeminiProvider(api_key, model=preferred), "GEMINI"
            except Exception:  # noqa: BLE001
                cred.status = AiCredentialStatus.INVALID
                cred.verified_model = None
                await self.db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "GEMINI_NOT_CONNECTED",
                "message": "Connect Gemini in AI Settings to use Ask AI.",
            },
        )

    async def create_conversation(
        self,
        user: User,
        workspace_id: UUID,
        *,
        title: str | None,
        space_ids: list[UUID],
    ) -> Conversation:
        await self.permissions.require_role(workspace_id, user.id, WorkspaceRole.VIEWER)
        if not space_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "SPACES_REQUIRED", "message": "Select at least one space."},
            )
        # Validate spaces
        for sid in space_ids:
            space = await self.permissions.require_space(sid)
            if space.workspace_id != workspace_id:
                raise HTTPException(status_code=404, detail={"code": "SPACE_NOT_FOUND", "message": "Space not found."})
            await self.permissions.require_space_access(sid, user.id, SpaceRole.VIEWER)

        conv = Conversation(
            id=uuid4(),
            user_id=user.id,
            workspace_id=workspace_id,
            title=(title or "New chat")[:255],
            status=ConversationStatus.ACTIVE,
        )
        self.db.add(conv)
        await self.db.flush()
        for sid in space_ids:
            self.db.add(ConversationSpace(conversation_id=conv.id, space_id=sid))
        await self.db.commit()
        await self.db.refresh(conv)
        return conv

    async def list_conversations(self, user: User, workspace_id: UUID) -> list[Conversation]:
        await self.permissions.require_role(workspace_id, user.id, WorkspaceRole.VIEWER)
        result = await self.db.execute(
            select(Conversation)
            .where(
                Conversation.workspace_id == workspace_id,
                Conversation.user_id == user.id,
                Conversation.status == ConversationStatus.ACTIVE,
            )
            .order_by(Conversation.updated_at.desc())
            .limit(50)
        )
        return list(result.scalars().all())

    async def get_conversation(self, user: User, conversation_id: UUID) -> Conversation:
        result = await self.db.execute(select(Conversation).where(Conversation.id == conversation_id))
        conv = result.scalar_one_or_none()
        if conv is None or conv.user_id != user.id:
            raise HTTPException(
                status_code=404,
                detail={"code": "CONVERSATION_NOT_FOUND", "message": "Conversation not found."},
            )
        await self.permissions.require_role(conv.workspace_id, user.id, WorkspaceRole.VIEWER)
        return conv

    async def conversation_space_ids(self, conversation_id: UUID) -> list[UUID]:
        result = await self.db.execute(
            select(ConversationSpace.space_id).where(ConversationSpace.conversation_id == conversation_id)
        )
        return list(result.scalars().all())

    async def list_messages(self, user: User, conversation_id: UUID) -> list[Message]:
        await self.get_conversation(user, conversation_id)
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .limit(200)
        )
        return list(result.scalars().all())

    async def list_citations(self, message_id: UUID) -> list[Citation]:
        result = await self.db.execute(
            select(Citation)
            .where(Citation.message_id == message_id)
            .order_by(Citation.citation_index.asc())
        )
        return list(result.scalars().all())

    async def ask(
        self,
        user: User,
        conversation_id: UUID,
        content: str,
        *,
        space_ids: list[UUID] | None = None,
        source_ids: list[UUID] | None = None,
    ) -> tuple[Message, Message, list[Citation], list[RetrievalHit], LlmResult, str]:
        question = (content or "").strip()
        if len(question) < 1:
            raise HTTPException(
                status_code=400,
                detail={"code": "EMPTY_MESSAGE", "message": "Message is empty."},
            )
        conv = await self.get_conversation(user, conversation_id)
        scoped = space_ids if space_ids else await self.conversation_space_ids(conv.id)
        if space_ids:
            # Keep conversation scope in sync with UI checkboxes.
            await self.db.execute(
                delete(ConversationSpace).where(ConversationSpace.conversation_id == conv.id)
            )
            for sid in scoped:
                space = await self.permissions.require_space(sid)
                if space.workspace_id != conv.workspace_id:
                    continue
                await self.permissions.require_space_access(sid, user.id, SpaceRole.VIEWER)
                self.db.add(ConversationSpace(conversation_id=conv.id, space_id=sid))
            await self.db.flush()

        provider, mode = await self.resolve_provider(user)
        cred = await self.get_credential(user)
        api_key = (
            decrypt_secret(cred.encrypted_api_key)
            if cred and cred.encrypted_api_key
            else None
        )
        preferred_model = cred.verified_model if cred else None
        hits = await self.retrieval.search(
            user,
            conv.workspace_id,
            question,
            space_ids=scoped or None,
            source_ids=source_ids,
            api_key=api_key,
            preferred_model=preferred_model,
        )

        async def _generate_once() -> LlmResult:
            return await provider.generate(question, hits)

        try:
            result = await _generate_once()
        except RuntimeError as exc:
            if cred and self._is_gemini_model_error(exc):
                cred.verified_model = None
                await self.db.commit()
                provider, mode = await self.resolve_provider(user)
                try:
                    result = await _generate_once()
                except RuntimeError as retry_exc:
                    raise self._gemini_http_exception(retry_exc) from retry_exc
            else:
                raise self._gemini_http_exception(exc) from exc

        if cred and result.model_name and cred.verified_model != result.model_name:
            cred.verified_model = result.model_name
            await self.db.commit()

        unique_docs = {h.document_id for h in hits}
        user_msg = Message(
            id=uuid4(),
            conversation_id=conv.id,
            user_id=user.id,
            role=MessageRole.USER,
            content=question,
            metadata_json={"space_ids": [str(s) for s in (scoped or [])]},
        )
        self.db.add(user_msg)
        await self.db.flush()

        assistant = Message(
            id=uuid4(),
            conversation_id=conv.id,
            user_id=None,
            role=MessageRole.ASSISTANT,
            content=result.text,
            model_provider=result.provider,
            model_name=result.model_name,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            metadata_json={
                "mode": mode,
                "hit_count": len(hits),
                "retrieved_chunk_count": len(hits),
                "unique_document_count": len(unique_docs),
                "structured": result.structured,
                "answer_type": (result.structured or {}).get("answer_type")
                if result.structured
                else None,
            },
        )
        self.db.add(assistant)
        await self.db.flush()

        citations: list[Citation] = []
        source_by_id: dict[int, dict] = {}
        if result.structured and isinstance(result.structured.get("sources"), list):
            for row in result.structured["sources"]:
                if isinstance(row, dict) and row.get("id") is not None:
                    try:
                        source_by_id[int(row["id"])] = row
                    except (TypeError, ValueError):
                        continue

        for idx in result.cited_indices:
            if idx < 1 or idx > len(hits):
                continue
            hit = hits[idx - 1]
            src = source_by_id.get(idx, {})
            cit = Citation(
                id=uuid4(),
                message_id=assistant.id,
                document_id=hit.document_id,
                chunk_id=hit.chunk_id,
                citation_index=idx,
                snippet=(
                    str(src.get("quoted_snippet") or hit.snippet or "")[:500] or None
                ),
                section_heading=(
                    str(
                        src.get("section_heading")
                        or hit.citation_label
                        or hit.section_heading
                        or ""
                    )[:500]
                    or None
                ),
                source_url=(
                    str(src.get("source_url") or hit.source_url or "")[:1000] or None
                ),
            )
            self.db.add(cit)
            citations.append(cit)

        self.db.add(
            AiUsage(
                id=uuid4(),
                user_id=user.id,
                workspace_id=conv.workspace_id,
                conversation_id=conv.id,
                message_id=assistant.id,
                provider=result.provider,
                model_name=result.model_name,
                input_tokens=result.input_tokens or 0,
                output_tokens=result.output_tokens or 0,
            )
        )
        if not conv.title or conv.title == "New chat":
            conv.title = question[:80]
        await self.db.commit()
        for c in citations:
            await self.db.refresh(c)
        await self.db.refresh(user_msg)
        await self.db.refresh(assistant)
        return user_msg, assistant, citations, hits, result, mode

    async def rename_conversation(self, user: User, conversation_id: UUID, title: str) -> Conversation:
        conv = await self.get_conversation(user, conversation_id)
        cleaned = (title or "").strip()
        if not cleaned:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_TITLE", "message": "Title is required."},
            )
        conv.title = cleaned[:255]
        await self.db.commit()
        await self.db.refresh(conv)
        return conv

    async def delete_conversation(self, user: User, conversation_id: UUID) -> None:
        conv = await self.get_conversation(user, conversation_id)
        conv.status = ConversationStatus.ARCHIVED
        await self.db.commit()
