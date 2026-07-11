"""Tests for notes, wiki-links, projects, and search."""

import pytest
from httpx import AsyncClient


async def _register_and_auth(
    client: AsyncClient, email: str, password: str = "TestPass123!"
) -> dict[str, str]:
    resp = await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_create_and_list_notes(client: AsyncClient):
    headers = await _register_and_auth(client, "note-create@example.com")

    resp = await client.post(
        "/api/v1/research/notes",
        json={"title": "My First Note", "content": "Hello world.", "tags": ["personal"]},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["title"] == "My First Note"
    assert data["tags"] == ["personal"]

    resp = await client.get("/api/v1/research/notes", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_create_note_requires_auth(client: AsyncClient):
    resp = await client.post("/api/v1/research/notes", json={"title": "X", "content": "Y"})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_wiki_links_resolved(client: AsyncClient):
    headers = await _register_and_auth(client, "note-links@example.com")

    # Create two notes
    resp = await client.post(
        "/api/v1/research/notes",
        json={"title": "Target Note", "content": "I am the target."},
        headers=headers,
    )
    assert resp.status_code == 201

    resp = await client.post(
        "/api/v1/research/notes",
        json={"title": "Source Note", "content": "See [[Target Note]] for details."},
        headers=headers,
    )
    assert resp.status_code == 201
    source_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/research/notes/{source_id}/backlinks", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["outgoing"]) == 1
    assert data["outgoing"][0]["title"] == "Target Note"


@pytest.mark.asyncio
async def test_wiki_link_to_self_ignored(client: AsyncClient):
    headers = await _register_and_auth(client, "note-self@example.com")

    resp = await client.post(
        "/api/v1/research/notes",
        json={"title": "Self Ref", "content": "I link to [[Self Ref]]"},
        headers=headers,
    )
    assert resp.status_code == 201
    note_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/research/notes/{note_id}/backlinks", headers=headers)
    data = resp.json()
    assert len(data["outgoing"]) == 0


@pytest.mark.asyncio
async def test_search_fulltext_fallback(client: AsyncClient):
    headers = await _register_and_auth(client, "note-search@example.com")

    await client.post(
        "/api/v1/research/notes",
        json={"title": "Investment Strategy", "content": "Diversify across asset classes."},
        headers=headers,
    )
    await client.post(
        "/api/v1/research/notes",
        json={"title": "Grocery List", "content": "Milk, eggs, bread."},
        headers=headers,
    )

    resp = await client.post(
        "/api/v1/research/notes/search",
        json={"query": "investment"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    results = resp.json()
    assert len(results) >= 1
    assert results[0]["method"] == "fulltext"  # no embedding provider
    assert "Investment" in results[0]["title"]


@pytest.mark.asyncio
async def test_search_no_results(client: AsyncClient):
    headers = await _register_and_auth(client, "note-empty@example.com")

    resp = await client.post(
        "/api/v1/research/notes/search",
        json={"query": "nonexistent"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_update_note_re_embeds(client: AsyncClient):
    headers = await _register_and_auth(client, "note-update@example.com")

    resp = await client.post(
        "/api/v1/research/notes",
        json={"title": "Original", "content": "Before"},
        headers=headers,
    )
    note_id = resp.json()["id"]

    resp = await client.put(
        f"/api/v1/research/notes/{note_id}",
        json={"content": "After update"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["content"] == "After update"


@pytest.mark.asyncio
async def test_delete_note(client: AsyncClient):
    headers = await _register_and_auth(client, "note-delete@example.com")

    resp = await client.post(
        "/api/v1/research/notes",
        json={"title": "To Delete", "content": "Gone"},
        headers=headers,
    )
    note_id = resp.json()["id"]

    resp = await client.delete(f"/api/v1/research/notes/{note_id}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/research/notes/{note_id}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_projects_crud(client: AsyncClient):
    headers = await _register_and_auth(client, "note-proj@example.com")

    resp = await client.post(
        "/api/v1/research/projects",
        json={"name": "Investing", "description": "All things portfolio"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    proj = resp.json()
    assert proj["name"] == "Investing"

    resp = await client.get("/api/v1/research/projects", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_filter_by_tag(client: AsyncClient):
    headers = await _register_and_auth(client, "note-tag@example.com")

    await client.post(
        "/api/v1/research/notes",
        json={"title": "T1", "content": "...", "tags": ["python"]},
        headers=headers,
    )
    await client.post(
        "/api/v1/research/notes",
        json={"title": "T2", "content": "...", "tags": ["rust"]},
        headers=headers,
    )

    resp = await client.get("/api/v1/research/notes?tag=python", headers=headers)
    assert resp.status_code == 200
    results = resp.json()
    assert all("python" in (n.get("tags") or []) for n in results)


# ── Wiki-link extraction (pure unit) ────────────────────────────────────


def test_extract_wikilinks_basic():
    from nexus.utils.wikilinks import extract_wikilinks

    content = "See [[Investment Strategy]] and [[Tax Planning]]"
    assert extract_wikilinks(content) == ["Investment Strategy", "Tax Planning"]


def test_extract_wikilinks_deduplicates():
    from nexus.utils.wikilinks import extract_wikilinks

    content = "A [[Foo]], B [[Foo]]"
    assert extract_wikilinks(content) == ["Foo"]


def test_extract_wikilinks_empty():
    from nexus.utils.wikilinks import extract_wikilinks

    assert extract_wikilinks("") == []
    assert extract_wikilinks("No links here") == []
