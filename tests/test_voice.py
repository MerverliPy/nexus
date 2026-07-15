"""Tests for voice interface — audio recording, transcription, intent parsing, TTS."""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
from fastapi import status

from nexus.services.voice import (
    parse_intent,
    parse_intent_llm,
    play_audio,
    record_audio,
    speak_text,
    transcribe_audio,
)


# ── record_audio ────────────────────────────────────────────────────────────


@patch("nexus.services.voice.subprocess.run")
@patch("nexus.services.voice.tempfile.NamedTemporaryFile")
def test_record_audio_success(mock_tmpfile, mock_run):
    mock_tmpfile.return_value.__enter__.return_value.name = "/tmp/recording.wav"
    mock_tmpfile.return_value.name = "/tmp/recording.wav"

    result = record_audio(duration=3)
    assert result is not None
    assert str(result) == "/tmp/recording.wav"
    mock_run.assert_called_once()
    assert "-d" in mock_run.call_args[0][0]
    assert "3" in mock_run.call_args[0][0]


@patch("nexus.services.voice.subprocess.run", side_effect=FileNotFoundError)
@patch("nexus.services.voice.tempfile.NamedTemporaryFile")
def test_record_audio_arecord_missing(mock_tmpfile, mock_run):
    mock_tmpfile.return_value.name = "/tmp/recording.wav"

    result = record_audio(duration=3)
    assert result is None


@patch("nexus.services.voice.subprocess.run", side_effect=FileNotFoundError)
@patch("nexus.services.voice.tempfile.NamedTemporaryFile")
def test_record_audio_cleans_up_on_failure(mock_tmpfile, mock_run):
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = True
    mock_tmpfile.return_value.name = "/tmp/recording.wav"

    with patch("nexus.services.voice.Path", return_value=mock_path):
        result = record_audio(duration=3)
    assert result is None


# ── transcribe_audio ─────────────────────────────────────────────────────────


def test_transcribe_audio_no_api_key(monkeypatch):
    monkeypatch.setattr("nexus.services.voice._get_openai_key", lambda: "")
    result = transcribe_audio(Path("/tmp/test.wav"))
    assert result is None


def test_transcribe_audio_success():
    """Uses httpx.post (imported inside function) — patch at httpx level."""
    with patch("nexus.services.voice._get_openai_key", return_value="sk-test"):
        with patch.object(Path, "read_bytes", return_value=b"audio_data"):
            with patch("httpx.post") as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.text = "Hello world"
                result = transcribe_audio(Path("/tmp/test.wav"))
    assert result == "Hello world"


def test_transcribe_audio_api_error():
    with patch("nexus.services.voice._get_openai_key", return_value="sk-test"):
        with patch.object(Path, "read_bytes", return_value=b"audio_data"):
            with patch("httpx.post") as mock_post:
                mock_post.return_value.status_code = 400
                mock_post.return_value.text = "error"
                result = transcribe_audio(Path("/tmp/test.wav"))
    assert result is None


def test_transcribe_audio_exception():
    with patch("nexus.services.voice._get_openai_key", return_value="sk-test"):
        with patch.object(Path, "read_bytes", return_value=b"audio_data"):
            with patch("httpx.post", side_effect=Exception("timeout")):
                result = transcribe_audio(Path("/tmp/test.wav"))
    assert result is None


# ── parse_intent (regex-based) ───────────────────────────────────────────────


class TestParseIntentFinanceLog:
    """All the regex patterns for finance_log."""

    def test_log_with_dollars(self):
        intent = parse_intent("log 50 dollars for coffee")
        assert intent["intent"] == "finance_log"
        assert intent["entities"]["amount"] == 50
        assert intent["entities"]["vendor"] == "coffee"

    def test_log_with_dollar_sign(self):
        intent = parse_intent("$20 for lunch at chipotle")
        assert intent["intent"] == "finance_log"
        assert intent["entities"]["amount"] == 20
        assert "chipotle" in intent["entities"]["vendor"]

    def test_log_spent(self):
        intent = parse_intent("spent 15 on uber")
        assert intent["intent"] == "finance_log"
        assert intent["entities"]["amount"] == 15
        assert intent["entities"]["vendor"] == "uber"

    def test_log_paid(self):
        intent = parse_intent("paid 45 at starbucks")
        assert intent["intent"] == "finance_log"
        assert intent["entities"]["amount"] == 45

    def test_log_spend(self):
        intent = parse_intent("spend 12.50 at subway")
        assert intent["intent"] == "finance_log"
        assert intent["entities"]["amount"] == 12.50

    def test_log_dollar_sign_amount_only(self):
        intent = parse_intent("$8 for lunch")
        assert intent["intent"] == "finance_log"
        assert intent["entities"]["amount"] == 8

    def test_log_with_bucks(self):
        intent = parse_intent("spent 30 bucks on gas")
        assert intent["intent"] == "finance_log"
        assert intent["entities"]["amount"] == 30

    def test_log_on_vendor(self):
        intent = parse_intent("log 25 on amazon")
        assert intent["intent"] == "finance_log"
        assert intent["entities"]["vendor"] == "amazon"

    def test_log_at_vendor(self):
        intent = parse_intent("paid 20 at walmart")
        assert intent["intent"] == "finance_log"
        assert intent["entities"]["vendor"] == "walmart"

    def test_log_for_vendor(self):
        intent = parse_intent("spent 100 for groceries")
        assert intent["intent"] == "finance_log"


