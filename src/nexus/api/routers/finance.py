"""Finance router — accounts and transactions CRUD, CSV import, analytics."""

import csv
import io
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.api.ws_manager import manager
from nexus.database import get_db
from nexus.models.finance import Account, Transaction
from nexus.models.user import User
from nexus.services import forecasting
from nexus.utils.categorizer import predict_category, record_correction
from nexus.utils.dependencies import get_current_user
from nexus.utils.ocr import process_receipt
from nexus.utils.storage import ensure_buckets, upload_receipt_bytes

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])


# ── Schemas ──────────────────────────────────────────────────────────────


class AccountCreate(BaseModel):
    name: str
    account_type: str  # checking, savings, credit_card, investment
    institution: str | None = None
    balance: Decimal | None = Decimal(0)


class AccountUpdate(BaseModel):
    name: str | None = None
    account_type: str | None = None
    institution: str | None = None
    balance: Decimal | None = None


class AccountResponse(BaseModel):
    id: int
    name: str
    account_type: str
    institution: str | None = None
    balance: Decimal
    is_active: bool
    last_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TransactionCreate(BaseModel):
    account_id: int | None = None
    amount: Decimal
    vendor: str | None = None
    category: str | None = None
    description: str | None = None
    transaction_date: date
    is_verified: bool = False


class TransactionUpdate(BaseModel):
    account_id: int | None = None
    amount: Decimal | None = None
    vendor: str | None = None
    category: str | None = None
    description: str | None = None
    transaction_date: date | None = None
    is_verified: bool | None = None


class TransactionResponse(BaseModel):
    id: int
    account_id: int | None = None
    amount: Decimal
    vendor: str | None = None
    category: str | None = None
    description: str | None = None
    transaction_date: date
    is_verified: bool
    receipt_url: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SpendingCategory(BaseModel):
    category: str
    total: Decimal
    count: int


class MonthlyTotal(BaseModel):
    year: int
    month: int
    total: Decimal
    count: int


# ── Account Endpoints ───────────────────────────────────────────────────


@router.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    body: AccountCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new financial account."""
    account = Account(
        user_id=user.id,
        name=body.name,
        account_type=body.account_type,
        institution=body.institution,
        balance=body.balance or Decimal(0),
        is_active=True,
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)
    account_data = AccountResponse.model_validate(account).model_dump(mode="json")
    await manager.broadcast(user.id, "account_created", account_data)
    return account


@router.get("/accounts", response_model=list[AccountResponse])
async def list_accounts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all accounts for the authenticated user."""
    result = await db.execute(select(Account).where(Account.user_id == user.id, Account.is_active))
    return result.scalars().all()


