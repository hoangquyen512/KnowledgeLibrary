from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ask.service import AskService
from app.auth.deps import get_current_user, require_csrf
from app.core.database import get_db
from app.models.document import Document
from app.models.user import User
from app.rag.providers import stream_text
from app.rag.retrieval import RetrievalService
from app.schemas.ask import (
    AiCredentialIn,
    AiCredentialOut,
    AiCredentialTestIn,
    AiCredentialTestOut,
    AiModelsOut,
    CitationOut,
    ConversationCreate,
    ConversationOut,
    ConversationUpdate,
    MessageCreate,
    MessageOut,
    SearchHitOut,
    SearchRequest,
)

router = APIRouter(tags=["ask"])


@router.get("/me/ai-credentials", response_model=AiCredentialOut)
async def get_ai_credentials(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiCredentialOut:
    data = await AskService(db).credential_status(user)
    return AiCredentialOut(**data)


@router.put("/me/ai-credentials", response_model=AiCredentialOut)
async def put_ai_credentials(
    body: AiCredentialIn,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> AiCredentialOut:
    svc = AskService(db)
    if body.test_only:
        data = await svc.test_gemini_key(user, body.api_key)
        return AiCredentialOut(**data)
    if not body.api_key or len(body.api_key.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_API_KEY", "message": "API key looks too short."},
        )
    data = await svc.save_gemini_key(
        user, body.api_key, verified_model=body.verified_model
    )
    return AiCredentialOut(**data)


@router.post("/me/ai-credentials/test", response_model=AiCredentialTestOut)
async def test_ai_credentials(
    body: AiCredentialTestIn | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiCredentialTestOut:
    from app.core.security import decrypt_secret
    from app.rag.gemini_models import diagnose_gemini_api

    svc = AskService(db)
    pasted = (body.api_key if body else None) or ""
    key = pasted.strip()
    if not key:
        cred = await svc.get_credential(user)
        if not cred or not cred.encrypted_api_key:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "GEMINI_NOT_CONNECTED",
                    "message": "Paste an API key or save one before testing.",
                },
            )
        key = decrypt_secret(cred.encrypted_api_key)
    elif len(key) < 10:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_API_KEY", "message": "API key looks too short."},
        )

    data = await diagnose_gemini_api(key)
    return AiCredentialTestOut(**data)


