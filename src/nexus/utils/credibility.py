"""Source credibility scoring — domain whitelist and heuristic ranking.

No LLM required; purely rules-based. Returns a 0.0-1.0 score.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

# High-trust academic / institutional domains
_HIGH_TRUST: set[str] = {
    "arxiv.org",
    "nature.com",
    "science.org",
    "pnas.org",
    "nejm.org",
    "the lancet.com",
    "cell.com",
    "ieee.org",
    "acm.org",
    "springer.com",
    "elsevier.com",
    "wiley.com",
    "jstor.org",
    "scholar.google.com",
    "semanticscholar.org",
    "pubmed.ncbi.nlm.nih.gov",
}

# Government & education
_GOV_EDU: frozenset[str] = frozenset({".gov", ".edu", ".mil"})

# Known low-credibility domains
_LOW_TRUST: set[str] = {
    "medium.com",
    "blogspot.com",
    "wordpress.com",
    "reddit.com",
    "twitter.com",
    "facebook.com",
}

# Wikipedia is treated as mid-credibility (good starting point, not authoritative)
_WIKIPEDIA_DOMAINS: set[str] = {"wikipedia.org", "en.wikipedia.org"}

# Conference proceedings and preprints — credible but not peer-reviewed
_PREPRINT_DOMAINS: set[str] = {"openreview.net", "ssrn.com", "researchgate.net"}


def score(url: str) -> float:
    """Return a 0.0–1.0 credibility score for a URL.

    Scoring tiers:
      - 1.0  high-trust academic/institutional domain
      - 0.9  .gov / .edu / .mil
      - 0.7  Wikipedia
      - 0.5  preprint / conference sites
      - 0.3  unknown domains
      - 0.1  known low-credibility platforms (Medium, Reddit, etc.)
    """
    if not url:
        return 0.0

    try:
        domain = _domain(url).lower()
    except Exception:  # noqa: BLE001
        return 0.0

    if not domain:
        return 0.0

    # Strip leading "www."
    domain = re.sub(r"^www\.", "", domain)

    if domain in _HIGH_TRUST:
        return 1.0

    if any(domain.endswith(tld) for tld in _GOV_EDU):
        return 0.9

    if domain in _WIKIPEDIA_DOMAINS:
        return 0.7

    if domain in _PREPRINT_DOMAINS:
        return 0.5

    if domain in _LOW_TRUST:
        return 0.1

    return 0.3


def _domain(url: str) -> str:
    """Extract the bare hostname from a URL, stripping www."""
    parsed = urlparse(url if "://" in url else f"http://{url}")
    return parsed.hostname or ""
