"""Redis-backed fixed-window rate limiting.

Designed to **fail open**: if Redis is unavailable the caller is always
allowed through, so a Redis outage degrades security posture but never takes
down authentication. This keeps the API usable in environments (dev, tests)
where Redis is not running.
"""

from __future__ import annotations

import structlog

from nexus.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

_redis = None


def _client():
    """Lazily construct a module-level async Redis client."""
    global _redis
    if _redis is None:
        import redis.asyncio as aioredis

        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def hit(key: str, *, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Register one attempt against ``key`` within a fixed window.

    Returns ``(allowed, retry_after_seconds)``. When the limit is exceeded,
    ``allowed`` is False and ``retry_after_seconds`` is the TTL until reset.
    Fails open (``(True, 0)``) if Redis is unreachable.
    """
    try:
        client = _client()
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, window_seconds)
        if count > limit:
            ttl = await client.ttl(key)
            return False, max(int(ttl), 0)
        return True, 0
    except Exception as exc:  # noqa: BLE001 - fail open on any Redis error
        logger.warning("ratelimit_unavailable", key=key, error=str(exc))
        return True, 0


async def reset(key: str) -> None:
    """Clear the counter for ``key`` (e.g. after a successful auth)."""
    try:
        await _client().delete(key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ratelimit_reset_failed", key=key, error=str(exc))
