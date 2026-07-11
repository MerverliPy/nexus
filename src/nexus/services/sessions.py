"""Session management service — create, rotate, list, and revoke refresh sessions.

Enforces a maximum number of concurrent sessions per user (default 3).
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.models.session import RefreshSession

MAX_SESSIONS = 3


async def create_session(
    db: AsyncSession,
    user_id: int,
    jti: str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
    device_name: str | None = None,
) -> RefreshSession:
    """Create a new session, evicting the oldest if the limit is exceeded."""
    # Count existing sessions
    count_result = await db.execute(
        select(RefreshSession).where(RefreshSession.user_id == user_id)
    )
    existing = count_result.scalars().all()

    if len(existing) >= MAX_SESSIONS:
        # Delete the oldest session
        oldest = min(existing, key=lambda s: s.created_at)
        await db.delete(oldest)

    session = RefreshSession(
        user_id=user_id,
        jti=jti,
        ip_address=ip_address,
        user_agent=user_agent,
        device_name=device_name,
    )
    db.add(session)
    return session


async def rotate_session(
    db: AsyncSession,
    old_jti: str | None,
    new_jti: str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> RefreshSession | None:
    """Rotate a session: try to find the old jti, delete it, create a new one.

    Returns None if the old jti was not found (already revoked or expired).
    """
    user_id = None
    if old_jti is not None:
        result = await db.execute(
            select(RefreshSession).where(RefreshSession.jti == old_jti)
        )
        old = result.scalar_one_or_none()
        if old is not None:
            user_id = old.user_id
            await db.delete(old)

    if user_id is None:
        return None  # session already invalidated

    session = RefreshSession(
        user_id=user_id,
        jti=new_jti,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(session)
    return session


async def list_sessions(
    db: AsyncSession, user_id: int
) -> list[RefreshSession]:
    """Return all active sessions for a user."""
    result = await db.execute(
        select(RefreshSession)
        .where(RefreshSession.user_id == user_id)
        .order_by(RefreshSession.last_used_at.desc())
    )
    return list(result.scalars().all())


async def revoke_session(db: AsyncSession, session_id: int, user_id: int) -> bool:
    """Revoke one session by ID, scoped to the owning user. Returns True if found."""
    result = await db.execute(
        select(RefreshSession).where(
            RefreshSession.id == session_id, RefreshSession.user_id == user_id
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        return False
    await db.delete(session)
    return True


async def revoke_all_sessions(db: AsyncSession, user_id: int) -> int:
    """Revoke all sessions for a user. Returns the count of deleted rows."""
    result = await db.execute(
        delete(RefreshSession).where(RefreshSession.user_id == user_id)
    )
    return result.rowcount
