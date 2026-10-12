from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

GEMINI_API_BASES: tuple[str, ...] = (
    "https://generativelanguage.googleapis.com/v1beta",
    "https://generativelanguage.googleapis.com/v1",
)

DEFAULT_GEMINI_MODEL = "gemini-flash-latest"
GEMINI_MODEL_FALLBACKS: tuple[str, ...] = (
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-pro-latest",
    "gemini-2.5-pro",
    "gemini-3-flash-preview",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
)

_SKIP_MODEL_MARKERS = ("image", "tts", "live", "embedding", "aqa", "vision", "audio", "native-audio")

_VERIFIED_MODEL_CACHE: dict[str, str] = {}


def normalize_gemini_model_id(name: str) -> str:
    return (name or "").removeprefix("models/").strip()


def _cache_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:20]


def remember_verified_model(api_key: str, model: str) -> None:
    model_id = normalize_gemini_model_id(model)
    if model_id:
        _VERIFIED_MODEL_CACHE[_cache_key(api_key)] = model_id


def get_verified_model(api_key: str) -> str | None:
    return _VERIFIED_MODEL_CACHE.get(_cache_key(api_key))


def _is_text_generation_model(model_id: str) -> bool:
    lowered = model_id.lower()
    if not lowered.startswith("gemini-"):
        return False
    return not any(marker in lowered for marker in _SKIP_MODEL_MARKERS)


def _model_rank(model_id: str) -> tuple[int, str]:
    lowered = model_id.lower()
    tier = 10
    if lowered.endswith("flash-latest") or lowered == "gemini-flash-latest":
        tier = 0
    elif "2.5-flash" in lowered and "lite" not in lowered:
        tier = 1
    elif "flash-lite" in lowered or lowered.endswith("flash-lite-latest"):
        tier = 2
    elif "2.5-pro" in lowered or lowered.endswith("pro-latest"):
        tier = 3
    elif "flash" in lowered:
        tier = 4
    elif "pro" in lowered:
        tier = 5
    elif "preview" in lowered:
        tier = 6
    return tier, lowered


def _candidate_models(preferred: str | None = None) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw in (preferred, settings.gemini_model, *GEMINI_MODEL_FALLBACKS):
        mid = normalize_gemini_model_id(str(raw or ""))
        if not mid or mid in seen:
            continue
        seen.add(mid)
        ordered.append(mid)
    return ordered


async def _gemini_http(
    api_key: str,
    *,
    method: str,
    path: str,
    json_body: dict[str, Any] | None = None,
) -> httpx.Response:
    last_resp: httpx.Response | None = None
    async with httpx.AsyncClient(timeout=60.0) as client:
        for base in GEMINI_API_BASES:
            url = f"{base.rstrip('/')}/{path.lstrip('/')}"
            header_resp = await client.request(
                method,
                url,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=json_body,
            )
            last_resp = header_resp
            if header_resp.status_code != 404:
                return header_resp
            query_resp = await client.request(
                method,
                url,
                params={"key": api_key},
                headers={"Content-Type": "application/json"},
                json=json_body,
            )
            last_resp = query_resp
            if query_resp.status_code != 404:
                return query_resp
    assert last_resp is not None
    return last_resp


async def list_gemini_models(api_key: str) -> list[str]:
    resp = await _gemini_http(api_key, method="GET", path="models")
    if resp.status_code >= 400:
        resp.raise_for_status()
    data = resp.json()
    models: list[str] = []
    for item in data.get("models") or []:
        methods = item.get("supportedGenerationMethods") or []
        if "generateContent" not in methods:
            continue
        mid = normalize_gemini_model_id(str(item.get("name") or ""))
        if mid and _is_text_generation_model(mid):
            models.append(mid)
    return models


def pick_gemini_model(available: list[str], preferred: str | None = None) -> str | None:
    if not available:
        return None
    available_set = set(available)
    for candidate in _candidate_models(preferred):
        if candidate in available_set:
            return candidate
    for candidate in _candidate_models(preferred):
        for name in available:
            if name == candidate or name.endswith(f"/{candidate}"):
                return normalize_gemini_model_id(name)
    return normalize_gemini_model_id(available[0])


