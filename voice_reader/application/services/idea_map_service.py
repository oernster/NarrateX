"""Application service: load persisted Ideas indexes.

Phase 1 scope: load-only and index existence checks.

Indexing/generation and UI dialog presentation are added in later phases.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from voice_reader.domain.interfaces.idea_index_repository import IdeaIndexRepository

_SUPPORTED_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class IdeaMapService:
    repo: IdeaIndexRepository

    @staticmethod
    def fingerprint_sha256(*, normalized_text: str) -> str:
        """Compute a stable fingerprint for a book's normalized text.

        This is used for caching/invalidation so we can detect when the persisted
        idea-map no longer matches the loaded book content.
        """

        text = str(normalized_text or "")
        return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()

    def has_completed_index(self, *, book_id: str) -> bool:
        """Return True if a persisted, minimally valid index exists."""

        doc = self.repo.load_doc(book_id=book_id)
        if not isinstance(doc, dict):
            return False

        # Minimal structural validation.
        if int(doc.get("schema_version", 0) or 0) != _SUPPORTED_SCHEMA_VERSION:
            return False

        status = doc.get("status")
        if not isinstance(status, dict):
            return False

        return str(status.get("state", "")) == "completed"

    def has_completed_index_for_text(
        self, *, book_id: str, normalized_text: str
    ) -> bool:
        """Return True if a completed index exists and matches the book content.

        Phase 5 adds fingerprint-based caching/invalidation: if the persisted
        fingerprint is missing or doesn't match, treat the book as unindexed.
        """

        expected = self.fingerprint_sha256(normalized_text=normalized_text)

        doc = self.repo.load_doc(book_id=book_id)
        if not isinstance(doc, dict):
            return False  # pragma: no cover

        if int(doc.get("schema_version", 0) or 0) != _SUPPORTED_SCHEMA_VERSION:
            return False

        status = doc.get("status")
        if not isinstance(status, dict):
            return False
        if str(status.get("state", "")) != "completed":
            return False

        book = doc.get("book")
        if not isinstance(book, dict):
            return False
        fingerprint = str(book.get("fingerprint_sha256", "") or "").strip()
        if not fingerprint:
            return False
        return fingerprint == expected

    def load_index_doc(self, *, book_id: str) -> dict | None:
        """Load the raw persisted index doc for the given book."""

        return self.repo.load_doc(book_id=book_id)
