"""Tests for Celery worker configuration and task logic."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from nexus.models.task import Task
from nexus.models.user import User
from nexus.workers import app as celery_app
from nexus.workers.tasks import _generate_recurring_tasks_core

# ── Celery app configuration ─────────────────────────────────────────────


def test_celery_app_configured():
    assert celery_app.main == "nexus"
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.timezone == "UTC"


def test_beat_schedule_registered():
    schedule = celery_app.conf.beat_schedule
    assert "generate-recurring-tasks" in schedule
    assert "retrain-categorizer" in schedule
    assert "daily-backup" in schedule


def test_tasks_registered():
    registered = celery_app.tasks
    assert "nexus.workers.tasks.generate_recurring_tasks" in registered
    assert "nexus.workers.tasks.retrain_categorizer" in registered
    assert "nexus.workers.tasks.run_backup" in registered
    assert "nexus.workers.tasks.cleanup_expired_sessions" in registered


# ── Recurring task generation logic ──────────────────────────────────────


async def _make_user(db_session, email: str) -> User:
    user = User(email=email, password_hash="x", is_active=True)
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_generate_recurring_tasks_creates_next_instance(db_session):
    user = await _make_user(db_session, "recur-worker@example.com")

    # A recurring task whose due date has passed
    past = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    task = Task(
        user_id=user.id,
        title="Weekly review",
        status="pending",
        priority=1,
        due_date=past,
        recurrence_rule="FREQ=WEEKLY;BYDAY=MO",
    )
    db_session.add(task)
    await db_session.flush()

    result = await _generate_recurring_tasks_core(db_session)
    assert result["created"] == 1

    # A new pending instance now exists with a future due date
    rows = (await db_session.execute(select(Task).where(Task.user_id == user.id))).scalars().all()
    assert len(rows) == 2
    new_tasks = [t for t in rows if t.due_date and t.due_date > past]
    assert len(new_tasks) == 1
    assert new_tasks[0].recurrence_rule == "FREQ=WEEKLY;BYDAY=MO"


@pytest.mark.asyncio
async def test_generate_recurring_tasks_skips_non_recurring(db_session):
    user = await _make_user(db_session, "nonrecur-worker@example.com")

    task = Task(
        user_id=user.id,
        title="One-off",
        status="pending",
        priority=0,
        due_date=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1),
        recurrence_rule=None,
    )
    db_session.add(task)
    await db_session.flush()

    result = await _generate_recurring_tasks_core(db_session)
    assert result["created"] == 0


@pytest.mark.asyncio
async def test_generate_recurring_tasks_skips_future(db_session):
    user = await _make_user(db_session, "future-worker@example.com")

    task = Task(
        user_id=user.id,
        title="Not due yet",
        status="pending",
        priority=0,
        due_date=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=5),
        recurrence_rule="FREQ=DAILY",
    )
    db_session.add(task)
    await db_session.flush()

    result = await _generate_recurring_tasks_core(db_session)
    assert result["created"] == 0
