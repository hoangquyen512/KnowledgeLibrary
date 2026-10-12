from __future__ import annotations

import hashlib
import logging
import struct

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _local_stub_embedding(text: str, dim: int) -> list[float]:
    """Deterministic local stub — same contract as apps/embedding-service."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    seed = digest
    while len(values) < dim:
        for i in range(0, len(seed), 4):
            if len(values) >= dim:
                break
            chunk = seed[i : i + 4]
            if len(chunk) < 4:
                chunk = chunk + b"\x00" * (4 - len(chunk))
            (n,) = struct.unpack("!I", chunk)
            values.append((n / 2**32) * 2 - 1)
        seed = hashlib.sha256(seed).digest()
    norm = sum(v * v for v in values) ** 0.5 or 1.0
    return [v / norm for v in values]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    # Keep payload sizes bounded so the embedding service / stub stays responsive.
    batch_size = 32
    if len(texts) > batch_size:
        out: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            out.extend(await embed_texts(texts[i : i + batch_size]))
        return out
    url = f"{settings.embedding_service_url.rstrip('/')}/v1/embeddings"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                json={"model": settings.embedding_model, "texts": texts},
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings") or []
            if len(embeddings) != len(texts):
                raise RuntimeError("Embedding count mismatch")
            return embeddings
    except Exception as exc:  # noqa: BLE001
        logger.warning("Embedding service unavailable (%s); using local stub vectors", exc)
        dim = settings.embedding_dimension
        return [_local_stub_embedding(text, dim) for text in texts]
