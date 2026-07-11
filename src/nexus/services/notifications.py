"""Notification service — enqueue, bundle, and deliver notifications.

Delivery channels degrade gracefully: if Telegram is unreachable or no chat
ID is configured, the notification is marked ``failed`` rather than raising.
Network delivery is skipped under pytest for deterministic tests.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.config import get_settings
from nexus.models.notification import Notification, NotificationPreference

logger = structlog.get_logger()
settings = get_settings()

PRIORITIES = {"urgent", "normal", "digest"}


async def enqueue(
    db: AsyncSession,
    user_id: int,
    title: str,
    body: str | None = None,
    *,
    priority: str = "normal",
    channel: str = "telegram",
) -> Notification:
    """Create a notification. Urgent notifications are delivered immediately."""
    if priority not in PRIORITIES:
        priority = "normal"

    notif = Notification(
        user_id=user_id,
        title=title,
        body=body,
        priority=priority,
        channel=channel,
        status="pending",
    )
    db.add(notif)
    await db.flush()

    if priority == "urgent":
        await _deliver_one(db, notif, user_id)
        await db.flush()

    return notif


async def bundle_and_send(
    db: AsyncSession, user_id: int, *, priority_filter: str | None = None
) -> dict:
    """Bundle pending notifications for a user into one message and send it.

    ``priority_filter`` limits which pending notifications are bundled
    (e.g. "normal" for the hourly digest, "digest" for the daily summary).
    Returns a summary dict.
    """
    q = select(Notification).where(
        Notification.user_id == user_id, Notification.status == "pending"
    )
    if priority_filter:
        q = q.where(Notification.priority == priority_filter)
    q = q.order_by(Notification.created_at)

    result = await db.execute(q)
    pending = list(result.scalars().all())

    if not pending:
        return {"bundled": 0, "sent": False}

    message = _compose_digest(pending)
    chat_id = await _resolve_chat_id(db, user_id)
    delivered = await _send_telegram(chat_id, message)

    now = datetime.now(UTC).replace(tzinfo=None)
    for n in pending:
        n.status = "sent" if delivered else "failed"
        n.sent_at = now if delivered else None

    logger.info(
        "notifications_bundled",
        user_id=user_id,
        count=len(pending),
        delivered=delivered,
    )
    return {"bundled": len(pending), "sent": delivered}


# ── Delivery ──────────────────────────────────────────────────────────────


async def _deliver_one(db: AsyncSession, notif: Notification, user_id: int) -> bool:
    """Deliver a single (urgent) notification immediately."""
    chat_id = await _resolve_chat_id(db, user_id)
    text = f"🚨 {notif.title}"
    if notif.body:
        text += f"\n{notif.body}"
    delivered = await _send_telegram(chat_id, text)
    notif.status = "sent" if delivered else "failed"
    notif.sent_at = datetime.now(UTC).replace(tzinfo=None) if delivered else None
    return delivered


async def _resolve_chat_id(db: AsyncSession, user_id: int) -> str | None:
    """Return the per-user chat ID, falling back to the global config."""
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    pref = result.scalar_one_or_none()
    if pref and pref.telegram_chat_id:
        return pref.telegram_chat_id
    return settings.telegram_chat_id or None


async def _send_telegram(chat_id: str | None, text: str) -> bool:
    """Send a Telegram message. Returns True on success, False otherwise.

    Skips actual network I/O under pytest.
    """
    if "pytest" in sys.modules:
        return False  # deterministic: no delivery in tests

    token = settings.telegram_bot_token
    if not token or not chat_id:
        logger.warning("telegram_not_configured")
        return False

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10)) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
            return resp.status_code == 200
    except Exception as exc:  # noqa: BLE001
        logger.error("telegram_send_failed", error=str(exc))
        return False


def _compose_digest(notifications: list[Notification]) -> str:
    """Compose a bundled digest message from multiple notifications."""
    count = len(notifications)
    header = f"📬 Nexus digest — {count} update{'s' if count != 1 else ''}"
    lines = [header, ""]
    for i, n in enumerate(notifications, 1):
        line = f"{i}. {n.title}"
        if n.body:
            line += f" — {n.body}"
        lines.append(line)
    return "\n".join(lines)
