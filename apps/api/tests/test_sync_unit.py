from datetime import UTC, datetime, timedelta

from app.ingestion.sync import SyncPlan, compute_next_sync_at, compute_sync_plan
from app.models.source import SyncInterval


def test_compute_sync_plan_added_updated_removed() -> None:
    remote = [
        {"id": "1", "version": "2"},
        {"id": "2", "version": "1"},
        {"id": "3", "version": "1"},
    ]
    local = {"1": "1", "2": "1", "4": "1"}
    plan = compute_sync_plan(remote, local)
    assert plan.added == ["3"]
    assert plan.updated == ["1"]
    assert plan.removed == ["4"]
    assert plan.unchanged == ["2"]
    assert set(plan.to_fetch) == {"1", "3"}


def test_compute_sync_plan_unchanged_when_versions_match() -> None:
    remote = [{"id": "10", "version": "5"}]
    local = {"10": "5"}
    plan = compute_sync_plan(remote, local)
    assert plan.unchanged == ["10"]
    assert plan.to_fetch == []


def test_sync_plan_summary() -> None:
    plan = SyncPlan(added=["a"], updated=["b"], removed=["c"], unchanged=["d"])
    assert plan.as_summary() == {
        "added": 1,
        "updated": 1,
        "removed": 1,
        "unchanged": 1,
        "failed": 0,
    }


def test_compute_next_sync_at_hourly() -> None:
    base = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    nxt = compute_next_sync_at(SyncInterval.HOURLY, from_time=base)
    assert nxt == base + timedelta(hours=1)


def test_compute_next_sync_at_off() -> None:
    assert compute_next_sync_at(SyncInterval.OFF) is None
