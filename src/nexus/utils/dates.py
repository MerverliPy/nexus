"""Natural language date parsing for smart scheduling."""

import calendar
from datetime import UTC, datetime, timedelta
from typing import Optional

import dateparser


def _preprocess(text: str, reference: datetime) -> str:
    """Preprocess common natural language patterns that dateparser struggles with."""
    lower = text.lower().strip()

    # "next {dayname}" — calculate the actual date
    day_names = {d.lower(): i for i, d in enumerate(calendar.day_name)}
    day_names_abbr = {d.lower(): i for i, d in enumerate(calendar.day_abbr)}

    for name, idx in {**day_names, **day_names_abbr}.items():
        patterns = [
            (f"next {name}", 7),
            (f"this {name}", 0),
            (f"next {name} ", 7),
            (f"this {name} ", 0),
        ]
        for pattern, offset_days in patterns:
            if lower.startswith(pattern):
                days_ahead = idx - reference.weekday()
                if days_ahead <= 0:
                    days_ahead += offset_days or 7
                future = reference + timedelta(days=days_ahead)
                # Preserve any trailing text (e.g. " 3pm")
                rest = text[len(pattern):]
                return future.strftime("%Y-%m-%d") + rest

    # "in X days/weeks"
    import re
    m = re.match(r'in\s+(\d+)\s+(day|days|week|weeks)', lower)
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        if unit in ("week", "weeks"):
            num *= 7
        future = reference + timedelta(days=num)
        return future.strftime("%Y-%m-%d")

    return text


def parse_natural_date(text: str, reference: Optional[datetime] = None) -> Optional[datetime]:
    """Parse a natural language date string into a datetime.

    Supports phrases like:
        "tomorrow", "tomorrow 3pm"
        "next week", "next monday"
        "in 3 days", "in 2 weeks"
        "friday at 5pm"
        "next month"
        "2026-07-15"
        "july 15"
    """
    if reference is None:
        reference = datetime.now(UTC)

    # Preprocess common patterns
    text = _preprocess(text, reference)

    settings = {
        "PREFER_DATES_FROM": "future",
        "RELATIVE_BASE": reference,
        "RETURN_AS_TIMEZONE_AWARE": False,
        "PREFER_DAY_OF_MONTH": "first",
        "PREFER_LOCALE_DATE_ORDER": False,
    }

    result = dateparser.parse(text, settings=settings)
    if result is None:
        return None

    # If no time was specified, default to end of day (for due dates)
    if result.time() == datetime.min.time():
        result = result.replace(hour=23, minute=59)

    return result


def parse_time_of_day(text: str) -> Optional[timedelta]:
    """Parse a time-of-day string into a timedelta offset."""
    time_map = {
        "morning": timedelta(hours=9),
        "afternoon": timedelta(hours=14),
        "evening": timedelta(hours=18),
        "night": timedelta(hours=21),
        "noon": timedelta(hours=12),
        "midnight": timedelta(hours=0),
    }

    if text.lower() in time_map:
        return time_map[text.lower()]

    return None