class TestParseIntentTaskAdd:
    def test_remind_me_to(self):
        intent = parse_intent("remind me to call dentist tomorrow")
        assert intent["intent"] == "task_add"
        assert intent["entities"]["title"] == "call dentist tomorrow"

    def test_todo(self):
        intent = parse_intent("todo buy groceries")
        assert intent["intent"] == "task_add"
        assert intent["entities"]["title"] == "buy groceries"

    def test_add_task(self):
        intent = parse_intent("add task write report")
        assert intent["intent"] == "task_add"
        assert intent["entities"]["title"] == "write report"

    def test_remember_to(self):
        intent = parse_intent("remember to pay bills")
        assert intent["intent"] == "task_add"
        assert intent["entities"]["title"] == "pay bills"

    def test_remind_uppercase(self):
        """Case insensitive test."""
        intent = parse_intent("REMIND ME TO EXERCISE")
        assert intent["intent"] == "task_add"

    def test_todo_strips_whitespace(self):
        intent = parse_intent("todo   clean garage")
        assert intent["intent"] == "task_add"
        assert intent["entities"]["title"] == "clean garage"


class TestParseIntentFinanceBalance:
    def test_balance_keyword(self):
        intent = parse_intent("whats my balance")
        assert intent["intent"] == "finance_balance"

    def test_balance_direct(self):
        intent = parse_intent("balance")
        assert intent["intent"] == "finance_balance"

    def test_how_much_money(self):
        intent = parse_intent("how much money do I have")
        assert intent["intent"] == "finance_balance"


class TestParseIntentFinanceRecent:
    def test_last_transaction(self):
        intent = parse_intent("show last transaction")
        assert intent["intent"] == "finance_recent"

    def test_recent_transaction(self):
        intent = parse_intent("recent transaction")
        assert intent["intent"] == "finance_recent"

    def test_last_purchase(self):
        intent = parse_intent("last purchase")
        assert intent["intent"] == "finance_recent"

    def test_last_transaction_case_insensitive(self):
        intent = parse_intent("LAST TRANSACTION")
        assert intent["intent"] == "finance_recent"


class TestParseIntentUnknown:
    def test_gibberish(self):
        intent = parse_intent("blah blah nothing relevant")
        assert intent["intent"] == "unknown"

    def test_empty_string(self):
        intent = parse_intent("")
        assert intent["intent"] == "unknown"

    def test_single_word(self):
        intent = parse_intent("hello")
        assert intent["intent"] == "unknown"


# ── parse_intent_llm ─────────────────────────────────────────────────────────


def test_parse_intent_llm_no_api_key(monkeypatch):
    monkeypatch.setattr("nexus.services.voice.get_settings", lambda: _FakeVoiceSettings(""))
    result = parse_intent_llm("buy milk")
    assert result["intent"] == "unknown"


@patch("nexus.services.voice._openrouter_completion")
def test_parse_intent_llm_valid_json(mock_completion):
    mock_completion.return_value = '{"intent":"task_add","entities":{"title":"buy milk"}}'
    with patch("nexus.services.voice.get_settings", lambda: _FakeVoiceSettings("sk-or-test")):
        result = parse_intent_llm("buy milk")
    assert result["intent"] == "task_add"
    assert result["entities"]["title"] == "buy milk"


@patch("nexus.services.voice._openrouter_completion")
def test_parse_intent_llm_invalid_json(mock_completion):
    """Invalid JSON from LLM falls back to unknown."""
    mock_completion.return_value = "not valid json"
    with patch("nexus.services.voice.get_settings", lambda: _FakeVoiceSettings("sk-or-test")):
        result = parse_intent_llm("buy milk")
    assert result["intent"] == "unknown"


