"""Portfolio analytics: valuation, allocation, rebalancing, and net worth."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.models.finance import Account
from nexus.models.portfolio import Holding, Portfolio
from nexus.services.market import get_price

# Account types treated as liabilities
LIABILITY_TYPES = {"credit_card", "loan"}


def _price_for(holding: Holding) -> Decimal:
    """Return the best available price: live → last_price → cost_basis."""
    live = get_price(holding.ticker)
    if live is not None:
        return Decimal(str(live))
    if holding.last_price is not None:
        return Decimal(str(holding.last_price))
    return Decimal(str(holding.cost_basis))


def analyze_holding(holding: Holding) -> dict:
    """Compute value / cost / gain-loss for a single holding."""
    qty = Decimal(str(holding.quantity))
    cost_basis = Decimal(str(holding.cost_basis))
    price = _price_for(holding)

    market_value = qty * price
    total_cost = qty * cost_basis
    gain_loss = market_value - total_cost
    gain_loss_pct = (gain_loss / total_cost * 100) if total_cost else Decimal(0)

    return {
        "id": holding.id,
        "ticker": holding.ticker,
        "asset_class": holding.asset_class,
        "quantity": float(qty),
        "cost_basis": float(cost_basis),
        "current_price": float(price),
        "market_value": float(round(market_value, 2)),
        "total_cost": float(round(total_cost, 2)),
        "gain_loss": float(round(gain_loss, 2)),
        "gain_loss_pct": float(round(gain_loss_pct, 2)),
        "price_is_live": get_price(holding.ticker) is not None,
    }


def analyze_portfolio(portfolio: Portfolio, holdings: list[Holding]) -> dict:
    """Compute total value, gain/loss, and allocation by asset class."""
    holding_analytics = [analyze_holding(h) for h in holdings]

    total_value = sum(Decimal(str(h["market_value"])) for h in holding_analytics)
    total_cost = sum(Decimal(str(h["total_cost"])) for h in holding_analytics)
    total_gain = total_value - total_cost

    # Allocation by asset class
    by_class: dict[str, Decimal] = {}
    for h in holding_analytics:
        by_class[h["asset_class"]] = by_class.get(h["asset_class"], Decimal(0)) + Decimal(
            str(h["market_value"])
        )

    allocation = {
        cls: float(round(val / total_value * 100, 2)) if total_value else 0.0
        for cls, val in by_class.items()
    }

    return {
        "portfolio_id": portfolio.id,
        "name": portfolio.name,
        "total_value": float(round(total_value, 2)),
        "total_cost": float(round(total_cost, 2)),
        "total_gain_loss": float(round(total_gain, 2)),
        "total_gain_loss_pct": float(round(total_gain / total_cost * 100, 2) if total_cost else 0),
        "allocation": allocation,
        "target_allocation": portfolio.target_allocation or {},
        "holdings": holding_analytics,
    }


def rebalance_recommendations(portfolio: Portfolio, holdings: list[Holding]) -> dict:
    """Compare current allocation to target and recommend trades."""
    analysis = analyze_portfolio(portfolio, holdings)
    total = Decimal(str(analysis["total_value"]))
    target = portfolio.target_allocation or {}
    current = analysis["allocation"]

    recommendations = []
    for asset_class, target_pct in target.items():
        current_pct = Decimal(str(current.get(asset_class, 0)))
        target_pct_d = Decimal(str(target_pct))
        drift = current_pct - target_pct_d
        target_value = total * target_pct_d / 100
        current_value = total * current_pct / 100
        delta = target_value - current_value

        action = "hold"
        if drift > Decimal("1"):  # over-allocated by >1%
            action = "sell"
        elif drift < Decimal("-1"):
            action = "buy"

        recommendations.append(
            {
                "asset_class": asset_class,
                "current_pct": float(current_pct),
                "target_pct": float(target_pct_d),
                "drift_pct": float(round(drift, 2)),
                "action": action,
                "amount": float(round(abs(delta), 2)),
            }
        )

    return {
        "portfolio_id": portfolio.id,
        "total_value": float(round(total, 2)),
        "recommendations": recommendations,
    }


async def compute_net_worth(db: AsyncSession, user_id: int) -> dict:
    """Compute net worth = (accounts + portfolios) - liabilities."""
    # Accounts
    acct_result = await db.execute(select(Account).where(Account.user_id == user_id))
    accounts = acct_result.scalars().all()

    asset_accounts = Decimal(0)
    liabilities = Decimal(0)
    for a in accounts:
        bal = Decimal(str(a.balance or 0))
        if a.account_type in LIABILITY_TYPES:
            liabilities += bal
        else:
            asset_accounts += bal

    # Portfolios
    pf_result = await db.execute(select(Portfolio).where(Portfolio.user_id == user_id))
    portfolio_value = Decimal(0)
    for pf in pf_result.scalars().all():
        h_result = await db.execute(select(Holding).where(Holding.portfolio_id == pf.id))
        holdings = h_result.scalars().all()
        analysis = analyze_portfolio(pf, list(holdings))
        portfolio_value += Decimal(str(analysis["total_value"]))

    total_assets = asset_accounts + portfolio_value
    net_worth = total_assets - liabilities

    return {
        "total_assets": float(round(total_assets, 2)),
        "total_liabilities": float(round(liabilities, 2)),
        "net_worth": float(round(net_worth, 2)),
        "breakdown": {
            "cash_accounts": float(round(asset_accounts, 2)),
            "portfolio": float(round(portfolio_value, 2)),
            "liabilities": float(round(liabilities, 2)),
        },
    }
