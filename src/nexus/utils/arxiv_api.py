"""arXiv API client — search academic papers by keyword, author, or category.

Uses the free arXiv API (no auth required). Returns structured paper data.
"""

from __future__ import annotations

import logging
from xml.etree import ElementTree

import httpx

logger = logging.getLogger(__name__)

ARXIV_API = "https://export.arxiv.org/api/query"

# arXiv category codes for common domains
CATEGORIES = {
    "cs": "Computer Science",
    "cs.AI": "Artificial Intelligence",
    "cs.LG": "Machine Learning",
    "cs.CL": "Computation and Language",
    "q-fin": "Quantitative Finance",
    "q-fin.PM": "Portfolio Management",
    "stat": "Statistics",
    "math": "Mathematics",
    "physics": "Physics",
}

# Namespace map for the Atom XML
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


async def search(
    query: str,
    *,
    max_results: int = 10,
    category: str | None = None,
) -> list[dict]:
    """Search arXiv and return structured paper metadata.

    Returns a list of dicts with keys: ``title``, ``summary``, ``authors``,
    ``published``, ``pdf_url``, ``arxiv_id``, ``primary_category``.
    """
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
    }
    if category:
        params["search_query"] = f"cat:{category} AND all:{query}"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20)) as client:
            resp = await client.get(ARXIV_API, params=params)
            resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.error("arxiv_search_failed %s: %s", query, exc)
        return []

    return _parse(resp.text)


def _parse(xml_text: str) -> list[dict]:
    """Parse arXiv Atom XML into a list of paper dicts."""
    root = ElementTree.fromstring(xml_text)
    papers: list[dict] = []
    for entry in root.findall("atom:entry", NS):
        papers.append(
            {
                "title": _text(entry, "atom:title"),
                "summary": _text(entry, "atom:summary")[:500],
                "authors": [_text(a, "atom:name") for a in entry.findall("atom:author", NS)],
                "published": _text(entry, "atom:published"),
                "arxiv_id": _id_from_url(_text(entry, "atom:id")),
                "pdf_url": _pdf_url(_id_from_url(_text(entry, "atom:id"))),
                "primary_category": _text(entry, "arxiv:primary_category", attr="term"),
            }
        )
    return papers


def _text(parent: ElementTree.Element, tag: str, attr: str | None = None) -> str:
    el = parent.find(tag, NS)
    if el is None:
        return ""
    if attr:
        return el.get(attr, "")
    return (el.text or "").strip().replace("\n", " ")


def _id_from_url(url: str) -> str:
    return url.rsplit("/", 1)[-1] if url else ""


def _pdf_url(arxiv_id: str) -> str:
    return f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else ""
