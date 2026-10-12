from __future__ import annotations

from uuid import UUID


def embedding_is_usable(vec: list[float] | None) -> bool:
    if not vec:
        return False
    return any(abs(v) > 1e-9 for v in vec)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


def rrf_fuse(
    ranked_lists: list[list[UUID]],
    *,
    k: int = 60,
) -> dict[UUID, float]:
    """Reciprocal rank fusion across ranked chunk-id lists."""
    scores: dict[UUID, float] = {}
    for ranked in ranked_lists:
        for rank, chunk_id in enumerate(ranked, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return scores
