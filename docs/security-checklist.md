# Security Checklist

## AuthN / AuthZ

- [x] Google OIDC only; no password/anonymous content
- [x] Session: HttpOnly, Secure, SameSite; CSRF on mutations
- [x] Suspended users blocked
- [ ] PermissionService used by all resource APIs
- [ ] Cross-workspace search/chat rejected
- [ ] Isolated Space members cannot enumerate Workspace
- [ ] Conversation access owner-only
- [x] Super Admin cannot browse documents by default

## Secrets

- [x] Gemini / PAT / SA / session credentials encrypted at rest *(encryption helper ready; credential tables Phase 4/8)*
- [x] Never returned in API responses *(Phase 1 `/me` verified)*
- [x] Never logged
- [ ] Share raw token stored as hash only
- [x] `.env` secrets not committed; `.env.example` has empty placeholders

## Network / Content

- [ ] SSRF protections for Direct Confluence fetches
- [ ] Prefer Local Agent for private Confluence
- [ ] Confluence HTML sanitized (no script/handlers/javascript:)
- [ ] Rate limits: login, redeem, analyze, chat, search, admin *(basic in-memory middleware for auth/share/admin/chat)*
- [ ] Object keys generated; no user filename as path
- [ ] Signed download URLs for attachments

## Audit / Tests

- [x] Audit events for share, connection, admin suspend, Gemini connect
- [ ] Critical IDOR tests green (see master prompt §85)
- [ ] Prompt injection defense in system prompt
