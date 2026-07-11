"""Recurrence engine — RRULE parsing and next-occurrence generation."""

import re
from datetime import UTC, datetime

from dateutil.rrule import rrulestr


def next_occurrence(rrule_str: str, after: datetime | None = None) -> datetime | None:
    """Get the next occurrence of a recurring task after a given datetime."""
    if after is None:
        after = datetime.now(UTC)
    try:
        rule = rrulestr(rrule_str, dtstart=after)
        return rule.after(after, inc=False)
    except Exception:
        return None


def generate_due_dates(rrule_str: str, from_date: datetime, count: int = 5) -> list[datetime]:
    """Generate the next N due dates from a recurrence rule."""
    try:
        rule = rrulestr(rrule_str, dtstart=from_date)
        return list(rule[:count])
    except Exception:
        return [from_date]


def rrule_description(rrule_str: str) -> str:
    """Return a human-readable description of an RRULE string."""
    day_map = {
        "MO": "Mon",
        "TU": "Tue",
        "WE": "Wed",
        "TH": "Thu",
        "FR": "Fri",
        "SA": "Sat",
        "SU": "Sun",
    }
    freq_upper = rrule_str.upper()

    try:
        rrulestr(rrule_str)  # validate it's parseable
    except Exception:
        return f"Repeats ({rrule_str})"

    parts = ["Repeats"]

    if "FREQ=DAILY" in freq_upper:
        m = re.search(r"INTERVAL=(\d+)", freq_upper)
        interval = f" every {m.group(1)} days" if (m and int(m.group(1)) > 1) else " daily"
        parts.append(interval)
    elif "FREQ=WEEKLY" in freq_upper:
        m = re.search(r"INTERVAL=(\d+)", freq_upper)
        interval = f" every {m.group(1)} weeks" if (m and int(m.group(1)) > 1) else " weekly"
        parts.append(interval)

        byday_match = re.search(r"BYDAY=([A-Z,]+)", freq_upper)
        if byday_match:
            days = [day_map.get(d, d) for d in byday_match.group(1).split(",")]
            parts.append(f"on {', '.join(days)}")
    elif "FREQ=MONTHLY" in freq_upper:
        parts.append(" monthly")
    elif "FREQ=YEARLY" in freq_upper:
        parts.append(" yearly")

    return " ".join(p.strip() for p in parts).strip().capitalize()
