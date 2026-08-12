"""
ingestion/embedder.py — Embedding generation via Ollama or Google Gemini.

Which backend is used depends on ``EMBEDDING_PROVIDER`` (see
``utils.providers``).  Local development normally uses Ollama; cloud
deployments use Gemini because there is no Ollama server to talk to.

IMPORTANT: embeddings from different models are not comparable, and they
often differ in width.  Switching provider or model means the existing
Chroma collection must be deleted and the documents re-indexed.
"""

import sys

from langchain_core.embeddings import Embeddings

from utils.config import settings
from utils.providers import resolve_provider

# Cached singleton — the model object is stateless but constructing it
# validates credentials, so we only want to do it once.
_embeddings: Embeddings = None


def get_embedding_model() -> Embeddings:
    """Return the configured embedding model (cached after first call)."""
    global _embeddings
    if _embeddings is not None:
        return _embeddings

    provider = resolve_provider(settings.embedding_provider, "Embedding")

    if provider == "ollama":
        from langchain_ollama import OllamaEmbeddings

        _embeddings = OllamaEmbeddings(
            model=settings.ollama_embedding_model,
            base_url=settings.ollama_base_url,
            keep_alive=-1,
        )
        print(
            f"[Embeddings] Using Ollama  ·  model={settings.ollama_embedding_model}",
            file=sys.stderr,
        )
    else:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        _embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.gemini_embedding_model,
            google_api_key=settings.gemini_api_key,
        )
        print(
            f"[Embeddings] Using Google Gemini  ·  model={settings.gemini_embedding_model}",
            file=sys.stderr,
        )

    return _embeddings


def active_embedding_model() -> str:
    """Return the model name currently configured, for diagnostics."""
    try:
        provider = resolve_provider(settings.embedding_provider, "Embedding")
    except RuntimeError:
        return "unavailable"
    return (
        settings.ollama_embedding_model
        if provider == "ollama"
        else settings.gemini_embedding_model
    )
