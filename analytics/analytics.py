import json
import os
from pathlib import Path
from typing import Union

class DocumentAnalytics:
    """Manages persistent tracking of document and page counts."""
    
    def __init__(self, storage_dir: Union[str, Path] = "analytics"):
        self.storage_dir = Path(storage_dir).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.stats_file = self.storage_dir / "stats.json"
        
        # Maps filename to page_count
        self.documents: dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        """Load the statistics from disk if they exist."""
        if self.stats_file.exists():
            try:
                with open(self.stats_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.documents = data.get("documents", {})
            except Exception as e:
                print(f"[ERROR] Failed to load analytics stats: {e}")

    def _save(self) -> None:
        """Persist the current statistics to disk."""
        try:
            with open(self.stats_file, "w", encoding="utf-8") as f:
                json.dump({"documents": self.documents}, f, indent=4)
        except Exception as e:
            print(f"[ERROR] Failed to save analytics stats: {e}")

    def add_document(self, filename: str, page_count: int) -> None:
        """Track a newly indexed document, automatically deduplicating by filename."""
        self.documents[filename] = page_count
        self._save()

    def remove_document(self, filename: str) -> None:
        """Remove a document from the statistics."""
        if filename in self.documents:
            del self.documents[filename]
            self._save()

    def sync(self, actual_filenames: list[str]) -> None:
        """Remove any tracked documents that are no longer in the actual list."""
        stale_docs = [fn for fn in self.documents if fn not in actual_filenames]
        if stale_docs:
            for fn in stale_docs:
                del self.documents[fn]
            self._save()

    def get_analytics(self) -> dict:
        """Calculate and return the current total statistics."""
        total_docs = len(self.documents)
        total_pages = sum(self.documents.values())
        return {
            "total_documents": total_docs,
            "total_pages": total_pages
        }

if __name__ == "__main__":
    # Provides the requested CLI output
    analytics = DocumentAnalytics()
    stats = analytics.get_analytics()
    
    print("=================================")
    print("DOCUMENT ANALYTICS")
    print("=================================")
    print(f"Total Documents Processed: {stats['total_documents']}")
    print(f"Total Pages Analyzed: {stats['total_pages']}")
    print("=================================")
