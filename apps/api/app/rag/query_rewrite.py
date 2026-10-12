from __future__ import annotations

import json
import re

from app.core.config import settings
from app.rag.gemini_models import gemini_generate_best
from app.rag.search_tokens import extract_search_tokens


def should_rewrite_query(query: str) -> bool:
    tokens = extract_search_tokens(query)
    return len(tokens) <= settings.ask_query_rewrite_max_tokens


async def rewrite_query_variants(
    api_key: str,
    query: str,
    *,
    preferred_model: str | None = None,
) -> list[str]:
    """Return up to two alternative search queries for short/vague questions."""
    prompt = (
        "You help improve document search queries for a company knowledge base.\n"
        "Given a short or vague user question, produce exactly two alternative search queries "
        "that would retrieve relevant internal documentation.\n"
        "Keep the same language as the question.\n"
        "Respond with ONLY JSON: {\"variants\": [\"query1\", \"query2\"]}\n\n"
        f"Question: {query.strip()}\n"
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
        variants = payload.get("variants") if isinstance(payload, dict) else []
        out: list[str] = []
        seen = {query.strip().lower()}
        for item in variants or []:
            if not isinstance(item, str):
                continue
            cleaned = re.sub(r"\s+", " ", item).strip()
            if len(cleaned) < 3:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(cleaned)
            if len(out) >= 2:
                break
        return out
    except Exception:  # noqa: BLE001
        return []
