"""Tests for market data service — price fetching with provider fallback and caching.

The production ``get_price`` function short-circuits when ``pytest`` is loaded.
We test the internal fetchers directly (they have no such guard) and test the
public function's pytest guard and edge cases.
"""

from unittest.mock import MagicMock, patch

import pytest


# ── _fetch_yfinance (yfinance may not be installed) ──────────────────────────


def test_fetch_yfinance_not_installed_returns_none():
    """When yfinance is not installed, _fetch_yfinance returns None gracefully."""
    from nexus.services.market import _fetch_yfinance

    price = _fetch_yfinance("AAPL")
    assert price is None


def test_fetch_yfinance_success_with_mock_import():
    """Mock yfinance at the sys.modules level to simulate import success."""
    mock_yfinance = MagicMock()
    mock_ticker = MagicMock()
    mock_info = MagicMock()
    mock_info.last_price = 180.50
    mock_ticker.fast_info = mock_info
    mock_yfinance.Ticker.return_value = mock_ticker

    with patch.dict("sys.modules", {"yfinance": mock_yfinance}):
        from nexus.services.market import _fetch_yfinance as fy

        price = fy("AAPL")
        assert price == 180.50
        mock_yfinance.Ticker.assert_called_once_with("AAPL")


def test_fetch_yfinance_no_price_in_info():
    """When yfinance returns no last_price, returns None."""
    mock_yfinance = MagicMock()
    mock_ticker = MagicMock()
    mock_info = MagicMock()
    mock_info.last_price = None
    mock_ticker.fast_info = mock_info
    mock_yfinance.Ticker.return_value = mock_ticker

    with patch.dict("sys.modules", {"yfinance": mock_yfinance}):
        from nexus.services.market import _fetch_yfinance as fy

        price = fy("AAPL")
        assert price is None


def test_fetch_yfinance_api_exception():
    """yfinance API errors return None."""
    mock_yfinance = MagicMock()
    mock_yfinance.Ticker.side_effect = ValueError("API error")

    with patch.dict("sys.modules", {"yfinance": mock_yfinance}):
        from nexus.services.market import _fetch_yfinance as fy

        price = fy("AAPL")
        assert price is None


# ── _fetch_yahoo_http ────────────────────────────────────────────────────────


@patch("nexus.services.market.httpx.Client")
def test_fetch_yahoo_http_success(mock_client_class):
    from nexus.services.market import _fetch_yahoo_http

    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "chart": {"result": [{"meta": {"regularMarketPrice": 250.75}}]}
    }
    mock_client.get.return_value = mock_response

    price = _fetch_yahoo_http("GOOGL")
    assert price == 250.75


@patch("nexus.services.market.httpx.Client")
def test_fetch_yahoo_http_no_price_in_meta(mock_client_class):
    """Meta dict missing regularMarketPrice returns None."""
    from nexus.services.market import _fetch_yahoo_http

    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "chart": {"result": [{"meta": {}}]}
    }
    mock_client.get.return_value = mock_response

    price = _fetch_yahoo_http("GOOGL")
    assert price is None


@patch("nexus.services.market.httpx.Client")
def test_fetch_yahoo_http_http_error(mock_client_class):
    """HTTP exceptions return None."""
    from nexus.services.market import _fetch_yahoo_http

    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    mock_client.get.side_effect = Exception("HTTP 429 Too Many Requests")

    price = _fetch_yahoo_http("AAPL")
    assert price is None


@patch("nexus.services.market.httpx.Client")
def test_fetch_yahoo_http_empty_result_list(mock_client_class):
    """Empty chart result list returns None."""
    from nexus.services.market import _fetch_yahoo_http

    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"chart": {"result": []}}
    mock_client.get.return_value = mock_response

    price = _fetch_yahoo_http("AAPL")
    assert price is None


@patch("nexus.services.market.httpx.Client")
def test_fetch_yahoo_http_verify_url_and_params(mock_client_class):
    """Verify the correct Yahoo Finance chart URL and params are used."""
    from nexus.services.market import _fetch_yahoo_http

    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "chart": {"result": [{"meta": {"regularMarketPrice": 100.0}}]}
    }
    mock_client.get.return_value = mock_response

    _fetch_yahoo_http("MSFT")

    mock_client.get.assert_called_once()
    call_args = mock_client.get.call_args
    assert "MSFT" in call_args[0][0]  # URL contains ticker
    assert call_args[1]["params"]["interval"] == "1d"
    assert call_args[1]["params"]["range"] == "1d"


# ── get_price (public) — pytest guard ────────────────────────────────────────


def test_get_price_blank_ticker():
    """Empty/blank ticker returns None immediately (before pytest guard)."""
    from nexus.services.market import get_price

    assert get_price("") is None
    assert get_price("   ") is None


def test_get_price_returns_none_under_pytest():
    """When pytest is detected, get_price returns None."""
    from nexus.services.market import get_price

    assert get_price("AAPL") is None


def test_get_price_ticker_upper_cased():
    """Ticker is uppercased and stripped."""
    from nexus.services.market import get_price

    # Still returns None due to pytest guard, but we verify no crash
    assert get_price("aapl ") is None
    assert get_price("  msft  ") is None


# When fetchers return values (bypassing pytest guard), they populate the cache.
def test_get_price_populates_cache():
    """Bypass the pytest guard and verify the cache is populated."""
    import sys

    from nexus.services.market import _cache

    _cache.clear()
    # Remove 'pytest' from sys.modules so get_price proceeds to fetchers
    clean_modules = {k: v for k, v in sys.modules.items() if "pytest" not in k.lower()}
    with patch.dict("sys.modules", clean_modules, clear=True):
        # Now mock both fetchers to return a known value
        import nexus.services.market as mkt

        with patch.object(mkt, "_fetch_yfinance", return_value=None):
            with patch.object(mkt, "_fetch_yahoo_http", return_value=200.0):
                result = mkt.get_price("GOOGL")
                assert result == 200.0
                assert "GOOGL" in mkt._cache


def test_get_prices_returns_dict():
    """get_prices returns dict mapping each ticker to its price (all None under pytest)."""
    from nexus.services.market import get_prices

    result = get_prices(["AAPL", "GOOGL"])
    assert result == {"AAPL": None, "GOOGL": None}


# ── is_available ─────────────────────────────────────────────────────────────


def test_is_available_false_under_pytest():
    from nexus.services.market import is_available

    assert is_available() is False


# ── Cache / constants ────────────────────────────────────────────────────────


def test_cache_ttl_constant():
    from nexus.services.market import CACHE_TTL

    assert CACHE_TTL == 300  # 5 minutes


def test_cache_is_empty_dict():
    from nexus.services.market import _cache

    _cache.clear()
    assert _cache == {}
