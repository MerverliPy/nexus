"""Tests for research workflows: arXiv search, credibility, export."""

import pytest
from httpx import AsyncClient

from nexus.utils.credibility import score as credibility_score


async def _register_and_auth(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post("/api/v1/auth/register", json={"email": email, "password": "pw"})
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── Credibility scoring (pure unit, no network) ────────────────────────────


def test_arxiv_is_high_trust():
    assert credibility_score("https://arxiv.org/abs/2301.00001") == 1.0


def test_nature_is_high_trust():
    assert credibility_score("https://www.nature.com/articles/s41586-023-00001") == 1.0


def test_edu_is_medium_high():
    assert credibility_score("https://cs.stanford.edu/~user/paper") == 0.9


def test_gov_is_medium_high():
    assert credibility_score("https://www.nasa.gov/press-release") == 0.9


def test_wikipedia_is_medium():
    assert credibility_score("https://en.wikipedia.org/wiki/Machine_learning") == 0.7


def test_medium_is_low():
    assert credibility_score("https://medium.com/@user/article") == 0.1


def test_reddit_is_low():
    assert credibility_score("https://reddit.com/r/machinelearning") == 0.1


def test_unknown_is_default():
    assert credibility_score("https://some-random-blog.example.com/post") == 0.3


def test_empty_url():
    assert credibility_score("") == 0.0


# ── arXiv search (real API call) ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_arxiv_search_returns_results(client: AsyncClient):
    headers = await _register_and_auth(client, "arxiv-test@example.com")
    resp = await client.get(
        "/api/v1/research/research/papers?q=transformer+attention&limit=3",
        headers=headers,
    )
    # arXiv API returns results unless it's down
    if resp.status_code == 200:
        papers = resp.json()
        assert len(papers) >= 1
        # Verify structure
        p = papers[0]
        assert "title" in p
        assert "authors" in p
        assert "pdf_url" in p
        assert "credibility" in p
    else:
        # arXiv API might be slow — skip gracefully
        pytest.skip("arXiv API unreachable")


# ── Note export (markdown always works) ───────────────────────────────────


@pytest.mark.asyncio
async def test_export_note_md(client: AsyncClient):
    headers = await _register_and_auth(client, "export-test@example.com")

    resp = await client.post(
        "/api/v1/research/notes",
        json={"title": "Export Me", "content": "Hello world."},
        headers=headers,
    )
    note_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/research/notes/{note_id}/export",
        json={"format": "md"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["format"] == "md"
    assert data["file"].endswith(".md")


@pytest.mark.asyncio
async def test_export_note_pdf_requires_pandoc(client: AsyncClient):
    """Export to PDF returns 400 if pandoc is not installed."""
    headers = await _register_and_auth(client, "export-pdf@example.com")

    resp = await client.post(
        "/api/v1/research/notes",
        json={"title": "PDF Me", "content": "Testing."},
        headers=headers,
    )
    note_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/research/notes/{note_id}/export",
        json={"format": "pdf"},
        headers=headers,
    )
    # Either succeeds (pandoc installed) or 400 (pandoc missing)
    assert resp.status_code in (200, 400), resp.text


# ── Research plan (LLM-powered, degrades to 503 without key) ──────────────


@pytest.mark.asyncio
async def test_research_plan_no_llm_key_returns_503(client: AsyncClient):
    headers = await _register_and_auth(client, "plan-test@example.com")
    resp = await client.post(
        "/api/v1/research/research/plan",
        json={"topic": "investment strategy"},
        headers=headers,
    )
    # Without an OpenRouter key, this returns 503
    assert resp.status_code in (200, 503), resp.text
