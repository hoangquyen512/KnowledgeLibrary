from datetime import UTC, date, datetime

from app.admin.labels import (
    format_activity_message,
    sanitize_metadata,
    source_bucket,
)
from app.admin.period import change_percent, resolve_date_range, rollup_daily


def test_default_range_is_seven_inclusive_days_in_utc7() -> None:
    now = datetime(2026, 8, 27, 15, 0, tzinfo=UTC)  # 22:00 UTC+7
    rng = resolve_date_range(None, None, now=now)
    assert rng.start_date == date(2026, 8, 21)
    assert rng.end_date == date(2026, 8, 27)
    assert rng.previous_start_date == date(2026, 8, 14)
    assert rng.previous_end_date == date(2026, 8, 20)
    assert rng.timezone == "Asia/Ho_Chi_Minh"
    assert len(rng.dates()) == 7


def test_change_percent_requires_previous_data() -> None:
    assert change_percent(10, 0) == (None, False)
    assert change_percent(12, 8) == (50.0, True)
    assert change_percent(6, 8) == (-25.0, True)


def test_source_bucket_maps_known_types_and_unknown_to_other() -> None:
    assert source_bucket("CONFLUENCE") == "confluence"
    assert source_bucket("FILE_UPLOAD") == "upload"
    assert source_bucket("LOCAL") == "other"
    assert source_bucket("GOOGLE_DRIVE") == "google_drive"
    assert source_bucket("WEB") == "web"


def test_sanitize_metadata_strips_secrets_and_content() -> None:
    cleaned = sanitize_metadata(
        {
            "name": "Sales Playbook",
            "api_key": "secret-value",
            "raw_content": "<p>internal</p>",
            "token": "abc",
        }
    )
    assert cleaned == {"name": "Sales Playbook"}
    assert "secret-value" not in format_activity_message("CREATE_SPACE", {"api_key": "x"})


def test_activity_message_uses_name_without_content() -> None:
    msg = format_activity_message("CREATE_SPACE", {"name": "Sales Playbook", "content": "nope"})
    assert msg == "New space 'Sales Playbook' was created"
    assert "nope" not in msg


def test_weekly_rollup_keeps_real_totals() -> None:
    points = [
        {"date": "2026-08-24", "documents": 1, "ai_queries": 2, "users": 0},
        {"date": "2026-08-25", "documents": 3, "ai_queries": 1, "users": 1},
    ]
    weekly = rollup_daily(points, "weekly")
    assert len(weekly) == 1
    assert weekly[0]["documents"] == 4
    assert weekly[0]["ai_queries"] == 3
    assert weekly[0]["users"] == 1
