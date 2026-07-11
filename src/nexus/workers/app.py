"""Celery application factory and beat schedule.

The broker and result backend both use Redis (see ``settings.redis_url``).
Task modules are auto-discovered from ``nexus.workers.tasks``.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from nexus.config import get_settings

settings = get_settings()

app = Celery(
    "nexus",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["nexus.workers.tasks"],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # hard limit: 10 min
    task_soft_time_limit=540,  # soft limit: 9 min
    worker_max_tasks_per_child=100,
    broker_connection_retry_on_startup=True,
)

# ── Beat schedule (periodic tasks) ─────────────────────────────────────────

app.conf.beat_schedule = {
    "generate-recurring-tasks": {
        "task": "nexus.workers.tasks.generate_recurring_tasks",
        "schedule": crontab(minute=0, hour="*"),  # hourly
    },
    "retrain-categorizer": {
        "task": "nexus.workers.tasks.retrain_categorizer",
        "schedule": crontab(minute=0, hour=3),  # daily at 03:00 UTC
    },
    "daily-backup": {
        "task": "nexus.workers.tasks.run_backup",
        "schedule": crontab(minute=0, hour=3),  # daily at 03:00 UTC
    },
}
