"""Tests for git-backed note versioning."""

import tempfile
from pathlib import Path

import pytest
from fastapi import status

import nexus.utils.versioning as versioning
from nexus.utils.versioning import (
    _note_file,
    get_note_history,
    init_repo,
    restore_note,
    save_note_version,
)


@pytest.fixture(autouse=True)
def temp_notes_repo(monkeypatch):
    """Redirect notes repo to a temp directory for isolated testing."""
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr(versioning, "NOTES_REPO_DIR", Path(tmp) / "notes")
        yield


# ── Unit tests ───────────────────────────────────────────────────────────────


def test_init_repo_creates_git_dir(temp_notes_repo):
    assert init_repo() is True
    assert (versioning.NOTES_REPO_DIR / ".git").is_dir()


def test_init_repo_idempotent(temp_notes_repo):
    assert init_repo() is True
    assert init_repo() is True


def test_save_note_version_creates_file_and_commits(temp_notes_repo):
    init_repo()
    assert save_note_version(1, "Test Note", "# Hello\n\nWorld") is True

    file_path = _note_file(1)
    assert file_path.exists()
    content = file_path.read_text()
    assert "title: Test Note" in content
    assert "# Hello" in content


def test_get_note_history_returns_entries(temp_notes_repo):
    init_repo()
    save_note_version(42, "First", "content v1")
    save_note_version(42, "Second", "content v2")

    history = get_note_history(42)
    assert len(history) >= 2
    assert history[0]["message"] == "Update: Second (note #42)"


def test_get_note_history_empty_for_new_note(temp_notes_repo):
    init_repo()
    history = get_note_history(999)
    assert history == []


def test_restore_note_returns_previous_version(temp_notes_repo):
    init_repo()
    save_note_version(7, "Versioned", "original content")
    save_note_version(7, "Versioned", "updated content")

    history = get_note_history(7)
    first_commit = history[-1]["full_commit"]

    restored = restore_note(7, first_commit)
    assert restored is not None
    assert "original content" in restored


def test_restore_note_returns_none_for_bad_commit(temp_notes_repo):
    init_repo()
    save_note_version(7, "Test", "content")

    restored = restore_note(7, "deadbeef")
    assert restored is None


def test_restore_note_returns_none_for_missing_note(temp_notes_repo):
    init_repo()
    restored = restore_note(999, "deadbeef")
    assert restored is None


# ── API Endpoint tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_history_endpoint_requires_auth(client):
    response = await client.get("/api/v1/research/notes/1/history")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_restore_endpoint_requires_auth(client):
    response = await client.post(
        "/api/v1/research/notes/1/restore", json={"commit": "abc1234"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
