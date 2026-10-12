# ADR 001: Multi-tenant Workspace

## Context

Need clear tenant isolation for a SaaS knowledge library with sharing.

## Decision

Workspace is the primary tenant boundary. All AI queries and retrieval are scoped to a single Workspace. Users may own ≤10 Workspaces; shared memberships do not count toward quota.

## Alternatives

- Organization/Company entity above Workspace — deferred; Workspace ≈ company for MVP.
- Space as tenant — rejected; Spaces nest under Workspace and can be shared independently.

## Consequences

Every tenant table carries `workspace_id` (direct or via resolvable FK). Cross-workspace operations return 403/validation errors before retrieval.
