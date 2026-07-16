"""
retrieval/retriever.py — Similarity search retriever.

Provides a thin convenience wrapper that exposes the VectorStoreManager's
similarity search as a LangChain-compatible retriever.
"""

from typing import Optional
from langchain_core.documents import Document
from retrieval.vector_store import VectorStoreManager
from utils.config import settings


def retrieve(query: str, vector_store: VectorStoreManager, k: Optional[int] = None) -> list[Document]:
    """Retrieve the top-k most relevant chunks for *query*.

    Args:
        query:        The user's question.
        vector_store: An initialised ``VectorStoreManager``.
        k:            Number of results (default from settings).

    Returns:
        List of ``Document`` objects with content and metadata.
    """
    k = k or settings.top_k_results
    return vector_store.similarity_search(query, k=k)
