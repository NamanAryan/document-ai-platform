"""
generation/llm.py — Chat model initialisation for Ollama or Google Gemini.

Exposes a single accessor that other modules import:

    from generation.llm import get_llm

Which backend is used depends on ``LLM_PROVIDER`` (see ``utils.providers``).
Pin it to ``gemini`` in a cloud deployment so start-up does not waste time
probing an Ollama server that will never answer.
"""

import sys

from utils.config import settings
from utils.providers import resolve_provider

# Cached singleton — avoids re-pinging the backend on every request.
_llm = None


def get_llm():
    """Initialise and return a LangChain chat model (cached after first call).

    Returns:
        A LangChain ``BaseChatModel`` instance.

    Raises:
        RuntimeError: If no backend is configured or reachable.
    """
    global _llm
    if _llm is not None:
        return _llm

    provider = resolve_provider(settings.llm_provider, "LLM")

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        _llm = ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0.2,
            keep_alive=-1,
        )
        print(
            f"[LLM] Using Ollama  ·  model={settings.ollama_model}  "
            f"·  base_url={settings.ollama_base_url}",
            file=sys.stderr,
        )
    else:
        from langchain_google_genai import ChatGoogleGenerativeAI

        _llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=0.2,
        )
        print(
            f"[LLM] Using Google Gemini  ·  model={settings.gemini_model}",
            file=sys.stderr,
        )

    return _llm
