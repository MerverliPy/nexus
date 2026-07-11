"""Celery workers package for Nexus background jobs.

Import ``app`` for use with the Celery CLI:

    celery -A nexus.workers.app worker --loglevel=info
    celery -A nexus.workers.app beat --loglevel=info
"""

from nexus.workers.app import app

__all__ = ["app"]
