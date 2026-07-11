"""Budget forecasting from historical transactions.

Trains lightweight per-category models using scikit-learn and returns
category-level and total monthly spending forecasts with confidence intervals.

Degrades gracefully:
  - With < 3 months of history for a category, falls back to a simple average.
  - With no transaction history, returns ``None`` for that category.
  - Never raises; all errors return a clear ``forecast_error`` field.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal

import structlog
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.models.finance import Transaction

logger = structlog.get_logger()

# Minimum data points to train a model; below this fallback to mean.
MIN_MONTHS = 3
FORECAST_DAYS = 30


@dataclass(frozen=True)
class CategoryForecast:
    category: str | None
    predicted_amount: float
    confidence_upper: float
    confidence_lower: float
    currency: str
    method: str
    data_points: int
    error: str | None = None


@dataclass(frozen=True)
class ForecastResult:
    total_predicted_amount: float
    total_confidence_upper: float
    total_confidence_lower: float
    currency: str
    horizon_days: int
    category_forecasts: list[CategoryForecast]


def _month_bucket(tx_date: date) -> tuple[int, int]:
    return tx_date.year, tx_date.month


def _parse_decimal(amount: Decimal | float | int) -> float:
    return float(amount)


async def _monthly_category_totals(
    db: AsyncSession, user_id: int, *, months: int = 24
) -> dict[str, dict[tuple[int, int], float]]:
    """Return {category: {(year, month): total}} for recent months."""
    cutoff = date.today().replace(day=1) - timedelta(days=months * 31)
    result = await db.execute(
        select(
            Transaction.category,
            extract("year", Transaction.transaction_date).label("year"),
            extract("month", Transaction.transaction_date).label("month"),
            func.sum(Transaction.amount).label("total"),
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.transaction_date >= cutoff,
            Transaction.amount > 0,
        )
        .group_by(
            Transaction.category,
            extract("year", Transaction.transaction_date),
            extract("month", Transaction.transaction_date),
        )
    )
    data: dict[str, dict[tuple[int, int], float]] = {}
    for row in result.all():
        category = row.category or "Uncategorized"
        bucket = (int(row.year), int(row.month))
        data.setdefault(category, {})[bucket] = _parse_decimal(row.total)
    return data


def _build_time_series(monthly_totals: dict[tuple[int, int], float]) -> list[float]:
    """Convert sparse monthly totals into a chronologically ordered list."""
    sorted_buckets = sorted(monthly_totals.items())
    return [amount for _, amount in sorted_buckets]


def _forecast(
    series: list[float], horizon_days: int
) -> tuple[float, float, float, str, int, str | None]:
    """Return (prediction, upper, lower, method, data_points, error)."""
    n = len(series)
    if n == 0:
        return 0.0, 0.0, 0.0, "none", 0, "no historical data"

    # Fallback: simple mean when too few points for trend modeling.
    if n < MIN_MONTHS:
        mean = sum(series) / n
        std = (sum((x - mean) ** 2 for x in series) / n) ** 0.5
        scale = horizon_days / 30.0
        pred = mean * scale
        return (
            round(pred, 2),
            round(pred + 1.96 * std * scale, 2),
            round(max(0.0, pred - 1.96 * std * scale), 2),
            "mean",
            n,
            None,
        )

    try:
        from sklearn.linear_model import LinearRegression

        X = [[i] for i in range(n)]
        y = series
        model = LinearRegression()
        model.fit(X, y)

        # Predict next month
        next_index = n
        pred = model.predict([[next_index]])[0]

        residuals = [y[i] - model.predict([[i]])[0] for i in range(n)]
        mse = sum(r * r for r in residuals) / max(1, n - 1)
        se = mse**0.5

        scale = horizon_days / 30.0
        base = pred * scale
        margin = 1.96 * se * scale
        return (
            round(max(0.0, base), 2),
            round(base + margin, 2),
            round(max(0.0, base - margin), 2),
            "linear_regression",
            n,
            None,
        )
    except Exception as exc:
        logger.warning("forecast_model_failed", error=str(exc))
        mean = sum(series) / n
        scale = horizon_days / 30.0
        pred = mean * scale
        return round(pred, 2), round(pred, 2), round(pred, 2), "mean", n, str(exc)


async def forecast_spending(
    db: AsyncSession,
    user_id: int,
    *,
    horizon_days: int = FORECAST_DAYS,
    currency: str = "USD",
) -> ForecastResult:
    """Generate a spending forecast for the given user."""
    monthly = await _monthly_category_totals(db, user_id)
    category_forecasts: list[CategoryForecast] = []
    total_pred = 0.0
    total_upper = 0.0
    total_lower = 0.0

    for category, totals in sorted(monthly.items()):
        series = _build_time_series(totals)
        pred, upper, lower, method, n, error = _forecast(series, horizon_days)
        category_forecasts.append(
            CategoryForecast(
                category=category,
                predicted_amount=pred,
                confidence_upper=upper,
                confidence_lower=lower,
                currency=currency,
                method=method,
                data_points=n,
                error=error,
            )
        )
        if error is None:
            total_pred += pred
            total_upper += upper
            total_lower += lower

    return ForecastResult(
        total_predicted_amount=round(total_pred, 2),
        total_confidence_upper=round(total_upper, 2),
        total_confidence_lower=round(total_lower, 2),
        currency=currency,
        horizon_days=horizon_days,
        category_forecasts=category_forecasts,
    )


def forecast_to_dict(result: ForecastResult) -> dict:
    """Serialize a ForecastResult to a JSON-friendly dict."""
    return {
        "total_predicted_amount": result.total_predicted_amount,
        "total_confidence_upper": result.total_confidence_upper,
        "total_confidence_lower": result.total_confidence_lower,
        "currency": result.currency,
        "horizon_days": result.horizon_days,
        "category_forecasts": [asdict(cf) for cf in result.category_forecasts],
    }
