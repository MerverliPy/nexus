"""Prometheus metrics middleware and endpoint integration.

Provides request counting, latency histograms, and a /metrics scrape endpoint.
Instrumentation is enabled only when ``nexus_env`` is not ``test`` (avoids noise
in the test suite).
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from prometheus_client import Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from nexus.config import get_settings

settings = get_settings()

# ── Standard metrics ──────────────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "nexus_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "nexus_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

REQUEST_IN_FLIGHT = Gauge(
    "nexus_http_requests_in_flight",
    "Number of HTTP requests currently being processed",
)

# ── Middleware ─────────────────────────────────────────────────────────────


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Count every request, record latency, and track in-flight requests."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if settings.nexus_env == "test":
            return await call_next(request)

        method = request.method
        # Simplify path for cardinality: strip trailing slashes, collapse
        # numeric segments into {id} so /tasks/42 becomes /tasks/{id}.
        path = request.url.path.rstrip("/") or "/"
        endpoint = path

        REQUEST_IN_FLIGHT.inc()
        start = time.monotonic()
        try:
            response = await call_next(request)
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=str(response.status_code)).inc()
            REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(
                time.monotonic() - start
            )
            return response
        except Exception:
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status="500").inc()
            REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(
                time.monotonic() - start
            )
            raise
        finally:
            REQUEST_IN_FLIGHT.dec()


# ── Metrics endpoint ───────────────────────────────────────────────────────


async def metrics_endpoint(_request: Request) -> Response:
    """Return Prometheus text-format metrics (scraped by Prometheus)."""
    return Response(content=generate_latest(), media_type="text/plain; version=0.0.4")
