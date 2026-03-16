from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FakeIdeasRepo:
    """Simple stub for IdeaIndexRepository used in UI/controller tests."""

    doc: dict | None = None

    def load_doc(self, *, book_id: str):
        del book_id
        return self.doc

    def save_doc_atomic(self, *, book_id: str, doc: dict) -> None:
        del book_id, doc

