"""Tests for notification bundling, priorities, and preferences."""

import pytest
from httpx import AsyncClient

from nexus.models.notification import Notification
from nexus.services.notifications import _compose_digest


async def _register_and_auth(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post("/api/v1/auth/register", json={"email": email, "password": "pw"})
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── Compose digest (pure) ─────────────────────────────────────────────────


def test_compose_digest_single():
    n = Notification(user_id=1, title="Alert", body="Something happened")
    msg = _compose_digest([n])
    assert "1 update" in msg
    assert "Alert" in msg
    assert "Something happened" in msg


def test_compose_digest_multiple():
    notifs = [
        Notification(user_id=1, title="First", body="A"),
        Notification(user_id=1, title="Second", body="B"),
        Notification(user_id=1, title="Third"),
    ]
    msg = _compose_digest(notifs)
    assert "3 updates" in msg
    assert "1. First" in msg
    assert "2. Second" in msg
    assert "3. Third" in msg


# ── Endpoint flow ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_normal_notification_stays_pending(client: AsyncClient):
    headers = await _register_and_auth(client, "notif-normal@example.com")
    resp = await client.post(
        "/api/v1/notifications",
        json={"title": "Weekly report ready", "priority": "normal"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["priority"] == "normal"
    assert data["status"] == "pending"  # bundled later, not sent immediately


@pytest.mark.asyncio
async def test_urgent_notification_attempts_immediate_delivery(client: AsyncClient):
    headers = await _register_and_auth(client, "notif-urgent@example.com")
    resp = await client.post(
        "/api/v1/notifications",
        json={"title": "Budget exceeded!", "priority": "urgent"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    # In tests, telegram delivery is skipped -> marked 'failed' (attempted, not pending)
    assert resp.json()["status"] == "failed"


@pytest.mark.asyncio
async def test_invalid_priority_defaults_to_normal(client: AsyncClient):
    headers = await _register_and_auth(client, "notif-invalid@example.com")
    resp = await client.post(
        "/api/v1/notifications",
        json={"title": "Test", "priority": "bogus"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["priority"] == "normal"


@pytest.mark.asyncio
async def test_digest_bundles_pending_notifications(client: AsyncClient):
    headers = await _register_and_auth(client, "notif-digest@example.com")

    # Enqueue 3 normal notifications
    for i in range(3):
        await client.post(
            "/api/v1/notifications",
            json={"title": f"Update {i}", "priority": "normal"},
            headers=headers,
        )

    # Trigger digest for normal priority
    resp = await client.post("/api/v1/notifications/digest?priority=normal", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["bundled"] == 3
    # Delivery fails in tests (no telegram), so sent is False
    assert data["sent"] is False


@pytest.mark.asyncio
async def test_list_notifications_filter(client: AsyncClient):
    headers = await _register_and_auth(client, "notif-list@example.com")
    await client.post(
        "/api/v1/notifications",
        json={"title": "Pending one", "priority": "normal"},
        headers=headers,
    )
    resp = await client.get("/api/v1/notifications?status_filter=pending", headers=headers)
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    assert all(n["status"] == "pending" for n in results)


@pytest.mark.asyncio
async def test_preferences_defaults_and_update(client: AsyncClient):
    headers = await _register_and_auth(client, "notif-prefs@example.com")

    # Defaults created on first access
    resp = await client.get("/api/v1/notifications/preferences", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["digest_hour"] == 9
    assert resp.json()["urgent_immediate"] is True

    # Update
    resp = await client.put(
        "/api/v1/notifications/preferences",
        json={"digest_hour": 18, "telegram_chat_id": "12345"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["digest_hour"] == 18
    assert resp.json()["telegram_chat_id"] == "12345"


@pytest.mark.asyncio
async def test_notifications_require_auth(client: AsyncClient):
    resp = await client.get("/api/v1/notifications")
    assert resp.status_code in (401, 403)
