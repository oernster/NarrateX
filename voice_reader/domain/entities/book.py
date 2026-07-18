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

    @property
    def document_model(self) -> Document:
        """The book's structure, as one unbroken run when there is none.

        Every consumer wants a model rather than a model-or-nothing, so the
        fallback lives here instead of at each call site. Answering with a real
        document keeps the renderer and the narrator on a single code path, and
        keeps that path exercised for well-structured books too.
        """

        return self.document or Document.unstructured(text=self.normalized_text)
