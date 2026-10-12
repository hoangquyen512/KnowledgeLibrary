"""Deterministic stub embedding service for local MVP boot.

Replace with real BGE-M3 (or adapter) without changing the HTTP contract.
"""

from __future__ import annotations

import hashlib
import os
import struct

from fastapi import FastAPI
from pydantic import BaseModel, Field

DIMENSION = int(os.environ.get("EMBEDDING_DIMENSION", "1024"))

app = FastAPI(title="Embedding Service Stub", version="0.1.0")


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1)
    model: str | None = None


class EmbedResponse(BaseModel):
    model: str
    dimension: int
    embeddings: list[list[float]]


def _embed_one(text: str, dim: int) -> list[float]:
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
    # L2 normalize
    norm = sum(v * v for v in values) ** 0.5 or 1.0
    return [v / norm for v in values]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/embeddings", response_model=EmbedResponse)
def embed(req: EmbedRequest) -> EmbedResponse:
    model = req.model or os.environ.get("EMBEDDING_MODEL", "bge-m3-stub")
    return EmbedResponse(
        model=model,
        dimension=DIMENSION,
        embeddings=[_embed_one(t, DIMENSION) for t in req.texts],
    )
