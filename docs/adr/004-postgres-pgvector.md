# ADR 004: PostgreSQL + pgvector

## Context

MVP needs relational data, FTS, and vectors without operating multiple data stores.

## Decision

Use PostgreSQL as system of record with `pgvector` for embeddings and `pg_trgm` + `simple` FTS for multilingual keyword search. Hybrid retrieval + RRF in application layer.

## Alternatives

- Pinecone/Qdrant early — extra ops cost before scale justifies it.
- Elasticsearch + Postgres — more moving parts for MVP.

## Consequences

Vector queries must include tenant/space filters. Scale path may later partition chunks or move vectors out.
