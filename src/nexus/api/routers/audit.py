"""Audit log read-only API router.

Provides authenticated access to the immutable audit trail with optional
filters (action, resource type, user, date range) and pagination.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.database import get_db
from nexus.models.automation import AuditLog
from nexus.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


class AuditLogEntry(BaseModel):
    """Public representation of one audit log row."""

    id: int
    user_id: int | None
    action: str
    resource_type: str | None
    resource_id: int | None
    ip_address: str | None
    user_agent: str | None
    details: dict | None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[AuditLogEntry])
async def list_audit_logs(
    action: str | None = Query(None, description="Filter by action (e.g. 'login', 'mfa_enroll')"),
    resource_type: str | None = Query(None, description="Filter by resource type"),
    user_id: int | None = Query(None, description="Filter by user ID"),
    date_from: date | None = Query(None, alias="from", description="Start date (inclusive)"),
    date_to: date | None = Query(None, alias="to", description="End date (inclusive)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> list[AuditLog]:
    """Return recent audit log entries, newest first."""
    q = select(AuditLog)
    if action:
        q = q.where(AuditLog.action == action)
    if resource_type:
        q = q.where(AuditLog.resource_type == resource_type)
    if user_id is not None:
        q = q.where(AuditLog.user_id == user_id)
    if date_from:
        q = q.where(AuditLog.created_at >= date_from)  # TimestampMixin field
    if date_to:
        q = q.where(AuditLog.created_at <= date_to)

    q = q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(q)
    rows = result.scalars().all()
    # Convert IPv4Address to string for JSON serialization
    return [
        AuditLogEntry(
            id=r.id,
            user_id=r.user_id,
            action=r.action,
            resource_type=r.resource_type,
            resource_id=r.resource_id,
            ip_address=str(r.ip_address) if r.ip_address else None,
            user_agent=r.user_agent,
            details=r.details,
        )
        for r in rows
    ]
