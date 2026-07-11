"""Tests for budget forecasting service and endpoint."""

from datetime import date, timedelta

import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.models.finance import Account, Transaction
from nexus.models.user import User
from nexus.services.forecasting import (
    _build_time_series,
    _forecast,
    forecast_spending,
    forecast_to_dict,
)


# ── Unit tests for pure helpers ─────────────────────────────────────────────


def test_build_time_series_orders_chronologically():
    totals = {(2024, 2): 100.0, (2023, 12): 50.0, (2024, 1): 75.0}
    assert _build_time_series(totals) == [50.0, 75.0, 100.0]


def test_forecast_empty_series():
    pred, upper, lower, method, n, error = _forecast([], 30)
    assert method == "none"
    assert n == 0
    assert error == "no historical data"
    assert pred == upper == lower == 0.0


def test_forecast_few_points_uses_mean():
    pred, upper, lower, method, n, error = _forecast([100.0, 120.0], 30)
    assert method == "mean"
    assert n == 2
    assert error is None
    assert pred == 110.0  # mean scaled to 30 days


def test_forecast_many_points_uses_linear_regression():
    pred, upper, lower, method, n, error = _forecast([100.0, 110.0, 120.0, 130.0], 30)
    assert method == "linear_regression"
    assert n == 4
    assert error is None
    assert pred > 130


def test_forecast_to_dict_serializes():
    from nexus.services.forecasting import CategoryForecast, ForecastResult

    result = ForecastResult(
        total_predicted_amount=150.0,
        total_confidence_upper=180.0,
        total_confidence_lower=120.0,
        currency="USD",
        horizon_days=30,
        category_forecasts=[
            CategoryForecast(
                category="Food",
                predicted_amount=100.0,
                confidence_upper=120.0,
                confidence_lower=80.0,
                currency="USD",
                method="linear_regression",
                data_points=4,
            )
        ],
    )
    serialized = forecast_to_dict(result)
    assert serialized["total_predicted_amount"] == 150.0
    assert serialized["currency"] == "USD"
    assert serialized["category_forecasts"][0]["category"] == "Food"


# ── Service tests with DB ───────────────────────────────────────────────────


async def _seed_user_with_transactions(db_session: AsyncSession) -> User:
    user = User(
        email="forecast@example.com",
        password_hash="hash",
        is_active=True,
        mfa_enabled=False,
    )
    db_session.add(user)
    await db_session.flush()

    account = Account(
        user_id=user.id,
        name="Checking",
        account_type="checking",
        balance=0,
    )
    db_session.add(account)
    await db_session.flush()

    base = date.today().replace(day=1)
    categories = ["Food", "Food", "Food", "Transport"]
    for i, category in enumerate(categories):
        tx = Transaction(
            user_id=user.id,
            account_id=account.id,
            amount=100.0 + i * 10,
            vendor="Vendor",
            category=category,
            transaction_date=base - timedelta(days=30 * i),
        )
        db_session.add(tx)

    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_forecast_spending_aggregates_by_category(db_session: AsyncSession):
    user = await _seed_user_with_transactions(db_session)

    result = await forecast_spending(db_session, user.id, horizon_days=30)  # type: ignore[arg-type]

    assert result.currency == "USD"
    assert result.horizon_days == 30
    assert result.total_predicted_amount >= 0
    assert result.total_confidence_upper >= result.total_predicted_amount

    categories = {f.category for f in result.category_forecasts}
    assert "Food" in categories
    assert "Transport" in categories
    assert "Uncategorized" not in categories


@pytest.mark.asyncio
async def test_forecast_spending_no_transactions_returns_empty(db_session: AsyncSession):
    user = User(
        email="empty@example.com",
        password_hash="hash",
        is_active=True,
        mfa_enabled=False,
    )
    db_session.add(user)
    await db_session.flush()

    result = await forecast_spending(db_session, user.id)  # type: ignore[arg-type]
    assert result.category_forecasts == []
    assert result.total_predicted_amount == 0.0


# ── API Endpoint tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_forecast_endpoint_requires_auth(client):
    response = await client.get("/api/v1/finance/analytics/forecast")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
