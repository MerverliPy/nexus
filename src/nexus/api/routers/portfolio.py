"""Portfolio & net-worth router — holdings, analytics, rebalancing, snapshots."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.database import get_db
from nexus.models.portfolio import Holding, NetWorthSnapshot, Portfolio
from nexus.models.user import User
from nexus.services import portfolio as pf_service
from nexus.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


# ── Schemas ──────────────────────────────────────────────────────────────


class PortfolioCreate(BaseModel):
    name: str
    target_allocation: dict[str, float] | None = None


class PortfolioResponse(BaseModel):
    id: int
    name: str
    target_allocation: dict | None

    model_config = {"from_attributes": True}


class HoldingCreate(BaseModel):
    portfolio_id: int
    ticker: str
    quantity: float
    cost_basis: float
    asset_class: str = "stocks"
    last_price: float | None = None


class HoldingResponse(BaseModel):
    id: int
    ticker: str
    quantity: float
    cost_basis: float
    asset_class: str

    model_config = {"from_attributes": True}


class NetWorthResponse(BaseModel):
    total_assets: float
    total_liabilities: float
    net_worth: float
    breakdown: dict


# ── Portfolio CRUD ─────────────────────────────────────────────────────────


@router.post("", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    body: PortfolioCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortfolioResponse:
    portfolio = Portfolio(user_id=user.id, name=body.name, target_allocation=body.target_allocation)
    db.add(portfolio)
    await db.flush()
    await db.refresh(portfolio)
    return PortfolioResponse.model_validate(portfolio)


@router.get("", response_model=list[PortfolioResponse])
async def list_portfolios(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PortfolioResponse]:
    result = await db.execute(select(Portfolio).where(Portfolio.user_id == user.id))
    return [PortfolioResponse.model_validate(p) for p in result.scalars().all()]


async def _owned_portfolio(db: AsyncSession, portfolio_id: int, user_id: int) -> Portfolio:
    result = await db.execute(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
    )
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    return portfolio


# ── Holdings ─────────────────────────────────────────────────────────────


@router.post("/holdings", response_model=HoldingResponse, status_code=status.HTTP_201_CREATED)
async def add_holding(
    body: HoldingCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HoldingResponse:
    await _owned_portfolio(db, body.portfolio_id, user.id)
    holding = Holding(
        portfolio_id=body.portfolio_id,
        ticker=body.ticker.upper(),
        quantity=body.quantity,
        cost_basis=body.cost_basis,
        asset_class=body.asset_class,
        last_price=body.last_price,
    )
    db.add(holding)
    await db.flush()
    await db.refresh(holding)
    return HoldingResponse.model_validate(holding)


@router.delete("/holdings/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holding(
    holding_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Holding)
        .join(Portfolio, Holding.portfolio_id == Portfolio.id)
        .where(Holding.id == holding_id, Portfolio.user_id == user.id)
    )
    holding = result.scalar_one_or_none()
    if holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")
    await db.delete(holding)


# ── Analytics ────────────────────────────────────────────────────────────


@router.get("/{portfolio_id}/analytics")
async def portfolio_analytics(
    portfolio_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return valuation, gain/loss, and allocation for a portfolio."""
    portfolio = await _owned_portfolio(db, portfolio_id, user.id)
    result = await db.execute(select(Holding).where(Holding.portfolio_id == portfolio_id))
    holdings = list(result.scalars().all())
    return pf_service.analyze_portfolio(portfolio, holdings)


@router.get("/{portfolio_id}/rebalance")
async def portfolio_rebalance(
    portfolio_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return rebalancing recommendations vs the target allocation."""
    portfolio = await _owned_portfolio(db, portfolio_id, user.id)
    result = await db.execute(select(Holding).where(Holding.portfolio_id == portfolio_id))
    holdings = list(result.scalars().all())
    return pf_service.rebalance_recommendations(portfolio, holdings)


# ── Net worth ─────────────────────────────────────────────────────────────


@router.get("/networth/current", response_model=NetWorthResponse)
async def current_net_worth(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NetWorthResponse:
    """Compute the user's current net worth."""
    data = await pf_service.compute_net_worth(db, user.id)
    return NetWorthResponse(**data)


@router.post("/networth/snapshot", response_model=NetWorthResponse)
async def snapshot_net_worth(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NetWorthResponse:
    """Compute and persist a net-worth snapshot for today."""
    data = await pf_service.compute_net_worth(db, user.id)
    snapshot = NetWorthSnapshot(
        user_id=user.id,
        total_assets=data["total_assets"],
        total_liabilities=data["total_liabilities"],
        net_worth=data["net_worth"],
        breakdown=data["breakdown"],
        snapshot_date=date.today(),
    )
    db.add(snapshot)
    await db.flush()
    return NetWorthResponse(**data)
