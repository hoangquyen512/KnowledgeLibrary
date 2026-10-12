"""Runtime environment helpers (avoid relying solely on Settings snapshot)."""

from __future__ import annotations

import os

from app.core.config import settings


def is_test_runtime() -> bool:
    """True under pytest or when APP_ENV=test (env wins over Settings defaults)."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    if os.environ.get("APP_ENV", "").strip().lower() == "test":
        return True
    return settings.app_env.strip().lower() == "test"
