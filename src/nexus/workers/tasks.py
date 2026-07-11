"""Celery task definitions for Nexus background jobs.

Celery runs tasks synchronously, but Nexus uses async SQLAlchemy. Each task
that touches the DB spins up a short-lived async engine via ``asyncio.run``
to avoid sharing event loops across the worker pool.
"""

from __future__ import annotations

import asyncio
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from nexus.config import get_settings
from nexus.models.task import Task
from nexus.utils.recurrence import next_occurrence
from nexus.workers.app import app

logger = structlog.get_logger()
settings = get_settings()


def _run_async(coro):
    """Run an async coroutine to completion in a fresh event loop."""
    return asyncio.run(coro)


async def _session() -> tuple[AsyncSession, AsyncEngine]:
    """Create a short-lived async session bound to a new engine."""
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return maker(), engine


# ── Recurring task generation ──────────────────────────────────────────────


@app.task(name="nexus.workers.tasks.generate_recurring_tasks")
def generate_recurring_tasks() -> dict:
    """For each recurring task due, spawn the next occurrence instance.

    A task with a ``recurrence_rule`` whose ``due_date`` has passed gets a new
    pending instance created at its next occurrence, and its own due_date
    advanced so it is only processed once per period.
    """
    return _run_async(_generate_recurring_tasks())


async def _generate_recurring_tasks() -> dict:
    session, engine = await _session()
    try:
        async with session:
            result = await _generate_recurring_tasks_core(session)
            await session.commit()
    finally:
        await engine.dispose()
    logger.info("generate_recurring_tasks", created=result["created"])
    return result


async def _generate_recurring_tasks_core(session: AsyncSession) -> dict:
    """Core recurring-task generation logic against a provided session.

    Does NOT commit — the caller controls the transaction. Testable directly.
    """
    created = 0
    now = datetime.now(UTC)
    result = await session.execute(
        select(Task).where(
            Task.recurrence_rule.isnot(None),
            Task.due_date.isnot(None),
            Task.due_date <= now.replace(tzinfo=None),
            Task.status.in_(["pending", "completed"]),
        )
    )
    recurring = result.scalars().all()

    for task in recurring:
        nxt = next_occurrence(task.recurrence_rule, after=now)
        if nxt is None:
            continue
        new_task = Task(
            user_id=task.user_id,
            title=task.title,
            description=task.description,
            status="pending",
            priority=task.priority,
            due_date=nxt.replace(tzinfo=None),
            recurrence_rule=task.recurrence_rule,
            context=task.context,
        )
        session.add(new_task)
        # Advance the parent so it isn't reprocessed this period
        task.recurrence_rule = None
        created += 1

    return {"created": created}


# ── ML categorizer retraining ──────────────────────────────────────────────


@app.task(name="nexus.workers.tasks.retrain_categorizer")
def retrain_categorizer() -> dict:
    """Rebuild the transaction categorization model from seed + corrections."""
    from nexus.utils import categorizer

    # Force a rebuild by removing the cached model, then re-instantiate.
    try:
        if categorizer.MODEL_PATH.exists():
            categorizer.MODEL_PATH.unlink()
        categorizer._get_model()  # rebuilds and persists
        corrections = categorizer._load_corrections()
        logger.info("retrain_categorizer", corrections=len(corrections))
        return {"status": "ok", "corrections": len(corrections)}
    except Exception as exc:  # noqa: BLE001
        logger.error("retrain_categorizer_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


# ── Automated backup ────────────────────────────────────────────────────────


@app.task(name="nexus.workers.tasks.run_backup")
def run_backup() -> dict:
    """Invoke the backup script (scripts/backup.sh)."""
    script = Path(__file__).resolve().parents[3] / "scripts" / "backup.sh"
    if not script.exists():
        logger.error("run_backup_no_script", path=str(script))
        return {"status": "error", "error": "backup.sh not found"}

    try:
        proc = subprocess.run(
            ["bash", str(script)],
            capture_output=True,
            text=True,
            timeout=300,
            env={"NEXUS_DB_PASSWORD": settings.nexus_db_password, "PATH": "/usr/bin:/bin"},
        )
        if proc.returncode != 0:
            logger.error("run_backup_failed", stderr=proc.stderr[-500:])
            return {"status": "error", "returncode": proc.returncode}
        logger.info("run_backup_ok")
        return {"status": "ok"}
    except subprocess.TimeoutExpired:
        logger.error("run_backup_timeout")
        return {"status": "error", "error": "timeout"}


# ── Net worth / stale cleanup placeholder ─────────────────────────────────


@app.task(name="nexus.workers.tasks.cleanup_expired_sessions")
def cleanup_expired_sessions() -> dict:
    """Remove refresh sessions older than the refresh-token TTL."""
    return _run_async(_cleanup_expired_sessions())


async def _cleanup_expired_sessions() -> dict:
    from nexus.models.session import RefreshSession

    session, engine = await _session()
    removed = 0
    try:
        async with session:
            cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(
                days=settings.nexus_refresh_token_expire_days
            )
            result = await session.execute(
                select(RefreshSession).where(RefreshSession.created_at < cutoff)
            )
            for s in result.scalars().all():
                await session.delete(s)
                removed += 1
            await session.commit()
    finally:
        await engine.dispose()

    logger.info("cleanup_expired_sessions", removed=removed)
    return {"removed": removed}
