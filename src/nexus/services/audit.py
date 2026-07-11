"""Audit logging service — create immutable audit records.

Every sensitive action (login, MFA changes, etc.) writes an immutable entry to
the ``audit_logs`` table. An SQLAlchemy event guard prevents tampering.
"""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.models.automation import AuditLog


async def log(
    db: AsyncSession,
    user_id: int | None,
    action: str,
    *,
    resource_type: str | None = None,
    resource_id: int | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict | None = None,
) -> AuditLog:
    """Create and stage an immutable audit log row."""
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
    )
    db.add(entry)
    return entry


# ── Immutability guard ────────────────────────────────────────────────────


@event.listens_for(AuditLog, "before_update", propagate=True)
def _block_update(_mapper, _connection, target: AuditLog) -> None:
    raise ValueError("Audit log entries are immutable (update blocked).")


@event.listens_for(AuditLog, "before_delete", propagate=True)
def _block_delete(_mapper, _connection, target: AuditLog) -> None:
    raise ValueError("Audit log entries are immutable (delete blocked).")
