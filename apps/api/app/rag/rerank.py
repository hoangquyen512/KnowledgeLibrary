from __future__ import annotations

import json
import logging
from uuid import UUID

from app.core.config import settings
from app.rag.gemini_models import gemini_generate_best
from app.rag.types import RetrievalHit

logger = logging.getLogger(__name__)


async def rerank_hits(
    api_key: str,
    query: str,
    hits: list[RetrievalHit],
    *,
    top_k: int | None = None,
    preferred_model: str | None = None,
) -> list[RetrievalHit]:
    """Listwise rerank with Gemini Flash; fall back to input order on failure."""
    if not hits:
        return []
    limit = top_k or settings.ask_rerank_top_k
    if len(hits) <= limit:
        return hits[:limit]

    items = []
    for hit in hits:
        items.append(
            {
                "id": str(hit.chunk_id),
                "title": hit.title,
                "section": hit.section_heading or hit.title,
                "snippet": (hit.snippet or hit.content or "")[:280],
            }
        )
    prompt = (
        "You are a search relevance reranker for an internal knowledge base.\n"
        "Rank the following document chunks by relevance to the user question.\n"
        "Respond with ONLY JSON: {\"ranked_ids\": [\"uuid\", ...]} listing ALL ids "
        "from most to least relevant.\n\n"
        f"Question: {query.strip()}\n\n"
        f"Chunks:\n{json.dumps(items, ensure_ascii=False)}\n"
    )
    try:
        data, _model = await gemini_generate_best(
            api_key,
            prompt,
            preferred_model=preferred_model,
            json_mode=True,
        )
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        payload = json.loads(text) if isinstance(text, str) else text
        ranked_raw = payload.get("ranked_ids") if isinstance(payload, dict) else []
        by_id = {str(hit.chunk_id): hit for hit in hits}
        ordered: list[RetrievalHit] = []
        seen: set[UUID] = set()
        for raw_id in ranked_raw or []:
            hit = by_id.get(str(raw_id))
            if hit is None or hit.chunk_id in seen:
                continue
            seen.add(hit.chunk_id)
            ordered.append(hit)
            if len(ordered) >= limit:
                break
        if ordered:
            for hit in hits:
                if hit.chunk_id in seen:
                    continue
                ordered.append(hit)
                if len(ordered) >= limit:
                    break
            return ordered[:limit]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini rerank failed, using RRF order: %s", exc)
    return hits[:limit]
