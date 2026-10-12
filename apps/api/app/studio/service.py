from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ask.service import AskService
from app.core.security import decrypt_secret
from app.models.ai import AiUsage
from app.models.document import Document, DocumentChunk, DocumentStatus, DocumentType
from app.models.space import SpaceRole
from app.models.studio import (
    StudioArtifact,
    StudioArtifactSource,
    StudioArtifactStage,
    StudioArtifactStatus,
    StudioArtifactType,
)
from app.models.user import User
from app.models.workspace import WorkspaceRole
from app.permissions.service import PermissionService
from app.rag.gemini_models import gemini_generate_best
from app.studio.export_pptx import export_presentation_pptx
from app.studio.pack import (
    DEFAULT_CHAR_BUDGET,
    MAX_DOCUMENTS,
    PackResult,
    PackedSource,
    build_context_blocks,
    estimate_chars,
    snippet_from_content,
)
from app.studio.parse import parse_mindmap, parse_presentation
from app.studio.prompts import (
    map_summarize_prompt,
    mindmap_prompt,
    presentation_prompt,
    regenerate_slide_prompt,
)

logger = logging.getLogger(__name__)

ACTIVE_PAGE = (DocumentStatus.READY, DocumentStatus.DRAFT)


class StudioService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.permissions = PermissionService(db)
        self.ask = AskService(db)

    async def _resolve_gemini(self, user: User) -> tuple[str, str, str | None]:
        provider, mode = await self.ask.resolve_provider(user)
        cred = await self.ask.get_credential(user)
        api_key = decrypt_secret(cred.encrypted_api_key) if cred and cred.encrypted_api_key else ""
        preferred = cred.verified_model if cred else None
        return api_key, mode, preferred

    async def _generate_json(
        self,
        api_key: str,
        prompt: str,
        *,
        preferred_model: str | None,
    ) -> tuple[str, str, int, int]:
        data, model = await gemini_generate_best(
            api_key, prompt, preferred_model=preferred_model, json_mode=True
        )
        text = ""
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:  # noqa: BLE001
            text = json.dumps(data)[:8000]
        usage = data.get("usageMetadata") or {}
        in_tok = int(usage.get("promptTokenCount") or 0)
        out_tok = int(usage.get("candidatesTokenCount") or 0)
        return text, model, in_tok, out_tok

    async def _load_documents(
        self,
        user: User,
        workspace_id: UUID,
        space_ids: list[UUID],
        document_ids: list[UUID] | None,
    ) -> tuple[list[Document], bool]:
        await self.permissions.require_role(workspace_id, user.id, WorkspaceRole.VIEWER)
        for sid in space_ids:
            space = await self.permissions.require_space(sid)
            if space.workspace_id != workspace_id:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "SPACE_NOT_FOUND", "message": "Space not found."},
                )
            await self.permissions.require_space_access(sid, user.id, SpaceRole.VIEWER)

        capped = False
        if document_ids:
            result = await self.db.execute(
                select(Document).where(
                    Document.id.in_(document_ids),
                    Document.workspace_id == workspace_id,
                    Document.space_id.in_(space_ids),
                    Document.document_type == DocumentType.PAGE,
                    Document.status.in_(ACTIVE_PAGE),
                )
            )
            docs = list(result.scalars().all())
        else:
            result = await self.db.execute(
                select(Document)
                .where(
                    Document.workspace_id == workspace_id,
                    Document.space_id.in_(space_ids),
                    Document.document_type == DocumentType.PAGE,
                    Document.status.in_(ACTIVE_PAGE),
                )
                .order_by(Document.updated_at.desc())
                .limit(MAX_DOCUMENTS + 1)
            )
            docs = list(result.scalars().all())
            if len(docs) > MAX_DOCUMENTS:
                capped = True
                docs = docs[:MAX_DOCUMENTS]

        if not docs:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "NO_DOCUMENTS",
                    "message": "No indexed pages found in the selected scope.",
                },
            )
        return docs, capped

    async def _pack_sources(self, docs: list[Document]) -> list[PackedSource]:
        sources: list[PackedSource] = []
        idx = 1
        for doc in docs:
            chunk_result = await self.db.execute(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == doc.id)
                .order_by(DocumentChunk.chunk_index.asc())
            )
            chunks = list(chunk_result.scalars().all())
            if chunks:
                for chunk in chunks:
                    content = (chunk.content or "").strip()
                    if not content:
                        continue
                    meta = chunk.metadata_json or {}
                    section = (
                        str(meta.get("section_heading") or chunk.heading_path or doc.title or "")
                    )[:500]
                    sources.append(
                        PackedSource(
                            index=idx,
                            document_id=doc.id,
                            chunk_id=chunk.id,
                            space_id=doc.space_id,
                            title=doc.title or "Untitled",
                            content=content,
                            section_heading=section,
                            source_url=doc.external_url,
                            snippet=snippet_from_content(content),
                        )
                    )
                    idx += 1
            else:
                content = (doc.normalized_content or doc.raw_content or "").strip()
                if not content:
                    continue
                sources.append(
                    PackedSource(
                        index=idx,
                        document_id=doc.id,
                        chunk_id=None,
                        space_id=doc.space_id,
                        title=doc.title or "Untitled",
                        content=content[:12000],
                        section_heading=doc.title or "",
                        source_url=doc.external_url,
                        snippet=snippet_from_content(content),
                    )
                )
                idx += 1
        return sources

    async def _maybe_map_reduce(
        self,
        sources: list[PackedSource],
        api_key: str,
        preferred_model: str | None,
    ) -> tuple[list[PackedSource], bool, int, int]:
        total = estimate_chars(sources)
        if total <= DEFAULT_CHAR_BUDGET:
            return sources, False, 0, 0

        by_doc: dict[UUID, list[PackedSource]] = {}
        for src in sources:
            by_doc.setdefault(src.document_id, []).append(src)

        mapped: list[PackedSource] = []
        idx = 1
        in_tok = out_tok = 0
        for doc_id, doc_sources in by_doc.items():
            combined = "\n\n".join(s.content for s in doc_sources)[:20000]
            title = doc_sources[0].title
            prompt = map_summarize_prompt(title, combined)
            text, _model, i_t, o_t = await self._generate_json(
                api_key, prompt, preferred_model=preferred_model
            )
            in_tok += i_t
            out_tok += o_t
            first = doc_sources[0]
            mapped.append(
                PackedSource(
                    index=idx,
                    document_id=doc_id,
                    chunk_id=first.chunk_id,
                    space_id=first.space_id,
                    title=title,
                    content=text.strip()[:8000],
                    section_heading=first.section_heading,
                    source_url=first.source_url,
                    snippet=snippet_from_content(text),
                )
            )
            idx += 1
        return mapped, True, in_tok, out_tok

    async def create_artifact(
        self,
        user: User,
        *,
        workspace_id: UUID,
        artifact_type: str,
        title: str | None,
        focus_prompt: str | None,
        space_ids: list[UUID],
        document_ids: list[UUID] | None,
    ) -> StudioArtifact:
        docs, capped = await self._load_documents(user, workspace_id, space_ids, document_ids)
        default_title = (
            "Presentation"
            if artifact_type == StudioArtifactType.PRESENTATION
            else "Mind map"
        )
        artifact = StudioArtifact(
            id=uuid4(),
            user_id=user.id,
            workspace_id=workspace_id,
            artifact_type=artifact_type,
            title=(title or default_title)[:255],
            status=StudioArtifactStatus.QUEUED,
            focus_prompt=(focus_prompt or "").strip() or None,
            stage=StudioArtifactStage.QUEUED,
            warning_json={"documents_capped": capped} if capped else None,
        )
        self.db.add(artifact)
        await self.db.flush()
        for doc in docs:
            self.db.add(
                StudioArtifactSource(
                    artifact_id=artifact.id,
                    space_id=doc.space_id,
                    document_id=doc.id,
                )
            )
        await self.db.commit()
        await self.db.refresh(artifact)
        return artifact

    async def get_artifact(self, user: User, artifact_id: UUID) -> StudioArtifact:
        result = await self.db.execute(
            select(StudioArtifact).where(StudioArtifact.id == artifact_id)
        )
        artifact = result.scalar_one_or_none()
        if artifact is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "ARTIFACT_NOT_FOUND", "message": "Artifact not found."},
            )
        await self.permissions.require_role(artifact.workspace_id, user.id, WorkspaceRole.VIEWER)
        return artifact

    async def _require_owner(self, user: User, artifact: StudioArtifact) -> None:
        if artifact.user_id != user.id:
            raise HTTPException(
                status_code=403,
                detail={"code": "FORBIDDEN", "message": "You can only edit your own artifacts."},
            )

    async def list_artifacts(
        self,
        user: User,
        workspace_id: UUID,
        *,
        artifact_type: str | None = None,
    ) -> list[StudioArtifact]:
        await self.permissions.require_role(workspace_id, user.id, WorkspaceRole.VIEWER)
        q = select(StudioArtifact).where(
            StudioArtifact.user_id == user.id,
            StudioArtifact.workspace_id == workspace_id,
        )
        if artifact_type:
            q = q.where(StudioArtifact.artifact_type == artifact_type)
        q = q.order_by(StudioArtifact.updated_at.desc()).limit(50)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def artifact_source_ids(self, artifact_id: UUID) -> tuple[list[UUID], list[UUID]]:
        result = await self.db.execute(
            select(StudioArtifactSource).where(StudioArtifactSource.artifact_id == artifact_id)
        )
        rows = list(result.scalars().all())
        return [r.space_id for r in rows], [r.document_id for r in rows]

    async def update_artifact(
        self,
        user: User,
        artifact_id: UUID,
        *,
        title: str | None = None,
        slides: list[dict] | None = None,
        nodes: list[dict] | None = None,
    ) -> StudioArtifact:
        artifact = await self.get_artifact(user, artifact_id)
        self._require_owner(user, artifact)
        if artifact.status != StudioArtifactStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail={"code": "NOT_READY", "message": "Artifact is not ready for editing."},
            )
        if title:
            artifact.title = title.strip()[:255]
        payload = dict(artifact.payload_json or {})
        if slides is not None:
            payload["slides"] = slides
        if nodes is not None:
            payload["nodes"] = nodes
        artifact.payload_json = payload
        await self.db.commit()
        await self.db.refresh(artifact)
        return artifact

    async def delete_artifact(self, user: User, artifact_id: UUID) -> None:
        artifact = await self.get_artifact(user, artifact_id)
        self._require_owner(user, artifact)
        await self.db.delete(artifact)
        await self.db.commit()

    async def export_pptx(self, user: User, artifact_id: UUID) -> tuple[bytes, str]:
        artifact = await self.get_artifact(user, artifact_id)
        if artifact.artifact_type != StudioArtifactType.PRESENTATION:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_TYPE", "message": "Only presentations can export PPTX."},
            )
        if not artifact.payload_json:
            raise HTTPException(
                status_code=400,
                detail={"code": "NOT_READY", "message": "Presentation has no content yet."},
            )
        data = export_presentation_pptx(artifact.payload_json, deck_title=artifact.title)
        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in artifact.title)[:80]
        return data, f"{safe_name or 'presentation'}.pptx"

    async def _set_progress(
        self,
        artifact: StudioArtifact,
        *,
        stage: str,
        percent: float,
        status: str | None = None,
    ) -> None:
        artifact.stage = stage
        artifact.progress_percent = min(100.0, max(0.0, percent))
        if status:
            artifact.status = status
        await self.db.commit()

    async def run_generation(
        self,
        artifact_id: UUID,
        *,
        regenerate_slide_id: str | None = None,
    ) -> None:
        result = await self.db.execute(
            select(StudioArtifact).where(StudioArtifact.id == artifact_id)
        )
        artifact = result.scalar_one_or_none()
        if artifact is None:
            return

        user_result = await self.db.execute(
            select(User).where(User.id == artifact.user_id)
        )
        user = user_result.scalar_one_or_none()
        if user is None:
            return

        try:
            artifact.status = StudioArtifactStatus.RUNNING
            artifact.error_message = None
            artifact.stage = StudioArtifactStage.LOADING
            artifact.progress_percent = 5.0
            await self.db.commit()

            space_ids, document_ids = await self.artifact_source_ids(artifact.id)
            docs, capped = await self._load_documents(
                user, artifact.workspace_id, space_ids, document_ids or None
            )
            sources = await self._pack_sources(docs)
            if not sources:
                raise RuntimeError("No content available in selected documents.")

            api_key, mode, preferred = await self._resolve_gemini(user)

            await self._set_progress(artifact, stage=StudioArtifactStage.SUMMARIZING, percent=25.0)

            packed, map_used, map_in, map_out = await self._maybe_map_reduce(
                sources, api_key, preferred
            )
            warnings = dict(artifact.warning_json or {})
            if map_used:
                warnings["map_reduce_used"] = True
            if capped:
                warnings["documents_capped"] = True
            artifact.warning_json = warnings or None

            context = build_context_blocks(packed)
            await self._set_progress(artifact, stage=StudioArtifactStage.GENERATING, percent=55.0)

            total_in = map_in
            total_out = map_out

            if artifact.artifact_type == StudioArtifactType.PRESENTATION:
                if regenerate_slide_id and artifact.payload_json:
                    slides = artifact.payload_json.get("slides") or []
                    target = next(
                        (s for s in slides if s.get("id") == regenerate_slide_id), None
                    )
                    slide_title = str(target.get("title") if target else "Slide")
                    prompt = regenerate_slide_prompt(
                        context,
                        slide_title=slide_title,
                        focus_prompt=artifact.focus_prompt,
                    )
                else:
                    prompt = presentation_prompt(context, focus_prompt=artifact.focus_prompt)
                raw_text, model, in_t, out_t = await self._generate_json(
                    api_key, prompt, preferred_model=preferred
                )
                total_in += in_t
                total_out += out_t
                parsed = parse_presentation(raw_text, packed)
                if parsed is None:
                    raise RuntimeError("Could not parse presentation from model output.")
                if regenerate_slide_id and artifact.payload_json:
                    existing = list(artifact.payload_json.get("slides") or [])
                    new_slide = parsed["slides"][0] if parsed["slides"] else None
                    if new_slide:
                        new_slide["id"] = regenerate_slide_id
                        replaced = [
                            new_slide if s.get("id") == regenerate_slide_id else s for s in existing
                        ]
                        parsed = {"title": artifact.title, "slides": replaced}
                artifact.title = str(parsed.get("title") or artifact.title)[:255]
                artifact.payload_json = {"slides": parsed["slides"]}
            else:
                prompt = mindmap_prompt(context, focus_prompt=artifact.focus_prompt)
                raw_text, model, in_t, out_t = await self._generate_json(
                    api_key, prompt, preferred_model=preferred
                )
                total_in += in_t
                total_out += out_t
                parsed = parse_mindmap(raw_text, packed)
                if parsed is None:
                    raise RuntimeError("Could not parse mind map from model output.")
                artifact.payload_json = parsed

            artifact.status = StudioArtifactStatus.COMPLETED
            artifact.stage = StudioArtifactStage.DONE
            artifact.progress_percent = 100.0
            artifact.model_provider = mode
            artifact.model_name = model
            artifact.input_tokens = total_in
            artifact.output_tokens = total_out
            artifact.error_message = None

            self.db.add(
                AiUsage(
                    id=uuid4(),
                    user_id=user.id,
                    workspace_id=artifact.workspace_id,
                    conversation_id=None,
                    message_id=None,
                    provider=mode,
                    model_name=model,
                    input_tokens=total_in,
                    output_tokens=total_out,
                )
            )
            await self.db.commit()
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Studio generation failed for %s", artifact_id)
            artifact.status = StudioArtifactStatus.FAILED
            artifact.stage = StudioArtifactStage.DONE
            artifact.error_message = str(exc)[:1000]
            await self.db.commit()

    async def schedule_regenerate(
        self,
        user: User,
        artifact_id: UUID,
        *,
        slide_id: str | None = None,
        focus_prompt: str | None = None,
    ) -> StudioArtifact:
        artifact = await self.get_artifact(user, artifact_id)
        self._require_owner(user, artifact)
        if focus_prompt is not None:
            artifact.focus_prompt = focus_prompt.strip() or None
        artifact.status = StudioArtifactStatus.QUEUED
        artifact.stage = StudioArtifactStage.QUEUED
        artifact.progress_percent = 0.0
        artifact.error_message = None
        await self.db.commit()
        await self.db.refresh(artifact)
        return artifact


async def run_studio_generation(artifact_id: UUID, *, slide_id: str | None = None) -> None:
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await StudioService(db).run_generation(artifact_id, regenerate_slide_id=slide_id)
