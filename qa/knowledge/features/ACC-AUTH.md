---
id: ACC-AUTH
title: Google Auth & Session
status: active
source: README Phase 1, docs/security-checklist.md
updated: 2026-10-07
---

# ACC-AUTH — Google Auth & Session

## Vai trò

- End user: đăng nhập Google, duy trì session
- Hệ thống: từ chối anonymous và user SUSPENDED

## Business rules

- BR-ACC-AUTH-01: Chỉ Google OIDC; không password auth.
- BR-ACC-AUTH-02: Identity DB key là `google_sub`.
- BR-ACC-AUTH-03: Session HttpOnly + CSRF bắt buộc cho mutation (logout, upload, …).
- BR-ACC-AUTH-04: User SUSPENDED → 403 trên API có auth.
- BR-ACC-AUTH-05: Endpoint demo login không còn (`404`).
- BR-ACC-AUTH-06: Secret session/encryption ≥ 32 ký tự ở runtime (không test env).

## Luồng chính

1. Login redirect Google → callback → cookie session
2. GET `/api/v1/me` trả profile
3. Logout xóa session (cần CSRF)

## Open questions

- (none)

## Change log

| Date | Change |
|------|--------|
| 2026-10-07 | Khởi tạo kho QA từ implementation plan |
