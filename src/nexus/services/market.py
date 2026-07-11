"""Market data service — fetch current prices with graceful degradation.

Provider chain:
  1. ``yfinance`` when installed.
  2. Direct Yahoo Finance chart API via httpx.
  3. Returns ``None`` when no source works — callers fall back to cost basis.

Prices are cached in-process for ``CACHE_TTL`` seconds to avoid hammering
external APIs.
"""

from __future__ import annotations

import time

import httpx
import structlog

from nexus.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

CACHE_TTL = 300  # 5 minutes
_cache: dict[str, tuple[float, float]] = {}  # ticker -> (price, fetched_at)

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"


def get_price(ticker: str) -> float | None:
    """Return the latest price for ``ticker``, or None if unavailable."""
    ticker = ticker.upper().strip()
    if not ticker:
        return None

    # Skip network under pytest for deterministic, fast tests.
    import sys

    if "pytest" in sys.modules or settings.nexus_env == "test":
        return None

    # Cache hit
    cached = _cache.get(ticker)
    if cached and (time.time() - cached[1]) < CACHE_TTL:
        return cached[0]

    price = _fetch_yfinance(ticker) or _fetch_yahoo_http(ticker)
    if price is not None:
        _cache[ticker] = (price, time.time())
    return price


def get_prices(tickers: list[str]) -> dict[str, float | None]:
    """Batch price lookup. Returns a dict of ticker -> price (or None)."""
    return {t: get_price(t) for t in tickers}


def _fetch_yfinance(ticker: str) -> float | None:
    try:
        import yfinance as yf

        data = yf.Ticker(ticker)
        info = data.fast_info
        price = getattr(info, "last_price", None)
        return float(price) if price else None
    except Exception:  # noqa: BLE001 - not installed / lookup failed
        return None


def _fetch_yahoo_http(ticker: str) -> float | None:
    try:
        with httpx.Client(timeout=httpx.Timeout(10)) as client:
            resp = client.get(
                YAHOO_CHART.format(ticker=ticker),
                params={"interval": "1d", "range": "1d"},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            resp.raise_for_status()
            data = resp.json()
            result = data["chart"]["result"][0]
            price = result["meta"].get("regularMarketPrice")
            return float(price) if price is not None else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("market_price_unavailable", ticker=ticker, error=str(exc))
        return None


def is_available() -> bool:
    """Best-effort check whether any price source is reachable."""
    return get_price("AAPL") is not None
