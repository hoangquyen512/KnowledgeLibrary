from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

# path prefix -> (max requests, window seconds)
_RATE_RULES: list[tuple[str, int, int]] = [
    ("/api/v1/auth/google/login", 20, 60),
    ("/api/v1/share/", 30, 60),
    ("/api/v1/conversations/", 40, 60),
    ("/api/v1/admin/", 60, 60),
]

_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _rule_for(path: str) -> tuple[int, int] | None:
    for prefix, limit, window in _RATE_RULES:
        if path.startswith(prefix):
            return limit, window
    if path.endswith("/search") or "/messages" in path:
        return 40, 60
    return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        rule = _rule_for(request.url.path)
        if rule is None:
            return await call_next(request)
        limit, window = rule
        now = time.monotonic()
        key = f"{_client_key(request)}:{request.url.path}"
        bucket = _BUCKETS[key]
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= limit:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests. Please try again shortly.",
                    }
                },
            )
        bucket.append(now)
        return await call_next(request)