async def resolve_gemini_models(api_key: str, preferred: str | None = None) -> list[str]:
    verified = get_verified_model(api_key)
    try:
        available = await list_gemini_models(api_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not list Gemini models: %s", exc)
        available = []

    ordered: list[str] = []
    seen: set[str] = set()

    def add(model: str) -> None:
        mid = normalize_gemini_model_id(model)
        if mid and mid not in seen:
            seen.add(mid)
            ordered.append(mid)

    if verified:
        add(verified)

    if available:
        available_set = set(available)
        for candidate in _candidate_models(preferred):
            if candidate in available_set:
                add(candidate)
        for name in sorted(available, key=_model_rank):
            add(name)
        return ordered

    for candidate in _candidate_models(preferred):
        add(candidate)
    return ordered or [DEFAULT_GEMINI_MODEL]


def parse_suggested_model_from_error(detail: str) -> str | None:
    if not detail:
        return None
    lowered = detail.lower()
    for marker in ("use ", "try ", "switch to "):
        idx = lowered.rfind(marker)
        if idx >= 0:
            tail = detail[idx + len(marker) :]
            match = re.search(r"\b(gemini-[a-z0-9][a-z0-9.\-]*)\b", tail, flags=re.IGNORECASE)
            if match:
                return normalize_gemini_model_id(match.group(1))
    matches = re.findall(r"\b(gemini-[a-z0-9][a-z0-9.\-]*)\b", detail, flags=re.IGNORECASE)
    if not matches:
        return None
    return normalize_gemini_model_id(matches[-1])


def gemini_generate_url(model: str, *, api_base: str = GEMINI_API_BASES[0]) -> str:
    return f"{api_base.rstrip('/')}/models/{normalize_gemini_model_id(model)}:generateContent"


def _generation_payload(prompt: str, *, json_mode: bool) -> dict[str, Any]:
    generation_config: dict[str, Any] = {"temperature": 0.2}
    if json_mode:
        generation_config["responseMimeType"] = "application/json"
    return {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": generation_config,
    }


async def gemini_generate_content(
    api_key: str,
    model: str,
    prompt: str,
    *,
    json_mode: bool = True,
) -> tuple[dict[str, Any], str]:
    model_id = normalize_gemini_model_id(model)
    payloads = [_generation_payload(prompt, json_mode=json_mode)]
    if json_mode:
        payloads.append(_generation_payload(prompt, json_mode=False))

    last_detail = ""
    last_status = 404
    for body in payloads:
        resp = await _gemini_http(
            api_key,
            method="POST",
            path=f"models/{model_id}:generateContent",
            json_body=body,
        )
        if resp.status_code < 400:
            remember_verified_model(api_key, model_id)
            return resp.json(), model_id
        last_status = resp.status_code
        try:
            last_detail = resp.json().get("error", {}).get("message", "") or resp.text[:300]
        except Exception:  # noqa: BLE001
            last_detail = resp.text[:300]
        if resp.status_code not in {400, 404}:
            raise RuntimeError(
                f"Gemini HTTP {resp.status_code}" + (f": {last_detail}" if last_detail else "")
            )
    raise RuntimeError(
        f"Gemini HTTP {last_status}" + (f": {last_detail}" if last_detail else "")
    )


async def gemini_generate_best(
    api_key: str,
    prompt: str,
    *,
    preferred_model: str | None = None,
    json_mode: bool = True,
) -> tuple[dict[str, Any], str]:
    models = await resolve_gemini_models(api_key, preferred_model)
    tried: set[str] = set()
    last_error: Exception | None = None

    for round_idx in range(2):
        progressed = False
        for model in list(models):
            if model in tried:
                continue
            tried.add(model)
            progressed = True
            try:
                return await gemini_generate_content(
                    api_key, model, prompt, json_mode=json_mode
                )
            except RuntimeError as exc:
                last_error = exc
                msg = str(exc).lower()
                if "quota" in msg or "429" in msg:
                    raise
                suggested = parse_suggested_model_from_error(str(exc))
                if suggested and suggested not in tried:
                    models.insert(0, suggested)
                logger.warning("Gemini model %s unavailable: %s", model, exc)
        if not progressed:
            break
        if round_idx == 0:
            models = await resolve_gemini_models(api_key, preferred_model=None)

    if last_error:
        raise last_error
    raise RuntimeError("No Gemini model available for this API key")


async def ping_gemini_api(api_key: str, *, preferred_model: str | None = None) -> tuple[bool, str | None]:
    """Validate API key with the same generate path used by Ask AI."""
    try:
        _, model = await gemini_generate_best(
            api_key,
            "ping",
            preferred_model=preferred_model,
            json_mode=False,
        )
        return True, model
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini ping failed: %s", exc)
        return False, None


async def diagnose_gemini_api(api_key: str) -> dict[str, Any]:
    listed: list[str] = []
    list_error: str | None = None
    try:
        listed = sorted(await list_gemini_models(api_key), key=_model_rank)
    except Exception as exc:  # noqa: BLE001
        list_error = f"{type(exc).__name__}: {exc}"[:200]

    ok, verified = await ping_gemini_api(api_key, preferred_model=None)
    test_error: str | None = None
    if not ok:
        test_error = "No working Gemini model found after trying fallbacks."

    return {
        "ok": ok,
        "models_listed": len(listed),
        "sample_models": listed[:8],
        "available_models": listed,
        "verified_model": verified,
        "preferred_model": normalize_gemini_model_id(settings.gemini_model or ""),
        "list_error": list_error,
        "test_error": test_error,
    }
