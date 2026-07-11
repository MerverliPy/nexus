"""Notification router — enqueue, list, digest, and preferences."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.database import get_db
from nexus.models.notification import Notification, NotificationPreference
from nexus.models.user import User
from nexus.services import notifications as notif_service
from nexus.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


# ── Schemas ──────────────────────────────────────────────────────────────


class NotificationCreate(BaseModel):
    title: str
    body: str | None = None
    priority: str = "normal"  # urgent, normal, digest
    channel: str = "telegram"


class NotificationResponse(BaseModel):
    id: int
    title: str
    body: str | None
    priority: str
    channel: str
    status: str

    model_config = {"from_attributes": True}


class DigestResponse(BaseModel):
    bundled: int
    sent: bool


class PreferenceUpdate(BaseModel):
    digest_hour: int | None = None
    urgent_immediate: bool | None = None
    bundle_normal: bool | None = None
    telegram_chat_id: str | None = None


class PreferenceResponse(BaseModel):
    digest_hour: int
    urgent_immediate: bool
    bundle_normal: bool
    telegram_chat_id: str | None

    model_config = {"from_attributes": True}


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    body: NotificationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationResponse:
    """Enqueue a notification (urgent ones are delivered immediately)."""
    notif = await notif_service.enqueue(
        db,
        user.id,
        body.title,
        body.body,
        priority=body.priority,
        channel=body.channel,
    )
    await db.refresh(notif)
    return NotificationResponse.model_validate(notif)


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    status_filter: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NotificationResponse]:
    """List the current user's notifications."""
    q = select(Notification).where(Notification.user_id == user.id)
    if status_filter:
        q = q.where(Notification.status == status_filter)
    q = q.order_by(Notification.created_at.desc()).limit(100)
    result = await db.execute(q)
    return [NotificationResponse.model_validate(n) for n in result.scalars().all()]


@router.post("/digest", response_model=DigestResponse)
async def send_digest(
    priority: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DigestResponse:
    """Bundle pending notifications and send them now."""
    result = await notif_service.bundle_and_send(db, user.id, priority_filter=priority)
    return DigestResponse(**result)


@router.get("/preferences", response_model=PreferenceResponse)
async def get_preferences(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PreferenceResponse:
    """Return notification preferences, creating defaults if absent."""
    pref = await _get_or_create_pref(db, user.id)
    return PreferenceResponse.model_validate(pref)


@router.put("/preferences", response_model=PreferenceResponse)
async def update_preferences(
    body: PreferenceUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PreferenceResponse:
    """Update notification preferences."""
    pref = await _get_or_create_pref(db, user.id)
    if body.digest_hour is not None:
        pref.digest_hour = body.digest_hour
    if body.urgent_immediate is not None:
        pref.urgent_immediate = body.urgent_immediate
    if body.bundle_normal is not None:
        pref.bundle_normal = body.bundle_normal
    if body.telegram_chat_id is not None:
        pref.telegram_chat_id = body.telegram_chat_id
    await db.flush()
    await db.refresh(pref)
    return PreferenceResponse.model_validate(pref)


async def _get_or_create_pref(db: AsyncSession, user_id: int) -> NotificationPreference:
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    pref = result.scalar_one_or_none()
    if pref is None:
        pref = NotificationPreference(user_id=user_id)
        db.add(pref)
        await db.flush()
        await db.refresh(pref)
    return pref
