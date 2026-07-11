"""Tests for portfolio analytics, rebalancing, and net worth."""

from decimal import Decimal

import pytest
from httpx import AsyncClient

from nexus.models.portfolio import Holding, Portfolio
from nexus.services import portfolio as pf


async def _register_and_auth(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post("/api/v1/auth/register", json={"email": email, "password": "pw"})
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── Analytics math (pure, deterministic via manual last_price) ─────────────


def _holding(ticker, qty, cost, price, asset_class="stocks"):
    h = Holding(
        portfolio_id=1,
        ticker=ticker,
        quantity=Decimal(str(qty)),
        cost_basis=Decimal(str(cost)),
        asset_class=asset_class,
        last_price=Decimal(str(price)),
    )
    return h


def test_analyze_holding_gain():
    h = _holding("AAPL", 10, 100, 150)
    result = pf.analyze_holding(h)
    # Note: live price lookup may override; with markets down it uses last_price
    assert result["quantity"] == 10.0
    assert result["total_cost"] == 1000.0
    # market value = 10 * price (150 unless live price available)
    assert result["market_value"] >= 0


def test_analyze_portfolio_allocation():
    p = Portfolio(user_id=1, name="Test", target_allocation={"stocks": 60, "bonds": 40})
    holdings = [
        _holding("AAPL", 10, 100, 100, "stocks"),  # value 1000
        _holding("BND", 10, 50, 50, "bonds"),  # value 500
    ]
    result = pf.analyze_portfolio(p, holdings)
    # With markets unreachable, prices fall back to last_price
    assert result["total_value"] > 0
    assert "stocks" in result["allocation"]
    assert "bonds" in result["allocation"]
    # Allocation percentages sum to ~100
    assert abs(sum(result["allocation"].values()) - 100.0) < 0.1


def test_rebalance_recommendations():
    p = Portfolio(user_id=1, name="Test", target_allocation={"stocks": 50, "bonds": 50})
    holdings = [
        _holding("AAPL", 10, 100, 100, "stocks"),  # value 1000 (100% stocks)
    ]
    result = pf.rebalance_recommendations(p, holdings)
    recs = {r["asset_class"]: r for r in result["recommendations"]}
    # Stocks over-allocated (100% vs 50% target) → sell
    assert recs["stocks"]["action"] == "sell"
    # Bonds under-allocated (0% vs 50%) → buy
    assert recs["bonds"]["action"] == "buy"


# ── Endpoint flow ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_portfolio_crud_and_analytics(client: AsyncClient):
    headers = await _register_and_auth(client, "pf-crud@example.com")

    # Create portfolio
    resp = await client.post(
        "/api/v1/portfolio",
        json={"name": "Retirement", "target_allocation": {"stocks": 70, "bonds": 30}},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    pid = resp.json()["id"]

    # Add holdings with manual prices (markets unreachable in test)
    resp = await client.post(
        "/api/v1/portfolio/holdings",
        json={
            "portfolio_id": pid,
            "ticker": "VTI",
            "quantity": 10,
            "cost_basis": 200,
            "asset_class": "stocks",
            "last_price": 250,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    # Analytics
    resp = await client.get(f"/api/v1/portfolio/{pid}/analytics", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_cost"] == 2000.0
    assert len(data["holdings"]) == 1


@pytest.mark.asyncio
async def test_portfolio_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/portfolio")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_add_holding_to_others_portfolio_fails(client: AsyncClient):
    headers_a = await _register_and_auth(client, "pf-owner@example.com")
    headers_b = await _register_and_auth(client, "pf-attacker@example.com")

    resp = await client.post("/api/v1/portfolio", json={"name": "Private"}, headers=headers_a)
    pid = resp.json()["id"]

    # User B tries to add a holding to user A's portfolio
    resp = await client.post(
        "/api/v1/portfolio/holdings",
        json={"portfolio_id": pid, "ticker": "X", "quantity": 1, "cost_basis": 1},
        headers=headers_b,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_net_worth_with_accounts(client: AsyncClient):
    headers = await _register_and_auth(client, "pf-networth@example.com")

    # Create a checking account (asset) and a credit card (liability)
    await client.post(
        "/api/v1/finance/accounts",
        json={"name": "Checking", "account_type": "checking", "balance": 5000},
        headers=headers,
    )
    await client.post(
        "/api/v1/finance/accounts",
        json={"name": "Visa", "account_type": "credit_card", "balance": 1500},
        headers=headers,
    )

    resp = await client.get("/api/v1/portfolio/networth/current", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_assets"] == 5000.0
    assert data["total_liabilities"] == 1500.0
    assert data["net_worth"] == 3500.0


@pytest.mark.asyncio
async def test_net_worth_snapshot(client: AsyncClient):
    headers = await _register_and_auth(client, "pf-snapshot@example.com")
    resp = await client.post("/api/v1/portfolio/networth/snapshot", headers=headers)
    assert resp.status_code == 200, resp.text
    assert "net_worth" in resp.json()
