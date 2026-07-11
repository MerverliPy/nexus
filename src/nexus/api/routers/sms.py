"""SMS webhook router — Twilio incoming message handler."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.database import get_db
from nexus.services.sms import process_sms_command, send_sms_reply, validate_twilio_signature

router = APIRouter(prefix="/api/v1/sms", tags=["sms"])

# In-memory rate limit store: phone → [timestamps]
_rate_limit_store: dict[str, list[float]] = {}
_RATE_LIMIT_MAX = 10
_RATE_LIMIT_WINDOW = 3600  # 1 hour


def _check_rate_limit(phone: str) -> bool:
    """Return True if the phone is under the rate limit."""
    import time

    now = time.time()
    timestamps = _rate_limit_store.get(phone, [])
    # Prune old entries
    timestamps = [t for t in timestamps if now - t < _RATE_LIMIT_WINDOW]
    _rate_limit_store[phone] = timestamps

    if len(timestamps) >= _RATE_LIMIT_MAX:
        return False

    timestamps.append(now)
    return True


@router.post("/webhook")
async def sms_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Twilio incoming SMS webhook.

    Validates X-Twilio-Signature, parses the message body as a command,
    executes it, and replies via Twilio API.
    """
    # Twilio sends form-encoded data
    form = await request.form()
    body = str(form.get("Body", "")).strip()
    from_number = str(form.get("From", ""))
    signature = request.headers.get("X-Twilio-Signature", "")

    if not body or not from_number:
        raise HTTPException(status_code=400, detail="Missing Body or From")

    # Build the full URL Twilio used to sign
    url = str(request.url)

    # Convert form to dict for validation
    params = {k: str(v) for k, v in form.items()}
    if not validate_twilio_signature(url, params, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    # Rate limit
    if not _check_rate_limit(from_number):
        send_sms_reply(from_number, "Rate limit reached. Try again later.")
        return {"status": "rate_limited"}

    # Process command
    reply = await process_sms_command(body, from_number, db, None)

    # Send reply via Twilio
    send_sms_reply(from_number, reply)

    return {"status": "ok", "reply": reply[:200]}
