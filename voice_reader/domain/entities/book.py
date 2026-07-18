"""Domain entity: Book."""

from __future__ import annotations

from dataclasses import dataclass

from voice_reader.domain.document.model import Document


@dataclass(frozen=True, slots=True)
class Book:
    id: str
    title: str
    raw_text: str
    normalized_text: str
    # The structured view of `normalized_text`. Optional so that a book loaded
    # before the model existed, or one whose extraction was too poor to
    # structure confidently, still behaves exactly as it always has.
    document: Document | None = None
