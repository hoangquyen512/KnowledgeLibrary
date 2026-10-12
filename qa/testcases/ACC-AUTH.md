---
feature: ACC-AUTH
updated: 2026-10-07
---

# Test cases — ACC-AUTH

| TC-ID | BR | Priority | Type | Automation | test_file |
|-------|-----|----------|------|------------|-----------|
| TC-ACC-AUTH-001 | BR-ACC-AUTH-03 | P0 | API | auto | tests/test_auth.py::test_me_requires_auth |
| TC-ACC-AUTH-002 | BR-ACC-AUTH-03 | P0 | API | auto | tests/test_auth.py::test_me_returns_user |
| TC-ACC-AUTH-003 | BR-ACC-AUTH-04 | P0 | API | auto | tests/test_auth.py::test_suspended_user_blocked |
| TC-ACC-AUTH-004 | BR-ACC-AUTH-03 | P0 | API | auto | tests/test_auth.py::test_logout_requires_csrf |
| TC-ACC-AUTH-005 | BR-ACC-AUTH-05 | P1 | API | auto | tests/test_demo.py::test_demo_login_removed |
| TC-ACC-AUTH-006 | BR-ACC-AUTH-03 | P0 | Unit | auto | tests/test_session.py |

## Scenario TC-ACC-AUTH-003

- **Given** user status SUSPENDED và session hợp lệ
- **When** GET `/api/v1/me`
- **Then** HTTP 403
