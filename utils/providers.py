"""
utils/providers.py — Backend selection for LLM and embedding models.

Local development uses Ollama; a cloud deployment (Render, Fly, …) has no
Ollama server, so it uses Google Gemini instead.  Both the chat model and
the embedding model go through :func:`resolve_provider` so the two never
disagree about which backend is available.

Set ``LLM_PROVIDER`` / ``EMBEDDING_PROVIDER`` to ``ollama`` or ``gemini``
to pin a backend explicitly.  The default, ``auto``, probes Ollama first
and falls back to Gemini.
"""

import sys
from typing import Optional

from utils.config import settings

# Cache the probe result — it is only meaningful once per process and the
# probe costs a network round trip.
_ollama_reachable: Optional[bool] = None


def ollama_available(force: bool = False) -> bool:
    """Return ``True`` if the configured Ollama server answers a request."""
    global _ollama_reachable
    if _ollama_reachable is not None and not force:
        return _ollama_reachable

    try:
        import ollama as ollama_sdk

        client = ollama_sdk.Client(host=settings.ollama_base_url)
        client.list()
        _ollama_reachable = True
    except Exception as exc:
        print(f"[providers] Ollama unreachable: {exc}", file=sys.stderr)
        _ollama_reachable = False

    return _ollama_reachable


def resolve_provider(preference: str, kind: str) -> str:
    """Resolve *preference* into a concrete provider name.

    Args:
        preference: ``"auto"``, ``"ollama"`` or ``"gemini"``.
        kind:       Human-readable label used in error messages.

    Returns:
        Either ``"ollama"`` or ``"gemini"``.

    Raises:
        RuntimeError: If the requested provider is not usable.
    """
    preference = (preference or "auto").strip().lower()

    if preference == "ollama":
        return "ollama"

    if preference == "gemini":
        if not settings.has_gemini_key:
            raise RuntimeError(
                f"{kind} provider is set to 'gemini' but GEMINI_API_KEY is missing. "
                "Add it to your environment or .env file."
            )
        return "gemini"

    if preference != "auto":
        raise RuntimeError(
            f"Unknown {kind} provider '{preference}'. "
            "Use 'auto', 'ollama' or 'gemini'."
        )

    if ollama_available():
        return "ollama"

    if settings.has_gemini_key:
        return "gemini"

    raise RuntimeError(
        f"No {kind} backend available. Start Ollama locally, or set "
        "GEMINI_API_KEY to use Google Gemini."
    )
