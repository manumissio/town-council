from __future__ import annotations

from datetime import date
import math
import re
import statistics


def month_start(value: date) -> date:
    return value.replace(day=1)


def shift_month(value: date, delta: int) -> date:
    year = value.year + ((value.month - 1 + delta) // 12)
    month = ((value.month - 1 + delta) % 12) + 1
    return date(year, month, 1)


def build_month_window(months: int, as_of: date | None = None) -> list[date]:
    if months <= 0:
        raise ValueError("months must be positive")
    anchor = month_start(as_of or date.today())
    start = shift_month(anchor, -(months - 1))
    return [shift_month(start, idx) for idx in range(months)]


def month_key(value: date) -> str:
    return value.strftime("%Y-%m")


def normalize_meeting_name(value: str | None) -> str:
    normalized = re.sub(r"\s+", " ", str(value or "").strip().lower())
    return normalized or "(missing)"


def compute_expected_monthly_event_baseline(event_counts: list[int]) -> tuple[float, int | None]:
    if not event_counts:
        return 0.0, None
    baseline = float(statistics.median(event_counts))
    if baseline < 2.0:
        return baseline, None
    # Conservative threshold highlights suspicious troughs without assuming each city's exact cadence.
    threshold = max(1, int(math.ceil(baseline * 0.5)))
    return baseline, threshold
