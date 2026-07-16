"""
ingestion/loader.py — Document loading for PDF, DOCX, and TXT files.

Provides the ``DocumentLoader`` class which can load individual files and
recursively scan directories for supported document types.
"""

import sys
from pathlib import Path
from typing import Union






class UnsupportedFileTypeError(Exception):
    """Raised when a file's extension is not in the supported set."""
    pass






SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}






class DocumentLoader:
    """Load text content from PDF, DOCX, or TXT files on disk."""



    @staticmethod
    def _load_pdf(path: Path) -> tuple[str, int]:
        """Extract text from a PDF using pypdf.

        Handles encrypted PDFs gracefully by attempting to decrypt with
        an empty password (which covers the common "owner-password-only"
        case).  If decryption fails, raises a RuntimeError.
        """
        from pypdf import PdfReader

        try:
            reader = PdfReader(str(path))


            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception:
                    raise RuntimeError(
                        f"PDF '{path.name}' is encrypted and could not be "
                        "decrypted with an empty password."
                    )

            pages_text = [
                page.extract_text() or "" for page in reader.pages
            ]
            return "\n".join(pages_text), len(reader.pages)

        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Failed to read PDF '{path.name}': {exc}") from exc

    @staticmethod
    def _load_docx(path: Path) -> tuple[str, int]:
        """Extract text from a DOCX file using python-docx."""
        from docx import Document as DocxDocument

        try:
            doc = DocxDocument(str(path))
            return "\n".join(para.text for para in doc.paragraphs), 0
        except Exception as exc:
            raise RuntimeError(
                f"Failed to read DOCX '{path.name}': {exc}"
            ) from exc

    @staticmethod
    def _load_txt(path: Path) -> tuple[str, int]:
        """Read a plain-text file, trying UTF-8 first, then latin-1."""
        try:
            return path.read_text(encoding="utf-8"), 0
        except UnicodeDecodeError:
            return path.read_text(encoding="latin-1"), 0
        except Exception as exc:
            raise RuntimeError(
                f"Failed to read TXT '{path.name}': {exc}"
            ) from exc



    def load(self, path: Union[str, Path]) -> dict:
        """Load a single document and return its content with metadata.

        Args:
            path: Path to a supported document file.

        Returns:
            A dict with keys ``text``, ``filename``, ``file_type``, and
            ``filepath``.

        Raises:
            UnsupportedFileTypeError: If the file extension is not
                ``.pdf``, ``.docx``, or ``.txt``.
            FileNotFoundError: If *path* does not exist.
        """
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        ext = path.suffix.lower()

        if ext not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFileTypeError(
                f"Unsupported file type '{ext}'. "
                f"Supported types: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        loaders = {
            ".pdf": self._load_pdf,
            ".docx": self._load_docx,
            ".txt": self._load_txt,
        }

        try:
            text, page_count = loaders[ext](path)
        except Exception as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            raise

        return {
            "text": text,
            "filename": path.name,
            "file_type": ext.lstrip("."),
            "filepath": str(path),
            "page_count": page_count,
        }

    def scan_directory(self, directory: Union[str, Path]) -> list[Path]:
        """Recursively find all supported documents in *directory*.

        Skips hidden files and directories (names starting with ``"."``).

        Args:
            directory: Local folder path to scan.

        Returns:
            Sorted list of ``Path`` objects for every matching file.

        Raises:
            FileNotFoundError: If *directory* does not exist or is not a
                directory.
        """
        directory = Path(directory).resolve()

        if not directory.exists():
            raise FileNotFoundError(
                f"Directory does not exist: {directory}"
            )
        if not directory.is_dir():
            raise FileNotFoundError(
                f"Path is not a directory: {directory}"
            )

        matched: list[Path] = []

        for item in sorted(directory.rglob("*")):

            if any(part.startswith(".") for part in item.parts):
                continue
            if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS:
                matched.append(item)

        return matched
