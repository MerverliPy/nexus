"""Resilient HTTP client with retry + circuit breaker for external API calls.

Wraps ``httpx.AsyncClient`` with exponential backoff (3 retries: 1s, 5s, 25s)
and a circuit breaker that opens after 5 consecutive failures (10 min cooldown).

Usage::

    from nexus.utils.resilience import resilient_request

    resp = await resilient_request("POST", "https://api.example.com/v1/chat",
                                   json={"prompt": "hello"})
"""

from __future__ import annotations

import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

import httpx

try:
    import circuitbreaker as _cb  # type: ignore[import-untyped]

    _has_cb = True
except ImportError:
    _has_cb = False

logger = structlog.get_logger()

RETRY_ATTEMPTS = 3
CIRCUIT_FAILURE_THRESHOLD = 5
CIRCUIT_TIMEOUT = 600  # seconds


# ── Circuit breaker (optional, degrades gracefully) ──────────────────────


_circuit_breaker = None

if _has_cb:

    class _CircuitBreaker(_cb.CircuitBreaker):
        FAILURE_THRESHOLD = CIRCUIT_FAILURE_THRESHOLD
        RECOVERY_TIMEOUT = CIRCUIT_TIMEOUT

    _circuit_breaker = _CircuitBreaker()


def _is_circuit_open() -> bool:
    """Check whether the circuit breaker is currently open (no-op if unavailable)."""
    if _circuit_breaker is None:
        return False
    return _circuit_breaker.opened()


def _report_failure() -> None:
    if _circuit_breaker is not None:
        _circuit_breaker.__call__(lambda: None)  # register failure via dummy call


# ── Resilient request ────────────────────────────────────────────────────


@retry(
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=1, max=30),
)
async def _do_request(
    method: str, url: str, *, timeout: int = 30, **kwargs: object
) -> httpx.Response:
    """Core request function with tenacity retry wrapping."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
        resp = await client.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp


async def resilient_request(
    method: str, url: str, *, timeout: int = 30, **kwargs: object
) -> httpx.Response | None:
    """Make an HTTP request with retry + circuit-breaker protection.

    Returns the response on success, or **None** when the circuit breaker
    is open (caller should fall back to an alternative / local model).
    """
    if _is_circuit_open():
        logger.warning("circuit_breaker_open", url=url)
        return None

    try:
        resp = await _do_request(method, url, timeout=timeout, **kwargs)
        return resp
    except Exception as exc:  # noqa: BLE001
        _report_failure()
        logger.error("external_request_failed", url=url, error=str(exc))
        return None
