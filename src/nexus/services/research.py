"""Research workflow service: plan generation, arXiv search, and export."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import structlog

logger = structlog.get_logger()

# ── Research plan generation ───────────────────────────────────────────────


async def generate_plan(
    topic: str, *, openrouter_api_key: str, default_model: str
) -> list[str] | None:
    """Generate 5-10 research questions for a topic using OpenRouter.

    Returns None if the LLM call fails (no key, network down, etc.).
    """
    from nexus.utils.resilience import resilient_request

    try:
        resp = await resilient_request(
            "POST",
            "https://openrouter.ai/api/v1/chat/completions",
            json={
                "model": default_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a research assistant. Generate 5-10 specific, "
                            "answerable research questions for the given topic. "
                            "Return only a JSON array of strings, no explanation."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Topic: {topic}",
                    },
                ],
                "max_tokens": 500,
                "temperature": 0.7,
            },
            headers={
                "Authorization": f"Bearer {openrouter_api_key}",
                "Content-Type": "application/json",
            },
        )
    except Exception as exc:  # noqa: BLE001 - never let a provider error 500
        logger.warning("generate_plan_error", topic=topic, error=str(exc))
        return None

    if resp is None or not openrouter_api_key:
        logger.warning("generate_plan_failed", topic=topic, reason="no_provider")
        return None

    try:
        body = resp.json()
        text = body["choices"][0]["message"]["content"]
        return json.loads(text)
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.error("generate_plan_parse_error", error=str(exc))
        return None


# ── arXiv search integration ────────────────────────────────────────────────


async def search_arxiv(query: str, max_results: int = 10) -> list[dict]:
    """Search arXiv for academic papers."""
    from nexus.utils.arxiv_api import search as arxiv_search

    return await arxiv_search(query, max_results=max_results)


# ── Export pipeline ─────────────────────────────────────────────────────────


EXPORT_DIR = Path.home() / ".nexus" / "exports"


def export_note(note: dict, fmt: str = "md") -> dict | None:
    """Export a note to the given format.

    Supported formats:
      - ``md`` — plain markdown (always available)
      - ``pdf`` — via pandoc (if installed)
      - ``html`` — via pandoc (if installed)
      - ``docx`` — via pandoc (if installed)

    Returns ``{"file": path, "format": fmt}`` or ``None`` on failure.
    """
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    safe = note.get("title", "note").replace("/", "_").replace(" ", "_")[:80]
    md_content = _render_markdown(note)

    if fmt == "md":
        path = EXPORT_DIR / f"{safe}.md"
        path.write_text(md_content)
        return {"file": str(path), "format": "md"}

    # Everything else requires pandoc
    if not _has_pandoc():
        logger.warning("pandoc_not_installed")
        return None

    ext_map = {"pdf": "pdf", "html": "html", "docx": "docx"}
    ext = ext_map.get(fmt, fmt)

    # Write markdown to a temp file for pandoc
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tmp:
        tmp.write(md_content)
        tmp_path = tmp.name

    try:
        out_path = EXPORT_DIR / f"{safe}.{ext}"
        result = subprocess.run(
            ["pandoc", tmp_path, "-o", str(out_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.error("pandoc_failed", stderr=result.stderr[-200:])
            return None
        return {"file": str(out_path), "format": fmt}
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.error("export_failed", error=str(exc))
        return None
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _has_pandoc() -> bool:
    return subprocess.run(["which", "pandoc"], capture_output=True).returncode == 0


def _render_markdown(note: dict) -> str:
    """Render a note dict into a markdown document."""
    lines = [
        f"# {note.get('title', 'Untitled')}",
        "",
        f"*Tags: {', '.join(note.get('tags') or ['none'])}*",
        f"*Source: {note.get('source_url') or 'none'}*",
        f"*Source type: {note.get('source_type') or 'none'}*",
        "",
        note.get("content", ""),
    ]
    return "\n".join(lines)


# ── Multi-source synthesis ──────────────────────────────────────────────


async def synthesize_sources(
    note_ids: list[int],
    user_id: int,
    db,
    *,
    openrouter_api_key: str,
    default_model: str,
) -> dict | None:
    """Synthesize findings from multiple notes using LLM.

    Returns a dict with:
      - title: suggested title
      - content: synthesized markdown
      - key_findings: list[str]
      - contradictions: list[str]
      - insights: list[str]
      - open_questions: list[str]
      - sources: list of source metadata
    Or None if synthesis fails.
    """
    from sqlalchemy import select

    from nexus.models.research import Note
    from nexus.utils.credibility import score as credibility_score
    from nexus.utils.resilience import resilient_request

    # Fetch notes
    result = await db.execute(
        select(Note).where(Note.id.in_(note_ids), Note.user_id == user_id)
    )
    notes = result.scalars().all()

    if len(notes) < 2:
        return None

    # Build source list sorted by credibility (highest first)
    sources = []
    for n in notes:
        cred = credibility_score(n.source_url or "")
        sources.append(
            {
                "id": n.id,
                "title": n.title,
                "url": n.source_url or "",
                "content": n.content[:3000],
                "credibility": cred,
            }
        )
    sources.sort(key=lambda s: s["credibility"], reverse=True)

    # Build LLM prompt
    source_text = "\n\n---\n\n".join(
        f"Source {i+1}: {s['title']}\nURL: {s['url']}\nCredibility: {s['credibility']}\n\n{s['content']}"
        for i, s in enumerate(sources)
    )

    system = (
        "You are a research synthesizer. Analyze the provided sources and produce "
        "a structured synthesis. Return ONLY valid JSON (no markdown wrapping) with keys:\n"
        '- "title": a concise title summarizing the synthesis\n'
        '- "key_findings": list of 3-5 key findings\n'
        '- "contradictions": list of any conflicting claims between sources\n'
        '- "insights": list of 2-3 novel insights from connecting the sources\n'
        '- "open_questions": list of 2-3 questions that remain unanswered\n'
    )

    try:
        resp = await resilient_request(
            "POST",
            "https://openrouter.ai/api/v1/chat/completions",
            json={
                "model": default_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"Synthesize these sources:\n\n{source_text}"},
                ],
                "max_tokens": 1500,
                "temperature": 0.5,
            },
            headers={
                "Authorization": f"Bearer {openrouter_api_key}",
                "Content-Type": "application/json",
            },
        )
    except Exception:
        return None

    if resp is None or not openrouter_api_key:
        return None

    try:
        body = resp.json()
        text = body["choices"][0]["message"]["content"]
        synthesis = json.loads(text)
    except (json.JSONDecodeError, KeyError, IndexError):
        return None

    # Build full markdown content
    md = f"# {synthesis['title']}\n\n"
    md += "## Key Findings\n\n"
    for f in synthesis.get("key_findings", []):
        md += f"- {f}\n"
    md += "\n## Contradictions\n\n"
    for c in synthesis.get("contradictions", []):
        md += f"- {c}\n"
    md += "\n## Insights\n\n"
    for i in synthesis.get("insights", []):
        md += f"- {i}\n"
    md += "\n## Open Questions\n\n"
    for q in synthesis.get("open_questions", []):
        md += f"- {q}\n"
    md += "\n## Sources\n\n"
    for s in sources:
        md += f"- [{s['title']}]({s['url']}) (credibility: {s['credibility']})\n"

    return {
        **synthesis,
        "content": md,
        "sources": [
            {"id": s["id"], "title": s["title"], "url": s["url"], "credibility": s["credibility"]}
            for s in sources
        ],
    }
