from __future__ import annotations

from typing import Any

from app.models.audit import AuditAction
from app.models.source import SourceType

SECRET_META_KEYS = {
    "secret",
    "token",
    "password",
    "api_key",
    "apikey",
    "pat",
    "credential",
    "encrypted_api_key",
    "session",
    "cookie",
    "raw_content",
    "normalized_content",
    "content",
}

SOURCE_BUCKETS: list[tuple[str, str, frozenset[str]]] = [
    ("confluence", "Confluence", frozenset({SourceType.CONFLUENCE})),
    ("jira", "Jira", frozenset({SourceType.JIRA})),
    ("google_drive", "Google Drive", frozenset({"GOOGLE_DRIVE", "GDRIVE"})),
    (
        "upload",
        "Upload",
        frozenset(
            {
                SourceType.FILE_UPLOAD,
                SourceType.FILE_EXCEL,
                SourceType.FILE_CSV,
                SourceType.FILE_WORD,
                SourceType.FILE_POWERPOINT,
                SourceType.FILE_PDF,
                "UPLOAD",
            }
        ),
    ),
    ("web", "Web", frozenset({"WEB", "WEB_CLIP"})),
]

RECENT_ACTIVITY_ACTIONS = frozenset(
    {
        AuditAction.CREATE_WORKSPACE,
        AuditAction.UPDATE_WORKSPACE,
        AuditAction.CREATE_SPACE,
        AuditAction.UPDATE_SPACE,
        AuditAction.ARCHIVE_SPACE,
        AuditAction.RESTORE_SPACE,
        AuditAction.CREATE_CONFLUENCE_CONNECTION,
        AuditAction.UPDATE_CONFLUENCE_CONNECTION,
        AuditAction.ATTACH_SOURCE,
        AuditAction.DELETE_SOURCE,
        AuditAction.START_INGESTION,
        AuditAction.SHARE_WORKSPACE,
        AuditAction.SHARE_SPACE,
        AuditAction.REDEEM_SHARE_LINK,
        AuditAction.REVOKE_SHARE_LINK,
        AuditAction.SUSPEND_USER,
        AuditAction.UNSUSPEND_USER,
        AuditAction.CREATE_PAGE,
        "CREATE_USER",
        "ASK_AI",
    }
)

_ACTION_COPY: dict[str, str] = {
    AuditAction.CREATE_WORKSPACE: "New workspace{name} was created",
    AuditAction.UPDATE_WORKSPACE: "Workspace{name} was updated",
    AuditAction.CREATE_SPACE: "New space{name} was created",
    AuditAction.UPDATE_SPACE: "Space{name} was updated",
    AuditAction.ARCHIVE_SPACE: "Space{name} was archived",
    AuditAction.RESTORE_SPACE: "Space{name} was restored",
    AuditAction.CREATE_CONFLUENCE_CONNECTION: "Confluence connection{name} was added",
    AuditAction.UPDATE_CONFLUENCE_CONNECTION: "Confluence connection{name} was updated",
    AuditAction.ATTACH_SOURCE: "Source{name} was connected",
    AuditAction.DELETE_SOURCE: "Source{name} was removed",
    AuditAction.START_INGESTION: "Import{name} was started",
    AuditAction.SHARE_WORKSPACE: "A workspace share link was created",
    AuditAction.SHARE_SPACE: "A space share link was created",
    AuditAction.REDEEM_SHARE_LINK: "A share link was redeemed",
    AuditAction.REVOKE_SHARE_LINK: "A share link was revoked",
    AuditAction.SUSPEND_USER: "User{name} was suspended",
    AuditAction.UNSUSPEND_USER: "User{name} was reactivated",
    AuditAction.CREATE_PAGE: "Page{name} was created",
    "CREATE_USER": "New user{name} was created",
    "ASK_AI": "AI query was run",
}


def sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    if not metadata:
        return None
    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        lowered = key.lower()
        if lowered in SECRET_META_KEYS or any(part in lowered for part in SECRET_META_KEYS):
            continue
        if isinstance(value, str) and len(value) > 240:
            continue
        cleaned[key] = value
    return cleaned or None


def source_bucket(source_type: str | None) -> str:
    value = (source_type or "").upper()
    for key, _label, members in SOURCE_BUCKETS:
        if value in members:
            return key
    return "other"


def source_bucket_labels() -> list[tuple[str, str]]:
    return [(key, label) for key, label, _ in SOURCE_BUCKETS] + [("other", "Other")]


def format_activity_message(action: str, metadata: dict[str, Any] | None) -> str:
    meta = sanitize_metadata(metadata) or {}
    raw_name = (
        meta.get("name")
        or meta.get("title")
        or meta.get("space_name")
        or meta.get("email")
        or meta.get("source_name")
    )
    name = f" '{raw_name}'" if isinstance(raw_name, str) and raw_name.strip() else ""
    template = _ACTION_COPY.get(action)
    if template:
        return template.format(name=name)
    readable = action.replace("_", " ").lower()
    return f"{readable}{name}".strip()


def actor_display(display_name: str | None, email: str | None) -> str | None:
    if display_name and display_name.strip():
        return display_name.strip()
    if email:
        return email
    return None
