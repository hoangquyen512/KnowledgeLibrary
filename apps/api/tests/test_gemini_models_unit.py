from unittest.mock import AsyncMock, patch

import pytest

from app.rag.gemini_models import (
    parse_suggested_model_from_error,
    pick_gemini_model,
    resolve_gemini_models,
)


def test_pick_gemini_model_prefers_configured_when_available() -> None:
    available = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
    assert pick_gemini_model(available, "gemini-2.5-flash") == "gemini-2.5-flash"


def test_pick_gemini_model_skips_deprecated_when_unavailable() -> None:
    available = ["gemini-2.5-flash-lite", "gemini-flash-latest"]
    assert pick_gemini_model(available, "gemini-3.7-flash") == "gemini-flash-latest"


def test_pick_gemini_model_normalizes_models_prefix() -> None:
    available = ["models/gemini-2.5-flash"]
    assert pick_gemini_model(available, "gemini-2.5-flash") == "gemini-2.5-flash"


@pytest.mark.asyncio
async def test_resolve_gemini_models_prefers_available_ranked() -> None:
    available = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-flash-latest"]
    with patch(
        "app.rag.gemini_models.list_gemini_models",
        new=AsyncMock(return_value=available),
    ):
        models = await resolve_gemini_models("fake-key", "gemini-3.7-flash")
    assert models[0] == "gemini-flash-latest"
    assert models[1] == "gemini-2.5-flash"


def test_parse_suggested_model_from_error() -> None:
    detail = "Model gemini-2.5-flash is no longer available. Use gemini-flash-latest instead."
    assert parse_suggested_model_from_error(detail) == "gemini-flash-latest"
