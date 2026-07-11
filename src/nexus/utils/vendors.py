"""Vendor normalization — alias table with fuzzy matching fallback."""

import re
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.models.finance import VendorAlias

_FUZZY_THRESHOLD = 0.80


def clean_vendor_name(vendor: str) -> str:
    """Normalize vendor name: lowercase, remove common suffixes/punctuation."""
    v = vendor.lower().strip()
    v = re.sub(r"\b(inc|llc|ltd|corp|co|store|online|com|www)\b", "", v)
    v = re.sub(r"[^a-z0-9\s]", "", v)
    v = re.sub(r"\s+", " ", v).strip()
    return v


async def normalize_vendor(vendor: str, user_id: int, db: AsyncSession) -> str:
    """Resolve a raw vendor name to its canonical form via alias table.

    1. Exact match on raw_name → return canonical_name
    2. Fuzzy match (SequenceMatcher > 80%) → return closest canonical_name
    3. Fall through → return cleaned raw name
    """
    if not vendor or not vendor.strip():
        return vendor

    cleaned = clean_vendor_name(vendor)

    # 1. Exact match in alias table
    result = await db.execute(
        select(VendorAlias).where(
            VendorAlias.user_id == user_id,
            VendorAlias.raw_name == cleaned,
        )
    )
    exact = result.scalar_one_or_none()
    if exact is not None:
        return exact.canonical_name

    # 2. Fuzzy match against all user's aliases
    result = await db.execute(
        select(VendorAlias).where(VendorAlias.user_id == user_id)
    )
    aliases = result.scalars().all()

    best_score = _FUZZY_THRESHOLD
    best_match: str | None = None
    for alias in aliases:
        score = SequenceMatcher(None, cleaned, str(alias.raw_name)).ratio()
        if score > best_score:
            best_score = score
            best_match = str(alias.canonical_name)

    if best_match is not None:
        return best_match

    # 3. Fallback: return cleaned name as-is
    return cleaned


async def merge_vendors(
    raw_names: list[str],
    canonical_name: str,
    user_id: int,
    db: AsyncSession,
) -> int:
    """Create or update aliases mapping raw vendor names → canonical name.

    Returns number of aliases created/updated.
    """
    count = 0
    for raw in raw_names:
        cleaned = clean_vendor_name(raw)
        if not cleaned or cleaned == canonical_name:
            continue

        # Upsert: update existing or create new
        result = await db.execute(
            select(VendorAlias).where(
                VendorAlias.user_id == user_id,
                VendorAlias.raw_name == cleaned,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            if existing.canonical_name != canonical_name:
                existing.canonical_name = canonical_name
                count += 1
        else:
            db.add(
                VendorAlias(
                    user_id=user_id,
                    raw_name=cleaned,
                    canonical_name=canonical_name,
                )
            )
            count += 1

    await db.flush()
    return count


async def list_vendors(
    user_id: int,
    db: AsyncSession,
    search: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List all vendor aliases for the user, optionally filtered by search."""
    query = select(VendorAlias).where(VendorAlias.user_id == user_id)
    if search:
        query = query.where(
            VendorAlias.raw_name.ilike(f"%{search}%")
            | VendorAlias.canonical_name.ilike(f"%{search}%")
        )
    query = query.order_by(VendorAlias.raw_name).limit(limit)
    result = await db.execute(query)
    aliases = result.scalars().all()

    return [
        {
            "id": a.id,
            "raw_name": a.raw_name,
            "canonical_name": a.canonical_name,
        }
        for a in aliases
    ]


async def list_distinct_vendors(
    user_id: int,
    db: AsyncSession,
    limit: int = 100,
) -> list[dict]:
    """List distinct vendor names from transactions (for merge suggestions)."""
    from sqlalchemy import func

    from nexus.models.finance import Transaction

    result = await db.execute(
        select(
            Transaction.vendor,
            func.count(Transaction.id).label("tx_count"),
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.vendor.isnot(None),
            Transaction.vendor != "",
        )
        .group_by(Transaction.vendor)
        .order_by(func.count(Transaction.id).desc())
        .limit(limit)
    )
    return [
        {"vendor": row.vendor, "transaction_count": row.tx_count}
        for row in result.all()
    ]
