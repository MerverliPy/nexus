"""Tests for Celery worker configuration and task logic."""

import subprocess
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from sqlalchemy import select

from nexus.models.task import Task
from nexus.models.user import User
from nexus.workers import app as celery_app
from nexus.workers.tasks import (
    _generate_recurring_tasks_core,
    cleanup_expired_sessions,
    run_backup,
    send_daily_summary,
    send_notification_digests,
)

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
    assert "nexus.workers.tasks.send_notification_digests" in registered
    assert "nexus.workers.tasks.send_daily_summary" in registered


# ── Recurring task generation logic ──────────────────────────────────────


async def _make_user(db_session, email: str) -> User:
    user = User(email=email, password_hash="x", is_active=True)
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_generate_recurring_tasks_creates_next_instance(db_session):
    user = await _make_user(db_session, "recur-worker@example.com")

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


@pytest.mark.asyncio
async def test_generate_recurring_tasks_handles_completed_status(db_session):
    """Completed recurring tasks also get regenerated."""
    user = await _make_user(db_session, "completed-recur@example.com")

    past = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=2)
    task = Task(
        user_id=user.id,
        title="Monthly bill",
        status="completed",
        priority=1,
        due_date=past,
        recurrence_rule="FREQ=MONTHLY",
    )
    db_session.add(task)
    await db_session.flush()

    result = await _generate_recurring_tasks_core(db_session)
    assert result["created"] == 1


@pytest.mark.asyncio
async def test_generate_recurring_tasks_invalid_rrule(db_session):
    """Tasks with invalid RRULE strings are skipped."""
    user = await _make_user(db_session, "bad-rrule@example.com")

    past = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    task = Task(
        user_id=user.id,
        title="Bad rrule",
        status="pending",
        priority=0,
        due_date=past,
        recurrence_rule="NOTVALID",
    )
    db_session.add(task)
    await db_session.flush()

    result = await _generate_recurring_tasks_core(db_session)
    assert result["created"] == 0


# ── retrain_categorizer ──────────────────────────────────────────────────────


def test_retrain_categorizer_success():
    """Patch nexus.utils.categorizer (module imported inside the function)."""
    with patch("nexus.utils.categorizer") as mock_cat:
        mock_cat._get_model.return_value = MagicMock()
        mock_cat._load_corrections.return_value = [1, 2, 3]
        # MODEL_PATH.exists is accessed on the mock
        type(mock_cat.MODEL_PATH).exists = MagicMock(return_value=False)

        from nexus.workers.tasks import retrain_categorizer

        result = retrain_categorizer()
    assert result["status"] == "ok"
    assert result["corrections"] == 3


def test_retrain_categorizer_removes_old_model():
    with patch("nexus.utils.categorizer") as mock_cat:
        mock_cat._get_model.return_value = MagicMock()
        mock_cat._load_corrections.return_value = []
        type(mock_cat.MODEL_PATH).exists = MagicMock(return_value=True)

        from nexus.workers.tasks import retrain_categorizer

        result = retrain_categorizer()
    assert result["status"] == "ok"
    mock_cat.MODEL_PATH.unlink.assert_called_once()


def test_retrain_categorizer_error():
    with patch("nexus.utils.categorizer") as mock_cat:
        mock_cat._get_model.side_effect = ValueError("model failed")

        from nexus.workers.tasks import retrain_categorizer

        result = retrain_categorizer()
    assert result["status"] == "error"
    assert "model failed" in result["error"]


# ── run_backup ───────────────────────────────────────────────────────────────


@patch("nexus.workers.tasks.Path.exists")
@patch("nexus.workers.tasks.subprocess.run")
def test_run_backup_success(mock_run, mock_exists):
    mock_exists.return_value = True
    mock_run.return_value.returncode = 0

    result = run_backup()
    assert result["status"] == "ok"


@patch("nexus.workers.tasks.Path.exists")
def test_run_backup_script_not_found(mock_exists):
    mock_exists.return_value = False

    result = run_backup()
    assert result["status"] == "error"
    assert "backup.sh not found" in result["error"]


@patch("nexus.workers.tasks.Path.exists")
@patch("nexus.workers.tasks.subprocess.run")
def test_run_backup_failure(mock_run, mock_exists):
    mock_exists.return_value = True
    mock_run.return_value.returncode = 1

    result = run_backup()
    assert result["status"] == "error"
    assert result["returncode"] == 1


@patch("nexus.workers.tasks.Path.exists")
@patch("nexus.workers.tasks.subprocess.run",
       side_effect=subprocess.TimeoutExpired(cmd="bash", timeout=300))
def test_run_backup_timeout(mock_run, mock_exists):
    mock_exists.return_value = True

    result = run_backup()
    assert result["status"] == "error"


# ── cleanup_expired_sessions (query logic test with real db session) ─────────


@pytest.mark.asyncio
async def test_cleanup_expired_sessions_query(db_session):
    """Test the query that identifies expired sessions."""
    from nexus.models.session import RefreshSession
    from nexus.models.user import User
    from nexus.workers.tasks import _cleanup_expired_sessions

    user = User(email="session-test@example.com", password_hash="x", is_active=True)
    db_session.add(user)
    await db_session.flush()

    expired = RefreshSession(
        user_id=user.id,
        jti="expired-token-jti",
        device_name="test",
        last_used_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=10),
    )
    fresh = RefreshSession(
        user_id=user.id,
        jti="fresh-token-jti",
        device_name="test",
        last_used_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1),
    )
    db_session.add(expired)
    db_session.add(fresh)
    await db_session.flush()

    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=7)
    result = await db_session.execute(
        select(RefreshSession).where(RefreshSession.last_used_at < cutoff)
    )
    stale = result.scalars().all()
    assert len(stale) == 1
    assert stale[0].jti == "expired-token-jti"


# ── Notification digests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_digests_query(db_session):
    """Test the query that finds pending normal-priority notifications."""
    from nexus.models.notification import Notification
    from nexus.models.user import User

    user = User(email="digest-test@example.com", password_hash="x", is_active=True)
    db_session.add(user)
    await db_session.flush()

    notification = Notification(
        user_id=user.id,
        title="Test",
        body="Hello",
        priority="normal",
    )
    db_session.add(notification)
    await db_session.flush()

    result = await db_session.execute(
        select(Notification.user_id)
        .where(
            Notification.status == "pending",
            Notification.priority == "normal",
        )
        .distinct()
    )
    user_ids = [row[0] for row in result.all()]
    assert len(user_ids) >= 1
    assert user.id in user_ids


# ── Celery app-level sync wrappers ──────────────────────────────────────────


def test_run_backup_is_registered_task():
    assert "nexus.workers.tasks.run_backup" in celery_app.tasks


def test_notification_digest_tasks_registered():
    assert "nexus.workers.tasks.send_notification_digests" in celery_app.tasks
    assert "nexus.workers.tasks.send_daily_summary" in celery_app.tasks
