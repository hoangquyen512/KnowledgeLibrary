# ADR 003: Confluence Local Connector Agent

## Context

Many Confluence Data Center instances are VPN/intranet-only; public SaaS cannot reach them.

## Decision

Support Direct connector when reachable, and Local Connector Agent (outbound TLS only) for private networks. Agent registers with one-time token, heartbeats, pulls jobs, fetches Confluence, uploads payloads. Credentials may stay local.

## Alternatives

- Require inbound VPN/peering — operationally heavy for customers.
- Browser-only scrape — insecure, fragile, violates product rules.

## Consequences

Extra agent package/Docker image and connector gateway APIs. Direct mode must still enforce SSRF protections.
