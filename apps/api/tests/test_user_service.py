from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.users.service import UserService


def _user(status: str) -> User:
    return User(
        id=uuid4(),
        google_sub=f"sub-{uuid4()}",
        email=f"{uuid4().hex[:8]}@example.com",
        email_verified=True,
        status=status,
    )


def test_assert_active_allows_active() -> None:
    UserService.assert_active(_user(UserStatus.ACTIVE))


def test_assert_active_blocks_suspended() -> None:
    with pytest.raises(HTTPException) as exc:
        UserService.assert_active(_user(UserStatus.SUSPENDED))
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "ACCOUNT_SUSPENDED"


def test_seed_super_admin_email_match(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "seed_super_admin_email", "admin@example.com")
    assert UserService._email_is_seed_super_admin("Admin@example.com")
    assert not UserService._email_is_seed_super_admin("other@example.com")


def test_seed_super_admin_blank_does_not_promote(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "seed_super_admin_email", "  ")
    assert not UserService._email_is_seed_super_admin("admin@example.com")
