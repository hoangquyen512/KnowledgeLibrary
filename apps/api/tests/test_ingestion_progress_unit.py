from datetime import UTC, datetime, timedelta

from app.ingestion.progress import empty_progress, estimate_eta_seconds, mark_stage


def test_empty_progress_has_stages() -> None:
    p = empty_progress()
    assert len(p["stages"]) >= 5
    assert p["stats"]["total_pages"] == 0


def test_mark_stage_advances() -> None:
    p = empty_progress()
    mark_stage(p, "SCANNING")
    assert p["stages"][0]["status"] == "completed"
    assert p["stages"][1]["key"] == "SCANNING"
    assert p["stages"][1]["status"] == "in_progress"
    assert p["stages"][2]["status"] == "pending"


def test_estimate_eta_none_without_progress() -> None:
    assert estimate_eta_seconds(processed=0, total=10, started_at=None) is None


def test_estimate_eta_with_rate() -> None:
    started = datetime.now(UTC) - timedelta(seconds=100)
    eta = estimate_eta_seconds(processed=50, total=100, started_at=started)
    assert eta is not None
    assert eta > 0


def test_estimate_eta_accepts_naive_started_at() -> None:
    started = datetime.utcnow() - timedelta(seconds=100)
    eta = estimate_eta_seconds(processed=50, total=100, started_at=started)
    assert eta is not None
    assert eta > 0
