"""Embedding service for semantic note search.

Pluggable with graceful degradation:
  1. OpenAI ``text-embedding-3-small`` (1536-dim) when ``openai`` is installed
     and an API key is configured.
  2. ``sentence-transformers`` local model when installed (padded/truncated to
     the target dimension).
  3. Otherwise returns ``None`` — callers fall back to full-text search.

The Note.embedding column is ``Vector(1536)``; all providers normalize to that
dimension so stored vectors are comparable.
"""

from __future__ import annotations

import os

import structlog

from nexus.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

EMBEDDING_DIM = 1536

_openai_client = None
_st_model = None
_provider_checked = False
_active_provider: str | None = None


def _detect_provider() -> str | None:
    """Determine which embedding provider is available (cached)."""
    global _provider_checked, _active_provider, _openai_client, _st_model
    if _provider_checked:
        return _active_provider
    _provider_checked = True

    # 1. OpenAI
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        try:
            import openai

            _openai_client = openai.OpenAI(api_key=api_key)
            _active_provider = "openai"
            logger.info("embedding_provider", provider="openai")
            return _active_provider
        except ImportError:
            pass

    # 2. sentence-transformers (local)
    try:
        from sentence_transformers import SentenceTransformer

        model_name = os.environ.get("NEXUS_ST_MODEL", "all-MiniLM-L6-v2")
        _st_model = SentenceTransformer(model_name)
        _active_provider = "sentence-transformers"
        logger.info("embedding_provider", provider="sentence-transformers", model=model_name)
        return _active_provider
    except Exception:  # noqa: BLE001 - not installed or model download failed
        pass

    logger.warning("embedding_provider_unavailable")
    _active_provider = None
    return None


def _pad_or_truncate(vec: list[float], dim: int = EMBEDDING_DIM) -> list[float]:
    """Normalize a vector to exactly ``dim`` dimensions."""
    if len(vec) == dim:
        return vec
    if len(vec) > dim:
        return vec[:dim]
    return vec + [0.0] * (dim - len(vec))


def embed(text: str) -> list[float] | None:
    """Return an embedding vector for ``text``, or None if no provider."""
    if not text or not text.strip():
        return None

    provider = _detect_provider()
    if provider is None:
        return None

    try:
        if provider == "openai" and _openai_client is not None:
            resp = _openai_client.embeddings.create(model="text-embedding-3-small", input=text)
            return _pad_or_truncate(list(resp.data[0].embedding))
        if provider == "sentence-transformers" and _st_model is not None:
            vec = _st_model.encode(text).tolist()
            return _pad_or_truncate(list(vec))
    except Exception as exc:  # noqa: BLE001
        logger.error("embedding_failed", provider=provider, error=str(exc))
    return None


def is_available() -> bool:
    """True when a real embedding provider is configured."""
    return _detect_provider() is not None
