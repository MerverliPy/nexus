"""Wiki-link parsing for notes: extract ``[[Note Title]]`` references."""

from __future__ import annotations

import re

_WIKILINK_RE = re.compile(r"\[\[([^\[\]]+?)\]\]")


def extract_wikilinks(content: str) -> list[str]:
    """Return the list of unique ``[[title]]`` targets found in ``content``.

    Titles are stripped of surrounding whitespace; duplicates are removed while
    preserving first-seen order.
    """
    seen: set[str] = set()
    result: list[str] = []
    for match in _WIKILINK_RE.findall(content or ""):
        title = match.strip()
        if title and title.lower() not in seen:
            seen.add(title.lower())
            result.append(title)
    return result
