"""Local Connector Agent — Phase 6: heartbeat, NOOP, FETCH_CONFLUENCE + payload upload."""

from __future__ import annotations

import base64
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("connector-agent")

VERSION = "0.6.0"
STATE_FILE = Path(os.environ.get("AGENT_STATE_FILE", ".agent_state.json"))


def _api_base() -> str:
    return (
        os.environ.get("SaaS_API_URL")
        or os.environ.get("API_URL")
        or "http://localhost:8000"
    ).rstrip("/")


def _request(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    url = f"{_api_base()}/api/v1{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            **(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {path}: {detail}") from exc


def _load_state() -> dict[str, str] | None:
    if not STATE_FILE.exists():
        return None
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if data.get("agent_id") and data.get("agent_secret"):
            return data
    except (OSError, json.JSONDecodeError):
        return None
    return None


def _save_state(agent_id: str, agent_secret: str, workspace_id: str) -> None:
    STATE_FILE.write_text(
        json.dumps(
            {
                "agent_id": agent_id,
                "agent_secret": agent_secret,
                "workspace_id": workspace_id,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def register() -> dict[str, str]:
    token = (os.environ.get("REGISTRATION_TOKEN") or "").strip()
    if not token:
        logger.error("Set REGISTRATION_TOKEN (or reuse %s from a prior register).", STATE_FILE)
        sys.exit(1)
    name = os.environ.get("AGENT_NAME", "Connector Agent")
    out = _request(
        "POST",
        "/agent/register",
        body={"registration_token": token, "name": name, "version": VERSION},
    )
    state = {
        "agent_id": str(out["agent_id"]),
        "agent_secret": str(out["agent_secret"]),
        "workspace_id": str(out["workspace_id"]),
    }
    _save_state(state["agent_id"], state["agent_secret"], state["workspace_id"])
    logger.info("Registered agent_id=%s workspace=%s", state["agent_id"], state["workspace_id"])
    return state


def _auth_headers(state: dict[str, str]) -> dict[str, str]:
    return {
        "X-Agent-Id": state["agent_id"],
        "X-Agent-Secret": state["agent_secret"],
    }


def heartbeat(state: dict[str, str]) -> int:
    out = _request(
        "POST",
        "/agent/heartbeat",
        body={"version": VERSION},
        headers=_auth_headers(state),
    )
    return int(out.get("next_heartbeat_seconds") or 30)


def _confluence_get_json(
    base_url: str,
    path: str,
    *,
    auth_type: str,
    username: str,
    secret: str,
    params: dict[str, str] | None = None,
) -> Any:
    url = base_url.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Accept": "application/json", "User-Agent": f"KnowledgeLibrary-Agent/{VERSION}"}
    if auth_type == "SESSION_COOKIE":
        cookie = secret if "=" in secret else f"JSESSIONID={secret}"
        headers["Cookie"] = cookie
        auth_header = None
    else:
        token = base64.b64encode(f"{username}:{secret}".encode()).decode()
        auth_header = f"Basic {token}"
        headers["Authorization"] = auth_header
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _confluence_get_bytes(
    base_url: str,
    path: str,
    *,
    auth_type: str,
    username: str,
    secret: str,
) -> tuple[bytes, str]:
    if path.startswith("http"):
        url = path
    else:
        url = base_url.rstrip("/") + (path if path.startswith("/") else "/" + path)
    headers = {"User-Agent": f"KnowledgeLibrary-Agent/{VERSION}"}
    if auth_type == "SESSION_COOKIE":
        cookie = secret if "=" in secret else f"JSESSIONID={secret}"
        headers["Cookie"] = cookie
    else:
        token = base64.b64encode(f"{username}:{secret}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read(), resp.headers.get("content-type", "application/octet-stream")


def _resolve_credentials(payload: dict[str, Any]) -> tuple[str, str, str]:
    auth_type = payload.get("auth_type") or "PAT"
    loc = payload.get("credential_location") or "CLOUD"
    if loc == "LOCAL_AGENT" or not payload.get("secret"):
        username = os.environ.get("CONFLUENCE_USERNAME", "")
        secret = os.environ.get("CONFLUENCE_PAT") or os.environ.get("CONFLUENCE_SECRET", "")
        auth_type = os.environ.get("CONFLUENCE_AUTH_TYPE", auth_type)
        if not secret:
            raise RuntimeError(
                "LOCAL_AGENT credentials missing. Set CONFLUENCE_USERNAME + CONFLUENCE_PAT "
                "(or CONFLUENCE_SECRET for cookie)."
            )
        return auth_type, username, secret
    return auth_type, payload.get("username") or "", payload.get("secret") or ""


def fetch_confluence_pages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    base_url = payload["base_url"]
    auth_type, username, secret = _resolve_credentials(payload)
    page_ids: list[str] = list(payload.get("page_ids") or [])
    scan_only = bool(payload.get("scan_only"))
    if not page_ids:
        if payload.get("external_type") == "PAGE":
            page_ids = [str(payload.get("external_id"))]
        else:
            space_key = payload.get("external_key") or payload.get("external_id")
            start = 0
            while True:
                data = _confluence_get_json(
                    base_url,
                    "/rest/api/content",
                    auth_type=auth_type,
                    username=username,
                    secret=secret,
                    params={
                        "spaceKey": str(space_key),
                        "type": "page",
                        "start": str(start),
                        "limit": "50",
                        "expand": "version",
                    },
                )
                batch = data.get("results") or []
                if not batch:
                    break
                page_ids.extend(str(p["id"]) for p in batch)
                start += len(batch)
                if len(batch) < 50 or len(page_ids) >= 500:
                    break

    if scan_only:
        pages: list[dict[str, Any]] = []
        for pid in page_ids:
            page = _confluence_get_json(
                base_url,
                f"/rest/api/content/{pid}",
                auth_type=auth_type,
                username=username,
                secret=secret,
                params={"expand": "version"},
            )
            pages.append(
                {
                    "id": str(page.get("id")),
                    "title": page.get("title") or "Untitled",
                    "version": str((page.get("version") or {}).get("number") or ""),
                }
            )
        return pages

    pages: list[dict[str, Any]] = []
    for pid in page_ids:
        page = _confluence_get_json(
            base_url,
            f"/rest/api/content/{pid}",
            auth_type=auth_type,
            username=username,
            secret=secret,
            params={"expand": "body.storage,version,space"},
        )
        body = ((page.get("body") or {}).get("storage") or {}).get("value") or ""
        atts_data = _confluence_get_json(
            base_url,
            f"/rest/api/content/{pid}/child/attachment",
            auth_type=auth_type,
            username=username,
            secret=secret,
            params={"limit": "200", "expand": "version,metadata.mediaType"},
        )
        attachments: list[dict[str, Any]] = []
        for row in atts_data.get("results") or []:
            download = (row.get("_links") or {}).get("download") or ""
            try:
                raw, ctype = _confluence_get_bytes(
                    base_url,
                    download,
                    auth_type=auth_type,
                    username=username,
                    secret=secret,
                )
                meta = row.get("metadata") or {}
                extensions = row.get("extensions") or {}
                media = meta.get("mediaType") or extensions.get("mediaType") or ctype
                attachments.append(
                    {
                        "id": str(row.get("id")),
                        "filename": row.get("title") or "attachment",
                        "media_type": media,
                        "data_b64": base64.b64encode(raw).decode("ascii"),
                        "size_bytes": len(raw),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Attachment download failed %s: %s", row.get("id"), exc)
        pages.append(
            {
                "id": str(page.get("id")),
                "title": page.get("title") or "Untitled",
                "body_storage": body,
                "version": str((page.get("version") or {}).get("number") or ""),
                "url": (page.get("_links") or {}).get("webui"),
                "attachments": attachments,
            }
        )
    return pages


def handle_fetch_job(state: dict[str, str], job: dict[str, Any]) -> None:
    job_id = job["id"]
    payload = job.get("payload_json") or {}
    pages = fetch_confluence_pages(payload)
    scan_only = bool(payload.get("scan_only"))
    _request(
        "POST",
        "/agent/ingestion-payloads",
        body={
            "ingestion_job_id": payload["ingestion_job_id"],
            "pages": pages,
            "scan": scan_only,
        },
        headers=_auth_headers(state),
    )
    _request(
        "POST",
        f"/agent/jobs/{job_id}/complete",
        body={
            "status": "SUCCEEDED",
            "result": {"pages": len(pages), "ingestion_job_id": payload.get("ingestion_job_id")},
        },
        headers=_auth_headers(state),
    )
    logger.info("FETCH_CONFLUENCE completed job=%s pages=%s", job_id, len(pages))


def poll_and_complete(state: dict[str, str]) -> None:
    job = _request("GET", "/agent/jobs/next", headers=_auth_headers(state))
    if not job:
        return
    job_id = job["id"]
    job_type = job.get("job_type", "NOOP")
    logger.info("Leased job %s type=%s", job_id, job_type)
    try:
        if job_type == "FETCH_CONFLUENCE":
            handle_fetch_job(state, job)
            return
        result = {"ack": True, "job_type": job_type, "agent_version": VERSION}
        _request(
            "POST",
            f"/agent/jobs/{job_id}/complete",
            body={"status": "SUCCEEDED", "result": result},
            headers=_auth_headers(state),
        )
        logger.info("Completed job %s", job_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Job %s failed", job_id)
        try:
            _request(
                "POST",
                f"/agent/jobs/{job_id}/complete",
                body={"status": "FAILED", "error_message": str(exc)[:500]},
                headers=_auth_headers(state),
            )
        except Exception:  # noqa: BLE001
            logger.exception("Could not report job failure")


def main() -> None:
    logger.info("Connector agent %s → %s", VERSION, _api_base())
    state = _load_state()
    if state is None:
        state = register()
    else:
        logger.info("Loaded credentials from %s (agent_id=%s)", STATE_FILE, state["agent_id"])

    while True:
        try:
            interval = heartbeat(state)
            poll_and_complete(state)
        except Exception as exc:  # noqa: BLE001
            logger.error("Loop error: %s", exc)
            interval = 30
        time.sleep(max(5, interval))


if __name__ == "__main__":
    main()
