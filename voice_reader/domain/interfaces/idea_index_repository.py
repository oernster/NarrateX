"""Domain protocol for persisted Ideas indexes."""

from __future__ import annotations

from typing import Protocol


class IdeaIndexRepository(Protocol):
    """Load and persist per-book idea-map index documents."""

    def load_doc(self, *, book_id: str) -> dict | None:
        """Return the persisted index doc, or None if missing/invalid."""

    def save_doc_atomic(self, *, book_id: str, doc: dict) -> None:
        """Persist the index doc atomically (write temp then replace)."""
