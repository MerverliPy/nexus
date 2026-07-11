"""SMS gateway — receive commands via Twilio, parse, execute, reply."""

from nexus.config import get_settings
from nexus.services.voice import parse_intent, parse_intent_llm


def validate_twilio_signature(
    url: str,
    params: dict[str, str],
    signature: str,
) -> bool:
    """Validate that a Twilio webhook request is authentic."""
    settings = get_settings()
    auth_token = settings.twilio_auth_token
    if not auth_token:
        return False

    import hmac
    import hashlib
    from urllib.parse import urlencode

    # Sort params and build the signed URL
    signed_params = {k: v for k, v in sorted(params.items())}
    signed_url = url
    if signed_params:
        signed_url += "?" + urlencode(signed_params)

    expected = hmac.new(
        auth_token.encode("utf-8"),
        signed_url.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    expected_b64 = __import__("base64").b64encode(expected).decode()

    return hmac.compare_digest(expected_b64, signature)


async def process_sms_command(
    body: str,
    from_number: str,
    db,
    user_resolver,
) -> str:
    """Process an incoming SMS command and return a reply.

    1. Resolve phone → user
    2. Parse intent
    3. Execute command
    4. Return reply
    """
    # Resolve user by phone number (from a lookup table or metadata)
    user_id = await _resolve_user_by_phone(from_number, db, user_resolver)
    if user_id is None:
        return "Unknown sender. Register your phone number first."

    # Parse intent — try LLM for complex commands, fall back to regex
    intent = parse_intent_llm(body)

    if intent["intent"] == "unknown":
        # Try regex as fallback
        intent = parse_intent(body)

    # Execute based on intent
    entities = intent.get("entities", {})

    if intent["intent"] == "finance_log":
        return await _execute_finance_log(user_id, entities, db)

    elif intent["intent"] == "finance_balance":
        return await _execute_finance_balance(user_id, db)

    elif intent["intent"] == "finance_recent":
        return await _execute_finance_recent(user_id, db)

    elif intent["intent"] == "task_add":
        return await _execute_task_add(user_id, entities, db)

    else:
        return (
            "I didn't understand that. Try:\n"
            '"50 coffee" — log expense\n'
            '"balance" — check balances\n'
            '"recent" — last 3 transactions\n'
            '"remind me to call dentist" — add task'
        )


async def _resolve_user_by_phone(
    phone: str, db, user_resolver
) -> int | None:
    """Resolve a phone number to a user ID."""
    from sqlalchemy import select

    from nexus.models.user import User

    result = await db.execute(
        select(User.id).where(User.sms_phone == phone)
    )
    row = result.first()
    if row:
        return row[0]
    return None


async def _execute_finance_log(user_id: int, entities: dict, db) -> str:
    """Log an expense from SMS."""
    amount = entities.get("amount")
    vendor = entities.get("vendor", "unknown")
    if not amount:
        return "Could not parse amount. Try: 50 coffee"

    from datetime import date
    from decimal import Decimal

    from nexus.models.finance import Transaction

    tx = Transaction(
        user_id=user_id,
        amount=Decimal(str(amount)),
        vendor=str(vendor),
        transaction_date=date.today(),
    )
    db.add(tx)
    await db.flush()

    return f"Logged: ${amount:.2f} at {vendor}"


async def _execute_finance_balance(user_id: int, db) -> str:
    """Return account balances."""
    from sqlalchemy import select

    from nexus.models.finance import Account

    result = await db.execute(
        select(Account).where(Account.user_id == user_id, Account.is_active)
    )
    accounts = result.scalars().all()

    if not accounts:
        return "No accounts found."

    lines = []
    total = 0
    for a in accounts:
        lines.append(f"{a.name}: ${float(a.balance):,.2f}")
        total += float(a.balance)
    lines.append(f"Total: ${total:,.2f}")
    return "\n".join(lines)


async def _execute_finance_recent(user_id: int, db) -> str:
    """Return last 3 transactions."""
    from sqlalchemy import select

    from nexus.models.finance import Transaction

    result = await db.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.transaction_date.desc())
        .limit(3)
    )
    txs = result.scalars().all()

    if not txs:
        return "No transactions yet."

    lines = ["Recent transactions:"]
    for tx in txs:
        date_str = tx.transaction_date.isoformat()
        vendor = tx.vendor or "—"
        cat = f" [{tx.category}]" if tx.category else ""
        lines.append(f"${float(tx.amount):,.2f} — {vendor}{cat} ({date_str})")
    return "\n".join(lines)


async def _execute_task_add(user_id: int, entities: dict, db) -> str:
    """Add a task from SMS."""
    title = entities.get("title")
    if not title:
        return "Could not parse task. Try: remind me to buy milk"

    from datetime import date

    from nexus.models.task import Task

    task = Task(
        user_id=user_id,
        title=title,
        due_date=date.today(),
        status="pending",
    )
    db.add(task)
    await db.flush()

    return f"Task added: {title}"


def send_sms_reply(to_number: str, body: str) -> bool:
    """Send an SMS reply via Twilio."""
    settings = get_settings()
    sid = settings.twilio_account_sid
    token = settings.twilio_auth_token
    from_number = settings.twilio_phone_number

    if not sid or not token or not from_number:
        return False

    import base64

    import httpx

    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()

    try:
        resp = httpx.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            headers={"Authorization": f"Basic {auth}"},
            data={
                "To": to_number,
                "From": from_number,
                "Body": body[:1600],
            },
            timeout=10,
        )
        return resp.status_code == 201
    except Exception:
        return False
