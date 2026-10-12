"""Jira Data Center REST client (PAT / Bearer)."""

from __future__ import annotations

from typing import Any

import httpx


class JiraClientError(Exception):
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


class JiraClient:
    def __init__(
        self,
        *,
        base_url: str,
        auth_type: str,
        username: str | None,
        secret: str,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_type = auth_type
        self.username = username or ""
        self.secret = secret
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.auth_type in {"PAT", "BEARER"}:
            # Jira DC PAT is typically sent as Bearer
            headers["Authorization"] = f"Bearer {self.secret}"
        else:
            headers["Authorization"] = f"Bearer {self.secret}"
        return headers

    def _auth(self) -> httpx.Auth | None:
        # Optional basic for older setups when username provided with PAT as password
        if self.auth_type == "BASIC" and self.username:
            return httpx.BasicAuth(self.username, self.secret)
        return None

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            resp = await client.request(
                method, url, headers=self._headers(), auth=self._auth(), **kwargs
            )
        if resp.status_code in {401, 403}:
            raise JiraClientError(
                "Jira authentication failed.",
                status_code=resp.status_code,
                code="JIRA_AUTH_FAILED",
            )
        if resp.status_code == 404:
            raise JiraClientError(
                "Jira resource not found.",
                status_code=404,
                code="JIRA_PROJECT_NOT_FOUND",
            )
        if resp.status_code >= 400:
            raise JiraClientError(
                f"Jira API error HTTP {resp.status_code}",
                status_code=resp.status_code,
                code="JIRA_ACCESS_DENIED" if resp.status_code == 403 else "JIRA_API_ERROR",
            )
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    async def test_connection(self) -> dict[str, Any]:
        # serverInfo is available on DC
        data = await self._request("GET", "/rest/api/2/serverInfo")
        return {
            "version": str((data or {}).get("version") or (data or {}).get("serverTitle") or "ok"),
            "raw": data,
        }

    async def list_projects(self, *, query: str | None = None) -> list[dict[str, Any]]:
        data = await self._request("GET", "/rest/api/2/project")
        items = data if isinstance(data, list) else (data or {}).get("values") or []
        out: list[dict[str, Any]] = []
        q = (query or "").strip().lower()
        for p in items:
            if not isinstance(p, dict):
                continue
            key = str(p.get("key") or "")
            name = str(p.get("name") or "")
            if q and q not in key.lower() and q not in name.lower():
                continue
            out.append(
                {
                    "id": str(p.get("id") or key),
                    "key": key,
                    "name": name,
                    "url": f"{self.base_url}/browse/{key}" if key else None,
                }
            )
        return out

    async def search_issues(
        self,
        *,
        jql: str,
        fields: list[str] | None = None,
        expand: list[str] | None = None,
        start_at: int = 0,
        max_results: int = 50,
    ) -> dict[str, Any]:
        payload = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results,
            "fields": fields
            or [
                "summary",
                "description",
                "status",
                "priority",
                "assignee",
                "reporter",
                "issuetype",
                "labels",
                "components",
                "created",
                "updated",
                "parent",
                "attachment",
                "comment",
            ],
        }
        if expand:
            payload["expand"] = expand
        return await self._request("POST", "/rest/api/2/search", json=payload)

    async def iter_project_issues(
        self,
        *,
        project_key: str,
        updated_after: str | None = None,
        include_changelog: bool = False,
        page_size: int = 50,
    ):
        jql = f'project = "{project_key}"'
        if updated_after:
            jql += f' AND updated >= "{updated_after}"'
        jql += " ORDER BY updated ASC"
        expand = ["changelog"] if include_changelog else None
        start = 0
        while True:
            page = await self.search_issues(
                jql=jql, start_at=start, max_results=page_size, expand=expand
            )
            issues = page.get("issues") or []
            for issue in issues:
                yield issue
            total = int(page.get("total") or 0)
            start += len(issues)
            if start >= total or not issues:
                break
