# ADR 008: RAG Citation Grounding

## Context

Answers must be grounded in selected Library sources with clickable citations.

## Decision

Hybrid retrieval → fusion → rerank → prompt with numbered sources → model citations validated against supplied chunk IDs before persist. No invented citations. Insufficient evidence → explicit “not found” response.

## Alternatives

- Trust model free-form URLs — hallucination risk.
- Footnotes without chunk mapping — weak deep-link UX.

## Consequences

Citation table + Document Viewer deep links; citation validator unit tests; prompt injection defenses treating doc content as untrusted data.
