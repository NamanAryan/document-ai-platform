"""
retrieval/vector_store.py — ChromaDB-backed vector store manager.

Handles document embedding, storage, deduplication, and similarity
search using a persistent ChromaDB collection.
"""

import hashlib
import os
import sys
from pathlib import Path

from typing import Optional
from langchain_core.documents import Document
from langchain_chroma import Chroma

from ingestion.embedder import get_embedding_model
from utils.config import settings


class VectorStoreManager:
    """Manage a persistent ChromaDB vector store for document embeddings.

    The store persists to disk at ``settings.chroma_persist_dir`` so that
    indexed data survives across sessions.

    Args:
        persist_dir: Override for the persistence directory
                     (default: ``settings.chroma_persist_dir``).
    """

    COLLECTION_NAME = "docaiapp_docs"

    def __init__(self, persist_dir: Optional[str] = None) -> None:
        self.persist_dir = persist_dir or settings.chroma_persist_dir


        Path(self.persist_dir).mkdir(parents=True, exist_ok=True)

        self._embedding_fn = get_embedding_model()


        self._store = Chroma(
            collection_name=self.COLLECTION_NAME,
            embedding_function=self._embedding_fn,
            persist_directory=self.persist_dir,
        )



    def add_documents(self, documents: list[Document]) -> None:
        """Embed and store *documents* in the ChromaDB collection.

        Each document receives a deterministic ID built from its
        ``filepath`` and ``chunk_index`` metadata so that re-indexing the
        same file does not create duplicates.
        """
        if not documents:
            return


        ids: list[str] = []
        for doc in documents:
            fp = doc.metadata.get("filepath", "unknown")
            ci = doc.metadata.get("chunk_index", 0)
            raw_id = f"{fp}::chunk_{ci}"
            ids.append(hashlib.sha256(raw_id.encode()).hexdigest())

        self._store.add_documents(documents, ids=ids)
        print(
            f"  ↳ Stored {len(documents)} chunk(s) in ChromaDB.",
            file=sys.stderr,
        )

    def similarity_search(self, query: str, k: Optional[int] = None, doc_filter: Optional[str] = None) -> list[Document]:
        """Return the *k* most similar documents for *query*.

        Args:
            query: The user's natural-language question.
            k:     Number of results (default: ``settings.top_k_results``).
            doc_filter: Optional filename to filter the search results.

        Returns:
            List of ``Document`` objects, each with content and metadata.
        """
        k = k or settings.top_k_results
        filter_dict = {"filename": doc_filter} if doc_filter else None
        return self._store.similarity_search(query, k=k, filter=filter_dict)

    def collection_exists(self, filepath: str) -> bool:
        """Check whether *filepath* has already been indexed.

        Uses the file path **and** its modification time: if the file has
        been modified since last indexing, this returns ``False`` so it
        gets re-indexed.
        """
        try:
            mtime = str(os.path.getmtime(filepath))
        except OSError:
            return False


        collection = self._store._collection
        results = collection.get(
            where={"filepath": filepath},
            limit=1,
            include=["metadatas"],
        )

        if not results["ids"]:
            return False


        stored_mtime = results["metadatas"][0].get("mtime") if results["metadatas"] else None
        return stored_mtime == mtime

    def list_indexed_documents(self) -> list[str]:
        """Return the unique filenames currently stored in the collection."""
        collection = self._store._collection
        results = collection.get(include=["metadatas"])

        filenames: set[str] = set()
        for meta in results.get("metadatas", []):
            if meta and "filename" in meta:
                filenames.add(meta["filename"])

        return sorted(filenames)

    def has_documents(self) -> bool:
        """Return ``True`` if the collection contains at least one document."""
        collection = self._store._collection
        return collection.count() > 0

    def delete_document(self, filename: str) -> bool:
        """Delete a document by filename from the vector store."""
        collection = self._store._collection
        
        # Check if it exists
        results = collection.get(
            where={"filename": filename},
            limit=1,
            include=["metadatas"],
        )
        if not results["ids"]:
            return False

        # Delete from ChromaDB
        collection.delete(where={"filename": filename})
        return True
