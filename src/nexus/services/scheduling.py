"""Smart scheduling — NL date parsing, conflict detection, slot suggestions."""

from datetime import datetime, timedelta, timezone

import dateparser
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.models.task import Task


def parse_nl_date(text: str) -> datetime | None:
    """Parse natural language date string into a datetime.

    Examples:
        "tomorrow 3pm" → tomorrow at 15:00
        "next monday" → next Monday
        "in 2 hours" → 2 hours from now
        "jul 15 5pm" → July 15 at 17:00

    Returns None if parsing fails.
    """
    if not text or not text.strip():
        return None

    result = dateparser.parse(
        text,
        settings={
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": datetime.now(timezone.utc).replace(tzinfo=None),
        },
    )
    return result


async def detect_conflicts(
    task_id: int,
    due_date: datetime,
    user_id: int,
    db: AsyncSession,
    *,
    window_minutes: int = 60,
) -> list[dict]:
    """Detect tasks that conflict with a given due date/time.

    Two tasks conflict if their due dates are within `window_minutes` of each other.
    Returns list of conflicting tasks (excluding the task itself).
    """
    lower = due_date - timedelta(minutes=window_minutes)
    upper = due_date + timedelta(minutes=window_minutes)

    query = (
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.status == "pending",
            Task.id != task_id,
            Task.due_date.isnot(None),
            Task.due_date >= lower,
            Task.due_date <= upper,
        )
        .order_by(Task.due_date)
    )
    result = await db.execute(query)
    tasks = result.scalars().all()

    return [
        {
            "id": t.id,
            "title": t.title,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "priority": t.priority,
        }
        for t in tasks
    ]


async def suggest_free_slots(
    user_id: int,
    db: AsyncSession,
    *,
    date: datetime | None = None,
    count: int = 3,
) -> list[dict]:
    """Suggest free time slots on a given date for scheduling a new task.

    Returns up to `count` suggested slots as ISO datetime strings.
    If no date provided, uses tomorrow.
    """
    ref_date = date or (datetime.now(timezone.utc) + timedelta(days=1))
    day_start = ref_date.replace(hour=8, minute=0, second=0, microsecond=0)
    day_end = ref_date.replace(hour=20, minute=0, second=0, microsecond=0)

    # Get existing tasks on that day
    result = await db.execute(
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.status == "pending",
            Task.due_date.isnot(None),
            Task.due_date >= day_start,
            Task.due_date <= day_end,
        )
        .order_by(Task.due_date)
    )
    existing = result.scalars().all()

    # Collect existing times
    busy_times = sorted(
        t.due_date.replace(tzinfo=None) if t.due_date else day_start
        for t in existing
    )

    # Find gaps between busy times
    suggested: list[dict] = []
    cursor = day_start.replace(tzinfo=None)
    slot_duration = timedelta(hours=1)

    for busy in busy_times:
        busy_dt = busy if not hasattr(busy, "replace") else busy
        if cursor + slot_duration <= busy_dt:
            suggested.append({
                "start": cursor.isoformat(),
                "end": (cursor + slot_duration).isoformat(),
                "date": cursor.strftime("%A %B %d"),
                "time": cursor.strftime("%I:%M %p").lstrip("0"),
            })
            if len(suggested) >= count:
                return suggested
        cursor = max(cursor, busy_dt + slot_duration)

    # Add remaining slots after last busy time
    while cursor + slot_duration <= day_end.replace(tzinfo=None) and len(suggested) < count:
        suggested.append({
            "start": cursor.isoformat(),
            "end": (cursor + slot_duration).isoformat(),
            "date": cursor.strftime("%A %B %d"),
            "time": cursor.strftime("%I:%M %p").lstrip("0"),
        })
        cursor += slot_duration

    return suggested
