"""Tests for vendor normalization."""

import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.models.finance import Transaction, VendorAlias
from nexus.models.user import User
from nexus.utils.vendors import (
    clean_vendor_name,
    list_distinct_vendors,
    list_vendors,
    merge_vendors,
    normalize_vendor,
)


# ── Unit tests ───────────────────────────────────────────────────────────────


def test_clean_vendor_lowercases_and_strips():
    assert clean_vendor_name("  Starbucks  ") == "starbucks"


def test_clean_vendor_removes_suffixes():
    assert clean_vendor_name("Amazon Inc.") == "amazon"
    assert clean_vendor_name("Best Buy Co") == "best buy"
    assert clean_vendor_name("Walmart.com") == "walmart"


def test_clean_vendor_removes_punctuation():
    assert clean_vendor_name("McDonald's") == "mcdonalds"
    assert clean_vendor_name("AT&T") == "att"


def test_clean_vendor_empty_string():
    assert clean_vendor_name("") == ""


# ── Service tests with DB ────────────────────────────────────────────────────


async def _seed_user(db_session: AsyncSession) -> User:
    user = User(
        email="vendor@example.com",
        password_hash="hash",
        is_active=True,
        mfa_enabled=False,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_normalize_vendor_exact_match(db_session: AsyncSession):
    user = await _seed_user(db_session)
    db_session.add(VendorAlias(user_id=user.id, raw_name="starbucks", canonical_name="Starbucks"))
    await db_session.flush()

    result = await normalize_vendor("Starbucks", user.id, db_session)  # type: ignore[arg-type]
    assert result == "Starbucks"


@pytest.mark.asyncio
async def test_normalize_vendor_fuzzy_match(db_session: AsyncSession):
    user = await _seed_user(db_session)
    db_session.add(VendorAlias(user_id=user.id, raw_name="starbucks", canonical_name="Starbucks"))
    await db_session.flush()

    # "starbuks" is close to "starbucks" (>80%)
    result = await normalize_vendor("starbuks", user.id, db_session)  # type: ignore[arg-type]
    assert result == "Starbucks"


@pytest.mark.asyncio
async def test_normalize_vendor_fallback_when_no_match(db_session: AsyncSession):
    user = await _seed_user(db_session)

    result = await normalize_vendor("some random vendor", user.id, db_session)  # type: ignore[arg-type]
    assert result == "some random vendor"


@pytest.mark.asyncio
async def test_normalize_vendor_empty_returns_empty(db_session: AsyncSession):
    user = await _seed_user(db_session)

    result = await normalize_vendor("", user.id, db_session)  # type: ignore[arg-type]
    assert result == ""


@pytest.mark.asyncio
async def test_merge_vendors_creates_new_aliases(db_session: AsyncSession):
    user = await _seed_user(db_session)

    count = await merge_vendors(
        ["starbucks", "star bucks", "sbux"], "Starbucks", user.id, db_session  # type: ignore[arg-type]
    )
    assert count == 3

    result = await db_session.execute(
        __import__("sqlalchemy").select(VendorAlias).where(VendorAlias.user_id == user.id)
    )
    aliases = result.scalars().all()
    assert len(aliases) == 3


@pytest.mark.asyncio
async def test_merge_vendors_updates_existing(db_session: AsyncSession):
    user = await _seed_user(db_session)
    db_session.add(VendorAlias(user_id=user.id, raw_name="starbucks", canonical_name="Coffee"))
    await db_session.flush()

    count = await merge_vendors(["starbucks"], "Starbucks", user.id, db_session)  # type: ignore[arg-type]
    assert count == 1

    result = await db_session.execute(
        __import__("sqlalchemy").select(VendorAlias).where(
            VendorAlias.user_id == user.id, VendorAlias.raw_name == "starbucks"
        )
    )
    alias = result.scalar_one()
    assert alias.canonical_name == "Starbucks"


@pytest.mark.asyncio
async def test_merge_vendors_skips_equivalent_canonical(db_session: AsyncSession):
    user = await _seed_user(db_session)

    # canonical_name gets cleaned to lowercase; same as raw_name → skip
    count = await merge_vendors(["Starbucks"], "starbucks", user.id, db_session)  # type: ignore[arg-type]
    assert count == 0


@pytest.mark.asyncio
async def test_list_vendors_returns_aliases(db_session: AsyncSession):
    user = await _seed_user(db_session)
    db_session.add(VendorAlias(user_id=user.id, raw_name="amzn", canonical_name="Amazon"))
    db_session.add(VendorAlias(user_id=user.id, raw_name="sbux", canonical_name="Starbucks"))
    await db_session.flush()

    result = await list_vendors(user.id, db_session)  # type: ignore[arg-type]
    assert len(result) == 2
    assert result[0]["raw_name"] == "amzn"
    assert result[1]["canonical_name"] == "Starbucks"


@pytest.mark.asyncio
async def test_list_vendors_with_search(db_session: AsyncSession):
    user = await _seed_user(db_session)
    db_session.add(VendorAlias(user_id=user.id, raw_name="amzn", canonical_name="Amazon"))
    db_session.add(VendorAlias(user_id=user.id, raw_name="sbux", canonical_name="Starbucks"))
    await db_session.flush()

    result = await list_vendors(user.id, db_session, search="bux")  # type: ignore[arg-type]
    assert len(result) == 1
    assert result[0]["raw_name"] == "sbux"


@pytest.mark.asyncio
async def test_list_distinct_vendors_from_transactions(db_session: AsyncSession):
    user = await _seed_user(db_session)
    from datetime import date

    for vendor in ["Amazon", "Starbucks", "Amazon", "Uber"]:
        db_session.add(
            Transaction(
                user_id=user.id,
                amount=10,
                vendor=vendor,
                transaction_date=date.today(),
            )
        )
    await db_session.flush()

    result = await list_distinct_vendors(user.id, db_session)  # type: ignore[arg-type]
    assert len(result) == 3
    vendors = {r["vendor"] for r in result}
    assert vendors == {"Amazon", "Starbucks", "Uber"}
    # Amazon should have count=2
    amazon_entry = next(r for r in result if r["vendor"] == "Amazon")
    assert amazon_entry["transaction_count"] == 2


# ── API Endpoint tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_vendors_endpoint_requires_auth(client):
    response = await client.get("/api/v1/finance/vendors")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_vendors_distinct_endpoint_requires_auth(client):
    response = await client.get("/api/v1/finance/vendors/distinct")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_merge_vendors_endpoint_requires_auth(client):
    response = await client.post("/api/v1/finance/vendors/merge", json={"raw_names": ["a"], "canonical_name": "b"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
