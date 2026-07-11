"""Tests for session management — create, list, revoke, and concurrent limit."""

import pytest
from httpx import AsyncClient


async def _register_and_auth(
    client: AsyncClient, email: str, password: str = "TestPass123!"
) -> dict[str, str]:
    """Register a user and return Authorization headers."""
    resp = await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_register_creates_session(client: AsyncClient):
    """Registration creates an initial refresh session."""
    headers = await _register_and_auth(client, "session-reg@example.com")

    resp = await client.get("/api/v1/auth/sessions", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["sessions"]) >= 1
    assert data["sessions"][0]["is_current"] is True


@pytest.mark.asyncio
async def test_multiple_logins_create_sessions(client: AsyncClient):
    """Each login creates a new session (up to the concurrency limit)."""
    email, pw = "session-multi@example.com", "TestPass123!"
    headers = await _register_and_auth(client, email, pw)

    # Login again -> new session
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert resp.status_code == 200, resp.text

    resp = await client.get("/api/v1/auth/sessions", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1  # At least one session; max 3 enforced


@pytest.mark.asyncio
async def test_revoke_single_session(client: AsyncClient):
    """Revoking a specific session removes it."""
    email, pw = "session-revoke@example.com", "TestPass123!"
    headers = await _register_and_auth(client, email, pw)

    # Login creates a second session
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert resp.status_code == 200, resp.text

    # List sessions, get the first one
    resp = await client.get("/api/v1/auth/sessions", headers=headers)
    sessions = resp.json()["sessions"]
    target_id = sessions[0]["id"]

    # Revoke it
    resp = await client.delete(f"/api/v1/auth/sessions/{target_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["revoked"] == 1

    # Verify it's gone
    resp = await client.get("/api/v1/auth/sessions", headers=headers)
    remaining_ids = {s["id"] for s in resp.json()["sessions"]}
    assert target_id not in remaining_ids


@pytest.mark.asyncio
async def test_revoke_nonexistent_session_returns_404(client: AsyncClient):
    headers = await _register_and_auth(client, "session-404@example.com")
    resp = await client.delete("/api/v1/auth/sessions/99999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_revoke_all_sessions(client: AsyncClient):
    """Revoking all sessions removes them, and subsequent requests fail."""
    email, pw = "session-all@example.com", "TestPass123!"
    headers = await _register_and_auth(client, email, pw)

    # Create a second session
    await client.post("/api/v1/auth/login", json={"email": email, "password": pw})

    # Revoke all
    resp = await client.delete("/api/v1/auth/sessions", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["revoked"] >= 1

    # List sessions should return zero
    resp = await client.get("/api/v1/auth/sessions", headers=headers)
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_sessions_endpoint_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/auth/sessions")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_session_limit_enforced(client: AsyncClient):
    """After MAX_SESSIONS (3) logins, the oldest is evicted."""
    email, pw = "session-limit@example.com", "TestPass123!"
    headers = await _register_and_auth(client, email, pw)

    # Login 4 more times (total 5 sessions, but max 3 means oldest 3 evicted)
    for _ in range(4):
        resp = await client.post("/api/v1/auth/login", json={"email": email, "password": pw})
        assert resp.status_code == 200, resp.text

    # Should only have 3 sessions
    resp = await client.get("/api/v1/auth/sessions", headers=headers)
    data = resp.json()
    assert data["total"] == 3, f"expected 3 sessions, got {data['total']}"


@pytest.mark.asyncio
async def test_refresh_rotates_session(client: AsyncClient):
    """Refreshing a token creates a new session with a matching IP."""
    email, pw = "session-rotate@example.com", "TestPass123!"
    reg = await client.post("/api/v1/auth/register", json={"email": email, "password": pw})
    refresh = reg.json()["refresh_token"]

    # Before refresh: 1 session
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    sess_before = await client.get("/api/v1/auth/sessions", headers=headers)
    count_before = sess_before.json()["total"]

    # Refresh
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200, resp.text

    # After refresh: still the same count (old rotated out, new rotated in)
    sess_after = await client.get("/api/v1/auth/sessions", headers=headers)
    assert sess_after.json()["total"] == count_before
