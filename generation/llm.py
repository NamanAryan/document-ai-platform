"""
generation/llm.py — LLM initialisation with Ollama primary and Gemini fallback.

Exposes a module-level ``llm`` object that other modules can import
directly:

    from generation.llm import get_llm
"""

import sys
from utils.config import settings

# Cached singleton — avoids re-pinging Ollama on every request
_llm = None


def get_llm():
    """Initialise and return a LangChain chat LLM (cached after first call).

    Strategy:
    1. Try to connect to the local Ollama server.  If it responds,
       return a ``ChatOllama`` instance.
    2. If Ollama is unreachable, fall back to Google Gemini
       (``ChatGoogleGenerativeAI``).  Raises ``RuntimeError`` when the
       Gemini API key is also missing.

    Returns:
        A LangChain ``BaseChatModel`` instance.
    """
    global _llm
    if _llm is not None:
        return _llm

    try:
        import ollama as ollama_sdk

        client = ollama_sdk.Client(host=settings.ollama_base_url)
        client.list()

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
        return _llm

    except Exception as exc:
        print(
            f"[LLM] Ollama unreachable ({exc}). "
            "Attempting Gemini fallback …",
            file=sys.stderr,
        )

    try:
        api_key = settings.gemini_api_key
    except ValueError as exc:
        raise RuntimeError(
            "Neither Ollama nor Gemini is available.  "
            "Start Ollama or set GEMINI_API_KEY in your .env file."
        ) from exc

    from langchain_google_genai import ChatGoogleGenerativeAI

    _llm = ChatGoogleGenerativeAI(
        model="gemini-pro",
        google_api_key=api_key,
        temperature=0.2,
    )
    print("[LLM] Using Google Gemini (fallback)  ·  model=gemini-pro", file=sys.stderr)
    return _llm

