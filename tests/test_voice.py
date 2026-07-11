"""Tests for voice interface — intent parsing and API endpoint."""

import pytest
from fastapi import status

from nexus.services.voice import parse_intent


# ── Intent parsing unit tests ───────────────────────────────────────────────


def test_parse_finance_log_with_dollars():
    intent = parse_intent("log 50 dollars for coffee")
    assert intent["intent"] == "finance_log"
    assert intent["entities"]["amount"] == 50
    assert intent["entities"]["vendor"] == "coffee"


def test_parse_finance_log_with_dollar_sign():
    intent = parse_intent("$20 for lunch at chipotle")
    assert intent["intent"] == "finance_log"
    assert intent["entities"]["amount"] == 20
    assert "chipotle" in intent["entities"]["vendor"]


def test_parse_finance_log_spent():
    intent = parse_intent("spent 15 on uber")
    assert intent["intent"] == "finance_log"
    assert intent["entities"]["amount"] == 15
    assert intent["entities"]["vendor"] == "uber"


def test_parse_task_add():
    intent = parse_intent("remind me to call dentist tomorrow")
    assert intent["intent"] == "task_add"
    assert intent["entities"]["title"] == "call dentist tomorrow"


def test_parse_task_todo():
    intent = parse_intent("todo buy groceries")
    assert intent["intent"] == "task_add"
    assert intent["entities"]["title"] == "buy groceries"


def test_parse_finance_balance():
    intent = parse_intent("whats my balance")
    assert intent["intent"] == "finance_balance"


def test_parse_finance_recent():
    intent = parse_intent("show last transaction")
    assert intent["intent"] == "finance_recent"


def test_parse_unknown():
    intent = parse_intent("blah blah nothing relevant")
    assert intent["intent"] == "unknown"


def test_parse_finance_paid():
    intent = parse_intent("paid 45 at starbucks")
    assert intent["intent"] == "finance_log"
    assert intent["entities"]["amount"] == 45


# ── API endpoint tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_transcribe_endpoint_with_text(client):
    """Test text-only transcription (no auth needed for parse, but endpoint requires auth)."""
    response = await client.post(
        "/api/v1/voice/transcribe",
        data={"text": "log 50 for coffee"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_transcribe_endpoint_no_input(client):
    response = await client.post("/api/v1/voice/transcribe")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