@router.get("/me/ai-credentials/models", response_model=AiModelsOut)
async def list_ai_credential_models(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiModelsOut:
    data = await AskService(db).list_gemini_models_for_user(user)
    return AiModelsOut(**data)


@router.post("/me/ai-credentials/models", response_model=AiModelsOut)
async def list_ai_credential_models_for_key(
    body: AiCredentialTestIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiModelsOut:
    data = await AskService(db).list_gemini_models_for_user(user, body.api_key)
    return AiModelsOut(**data)


@router.delete("/me/ai-credentials", response_model=AiCredentialOut)
async def delete_ai_credentials(
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> AiCredentialOut:
    data = await AskService(db).disconnect_gemini(user)
    return AiCredentialOut(**data)


@router.post("/workspaces/{workspace_id}/search", response_model=list[SearchHitOut])
async def workspace_search(
    workspace_id: UUID,
    body: SearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SearchHitOut]:
    hits = await RetrievalService(db).search(
        user,
        workspace_id,
        body.q,
        space_ids=body.space_ids,
        source_ids=body.source_ids,
        limit=body.limit,
    )
    return [
        SearchHitOut(
            chunk_id=h.chunk_id,
            document_id=h.document_id,
            space_id=h.space_id,
            title=h.title,
            snippet=h.snippet,
            score=h.score,
        )
        for h in hits
    ]


@router.get("/workspaces/{workspace_id}/search", response_model=list[SearchHitOut])
async def workspace_search_get(
    workspace_id: UUID,
    q: str = Query(min_length=2),
    space_id: UUID | None = None,
    limit: int = Query(default=12, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SearchHitOut]:
    hits = await RetrievalService(db).search(
        user,
        workspace_id,
        q,
        space_ids=[space_id] if space_id else None,
        limit=limit,
    )
    return [
        SearchHitOut(
            chunk_id=h.chunk_id,
            document_id=h.document_id,
            space_id=h.space_id,
            title=h.title,
            snippet=h.snippet,
            score=h.score,
        )
        for h in hits
    ]


async def _conversation_out(svc: AskService, conv) -> ConversationOut:
    space_ids = await svc.conversation_space_ids(conv.id)
    return ConversationOut(
        id=conv.id,
        workspace_id=conv.workspace_id,
        title=conv.title,
        status=conv.status,
        space_ids=space_ids,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.get("/workspaces/{workspace_id}/conversations", response_model=list[ConversationOut])
async def list_conversations(
    workspace_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationOut]:
    svc = AskService(db)
    rows = await svc.list_conversations(user, workspace_id)
    return [await _conversation_out(svc, c) for c in rows]


@router.post("/workspaces/{workspace_id}/conversations", response_model=ConversationOut, status_code=201)
async def create_conversation(
    workspace_id: UUID,
    body: ConversationCreate,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> ConversationOut:
    svc = AskService(db)
    conv = await svc.create_conversation(
        user, workspace_id, title=body.title, space_ids=body.space_ids
    )
    return await _conversation_out(svc, conv)


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationOut:
    svc = AskService(db)
    conv = await svc.get_conversation(user, conversation_id)
    return await _conversation_out(svc, conv)


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
async def rename_conversation(
    conversation_id: UUID,
    body: ConversationUpdate,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> ConversationOut:
    svc = AskService(db)
    conv = await svc.rename_conversation(user, conversation_id, body.title)
    return await _conversation_out(svc, conv)


@router.delete("/conversations/{conversation_id}", status_code=204, response_class=Response)
async def delete_conversation(
    conversation_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> Response:
    svc = AskService(db)
    await svc.delete_conversation(user, conversation_id)
    return Response(status_code=204)


def _message_meta(m) -> tuple[dict | None, int | None, int | None, list[UUID]]:
    meta = m.metadata_json or {}
    structured = meta.get("structured") if isinstance(meta.get("structured"), dict) else None
    chunk_count = meta.get("retrieved_chunk_count")
    doc_count = meta.get("unique_document_count")
    space_ids: list[UUID] = []
    for raw in meta.get("space_ids") or []:
        try:
            space_ids.append(UUID(str(raw)))
        except (TypeError, ValueError):
            continue
    return structured, chunk_count, doc_count, space_ids


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    svc = AskService(db)
    messages = await svc.list_messages(user, conversation_id)
    out: list[MessageOut] = []
    for m in messages:
        cites = await svc.list_citations(m.id)
        titles: dict[UUID, str] = {}
        space_by_doc: dict[UUID, UUID] = {}
        if cites:
            doc_ids = {c.document_id for c in cites}
            result = await db.execute(select(Document).where(Document.id.in_(doc_ids)))
            for d in result.scalars().all():
                titles[d.id] = d.title
                space_by_doc[d.id] = d.space_id
        structured, chunk_count, doc_count, space_ids = _message_meta(m)
        out.append(
            MessageOut(
                id=m.id,
                conversation_id=m.conversation_id,
                role=m.role,
                content=m.content,
                model_provider=m.model_provider,
                model_name=m.model_name,
                created_at=m.created_at,
                citations=[
                    CitationOut(
                        id=c.id,
                        document_id=c.document_id,
                        chunk_id=c.chunk_id,
                        citation_index=c.citation_index,
                        snippet=c.snippet,
                        title=titles.get(c.document_id),
                        space_id=space_by_doc.get(c.document_id),
                        section_heading=c.section_heading,
                        source_url=c.source_url,
                    )
                    for c in cites
                ],
                structured=structured,
                retrieved_chunk_count=chunk_count,
                unique_document_count=doc_count,
                space_ids=space_ids,
            )
        )
    return out


@router.post("/conversations/{conversation_id}/messages")
async def post_message(
    conversation_id: UUID,
    body: MessageCreate,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
):
    svc = AskService(db)
    try:
        user_msg, assistant, citations, hits, result, mode = await svc.ask(
            user,
            conversation_id,
            body.content,
            space_ids=body.space_ids,
            source_ids=body.source_ids,
        )
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise AskService._gemini_http_exception(exc) from exc
    hit_by_idx = {i: h for i, h in enumerate(hits, start=1)}
    cite_payload = []
    for c in citations:
        hit = hit_by_idx.get(c.citation_index)
        cite_payload.append(
            {
                "id": str(c.id),
                "document_id": str(c.document_id),
                "chunk_id": str(c.chunk_id),
                "citation_index": c.citation_index,
                "snippet": c.snippet,
                "title": hit.title if hit else None,
                "space_id": str(hit.space_id) if hit else None,
                "section_heading": c.section_heading or (hit.section_heading if hit else None),
                "source_url": c.source_url or (hit.source_url if hit else None),
            }
        )

    unique_docs = {h.document_id for h in hits}
    meta_payload = {
        "mode": mode,
        "provider": result.provider,
        "user_message_id": str(user_msg.id),
        "assistant_message_id": str(assistant.id),
        "retrieved_chunk_count": len(hits),
        "unique_document_count": len(unique_docs),
    }

    async def event_stream():
        yield f"event: meta\ndata: {json.dumps(meta_payload)}\n\n"
        if result.structured:
            yield f"event: structured\ndata: {json.dumps({'structured': result.structured})}\n\n"
        async for piece in stream_text(result.text):
            yield f"event: token\ndata: {json.dumps({'text': piece})}\n\n"
        yield f"event: citations\ndata: {json.dumps({'citations': cite_payload})}\n\n"
        yield f"event: done\ndata: {json.dumps({'ok': True})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
