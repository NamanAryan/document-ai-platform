"""
ingestion/embedder.py — Embedding generation via Ollama.

Thin wrapper around LangChain's OllamaEmbeddings for convenience and
consistent configuration.
"""

from langchain_ollama import OllamaEmbeddings
from utils.config import settings


def get_embedding_model() -> OllamaEmbeddings:
    """Return an ``OllamaEmbeddings`` instance configured from settings."""
    return OllamaEmbeddings(
        model=settings.ollama_embedding_model,
        base_url=settings.ollama_base_url,
        keep_alive=-1,
    )
