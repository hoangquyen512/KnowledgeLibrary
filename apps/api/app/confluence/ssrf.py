"""SSRF guards for Direct Confluence fetches."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse, urlunparse

from fastapi import HTTPException, status


class SsrfBlocked(Exception):
    def __init__(self, message: str = "URL is not allowed.") -> None:
        self.message = message
        super().__init__(message)


def normalize_base_url(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_URL", "message": "Base URL is required."},
        )
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    if parsed.scheme not in {"https", "http"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_URL", "message": "Only http(s) URLs are supported."},
        )
    if not parsed.hostname:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_URL", "message": "URL host is required."},
        )
    # Drop path/query/fragment — connection is host root
    cleaned = urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), "", "", "", ""))
    return cleaned.rstrip("/")


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def assert_public_url(
    url: str, *, allow_http: bool = False, allow_private: bool = False
) -> str:
    """Validate URL before outbound request. Returns the same URL if allowed."""
    parsed = urlparse(url)
    if parsed.scheme == "http" and not allow_http:
        raise SsrfBlocked("Only HTTPS is allowed in this environment.")
    if parsed.scheme not in {"https", "http"}:
        raise SsrfBlocked("Unsupported URL scheme.")
    host = parsed.hostname
    if not host:
        raise SsrfBlocked("Missing host.")
    if host.lower() in {"localhost", "metadata.google.internal"} and not allow_private:
        raise SsrfBlocked("Host is not allowed.")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise SsrfBlocked(f"Unable to resolve host: {host}") from exc
    if not allow_private:
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if _is_blocked_ip(ip):
                raise SsrfBlocked("Resolved address is not publicly routable.")
    return url


def ssrf_http_exception(exc: SsrfBlocked) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": "SSRF_BLOCKED", "message": exc.message},
    )
