"""Tests for smart scheduling — NL date parsing, conflict detection, slot suggestions."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.models.task import Task
from nexus.models.user import User
from nexus.services.scheduling import detect_conflicts, parse_nl_date, suggest_free_slots


# ── NL date parsing ──────────────────────────────────────────────────────────


def test_parse_nl_date_tomorrow_3pm():
    result = parse_nl_date("tomorrow 3pm")
    assert result is not None
    assert result.hour == 15


def test_parse_nl_date_empty():
    assert parse_nl_date("") is None
    assert parse_nl_date("   ") is None


def test_parse_nl_date_explicit():
    result = parse_nl_date("2026-12-25 10:00")
    assert result is not None
    assert result.month == 12
    assert result.day == 25


def test_parse_nl_date_relative():
    result = parse_nl_date("in 2 hours")
    assert result is not None


# ── Conflict detection ──────────────────────────────────────────────────────


async def _seed_tasks(db_session: AsyncSession) -> tuple[User, int]:
    user = User(email="sched@example.com", password_hash="hash", is_active=True, mfa_enabled=False)
    db_session.add(user)
    await db_session.flush()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    base_task = Task(
        user_id=user.id,
        title="Main Task",
        due_date=now + timedelta(hours=2),
        status="pending",
    )
    db_session.add(base_task)
    await db_session.flush()

    return user, base_task.id


@pytest.mark.asyncio
async def test_detect_conflicts_within_window(db_session: AsyncSession):
    user, main_id = await _seed_tasks(db_session)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Create a conflicting task 30 min away
    conflict = Task(
        user_id=user.id,
        title="Conflict Task",
        due_date=now + timedelta(hours=2, minutes=30),
        status="pending",
    )
    db_session.add(conflict)
    await db_session.flush()

    conflicts = await detect_conflicts(
        main_id, now + timedelta(hours=2), user.id, db_session, window_minutes=60  # type: ignore[arg-type]
    )
    assert len(conflicts) == 1
    assert conflicts[0]["title"] == "Conflict Task"


@pytest.mark.asyncio
async def test_detect_conflicts_outside_window(db_session: AsyncSession):
    user, main_id = await _seed_tasks(db_session)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Task 3 hours away — should not conflict
    far_task = Task(
        user_id=user.id,
        title="Far Task",
        due_date=now + timedelta(hours=5),
        status="pending",
    )
    db_session.add(far_task)
    await db_session.flush()

    conflicts = await detect_conflicts(
        main_id, now + timedelta(hours=2), user.id, db_session, window_minutes=60  # type: ignore[arg-type]
    )
    assert len(conflicts) == 0


# ── Slot suggestions ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_suggest_free_slots_empty_day(db_session: AsyncSession):
    user, _ = await _seed_tasks(db_session)
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).replace(tzinfo=None)

    slots = await suggest_free_slots(user.id, db_session, date=tomorrow)  # type: ignore[arg-type]
    assert len(slots) > 0
    assert "start" in slots[0]
    assert "time" in slots[0]


@pytest.mark.asyncio
async def test_suggest_free_slots_with_busy_times(db_session: AsyncSession):
    user, _ = await _seed_tasks(db_session)
    tomorrow_8am = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
        hour=8, minute=0, second=0, microsecond=0, tzinfo=None
    )

    # Fill 8am-10am
    task1 = Task(
        user_id=user.id,
        title="Morning",
        due_date=tomorrow_8am + timedelta(hours=1),
        status="pending",
    )
    db_session.add(task1)
    await db_session.flush()

    slots = await suggest_free_slots(user.id, db_session, date=tomorrow_8am, count=2)  # type: ignore[arg-type]
    assert len(slots) >= 1
    # 8:00-9:00 is free (busy at 9:00), so first slot is at 8:00
    first_slot = datetime.fromisoformat(slots[0]["start"])


# ── API endpoint tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_suggest_time_endpoint(client):
    response = await client.get("/api/v1/tasks/suggest-time?text=tomorrow 3pm")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "datetime" in data


@pytest.mark.asyncio
async def test_suggest_time_bad_input(client):
    response = await client.get("/api/v1/tasks/suggest-time?text=xyzzy_not_a_date")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_suggest_slot_endpoint_requires_auth(client):
    response = await client.get("/api/v1/tasks/suggest-slot")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_conflicts_endpoint_requires_auth(client):
    response = await client.get("/api/v1/tasks/1/conflicts")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
