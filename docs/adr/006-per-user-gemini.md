# ADR 006: Per-User Gemini Credentials

## Context

Google Login is identity only. LLM generation cost/quota should belong to each user.

## Decision

Each user connects their own Gemini API/Auth key (encrypted server-side). Ask AI requires valid user credential. Keys never returned after save; status + mask only.

## Alternatives

- Shared platform Gemini key billed centrally — different product model.
- Infer Gemini access from Google Login — not supported/reliable.

## Consequences

Onboarding UX when key missing; INVALID status on 401/403; `ai_usage` for observability.
