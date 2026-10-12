from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.models.confluence import ConnectionAuthType


class ConfluenceClientError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


_COOKIE_ATTRS = {
    "path",
    "domain",
    "expires",
    "max-age",
    "secure",
    "httponly",
    "samesite",
    "priority",
    "partitioned",
    "size",
}

_PREFERRED_COOKIES = (
    "jsessionid",
    "seraph.rememberme",
    "crowd.token_key",
    "studio.crowd.tokenkey",
)


def normalize_ancestors(raw: Any) -> list[dict[str, str]]:
    """Normalize Confluence ancestor payloads (list or ``{results: [...]}``)."""
    if not raw:
        return []
    rows = raw
    if isinstance(raw, dict):
        rows = raw.get("results") or raw.get("items") or []
    if not isinstance(rows, list):
        return []
    out: list[dict[str, str]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        aid = item.get("id")
        if aid is None or str(aid).strip() == "":
            continue
        atype = str(item.get("type") or "page").lower()
        if atype in {"space", "attachment", "comment"}:
            continue
        out.append({"id": str(aid), "title": str(item.get("title") or "")})
    return out


def cookie_names(header: str) -> list[str]:
    names: list[str] = []
    for part in (header or "").split(";"):
        if "=" not in part:
            continue
        name = part.split("=", 1)[0].strip()
        if name:
            names.append(name)
    return names


def _looks_like_json_cookies(raw: str) -> bool:
    text = raw.strip()
    return text.startswith("[") or text.startswith("{")


def _pairs_from_json(raw: str) -> list[tuple[str, str]]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    rows: list[dict[str, Any]]
    if isinstance(data, list):
        rows = [row for row in data if isinstance(row, dict)]
    elif isinstance(data, dict) and isinstance(data.get("cookies"), list):
        rows = [row for row in data["cookies"] if isinstance(row, dict)]
    else:
        return []
    pairs: list[tuple[str, str]] = []
    for row in rows:
        name = str(row.get("name") or "").strip()
        value = str(row.get("value") or "")
        if name and name.lower() not in _COOKIE_ATTRS:
            pairs.append((name, value))
    return pairs


def _pairs_from_table(raw: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for line in raw.replace("\r\n", "\n").split("\n"):
        if "\t" not in line or "=" in line.split("\t", 1)[0]:
            continue
        cols = [c.strip() for c in line.split("\t")]
        if len(cols) < 2:
            continue
        name, value = cols[0], cols[1]
        if not name or name.lower() in {"name", "cookie"}:
            continue
        if name.lower() in _COOKIE_ATTRS:
            continue
        pairs.append((name, value))
    return pairs


def _pairs_from_text(raw: str) -> list[tuple[str, str]]:
    table = _pairs_from_table(raw)
    if table:
        return table
    text = raw.replace("\r\n", "\n").strip()
    if text.lower().startswith("cookie:"):
        text = text.split(":", 1)[1].strip()
    curl = re.search(
        r"""(?:-H|--header|--cookie|-b)\s+['"]?(?:Cookie:\s*)?([^'"\n]+)""",
        text,
        flags=re.IGNORECASE,
    )
    if curl and "=" in curl.group(1):
        text = curl.group(1).strip()
    text = text.replace("\n", ";").replace("\t", ";")
    pairs: list[tuple[str, str]] = []
    for part in text.split(";"):
        item = part.strip()
        if not item or "=" not in item:
            continue
        name, value = item.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if not name or name.lower() in _COOKIE_ATTRS:
            continue
        pairs.append((name, value))
    return pairs


def normalize_cookie_header(raw: str) -> str:
    """Accept Cookie header, multiline DevTools paste, JSON export, or bare session id."""
    value = (raw or "").strip()
    if not value:
        return value
    pairs = _pairs_from_json(value) if _looks_like_json_cookies(value) else []
    if not pairs:
        pairs = _pairs_from_text(value)
    if not pairs:
        return f"JSESSIONID={value.splitlines()[0].strip()}"

    preferred = [p for p in pairs if p[0].lower() in _PREFERRED_COOKIES]
    chosen = preferred or pairs
    # Keep first occurrence of each name.
    seen: set[str] = set()
    ordered: list[tuple[str, str]] = []
    for name, val in chosen:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append((name, val))
    return "; ".join(f"{name}={val}" for name, val in ordered)


class ConfluenceClient:
    def __init__(
        self,
        *,
        base_url: str,
        auth_type: str,
        username: str | None,
        secret: str,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_type = auth_type
        self.username = username
        self.secret = (
            normalize_cookie_header(secret)
            if auth_type == ConnectionAuthType.SESSION_COOKIE
            else secret
        )
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._download_client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> ConfluenceClient:
        limits = httpx.Limits(max_connections=12, max_keepalive_connections=8)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout, connect=15.0),
            follow_redirects=False,
            headers=self._headers(),
            auth=self._auth(),
            limits=limits,
        )
        self._download_client = httpx.AsyncClient(
            timeout=httpx.Timeout(max(self.timeout, 90.0), connect=15.0),
            follow_redirects=True,
            headers=self._headers(),
            auth=self._auth(),
            limits=limits,
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        if self._download_client is not None:
            await self._download_client.aclose()
            self._download_client = None

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "KnowledgeLibrary/0.1 (ConfluenceConnector)",
        }
        if self.auth_type == ConnectionAuthType.SESSION_COOKIE:
            headers["Cookie"] = self.secret
        return headers

    def _auth(self) -> httpx.Auth | None:
        if self.auth_type == ConnectionAuthType.PAT:
            return httpx.BasicAuth(self.username or "pat", self.secret)
        return None

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        try:
            if self._client is not None:
                resp = await self._client.get(url, params=params)
            else:
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    follow_redirects=False,
                    headers=self._headers(),
                    auth=self._auth(),
                ) as client:
                    resp = await client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise ConfluenceClientError(f"Confluence unreachable: {exc}") from exc

        # Login redirect / session expired often returns 302 to login
        if resp.status_code in {301, 302, 303, 307, 308}:
            raise ConfluenceClientError(
                "Confluence redirected (session invalid or not authenticated).",
                status_code=resp.status_code,
                code="CONFLUENCE_SESSION_EXPIRED",
            )
        if resp.status_code in {401, 403}:
            raise ConfluenceClientError(
                "Confluence authentication failed. Check PAT/username or session cookie.",
                status_code=resp.status_code,
                code="CONFLUENCE_AUTH_FAILED",
            )
        if resp.status_code >= 400:
            code = "SOURCE_NOT_FOUND" if resp.status_code == 404 else None
            raise ConfluenceClientError(
                f"Confluence returned HTTP {resp.status_code}",
                status_code=resp.status_code,
                code=code,
            )
        if not resp.content:
            return {}
        return resp.json()

    @staticmethod
    def _is_anonymous_user(data: dict[str, Any]) -> bool:
        user_type = str(data.get("type") or "").lower()
        username = str(data.get("username") or data.get("userKey") or "").lower()
        display = str(data.get("displayName") or "").lower()
        if user_type == "anonymous":
            return True
        if username in {"anonymous", "anonymoususer"}:
            return True
        if display == "anonymous":
            return True
        return False

    async def test(self) -> dict[str, Any]:
        """Require a real authenticated user — never treat anonymous as success."""
        data = await self._get("/rest/api/user/current")
        if not isinstance(data, dict) or self._is_anonymous_user(data):
            names = cookie_names(self.secret) if self.auth_type == ConnectionAuthType.SESSION_COOKIE else []
            missing = []
            lower = {n.lower() for n in names}
            if self.auth_type == ConnectionAuthType.SESSION_COOKIE:
                if "jsessionid" not in lower:
                    missing.append("JSESSIONID")
                if "seraph.rememberme" not in lower:
                    missing.append("seraph.rememberme")
            sent = ", ".join(names) if names else "none"
            hint = (
                f" Cookies sent: {sent}."
                + (f" Missing {', '.join(missing)}." if missing else "")
                + " Paste the full Cookie header (JSESSIONID + seraph.rememberme) from a logged-in browser tab."
            )
            raise ConfluenceClientError(
                "Authenticated as anonymous. Only public spaces would be visible." + hint,
                status_code=401,
                code="CONFLUENCE_SESSION_EXPIRED",
            )
        return {
            "ok": True,
            "display_name": data.get("displayName") or data.get("username"),
            "detected": str(data.get("type") or "user"),
            "username": data.get("username"),
        }

    def _map_space(self, s: dict[str, Any]) -> dict[str, Any]:
        return {
            "key": s.get("key"),
            "name": s.get("name"),
            "type": s.get("type"),
            "id": str(s.get("id")) if s.get("id") is not None else s.get("key"),
            "url": (s.get("_links") or {}).get("webui"),
        }

    async def list_spaces(
        self, *, query: str | None = None, start: int = 0, limit: int = 50
    ) -> dict[str, Any]:
        """
        List spaces visible to the authenticated user.

        Paginates Confluence `/rest/api/space` so we do not stop at the first
        page (which often looks like “only public” when many spaces exist).
        Optional `query` filters by name/key substring after fetching pages.
        """
        page_size = min(max(limit, 1), 100)
        # If caller asks for a slice, honour start/limit as one page.
        # UI browse uses start=0 and wants a searchable full-ish list — fetch pages.
        if start > 0:
            data = await self._get(
                "/rest/api/space",
                params={"start": start, "limit": page_size},
            )
            results = list(data.get("results") or [])
            if query:
                q = query.lower().strip()
                results = [
                    s
                    for s in results
                    if q in (s.get("name") or "").lower() or q in (s.get("key") or "").lower()
                ]
            return {
                "items": [self._map_space(s) for s in results],
                "start": start,
                "limit": page_size,
                "size": len(results),
                "total": data.get("size"),
            }

        # Substring filter on the full paginated list (CQL title~/key often misses
        # partial matches like "edu" → "EDU School" / "EDUS" on Confluence DC).
        results: list[dict[str, Any]] = []
        cursor = 0
        max_pages = 40  # safety: up to ~4000 spaces
        for _ in range(max_pages):
            data = await self._get(
                "/rest/api/space",
                params={"start": cursor, "limit": page_size},
            )
            batch = list(data.get("results") or [])
            if not batch:
                break
            results.extend(batch)
            cursor += len(batch)
            if len(batch) < page_size:
                break

        if query and query.strip():
            q = query.lower().strip()
            results = [
                s
                for s in results
                if q in (s.get("name") or "").lower() or q in (s.get("key") or "").lower()
            ]

        return {
            "items": [self._map_space(s) for s in results],
            "start": 0,
            "limit": page_size,
            "size": len(results),
            "total": len(results),
        }

    async def _search_spaces_cql(self, query: str, *, limit: int) -> dict[str, Any]:
        # Escape quotes in CQL
        safe = query.replace("\\", "\\\\").replace('"', '\\"')
        cql = f'type=space AND (title~"{safe}" OR space.key="{safe}")'
        data = await self._get(
            "/rest/api/search",
            params={"cql": cql, "limit": min(limit, 50)},
        )
        items: list[dict[str, Any]] = []
        for row in data.get("results") or []:
            space = row.get("space") or {}
            if not space.get("key"):
                # Some payloads nest under content
                content = row.get("content") or {}
                space = {
                    "key": content.get("space", {}).get("key") if isinstance(content.get("space"), dict) else None,
                    "name": content.get("title") or row.get("title"),
                    "id": content.get("id"),
                    "_links": content.get("_links") or row.get("_links") or {},
                }
            if space.get("key"):
                items.append(self._map_space(space))
        # Deduplicate by key
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for item in items:
            key = str(item.get("key") or "")
            if key and key not in seen:
                seen.add(key)
                unique.append(item)
        return {
            "items": unique,
            "start": 0,
            "limit": limit,
            "size": len(unique),
            "total": data.get("totalSize", len(unique)),
        }

    async def _get_bytes(self, path: str, params: dict[str, Any] | None = None) -> tuple[bytes, str]:
        url = f"{self.base_url}{path}"
        try:
            if self._download_client is not None:
                resp = await self._download_client.get(url, params=params)
            else:
                async with httpx.AsyncClient(
                    timeout=max(self.timeout, 90.0),
                    follow_redirects=True,
                    headers=self._headers(),
                    auth=self._auth(),
                ) as client:
                    resp = await client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise ConfluenceClientError(f"Confluence unreachable: {exc}") from exc
        if resp.status_code in {401, 403}:
            raise ConfluenceClientError(
                "Confluence authentication failed while downloading attachment.",
                status_code=resp.status_code,
            )
        if resp.status_code >= 400:
            raise ConfluenceClientError(
                f"Confluence download HTTP {resp.status_code}",
                status_code=resp.status_code,
            )
        content_type = resp.headers.get("content-type", "application/octet-stream")
        return resp.content, content_type

    async def get_page(self, page_id: str) -> dict[str, Any]:
        data = await self._get(
            f"/rest/api/content/{page_id}",
            params={"expand": "body.storage,version,space,ancestors,metadata.labels"},
        )
        body = ((data.get("body") or {}).get("storage") or {}).get("value") or ""
        version = (data.get("version") or {}).get("number")
        space = data.get("space") or {}
        return {
            "id": str(data.get("id")),
            "title": data.get("title") or "Untitled",
            "type": data.get("type"),
            "body_storage": body,
            "version": str(version) if version is not None else None,
            "space_key": space.get("key"),
            "url": (data.get("_links") or {}).get("webui"),
            "ancestors": normalize_ancestors(data.get("ancestors")),
        }

    async def get_space(self, space_key: str) -> dict[str, Any]:
        """Fetch a space by key; map 404 to SOURCE_NOT_FOUND."""
        key = (space_key or "").strip()
        if not key:
            raise ConfluenceClientError(
                "Confluence space key is missing.",
                status_code=404,
                code="SOURCE_NOT_FOUND",
            )
        try:
            data = await self._get(f"/rest/api/space/{key}")
        except ConfluenceClientError as exc:
            if exc.status_code == 404:
                raise ConfluenceClientError(
                    f"Confluence space '{key}' was not found or is not accessible.",
                    status_code=404,
                    code="SOURCE_NOT_FOUND",
                ) from exc
            raise
        return self._map_space(data if isinstance(data, dict) else {})

    def _normalize_page_results(
        self, data: dict[str, Any], *, start: int, limit: int
    ) -> dict[str, Any]:
        if isinstance(data.get("page"), dict):
            data = data["page"]
        results = data.get("results") or data.get("items") or []
        items: list[dict[str, Any]] = []
        for p in results:
            row: dict[str, Any] = {
                "id": str(p.get("id")),
                "title": p.get("title"),
                "type": p.get("type"),
                "url": (p.get("_links") or {}).get("webui"),
                "version": str((p.get("version") or {}).get("number") or "")
                if isinstance(p.get("version"), dict)
                else str(p.get("version") or ""),
            }
            if "ancestors" in p:
                row["ancestors"] = normalize_ancestors(p.get("ancestors"))
            items.append(row)
        return {
            "items": items,
            "start": data.get("start", start),
            "limit": data.get("limit", limit),
            "size": data.get("size", len(results)),
        }

    async def list_all_pages_in_space(
        self,
        space_key: str,
        *,
        space_id: str | None = None,
        max_pages: int = 10_000,
    ) -> list[dict[str, Any]]:
        """List pages for a space.

        Prefer space key, then fall back to numeric space id. Do not fail solely
        because ``GET /space/{key}`` 404s — some Server/DC setups still allow
        content listing, and expired sessions often look like space-not-found.
        """
        key = (space_key or "").strip()
        sid = (space_id or "").strip()
        keys_to_try: list[str] = []
        if key:
            keys_to_try.append(key)
        if sid and sid not in keys_to_try:
            keys_to_try.append(sid)
        if not keys_to_try:
            raise ConfluenceClientError(
                "Confluence space key is missing.",
                status_code=404,
                code="SOURCE_NOT_FOUND",
            )

        last_error: ConfluenceClientError | None = None
        for candidate in keys_to_try:
            try:
                items: list[dict[str, Any]] = []
                start = 0
                limit = 50
                while len(items) < max_pages:
                    batch = await self.list_pages(space_key=candidate, start=start, limit=limit)
                    rows = batch.get("items") or []
                    if not rows:
                        break
                    items.extend(rows)
                    start += len(rows)
                    if len(rows) < limit:
                        break
                if items:
                    return items[:max_pages]
                # Empty space is valid once listing succeeds.
                return []
            except ConfluenceClientError as exc:
                last_error = exc
                if exc.status_code not in {400, 404}:
                    raise

        label = key or sid
        if last_error and last_error.code == "CONFLUENCE_SESSION_EXPIRED":
            raise last_error
        raise ConfluenceClientError(
            f"Confluence space '{label}' was not found or is not accessible.",
            status_code=(last_error.status_code if last_error else 404),
            code="SOURCE_NOT_FOUND",
        )


    async def list_attachments(self, page_id: str) -> list[dict[str, Any]]:
        """List all attachments for a page (paginated; Confluence default caps per call)."""
        out: list[dict[str, Any]] = []
        start = 0
        page_size = 50
        while True:
            data = await self._get(
                f"/rest/api/content/{page_id}/child/attachment",
                params={
                    "limit": page_size,
                    "start": start,
                    "expand": "version,metadata.mediaType",
                },
            )
            rows = data.get("results") or []
            for row in rows:
                extensions = row.get("extensions") or {}
                meta = row.get("metadata") or {}
                media = (
                    meta.get("mediaType")
                    or extensions.get("mediaType")
                    or "application/octet-stream"
                )
                download = (row.get("_links") or {}).get("download") or ""
                out.append(
                    {
                        "id": str(row.get("id")),
                        "title": row.get("title") or "attachment",
                        "media_type": media,
                        "file_size": int(extensions.get("fileSize") or 0),
                        "download_path": download,
                    }
                )
            size = int(data.get("size") or len(rows))
            if size < page_size or not rows:
                break
            start += size
            # Safety cap — pathological pages
            if start >= 5000:
                break
        return out

    async def download_attachment(self, download_path: str) -> tuple[bytes, str]:
        path = download_path
        if path.startswith("http"):
            # Absolute URL — strip base if same host, else use path only via client
            if path.startswith(self.base_url):
                path = path[len(self.base_url) :]
            else:
                # Fall back to absolute GET
                try:
                    async with httpx.AsyncClient(
                        timeout=max(self.timeout, 120.0),
                        follow_redirects=True,
                        headers=self._headers(),
                        auth=self._auth(),
                    ) as client:
                        resp = await client.get(path)
                    if resp.status_code >= 400:
                        raise ConfluenceClientError(
                            f"Attachment download HTTP {resp.status_code}",
                            status_code=resp.status_code,
                        )
                    return resp.content, resp.headers.get(
                        "content-type", "application/octet-stream"
                    )
                except httpx.HTTPError as exc:
                    raise ConfluenceClientError(f"Attachment download failed: {exc}") from exc
        if not path.startswith("/"):
            path = "/" + path
        return await self._get_bytes(path)

    async def list_pages(
        self, *, space_key: str, start: int = 0, limit: int = 25
    ) -> dict[str, Any]:
        """List pages in a space with Server/DC-friendly fallbacks."""
        key = (space_key or "").strip()
        start_i = max(start, 0)
        limit_i = min(max(limit, 1), 50)
        params_common = {"start": start_i, "limit": limit_i, "expand": "version,ancestors"}
        errors: list[ConfluenceClientError] = []

        try:
            data = await self._get(
                f"/rest/api/space/{key}/content/page",
                params=params_common,
            )
            return self._normalize_page_results(data, start=start_i, limit=limit_i)
        except ConfluenceClientError as exc:
            errors.append(exc)
            if exc.status_code not in {404, 400}:
                raise

        try:
            data = await self._get(
                "/rest/api/content",
                params={
                    "spaceKey": key,
                    "type": "page",
                    **params_common,
                },
            )
            return self._normalize_page_results(data, start=start_i, limit=limit_i)
        except ConfluenceClientError as exc:
            errors.append(exc)
            if exc.status_code not in {404, 400}:
                raise

        try:
            safe = key.replace('\\', '\\\\').replace('"', '\\"')
            data = await self._get(
                "/rest/api/content/search",
                params={
                    "cql": f'space="{safe}" AND type=page',
                    **params_common,
                },
            )
            return self._normalize_page_results(data, start=start_i, limit=limit_i)
        except ConfluenceClientError as exc:
            errors.append(exc)

        last = errors[-1] if errors else None
        raise ConfluenceClientError(
            f"Confluence space '{key}' was not found or is not accessible.",
            status_code=(last.status_code if last else 404),
            code="SOURCE_NOT_FOUND",
        )

