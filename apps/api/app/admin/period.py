from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

ADMIN_TZ_NAME = "Asia/Ho_Chi_Minh"
ADMIN_TZ = ZoneInfo(ADMIN_TZ_NAME)
MAX_RANGE_DAYS = 366


@dataclass(frozen=True)
class DateRange:
    start: datetime
    end: datetime
    start_date: date
    end_date: date
    previous_start: datetime
    previous_end: datetime
    previous_start_date: date
    previous_end_date: date
    timezone: str = ADMIN_TZ_NAME

    def dates(self) -> list[date]:
        days: list[date] = []
        cur = self.start_date
        while cur <= self.end_date:
            days.append(cur)
            cur += timedelta(days=1)
        return days


def resolve_date_range(
    from_date: date | None,
    to_date: date | None,
    *,
    now: datetime | None = None,
) -> DateRange:
    now_local = (now or datetime.now(UTC)).astimezone(ADMIN_TZ)
    end_d = to_date or now_local.date()
    start_d = from_date or (end_d - timedelta(days=6))
    if start_d > end_d:
        start_d = end_d
    if (end_d - start_d).days > MAX_RANGE_DAYS - 1:
        start_d = end_d - timedelta(days=MAX_RANGE_DAYS - 1)

    start = datetime.combine(start_d, time.min, tzinfo=ADMIN_TZ).astimezone(UTC)
    end = datetime.combine(end_d, time.max, tzinfo=ADMIN_TZ).astimezone(UTC)

    span = (end_d - start_d).days + 1
    prev_end_d = start_d - timedelta(days=1)
    prev_start_d = prev_end_d - timedelta(days=span - 1)
    prev_start = datetime.combine(prev_start_d, time.min, tzinfo=ADMIN_TZ).astimezone(UTC)
    prev_end = datetime.combine(prev_end_d, time.max, tzinfo=ADMIN_TZ).astimezone(UTC)

    return DateRange(
        start=start,
        end=end,
        start_date=start_d,
        end_date=end_d,
        previous_start=prev_start,
        previous_end=prev_end,
        previous_start_date=prev_start_d,
        previous_end_date=prev_end_d,
    )


def change_percent(current: int, previous: int) -> tuple[float | None, bool]:
    if previous <= 0:
        return None, False
    return round((current - previous) / previous * 100.0, 1), True


def fill_daily_series(days: list[date], counts: dict[date, int]) -> list[dict[str, object]]:
    return [{"date": d.isoformat(), "value": int(counts.get(d, 0))} for d in days]


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def rollup_daily(
    points: list[dict[str, object]],
    granularity: str,
) -> list[dict[str, object]]:
    if granularity == "daily":
        return points
    buckets: dict[str, dict[str, int]] = {}
    order: list[str] = []
    for point in points:
        day = date.fromisoformat(str(point["date"]))
        if granularity == "weekly":
            iso = day.isocalendar()
            key = f"{iso.year}-W{iso.week:02d}"
        else:
            key = f"{day.year:04d}-{day.month:02d}"
        if key not in buckets:
            buckets[key] = {"documents": 0, "ai_queries": 0, "users": 0}
            order.append(key)
        buckets[key]["documents"] += int(point.get("documents") or 0)
        buckets[key]["ai_queries"] += int(point.get("ai_queries") or 0)
        buckets[key]["users"] += int(point.get("users") or 0)
    return [{"date": key, **buckets[key]} for key in order]
