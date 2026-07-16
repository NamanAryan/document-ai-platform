"""
ingestion/chunker.py — Text splitting with configurable overlap.

Uses LangChain's ``RecursiveCharacterTextSplitter`` to break large
documents into smaller, overlapping chunks while preserving natural
text boundaries (paragraphs → sentences → words).
"""

import sys
from typing import Optional
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from utils.config import settings


class TextChunker:
    """Split text into overlapping chunks and attach metadata.

    Args:
        chunk_size:    Maximum characters per chunk (default from settings).
        chunk_overlap: Overlap between consecutive chunks (default from settings).
    """

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> None:
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap

        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

    def chunk(self, text: str, metadata: dict) -> list[Document]:
        """Split *text* into LangChain ``Document`` objects with metadata.

        Each returned ``Document`` carries the original *metadata* dict
        plus an additional ``chunk_index`` key indicating its position in
        the split sequence.

        Args:
            text:     The raw document text to split.
            metadata: Base metadata dict (filename, file_type, filepath).

        Returns:
            List of ``Document`` objects ready for embedding.
        """
        raw_chunks = self._splitter.split_text(text)

        documents: list[Document] = []
        for idx, chunk_text in enumerate(raw_chunks):
            doc_metadata = {**metadata, "chunk_index": idx}
            documents.append(
                Document(page_content=chunk_text, metadata=doc_metadata)
            )

        print(
            f"  ↳ Split into {len(documents)} chunk(s) "
            f"(size={self.chunk_size}, overlap={self.chunk_overlap})",
            file=sys.stderr,
        )
        return documents
