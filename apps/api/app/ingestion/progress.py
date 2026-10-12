from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from app.models.source import SourceType

STAGE_DEFS: list[dict[str, str]] = [
    {"key": "CONNECTING", "label": "Connecting to Confluence"},
    {"key": "SCANNING", "label": "Reading page tree"},
    {"key": "IMPORTING_PAGES", "label": "Importing pages"},
    {"key": "IMPORTING_ATTACHMENTS", "label": "Importing attachments"},
    {"key": "INDEXING", "label": "Generating previews / indexing"},
    {"key": "FINALIZING", "label": "Finalizing"},
]

JIRA_STAGE_DEFS: list[dict[str, str]] = [
    {"key": "CONNECTING", "label": "Connecting to Jira"},
    {"key": "FETCHING", "label": "Fetching issues"},
    {"key": "PARSING", "label": "Parsing issues"},
    {"key": "INDEXING", "label": "Indexing"},
    {"key": "FINALIZING", "label": "Finalizing"},
]

FILE_STAGE_DEFS: dict[str, list[dict[str, str]]] = {
    SourceType.FILE_EXCEL: [
        {"key": "UPLOADING", "label": "Uploading"},
        {"key": "READING", "label": "Reading sheets"},
        {"key": "PARSING", "label": "Parsing rows"},
        {"key": "INDEXING", "label": "Indexing"},
        {"key": "FINALIZING", "label": "Finalizing"},
    ],
    SourceType.FILE_CSV: [
        {"key": "UPLOADING", "label": "Uploading"},
        {"key": "READING", "label": "Reading CSV"},
        {"key": "PARSING", "label": "Parsing rows"},
        {"key": "INDEXING", "label": "Indexing"},
        {"key": "FINALIZING", "label": "Finalizing"},
    ],
    SourceType.FILE_WORD: [
        {"key": "UPLOADING", "label": "Uploading"},
        {"key": "READING", "label": "Reading document"},
        {"key": "PARSING", "label": "Extracting sections"},
        {"key": "INDEXING", "label": "Indexing"},
        {"key": "FINALIZING", "label": "Finalizing"},
    ],
    SourceType.FILE_POWERPOINT: [
        {"key": "UPLOADING", "label": "Uploading"},
        {"key": "READING", "label": "Reading slides"},
        {"key": "PARSING", "label": "Extracting text"},
        {"key": "INDEXING", "label": "Indexing"},
        {"key": "FINALIZING", "label": "Finalizing"},
    ],
    SourceType.FILE_PDF: [
        {"key": "UPLOADING", "label": "Uploading"},
        {"key": "READING", "label": "Reading pages"},
        {"key": "PARSING", "label": "Extracting text"},
        {"key": "INDEXING", "label": "Indexing"},
        {"key": "FINALIZING", "label": "Finalizing"},
    ],
}


def stage_defs_for(source_type: str | None) -> list[dict[str, str]]:
    st = (source_type or SourceType.CONFLUENCE).upper()
    if st == SourceType.JIRA:
        return JIRA_STAGE_DEFS
    if st in FILE_STAGE_DEFS:
        return FILE_STAGE_DEFS[st]
    if st == SourceType.FILE_UPLOAD:
        return FILE_STAGE_DEFS[SourceType.FILE_PDF]
    return STAGE_DEFS


def ensure_utc(dt: datetime | None) -> datetime | None:
    """SQLite may return naive datetimes even for tz-aware columns."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def empty_progress(source_type: str | None = None) -> dict[str, Any]:
    defs = stage_defs_for(source_type)
    return {
        "cancel_requested": False,
        "eta_seconds": None,
        "stats": {
            "total_pages": 0,
            "processed_pages": 0,
            "total_attachments": 0,
            "processed_attachments": 0,
            "total_diagrams": 0,
            "processed_diagrams": 0,
            "failed_items": 0,
        },
        "stages": [{"key": s["key"], "label": s["label"], "status": "pending"} for s in defs],
        "current_items": [],
        "started_by_name": None,
        "import_mode": None,
        "destination_name": None,
        "source_type": source_type or SourceType.CONFLUENCE,
        "source_name": None,
    }


def progress_for_source(source_type: str | None) -> dict[str, Any]:
    return empty_progress(source_type=source_type)


def mark_stage(progress: dict[str, Any], active_key: str) -> None:
    """Mark stages before active as completed, active in_progress, rest pending."""
    reached = False
    for stage in progress.get("stages") or []:
        if stage.get("status") in {"failed", "skipped"}:
            if stage["key"] == active_key:
                reached = True
            continue
        if stage["key"] == active_key:
            stage["status"] = "in_progress"
            reached = True
        elif not reached:
            stage["status"] = "completed"
        else:
            stage["status"] = "pending"


def set_stage_status(progress: dict[str, Any], key: str, status: str) -> None:
    for stage in progress.get("stages") or []:
        if stage["key"] == key:
            stage["status"] = status
            return


def complete_all_stages(progress: dict[str, Any]) -> None:
    for stage in progress.get("stages") or []:
        if stage["status"] not in {"failed", "skipped"}:
            stage["status"] = "completed"


def push_current_item(
    progress: dict[str, Any],
    *,
    name: str,
    item_status: str,
    item_type: str = "PAGE",
    limit: int = 8,
) -> None:
    items: list[dict[str, Any]] = list(progress.get("current_items") or [])
    if item_status == "importing":
        for row in items:
            if row.get("status") == "importing":
                row["status"] = "imported"
    items.insert(
        0,
        {
            "name": name[:200],
            "status": item_status,
            "type": item_type,
            "at": datetime.now(UTC).isoformat(),
        },
    )
    progress["current_items"] = items[:limit]


def estimate_eta_seconds(
    *,
    processed: int,
    total: int,
    started_at: datetime | None,
) -> int | None:
    if not started_at or processed <= 0 or total <= processed:
        return None
    started = ensure_utc(started_at)
    if started is None:
        return None
    elapsed = (datetime.now(UTC) - started).total_seconds()
    if elapsed < 1:
        return None
    rate = processed / elapsed
    if rate <= 0:
        return None
    remaining = total - processed
    return max(1, int(remaining / rate))


def merge_progress(base: dict[str, Any] | None, **updates: Any) -> dict[str, Any]:
    data = deepcopy(base) if base else empty_progress()
    for key, value in updates.items():
        if key == "stats" and isinstance(value, dict):
            data.setdefault("stats", {}).update(value)
        else:
            data[key] = value
    return data
