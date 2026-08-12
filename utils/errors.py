"""
utils/errors.py — Turn provider exceptions into short, user-facing messages.

Model providers raise long structured errors: Google's quota failures carry
the full quota metric name, retry metadata and a copy of the request. That
detail belongs in the logs, not in a chat bubble or a sidebar status line, so
everything shown to a user goes through :func:`friendly_error` while the
original exception is logged untouched.
"""

from typing import Tuple

# Matched against a lower-cased string form of the exception. Providers are
# inconsistent about exception classes but consistent about these markers.
_QUOTA_MARKERS = (
    "429",
    "resource_exhausted",
    "resourceexhausted",
    "quota",
    "rate limit",
    "ratelimit",
    "too many requests",
)
_AUTH_MARKERS = (
    "api key not valid",
    "api_key_invalid",
    "invalid api key",
    "unauthenticated",
    "permission_denied",
    "permissiondenied",
    "401",
    "403",
)
_MODEL_MARKERS = (
    "not found for api version",
    "is not supported",
    "unknown model",
    "404",
)
_CONNECTION_MARKERS = (
    "connection refused",
    "connection error",
    "connect timeout",
    "timed out",
    "timeout",
    "unavailable",
    "failed to establish",
)

# Longest single-line message we will show for an unclassified error.
_MAX_DETAIL = 140


def active_provider_label() -> str:
    """Return a display name for the configured chat backend."""
    try:
        from utils.config import settings
        from utils.providers import resolve_provider

        return "Ollama" if resolve_provider(settings.llm_provider, "LLM") == "ollama" else "Gemini"
    except Exception:
        # Never let diagnostics reporting raise inside an error handler.
        return "The AI service"


def classify_error(exc: BaseException) -> str:
    """Classify *exc* as 'quota', 'auth', 'model', 'connection' or 'unknown'."""
    text = f"{type(exc).__name__} {exc}".lower()

    # Quota is checked first: a 429 often also mentions the model name.
    for marker in _QUOTA_MARKERS:
        if marker in text:
            return "quota"
    for marker in _AUTH_MARKERS:
        if marker in text:
            return "auth"
    for marker in _MODEL_MARKERS:
        if marker in text:
            return "model"
    for marker in _CONNECTION_MARKERS:
        if marker in text:
            return "connection"
    return "unknown"


def friendly_error(exc: BaseException) -> Tuple[int, str]:
    """Return an ``(http_status, short_message)`` pair for *exc*.

    The message is safe to show directly to a user: one sentence, no stack
    traces, no provider payloads.
    """
    kind = classify_error(exc)
    label = active_provider_label()

    if kind == "quota":
        return 429, f"{label} quota exhausted. Please try again in a few minutes."
    if kind == "auth":
        return 401, f"{label} rejected the API key. Check the server configuration."
    if kind == "model":
        return 502, f"The configured {label} model is unavailable."
    if kind == "connection":
        return 503, f"Can't reach {label} right now. Please try again shortly."

    # Unclassified: keep the first line of the real error, since for things
    # like a corrupt PDF that text is short and genuinely useful.
    detail = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
    if len(detail) > _MAX_DETAIL:
        detail = detail[: _MAX_DETAIL - 1].rstrip() + "…"
    return 500, detail
