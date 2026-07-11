"""Tests for audit logging — creation, immutability, and read endpoint."""

import pytest
from httpx import AsyncClient

from nexus.services.audit import log as audit_log

# ── Audit log creation (endpoint integration) ───────────────────────────


@pytest.mark.asyncio
async def test_register_creates_audit_log(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register", json={"email": "audit-reg@example.com", "password": "pw"}
    )
    assert resp.status_code == 201, resp.text

    # Verify an audit entry was created
    token = resp.json()["access_token"]
    audit_resp = await client.get(
        "/api/v1/audit?action=register",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert audit_resp.status_code == 200
    entries = audit_resp.json()
    assert len(entries) >= 1
    assert entries[0]["action"] == "register"
    assert entries[0]["resource_type"] == "user"


@pytest.mark.asyncio
async def test_login_creates_audit_log(client: AsyncClient):
    # Register
    resp = await client.post(
        "/api/v1/auth/register", json={"email": "audit-login@example.com", "password": "pw"}
    )
    token = resp.json()["access_token"]

    # Login creates a "login" audit entry
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "audit-login@example.com", "password": "pw"}
    )
    assert resp.status_code == 200, resp.text

    audit_resp = await client.get(
        "/api/v1/audit?action=login",
        headers={"Authorization": f"Bearer {token}"},
    )
    entries = audit_resp.json()
    assert any(e["action"] == "login" for e in entries)


@pytest.mark.asyncio
async def test_login_failed_creates_audit_log(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong"}
    )
    assert resp.status_code == 401

    # register a user so we can auth to read the audit log
    reg = await client.post(
        "/api/v1/auth/register", json={"email": "audit-reader@example.com", "password": "pw"}
    )
    token = reg.json()["access_token"]

    audit_resp = await client.get(
        "/api/v1/audit?action=login_failed",
        headers={"Authorization": f"Bearer {token}"},
    )
    entries = audit_resp.json()
    assert any(e["action"] == "login_failed" for e in entries)


@pytest.mark.asyncio
async def test_mfa_events_are_audited(client: AsyncClient):
    """enroll, verify (activate), and disable all generate audit entries."""
    # Register
    reg = await client.post(
        "/api/v1/auth/register", json={"email": "audit-mfa@example.com", "password": "pw"}
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    import pyotp

    # Enroll
    resp = await client.post("/api/v1/auth/mfa/enroll", headers=headers)
    secret = resp.json()["secret"]

    # Verify
    await client.post(
        "/api/v1/auth/mfa/verify",
        headers=headers,
        json={"code": pyotp.TOTP(secret).now()},
    )

    # Disable
    await client.post("/api/v1/auth/mfa/disable", headers=headers, json={"password": "pw"})

    # Check audit trail
    audit_resp = await client.get("/api/v1/audit", headers=headers)
    entries = audit_resp.json()
    actions = {e["action"] for e in entries}
    assert "mfa_enroll" in actions
    assert "mfa_activate" in actions
    assert "mfa_disable" in actions


# ── Read endpoint authorization ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_endpoint_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/audit")
    assert resp.status_code in (401, 403)


# ── Filtering ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_action_filter(client: AsyncClient):
    reg = await client.post(
        "/api/v1/auth/register", json={"email": "audit-f@example.com", "password": "pw"}
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Only "register" entries
    resp = await client.get("/api/v1/audit?action=register", headers=headers)
    entries = resp.json()
    assert len(entries) >= 1
    assert all(e["action"] == "register" for e in entries)

    # Non-existent action
    resp = await client.get("/api/v1/audit?action=nonexistent", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


# ── Immutability ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_log_cannot_be_updated(db_session):
    entry = await audit_log(db_session, user_id=None, action="test_action", resource_type="test")
    await db_session.flush()

    with pytest.raises(ValueError, match="immutable"):
        entry.action = "hacked"
        await db_session.flush()


@pytest.mark.asyncio
async def test_audit_log_cannot_be_deleted(db_session):
    entry = await audit_log(db_session, user_id=None, action="test_action", resource_type="test")
    await db_session.flush()

    with pytest.raises(ValueError, match="immutable"):
        await db_session.delete(entry)
        await db_session.flush()
