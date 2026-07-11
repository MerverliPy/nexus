"""Voice input — record, transcribe, parse intent."""

import json
import re
import subprocess
import tempfile
from pathlib import Path

from nexus.config import get_settings


def record_audio(duration: int = 5) -> Path | None:
    """Record audio from default mic using arecord. Returns WAV file path or None."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    path = Path(tmp.name)

    try:
        subprocess.run(
            ["arecord", "-d", str(duration), "-f", "cd", "-t", "wav", str(path)],
            capture_output=True,
            text=True,
            timeout=duration + 5,
            check=True,
        )
        return path
    except (subprocess.CalledProcessError, FileNotFoundError):
        if path.exists():
            path.unlink()
        return None


def transcribe_audio(audio_path: Path) -> str | None:
    """Transcribe audio file using OpenAI Whisper API.

    Returns transcribed text or None if unavailable.
    """
    settings = get_settings()
    api_key = settings.openai_api_key
    if not api_key:
        return None

    import base64

    import httpx

    audio_bytes = audio_path.read_bytes()
    audio_b64 = base64.b64encode(audio_bytes).decode()

    try:
        resp = httpx.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            data={
                "model": "whisper-1",
                "response_format": "text",
            },
            files={
                "file": ("audio.wav", audio_bytes, "audio/wav"),
            },
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.text.strip()
        return None
    except Exception:
        return None


def parse_intent(text: str) -> dict:
    """Parse a natural language command into intent + entities.

    Uses regex-based patterns with fallback keyword detection.
    Returns: {"intent": str, "entities": dict}
    """
    text_lower = text.lower().strip()

    # ── Finance: log expenses ──────────────────────────────────────────
    # "log 50 dollars for coffee" / "spent 20 at starbucks" / "$15 lunch"
    finance_patterns = [
        r"(?:log|spent|paid|spend)\s+\$?(\d+(?:\.\d{2})?)\s*(?:dollars?|bucks?)?\s*(?:for|on|at)?\s*(.+)",
        r"\$(\d+(?:\.\d{2})?)\s+(?:for|on|at)?\s*(.+)",
    ]
    for pat in finance_patterns:
        m = re.match(pat, text_lower)
        if m:
            return {
                "intent": "finance_log",
                "entities": {
                    "amount": float(m.group(1)),
                    "vendor": m.group(2).strip(),
                },
            }

    # ── Task: reminders / todo ─────────────────────────────────────────
    # "remind me to X" / "add task X" / "todo X"
    task_patterns = [
        r"remind\s+me\s+to\s+(.+)",
        r"add\s+task\s+(.+)",
        r"todo\s+(.+)",
        r"remember\s+to\s+(.+)",
    ]
    for pat in task_patterns:
        m = re.match(pat, text_lower)
        if m:
            return {
                "intent": "task_add",
                "entities": {"title": m.group(1).strip()},
            }

    # ── Finance: balance / query ───────────────────────────────────────
    if any(kw in text_lower for kw in ["balance", "how much money", "whats my balance"]):
        return {"intent": "finance_balance", "entities": {}}

    # ── Finance: recent transactions ───────────────────────────────────
    if any(kw in text_lower for kw in ["last transaction", "recent transaction", "last purchase"]):
        return {"intent": "finance_recent", "entities": {}}

    # ── Fallback: unknown ──────────────────────────────────────────────
    return {"intent": "unknown", "entities": {"raw": text}}


def _openrouter_completion(prompt: str, system: str = "") -> str | None:
    """Call OpenRouter API for LLM-based intent parsing fallback."""
    settings = get_settings()
    api_key = settings.openrouter_api_key
    if not api_key:
        return None

    import httpx

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.llm_default_model,
                "messages": messages,
                "max_tokens": 200,
                "temperature": 0,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        return None
    except Exception:
        return None


def parse_intent_llm(text: str) -> dict:
    """Use LLM to parse natural language into intent (fallback for complex commands)."""
    system = (
        "You are a command parser. Return ONLY valid JSON with keys: "
        '"intent" (one of: finance_log, task_add, finance_balance, finance_recent, unknown), '
        '"entities" (object with relevant fields like amount, vendor, title). '
        'Example: {"intent":"finance_log","entities":{"amount":50,"vendor":"coffee"}}'
    )
    prompt = f"Parse this command: {text}"

    result = _openrouter_completion(prompt, system)
    if result:
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            pass
    return {"intent": "unknown", "entities": {"raw": text}}
