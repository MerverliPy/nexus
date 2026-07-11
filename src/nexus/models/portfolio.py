"""Portfolio, holding, and net-worth models."""

from sqlalchemy import DECIMAL, JSON, Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from nexus.models.base import BaseModel


class Portfolio(BaseModel):
    """An investment portfolio with a target allocation."""

    __tablename__ = "portfolios"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(255), nullable=False)
    # Target allocation by asset class, e.g. {"stocks": 60, "bonds": 30, "cash": 10}
    target_allocation = Column(JSON, nullable=True)

    user = relationship("User")
    holdings = relationship("Holding", back_populates="portfolio", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Portfolio(id={self.id}, name='{self.name}')>"


class Holding(BaseModel):
    """A single position within a portfolio."""

    __tablename__ = "holdings"

    portfolio_id = Column(
        Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticker = Column(String(20), nullable=False, index=True)
    quantity = Column(DECIMAL(18, 6), nullable=False, default=0)
    cost_basis = Column(DECIMAL(18, 6), nullable=False, default=0)  # per share
    asset_class = Column(String(20), nullable=False, default="stocks")  # stocks/bonds/cash/crypto
    last_price = Column(DECIMAL(18, 6), nullable=True)  # latest known market price
    last_price_at = Column(DateTime, nullable=True)

    portfolio = relationship("Portfolio", back_populates="holdings")

    def __repr__(self) -> str:
        return f"<Holding(id={self.id}, ticker='{self.ticker}', qty={self.quantity})>"


class NetWorthSnapshot(BaseModel):
    """A point-in-time snapshot of the user's net worth."""

    __tablename__ = "net_worth_snapshots"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    total_assets = Column(DECIMAL(18, 2), nullable=False, default=0)
    total_liabilities = Column(DECIMAL(18, 2), nullable=False, default=0)
    net_worth = Column(DECIMAL(18, 2), nullable=False, default=0)
    breakdown = Column(JSON, nullable=True)  # {accounts: X, portfolio: Y, ...}
    snapshot_date = Column(Date, nullable=False, index=True)

    user = relationship("User")

    def __repr__(self) -> str:
        return f"<NetWorthSnapshot(id={self.id}, net_worth={self.net_worth})>"
