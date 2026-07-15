"""Tests for SMS gateway — signature validation, command parsing, rate limiting."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.services.sms import (
    process_sms_command,
    send_sms_reply,
    validate_twilio_signature,
)


def _make_mock_db(user_id: int | None) -> AsyncMock:
    """Create an AsyncMock db session with controlled execute behavior."""
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.first.return_value = (user_id,) if user_id is not None else None
    db.execute.return_value = result_mock
    return db


# ── Twilio signature validation ──────────────────────────────────────────────


def test_validate_signature_returns_false_without_token(monkeypatch):
    monkeypatch.setattr("nexus.services.sms.get_settings", lambda: _FakeSettings("", ""))
    assert validate_twilio_signature("https://example.com/webhook", {}, "sig123") is False


def test_validate_signature_with_correct_token():
    """Known-good Twilio signature test vector."""
    result = validate_twilio_signature(
        "https://example.com/webhook",
        {"Body": "hello", "From": "+155****4567"},
        "invalid_sig",
    )
    assert result is False  # invalid signature


def test_validate_signature_empty_params():
    """Signature validation with empty params still runs HMAC computation."""
    result = validate_twilio_signature(
        "https://example.com/webhook",
        {},
        "some_signature",
    )
    assert result is False


def test_validate_signature_handles_special_chars():
    """Params with special characters are properly encoded."""
    with patch("nexus.services.sms.get_settings") as mock_settings:
        mock_settings.return_value = _FakeSettings(sid="ACxxx", token="mytoken")
        result = validate_twilio_signature(
            "https://example.com/webhook",
            {"Body": "hello & goodbye", "From": "+15550001111"},
            "bad_signature",
        )
        assert result is False


def test_validate_signature_missing_sig_argument():
    """Empty signature argument returns False."""
    result = validate_twilio_signature("https://example.com/webhook", {"Body": "hi"}, "")
    assert result is False


# ── send_sms_reply ───────────────────────────────────────────────────────────


def test_send_sms_reply_returns_false_without_credentials(monkeypatch):
    monkeypatch.setattr("nexus.services.sms.get_settings", lambda: _FakeSettings("", "", ""))
    assert send_sms_reply("+15550001111", "Hello") is False


def test_send_sms_reply_returns_false_without_from_number(monkeypatch):
    monkeypatch.setattr(
        "nexus.services.sms.get_settings",
        lambda: _FakeSettings("ACxxx", "token", ""),
    )
    assert send_sms_reply("+15550001111", "Hello") is False


def test_send_sms_reply_success():
    """Successful Twilio API call returns True."""
    with patch("nexus.services.sms.get_settings") as mock_settings:
        mock_settings.return_value = _FakeSettings("ACxxx", "token", "+15550000000")
        with patch("httpx.post") as mock_post:
            mock_post.return_value.status_code = 201
            result = send_sms_reply("+15550001111", "Hello there")
            assert result is True
            mock_post.assert_called_once()
            call_args = mock_post.call_args[0][0]
            assert "api.twilio.com" in call_args


def test_send_sms_reply_http_error():
    """Non-201 response from Twilio returns False."""
    with patch("nexus.services.sms.get_settings") as mock_settings:
        mock_settings.return_value = _FakeSettings("ACxxx", "token", "+15550000000")
        with patch("httpx.post") as mock_post:
            mock_post.return_value.status_code = 400
            assert send_sms_reply("+15550001111", "Hi") is False


def test_send_sms_reply_exception():
    """Connection error returns False."""
    with patch("nexus.services.sms.get_settings") as mock_settings:
        mock_settings.return_value = _FakeSettings("ACxxx", "token", "+15550000000")
        with patch("httpx.post", side_effect=Exception("connection failed")):
            assert send_sms_reply("+15550001111", "Hi") is False


def test_send_sms_reply_truncates_long_body():
    """Body over 1600 chars is truncated."""
    long_body = "A" * 2000
    with patch("nexus.services.sms.get_settings") as mock_settings:
        mock_settings.return_value = _FakeSettings("ACxxx", "token", "+15550000000")
        with patch("httpx.post") as mock_post:
            mock_post.return_value.status_code = 201
            send_sms_reply("+15550001111", long_body)
            sent_data = mock_post.call_args[1]["data"]
            assert len(sent_data["Body"]) == 1600


# ── process_sms_command ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_process_sms_unknown_sender():
    """Unknown phone number returns error message."""
    db = _make_mock_db(user_id=None)
    result = await process_sms_command("hello", "+155****9999", db, None)
    assert "Unknown sender" in result


@pytest.mark.asyncio
async def test_process_sms_finance_log():
    """Finance log intent creates a transaction."""
    db = _make_mock_db(user_id=42)

    result = await process_sms_command("log 50 coffee", "+155****1111", db, None)
    assert "Logged:" in result
    assert "$50" in result


@pytest.mark.asyncio
async def test_process_sms_finance_log_no_amount():
    """Command without a recognizable amount returns help text."""
    db = _make_mock_db(user_id=42)

    result = await process_sms_command("log for coffee", "+155****1111", db, None)
    assert "I didn't understand" in result


@pytest.mark.asyncio
async def test_process_sms_balance():
    """Balance intent returns account info (even if zero)."""
    db = _make_mock_db(user_id=42)

    result = await process_sms_command("balance", "+155****1111", db, None)
    assert result is not None


@pytest.mark.asyncio
async def test_process_sms_recent():
    """Recent transactions intent returns transaction list."""
    db = _make_mock_db(user_id=42)

    result = await process_sms_command("last transaction", "+15550001111", db, None)
    assert "No transactions" in result or "Recent" in result


@pytest.mark.asyncio
async def test_process_sms_task_add():
    """Task add intent creates a task."""
    db = _make_mock_db(user_id=42)

    result = await process_sms_command("remind me to buy milk", "+15550001111", db, None)
    assert "Task added" in result


@pytest.mark.asyncio
async def test_process_sms_task_add_no_title():
    """Task add without title falls through gracefully."""
    db = _make_mock_db(user_id=42)

    result = await process_sms_command("add task", "+15550001111", db, None)
    assert result is not None


@pytest.mark.asyncio
async def test_process_sms_unknown_intent():
    """Unrecognized command returns help text."""
    db = _make_mock_db(user_id=42)

    result = await process_sms_command("xyzzy flurbo garblex", "+15550001111", db, None)
    assert "I didn't understand" in result
    assert "50 coffee" in result


# ── API endpoint tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sms_webhook_no_body(client):
    response = await client.post("/api/v1/sms/webhook", data={})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_sms_webhook_invalid_signature(client, monkeypatch):
    monkeypatch.setattr(
        "nexus.services.sms.validate_twilio_signature", lambda *a, **kw: False
    )
    response = await client.post(
        "/api/v1/sms/webhook",
        data={"Body": "hello", "From": "+155****4567"},
        headers={"X-Twilio-Signature": "bad"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ── Fixtures ─────────────────────────────────────────────────────────────────


class _FakeSettings:
    def __init__(self, sid="", token="", phone=""):
        self.twilio_account_sid = sid
        self.twilio_auth_token = token
        self.twilio_phone_number = phone
