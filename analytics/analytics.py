"""
analytics/analytics.py — Persistent document and query telemetry.

Tracks two things across restarts:

    * per-document records (pages, file type, size, when it was indexed)
    * a rolling log of answered questions with retrieval latencies

Index-level facts (chunk counts, vector width, on-disk size) are *not*
stored here — they are derived live from the Chroma collection by
``VectorStoreManager.stats()``.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

# How many individual query records to keep on disk.  Lifetime counters
# are tracked separately so trimming the log never loses the totals.
MAX_QUERY_LOG = 200


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _percentile(ordered: list[float], p: float) -> float:
    """Return the *p*-th percentile of an already-sorted list."""
    if not ordered:
        return 0.0
    idx = int(round((p / 100) * (len(ordered) - 1)))
    return ordered[min(len(ordered) - 1, max(0, idx))]


class DocumentAnalytics:
    """Manages persistent tracking of documents and query statistics."""

    def __init__(self, storage_dir: Union[str, Path] = "analytics"):
        self.storage_dir = Path(storage_dir).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.stats_file = self.storage_dir / "stats.json"

        # Maps filename -> record dict (see _normalise_record)
        self.documents: dict[str, dict] = {}
        self.queries: list[dict] = []
        self.query_totals: dict = {"count": 0, "total_latency_ms": 0.0}
        self._load()

    # -- persistence --------------------------------------------------

    @staticmethod
    def _normalise_record(value) -> dict:
        """Coerce a stored value into the current record shape.

        Earlier versions stored a bare ``int`` page count per filename;
        those files are still readable and get upgraded in place.
        """
        if isinstance(value, dict):
            return {
                "pages": value.get("pages", 0),
                "file_type": value.get("file_type", "?"),
                "size_bytes": value.get("size_bytes", 0),
                "indexed_at": value.get("indexed_at"),
            }
        return {
            "pages": int(value or 0),
            "file_type": "?",
            "size_bytes": 0,
            "indexed_at": None,
        }

    def _load(self) -> None:
        """Load the statistics from disk if they exist."""
        if not self.stats_file.exists():
            return
        try:
            with open(self.stats_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_docs = data.get("documents", {})
            self.documents = {
                name: self._normalise_record(value) for name, value in raw_docs.items()
            }
            self.queries = data.get("queries", [])
            totals = data.get("query_totals") or {}
            self.query_totals = {
                "count": totals.get("count", len(self.queries)),
                "total_latency_ms": totals.get("total_latency_ms", 0.0),
            }
        except Exception as e:
            print(f"[ERROR] Failed to load analytics stats: {e}")

    def _save(self) -> None:
        """Persist the current statistics to disk."""
        try:
            with open(self.stats_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "documents": self.documents,
                        "queries": self.queries,
                        "query_totals": self.query_totals,
                    },
                    f,
                    indent=4,
                )
        except Exception as e:
            print(f"[ERROR] Failed to save analytics stats: {e}")

    # -- documents ----------------------------------------------------

    def add_document(
        self,
        filename: str,
        page_count: int,
        file_type: str = "?",
        size_bytes: int = 0,
    ) -> None:
        """Track a newly indexed document, deduplicating by filename."""
        self.documents[filename] = {
            "pages": page_count,
            "file_type": file_type,
            "size_bytes": size_bytes,
            "indexed_at": _now_iso(),
        }
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

    # -- queries ------------------------------------------------------

    def record_query(
        self,
        question: str,
        latency_ms: float,
        chunks_retrieved: int = 0,
        sources: Optional[list[str]] = None,
        doc_filter: Optional[str] = None,
        answer_chars: int = 0,
    ) -> None:
        """Append a single answered question to the rolling query log."""
        self.queries.append(
            {
                "question": question[:300],
                "latency_ms": round(latency_ms, 1),
                "chunks_retrieved": chunks_retrieved,
                "sources": sources or [],
                "doc_filter": doc_filter,
                "answer_chars": answer_chars,
                "at": _now_iso(),
            }
        )
        if len(self.queries) > MAX_QUERY_LOG:
            self.queries = self.queries[-MAX_QUERY_LOG:]

        self.query_totals["count"] += 1
        self.query_totals["total_latency_ms"] += latency_ms
        self._save()

    def get_query_stats(self) -> dict:
        """Summarise the query log into latency and usage statistics."""
        lifetime = self.query_totals.get("count", 0)
        latencies = sorted(q.get("latency_ms", 0) for q in self.queries)
        chunk_counts = [q.get("chunks_retrieved", 0) for q in self.queries]

        # Most-repeated questions, compared case-insensitively.
        counter: dict[str, dict] = {}
        for q in self.queries:
            key = q.get("question", "").strip().lower()
            if not key:
                continue
            entry = counter.setdefault(key, {"question": q["question"], "count": 0})
            entry["count"] += 1
        top = sorted(counter.values(), key=lambda e: e["count"], reverse=True)[:5]

        return {
            "total_queries": lifetime,
            "logged_queries": len(self.queries),
            "avg_latency_ms": round(
                self.query_totals.get("total_latency_ms", 0.0) / lifetime, 1
            )
            if lifetime
            else 0,
            "p50_latency_ms": round(_percentile(latencies, 50), 1),
            "p95_latency_ms": round(_percentile(latencies, 95), 1),
            "max_latency_ms": round(latencies[-1], 1) if latencies else 0,
            "avg_chunks_retrieved": round(sum(chunk_counts) / len(chunk_counts), 2)
            if chunk_counts
            else 0,
            "top_questions": top,
            "recent": list(reversed(self.queries[-8:])),
        }

    # -- aggregate ----------------------------------------------------

    def get_analytics(self) -> dict:
        """Calculate and return the current total statistics."""
        total_docs = len(self.documents)
        total_pages = sum(r.get("pages", 0) for r in self.documents.values())
        return {
            "total_documents": total_docs,
            "total_pages": total_pages,
            "total_bytes": sum(r.get("size_bytes", 0) for r in self.documents.values()),
            "documents": self.documents,
        }


if __name__ == "__main__":
    analytics = DocumentAnalytics()
    stats = analytics.get_analytics()
    queries = analytics.get_query_stats()

    print("=================================")
    print("DOCUMENT ANALYTICS")
    print("=================================")
    print(f"Total Documents Processed: {stats['total_documents']}")
    print(f"Total Pages Analyzed: {stats['total_pages']}")
    print(f"Total Queries Answered: {queries['total_queries']}")
    print(f"Average Latency: {queries['avg_latency_ms']} ms")
    print("=================================")
