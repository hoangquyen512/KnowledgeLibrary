"""Confluence delta sync planning helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.models.source import SyncInterval


@dataclass
class SyncPlan:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)

    @property
    def to_fetch(self) -> list[str]:
        return [*self.added, *self.updated]

    def as_summary(self) -> dict[str, int]:
        return {
            "added": len(self.added),
            "updated": len(self.updated),
            "removed": len(self.removed),
            "unchanged": len(self.unchanged),
            "failed": 0,
        }


def compute_sync_plan(
    remote_pages: list[dict],
    local_by_external_id: dict[str, str | None],
) -> SyncPlan:
    """Compare remote page versions with stored ``external_version`` values."""
    plan = SyncPlan()
    remote_ids: set[str] = set()
    for page in remote_pages:
        ext_id = str(page.get("id") or "").strip()
        if not ext_id:
            continue
        remote_ids.add(ext_id)
        remote_version = _norm_version(page.get("version"))
        local_version = _norm_version(local_by_external_id.get(ext_id))
        if ext_id not in local_by_external_id:
            plan.added.append(ext_id)
        elif remote_version and local_version and remote_version == local_version:
            plan.unchanged.append(ext_id)
        elif remote_version and local_version and remote_version != local_version:
            plan.updated.append(ext_id)
        elif not remote_version and not local_version:
            plan.unchanged.append(ext_id)
        else:
            plan.updated.append(ext_id)

    for ext_id in local_by_external_id:
        if ext_id not in remote_ids:
            plan.removed.append(ext_id)
    return plan


def _norm_version(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def compute_next_sync_at(interval: str, *, from_time: datetime | None = None) -> datetime | None:
    base = from_time or datetime.now(UTC)
    if interval == SyncInterval.HOURLY:
        return base + timedelta(hours=1)
    if interval == SyncInterval.DAILY:
        return base + timedelta(days=1)
    return None