@router.get("/accounts/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single account by ID."""
    result = await db.execute(
        select(Account).where(Account.id == account_id, Account.user_id == user.id)
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


@router.patch("/accounts/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: int,
    body: AccountUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an account."""
    result = await db.execute(
        select(Account).where(Account.id == account_id, Account.user_id == user.id)
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(account, field, value)

    await db.flush()
    await db.refresh(account)
    account_data = AccountResponse.model_validate(account).model_dump(mode="json")
    await manager.broadcast(user.id, "account_updated", account_data)
    return account


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate an account (soft delete)."""
    result = await db.execute(
        select(Account).where(Account.id == account_id, Account.user_id == user.id)
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    account.is_active = False
    await db.flush()


# ── Transaction Endpoints ────────────────────────────────────────────────


@router.post(
    "/transactions", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED
)
async def create_transaction(
    body: TransactionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new transaction."""
    tx = Transaction(
        user_id=user.id,
        account_id=body.account_id,
        amount=body.amount,
        vendor=body.vendor,
        category=body.category,
        description=body.description,
        transaction_date=body.transaction_date,
        is_verified=body.is_verified,
    )
    db.add(tx)
    await db.flush()
    await db.refresh(tx)
    tx_data = TransactionResponse.model_validate(tx).model_dump(mode="json")
    await manager.broadcast(user.id, "transaction_created", tx_data)
    return tx


@router.get("/transactions", response_model=list[TransactionResponse])
async def list_transactions(
    vendor: str | None = Query(None),
    category: str | None = Query(None),
    account_id: int | None = Query(None),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List transactions with optional filters."""
    query = select(Transaction).where(Transaction.user_id == user.id)

    if vendor:
        query = query.where(Transaction.vendor.ilike(f"%{vendor}%"))
    if category:
        query = query.where(Transaction.category == category)
    if account_id:
        query = query.where(Transaction.account_id == account_id)
    if date_from:
        query = query.where(Transaction.transaction_date >= date_from)
    if date_to:
        query = query.where(Transaction.transaction_date <= date_to)

    query = query.order_by(Transaction.transaction_date.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single transaction by ID."""
    result = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user.id)
    )
    tx = result.scalar_one_or_none()
    if tx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return tx


@router.patch("/transactions/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: int,
    body: TransactionUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a transaction."""
    result = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user.id)
    )
    tx = result.scalar_one_or_none()
    if tx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tx, field, value)

    await db.flush()
    await db.refresh(tx)
    tx_data = TransactionResponse.model_validate(tx).model_dump(mode="json")
    await manager.broadcast(user.id, "transaction_updated", tx_data)
    return tx


@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a transaction."""
    result = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user.id)
    )
    tx = result.scalar_one_or_none()
    if tx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    await db.delete(tx)
    await db.flush()
    await manager.broadcast(user.id, "transaction_deleted", {"id": transaction_id})


# ── CSV Import ──────────────────────────────────────────────────────────


@router.post("/transactions/import", response_model=dict)
async def import_csv(
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Import transactions from a CSV file.

    Expected columns: date, description, amount (negative for expenses, positive for income)
    Optional columns: vendor, category, account_id
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    content = await file.read()
    text = content.decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="Empty or invalid CSV")

    # Auto-detect column mapping
    col_map = _detect_columns(reader.fieldnames)
    if "date" not in col_map or "amount" not in col_map:
        raise HTTPException(
            status_code=400,
            detail="CSV must have 'date' and 'amount' columns (auto-detected from: "
            + ", ".join(reader.fieldnames)
            + ")",
        )

    imported = 0
    skipped = 0
    errors = []

    for row_num, row in enumerate(reader, start=2):
        try:
            # Parse date
            tx_date = _parse_date(row[col_map["date"]])
            if tx_date is None:
                errors.append(f"Row {row_num}: invalid date '{row[col_map['date']]}'")
                skipped += 1
                continue

            # Parse amount
            amount = _parse_amount(row[col_map["amount"]])
            if amount is None:
                errors.append(f"Row {row_num}: invalid amount '{row[col_map['amount']]}'")
                skipped += 1
                continue

            # Duplicate check: same amount + date + vendor
            vendor = row.get(col_map.get("vendor", ""), "") if "vendor" in col_map else None
            dup_check = await db.execute(
                select(Transaction).where(
                    Transaction.user_id == user.id,
                    Transaction.amount == abs(amount),
                    Transaction.transaction_date == tx_date,
                    Transaction.vendor == (vendor or None),
                )
            )
            if dup_check.first() is not None:
                skipped += 1
                continue

            tx = Transaction(
                user_id=user.id,
                amount=abs(amount),
                vendor=vendor,
                category=(
                    row.get(col_map.get("category", ""), "") if "category" in col_map else None
                ),
                description=(
                    row.get(col_map.get("description", ""), "")
                    if "description" in col_map
                    else None
                ),
                transaction_date=tx_date,
                is_verified=False,
            )
            db.add(tx)
            imported += 1
        except Exception as e:
            errors.append(f"Row {row_num}: {str(e)}")
            skipped += 1

    await db.flush()
    return {"imported": imported, "skipped": skipped, "errors": errors[:10]}


def _detect_columns(fieldnames: list[str]) -> dict[str, str]:
    """Auto-detect column mapping from CSV headers."""
    lower = {c.lower().strip(): c for c in fieldnames}
    mapping: dict[str, str] = {}

    date_keys = {"date", "transaction_date", "tx_date", "posting_date", "posted"}
    amount_keys = {"amount", "sum", "total", "value", "debit", "credit", "withdrawal", "deposit"}
    vendor_keys = {"vendor", "merchant", "payee", "description", "name", "store"}
    category_keys = {"category", "type", "class"}
    description_keys = {"description", "memo", "notes", "details"}

    for k in date_keys:
        if k in lower:
            mapping["date"] = lower[k]
            break
    for k in amount_keys:
        if k in lower:
            mapping["amount"] = lower[k]
            break
    for k in vendor_keys:
        if k in lower:
            mapping["vendor"] = lower[k]
            break
    for k in category_keys:
        if k in lower:
            mapping["category"] = lower[k]
            break
    for k in description_keys:
        if k in lower:
            mapping["description"] = lower[k]
            break

    return mapping


def _parse_date(value: str) -> date | None:
    """Parse a date string in common formats."""
    from dateparser import parse as dp_parse

    result = dp_parse(value)
    if result:
        return result.date()
    return None


def _parse_amount(value: str) -> Decimal | None:
    """Parse an amount string, handling negative signs and currency symbols."""
    clean = value.replace("$", "").replace("€", "").replace("£", "").replace(",", "").strip()
    if not clean:
        return None
    # Handle parenthetical negatives: (50.00) → -50.00
    if clean.startswith("(") and clean.endswith(")"):
        clean = "-" + clean[1:-1]
    try:
        return Decimal(clean)
    except Exception:
        return None


# ── Analytics Endpoints ─────────────────────────────────────────────────


@router.get("/analytics/spending-by-category")
async def spending_by_category(
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate spending by category."""
    query = select(
        Transaction.category,
        func.sum(Transaction.amount).label("total"),
        func.count(Transaction.id).label("count"),
    ).where(
        Transaction.user_id == user.id,
        Transaction.amount > 0,  # expenses only
    )

    if date_from:
        query = query.where(Transaction.transaction_date >= date_from)
    if date_to:
        query = query.where(Transaction.transaction_date <= date_to)

    query = query.group_by(Transaction.category).order_by(func.sum(Transaction.amount).desc())
    result = await db.execute(query)
    rows = result.all()
    return [
        {"category": r.category or "Uncategorized", "total": float(r.total), "count": r.count}
        for r in rows
    ]


@router.get("/analytics/monthly-totals")
async def monthly_totals(
    months: int = Query(12, le=36),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate monthly spending totals."""
    from sqlalchemy import extract

    query = select(
        extract("year", Transaction.transaction_date).label("year"),
        extract("month", Transaction.transaction_date).label("month"),
        func.sum(Transaction.amount).label("total"),
        func.count(Transaction.id).label("count"),
    ).where(
        Transaction.user_id == user.id,
        Transaction.amount > 0,
    )

    query = (
        query.group_by(
            extract("year", Transaction.transaction_date),
            extract("month", Transaction.transaction_date),
        )
        .order_by(
            extract("year", Transaction.transaction_date).desc(),
            extract("month", Transaction.transaction_date).desc(),
        )
        .limit(months)
    )

    result = await db.execute(query)
    rows = result.all()
    return [
        {"year": int(r.year), "month": int(r.month), "total": float(r.total), "count": r.count}
        for r in rows
    ]


# ── Receipt OCR & Category Prediction ──────────────────────────────────


@router.post("/transactions/scan", response_model=dict)
async def scan_receipt(
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a receipt image, OCR it, and create a transaction.

    Returns the OCR result and created transaction.
    The user can review and edit before confirming.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are supported")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    # Save to temp file for OCR
    suffix = Path(file.filename).suffix if file.filename else ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = process_receipt(tmp_path)

        # Upload to MinIO
        ensure_buckets()
        object_name = f"user_{user.id}/{file.filename or 'receipt.jpg'}"
        receipt_url = upload_receipt_bytes(content, object_name)

        # Predict category
        category, cat_conf = None, 0.0
        if result.vendor:
            category, cat_conf = predict_category(result.vendor)

        # Always create a pending transaction from OCR
        tx_date = result.tx_date or date.today()
        tx = Transaction(
            user_id=user.id,
            amount=result.amount or Decimal(0),
            vendor=result.vendor,
            category=category if cat_conf >= 0.3 else None,
            transaction_date=tx_date,
            is_verified=result.is_reliable(),
            receipt_url=receipt_url,
        )
        db.add(tx)
        await db.flush()
        await db.refresh(tx)
        tx_data = TransactionResponse.model_validate(tx).model_dump(mode="json")
        await manager.broadcast(user.id, "transaction_created", tx_data)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {
        "transaction": tx_data,
        "ocr": {
            "raw_text": result.raw_text,
            "confidence": round(result.confidence, 2),
            "is_reliable": result.is_reliable(),
        },
        "prediction": {
            "category": category,
            "confidence": round(cat_conf, 2),
        },
    }


@router.post("/transactions/{transaction_id}/predict-category", response_model=dict)
async def predict_transaction_category(
    transaction_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Predict the category for a transaction based on its vendor name."""
    result = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user.id)
    )
    tx = result.scalar_one_or_none()
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if not tx.vendor:
        return {"category": None, "confidence": 0.0, "detail": "No vendor name to analyze"}

    category, confidence = predict_category(tx.vendor)
    return {"category": category, "confidence": round(confidence, 2), "vendor": tx.vendor}


@router.post("/transactions/{transaction_id}/correct-category", response_model=dict)
async def correct_transaction_category(
    transaction_id: int,
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record a user's category correction and retrain the model."""
    correct_category = body.get("category")
    if not correct_category:
        raise HTTPException(status_code=400, detail="Category is required")

    result = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user.id)
    )
    tx = result.scalar_one_or_none()
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Update the transaction
    tx.category = correct_category
    tx.is_verified = True
    await db.flush()

    # Record correction for model training
    if tx.vendor:
        record_correction(tx.vendor, correct_category)

    tx_data = TransactionResponse.model_validate(tx).model_dump(mode="json")
    await manager.broadcast(user.id, "transaction_updated", tx_data)

    return {"status": "corrected", "transaction": tx_data}


# ── Forecasting ─────────────────────────────────────────────────────────


@router.get("/analytics/forecast")
async def spending_forecast(
    horizon_days: int = Query(30, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Forecast spending per category for the next N days based on history."""
    result = await forecasting.forecast_spending(db, user.id, horizon_days=horizon_days)
    return forecasting.forecast_to_dict(result)
