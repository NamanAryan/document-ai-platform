import json
import os
from pathlib import Path
from typing import Union, Optional

class FAQManager:
    """Manages persistent storage of dynamically generated FAQs."""
    
    def __init__(self, storage_dir: Union[str, Path] = "analytics"):
        self.storage_dir = Path(storage_dir).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.faqs_file = self.storage_dir / "faqs.json"
        
        # Maps filename to list of questions
        self.faqs: dict[str, list[str]] = {}
        self._load()

    def _load(self) -> None:
        """Load FAQs from disk if they exist."""
        if self.faqs_file.exists():
            try:
                with open(self.faqs_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.faqs = data.get("faqs", {})
            except Exception as e:
                print(f"[ERROR] Failed to load FAQs: {e}")

    def _save(self) -> None:
        """Persist FAQs to disk."""
        try:
            with open(self.faqs_file, "w", encoding="utf-8") as f:
                json.dump({"faqs": self.faqs}, f, indent=4)
        except Exception as e:
            print(f"[ERROR] Failed to save FAQs: {e}")

    def save_faqs(self, filename: str, questions: list[str]) -> None:
        """Save a list of questions for a specific document."""
        self.faqs[filename] = questions
        self._save()

    def get_faqs(self, filename: str) -> Optional[list[str]]:
        """Retrieve FAQs for a specific document, if available."""
        return self.faqs.get(filename)

    def remove_faqs(self, filename: str) -> None:
        """Remove FAQs for a document from storage."""
        if filename in self.faqs:
            del self.faqs[filename]
            self._save()