@patch("nexus.services.voice._openrouter_completion")
def test_parse_intent_llm_none_response(mock_completion):
    mock_completion.return_value = None
    with patch("nexus.services.voice.get_settings", lambda: _FakeVoiceSettings("sk-or-test")):
        result = parse_intent_llm("buy milk")
    assert result["intent"] == "unknown"


# ── _openrouter_completion ───────────────────────────────────────────────────


def test_openrouter_completion_no_key(monkeypatch):
    monkeypatch.setattr("nexus.services.voice.get_settings", lambda: _FakeVoiceSettings(""))
    from nexus.services.voice import _openrouter_completion

    assert _openrouter_completion("test prompt") is None


def test_openrouter_completion_success():
    """Use httpx.post directly since it's imported inside the function."""
    with patch("nexus.services.voice.get_settings", lambda: _FakeVoiceSettings("sk-or-test")):
        with patch("httpx.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "choices": [{"message": {"content": "Hello response"}}]
            }
            from nexus.services.voice import _openrouter_completion

            result = _openrouter_completion("test prompt")
    assert result == "Hello response"


def test_openrouter_completion_api_error():
    with patch("nexus.services.voice.get_settings", lambda: _FakeVoiceSettings("sk-or-test")):
        with patch("httpx.post") as mock_post:
            mock_post.return_value.status_code = 500
            mock_post.return_value.text = "error"
            from nexus.services.voice import _openrouter_completion

            result = _openrouter_completion("test prompt")
    assert result is None


def test_openrouter_completion_exception():
    with patch("nexus.services.voice.get_settings", lambda: _FakeVoiceSettings("sk-or-test")):
        with patch("httpx.post", side_effect=Exception("timeout")):
            from nexus.services.voice import _openrouter_completion

            result = _openrouter_completion("test prompt")
    assert result is None


# ── speak_text (TTS) ────────────────────────────────────────────────────────


def test_speak_text_returns_none_without_api_key(monkeypatch):
    monkeypatch.setattr("nexus.services.voice._get_openai_key", lambda: "")
    assert speak_text("hello") is None


def test_speak_text_calls_openai():
    with patch("httpx.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.content = b"mp3data"
        with patch("nexus.services.voice._get_openai_key", return_value="sk-test"):
            result = speak_text("hello world", voice="nova")
            assert result == b"mp3data"


def test_speak_text_returns_none_on_api_error():
    with patch("httpx.post") as mock_post:
        mock_post.return_value.status_code = 500
        mock_post.return_value.content = b""
        with patch("nexus.services.voice._get_openai_key", return_value="sk-test"):
            result = speak_text("hello")
            assert result is None


def test_speak_text_custom_voice():
    with patch("httpx.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.content = b"data"
        with patch("nexus.services.voice._get_openai_key", return_value="sk-test"):
            result = speak_text("hello", voice="shimmer")
            assert result == b"data"


def test_speak_text_exception():
    with patch("nexus.services.voice._get_openai_key", return_value="sk-test"):
        with patch("httpx.post", side_effect=Exception("timeout")):
            result = speak_text("hello")
            assert result is None


# ── play_audio ───────────────────────────────────────────────────────────────


@patch("nexus.services.voice.subprocess.run")
def test_play_audio_ffplay_success(mock_run):
    result = play_audio(b"audio_data")
    assert result is True
    assert "ffplay" in mock_run.call_args[0][0]


@patch("nexus.services.voice.subprocess.run")
def test_play_audio_aplay_fallback(mock_run):
    """First call (ffplay) fails, second (aplay) succeeds."""
    mock_run.side_effect = [FileNotFoundError, MagicMock()]
    result = play_audio(b"audio_data")
    assert result is True
    assert mock_run.call_count == 2


@patch("nexus.services.voice.subprocess.run", side_effect=FileNotFoundError)
def test_play_audio_both_fail(mock_run):
    result = play_audio(b"audio_data")
    assert result is False


# ── API endpoint tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_transcribe_endpoint_with_text(client):
    """Test text-only transcription (endpoint requires auth)."""
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


# ── Fixtures ─────────────────────────────────────────────────────────────────


class _FakeVoiceSettings:
    def __init__(self, openrouter_key=""):
        self.openrouter_api_key = openrouter_key
        self.llm_default_model = "anthropic/claude-3-5-sonnet"
