# ADR 007: Share Link Security

## Context

Workspace/Space sharing via multi-use links that require Google login.

## Decision

Cryptographically secure tokens (≥256 bits). Store only `token_hash`. Raw token shown once at create. Redeem after login grants membership with audit. Revoke immediate. OWNER role links require extra confirmation and Owner-only creation.

## Alternatives

- Email invites only — slower collaboration.
- Public anonymous links — violates auth rules.

## Consequences

Redeem/revoke APIs, redemptions table, rate limits on redeem, Isolated Space UX for Space-only grants.
