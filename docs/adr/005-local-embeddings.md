# ADR 005: Local / System-Hosted Embeddings

## Context

Indexing is a Workspace asset shared by many users; tying embeddings to an Owner’s Gemini key causes quota coupling and cost volatility.

## Decision

Use a system-hosted multilingual embedding provider (BGE-M3 or equivalent) behind `EmbeddingProvider`. Gemini/OpenAI embeddings remain future adapters.

## Alternatives

- Embed with each user’s Gemini key — rejected for shared index ownership.
- Single global Gemini key in env for all RAG — rejected for user-cost model of generation; embeddings remain system-hosted.

## Consequences

Embedding service in Compose; dimension fixed per model version; reindex job required on model change.
