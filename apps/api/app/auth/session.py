from __future__ import annotations

import secrets
from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import settings


@dataclass
class SessionPayload:
    user_id: str
    csrf_token: str


def _serializer() -> URLSafeTimedSerializer:
    if not settings.session_secret:
        raise RuntimeError("SESSION_SECRET is not configured")
    return URLSafeTimedSerializer(settings.session_secret, salt="kl-session-v1")


def create_session_token(user_id: UUID, csrf_token: str | None = None) -> tuple[str, str]:
    csrf = csrf_token or secrets.token_urlsafe(32)
    payload = SessionPayload(user_id=str(user_id), csrf_token=csrf)
    token = _serializer().dumps(asdict(payload))
    return token, csrf


def load_session_token(token: str) -> SessionPayload:
    data: dict[str, Any] = _serializer().loads(token, max_age=settings.session_ttl_seconds)
    return SessionPayload(user_id=str(data["user_id"]), csrf_token=str(data["csrf_token"]))


def safe_load_session_token(token: str) -> SessionPayload | None:
    try:
        return load_session_token(token)
    except (BadSignature, SignatureExpired, KeyError, TypeError, ValueError):
        return None


def new_oauth_state() -> str:
    return secrets.token_urlsafe(32)
