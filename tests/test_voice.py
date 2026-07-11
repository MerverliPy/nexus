"""Tests for voice interface — intent parsing and API endpoint."""

from unittest.mock import patch

import pytest
from fastapi import status

from nexus.services.voice import parse_intent, speak_text


class _FakeResp:
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content


# ── TTS unit tests ──────────────────────────────────────────────────────────


def test_speak_text_returns_none_without_api_key(monkeypatch):
    monkeypatch.setattr("nexus.services.voice._get_openai_key", lambda: "")
    assert speak_text("hello") is None


def test_speak_text_calls_openai():
    with patch("httpx.post", return_value=_FakeResp(200, b"mp3data")):
        with patch("nexus.services.voice._get_openai_key", return_value="sk-test"):
            result = speak_text("hello world", voice="nova")
            assert result == b"mp3data"


def test_speak_text_returns_none_on_api_error():
    with patch("httpx.post", return_value=_FakeResp(500, b"")):
        with patch("nexus.services.voice._get_openai_key", return_value="sk-test"):
            result = speak_text("hello")
            assert result is None


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


@pytest.mark.asyncio
async def test_speak_endpoint_requires_auth(client):
    response = await client.post("/api/v1/voice/speak", json={"text": "hello"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
