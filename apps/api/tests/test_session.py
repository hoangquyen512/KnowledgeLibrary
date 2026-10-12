from uuid import uuid4

from app.auth.session import create_session_token, safe_load_session_token


def test_session_roundtrip() -> None:
    user_id = uuid4()
    token, csrf = create_session_token(user_id)
    payload = safe_load_session_token(token)
    assert payload is not None
    assert payload.user_id == str(user_id)
    assert payload.csrf_token == csrf


def test_session_rejects_tamper() -> None:
    user_id = uuid4()
    token, _ = create_session_token(user_id)
    assert safe_load_session_token(token + "x") is None
