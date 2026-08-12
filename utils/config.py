"""
utils/config.py — Centralised configuration for DocAIApp.

Loads all settings from a .env file (via python-dotenv) and exposes them
through a singleton `settings` object.  Every other module should import:

    from utils.config import settings
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional


class Config:
    """Application configuration backed by environment variables.

    Attributes are lazily validated: a ``ValueError`` is raised only when
    a *required* variable is actually accessed and found to be missing.
    All other variables have sensible defaults.
    """

    def __init__(self) -> None:

        env_path = Path(__file__).resolve().parent.parent / ".env"
        load_dotenv(dotenv_path=env_path)


        self.ollama_base_url: str = os.getenv(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        )
        self.ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3")
        self.ollama_embedding_model: str = os.getenv(
            "OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"
        )
        self.chroma_persist_dir: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
        self.chunk_size: int = int(os.getenv("CHUNK_SIZE", "500"))
        self.chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "50"))
        self.top_k_results: int = int(os.getenv("TOP_K_RESULTS", "5"))
        self.docs_dir: str = os.getenv("DOCS_DIR", "./documents")


        self._gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")

        # Backend selection: "auto" probes Ollama and falls back to Gemini.
        # Cloud deployments should pin these to "gemini".
        self.llm_provider: str = os.getenv("LLM_PROVIDER", "auto")
        self.embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "auto")

        # Model names are configurable because hosted model identifiers are
        # retired and replaced far more often than this code changes.
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
        self.gemini_embedding_model: str = os.getenv(
            "GEMINI_EMBEDDING_MODEL", "gemini-embedding-2-preview"
        )

        # Comma-separated list of allowed browser origins.  "*" is fine for
        # local use; a split frontend/backend deployment should name the
        # frontend origin explicitly.
        self.cors_allow_origins: list[str] = [
            origin.strip()
            for origin in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")
            if origin.strip()
        ]

    @property
    def has_gemini_key(self) -> bool:
        """Return ``True`` if a usable Gemini API key is configured."""
        return bool(self._gemini_api_key) and not self._gemini_api_key.startswith("your_")

    @property
    def gemini_api_key(self) -> str:
        """Return the Gemini API key, raising if it was never configured."""
        if not self.has_gemini_key:
            raise ValueError(
                "GEMINI_API_KEY is not set.  Add it to your .env file or "
                "export it as an environment variable."
            )
        return self._gemini_api_key






settings = Config()
